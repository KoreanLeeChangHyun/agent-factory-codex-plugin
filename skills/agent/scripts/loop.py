#!/usr/bin/env python3
"""Orchestrate the Agent Factory Work/Verification loop."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.dont_write_bytecode = True
import exec as agent_exec


SCHEMA_VERSION = "0.1.0"
CHILD_TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled"}
RECEIPT_RECOVERY_ERRORS = {
    "receipt_missing", "receipt_format_invalid", "receipt_path_contract_invalid",
}
LEGACY_PATH_CONTRACT_ERRORS = {
    "changedPaths must be bounded relative paths",
    "changedPaths must contain only project-root-relative paths",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def role_model_options(execution: dict[str, Any], role: str, operation: str) -> dict[str, Any]:
    """Bind role overrides on every turn; retain the legacy shared submit model."""
    profile = execution.get("agentModels", {}).get(role, {})
    options = dict(profile)
    if operation == "submit" and not options.get("model") and execution.get("model"):
        options["model"] = execution["model"]
    return options


class AgentRuntime:
    """Call only the public managed-session interface."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.runtime_binding = agent_exec.runtime_paths.resolve(project_root, create=True)
        self.script = Path(agent_exec.__file__).resolve()

    def call(self, arguments: list[str]) -> dict[str, Any]:
        process = subprocess.run(
            [sys.executable, str(self.script), *arguments, "--project-root", str(self.project_root), *agent_exec.runtime_paths.arguments(self.project_root)],
            cwd=self.project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        if not lines:
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime returned no response")
        try:
            response = json.loads(lines[-1])
        except json.JSONDecodeError as error:
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime response is invalid") from error
        if not isinstance(response, dict):
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime response is invalid")
        if process.returncode != 0 or response.get("kind") == "error":
            detail = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise agent_exec.ContractError(
                str(detail.get("code", "child_runtime_failure")),
                str(detail.get("message", "Agent runtime command failed")),
            )
        return response

    def dispatch(
        self,
        *,
        operation: str,
        agent_id: str,
        role: str,
        request_file: Path,
        request_hash: str,
        dispatch_id: str,
        verified_work_run_id: str | None,
        execution: dict[str, Any],
        capability_binding_file: Path | None,
        human_approval_policy: str,
    ) -> dict[str, Any]:
        profile = execution.get("agentPermissions", {}).get(role)
        if profile:
            execution = {**execution, "executionPolicy": profile["policy"], "executionPolicyPath": profile["path"]}
            human_approval_policy = profile["humanApprovalPolicy"]
        arguments = [
            operation,
            "--agent", agent_id,
            "--request-file", str(request_file),
            "--receipt-request-hash", request_hash,
            "--dispatch-id", dispatch_id,
            "--human-approval-policy", human_approval_policy,
        ]
        if execution.get("taskListPath"):
            import task_binding
            current_binding = task_binding.load(agent_exec.safe_read_json, Path(execution["taskListPath"]), execution["taskBinding"]["taskId"], request_hash)
            if current_binding != execution["taskBinding"]:
                raise agent_exec.ContractError("task_binding_invalid", "The loop task snapshot changed before dispatch")
            arguments.extend(["--task-list-file", execution["taskListPath"], "--task-id", execution["taskBinding"]["taskId"]])
        if execution.get("executionPolicyPath"):
            if agent_exec.safe_read_json(Path(execution["executionPolicyPath"])) != execution["executionPolicy"]:
                raise agent_exec.ContractError("execution_policy_mismatch", "Loop execution policy snapshot changed")
            arguments.extend(["--execution-policy-file", execution["executionPolicyPath"]])
        if operation == "submit":
            arguments.extend([
                "--role", role,
                "--codex", str(execution["codex"]),
            ])
        for key, value in role_model_options(execution, role, operation).items():
            arguments.extend(["--model" if key == "model" else "--reasoning-effort", str(value)])
        if role == "work" and execution.get("taskMode"):
            arguments.extend(["--task-mode", execution["taskMode"]])
        if verified_work_run_id is not None:
            arguments.extend(["--verified-work-run-id", verified_work_run_id])
        if capability_binding_file is not None:
            arguments.extend(["--capability-binding-file", str(capability_binding_file)])
        return self.call(arguments)

    def status(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--run-id", run_id])["run"]

    def status_dispatch(self, agent_id: str, dispatch_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--dispatch-id", dispatch_id])["run"]


def loop_directory(root: Path, work_agent: str, loop_id: str, *, create: bool = False) -> Path:
    agent_exec.validate_id(work_agent, agent_exec.AGENT_ID, "agent_id")
    agent_exec.validate_id(loop_id, agent_exec.AGENT_ID, "loop_id")
    directory = agent_exec.agent_directory(root, work_agent, create=create) / "loops" / loop_id
    if create:
        agent_exec.ensure_directory(directory, agent_exec.find_project_anchor(directory))
    return directory


def state_path(root: Path, work_agent: str, loop_id: str) -> Path:
    return loop_directory(root, work_agent, loop_id) / "state.json"


def read_state(root: Path, work_agent: str, loop_id: str) -> tuple[Path, dict[str, Any]]:
    path = state_path(root, work_agent, loop_id)
    return path, agent_exec.safe_read_json(path)


def upgrade_execution_policy(state: dict[str, Any], path: Path, args: argparse.Namespace, root: Path) -> None:
    """Upgrade only operational loop metadata using current authority."""
    execution = state.get("execution")
    if not isinstance(execution, dict):
        raise agent_exec.ContractError("loop_state_invalid", "Loop execution settings are missing")
    if execution.get("executionPolicy") is not None and execution.get("executionPolicyPath"):
        return
    policy_args = argparse.Namespace(**vars(args))
    policy_args.codex = execution.get("codex", "codex")
    if getattr(policy_args, "sandbox", None) is None:
        policy_args.sandbox = execution.get("sandbox")
    if execution.get("executionPolicy") is None:
        policy = agent_exec.resolve_execution_policy(policy_args, root)
    else:
        try:
            policy = agent_exec.execution_policy.normalize(execution["executionPolicy"])
        except ValueError as error:
            raise agent_exec.ContractError("execution_policy_invalid", str(error)) from error
    if execution.get("sandbox") is not None and execution["sandbox"] != policy["sandboxPolicy"]["type"]:
        raise agent_exec.ContractError("execution_policy_mismatch", "Legacy loop sandbox differs from current authorized policy")
    policy_path = path.parent / "execution-policy.json"
    agent_exec.atomic_write_json(policy_path, policy)
    execution.update(executionPolicy=policy, executionPolicyPath=str(policy_path))
    if isinstance(state.get("pendingDispatch"), dict):
        # An already accepted historical run retains its original immutable tuple.
        state["pendingDispatch"]["legacyPolicyUnbound"] = True
    state["updatedAt"] = now()
    agent_exec.atomic_write_json(path, state)


def observed_task_status(child):
    status = child.get("status")
    if status == "needs-human-decision":
        return "blocked"
    if status in {"failed", "cancelled"}:
        return status
    # Completion still requires the selected route's receipt processing.
    return "running"


def public_state(state: dict[str, Any], child: dict[str, Any] | None = None) -> dict[str, Any]:
    workflow = copy.deepcopy(state.get("workflow"))
    if workflow and child and state.get("status") == "active":
        task = workflow["tasks"][workflow["index"]]
        current = state.get("currentChild") or {}
        role = current.get("role")
        if (role in {"work", "verification"} and current.get("runId") == child.get("runId")
                and current.get("agentId") == child.get("agentId")
                and task.get(role + "RunId") == child.get("runId")
                and task.get(role + "AgentId") == child.get("agentId")):
            task[role + "Status"] = observed_task_status(child)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "work-verification-loop",
        "loopId": state["loopId"],
        "workflow": workflow,
        "taskMode": state.get("execution", {}).get("taskMode", "work-verification"),
        "status": state["status"],
        "phase": state["phase"],
        "workAgentId": state["workAgentId"],
        "verificationAgentId": state["verificationAgentId"],
        "latestWorkRunId": state.get("latestWorkRunId"),
        "latestVerificationRunId": state.get("latestVerificationRunId"),
        "humanSkip": state.get("humanSkip"),
        "pendingDispatch": state.get("pendingDispatch"),
        "controlPlaneError": state.get("controlPlaneError"),
        "receiptRecovery": state.get("receiptRecovery"),
        "currentChild": child,
        "terminalReason": state.get("terminalReason"),
        "statePath": state["statePath"],
    }


def write_request(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    agent_exec.atomic_write(path, content.encode("utf-8"))
    return path


def assigned_agent(state: dict[str, Any], role: str) -> str:
    """Keep the loop storage owner stable while routing each task to its assignee."""
    workflow = state.get("workflow")
    task = workflow["tasks"][workflow["index"]] if workflow else {}
    return task.get(role + "AgentId", state[role + "AgentId"])


def validate_assignments(tasks, root, work_agent, verification_agent):
    work_ids, verification_ids = set(), set()
    for task in tasks:
        work_ids.add(task.get("workAgentId", work_agent))
        verifier = task.get("verificationAgentId", verification_agent)
        if verifier:
            verification_ids.add(verifier)
    if tasks[0].get("workAgentId", work_agent) != work_agent:
        raise agent_exec.ContractError("task_assignment_invalid", "The first task must use --work-agent, the stable loop owner")
    if work_ids & verification_ids:
        raise agent_exec.ContractError("agent_identity_conflict", "Work and Verification must use separate sessions across the entire list")
    for role, identifiers in (("work", work_ids), ("verification", verification_ids)):
        for agent_id in identifiers:
            try:
                session = agent_exec.session_file(root, agent_id)
            except agent_exec.ContractError as error:
                if error.code == "project_uninitialized":
                    continue
                raise
            if session.exists() and agent_exec.safe_read_json(session).get("role") != role:
                raise agent_exec.ContractError("agent_identity_conflict", "An assigned session has a different role")


def prepare_dispatch(
    state: dict[str, Any], path: Path, *, role: str, request_file: Path,
    verified_work_run_id: str | None = None,
    recovery_of_run_id: str | None = None,
) -> None:
    if role not in {"work", "verification"}:
        raise agent_exec.ContractError("graph_role_invalid", "dispatch role is outside the graph")
    if isinstance(state.get("pendingDispatch"), dict):
        raise agent_exec.ContractError("dispatch_intent_exists", "a durable dispatch intent already exists")
    if role == "verification" and state.get("execution", {}).get("taskMode") in ("work", "plan-work"):
        raise agent_exec.ContractError("graph_transition_invalid", "This mode does not request separate Verification")
    if role == "verification" and (
        not isinstance(state.get("latestWorkRunId"), str)
        or verified_work_run_id != state.get("latestWorkRunId")
    ):
        raise agent_exec.ContractError("graph_transition_invalid", "Verification must bind the latest Work run")
    if recovery_of_run_id is not None and (
        role != "work" or recovery_of_run_id != state.get("latestWorkRunId")
    ):
        raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Receipt recovery must bind the failed latest Work run")
    if (
        role == "work" and state.get("latestWorkRunId") is not None
        and state.get("lastVerificationDecision") != "fail"
        and recovery_of_run_id is None
    ):
        raise agent_exec.ContractError("graph_transition_invalid", "a Work revision requires failed Verification")
    agent_id = assigned_agent(state, role)
    root = Path(state["projectRoot"])
    operation = "send" if agent_exec.session_file(root, agent_id).exists() else "submit"
    if recovery_of_run_id is not None and operation != "send":
        raise agent_exec.ContractError("receipt_recovery_session_invalid", "Receipt recovery requires the existing Work session")
    content = agent_exec.safe_read_bytes(request_file, agent_exec.MAX_REQUEST_BYTES)
    role_binding = state.get("capabilityBindings", {}).get(role, {})
    state["pendingDispatch"] = {
        "dispatchId": f"dispatch-{uuid.uuid4().hex}",
        "operation": operation,
        "agentId": agent_id,
        "role": role,
        "workGoal": role == "work",
        "requestPath": str(request_file),
        "requestHash": hashlib.sha256(content).hexdigest(),
        "receiptRequestHash": state["originalRequestHash"],
        "verifiedWorkRunId": verified_work_run_id,
        "capabilityBindingPath": role_binding.get("path"),
        "capabilityBindingHash": role_binding.get("hash"),
    }
    if recovery_of_run_id is not None:
        state["pendingDispatch"]["recoveryOfRunId"] = recovery_of_run_id
    state["phase"] = f"{role}-dispatching"
    state["updatedAt"] = now()
    agent_exec.atomic_write_json(path, state)


def complete_pending_dispatch(
    state: dict[str, Any], path: Path, runtime: AgentRuntime,
) -> dict[str, Any]:
    pending = state.get("pendingDispatch")
    if not isinstance(pending, dict):
        raise agent_exec.ContractError("dispatch_intent_missing", "durable dispatch intent is missing")
    if pending.get("recoveryOfRunId") is not None:
        recovery = state.get("receiptRecovery")
        if (
            not isinstance(recovery, dict)
            or recovery.get("failedWorkRunId") != pending["recoveryOfRunId"]
            or recovery.get("requestPath") != pending.get("requestPath")
            or recovery.get("requestHash") != pending.get("requestHash")
        ):
            raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Receipt recovery intent binding is invalid")
    try:
        run = runtime.status_dispatch(pending["agentId"], pending["dispatchId"])
    except agent_exec.ContractError as error:
        if error.code != "dispatch_not_found":
            raise
        acknowledgement = runtime.dispatch(
            operation=pending["operation"],
            agent_id=pending["agentId"],
            role=pending["role"],
            request_file=Path(pending["requestPath"]),
            request_hash=pending["receiptRequestHash"],
            dispatch_id=pending["dispatchId"],
            verified_work_run_id=pending["verifiedWorkRunId"],
            execution=state["execution"],
            capability_binding_file=(
                Path(pending["capabilityBindingPath"])
                if pending.get("capabilityBindingPath") else None
            ),
            human_approval_policy="required",
        )
        run = runtime.status(pending["agentId"], str(acknowledgement["runId"]))
    role_permission = state["execution"].get("agentPermissions", {}).get(pending["role"], {})
    expected_tuple = {
        "agentId": pending["agentId"],
        "role": pending["role"],
        "actor": "main",
        "requestHash": pending["requestHash"],
        "receiptRequestHash": pending["receiptRequestHash"],
        "verifiedWorkRunId": pending["verifiedWorkRunId"],
        "operation": pending["operation"],
        "humanApprovalPolicy": role_permission.get("humanApprovalPolicy", "required"),
    }
    if "executionPolicy" in state["execution"] and not (
        pending.get("legacyPolicyUnbound") and "executionPolicy" not in run.get("dispatchTuple", {})
    ):
        expected_tuple["executionPolicy"] = role_permission.get("policy", state["execution"]["executionPolicy"])
    model_options = role_model_options(state["execution"], pending["role"], pending["operation"])
    if model_options:
        expected_tuple["executionOptions"] = model_options
    if pending["role"] == "work" and state["execution"].get("taskMode"):
        expected_tuple.setdefault("executionOptions", {})["taskMode"] = state["execution"]["taskMode"]
    if pending.get("capabilityBindingHash") is not None:
        expected_tuple["capabilityBindingHash"] = pending["capabilityBindingHash"]
    if state["execution"].get("taskBinding"):
        expected_tuple["taskBinding"] = state["execution"]["taskBinding"]
    if pending.get("workGoal"):
        from task_modes import work_goal_options
        content = agent_exec.safe_read_bytes(Path(pending["requestPath"]), agent_exec.MAX_REQUEST_BYTES)
        if hashlib.sha256(content).hexdigest() != pending["requestHash"]:
            raise agent_exec.ContractError("dispatch_identity_mismatch", "Pending Work request changed")
        expected_tuple["executionOptions"] = work_goal_options(
            expected_tuple.get("executionOptions", {}), content.decode("utf-8"))
    actual_tuple = run.get("dispatchTuple")
    # Parent linkage is added by exec, independently of the loop's dispatch
    # intent. Validate it against the accepted run, not the current caller:
    # reconciliation can be performed by another Main run or the extension.
    parent_keys = ("parentAgentId", "parentRunId")
    if isinstance(actual_tuple, dict) and any(key in actual_tuple or key in run for key in parent_keys):
        for key in parent_keys:
            value = actual_tuple.get(key)
            if not isinstance(value, str) or not agent_exec.AGENT_ID.fullmatch(value) or run.get(key) != value:
                raise agent_exec.ContractError("dispatch_binding_invalid", "managed parent linkage does not match accepted run")
            expected_tuple[key] = value
    if isinstance(actual_tuple, dict) and "humanApprovalPolicy" not in actual_tuple:
        # Historical managed runs predate this tuple field; omission represented
        # the only then-supported behavior, which is today's required default.
        actual_tuple = {**actual_tuple, "humanApprovalPolicy": "required"}
    if run.get("dispatchId") != pending["dispatchId"] or actual_tuple != expected_tuple:
        raise agent_exec.ContractError("dispatch_binding_invalid", "managed run does not match durable dispatch intent")
    role = pending["role"]
    run_id = str(run["runId"])
    state["currentChild"] = {"role": role, "agentId": pending["agentId"], "runId": run_id}
    state["phase"] = f"{role}-running"
    if state.get("workflow"):
        task = state["workflow"]["tasks"][state["workflow"]["index"]]
        task["workStatus" if role == "work" else "verificationStatus"] = observed_task_status(run)
        task[role + "RunId"] = run_id
        task[role + "AgentId"] = pending["agentId"]
    if role == "work":
        state["latestWorkRunId"] = run_id
    else:
        state["latestVerificationRunId"] = run_id
    state["pendingDispatch"] = None
    state["controlPlaneError"] = None
    state["status"] = "active"
    if pending.get("recoveryOfRunId") is not None:
        recovery = state.get("receiptRecovery")
        if not isinstance(recovery, dict) or recovery.get("failedWorkRunId") != pending["recoveryOfRunId"]:
            raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Receipt recovery audit linkage is invalid")
        recovery.update({"recoveryWorkRunId": run_id, "dispatchedAt": now()})
    state["updatedAt"] = now()
    agent_exec.atomic_write_json(path, state)
    return run


def dispatch(
    state: dict[str, Any], path: Path, runtime: AgentRuntime, *, role: str,
    request_file: Path, verified_work_run_id: str | None = None,
    recovery_of_run_id: str | None = None,
) -> dict[str, Any]:
    prepare_dispatch(
        state, path, role=role, request_file=request_file,
        verified_work_run_id=verified_work_run_id,
        recovery_of_run_id=recovery_of_run_id,
    )
    return complete_pending_dispatch(state, path, runtime)


def start_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    agent_exec.validate_id(args.work_agent, agent_exec.AGENT_ID, "work_agent")
    mode = getattr(args, "task_mode", "work-verification")
    if mode not in ("work", "plan-work") and not args.verification_agent:
        raise agent_exec.ContractError("verification_agent_required", "This route requires Verification")
    if args.verification_agent:
        agent_exec.validate_id(args.verification_agent, agent_exec.AGENT_ID, "verification_agent")
    if args.work_agent == args.verification_agent:
        raise agent_exec.ContractError("agent_identity_conflict", "Work and Verification require different Agent sessions")
    request = agent_exec.safe_read_bytes(args.request_file, agent_exec.MAX_REQUEST_BYTES)
    if not request.decode("utf-8").strip():
        raise agent_exec.ContractError("request_invalid", "request must not be empty")
    import task_binding
    if getattr(args, "task_list_file", None) is None or not getattr(args, "task_id", None):
        raise agent_exec.ContractError("task_binding_required", "Delegated execution requires --task-list-file and --task-id before dispatch")
    # Read once, normalize a private snapshot, and hash exactly the bytes we retain.
    submitted_document = agent_exec.safe_read_json(args.task_list_file)
    parent = agent_exec.managed_parent_identity(root)
    if parent is not None:
        import task_announcement
        with agent_exec.file_lock(agent_exec.agent_directory(root, parent["agentId"]) / ".dispatch.lock"):
            agent_exec.require_current_parent_conversation(root, parent)
            task_announcement.check_submission(agent_exec.safe_read_json,
                agent_exec.state_file(root, parent["agentId"], parent["runId"]), parent, submitted_document)
    task_document, binding = task_binding.resolve(
        submitted_document, args.task_id, hashlib.sha256(request).hexdigest())
    tasks = task_document["tasks"]
    if args.task_id != tasks[0]["id"]:
        raise agent_exec.ContractError("task_order_invalid", "Submit the first task; the engine executes the whole list in order")
    validate_assignments(tasks, root, args.work_agent, args.verification_agent)
    for task in tasks:
        task.setdefault("workAgentId", args.work_agent)
        if args.verification_agent:
            task.setdefault("verificationAgentId", args.verification_agent)
    binding = task_binding.validate(task_document, args.task_id, hashlib.sha256(request).hexdigest())
    task_requests = []
    for index, task in enumerate(tasks):
        content = request if index == 0 else agent_exec.safe_read_bytes(Path(task["requestFile"]), agent_exec.MAX_REQUEST_BYTES) if isinstance(task.get("requestFile"), str) else None
        if content is None or not content.decode("utf-8").strip():
            raise agent_exec.ContractError("task_request_invalid", "Every subsequent task requires a matching requestFile before execution")
        task["requestHash"] = hashlib.sha256(content).hexdigest()
        task_requests.append(content)
    loop_id = f"loop-{uuid.uuid4().hex[:16]}"
    directory = loop_directory(root, args.work_agent, loop_id, create=True)
    # Establish the per-loop lock as part of loop creation so later rejected
    # control-plane operations never create a new artifact.
    with agent_exec.file_lock(directory / ".loop.lock"):
        pass
    workflow_tasks = []
    for index, (task, content) in enumerate(zip(tasks, task_requests)):
        request_path = directory / f"task-{index}.md"
        agent_exec.atomic_write(request_path, content)
        workflow_tasks.append({**task, "requestPath": str(request_path), "workStatus": "pending", "verificationStatus": "pending"})
    task_list_path = directory / "task-list.json"
    agent_exec.atomic_write_json(task_list_path, task_document)
    original = directory / "original-request.md"
    agent_exec.atomic_write(original, request)
    policy = agent_exec.resolve_execution_policy(args, root)
    policy_path = directory / "execution-policy.json"
    agent_exec.atomic_write_json(policy_path, policy)
    role_permissions = {}
    for role in ("work", "verification"):
        permission_mode = getattr(args, role + "_execution_mode", None)
        if permission_mode is None:
            continue
        locator = os.environ.get(agent_exec.execution_policy.PARENT_STATE_ENV)
        if locator:
            captured = agent_exec.safe_read_json(Path(locator)).get("executionOptions", {}).get("agentPermissions", {}).get(role)
            if captured is not None and permission_mode != captured:
                raise agent_exec.ContractError("execution_policy_mismatch", "Role permission mode differs from captured Human selection")
        selected = agent_exec.execution_policy.role_policy(permission_mode, policy, root)
        authorized = agent_exec.execution_policy.authorized_role_policy(role, policy, str(root))
        if os.environ.get(agent_exec.execution_policy.PARENT_STATE_ENV) and selected != (authorized or policy):
            raise agent_exec.ContractError("execution_policy_mismatch", "Role permissions differ from captured Human selection")
        role_path = directory / f"{role}-execution-policy.json"
        agent_exec.atomic_write_json(role_path, selected)
        role_permissions[role] = {"policy": selected, "path": str(role_path), "humanApprovalPolicy": "bypass" if permission_mode == "bypass" else "required"}
    capability_bindings: dict[str, dict[str, str | None]] = {}
    for role in ("work", "verification"):
        _binding_document, binding_bytes = agent_exec.read_capability_bindings(
            getattr(args, f"{role}_capability_binding_file", None)
        )
        binding_path = None
        binding_hash = None
        if binding_bytes is not None:
            binding_path = directory / f"{role}-capability-bindings.json"
            agent_exec.atomic_write(binding_path, binding_bytes)
            binding_hash = hashlib.sha256(binding_bytes).hexdigest()
        capability_bindings[role] = {
            "path": str(binding_path) if binding_path else None,
            "hash": binding_hash,
        }
    created = now()
    path = directory / "state.json"
    state = {
        "schemaVersion": SCHEMA_VERSION,
        "loopId": loop_id,
        "status": "active",
        "phase": "starting",
        "projectRoot": str(root),
        "statePath": str(path),
        "originalRequestPath": str(original),
        "originalRequestHash": hashlib.sha256(request).hexdigest(),
        "capabilityBindings": capability_bindings,
        "workAgentId": args.work_agent,
        "verificationAgentId": args.verification_agent,
        "latestWorkRunId": None,
        "latestVerificationRunId": None,
        "lastVerificationDecision": None,
        "pendingFindingIds": [],
        "currentChild": None,
        "humanSkip": None,
        "pendingDispatch": None,
        "controlPlaneError": None,
        "receiptRecovery": None,
        "terminalReason": None,
        "workflow": {"id": task_document["id"], "title": task_document["title"], "index": 0, "tasks": workflow_tasks},
        "parentStatePath": os.environ.get(agent_exec.execution_policy.PARENT_STATE_ENV),
        "execution": {"taskListPath": str(task_list_path), "taskBinding": binding, "taskMode": mode, "codex": args.codex, "model": args.model,
                      "agentModels": {role: {key: value for key, value in {"model": getattr(args, role + "_model", None), "reasoningEffort": getattr(args, role + "_reasoning_effort", None)}.items() if value} for role in ("work", "verification")},
                      "executionPolicy": policy, "executionPolicyPath": str(policy_path), "agentPermissions": role_permissions},
        "createdAt": created,
        "updatedAt": created,
    }
    agent_exec.atomic_write_json(path, state)
    dispatch(state, path, AgentRuntime(root), role="work", request_file=original)
    return public_state(state, state["currentChild"])


def verification_request(state: dict[str, Any], work: dict[str, Any], directory: Path) -> Path:
    recovery_evidence = ""
    recovery = state.get("receiptRecovery")
    if isinstance(recovery, dict) and recovery.get("recoveryWorkRunId") == work.get("runId"):
        recovery_evidence = f"""
Receipt recovery evidence:
- Failed Work run: {recovery['failedWorkRunId']}
- Preserved failed result: {recovery['failedResultPath']}
- Preserved failed receipt: {recovery['failedReceiptPath']}
"""
    return write_request(directory, f"verification-{work['runId']}.md", f"""Verify this Work result.

Original request: {state['originalRequestPath']}
Work run: {work['runId']}
Work result: {work['resultPath']}
Work receipt: {work['receiptPath']}
{recovery_evidence}
""")


def revision_request(state: dict[str, Any], verification: dict[str, Any], receipt: dict[str, Any], directory: Path) -> Path:
    findings = json.dumps(receipt["findings"], ensure_ascii=False, indent=2)
    return write_request(directory, f"revision-{verification['runId']}.md", f"""Address these failed Verification findings.

Original request: {state['originalRequestPath']}
Previous Work run: {state['latestWorkRunId']}
Verification result: {verification['resultPath']}
Findings:
{findings}
""")


def receipt_recovery_request(
    state: dict[str, Any], failed: dict[str, Any], error: dict[str, Any], directory: Path,
) -> Path:
    finding_ids = json.dumps(state.get("pendingFindingIds", []), ensure_ascii=False)
    return write_request(directory, f"receipt-recovery-{failed['runId']}.md", f"""Recover from a receipt publication or validation failure without repeating Work effects.

Original request: {state['originalRequestPath']}
Failed Work run: {failed['runId']}
Preserved result: {failed['resultPath']}
Preserved receipt: {failed['receiptPath']}
Failure: {error['code']}: {error['message']}
Required addressed finding IDs: {finding_ids}

Do not repeat any already performed tool effect, external action, or project modification.
Do not modify the failed run or its artifacts. Use the preserved evidence to write a
fresh result and a corrected receipt for this recovery run. In `changedPaths`, report
only project-root-relative paths changed by the failed Work; report runtime-only
artifacts in the detailed result and use an empty array when the project was untouched.
Capability outcomes must describe this recovery run; do not re-invoke a capability
merely to reproduce an earlier outcome.
""")


def recover_receipt(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] == "cancelled":
            return public_state(state)
        runtime = AgentRuntime(root)
        recovery = state.get("receiptRecovery")
        if isinstance(recovery, dict):
            if isinstance(state.get("pendingDispatch"), dict):
                child = complete_pending_dispatch(state, path, runtime)
                return public_state(state, child)
            if recovery.get("recoveryWorkRunId") is None:
                content = agent_exec.safe_read_bytes(Path(recovery["requestPath"]), agent_exec.MAX_REQUEST_BYTES)
                if hashlib.sha256(content).hexdigest() != recovery.get("requestHash"):
                    raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Receipt recovery request changed after intent publication")
                upgrade_execution_policy(state, path, args, root)
                dispatch(
                    state, path, runtime, role="work",
                    request_file=Path(recovery["requestPath"]),
                    recovery_of_run_id=recovery["failedWorkRunId"],
                )
                return public_state(state, state["currentChild"])
            if state.get("status") == "completed":
                return public_state(state)
            current = state.get("currentChild")
            recovery_is_current = (
                isinstance(current, dict)
                and current.get("runId") == recovery.get("recoveryWorkRunId")
            )
            verification_of_recovery_is_current = (
                isinstance(current, dict) and current.get("role") == "verification"
                and state.get("latestWorkRunId") == recovery.get("recoveryWorkRunId")
            )
            if not recovery_is_current and not verification_of_recovery_is_current:
                raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Recovery run no longer matches the loop child")
            child = runtime.status(current["agentId"], current["runId"])
            return public_state(state, child)
        if state.get("status") != "runtime-error" or state.get("phase") != "control-plane-error":
            raise agent_exec.ContractError("receipt_recovery_unavailable", "Loop is not stopped on a recoverable receipt failure")
        if state.get("pendingDispatch") is not None:
            raise agent_exec.ContractError("receipt_recovery_ambiguous", "Loop has an unresolved dispatch intent")
        current = state.get("currentChild")
        if (
            not isinstance(current, dict) or current.get("role") != "work"
            or current.get("runId") != state.get("latestWorkRunId")
        ):
            raise agent_exec.ContractError("receipt_recovery_binding_invalid", "Receipt recovery requires the failed latest Work child")
        failed = runtime.status(current["agentId"], current["runId"])
        error = state.get("controlPlaneError")
        if failed.get("status") != "failed" or not isinstance(error, dict) or failed.get("error") != error:
            raise agent_exec.ContractError("receipt_recovery_unsafe", "Child state is active, ambiguous, or not an allowlisted receipt failure")
        error_code = error.get("code")
        legacy_path_error = (
            error_code == "receipt_invalid"
            and error.get("message") in LEGACY_PATH_CONTRACT_ERRORS
            and failed.get("capabilityBindingHash") is None
        )
        recoverable = error_code in RECEIPT_RECOVERY_ERRORS or legacy_path_error
        if error_code in {"receipt_missing", "receipt_format_invalid"} and failed.get("capabilityBindingHash") is not None:
            recoverable = False
        if not recoverable:
            raise agent_exec.ContractError("receipt_recovery_unsafe", "Child receipt failure can contain unsafe test or capability evidence")
        session = agent_exec.safe_read_json(agent_exec.session_file(root, assigned_agent(state, "work")))
        if not isinstance(failed.get("sessionId"), str) or session.get("sessionId") != failed.get("sessionId"):
            raise agent_exec.ContractError("receipt_recovery_session_invalid", "Failed Work run is not bound to the current Work session")
        request = receipt_recovery_request(state, failed, error, path.parent)
        request_hash = hashlib.sha256(agent_exec.safe_read_bytes(request, agent_exec.MAX_REQUEST_BYTES)).hexdigest()
        state["receiptRecovery"] = {
            "failedWorkRunId": failed["runId"],
            "failure": error,
            "failedResultPath": failed["resultPath"],
            "failedReceiptPath": failed["receiptPath"],
            "requestPath": str(request),
            "requestHash": request_hash,
            "recoveryWorkRunId": None,
            "requestedAt": now(),
            "dispatchedAt": None,
        }
        state["updatedAt"] = now()
        agent_exec.atomic_write_json(path, state)
        # The accepted recovery intent is durable before any legacy policy publication.
        upgrade_execution_policy(state, path, args, root)
        dispatch(
            state, path, runtime, role="work", request_file=request,
            recovery_of_run_id=failed["runId"],
        )
        return public_state(state, state["currentChild"])


def finish_workflow_task(state, path, runtime, reason):
    workflow = state.get("workflow")
    if workflow:
        task = workflow["tasks"][workflow["index"]]
        task["workStatus"] = "completed"
        if reason == "pass":
            task["verificationStatus"] = "completed"
        if workflow["index"] + 1 < len(workflow["tasks"]):
            workflow["index"] += 1
            next_task = workflow["tasks"][workflow["index"]]
            import task_binding
            document = agent_exec.safe_read_json(Path(state["execution"]["taskListPath"]))
            binding = task_binding.validate(document, next_task["id"], next_task["requestHash"])
            expected = task_binding.validate({"id": workflow["id"], "title": workflow["title"], "tasks": workflow["tasks"]}, next_task["id"], next_task["requestHash"])
            if binding != expected:
                raise agent_exec.ContractError("task_binding_invalid", "The submitted task snapshot changed")
            state["execution"]["taskBinding"] = binding
            state.update(originalRequestPath=next_task["requestPath"], originalRequestHash=next_task["requestHash"],
                         latestWorkRunId=None, latestVerificationRunId=None, lastVerificationDecision=None,
                         pendingFindingIds=[], currentChild=None, humanSkip=None, receiptRecovery=None,
                         status="active", terminalReason=None)
            dispatch(state, path, runtime, role="work", request_file=Path(next_task["requestPath"]))
            return public_state(state, state["currentChild"])
    state.update(status="completed", phase="ended", currentChild=None,
                 terminalReason={"code": reason, "message": "All submitted tasks completed"}, updatedAt=now())
    agent_exec.atomic_write_json(path, state)
    return public_state(state)


def reconcile_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] in {"completed", "cancelled"}:
            return public_state(state)
        upgrade_execution_policy(state, path, args, root)
        runtime = AgentRuntime(root)
        if isinstance(state.get("pendingDispatch"), dict):
            child = complete_pending_dispatch(state, path, runtime)
            return public_state(state, child)
        current = state.get("currentChild")
        if not isinstance(current, dict):
            raise agent_exec.ContractError("loop_state_invalid", "active loop has no child")
        child = runtime.status(current["agentId"], current["runId"])
        if child["status"] not in CHILD_TERMINAL:
            return public_state(state, child)
        if child["status"] != "completed":
            if state.get("workflow"):
                state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus" if current["role"] == "work" else "verificationStatus"] = "blocked" if child["status"] == "needs-human-decision" else child["status"]
            state.update({
                "status": "runtime-error",
                "phase": "control-plane-error",
                "controlPlaneError": child.get("error") or {
                    "code": child["status"],
                    "message": "managed child did not complete",
                },
                "updatedAt": now(),
            })
            agent_exec.atomic_write_json(path, state)
            return public_state(state, child)
        directory = path.parent
        if current["role"] == "work":
            receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
            pending_findings = set(state.get("pendingFindingIds", []))
            if not pending_findings.issubset(set(receipt["addressedFindingIds"])):
                raise agent_exec.ContractError("finding_binding_invalid", "Work receipt omitted failed Verification findings")
            if state.get("execution", {}).get("taskMode") in ("work", "plan-work"):
                return finish_workflow_task(state, path, runtime, "work-completed")
            if isinstance(state.get("humanSkip"), dict):
                if state.get("workflow"):
                    workflow = state["workflow"]
                    workflow["tasks"][workflow["index"]]["workStatus"] = "completed"
                    workflow["tasks"][workflow["index"]]["verificationStatus"] = "cancelled"
                    for remaining in workflow["tasks"][workflow["index"] + 1:]:
                        remaining.update(workStatus="cancelled", verificationStatus="cancelled")
                state.update({"status": "completed", "phase": "ended", "currentChild": None, "terminalReason": {"code": "human-skip", "message": "Human skipped Verification"}, "updatedAt": now()})
                agent_exec.atomic_write_json(path, state)
                return public_state(state)
            if state.get("workflow"):
                state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus"] = "completed"
            request = verification_request(state, child, directory)
            state["pendingFindingIds"] = []
            dispatch(state, path, runtime, role="verification", request_file=request, verified_work_run_id=child["runId"])
            return public_state(state, state["currentChild"])
        if current["role"] != "verification":
            raise agent_exec.ContractError("loop_state_invalid", "child role is outside the graph")
        receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
        if receipt["decision"] == "pass":
            state["lastVerificationDecision"] = "pass"
            return finish_workflow_task(state, path, runtime, "pass")
        if state.get("workflow"):
            state["workflow"]["tasks"][state["workflow"]["index"]]["verificationStatus"] = "pending"
        state["lastVerificationDecision"] = "fail"
        state["pendingFindingIds"] = [finding["id"] for finding in receipt["findings"]]
        request = revision_request(state, child, receipt, directory)
        dispatch(state, path, runtime, role="work", request_file=request)
        return public_state(state, state["currentChild"])


def status_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    _path, state = read_state(root, args.work_agent, args.loop_id)
    child = None
    if isinstance(state.get("currentChild"), dict) and state["status"] not in {"completed", "cancelled"}:
        current = state["currentChild"]
        child = AgentRuntime(root).status(current["agentId"], current["runId"])
    return public_state(state, child)


def skip_loop(args: argparse.Namespace) -> dict[str, Any]:
    if args.actor != "human":
        raise agent_exec.ContractError("human_skip_unauthorized", "Verification skip requires actor human")
    if not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("human_skip_evidence_missing", "Verification skip requires authorization reference and decision evidence")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state.get("execution", {}).get("taskMode") in ("work", "plan-work"):
            raise agent_exec.ContractError("verification_not_requested", "This mode has no separate Verification to skip")
        if state["status"] in {"completed", "cancelled"}:
            return public_state(state)
        current = state.get("currentChild")
        if not isinstance(current, dict) or current.get("role") != "work":
            raise agent_exec.ContractError("verification_already_started", "Human skip is available only before Verification starts")
        state.update({
            "status": "active",
            "humanSkip": {
                "actor": "human",
                "authorizationReference": args.authorization_reference.strip(),
                "decisionEvidence": args.decision_evidence.strip(),
                "recordedAt": now(),
            },
            "updatedAt": now(),
        })
        agent_exec.atomic_write_json(path, state)
        return public_state(state, current)


def close_loop(args):
    """Close a stopped failed workflow without rewriting its execution evidence."""
    if args.actor != "human" or not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("loop_close_unauthorized", "Closing requires Human authorization and evidence")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] == "cancelled":
            return public_state(state)
        if state["status"] != "runtime-error" or state.get("pendingDispatch"):
            raise agent_exec.ContractError("loop_close_not_stopped", "Only failed workflows without uncertain dispatches can be closed")
        current = state.get("currentChild")
        if current:
            child = AgentRuntime(root).status(current["agentId"], current["runId"])
            if child["status"] not in CHILD_TERMINAL:
                raise agent_exec.ContractError("loop_close_child_active", "The current child must stop before closing the workflow")
        workflow = state.get("workflow")
        if workflow:
            for task in workflow["tasks"][workflow["index"]:]:
                for key in ("workStatus", "verificationStatus"):
                    if task.get(key) not in {None, "completed", "failed", "cancelled"}:
                        task[key] = "cancelled"
        state.update(status="cancelled", phase="ended", updatedAt=now(), terminalReason={
            "code": "human-closed", "message": "Human closed the failed workflow",
            "actor": args.actor, "authorizationReference": args.authorization_reference.strip(),
            "decisionEvidence": args.decision_evidence.strip(), "recordedAt": now(),
        })
        agent_exec.atomic_write_json(path, state)
        return public_state(state)


def drive_loop(args):
    """Run the durable graph independently of Main and the chat panel."""
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".driver.lock"):
        while True:
            state = agent_exec.safe_read_json(path)
            if state["status"] != "active":
                return public_state(state)
            try:
                result = reconcile_loop(args)
            except (agent_exec.ContractError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
                # Preserve the exact recovery point. Never retry an uncertain dispatch.
                with agent_exec.file_lock(path.parent / ".loop.lock"):
                    state = agent_exec.safe_read_json(path)
                    if state["status"] == "cancelled":
                        return public_state(state)
                    state.update(status="runtime-error", controlPlaneError={"code": getattr(error, "code", "driver_error"), "message": str(error)})
                    if state.get("workflow"):
                        task = state["workflow"]["tasks"][state["workflow"]["index"]]
                        role = (state.get("currentChild") or {}).get("role", "work")
                        task["verificationStatus" if role == "verification" else "workStatus"] = "blocked"
                    agent_exec.atomic_write_json(path, state)
                return public_state(state)
            if result["status"] != "active":
                return result
            time.sleep(2)


def launch_driver(args, result):
    arguments = [sys.executable, str(Path(__file__).resolve()), "drive", "--project-root", str(args.project_root),
                 "--work-agent", args.work_agent, "--loop-id", result["loopId"]]
    for name in ("runtime_home", "project_id"):
        value = getattr(args, name, None)
        if value:
            arguments.extend(["--" + name.replace("_", "-"), str(value)])
    with open(Path(result["statePath"]).parent / "driver.log", "ab") as log:
        subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


def build_parser() -> agent_exec.JsonArgumentParser:
    parser = agent_exec.JsonArgumentParser(prog="loop.py")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    agent_exec.add_project_argument(start)
    start.add_argument("--task-list-file", type=Path, required=True)
    start.add_argument("--task-id", required=True)
    start.add_argument("--request-file", type=Path, required=True)
    start.add_argument("--work-agent", required=True)
    start.add_argument("--task-mode", choices=("work", "plan-work", "work-verification", "plan-work-verification"), default="work-verification")
    start.add_argument("--verification-agent")
    start.add_argument("--codex", default="codex")
    agent_exec.execution_policy.add_policy_arguments(start)
    start.add_argument("--model")
    for role in ("work", "verification"):
        start.add_argument("--" + role + "-model")
        start.add_argument("--" + role + "-reasoning-effort", choices=("none", "low", "medium", "high", "xhigh", "max"))
        start.add_argument("--" + role + "-execution-mode", choices=("cli-default", "workspace-write", "danger-full-access", "bypass"))
    start.add_argument("--work-capability-binding-file", type=Path)
    start.add_argument("--verification-capability-binding-file", type=Path)
    for name in ("status", "reconcile", "recover-receipt", "skip", "drive", "close"):
        command = commands.add_parser(name)
        agent_exec.add_project_argument(command)
        if name in {"reconcile", "recover-receipt", "drive"}:
            agent_exec.execution_policy.add_policy_arguments(command)
        command.add_argument("--work-agent", required=True)
        command.add_argument("--loop-id", required=True)
        if name in {"skip", "close"}:
            command.add_argument("--actor", choices=agent_exec.ACTORS, required=True)
            command.add_argument("--authorization-reference", required=True)
            command.add_argument("--decision-evidence", required=True)
    return parser


def emit(value: dict[str, Any]) -> None:
    agent_exec.emit(value)


def main(argv: Sequence[str] | None = None) -> int:
    operation_token = agent_exec.response_operation.set(None)
    try:
        args = build_parser().parse_args(argv)
        agent_exec.response_operation.set({"schemaVersion": 1, "provider": "agent-factory", "script": "loop.py", "action": args.command})
        agent_exec.require_managed_platform()
        agent_exec.runtime_paths.resolve(args.project_root, home=args.runtime_home, project_id=args.project_id)
        handlers = {"start": start_loop, "status": status_loop, "reconcile": reconcile_loop, "recover-receipt": recover_receipt, "skip": skip_loop, "drive": drive_loop, "close": close_loop}
        result = handlers[args.command](args)
        if args.command == "start" and result.get("status") == "active":
            try:
                launch_driver(args, result)
            except OSError as error:
                # Acceptance already happened: retain its identity and stop explicitly.
                path = Path(result["statePath"])
                with agent_exec.file_lock(path.parent / ".loop.lock"):
                    state = agent_exec.safe_read_json(path)
                    if state["status"] != "cancelled":
                        state.update(status="runtime-error", controlPlaneError={"code": "driver_launch_failed", "message": str(error)})
                        agent_exec.atomic_write_json(path, state)
                    result = public_state(state, state.get("currentChild"))
        emit(result)
        return 0
    except agent_exec.ContractError as error:
        emit(agent_exec.error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        emit(agent_exec.error_document("runtime_failure", str(error)))
        return 1
    finally:
        agent_exec.response_operation.reset(operation_token)


if __name__ == "__main__":
    raise SystemExit(main())
