#!/usr/bin/env python3
"""Manage provider-neutral resumable Agent execution and result persistence."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Callable, IO, Iterator, Sequence

SCHEMA_VERSION = "0.1.0"
AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ROLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
CHANGED_PATH_PATTERN = r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[^\r\n]+$"
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
DISPATCH_ID = re.compile(r"^dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
DEFAULT_SANDBOX = None
ACTORS = ("main", "human")
HUMAN_APPROVAL_POLICIES = ("required", "bypass")
ACTIVE_STATES = {"accepted", "queued", "starting", "running", "cancelling"}
TERMINAL_STATES = {"completed", "needs-human-decision", "failed", "cancelled"}
MAX_REQUEST_BYTES = None
MAX_EVENT_BYTES = None
MAX_EVENTS_BYTES = None
MAX_STDERR_BYTES = None
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_CAPABILITY_BINDING_BYTES = 256 * 1024
PROCESS_TERM_TIMEOUT = 5.0
PROCESS_KILL_TIMEOUT = 5.0
CONTAINMENT_START_TIMEOUT = 5.0
CONTAINMENT_QUERY_TIMEOUT = 2.0
SYSTEMD_UNIT = re.compile(r"^agent-factory-[a-f0-9]{24}\.service$")
SYSTEMD_DESCRIPTION_PREFIX = "Agent Factory containment "
SYSTEMD_REQUIRED_OPTIONS = (
    "--collect",
    "--service-type=",
    "--property=",
    "--working-directory=",
    "--unit=",
    "--description=",
    "--user",
)
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CGROUP_ROOT = Path("/sys/fs/cgroup")
SCRIPT_PATH = Path(__file__).resolve()
PLUGIN_ROOT = SCRIPT_PATH.parents[1]
PROMPTS = PLUGIN_ROOT / "skills" / "agent" / "prompt"
sys.dont_write_bytecode = True
sys.path.insert(0, str(PLUGIN_ROOT / "runtime"))
from system import sandbox as sandbox_diagnostics
from execution import lessons as lesson_capture
from execution import worktrees
from storage.files import response_operation
from execution import policy as execution_policy
from storage.errors import ContractError
from execution.usage import UsageAccumulator, record_attempt
from system import portable
from system import containment as process_containment
from system.containment import (
    require_managed_platform,
    now,
    parse_time,
    linux_boot_id,
    linux_process_identity,
    process_identity,
    process_identity_status,
    _systemd_command,
    systemd_environment_supported,
    cgroup_v2_available,
    systemd_manager_usable,
    _systemd_environment_line,
    create_systemd_environment_file,
    systemd_unit_name,
    validate_containment,
    _parse_systemd_show,
    systemd_cgroup_populated,
    query_systemd_containment,
    _systemd_signal,
    wait_containment_empty,
    containment_is_empty,
    request_containment_stop,
    force_containment_stop,
    containment_bootstrap,
    spawn_contained_process,
    release_contained_process,
    abort_contained_process,
)
from storage import files as runtime_storage
from storage.files import (
    emit, error_document, validate_id, resolve_project_root, ensure_directory,
    reject_symlink, atomic_write, find_project_anchor, atomic_write_json,
    safe_read_bytes, safe_read_json, agent_root, agent_directory, run_directory,
    file_lock, update_json, role_path, read_request, new_run_id, session_file,
    dispatch_reservation_file, state_file,
)
from contracts import capabilities as capability_contracts
from contracts.capabilities import (
    _bounded_text, validate_capability_bindings, read_capability_bindings,
    safe_read_caller_file,
)
from contracts import receipts as receipt_contracts
from contracts.receipts import (
    receipt_schema_document, _exact_keys, _string_list,
    _require_managed_directory, _require_managed_file, validate_receipt, publish_structured_receipt,
)
from system import transport as process_transport
from system.transport import (
    AttemptFailure, build_prompt, build_prompt_parts, build_codex_command,
    response_schema_document, inline_result, validate_terminal_result, publish_terminal_result,
    structured_receipt,
    stderr_reports_sandbox_unavailable, process_exit_failure,
    missing_result_failure, result_publication_failure, append_bounded,
    EventLogWriter, append_event, read_process_lines, stream_stderr, process_group_exists,
    terminate_attempt_group, terminate_verified_group,
)
from storage.public_state import public_state as project_public_state
from runs import attempt as run_attempt
from runs import commands as run_commands
from runs import launch as run_launch
from runs import records as run_records
from execution import requests as execution_requests
from execution.cli import (
    JsonArgumentParser, add_project_argument, add_request_arguments, parse_args,
    validate_submit_options,
)

# Diagnostic/refusal paths must load even where runtime imports cannot.
if sys.platform in portable.SUPPORTED_PLATFORMS:
    import adapters
    from storage import paths as runtime_paths
    from execution import images as image_input


class _HostView:
    """Live view of this script's globals for domain modules.

    Domain functions reach host names through it at call time, so later definitions and
    test patches applied to this module are observed without importing the script again.
    """
    __slots__ = ()

    def __getattr__(self, name):
        try:
            return _HOST_GLOBALS[name]
        except KeyError:
            raise AttributeError(name) from None


_HOST_GLOBALS = globals()
_runtime = _HostView()

# Functions owned by domain modules, bound to this script so host-level patches apply.
create_run = partial(run_records.create_run, _runtime)
create_session = partial(run_records.create_session, _runtime)
load_session = partial(run_records.load_session, _runtime)
managed_parent_identity = partial(run_records.managed_parent_identity, _runtime)
require_current_parent_conversation = partial(run_records.require_current_parent_conversation, _runtime)
validate_state_containment_fields = partial(run_records.validate_state_containment_fields, _runtime)
_validate_state_containment = partial(run_records._validate_state_containment, _runtime)
find_run = partial(run_records.find_run, _runtime)
iter_agent_directories = partial(run_records.iter_agent_directories, _runtime)
iter_run_states = partial(run_records.iter_run_states, _runtime)
_launch_systemd_worker = partial(run_launch._launch_systemd_worker, _runtime)
_launch_fallback_worker = partial(run_launch._launch_fallback_worker, _runtime)
spawn_worker = partial(run_launch.spawn_worker, _runtime)
pid_alive = partial(run_launch.pid_alive, _runtime)
cancel_requested = partial(run_attempt.cancel_requested, _runtime)
run_codex_attempt = partial(run_attempt.run_codex_attempt, _runtime)
capture_lesson = partial(run_attempt.capture_lesson, _runtime)
mark_terminal = partial(run_attempt.mark_terminal, _runtime)
worker = partial(run_attempt.worker, _runtime)
command_status = partial(run_commands.command_status, _runtime)
command_result = partial(run_commands.command_result, _runtime)
command_list = partial(run_commands.command_list, _runtime)
command_reset_conversation = partial(run_commands.command_reset_conversation, _runtime)
command_inbox = partial(run_commands.command_inbox, _runtime)
command_cancel = partial(run_commands.command_cancel, _runtime)
heartbeat_stale = partial(run_commands.heartbeat_stale, _runtime)
event_stream_has_start_marker = partial(run_commands.event_stream_has_start_marker, _runtime)
durably_never_started = partial(run_commands.durably_never_started, _runtime)
command_reconcile = partial(run_commands.command_reconcile, _runtime)
request_native_pause = partial(run_commands.request_native_pause, _runtime)
record_goal_uncertainty = partial(run_commands.record_goal_uncertainty, _runtime)
wait_native_pause = partial(run_commands.wait_native_pause, _runtime)
command_goal = partial(run_commands.command_goal, _runtime)
resolve_execution_policy = partial(execution_requests.resolve_execution_policy, _runtime)
resolve_human_approval_policy = partial(execution_requests.resolve_human_approval_policy, _runtime)
requested_execution = partial(execution_requests.requested_execution, _runtime)

VALID_ROLES = {"main", "work", "verification"}
CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AUTHORITY_KINDS = {
    "native-executable", "project-cli", "mcp-server", "plugin",
    "host-capability", "external-provider",
}
CAPABILITY_OUTCOMES = {"succeeded", "failed", "unknown", "not-invoked"}


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    # Live count of this run's error captures the project does not hold yet. They never gate
    # completion; a later run that may write the project records them.
    return {**project_public_state(state), "pendingLessons": lesson_capture.pending_count(state)}


def submit(args: argparse.Namespace, new_agent: bool) -> int:
    require_managed_platform()
    project_root = resolve_project_root(args.project_root)
    validate_id(args.agent, AGENT_ID, "agent_id")
    if args.actor not in ACTORS:
        raise ContractError("actor_invalid", "actor is invalid")
    if getattr(args, "input_file", None) is not None:
        request, images = image_input.read_agent_input(args.input_file)
    else:
        request, images = read_request(args), []
    try:
        request_text = request.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("request_invalid", "request must be UTF-8 text") from error
    if not request_text.strip():
        raise ContractError("request_invalid", "request must not be empty")
    receipt_request_hash = getattr(args, "receipt_request_hash", None)
    verified_work_run_id = getattr(args, "verified_work_run_id", None)
    dispatch_id = getattr(args, "dispatch_id", None)
    if dispatch_id is None:
        dispatch_id = f"dispatch-{uuid.uuid4().hex}"
    _capability_document, capability_bindings = read_capability_bindings(
        getattr(args, "capability_binding_file", None)
    )
    capability_binding_hash = (
        hashlib.sha256(capability_bindings).hexdigest()
        if capability_bindings is not None else None
    )
    if dispatch_id is not None:
        if not DISPATCH_ID.fullmatch(dispatch_id):
            raise ContractError(
                "invalid_dispatch_id",
                "dispatch id must match dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}; "
                "omit --dispatch-id for a new request, or reuse the original key for recovery",
            )
    if receipt_request_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", receipt_request_hash):
        raise ContractError("receipt_binding_invalid", "receipt request hash is invalid")
    if verified_work_run_id is not None:
        validate_id(verified_work_run_id, AGENT_ID, "run_id")
    if new_agent:
        role = validate_id(args.role, ROLE_ID, "role")
        role_path(role)
    else:
        role = load_session(project_root, args.agent).get("role")
    stored_session = None if new_agent else load_session(project_root, args.agent)
    # Not an execution option: the dispatch tuple records only what the caller requested.
    args.inherited_provider = execution_requests.inherited_provider(_runtime, args) if new_agent else None
    provider = adapters.provider_for(getattr(args, "model", None), getattr(args, "provider", None) or args.inherited_provider, stored_session)
    policy = resolve_execution_policy(args, project_root, stored_session)
    args.resolved_execution_policy = policy
    human_approval_policy = resolve_human_approval_policy(args, stored_session)
    args.resolved_human_approval_policy = human_approval_policy
    standalone = role == "verification" and getattr(args, "task_mode", None) == "verification"
    if standalone and (verified_work_run_id is not None or receipt_request_hash is not None):
        raise ContractError("receipt_binding_invalid", "Standalone verification binds its own target request, not a Work run")
    if role == "verification" and not standalone and verified_work_run_id is None:
        raise ContractError(
            "receipt_binding_invalid",
            "Verification runs require the exact Work run identifier",
        )
    if role != "verification" and verified_work_run_id is not None:
        raise ContractError(
            "receipt_binding_invalid",
            "verified Work run binding is valid only for Verification runs",
        )
    execution_options = requested_execution(args)
    if role == "main":
        execution_options.setdefault("taskMode", "orchestrate")
    adapters.adapter(provider).validate({**(stored_session or {}), **execution_options,
                                         "role": role, "executionPolicy": policy})
    from tasks.modes import validate_mode
    if "taskMode" in execution_options:
        validate_mode(execution_options["taskMode"])
        if (role == "verification" and not standalone) or (role == "work" and execution_options["taskMode"] in ("orchestrate", "direct", "verification")):
            raise ContractError("task_mode_role_invalid", "Task mode is incompatible with this role")
    work_profile = getattr(args, "work_profile", None)
    if work_profile is not None and role != "work":
        raise ContractError("work_profile_role_invalid", "--work-profile labels Work runs only")
    goal_action = getattr(args, "goal_action", None)
    if role == "main" and execution_options.get("taskMode") != "direct" and execution_options.get("goalMode", (stored_session or {}).get("goalMode")) is True:
        raise ContractError("goal_role_invalid", "Main Goal is direct-only; delegated execution uses Work's native Goal. Submit the captured route with Main --no-goal-mode")
    if role == "work":
        # Each bounded execution/revision owns a fresh objective, including long requests.
        # The complete request is delivered by the native bridge, never truncated here.
        from tasks.modes import work_goal_options
        execution_options = work_goal_options(execution_options, request_text)
    if role == "verification" and (execution_options.get("goalMode") is True or goal_action):
        raise ContractError("goal_role_invalid", "Verification cannot use native Goal continuation")
    if execution_options.get("goalMode") is True and new_agent and "goalObjective" not in execution_options:
        execution_options["goalObjective"] = request_text
    operation = "submit" if new_agent else "send"
    parent = managed_parent_identity(project_root) if role in {"work", "verification"} else None
    request_hash = hashlib.sha256(request).hexdigest()
    binding = None
    if role in {"work", "verification"}:
        from tasks import binding as task_binding
        task_list_file = getattr(args, "task_list_file", None)
        task_id = getattr(args, "task_id", None)
        if task_list_file is None or not task_id:
            raise ContractError("task_binding_required", "Delegated execution requires --task-list-file and --task-id before dispatch")
        task_document = safe_read_json(task_list_file)
        # Accepted dispatches retain their immutable tuple and existing deduplication path.
        accepted_retry = parent is not None and any(value.get("dispatchId") == dispatch_id
                             for value in iter_run_states(project_root, args.agent))
        # A runtime-derived orchestrator brief has no announcement by design.
        if parent is not None and not accepted_retry and task_document.get("brief") is not True:
            from tasks import announcement as task_announcement
            with file_lock(agent_directory(project_root, parent["agentId"]) / ".dispatch.lock"):
                require_current_parent_conversation(project_root, parent)
                task_announcement.check_submission(safe_read_json,
                    state_file(project_root, parent["agentId"], parent["runId"]), parent, task_document)
        binding = task_binding.resolve(task_document, task_id,
            request_hash if new_agent and role == "work" else receipt_request_hash or request_hash)[1]
    input_images = [{"mediaType": image["mediaType"], "size": len(image["content"]),
                     "sha256": hashlib.sha256(image["content"]).hexdigest()} for image in images]
    dispatch_tuple = {
        "agentId": args.agent,
        "role": role,
        "actor": args.actor,
        "requestHash": request_hash,
        "receiptRequestHash": receipt_request_hash or request_hash,
        "verifiedWorkRunId": verified_work_run_id,
        "operation": operation,
        "executionPolicy": policy,
        "humanApprovalPolicy": human_approval_policy,
    }
    if not new_agent and getattr(args, "codex", None) is not None:
        dispatch_tuple["requestedCodex"] = args.codex
    if binding is not None:
        dispatch_tuple["taskBinding"] = binding
    if getattr(args, "resolved_task_workspace", None):
        dispatch_tuple["taskWorkspaceId"] = args.resolved_task_workspace["id"]
    if parent is not None:
        dispatch_tuple.update({
            "parentAgentId": parent["agentId"],
            "parentRunId": parent["runId"],
        })
    if input_images:
        dispatch_tuple["imageInputs"] = input_images
    if execution_options:
        dispatch_tuple["executionOptions"] = execution_options
    if work_profile is not None:
        dispatch_tuple["workProfile"] = work_profile
    if goal_action:
        dispatch_tuple["goalAction"] = goal_action
    if capability_binding_hash is not None:
        dispatch_tuple["capabilityBindingHash"] = capability_binding_hash
    agent_path = agent_directory(project_root, args.agent, create=True)
    if parent is not None and parent["agentId"] == args.agent:
        raise ContractError("parent_session_invalid", "A child Agent cannot reuse its parent Agent identity")
    with contextlib.ExitStack() as locks:
        locks.enter_context(file_lock(Path(runtime_paths.resolve(project_root)["runtimeRoot"]) / ".worktree.lock"))
        if parent is not None:
            locks.enter_context(file_lock(agent_directory(project_root, parent["agentId"]) / ".dispatch.lock"))
        locks.enter_context(file_lock(agent_path / ".dispatch.lock"))
        if parent is not None:
            require_current_parent_conversation(project_root, parent)
        if not new_agent:
            current_session = load_session(project_root, args.agent)
            policy = resolve_execution_policy(args, project_root, current_session)
            human_approval_policy = resolve_human_approval_policy(args, current_session)
            args.resolved_execution_policy = policy
            args.resolved_human_approval_policy = human_approval_policy
            dispatch_tuple["executionPolicy"] = policy
            dispatch_tuple["humanApprovalPolicy"] = human_approval_policy
        reservation_path: Path | None = None
        if new_agent and dispatch_id is not None:
            reservation_path = dispatch_reservation_file(
                project_root, args.agent, dispatch_id
            )
            if reservation_path.exists():
                reservation = safe_read_json(reservation_path)
                if (
                    set(reservation)
                    != {"schemaVersion", "kind", "dispatchId", "dispatchTuple"}
                    or reservation.get("schemaVersion") != SCHEMA_VERSION
                    or reservation.get("kind") != "dispatch-reservation"
                    or reservation.get("dispatchId") != dispatch_id
                    or reservation.get("dispatchTuple") != dispatch_tuple
                ):
                    raise ContractError(
                        "dispatch_id_collision",
                        "dispatch identifier was reserved with a different immutable tuple",
                    )
            else:
                if session_file(project_root, args.agent).exists():
                    prior = [
                        value
                        for value in iter_run_states(project_root, args.agent)
                        if value.get("dispatchId") == dispatch_id
                    ]
                    if len(prior) > 1:
                        raise ContractError(
                            "dispatch_id_collision", "dispatch identifier is not unique"
                        )
                    if prior:
                        state = prior[0]
                        if state.get("dispatchTuple") != dispatch_tuple:
                            raise ContractError(
                                "dispatch_id_collision",
                                "dispatch identifier was used with a different immutable tuple",
                            )
                        emit({
                            "schemaVersion": SCHEMA_VERSION,
                            "kind": "ack",
                            "status": "accepted",
                            "agentId": args.agent,
                            "runId": state["runId"],
                            "workerPid": state.get("workerPid"),
                            "statePath": str(
                                state_file(project_root, args.agent, state["runId"])
                            ),
                            "dispatchId": dispatch_id,
                            "deduplicated": True,
                        })
                        return 0
                    raise ContractError("agent_exists", "Agent already exists; use send")
                reservation_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(
                    reservation_path,
                    {
                        "schemaVersion": SCHEMA_VERSION,
                        "kind": "dispatch-reservation",
                        "dispatchId": dispatch_id,
                        "dispatchTuple": dispatch_tuple,
                    },
                )
        if dispatch_id is not None:
            matches = [
                value for value in iter_run_states(project_root, args.agent)
                if value.get("dispatchId") == dispatch_id
            ]
            if len(matches) > 1:
                raise ContractError("dispatch_id_collision", "dispatch identifier is not unique")
            if matches:
                state = matches[0]
                if not new_agent and all(getattr(args, name, None) is None for name in (
                    "sandbox", "approval_policy", "execution_policy_file", "network_access", "writable_root"
                )) and "executionPolicy" in state:
                    dispatch_tuple["executionPolicy"] = execution_policy.normalize(state["executionPolicy"])
                if not new_agent and getattr(args, "human_approval_policy", None) is None and "humanApprovalPolicy" in state:
                    dispatch_tuple["humanApprovalPolicy"] = state["humanApprovalPolicy"]
                if state.get("dispatchTuple") != dispatch_tuple:
                    raise ContractError("dispatch_id_collision", "dispatch identifier was used with a different immutable tuple")
                emit({
                    "schemaVersion": SCHEMA_VERSION,
                    "kind": "ack",
                    "status": "accepted",
                    "agentId": args.agent,
                    "runId": state["runId"],
                    "workerPid": state.get("workerPid"),
                    "statePath": str(state_file(project_root, args.agent, state["runId"])),
                    "dispatchId": dispatch_id,
                    "deduplicated": True,
                })
                return 0
        if new_agent:
            session = (
                load_session(project_root, args.agent)
                if reservation_path is not None
                and session_file(project_root, args.agent).exists()
                else create_session(args, project_root)
            )
        else:
            session = load_session(project_root, args.agent)
        if any(value.get("status") in ACTIVE_STATES for value in iter_run_states(project_root, args.agent)):
            raise ContractError("session_busy", "An accepted or active run already owns this exact session")
        if parent is not None:
            session = worktrees.inherit(session, {"projectRoot": str(project_root), **load_session(project_root, parent["agentId"])})
            update_json(session_file(project_root, args.agent), agent_path / ".session-state.lock",
                        lambda value: value.update({"worktree": session.get("worktree"), "executionPolicy": session.get("executionPolicy")}))
        from tasks import workspaces as task_workspaces
        task_workspace = task_workspaces.dispatch_binding(_runtime, args, project_root)
        if task_workspace:
            session = task_workspaces.bind(session, task_workspace)
            update_json(session_file(project_root, args.agent), agent_path / ".session-state.lock",
                        lambda value: value.update({"taskWorkspace": task_workspace, "executionPolicy": policy}))
        policy_changed = "executionPolicy" not in session or execution_policy.session_policy(session) != policy
        if policy_changed:
            if "executionPolicy" in session and not execution_policy.has_explicit_policy(args):
                raise ContractError("execution_policy_mismatch", "Changing an idle session policy requires a complete explicit policy")
            session = {**session, "executionPolicy": policy, "sandbox": policy["sandboxPolicy"]["type"],
                       "executionPolicySource": "explicit" if execution_policy.has_explicit_policy(args) else "legacy"}
        human_approval_policy_changed = session.get("humanApprovalPolicy", "required") != human_approval_policy
        if human_approval_policy_changed:
            session = {**session, "humanApprovalPolicy": human_approval_policy}
        worktrees.checked_path({"projectRoot": str(project_root), **session})
        effective = {**session, **execution_options}
        provider_changed = provider != session.get("provider", "codex")
        codex_changed = False
        if provider_changed:
            # Only a cleared/unstarted conversation reaches here. Never resume an
            # ID belonging to the other provider; historical runs remain untouched.
            from shutil import which
            executable = which(adapters.adapter(provider).executable(args, session))
            if executable is None:
                raise ContractError("provider_not_found", f"{provider} executable was not found")
            session = {**session, **adapters.adapter(provider).session_fields(executable)}
            effective = {**session, **execution_options}
        elif provider == "codex" and not new_agent and getattr(args, "codex", None):
            # A resumed conversation keeps its native thread ID and history, but each
            # accepted turn uses the CLI currently selected by the extension host.
            requested_codex = args.codex
            if os.sep not in requested_codex:
                from shutil import which
                resolved_codex = which(requested_codex) or portable.find_cli(requested_codex)
            else:
                try:
                    resolved_codex = str(Path(requested_codex).resolve(strict=True))
                except OSError as error:
                    raise ContractError("codex_not_found", f"Codex executable was not found: {requested_codex}") from error
            if not resolved_codex or not Path(resolved_codex).is_file() or not os.access(resolved_codex, os.X_OK):
                raise ContractError("codex_not_found", f"Codex executable was not found: {requested_codex}")
            resolved_codex = portable.native_executable(resolved_codex, "codex")
            codex_changed = resolved_codex != session.get("codex")
            if codex_changed:
                capabilities = adapters.adapter("codex").inspect_capabilities(
                    resolved_codex, refresh=True,
                    runtime_home=runtime_paths.resolve(project_root, create=True)["home"])
                if session.get("backend") == "app-server" and capabilities.get("send", {}).get("instructionDelivery") is not True:
                    raise ContractError("native_unsupported", "The selected Codex CLI cannot resume this app-server conversation")
                session = {**session, "codex": resolved_codex}
                effective = {**session, **execution_options}
        adapters.adapter(provider).validate_execution(effective, goal_action)
        image_input.validate_execution(images, effective)
        state = create_run(
            project_root=project_root,
            agent_id=args.agent,
            actor=args.actor,
            request=request,
            session=session,
            receipt_request_hash=receipt_request_hash,
            verified_work_run_id=verified_work_run_id,
            dispatch_id=dispatch_id,
            dispatch_operation=operation,
            requested_codex=getattr(args, "codex", None) if not new_agent else None,
            capability_bindings=capability_bindings,
            execution_options=execution_options,
            work_profile=work_profile,
            goal_action=goal_action,
            images=images,
            parent_agent_id=parent["agentId"] if parent else None,
            parent_run_id=parent["runId"] if parent else None,
            task_binding=binding,
            task_workspace_id=dispatch_tuple.get("taskWorkspaceId"),
            response_contract=getattr(args, "response_contract", None),
        )
        if policy_changed or human_approval_policy_changed or provider_changed or codex_changed:
            session_updates = {"humanApprovalPolicy": human_approval_policy}
            if provider_changed or codex_changed:
                session_updates.update(adapters.for_session(session).persisted_fields(session))
            if policy_changed:
                session_updates.update({
                    "executionPolicy": policy,
                    "sandbox": policy["sandboxPolicy"]["type"],
                    "executionPolicySource": session["executionPolicySource"],
                })
            update_json(
                session_file(project_root, args.agent),
                agent_path / ".session-state.lock",
                lambda value: value.update(session_updates),
            )
        worker_pid = spawn_worker(project_root, args.agent, state["runId"])
    document = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "ack",
            "status": "accepted",
            "agentId": args.agent,
            "runId": state["runId"],
            "workerPid": worker_pid,
            "statePath": str(state_file(project_root, args.agent, state["runId"])),
        }
    if dispatch_id is not None:
        document.update({"dispatchId": dispatch_id, "deduplicated": False})
    emit(document)
    return 0


class Heartbeat:
    def __init__(self, path: Path, state_path: Path, interval: float) -> None:
        self.path = path
        self.state_path = state_path
        self.interval = interval
        self.stop_event = threading.Event()
        self.sequence = 0
        self.status = "queued"
        self.attempt = 0
        self.codex_pid: int | None = None
        self.codex_identity: dict[str, Any] | None = None
        self.worker_identity = process_identity(os.getpid())
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._write()
        self.thread.start()

    def update(
        self,
        *,
        status: str,
        attempt: int,
        codex_pid: int | None,
        codex_identity: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.status = status
            self.attempt = attempt
            self.codex_pid = codex_pid
            self.codex_identity = codex_identity
        self._write()

    def close(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=max(1.0, self.interval * 2))
        self._write()

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval):
            with contextlib.suppress(Exception):
                self._write()

    def _write(self) -> None:
        with self.lock:
            self.sequence += 1
            value = {
                "schemaVersion": SCHEMA_VERSION,
                "runId": self.state_path.parent.name,
                "attempt": self.attempt,
                "sequence": self.sequence,
                "status": self.status,
                "workerPid": os.getpid(),
                "workerIdentity": self.worker_identity,
                "codexPid": self.codex_pid,
                "codexIdentity": self.codex_identity,
                "observedAt": now(),
            }
        atomic_write_json(self.path, value)
        fact = "process_alive" if process_identity_status(value.get("codexIdentity")) == "match" else "unreachable"  # noqa: F841 - unused, but the identity probe stays: removing a call is not a lint-only change


def __getattr__(name):
    # Lazy compatibility exports for existing Python integrations. Execution
    # itself accesses providers only through adapters.
    import importlib
    legacy = {"native_codex": "adapters.codex.transport",
              "execution_preflight": "adapters.codex.preflight",
              "runtime_permissions": "adapters.codex.policy"}
    if name in legacy:
        return importlib.import_module(legacy[name])
    raise AttributeError(name)


def main(argv: Sequence[str] | None = None) -> int:
    operation_token = response_operation.set(None)
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        if arguments and arguments[0] == "doctor":
            return sandbox_diagnostics.main(arguments[1:])
        args = parse_args(arguments)
        if not args.command.startswith("_"):
            response_operation.set({"schemaVersion": 1, "provider": "agent-factory", "script": "exec.py", "action": args.command})
        require_managed_platform()
        if hasattr(args, "project_root") and args.command != "rebind":
            binding = runtime_paths.resolve(args.project_root, create=args.command == "init",
                                            home=args.runtime_home, project_id=args.project_id)
            os.environ["AGENT_FACTORY_HOME"] = binding["home"]
        if args.command in {"init", "location"}:
            emit(binding)
            return 0
        if args.command == "map-path":
            emit(runtime_paths.map_evidence(args.project_root, args.path))
            return 0
        if args.command == "projects":
            emit({"schemaVersion": 1, "kind": "runtime-projects", **runtime_paths.registry(Path(binding["home"]))})
            return 0
        if args.command == "rebind":
            emit(runtime_paths.rebind(args.runtime_home, args.project_id, args.from_root, args.project_root))
            return 0
        if args.command == "capabilities":
            session = None
            if args.agent:
                session = load_session(resolve_project_root(args.project_root), args.agent)
            provider = adapters.provider_for(args.model, args.provider, {**session, "sessionId": None} if session else None)
            executable = (args.codex or (session or {}).get("codex") or "codex") if provider == "codex" else adapters.adapter(provider).executable(args, session)
            capabilities = dict(adapters.adapter(provider).inspect_capabilities(executable))
            # Provider-independent runtime features. Hosts pass --work-profile and give per-class failure
            # guidance only when reported; `pendingLessons` marks runs that complete with unsaved captures.
            # `responseContract` is the newest Work response contract this runtime creates runs under
            # (2: receipt fields in the structured final output); `revisionLimitPause` marks loops whose
            # public state carries the structured `pause` a Human decides on.
            # `workIsolation`: Main runs accept --work-isolation on|off and loops inherit it.
            for operation in ("submit", "send"):
                capabilities[operation] = {**capabilities[operation], "workProfile": True, "failureClass": True,
                                           "pendingLessons": True,
                                           "responseContract": receipt_contracts.RESPONSE_CONTRACTS[-1],
                                           "revisionLimitPause": True, "taskWorkspaces": True,
                                           "workIsolation": True}
            if session is not None and session.get("sessionId"):
                # A started conversation keeps its provider; hosts can mark models on other providers.
                capabilities["send"] = {**capabilities["send"], "sessionProvider": session.get("provider", "codex")}
            if session is not None and "executionPolicy" in session:
                capabilities["executionMode"] = (
                    "bypass"
                    if session.get("humanApprovalPolicy") == "bypass"
                    else execution_policy.session_policy(session)["sandboxPolicy"]["type"]
                )
            emit(capabilities)
            return 0
        if args.command == "worktree":
            return worktrees.command(sys.modules[__name__], args)
        if args.command == "goal":
            return command_goal(args)
        if args.command == "announce-tasks":
            from tasks import announcement as task_announcement
            emit(task_announcement.prepare(sys.modules[__name__], args))
            return 0
        if args.command == "submit":
            validate_submit_options(args)
            return submit(args, True)
        if args.command == "send":
            return submit(args, False)
        if args.command == "status":
            return command_status(args)
        if args.command == "result":
            return command_result(args)
        if args.command == "list":
            return command_list(args)
        if args.command == "reset-conversation":
            return command_reset_conversation(args)
        if args.command == "inbox":
            return command_inbox(args)
        if args.command == "cancel":
            return command_cancel(args)
        if args.command == "reconcile":
            return command_reconcile(args)
        if args.command == "_worker":
            return worker(args)
        if args.command == "_bootstrap":
            return containment_bootstrap(args)
        raise ContractError("invalid_command", "command is invalid")
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        emit(error_document("runtime_failure", str(error)))
        return 1
    finally:
        response_operation.reset(operation_token)


if __name__ == "__main__":
    raise SystemExit(main())
