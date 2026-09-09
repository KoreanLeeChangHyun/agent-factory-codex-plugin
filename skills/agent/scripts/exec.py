#!/usr/bin/env python3
"""Manage resumable Codex exec roles without blocking the Main Agent."""

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
from types import SimpleNamespace
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
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_EVENTS_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 4 * 1024 * 1024
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
SKILL_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = SKILL_ROOT / "prompt"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT / "runtime"))
import sandbox_diagnostics
import permissions as runtime_permissions
import execution_policy
import preflight as execution_preflight
from runtime_errors import ContractError
import process_containment
from process_containment import (
    require_managed_platform,
    now,
    parse_time,
    linux_boot_id,
    linux_process_identity,
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
import runtime_storage
from runtime_storage import (
    emit, error_document, validate_id, resolve_project_root, ensure_directory,
    reject_symlink, atomic_write, find_project_anchor, atomic_write_json,
    safe_read_bytes, safe_read_json, agent_root, agent_directory, run_directory,
    file_lock, update_json, role_path, read_request, new_run_id, session_file,
    dispatch_reservation_file, state_file,
)
import capability_contracts
from capability_contracts import (
    _bounded_text, validate_capability_bindings, read_capability_bindings,
    result_file_identity, safe_hash_caller_file, safe_read_caller_file,
)
import receipt_contracts
from receipt_contracts import (
    receipt_schema_document, _exact_keys, _string_list,
    _require_managed_directory, _require_managed_file, validate_receipt,
)
import process_transport
from process_transport import (
    AttemptFailure, build_prompt, build_codex_command,
    stderr_reports_sandbox_unavailable, process_exit_failure,
    missing_result_failure, result_publication_failure, append_bounded,
    append_event, read_process_lines, stream_stderr, process_group_exists,
    terminate_attempt_group, terminate_verified_group,
)
from public_state import public_state
from exec_cli import (
    JsonArgumentParser, add_project_argument, add_request_arguments, parse_args,
    validate_submit_options,
)

# Diagnostic/refusal paths must load even where POSIX runtime imports cannot.
if sys.platform == "linux":
    import cloud_reporting
    import native_codex
    import paths as runtime_paths
VALID_ROLES = {"main", "work", "verification"}
CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AUTHORITY_KINDS = {
    "native-executable", "project-cli", "mcp-server", "plugin",
    "host-capability", "external-provider",
}
CAPABILITY_OUTCOMES = {"succeeded", "failed", "unknown", "not-invoked"}


def reporting_runtime():
    """Expose runtime primitives also when a host loads this file without registration."""
    return SimpleNamespace(**globals())


def create_run(
    *,
    project_root: Path,
    agent_id: str,
    actor: str,
    request: bytes,
    session: dict[str, Any],
    receipt_request_hash: str | None = None,
    verified_work_run_id: str | None = None,
    dispatch_id: str | None = None,
    dispatch_operation: str | None = None,
    capability_bindings: bytes | None = None,
    reporting_config: dict[str, Any] | None = None,
    reporting_loop_id: str | None = None,
    execution_options: dict[str, Any] | None = None,
    goal_action: str | None = None,
) -> dict[str, Any]:
    run_id = new_run_id()
    directory = run_directory(project_root, agent_id, run_id, create=True)
    request_path = directory / "request.md"
    result_path = directory / "result.md"
    events_path = directory / "events.jsonl"
    heartbeat_path = directory / "heartbeat.json"
    response_schema = directory / "response.schema.json"
    receipt_path = directory / "receipt.json"
    receipt_schema = directory / "receipt.schema.json"
    capability_binding_path = directory / "capability-bindings.json"
    request_hash = hashlib.sha256(request).hexdigest()
    atomic_write(request_path, request)
    capability_binding_hash = None
    capability_binding_document = None
    if capability_bindings is not None:
        capability_binding_document = validate_capability_bindings(json.loads(capability_bindings))
        atomic_write(capability_binding_path, capability_bindings)
        capability_binding_hash = hashlib.sha256(capability_bindings).hexdigest()
    atomic_write_json(
        response_schema,
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["completed", "needs-human-decision", "failed"],
                },
                "resultPath": {"type": "string", "const": str(result_path)},
            },
            "required": ["status", "resultPath"],
            "additionalProperties": False,
        },
    )
    role = str(session["role"])
    if role in {"work", "verification"}:
        atomic_write_json(
            receipt_schema,
            receipt_schema_document(
                role=role,
                run_id=run_id,
                request_hash=receipt_request_hash or request_hash,
                verified_work_run_id=verified_work_run_id,
                capability_bindings=capability_binding_document,
            ),
        )
    accepted_at = now()
    state = {
        "runtimeBinding": runtime_paths.resolve(project_root, create=True),
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "agentId": agent_id,
        "role": session["role"],
        "actor": actor,
        "status": "accepted",
        "attempt": 0,
        "startDisposition": "not-started",
        "maxAttempts": session["maxAttempts"],
        "requestPath": str(request_path),
        "requestHash": request_hash,
        "statePath": str(directory / "state.json"),
        "resultPath": str(result_path),
        "eventsPath": str(events_path),
        "heartbeatPath": str(heartbeat_path),
        "responseSchemaPath": str(response_schema),
        "acceptedAt": accepted_at,
        "updatedAt": accepted_at,
        "workerPid": None,
        "workerIdentity": None,
        "containmentAttempt": 0,
        "containment": None,
        "containmentLaunchDisposition": "not-launched",
        "codexPid": None,
        "codexIdentity": None,
        "lastCodexIdentity": None,
        "cancelRequested": False,
        "unread": False,
        "error": None,
    }
    if execution_options:
        state["executionOptions"] = execution_options
    state["humanApprovalPolicy"] = session.get("humanApprovalPolicy", "required")
    if "executionPolicy" in session:
        state["executionPolicy"] = session["executionPolicy"]
    if goal_action:
        state["goalAction"] = goal_action
    if reporting_config is not None:
        state["cloudReporting"] = reporting_config
        state["reportingLoopId"] = reporting_loop_id
    if dispatch_id is not None:
        state["dispatchId"] = dispatch_id
        state["dispatchTuple"] = {
            "agentId": agent_id,
            "role": role,
            "actor": actor,
            "requestHash": request_hash,
            "receiptRequestHash": receipt_request_hash or request_hash,
            "verifiedWorkRunId": verified_work_run_id,
            "operation": dispatch_operation,
        }
        if "executionPolicy" in session:
            state["dispatchTuple"]["executionPolicy"] = session["executionPolicy"]
        state["dispatchTuple"]["humanApprovalPolicy"] = state["humanApprovalPolicy"]
        if execution_options:
            state["dispatchTuple"]["executionOptions"] = execution_options
        if goal_action:
            state["dispatchTuple"]["goalAction"] = goal_action
        if reporting_config is not None:
            state["dispatchTuple"]["reportingConfigHash"] = cloud_reporting.digest(reporting_config)
            state["dispatchTuple"]["reportingLoopId"] = reporting_loop_id
        if capability_binding_hash is not None:
            state["dispatchTuple"]["capabilityBindingHash"] = capability_binding_hash
    if role in {"work", "verification"}:
        state.update(
            {
                "receiptPath": str(receipt_path),
                "receiptSchemaPath": str(receipt_schema),
                "receiptRequestHash": receipt_request_hash or request_hash,
            }
        )
    if role == "verification":
        state["verifiedWorkRunId"] = verified_work_run_id
    if capability_binding_hash is not None:
        state.update({
            "capabilityBindingPath": str(capability_binding_path),
            "capabilityBindingHash": capability_binding_hash,
        })
    atomic_write_json(directory / "state.json", state)
    atomic_write_json(
        heartbeat_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "attempt": 0,
            "sequence": 0,
            "status": "accepted",
            "workerPid": None,
            "codexPid": None,
            "observedAt": accepted_at,
        },
    )
    cloud_reporting.hook(reporting_runtime(), directory / "state.json")
    return state


def create_session(args: argparse.Namespace, project_root: Path) -> dict[str, Any]:
    directory = agent_directory(project_root, args.agent, create=True)
    path = directory / "session.json"
    if path.exists():
        raise ContractError("agent_exists", "Agent already exists; use send")
    role = validate_id(args.role, ROLE_ID, "role")
    role_path(role)
    if not hasattr(args, "resolved_execution_policy"):
        args.resolved_execution_policy = resolve_execution_policy(args, project_root)
    codex = args.codex
    if os.sep not in codex:
        from shutil import which

        resolved = which(codex)
        if resolved is None:
            raise ContractError("codex_not_found", "codex executable was not found")
        codex = resolved
    else:
        codex = str(Path(codex).resolve(strict=True))
    options = requested_execution(args)
    if options.get("fast") is True or options.get("goalMode") is True:
        capabilities = native_codex.inspect_capabilities(codex, refresh=True, runtime_home=runtime_paths.resolve(project_root, create=True)["home"])
        for key, field in (("fast", "fast"), ("goalMode", "goal")):
            if options.get(key) is True and not capabilities["submit"][field]:
                raise ContractError("native_unsupported", capabilities["diagnostic"] or f"Native {field} unsupported")
    created_at = now()
    session = {
        "schemaVersion": SCHEMA_VERSION,
        "agentId": args.agent,
        "role": role,
        "sessionId": None,
        "projectRoot": str(project_root),
        "runtimeBinding": runtime_paths.resolve(project_root, create=True),
        "codex": codex,
        "sandbox": args.resolved_execution_policy["sandboxPolicy"]["type"],
        "executionPolicy": args.resolved_execution_policy,
        "humanApprovalPolicy": getattr(args, "resolved_human_approval_policy", "required"),
        "model": args.model,
        "reasoningEffort": getattr(args, "reasoning_effort", None),
        "heartbeatInterval": args.heartbeat_interval,
        "heartbeatTimeout": args.heartbeat_timeout,
        "startTimeout": args.start_timeout,
        "turnTimeout": args.turn_timeout,
        "maxAttempts": args.max_attempts,
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    atomic_write_json(path, session)
    return session


def load_session(project_root: Path, agent_id: str) -> dict[str, Any]:
    path = session_file(project_root, agent_id)
    session = safe_read_json(path)
    if session.get("agentId") != agent_id or session.get("projectRoot") != str(project_root):
        raise ContractError("session_invalid", "Agent session binding is invalid")
    session_id = session.get("sessionId")
    if session_id is not None and (
        not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id)
    ):
        raise ContractError("session_invalid", "Codex session identifier is invalid")
    role_path(str(session.get("role", "")))
    return session


def validate_state_containment_fields(state: dict[str, Any]) -> None:
    fields = {"containmentAttempt", "containment", "containmentLaunchDisposition"}
    present = fields.intersection(state)
    if not present:
        return
    if present != fields:
        raise ContractError("containment_state_invalid", "containment state fields are incomplete")
    attempt = state.get("containmentAttempt")
    disposition = state.get("containmentLaunchDisposition")
    if not isinstance(attempt, int) or attempt < 0 or disposition not in {
        "not-launched", "launching", "launched"
    }:
        raise ContractError("containment_state_invalid", "containment state fields are invalid")
    containment = state.get("containment")
    if containment is None:
        if attempt != 0 or disposition != "not-launched":
            raise ContractError("containment_identity_unbound", "launched containment identity is not bound")
        return
    validate_containment(containment)
    if attempt < 1 or disposition == "not-launched":
        raise ContractError("containment_state_invalid", "containment launch state is invalid")


def _validate_state_containment(state: dict[str, Any]) -> dict[str, Any]:
    validate_state_containment_fields(state)
    containment = validate_containment(state.get("containment"))
    if containment["kind"] == "systemd-user-service":
        attempt = state.get("containmentAttempt")
        if not isinstance(attempt, int) or attempt < 1 or containment["unitName"] != systemd_unit_name(
            str(state.get("agentId")), str(state.get("runId")), attempt
        ):
            raise ContractError("containment_identity_mismatch", "systemd unit is not bound to this run attempt")
    elif containment["identity"] != state.get("workerIdentity"):
        raise ContractError("containment_identity_mismatch", "fallback containment is not bound to this worker")
    return containment


def _launch_systemd_worker(
    project_root: Path,
    agent_id: str,
    run_id: str,
    command: Sequence[str],
    environment_resource: tuple[int, str],
) -> int:
    environment_fd, environment_path = environment_resource
    try:
        path = state_file(project_root, agent_id, run_id)
        state = safe_read_json(path)
        attempt = int(state.get("containmentAttempt", 0)) + 1
        containment = {
            "kind": "systemd-user-service",
            "unitName": systemd_unit_name(agent_id, run_id, attempt),
            "bindingToken": uuid.uuid4().hex,
            "invocationId": None,
            "weakerDescendantContainment": False,
        }
        update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "containmentAttempt": attempt,
                    "containment": containment,
                    "containmentLaunchDisposition": "launching",
                    "status": "starting",
                }
            ),
        )
        result = _systemd_command((
            "systemd-run", "--user", f"--unit={containment['unitName']}",
            f"--description={SYSTEMD_DESCRIPTION_PREFIX}{containment['bindingToken']}",
            "--collect", "--service-type=exec",
            "--property=KillMode=control-group",
            f"--property=TimeoutStopSec={PROCESS_TERM_TIMEOUT}s",
            "--property=SendSIGKILL=no",
            f"--property=EnvironmentFile={environment_path}",
            f"--working-directory={project_root}", "--", *command,
        ))
    finally:
        with contextlib.suppress(OSError):
            os.close(environment_fd)
    if result.returncode != 0:
        raise ContractError(
            "containment_launch_failed",
            "the bound systemd service launch was not acknowledged; the run will not be replayed without reconciliation",
        )
    observed = query_systemd_containment(containment)
    if observed["invocationId"] is None:
        raise ContractError("containment_launch_ack_missing", "systemd returned no invocation identity")
    containment = {**containment, "invocationId": observed["invocationId"]}
    state = update_json(
        path,
        path.parent / ".state.lock",
        lambda value: value.update(
            {
                "containment": containment,
                "containmentLaunchDisposition": "launched",
                "workerPid": observed["mainPid"],
                "status": "queued",
            }
        ),
    )
    worker_pid = state.get("workerPid")
    return worker_pid if isinstance(worker_pid, int) and worker_pid > 0 else 0


def _launch_fallback_worker(
    project_root: Path, agent_id: str, run_id: str, command: Sequence[str]
) -> int:
    command = [
        *command,
    ]
    try:
        process, identity, release_fd = spawn_contained_process(
            command,
            cwd=project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except ContractError as error:
        raise ContractError(error.code, error.message) from error
    except OSError as error:
        raise ContractError("worker_start_failed", "background worker could not start") from error
    release_attempted = False
    try:
        path = state_file(project_root, agent_id, run_id)
        update_json(
            path,
            path.parent / ".state.lock",
            lambda state: state.update(
                {
                    "workerPid": process.pid,
                    "workerIdentity": identity,
                    "containmentAttempt": int(state.get("containmentAttempt", 0)) + 1,
                    "containment": {
                        "kind": "process-group",
                        "identity": identity,
                        "weakerDescendantContainment": True,
                    },
                    "containmentLaunchDisposition": "launched",
                    "status": "queued",
                }
            ),
        )
        release_attempted = True
        release_contained_process(process, identity, release_fd)
    except (ContractError, OSError) as error:
        abort_contained_process(
            process,
            identity,
            None if release_attempted else release_fd,
        )
        if isinstance(error, ContractError):
            raise ContractError(error.code, error.message) from error
        raise ContractError("worker_start_failed", "background worker could not start") from error
    return process.pid


def spawn_worker(project_root: Path, agent_id: str, run_id: str) -> int:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        *runtime_paths.arguments(project_root),
        "--project-root",
        str(project_root),
        "--agent",
        agent_id,
        "--run-id",
        run_id,
    ]
    if systemd_manager_usable():
        try:
            environment_resource = create_systemd_environment_file()
        except ContractError as error:
            if error.code not in {
                "containment_environment_invalid",
                "containment_environment_unavailable",
            }:
                raise
        else:
            return _launch_systemd_worker(
                project_root, agent_id, run_id, command, environment_resource
            )
    return _launch_fallback_worker(project_root, agent_id, run_id, command)


def submit(args: argparse.Namespace, new_agent: bool) -> int:
    require_managed_platform()
    project_root = resolve_project_root(args.project_root)
    validate_id(args.agent, AGENT_ID, "agent_id")
    if args.actor not in ACTORS:
        raise ContractError("actor_invalid", "actor is invalid")
    request = read_request(args)
    try:
        request_text = request.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("request_invalid", "request must be UTF-8 text") from error
    if not request_text.strip():
        raise ContractError("request_invalid", "request must not be empty")
    receipt_request_hash = getattr(args, "receipt_request_hash", None)
    verified_work_run_id = getattr(args, "verified_work_run_id", None)
    dispatch_id = getattr(args, "dispatch_id", None)
    _capability_document, capability_bindings = read_capability_bindings(
        getattr(args, "capability_binding_file", None)
    )
    capability_binding_hash = (
        hashlib.sha256(capability_bindings).hexdigest()
        if capability_bindings is not None else None
    )
    if dispatch_id is not None:
        validate_id(dispatch_id, DISPATCH_ID, "dispatch_id")
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
    policy = resolve_execution_policy(args, project_root, stored_session)
    args.resolved_execution_policy = policy
    human_approval_policy = resolve_human_approval_policy(args, stored_session)
    args.resolved_human_approval_policy = human_approval_policy
    if role != "main" and human_approval_policy != "required":
        raise ContractError(
            "human_approval_policy_invalid",
            "Human approval bypass is valid only for Main",
        )
    if role == "verification" and verified_work_run_id is None:
        raise ContractError(
            "receipt_binding_invalid",
            "Verification runs require the exact Work run identifier",
        )
    if role != "verification" and verified_work_run_id is not None:
        raise ContractError(
            "receipt_binding_invalid",
            "verified Work run binding is valid only for Verification runs",
        )
    reporting_config = cloud_reporting.read_config(reporting_runtime(), getattr(args, "reporting_config", None))
    reporting_loop_id = getattr(args, "reporting_loop_id", None)
    if reporting_loop_id is not None:
        if reporting_config is None or not cloud_reporting.IDENTIFIER.fullmatch(reporting_loop_id):
            raise ContractError("reporting_binding_invalid", "Loop reporting requires configuration and a valid identity")
    if reporting_config is not None and not cloud_reporting.IDENTIFIER.fullmatch(args.agent):
        raise ContractError("reporting_binding_invalid", "Agent identity is unsupported by the reporting recipient")
    execution_options = requested_execution(args)
    goal_action = getattr(args, "goal_action", None)
    if role != "main" and (execution_options.get("goalMode") is True or goal_action):
        raise ContractError("goal_role_invalid", "Native Goal continuation is Main-only; Work and Verification remain bounded")
    if execution_options.get("goalMode") is True and new_agent and "goalObjective" not in execution_options:
        if len(request_text) > 4000:
            raise ContractError("goal_objective_invalid", "Supply --goal-objective with 1–4000 characters for this longer request")
        execution_options["goalObjective"] = request_text
    operation = "submit" if new_agent else "send"
    request_hash = hashlib.sha256(request).hexdigest()
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
    if execution_options:
        dispatch_tuple["executionOptions"] = execution_options
    if goal_action:
        dispatch_tuple["goalAction"] = goal_action
    if reporting_config is not None:
        dispatch_tuple["reportingConfigHash"] = cloud_reporting.digest(reporting_config)
        dispatch_tuple["reportingLoopId"] = reporting_loop_id
    if capability_binding_hash is not None:
        dispatch_tuple["capabilityBindingHash"] = capability_binding_hash
    agent_path = agent_directory(project_root, args.agent, create=True)
    with file_lock(agent_path / ".dispatch.lock"):
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
        policy_changed = "executionPolicy" not in session or execution_policy.session_policy(session) != policy
        if policy_changed:
            if "executionPolicy" in session and not execution_policy.has_explicit_policy(args):
                raise ContractError("execution_policy_mismatch", "Changing an idle session policy requires a complete explicit policy")
            session = {**session, "executionPolicy": policy, "sandbox": policy["sandboxPolicy"]["type"],
                       "executionPolicySource": "explicit" if execution_policy.has_explicit_policy(args) else "legacy"}
        human_approval_policy_changed = session.get("humanApprovalPolicy", "required") != human_approval_policy
        if human_approval_policy_changed:
            session = {**session, "humanApprovalPolicy": human_approval_policy}
        effective = {**session, **execution_options}
        if effective.get("fast") is True or effective.get("goalMode") is True or goal_action or session.get("backend") == "app-server":
            capabilities = native_codex.inspect_capabilities(str(session["codex"]))
            required = {"fast": effective.get("fast") is True and goal_action in (None, "resume", "reopen"),
                        "goal": effective.get("goalMode") is True or bool(goal_action)}
            for field, needed in required.items():
                if needed and not capabilities["send"][field]:
                    raise ContractError("native_unsupported", capabilities["diagnostic"] or f"Native {field} unsupported")
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
            capability_bindings=capability_bindings,
            reporting_config=reporting_config,
            reporting_loop_id=reporting_loop_id,
            execution_options=execution_options,
            goal_action=goal_action,
        )
        if policy_changed or human_approval_policy_changed:
            session_updates = {"humanApprovalPolicy": human_approval_policy}
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
        self.worker_identity = linux_process_identity(os.getpid())
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
        fact = "process_alive" if process_identity_status(value.get("codexIdentity")) == "match" else "unreachable"
        cloud_reporting.hook(reporting_runtime(), self.state_path, (value["observedAt"], fact))


def cancel_requested(state_path: Path, cancel_event: threading.Event) -> bool:
    if cancel_event.is_set():
        return True
    with contextlib.suppress(ContractError):
        return bool(safe_read_json(state_path).get("cancelRequested"))
    return False


def run_codex_attempt(
    *,
    project_root: Path,
    session: dict[str, Any],
    state: dict[str, Any],
    attempt: int,
    heartbeat: Heartbeat,
    cancel_event: threading.Event,
    expected_agent_id: str,
    expected_run_id: str,
) -> tuple[str, str]:
    state_path = Path(state["requestPath"]).parent / "state.json"
    request = safe_read_bytes(Path(state["requestPath"]), MAX_REQUEST_BYTES)
    if hashlib.sha256(request).hexdigest() != state.get("requestHash"):
        raise AttemptFailure("request_changed", "managed request content changed", False)
    execution = state.get("executionOptions", {})
    session = dict(session)
    try:
        if "executionPolicy" not in session:
            raise ValueError("Legacy queued run lacks a verified permission snapshot; resubmit with current parent or explicit policy")
        stored_policy = execution_policy.session_policy(session)
        policy = execution_policy.normalize(state["executionPolicy"]) if "executionPolicy" in state else stored_policy
        if policy != stored_policy:
            raise ValueError("Run and session execution policies differ")
    except ValueError as error:
        raise AttemptFailure("execution_policy_mismatch", str(error), False) from error
    session["executionPolicy"] = policy
    try:
        checked = execution_preflight.check(str(session["codex"]), policy, project_root, state_path.parent, Path(state["requestPath"]))
    except Exception as error:
        checked = {"passed": False, "error": str(error)}
    if not isinstance(checked, dict):
        checked = {"passed": False, "error": "Invalid execution preflight response"}
    state["executionPolicy"] = policy
    state["executionPreflight"] = checked
    update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update({"executionPreflight": checked, "executionPolicy": policy}))
    if checked.get("passed") is not True:
        raise AttemptFailure("execution_preflight_failed", str(checked.get("error") or checked.get("diagnostic") or "Execution policy preflight failed"), False)
    for key in ("model", "reasoningEffort", "fast", "goalMode"):
        if key in execution:
            session[key] = execution[key]
    if session.get("backend") == "app-server" or session.get("fast") is True or session.get("goalMode") is True or state.get("goalAction"):
        session["backend"] = "app-server"
    # Legacy explicit off is applied as a config override by build_codex_command.
    if session.get("backend") == "app-server":
        session["nativeCapabilities"] = native_codex.inspect_capabilities(str(session["codex"]))["send"]
        state["nativeSessionPath"] = str(state_path.parent / "native-session.json")
        objective = execution.get("goalObjective")
        if session.get("goalMode") is True and not objective and not session.get("goal"):
            text = request.decode("utf-8")
            if len(text) > 4000:
                raise AttemptFailure("goal_objective_invalid", "Supply --goal-objective with 1–4000 characters", False)
            objective = text
        if objective:
            state["goalObjective"] = objective
        atomic_write_json(Path(state["nativeSessionPath"]), session)
        update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update({
            "nativeSessionPath": state["nativeSessionPath"], "goalObjective": objective, "backend": "app-server",
            "goal": session.get("goal"), "goalError": session.get("goalError"),
            "nativeGoalExpected": session.get("goalMode") is True or bool(session.get("goal"))}))
    existing_session = session.get("sessionId")
    command = build_codex_command(session, state, existing_session)
    stderr_path = state_path.parent / "stderr.log"
    reject_symlink(stderr_path)
    update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"status": "starting", "attempt": attempt, "startDisposition": "launching"}
        ),
    )
    try:
        process, codex_identity, release_fd = spawn_contained_process(
            command,
            env={**os.environ, "AGENT_FACTORY_EXECUTION_POLICY": json.dumps(policy, sort_keys=True),
                 "AGENT_FACTORY_PARENT_STATE": str(state_path)},
            cwd=project_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
        )
    except ContractError as error:
        raise AttemptFailure(error.code, error.message, False) from error
    except OSError as error:
        raise AttemptFailure(
            "codex_start_failed", "codex exec could not start", False
        ) from error
    def stop_attempt():
        if session.get("backend") == "app-server":
            try:
                request_native_pause(state_path)
                wait_native_pause(state_path)
            except Exception:
                with contextlib.suppress(Exception):
                    record_goal_uncertainty(state_path, "Native pause could not be confirmed; refresh Goal before reopening")
        terminate_attempt_group(process, codex_identity)

    release_attempted = False
    try:
        update_json(
            state_path,
            state_path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "status": "starting",
                    "attempt": attempt,
                    "codexPid": process.pid,
                    "codexIdentity": codex_identity,
                    "lastCodexIdentity": codex_identity,
                }
            ),
        )
        heartbeat.update(
            status="starting",
            attempt=attempt,
            codex_pid=process.pid,
            codex_identity=codex_identity,
        )
        release_attempted = True
        release_contained_process(process, codex_identity, release_fd)
    except (ContractError, OSError) as error:
        abort_contained_process(
            process,
            codex_identity,
            None if release_attempted else release_fd,
        )
        code = error.code if isinstance(error, ContractError) else "codex_start_failed"
        message = (
            error.message
            if isinstance(error, ContractError)
            else "codex exec could not start"
        )
        raise AttemptFailure(code, message, False, False) from error
    if process.stdin is None or process.stdout is None or process.stderr is None:
        stop_attempt()
        raise AttemptFailure(
            "codex_start_failed", "codex exec pipes are unavailable", False, True
        )
    prompt = build_prompt(
        agent_id=str(state["agentId"]),
        role=str(state["role"]),
        request_path=Path(state["requestPath"]),
        result_path=Path(state["resultPath"]),
        run_id=str(state["runId"]),
        receipt_path=(Path(state["receiptPath"]) if state.get("receiptPath") else None),
        receipt_schema_path=(
            Path(state["receiptSchemaPath"]) if state.get("receiptSchemaPath") else None
        ),
        capability_binding_path=(
            Path(state["capabilityBindingPath"])
            if state.get("capabilityBindingPath") else None
        ),
        human_approval_policy=str(state.get("humanApprovalPolicy", "required")),
    )
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except (BrokenPipeError, OSError, UnicodeError) as error:
        stop_attempt()
        raise AttemptFailure(
            "codex_write_failed", "codex exec rejected the prompt", False, True
        ) from error
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threading.Thread(
        target=read_process_lines, args=(process.stdout, lines), daemon=True
    ).start()
    threading.Thread(
        target=stream_stderr, args=(process.stderr, stderr_path, lines), daemon=True
    ).start()
    started = False
    active_session: str | None = None
    final_messages: list[str] = []
    publication_failed = False
    started_at = time.monotonic()
    start_deadline = started_at + float(session["startTimeout"])
    turn_deadline = started_at + float(session["turnTimeout"])
    stdout_eof = False
    stderr_eof = False
    try:
        while True:
            if cancel_requested(state_path, cancel_event):
                stop_attempt()
                raise AttemptFailure("cancelled", "run was cancelled", started, True)
            current = time.monotonic()
            if not started and current >= start_deadline:
                stop_attempt()
                raise AttemptFailure(
                    "start_timeout", "codex exec sent no start ACK", False, True
                )
            if current >= turn_deadline:
                stop_attempt()
                raise AttemptFailure(
                    "turn_timeout", "codex exec exceeded its turn timeout", started, True
                )
            try:
                kind, line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "error":
                stop_attempt()
                raise AttemptFailure(
                    "event_read_failed", "codex event stream failed", started, True
                )
            if kind == "stderr_error":
                stop_attempt()
                raise AttemptFailure(
                    "stderr_log_failed", "Codex stderr log could not be persisted", started, True
                )
            if kind == "stderr_overflow":
                stop_attempt()
                raise AttemptFailure(
                    "stderr_log_limit_exceeded",
                    "Codex stderr exceeded the per-run byte limit",
                    started,
                    True,
                )
            if kind == "stdout_eof":
                stdout_eof = True
                if stderr_eof:
                    break
                continue
            if kind == "stderr_eof":
                stderr_eof = True
                if stdout_eof:
                    break
                continue
            if line is None or len(line.encode()) > MAX_EVENT_BYTES:
                stop_attempt()
                raise AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            if not append_event(Path(state["eventsPath"]), line):
                stop_attempt()
                raise AttemptFailure(
                    "event_log_limit_exceeded",
                    "Codex events exceeded the per-run byte limit",
                    started,
                    True,
                )
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                stop_attempt()
                raise AttemptFailure(
                    "event_invalid", "codex emitted malformed JSONL", started, True
                ) from error
            if not isinstance(event, dict):
                stop_attempt()
                raise AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            if event.get("type") == "error" and session.get("backend") == "app-server":
                stop_attempt()
                message = str(event.get("message", "Native Codex error"))
                diagnostic = sandbox_diagnostics.sandbox_failure(message)
                raise AttemptFailure("sandbox_unavailable" if diagnostic else "native_backend_error", diagnostic or message, started, True)
            if event.get("type") == "goal.error":
                record_goal_uncertainty(state_path, str(event.get("message", "Native Goal state unconfirmed")))
            if event.get("type") == "thread.started":
                observed = event.get("thread_id")
                if not isinstance(observed, str) or not SESSION_ID.fullmatch(observed):
                    stop_attempt()
                    raise AttemptFailure(
                        "session_invalid", "codex returned an invalid session", started, True
                    )
                if existing_session is not None and observed != existing_session:
                    stop_attempt()
                    raise AttemptFailure(
                        "session_mismatch", "codex resumed a different session", started, True
                    )
                active_session = observed
                started = True
                heartbeat.update(
                    status="running",
                    attempt=attempt,
                    codex_pid=process.pid,
                    codex_identity=codex_identity,
                )
                update_json(
                    state_path,
                    state_path.parent / ".state.lock",
                    lambda value: value.update(
                        {
                            "status": "running", "sessionId": observed,
                            "startedAt": now(), "startDisposition": "started",
                        }
                    ),
                )
                session_path = session_file(project_root, str(state["agentId"]))
                saved = {key: session[key] for key in ("model", "reasoningEffort", "fast", "goalMode", "backend") if key in session}
                saved["sessionId"] = observed
                update_json(session_path, session_path.parent / ".session-state.lock", lambda value: value.update(saved))
            publication_status = result_publication_failure(event, state["resultPath"])
            if publication_status is not None:
                publication_failed = publication_status
            item = event.get("item") if event.get("type") == "item.completed" else None
            if isinstance(item, dict) and item.get("type") in (None, "agent_message"):
                text = item.get("text")
                if isinstance(text, str):
                    final_messages.append(text)
        return_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired as error:
        stop_attempt()
        raise AttemptFailure(
            "codex_exit_timeout", "codex exec did not exit", started, True
        ) from error
    # The leader may exit while descendants keep its isolated process group.
    # Contain that group before validating or returning any post-exit outcome.
    stop_attempt()
    cloud_reporting.hook(reporting_runtime(), state_path, (now(), "process_exited"))
    if return_code != 0:
        raise process_exit_failure(return_code, stderr_path, started)
    if not started or active_session is None:
        raise AttemptFailure(
            "start_ack_missing", "codex exec returned no start ACK", False, True
        )
    if not final_messages:
        raise AttemptFailure("result_missing", "codex exec returned no terminal result", True)
    try:
        terminal = json.loads(final_messages[-1])
    except json.JSONDecodeError as error:
        raise AttemptFailure("result_invalid", "codex returned invalid terminal JSON", True) from error
    valid = (
        isinstance(terminal, dict)
        and set(terminal) == {"status", "resultPath"}
        and terminal.get("status") in {"completed", "needs-human-decision", "failed"}
        and terminal.get("resultPath") == state["resultPath"]
    )
    if not valid:
        raise AttemptFailure("result_invalid", "codex returned an invalid terminal result", True)
    result_path = Path(state["resultPath"])
    try:
        result_info = os.lstat(result_path)
    except FileNotFoundError as error:
        raise missing_result_failure(stderr_path, publication_failed) from error
    if (
        stat.S_ISLNK(result_info.st_mode)
        or not stat.S_ISREG(result_info.st_mode)
        or result_info.st_size == 0
    ):
        raise AttemptFailure("result_file_invalid", "Agent result path is unsafe", True)
    validated_receipt = None
    if terminal["status"] == "completed" and state.get("role") in {"work", "verification"}:
        try:
            validated_receipt = validate_receipt(
                project_root, state, agent_id=expected_agent_id, run_id=expected_run_id)
        except ContractError as error:
            raise AttemptFailure(error.code, error.message, True) from error
    if state.get("cloudReporting"):
        intent = {"status": terminal["status"], "run_id": state["runId"],
                  "agent_id": state["agentId"], "session_id": active_session,
                  "request_sha256": state["requestHash"], "role": state["role"],
                  "result_identity": result_file_identity(result_info),
                  "receipt_sha256": cloud_reporting.digest(validated_receipt) if validated_receipt else None}
        # Retain in the attempt object too: worker's authoritative terminal write
        # includes this intent even if its earlier standalone publication fails.
        state["reportingSemanticIntent"] = intent
        for _ in range(2):
            try:
                update_json(state_path, state_path.parent / ".state.lock",
                            lambda value: value.update({"reportingSemanticIntent": intent,
                                "reportingCaptureError": "reporting_capture_pending"}))
                cloud_reporting.sync_directory(state_path.parent)
                break
            except Exception:
                continue
    return str(terminal["status"]), active_session


def mark_terminal(
    state_path: Path,
    status: str,
    error: dict[str, str] | None = None,
    *,
    attempt: int | None = None,
    start_disposition: str | None = None,
    semantic_intent: dict[str, Any] | None = None,
) -> None:
    def change(value: dict[str, Any]) -> None:
        value.update(
            {
                "status": status,
                "codexPid": None,
                "codexIdentity": None,
                "finishedAt": now(),
                "unread": True,
                "error": error,
            }
        )
        if semantic_intent is not None:
            value["reportingSemanticIntent"] = semantic_intent
            if not value.get("reportingSemanticResult"):
                value["reportingCaptureError"] = "reporting_capture_pending"
        if attempt is not None:
            value["attempt"] = attempt
        if start_disposition is not None:
            value["startDisposition"] = start_disposition

    update_json(state_path, state_path.parent / ".state.lock", change)
    if semantic_intent is not None:
        with contextlib.suppress(OSError):
            cloud_reporting.sync_directory(state_path.parent)
    cloud_reporting.hook(reporting_runtime(), state_path)


def worker(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state_path = state_file(project_root, args.agent, args.run_id)
    state = find_run(project_root, args.agent, args.run_id)
    worker_identity = linux_process_identity(os.getpid())
    update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"workerPid": os.getpid(), "workerIdentity": worker_identity}
        ),
    )
    session = load_session(project_root, args.agent)
    heartbeat = Heartbeat(
        Path(state["heartbeatPath"]), state_path, float(session["heartbeatInterval"])
    )
    cancel_event = threading.Event()

    def request_cancel(_signum: int, _frame: object) -> None:
        cancel_event.set()

    signal.signal(signal.SIGTERM, request_cancel)
    signal.signal(signal.SIGINT, request_cancel)
    heartbeat.start()
    lock_path = agent_directory(project_root, args.agent) / ".session.lock"
    try:
        with file_lock(lock_path):
            state = safe_read_json(state_path)
            if state.get("status") in TERMINAL_STATES:
                return 0
            if state.get("cancelRequested") is True:
                mark_terminal(state_path, "cancelled")
                heartbeat.update(status="cancelled", attempt=0, codex_pid=None)
                return 1
            max_attempts = int(state["maxAttempts"])
            while int(state.get("attempt", 0)) < max_attempts:
                attempt = int(state.get("attempt", 0)) + 1
                try:
                    attempt_state = safe_read_json(state_path)
                    terminal_status, _session_id = run_codex_attempt(
                        project_root=project_root,
                        session=load_session(project_root, args.agent),
                        state=attempt_state,
                        attempt=attempt,
                        heartbeat=heartbeat,
                        cancel_event=cancel_event,
                        expected_agent_id=args.agent,
                        expected_run_id=args.run_id,
                    )
                    mark_terminal(state_path, terminal_status,
                                  semantic_intent=attempt_state.get("reportingSemanticIntent"))
                    heartbeat.update(
                        status=terminal_status, attempt=attempt, codex_pid=None
                    )
                    return 0 if terminal_status != "failed" else 1
                except AttemptFailure as failure:
                    disposition = (
                        "started"
                        if failure.started
                        else "launching"
                        if failure.launched
                        else "not-started"
                    )
                    if failure.code == "cancelled":
                        mark_terminal(
                            state_path,
                            "cancelled",
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(status="cancelled", attempt=attempt, codex_pid=None)
                        return 1
                    if failure.started or failure.launched or attempt >= max_attempts or failure.code in {"execution_preflight_failed", "execution_policy_mismatch"}:
                        mark_terminal(
                            state_path,
                            "failed",
                            {"code": failure.code, "message": failure.message},
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(
                            status="failed", attempt=attempt, codex_pid=None
                        )
                        return 1
                    state = update_json(
                        state_path,
                        state_path.parent / ".state.lock",
                        lambda value: value.update(
                            {
                                "attempt": attempt,
                                "codexPid": None,
                                "codexIdentity": None,
                                "status": "queued",
                                "startDisposition": disposition,
                            }
                        ),
                    )
                    heartbeat.update(status="queued", attempt=attempt, codex_pid=None)
            failure = AttemptFailure(
                "attempts_exhausted", "no execution attempt remained", False
            )
            mark_terminal(
                state_path,
                "failed",
                {"code": failure.code, "message": failure.message},
            )
            heartbeat.update(
                status="failed", attempt=int(state.get("attempt", 0)), codex_pid=None
            )
            return 1
    except ContractError as error:
        with contextlib.suppress(Exception):
            mark_terminal(
                state_path, "failed", {"code": error.code, "message": error.message}
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        with contextlib.suppress(Exception):
            mark_terminal(
                state_path,
                "failed",
                {"code": "worker_failure", "message": str(error)},
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    finally:
        heartbeat.close()


def find_run(project_root: Path, agent_id: str, run_id: str) -> dict[str, Any]:
    path = state_file(project_root, agent_id, run_id)
    state = safe_read_json(path)
    if state.get("agentId") != agent_id or state.get("runId") != run_id:
        raise ContractError("state_invalid", "run identity does not match its managed directory")
    for field, name in {"statePath": "state.json", "requestPath": "request.md", "resultPath": "result.md",
                        "eventsPath": "events.jsonl", "heartbeatPath": "heartbeat.json",
                        "responseSchemaPath": "response.schema.json", "receiptPath": "receipt.json",
                        "receiptSchemaPath": "receipt.schema.json", "capabilityBindingPath": "capability-bindings.json"}.items():
        if state.get(field) is not None and state[field] != str(path.parent / name):
            raise ContractError("state_invalid", "run file path escaped its managed binding")
    return state


def command_status(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    dispatch_id = getattr(args, "dispatch_id", None)
    if dispatch_id is not None:
        validate_id(dispatch_id, DISPATCH_ID, "dispatch_id")
        matches = [state for state in iter_run_states(root, args.agent) if state.get("dispatchId") == dispatch_id]
        if not matches:
            raise ContractError("dispatch_not_found", "dispatch identifier has no managed run")
        if len(matches) != 1:
            raise ContractError("dispatch_id_collision", "dispatch identifier is not unique")
        state = matches[0]
    else:
        state = find_run(root, args.agent, args.run_id)
    heartbeat_path = Path(state["heartbeatPath"])
    heartbeat = safe_read_json(heartbeat_path)
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "status",
            "run": public_state(state),
            "heartbeat": heartbeat,
        }
    )
    return 0


def command_result(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    state = find_run(root, args.agent, args.run_id)
    if state.get("status") not in TERMINAL_STATES:
        raise ContractError("result_not_ready", "run has no terminal result")
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "result",
            "run": public_state(state),
        }
    )
    if args.ack:
        path = state_file(root, args.agent, args.run_id)
        update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update({"unread": False, "readAt": now()}),
        )
    return 0


def iter_agent_directories(root: Path) -> Iterator[Path]:
    if not runtime_paths.resolve(root)["registered"]:
        return
    agents = agent_root(root, create=False)
    if not agents.exists():
        return
    reject_symlink(agents)
    for item in sorted(agents.iterdir(), key=lambda path: path.name):
        if AGENT_ID.fullmatch(item.name) and item.is_dir() and not item.is_symlink():
            yield item


def command_list(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    agents = []
    for directory in iter_agent_directories(root):
        with contextlib.suppress(ContractError):
            agents.append(safe_read_json(directory / "session.json"))
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "agent-list",
            "agents": agents,
        }
    )
    return 0


def iter_run_states(root: Path, selected_agent: str | None = None) -> Iterator[dict[str, Any]]:
    for directory in iter_agent_directories(root):
        if selected_agent is not None and directory.name != selected_agent:
            continue
        runs = directory / "runs"
        if not runs.exists() or runs.is_symlink():
            continue
        for item in sorted(runs.iterdir(), key=lambda path: path.name):
            if item.is_dir() and not item.is_symlink():
                with contextlib.suppress(ContractError):
                    yield safe_read_json(item / "state.json")


def command_inbox(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    if args.agent is not None:
        validate_id(args.agent, AGENT_ID, "agent_id")
    states = [
        state
        for state in iter_run_states(root, args.agent)
        if state.get("status") in TERMINAL_STATES and state.get("unread") is True
    ]
    states.sort(key=lambda value: str(value.get("finishedAt", value.get("updatedAt", ""))))
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "inbox",
            "runs": [public_state(state) for state in states],
        }
    )
    if args.ack:
        for state in states:
            path = state_file(root, str(state["agentId"]), str(state["runId"]))
            update_json(
                path,
                path.parent / ".state.lock",
                lambda value: value.update({"unread": False, "readAt": now()}),
            )
    return 0


def pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def command_cancel(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    path = state_file(root, args.agent, args.run_id)
    state = safe_read_json(path)
    if state.get("status") in TERMINAL_STATES:
        raise ContractError("run_terminal", "run is already terminal")
    state = update_json(
        path,
        path.parent / ".state.lock",
        lambda value: value.update({"cancelRequested": True, "status": "cancelling"}),
    )
    if state.get("backend") == "app-server":
        wait_native_pause(path)
    containment_value = state.get("containment")
    if containment_value is None:
        validate_state_containment_fields(state)
        identities = (
            ("Codex", state.get("codexIdentity")),
            ("worker", state.get("workerIdentity")),
        )
        statuses = [(label, identity, process_identity_status(identity)) for label, identity in identities if identity is not None]
        if any(status in {"unknown", "mismatch"} for _label, _identity, status in statuses):
            raise ContractError(
                "process_identity_mismatch",
                "managed process identity could not be verified; refusing to signal",
            )
        if "containmentAttempt" in state and statuses:
            raise ContractError(
                "containment_identity_unbound",
                "managed processes exist without a bound containment identity; refusing to signal",
            )
        # Migration compatibility for runs accepted before containment binding existed.
        codex_identity = state.get("codexIdentity")
        if isinstance(codex_identity, dict) and process_identity_status(codex_identity) in {"match", "dead"}:
            terminate_verified_group(codex_identity)
        worker_identity = state.get("workerIdentity")
        if isinstance(worker_identity, dict) and process_identity_status(worker_identity) == "match":
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(worker_identity["pid"]), signal.SIGTERM)
    else:
        containment = _validate_state_containment(state)
        if containment["kind"] == "process-group":
            codex_identity = state.get("codexIdentity")
            if codex_identity is not None and process_identity_status(codex_identity) in {"unknown", "mismatch"}:
                raise ContractError(
                    "process_identity_mismatch",
                    "managed Codex identity could not be verified; refusing to signal",
                )
            if isinstance(codex_identity, dict):
                terminate_verified_group(codex_identity)
        request_containment_stop(containment)
        if not wait_containment_empty(containment, PROCESS_TERM_TIMEOUT):
            force_containment_stop(containment)
        if not wait_containment_empty(containment, PROCESS_KILL_TIMEOUT):
            raise ContractError("containment_not_empty", "managed containment did not become empty")
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "ack",
            "status": "cancelling",
            "agentId": args.agent,
            "runId": args.run_id,
        }
    )
    return 0


def heartbeat_stale(state: dict[str, Any], session: dict[str, Any]) -> bool:
    try:
        heartbeat = safe_read_json(Path(state["heartbeatPath"]))
    except ContractError:
        return True
    observed = parse_time(heartbeat.get("observedAt"))
    return observed is None or time.time() - observed > float(session["heartbeatTimeout"])


def event_stream_has_start_marker(state: dict[str, Any]) -> bool:
    try:
        content = safe_read_bytes(Path(state["eventsPath"]), MAX_REQUEST_BYTES)
    except ContractError as error:
        if error.code == "file_not_found":
            return False
        return True
    try:
        lines = content.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError:
        return True
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return True
        if isinstance(event, dict) and event.get("type") == "thread.started":
            return True
    return False


def durably_never_started(state: dict[str, Any]) -> bool:
    return (
        state.get("startDisposition") == "not-started"
        and state.get("containmentLaunchDisposition") != "launching"
        and state.get("status") in {"accepted", "queued"}
        and state.get("startedAt") is None
        and state.get("sessionId") is None
        and not event_stream_has_start_marker(state)
    )


def command_reconcile(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    if args.agent is not None:
        validate_id(args.agent, AGENT_ID, "agent_id")
    reconciled: list[dict[str, Any]] = []
    for state in iter_run_states(root, args.agent):
        if state.get("status") not in ACTIVE_STATES:
            continue
        agent_id = str(state["agentId"])
        session = load_session(root, agent_id)
        if not heartbeat_stale(state, session):
            continue
        containment_value = state.get("containment")
        if containment_value is not None:
            try:
                containment = _validate_state_containment(state)
                if not containment_is_empty(containment):
                    reconciled.append(
                        {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
                    )
                    continue
            except ContractError:
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            # A positively empty bound containment is evaluated below against
            # semantic start evidence; it is never inferred from a numeric PID.
            identity_statuses: list[str] = ["dead"]
        else:
            try:
                validate_state_containment_fields(state)
            except ContractError:
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            if "containmentAttempt" in state and (
                state.get("workerIdentity") is not None or state.get("codexIdentity") is not None
            ):
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            # Legacy states retain their exact boot-ID/start-ticks behavior.
            identity_statuses = [
                process_identity_status(identity)
                for identity in (state.get("workerIdentity"), state.get("codexIdentity"))
                if identity is not None
            ]
        if any(status == "match" for status in identity_statuses):
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
            )
            continue
        if not identity_statuses or any(status == "unknown" for status in identity_statuses):
            reconciled.append(
                {
                    "agentId": agent_id,
                    "runId": state["runId"],
                    "action": "stale-identity-unknown",
                }
            )
            continue
        if not durably_never_started(state):
            path = state_file(root, agent_id, str(state["runId"]))
            started = (
                state.get("startDisposition") == "started"
                or state.get("startedAt") is not None
                or state.get("sessionId") is not None
                or event_stream_has_start_marker(state)
            )
            code = "started_run_not_replayable" if started else "run_start_unknown"
            mark_terminal(
                path,
                "failed",
                {
                    "code": code,
                    "message": "stale managed run cannot be replayed without durable proof that its semantic turn never started",
                },
            )
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "failed-not-replayable"}
            )
            continue
        if int(state.get("attempt", 0)) >= int(state.get("maxAttempts", 1)):
            path = state_file(root, agent_id, str(state["runId"]))
            mark_terminal(
                path,
                "failed",
                {"code": "heartbeat_timeout", "message": "worker heartbeat expired"},
            )
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "failed"}
            )
            continue
        pid = spawn_worker(root, agent_id, str(state["runId"]))
        reconciled.append(
            {
                "agentId": agent_id,
                "runId": state["runId"],
                "action": "resubmitted",
                "workerPid": pid,
            }
        )
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "reconcile",
            "runs": reconciled,
        }
    )
    return 0


def resolve_execution_policy(args: argparse.Namespace, project_root: Path, session: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        stored = execution_policy.session_policy(session) if session is not None and "executionPolicy" in session else None
        policy_args = argparse.Namespace(**vars(args))
        if session is not None and session.get("codex"):
            policy_args.codex = session["codex"]
        policy = execution_policy.resolve(policy_args, project_root, fallback_policy=stored, allow_session_change=session is not None)
        if stored is not None and policy != stored and not execution_policy.has_explicit_policy(args):
            raise ContractError("execution_policy_mismatch", "Changing an idle session policy requires a complete explicit policy")
        if session is not None and stored is None and session.get("sandbox") != policy["sandboxPolicy"]["type"] and not execution_policy.has_explicit_policy(args):
            raise ContractError("execution_policy_mismatch", "Legacy session sandbox differs from current authorized policy")
        return policy
    except (ValueError, OSError) as error:
        raise ContractError("execution_policy_invalid", str(error)) from error


def resolve_human_approval_policy(args: argparse.Namespace, session: dict[str, Any] | None = None) -> str:
    requested = getattr(args, "human_approval_policy", None)
    stored = session.get("humanApprovalPolicy", "required") if session is not None else "required"
    if stored not in HUMAN_APPROVAL_POLICIES:
        raise ContractError("human_approval_policy_invalid", "Stored Human approval policy is invalid")
    return requested if requested is not None else stored


def requested_execution(args: argparse.Namespace) -> dict[str, Any]:
    options = {}
    for argument, key in (("model", "model"), ("reasoning_effort", "reasoningEffort"), ("fast", "fast"), ("goal_mode", "goalMode"), ("goal_objective", "goalObjective")):
        value = getattr(args, argument, None)
        if value is not None:
            options[key] = value
    objective = options.get("goalObjective")
    if objective is not None:
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 4000:
            raise ContractError("goal_objective_invalid", "Goal objective must contain 1–4000 characters")
        if options.get("goalMode") is False:
            raise ContractError("goal_objective_invalid", "An objective cannot be combined with --no-goal-mode")
        options["goalMode"] = True
    return options


def request_native_pause(path: Path) -> None:
    update_json(path, path.parent / ".state.lock", lambda value: value.update({
        "goalControl": {"id": str(uuid.uuid4()), "action": "pause"}}))


def record_goal_uncertainty(path: Path, message: str) -> None:
    fields = {"goalError": message}
    state = update_json(path, path.parent / ".state.lock", lambda value: value.update(fields))
    target = session_file(runtime_paths.project_for(path), str(state["agentId"]))
    update_json(target, target.parent / ".session-state.lock", lambda value: value.update(fields))
    # A full log cannot conceal the diagnostic: status/result and session are
    # authoritative fallbacks even when no more bounded events fit.
    with contextlib.suppress(Exception):
        append_event(Path(state["eventsPath"]), json.dumps({"type": "goal.error", "message": message}) + "\n")


def wait_native_pause(path: Path) -> None:
    # Give the live RPC owner a bounded opportunity before ordinary containment
    # termination. Never open a competing app-server against an active thread.
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = safe_read_json(path)
        if state.get("goalError"):
            return
        if state.get("goal") and state["goal"].get("status") != "active":
            return
        if not state.get("goal") and (state.get("goalObservedAt") or not state.get("nativeGoalExpected")):
            return
        time.sleep(0.05)
    record_goal_uncertainty(path, "Native pause unconfirmed after containment stop; refresh Goal before reopening")


def command_goal(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    session = load_session(root, args.agent)
    if session["role"] != "main":
        raise ContractError("goal_role_invalid", "Goal controls belong to Main")
    if args.action == "get":
        emit({"kind": "goal", "agentId": args.agent, "sessionId": session.get("sessionId"),
              "goal": session.get("goal"), "observedAt": session.get("goalObservedAt"),
              "error": session.get("goalError"), "source": "last-native-observation"})
        return 0
    if not session.get("sessionId"):
        raise ContractError("session_missing", "Start a Main session with a Goal first")
    directory = agent_directory(root, args.agent)
    with file_lock(directory / ".dispatch.lock"):
        active = [state for state in iter_run_states(root, args.agent) if state.get("status") in ACTIVE_STATES]
        if active:
            if len(active) != 1 or args.action in ("resume", "reopen"):
                raise ContractError("session_busy", "Pause the active run before reopening Goal")
            state = active[0]
            if state.get("backend") != "app-server":
                raise ContractError("goal_unavailable", "The active run does not own a native Goal connection")
            path = Path(state["statePath"])
            control = {"id": str(uuid.uuid4()), "action": "get" if args.action == "refresh" else args.action}
            update_json(path, path.parent / ".state.lock", lambda value: value.update({"goalControl": control}))
            emit({"kind": "goal-control", "status": "accepted", "agentId": args.agent, "runId": state["runId"], **control})
            return 0
    # Reuse managed acceptance, locks, process containment, events and run results.
    if args.action in ("resume", "reopen") and not session.get("goal"):
        raise ContractError("goal_missing", "Goal was cleared; send a new objective with Goal enabled")
    send_args = parse_args(["send", "--project-root", str(root), "--agent", args.agent,
                           "--actor", "human", "--message", "Continue the existing native Goal through the Main → Work → Verification graph.",
                           *(["--goal-mode"] if args.action in ("resume", "reopen") else ["--no-goal-mode"] if args.action in ("clear", "cancel", "disable") else [])])
    send_args.goal_action = "get" if args.action == "refresh" else args.action
    return submit(send_args, False)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        if arguments and arguments[0] == "doctor":
            return sandbox_diagnostics.main(arguments[1:])
        args = parse_args(arguments)
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
            codex = args.codex
            session = None
            if args.agent:
                session = load_session(resolve_project_root(args.project_root), args.agent)
                codex = session["codex"]
            capabilities = dict(native_codex.inspect_capabilities(codex))
            if session is not None and "executionPolicy" in session:
                capabilities["executionMode"] = (
                    "bypass"
                    if session.get("humanApprovalPolicy") == "bypass"
                    else execution_policy.session_policy(session)["sandboxPolicy"]["type"]
                )
            emit(capabilities)
            return 0
        if args.command == "goal":
            return command_goal(args)
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
        if args.command == "inbox":
            return command_inbox(args)
        if args.command == "cancel":
            return command_cancel(args)
        if args.command == "reconcile":
            return command_reconcile(args)
        if args.command in {"reporting-deliver", "_report-send"}:
            try:
                root = resolve_project_root(args.project_root)
                state = find_run(root, args.agent, args.run_id)
                if not state.get("cloudReporting"):
                    emit({"reporting": None})
                elif args.command == "_report-send":
                    emit({"ack": cloud_reporting.send_one(reporting_runtime(), root, state, args.entry)})
                else:
                    emit({"reporting": cloud_reporting.deliver(reporting_runtime(), root, state)})
                return 0
            except Exception:
                emit({"reporting": {"pending": True, "error": "reporting_delivery_pending"}})
                return 1
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


if __name__ == "__main__":
    raise SystemExit(main())
