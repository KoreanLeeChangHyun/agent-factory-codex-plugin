#!/usr/bin/env python3
"""Orchestrate the Agent Factory Work/Verification loop."""

from __future__ import annotations

import argparse
import contextlib
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
from tasks import progress as loop_progress
from tasks.modes import WORK_PROFILES


SCHEMA_VERSION = "0.1.0"
CHILD_TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled"}
RECEIPT_RECOVERY_ERRORS = {
    "receipt_missing", "receipt_format_invalid", "receipt_path_contract_invalid",
}
LEGACY_PATH_CONTRACT_ERRORS = {
    "changedPaths must be bounded relative paths",
    "changedPaths must contain only project-root-relative paths",
}
# A failed Verification returns to Work at most this many times per task before a Human decides.
DEFAULT_MAX_REVISIONS = 3
# Reading a run's status has no side effect, so a transient failure is retried; a dispatch never is.
STATUS_READ_ATTEMPTS = 3
STATUS_READ_BACKOFF_SECONDS = 0.5
TRANSIENT_READ_ERRORS = {"child_runtime_failure", "runtime_failure"}
# How often the driver asks exec to reconcile a child whose worker may have died.
STALE_CHECK_SECONDS = 30.0
# One bounded wait budget per task, retained across driver restarts/reconcile.
INTEGRATION_WAIT_ATTEMPTS = 150
INTEGRATION_WAIT_ERRORS = {"task_target_busy", "task_workspace_busy", "lock_busy"}
# Human-invoked commands that return a stopped loop to `active`.
RESUMING_COMMANDS = {"recover-receipt", "extend-revisions", "answer", "steer", "retry-preparation"}
# Commands after which an active loop must have a driver; one is launched only when none holds the driver lock.
DRIVER_ENSURING_COMMANDS = RESUMING_COMMANDS | {"reconcile", "skip"}
# Private systemd EnvironmentFile kept beside the loop so Restart=on-failure can reread it.
DRIVER_ENVIRONMENT_FILE = "driver.env"
# What a stopped loop means for its caller. `contract`: the Agent's output broke its contract; a
# repair turn or a stronger profile can fix it. `transient`: the control plane failed; inspect and
# reconcile, the work itself is not at fault. `provider`: the model backend failed. `environment`:
# the host or policy must change first; another attempt fails the same way. `human`: a Human decides.
FAILURE_CLASSES = {
    "contract": {
        "receipt_missing", "receipt_format_invalid", "receipt_path_contract_invalid", "receipt_invalid",
        "receipt_binding_invalid", "receipt_tests_invalid", "receipt_decision_invalid",
        "receipt_capability_invalid", "finding_binding_invalid", "result_invalid", "result_missing",
        "result_file_missing", "result_file_invalid",
    },
    "transient": {
        "child_runtime_failure", "runtime_failure", "driver_error", "driver_launch_failed",
        "heartbeat_timeout", "event_read_failed", "codex_exit_timeout", "worker_failure",
        "started_run_not_replayable", "run_start_unknown",
        "task_target_busy", "task_workspace_busy", "lock_busy", "task_target_changed",
    },
    "provider": {
        "native_backend_error", "codex_failed", "event_invalid", "turn_timeout", "start_timeout",
        "start_ack_missing", "session_invalid", "session_mismatch",
    },
    "environment": {
        "sandbox_unavailable", "execution_preflight_failed", "execution_policy_mismatch",
        "provider_not_found", "codex_start_failed", "worktree_binding_changed",
        "task_repository_invalid", "task_repository_overlap", "parent_session_invalid",
        "parent_conversation_reset", "task_workspace_binding", "task_workspace_missing",
        "task_target_busy_timeout", "task_workspace_busy_timeout", "lock_busy_timeout",
        "task_preparation_failed", "task_guidance_missing", "task_guidance_unsafe", "task_check_input_changed",
    },
    "human": {"needs-human-decision", "revision_limit_reached", "cancelled"},
}


# Integration refusals that keep Work Units unmerged. Under the Human's Work isolation toggle they end the
# task with the preserved branches reported instead of waiting for a Human; busy targets stay transient.
PRESERVED_INTEGRATION_ERRORS = {
    "task_target_dirty", "task_integration_check_failed", "task_check_modified_sources", "task_merge_failed",
    "task_target_changed", "task_changes_outside_receipt", "task_target_checkout_exists",
}


# Codes the runtime no longer raises; loops stopped by them before keep their class.
RETIRED_FAILURE_CODES = {"lesson_recording_incomplete": "contract"}


def failure_class(error: Any) -> str | None:
    """Classify a recorded stop so callers pick repair, re-inspection, escalation or a Human."""
    if not isinstance(error, dict) or not isinstance(error.get("code"), str):
        return None
    return next((name for name, codes in FAILURE_CLASSES.items() if error["code"] in codes),
                RETIRED_FAILURE_CODES.get(error["code"], "unknown"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def publish_progress(path, state):
    try:
        return {"status": "current", **loop_progress.publish(path, state, agent_exec.atomic_write)}
    except (OSError, ValueError, TypeError, KeyError, agent_exec.ContractError) as error:
        # A display failure must never undo a committed dispatch or block execution.
        print(f"Progress projection failed for {state.get('loopId')}: {error}", file=sys.stderr)
        return {"status": "stale", "error": str(error), "stateRevision": state.get("stateRevision", 0)}


def save_loop_state(path, state):
    state["stateRevision"] = state.get("stateRevision", 0) + 1
    agent_exec.atomic_write_json(path, state)
    publish_progress(path, state)


def refresh_progress(args):
    root = agent_exec.resolve_project_root(args.project_root)
    path = state_path(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        return {"loopId": state["loopId"], "projection": publish_progress(path, state)}


def role_model_options(execution: dict[str, Any], role: str, operation: str) -> dict[str, Any]:
    """Bind role overrides on every turn; retain the legacy shared submit model."""
    profile = execution.get("agentModels", {}).get(role, {})
    options = dict(profile)
    if operation == "submit" and not options.get("model") and execution.get("model"):
        options["model"] = execution["model"]
    return options


class AgentRuntime:
    """Call only the public managed-session interface."""

    def __init__(self, project_root: Path, parent_state_path: str | None = None) -> None:
        self.project_root = project_root
        self.runtime_binding = agent_exec.runtime_paths.resolve(project_root, create=True)
        self.script = Path(agent_exec.__file__).resolve()
        self.parent_state_path = parent_state_path

    def call(self, arguments: list[str], *, idempotent: bool = False) -> dict[str, Any]:
        """Run one exec command. Only side-effect-free reads retry a transient failure."""
        attempts = STATUS_READ_ATTEMPTS if idempotent else 1
        for attempt in range(1, attempts + 1):
            try:
                return self._call(arguments)
            except agent_exec.ContractError as error:
                if error.code not in TRANSIENT_READ_ERRORS or attempt == attempts:
                    raise
            except (subprocess.TimeoutExpired, OSError):
                if attempt == attempts:
                    raise
            time.sleep(STATUS_READ_BACKOFF_SECONDS * 2 ** (attempt - 1))
        raise agent_exec.ContractError("child_runtime_failure", "Agent runtime returned no response")

    def _call(self, arguments: list[str]) -> dict[str, Any]:
        environment = os.environ.copy()
        # The driver outlives its caller. Keep the announcement and child runs
        # bound to the Main run that accepted the immutable task list.
        if self.parent_state_path:
            environment[agent_exec.execution_policy.PARENT_STATE_ENV] = self.parent_state_path
        else:
            environment.pop(agent_exec.execution_policy.PARENT_STATE_ENV, None)
        process = subprocess.run(
            [sys.executable, str(self.script), *arguments, "--project-root", str(self.project_root), *agent_exec.runtime_paths.arguments(self.project_root)],
            cwd=self.project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
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
            from tasks import binding as task_binding
            current_binding = task_binding.load(agent_exec.safe_read_json, Path(execution["taskListPath"]), execution["taskBinding"]["taskId"], request_hash)
            if current_binding != execution["taskBinding"]:
                raise agent_exec.ContractError("task_binding_invalid", "The loop task snapshot changed before dispatch")
            arguments.extend(["--task-list-file", execution["taskListPath"], "--task-id", execution["taskBinding"]["taskId"]])
        if execution.get("executionPolicyPath"):
            if agent_exec.safe_read_json(Path(execution["executionPolicyPath"])) != execution["executionPolicy"]:
                raise agent_exec.ContractError("execution_policy_mismatch", "Loop execution policy snapshot changed")
            arguments.extend(["--execution-policy-file", execution["executionPolicyPath"]])
        if execution.get("taskWorkspacePath"):
            arguments.extend(["--task-workspace-file", execution["taskWorkspacePath"]])
        if operation == "submit":
            arguments.extend([
                "--role", role,
                "--codex", str(execution["codex"]),
            ])
        for key, value in role_model_options(execution, role, operation).items():
            if key == "model":
                arguments.extend(["--model", str(value)])
            elif key == "reasoningEffort":
                arguments.extend(["--reasoning-effort", str(value)])
            elif key == "fast":
                arguments.append("--fast" if value else "--no-fast")
        if role == "work" and execution.get("taskMode"):
            arguments.extend(["--task-mode", execution["taskMode"]])
        if role == "work" and execution.get("workProfile"):
            arguments.extend(["--work-profile", execution["workProfile"]])
        if role == "work":
            # A loop finishes under the response contract it captured at start; loops persisted
            # before the field keep the file contract (1) for every later Work run.
            arguments.extend(["--response-contract",
                              str(execution.get("responseContract", agent_exec.receipt_contracts.FILE_RESPONSE_CONTRACT))])
        if verified_work_run_id is not None:
            arguments.extend(["--verified-work-run-id", verified_work_run_id])
        if capability_binding_file is not None:
            arguments.extend(["--capability-binding-file", str(capability_binding_file)])
        return self.call(arguments)

    def status(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--run-id", run_id], idempotent=True)["run"]

    def status_dispatch(self, agent_id: str, dispatch_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--dispatch-id", dispatch_id], idempotent=True)["run"]

    def reconcile_stale(self, agent_id: str) -> list[dict[str, Any]]:
        """Let exec settle this Agent's runs whose worker heartbeat expired; live runs are untouched."""
        return self.call(["reconcile", "--agent", agent_id]).get("runs", [])


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
    save_loop_state(path, state)


def observed_task_status(child):
    status = child.get("status")
    if status == "needs-human-decision":
        return "blocked"
    if status in {"failed", "cancelled"}:
        return status
    # Completion still requires the selected route's receipt processing.
    return "running"


def revision_pause(state: dict[str, Any]) -> dict[str, Any] | None:
    """A stop on the revision limit as data a host can render and a Human decides on."""
    error = state.get("controlPlaneError")
    if (state.get("status") != "needs-human-decision" or not isinstance(error, dict)
            or error.get("code") != "revision_limit_reached"):
        return None
    return {
        "code": "revision_limit_reached",
        "revisionCount": state.get("revisionCount", 0),
        "maxRevisions": state.get("execution", {}).get("maxRevisions"),
        "pendingFindingIds": list(state.get("pendingFindingIds", [])),
        # Summaries exist only for loops stopped by a runtime that records them.
        "findings": copy.deepcopy(state.get("revisionLimitFindings") or []),
    }


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
        "taskWorkspaces": copy.deepcopy(state.get("taskWorkspaces", {})),
        "loopId": state["loopId"],
        "workflow": workflow,
        "contract": copy.deepcopy(state.get("contract")),
        "createdAt": state.get("createdAt"),
        "updatedAt": state.get("updatedAt"),
        "stateRevision": state.get("stateRevision", 0),
        "progressPath": str(Path(state["statePath"]).parent / "progress.md"),
        "progressProjection": loop_progress.health(Path(state["statePath"]), state),
        "taskMode": state.get("execution", {}).get("taskMode", "work-verification"),
        # Present only when Main recorded its choice at start; older loops keep their shape.
        **({"workProfile": state["execution"]["workProfile"]} if state.get("execution", {}).get("workProfile") else {}),
        # A completed Scribe's uncommitted draft and the Human's review decision.
        **({"draftReview": copy.deepcopy(state["draftReview"])} if state.get("draftReview") else {}),
        "status": state["status"],
        "phase": state["phase"],
        "workAgentId": state["workAgentId"],
        "verificationAgentId": state["verificationAgentId"],
        "latestWorkRunId": state.get("latestWorkRunId"),
        "latestVerificationRunId": state.get("latestVerificationRunId"),
        "humanSkip": state.get("humanSkip"),
        "pendingDispatch": state.get("pendingDispatch"),
        "controlPlaneError": state.get("controlPlaneError"),
        "integrationWait": copy.deepcopy(state.get("integrationWait")),
        "pendingDecision": copy.deepcopy(state.get("decisions", {}).get(state.get("pendingDecisionId"))),
        "recovery": copy.deepcopy(state.get("recovery")),
        "completion": copy.deepcopy(state.get("completion")),
        "preflight": copy.deepcopy(state.get("preflight")),
        "steering": copy.deepcopy(state.get("steering", [])),
        "failureClass": failure_class(state.get("controlPlaneError")),
        "receiptRecovery": state.get("receiptRecovery"),
        "revisionCount": state.get("revisionCount", 0),
        "maxRevisions": state.get("execution", {}).get("maxRevisions"),
        "pause": revision_pause(state),
        "currentChild": child,
        "stopPending": state.get("stopPending", False),
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
        and not state.get("integrationRevisionPending")
        and not state.get("decisionContinuationPending")
        and not state.get("steeringContinuationPending")
    ):
        raise agent_exec.ContractError("graph_transition_invalid", "a Work revision requires failed Verification")
    agent_id = assigned_agent(state, role)
    root = Path(state["projectRoot"])
    if role == "work":
        from tasks import workspaces
        workspaces.prepare(agent_exec, state, path, lambda: save_loop_state(path, state))
    operation = "send" if agent_exec.session_file(root, agent_id).exists() else "submit"
    if recovery_of_run_id is not None and operation != "send":
        raise agent_exec.ContractError("receipt_recovery_session_invalid", "Receipt recovery requires the existing Work session")
    content = agent_exec.safe_read_bytes(request_file, agent_exec.MAX_REQUEST_BYTES)
    queued = [item for item in state.get("steering", []) if item["status"] == "queued"
              and item["taskId"] == state["execution"]["taskBinding"]["taskId"]]
    if role == "work" and queued:
        request_file = write_request(path.parent, "steering-" + uuid.uuid4().hex + ".md",
            content.decode("utf-8") + "\n\n[Bound additions to this task; preserve captured authority]\n"
            + json.dumps(queued, ensure_ascii=False))
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
        "steeringIds": [item["id"] for item in queued] if role == "work" else [],
    }
    if recovery_of_run_id is not None:
        state["pendingDispatch"]["recoveryOfRunId"] = recovery_of_run_id
    state["phase"] = f"{role}-dispatching"
    state.pop("integrationRevisionPending", None)
    state.pop("steeringContinuationPending", None)
    if state.get("decisionContinuationPending"):
        state["pendingDispatch"]["decisionId"] = state.pop("decisionContinuationPending")
    state["updatedAt"] = now()
    save_loop_state(path, state)


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
        if state.get("lifecycleVersion"):
            from tasks import preparation
            if not preparation.ready(agent_exec, state, path, lambda: save_loop_state(path, state)):
                state["phase"] = "preparing"
                save_loop_state(path, state)
                return None
        pending["attemptedAt"] = now()
        save_loop_state(path, state)
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
        if state["execution"].get("taskWorkspacePath"):
            workspace = agent_exec.safe_read_json(Path(state["execution"]["taskWorkspacePath"]))
            expected_tuple["executionPolicy"] = agent_exec.worktrees.relocate_policy(expected_tuple["executionPolicy"], Path(state["projectRoot"]), Path(workspace["path"]))
            expected_tuple["taskWorkspaceId"] = workspace["id"]
    model_options = role_model_options(state["execution"], pending["role"], pending["operation"])
    if model_options:
        expected_tuple["executionOptions"] = model_options
    if pending["role"] == "work" and state["execution"].get("taskMode"):
        expected_tuple.setdefault("executionOptions", {})["taskMode"] = state["execution"]["taskMode"]
    if pending.get("capabilityBindingHash") is not None:
        expected_tuple["capabilityBindingHash"] = pending["capabilityBindingHash"]
    if pending["role"] == "work" and state["execution"].get("workProfile"):
        expected_tuple["workProfile"] = state["execution"]["workProfile"]
    if state["execution"].get("taskBinding"):
        expected_tuple["taskBinding"] = state["execution"]["taskBinding"]
    if pending.get("workGoal"):
        from tasks.modes import work_goal_options
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
    if isinstance(actual_tuple, dict) and "taskWorkspaceId" in expected_tuple and "taskWorkspaceId" not in actual_tuple:
        # Runs accepted before the tuple carried the workspace still recorded the
        # exec-validated binding itself; accept only that exact workspace.
        recorded = agent_exec.safe_read_json(
            agent_exec.state_file(Path(state["projectRoot"]), pending["agentId"], str(run["runId"]))).get("taskWorkspace")
        if isinstance(recorded, dict) and recorded.get("id") == expected_tuple["taskWorkspaceId"] and recorded.get("path") == workspace["path"]:
            actual_tuple = {**actual_tuple, "taskWorkspaceId": recorded["id"]}
    if run.get("dispatchId") != pending["dispatchId"] or actual_tuple != expected_tuple:
        raise agent_exec.ContractError("dispatch_binding_invalid", "managed run does not match durable dispatch intent")
    role = pending["role"]
    run_id = str(run["runId"])
    state["currentChild"] = {"role": role, "agentId": pending["agentId"], "runId": run_id}
    state["phase"] = f"{role}-running"
    if state.get("workflow"):
        task = state["workflow"]["tasks"][state["workflow"]["index"]]
        if role == "verification":
            # The Work receipt was validated before this dispatch intent. A
            # recovered control-plane failure may have projected it as blocked.
            task["workStatus"] = "completed"
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
    if pending.get("decisionId"):
        decision = state["decisions"][pending["decisionId"]]
        decision.update(status="resumed", continuationRunId=run_id, dispatchId=pending["dispatchId"])
        state["pendingDecisionId"] = None
    for item in state.get("steering", []):
        if item["id"] in pending.get("steeringIds", []):
            item.update(status="delivered", continuationRunId=run_id, dispatchId=pending["dispatchId"])
    save_loop_state(path, state)
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


def work_isolation(args: argparse.Namespace) -> bool:
    """The Human's Work isolation toggle captured on the managed parent; a direct CLI start may pass the flag."""
    requested = getattr(args, "work_isolation", None)
    locator = os.environ.get(agent_exec.execution_policy.PARENT_STATE_ENV)
    captured = agent_exec.safe_read_json(Path(locator)).get("executionOptions", {}).get("workIsolation") if locator else None
    if captured is not None and requested is not None and requested != captured:
        raise agent_exec.ContractError("work_isolation_mismatch", "Work isolation differs from the captured Human selection")
    return (captured if captured is not None else requested) is True


def start_loop(args: argparse.Namespace) -> dict[str, Any]:
    args.work_isolation_enabled = work_isolation(args)
    document = agent_exec.safe_read_json(args.task_list_file) if getattr(args, "task_list_file", None) else None
    declared = agent_exec.safe_read_json(args.workspace_file) if getattr(args, "workspace_file", None) else next((task.get("workspace") for task in (document or {}).get("tasks", []) if task.get("id") == getattr(args, "task_id", None)), None)
    if declared is None:
        if args.work_isolation_enabled:
            raise agent_exec.ContractError("task_workspace_required", "Work isolation is on; supply --workspace-file with a code or read-only plan")
        return start_loop_captured(args)
    root = agent_exec.resolve_project_root(args.project_root)
    agent_exec.runtime_paths.resolve(root, create=True)
    agent_exec.validate_id(args.work_agent, agent_exec.AGENT_ID, "work_agent")
    from tasks import workspaces
    selected = None
    parent = agent_exec.managed_parent_identity(root)
    if parent:
        selected = agent_exec.load_session(root, parent["agentId"]).get("worktree")
    captured = workspaces.plan(root, declared, selected, args.work_isolation_enabled)
    args.captured_workspace_plan = captured
    if captured["mode"] != "code":
        return start_loop_captured(args)
    agent = agent_exec.agent_directory(root, args.work_agent, create=True)
    with agent_exec.file_lock(agent / ".task-workspace-start.lock"):
        request_hash = hashlib.sha256(agent_exec.safe_read_bytes(args.request_file, agent_exec.MAX_REQUEST_BYTES)).hexdigest()
        acceptance = {"requestHash": request_hash, "workspace": captured,
                      "taskDocument": document, "options": {key: value for key, value in vars(args).items() if key in (
                          "task_id", "task_mode", "work_agent", "verification_agent", "work_model", "verification_model",
                          "work_reasoning_effort", "verification_reasoning_effort", "work_fast", "verification_fast",
                          "work_execution_mode", "verification_execution_mode", "work_profile", "max_revisions", "receipt_recovery")},
                      **({"workIsolation": True} if args.work_isolation_enabled else {})}
        args.workspace_acceptance_key = hashlib.sha256(json.dumps(acceptance, sort_keys=True).encode()).hexdigest()
        for previous_path in sorted((agent / "loops").glob("*/state.json")):
            previous = agent_exec.safe_read_json(previous_path)
            if previous.get("acceptedRequestHash", previous.get("originalRequestHash")) != request_hash or not previous.get("execution", {}).get("workspacePlan"):
                continue
            if (previous.get("workspaceAcceptanceKey") != args.workspace_acceptance_key or previous["execution"]["taskMode"] != args.task_mode or
                    previous.get("verificationAgentId") != args.verification_agent):
                raise agent_exec.ContractError("task_workspace_acceptance_collision", "This task was already accepted with different workspace or route bindings")
            # A retried start returns the accepted loop; it must not launch a second driver for it.
            args.accepted_existing_loop = True
            return public_state(previous)
        return start_loop_captured(args)


def start_loop_captured(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    agent_exec.validate_id(args.work_agent, agent_exec.AGENT_ID, "work_agent")
    mode = getattr(args, "task_mode", "work-verification")
    if mode not in ("work", "plan-work") and not args.verification_agent:
        raise agent_exec.ContractError("verification_agent_required", "This route requires Verification")
    if args.verification_agent:
        agent_exec.validate_id(args.verification_agent, agent_exec.AGENT_ID, "verification_agent")
    if args.work_agent == args.verification_agent:
        raise agent_exec.ContractError("agent_identity_conflict", "Work and Verification require different Agent sessions")
    max_revisions = getattr(args, "max_revisions", DEFAULT_MAX_REVISIONS)
    if type(max_revisions) is not int or max_revisions < 0:
        raise agent_exec.ContractError("revision_limit_invalid", "--max-revisions must be 0 (unlimited) or a positive integer")
    work_profile = getattr(args, "work_profile", None)
    if work_profile is not None and work_profile not in WORK_PROFILES:
        raise agent_exec.ContractError("work_profile_invalid", "--work-profile must be " + ", ".join(WORK_PROFILES))
    request = agent_exec.safe_read_bytes(args.request_file, agent_exec.MAX_REQUEST_BYTES)
    if not request.decode("utf-8").strip():
        raise agent_exec.ContractError("request_invalid", "request must not be empty")
    from tasks import binding as task_binding
    if (getattr(args, "task_list_file", None) is None) != (not getattr(args, "task_id", None)):
        raise agent_exec.ContractError("task_binding_required", "--task-list-file and --task-id are supplied together")
    parent = agent_exec.managed_parent_identity(root)
    if getattr(args, "task_list_file", None) is None:
        # Orchestrator dispatch: one brief, one task. The runtime derives the list so Main
        # writes no task-list JSON or announcement; the panel still shows this single task.
        submitted_document = task_binding.brief_document(request.decode("utf-8"))
        args.task_id = submitted_document["tasks"][0]["id"]
        if parent is not None:
            with agent_exec.file_lock(agent_exec.agent_directory(root, parent["agentId"]) / ".dispatch.lock"):
                agent_exec.require_current_parent_conversation(root, parent)
    else:
        # Read once, normalize a private snapshot, and hash exactly the bytes we retain.
        submitted_document = agent_exec.safe_read_json(args.task_list_file)
        if parent is not None:
            from tasks import announcement as task_announcement
            with agent_exec.file_lock(agent_exec.agent_directory(root, parent["agentId"]) / ".dispatch.lock"):
                agent_exec.require_current_parent_conversation(root, parent)
                task_announcement.check_submission(agent_exec.safe_read_json,
                    agent_exec.state_file(root, parent["agentId"], parent["runId"]), parent, submitted_document)
    task_document, binding = task_binding.resolve(
        submitted_document, args.task_id, hashlib.sha256(request).hexdigest())
    from tasks import workspaces
    workspace_plan = getattr(args, "captured_workspace_plan", None)
    tasks = task_document["tasks"]
    selected_unit = agent_exec.load_session(root, parent["agentId"]).get("worktree") if parent else None
    isolation = getattr(args, "work_isolation_enabled", False)
    workspace_plans = {task["id"]: workspaces.plan(root, task["workspace"], selected_unit, isolation) for task in tasks if "workspace" in task}
    workspace_plan = workspace_plans.get(args.task_id, workspace_plan)
    if isolation and any(task["id"] not in workspace_plans for task in tasks) and not getattr(args, "captured_workspace_plan", None):
        raise agent_exec.ContractError("task_workspace_required", "Work isolation is on; every task requires a code or read-only workspace plan")
    if work_profile == "scribe" and any(plan.get("mode") == "code" for plan in (*workspace_plans.values(), workspace_plan or {})):
        # A code Work Unit is committed and merged automatically; a Scribe draft must wait for the Human's review.
        raise agent_exec.ContractError("scribe_draft_review_required",
                                       "Scribe drafts stay uncommitted in the shared checkout for Human review; use the read-only workspace plan")
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
    for index, (task, content) in enumerate(zip(tasks, task_requests, strict=False)):
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
        "lifecycleVersion": 1,
        "loopId": loop_id,
        "status": "active",
        "phase": "starting",
        "projectRoot": str(root),
        "statePath": str(path),
        "originalRequestPath": str(original),
        "originalRequestHash": hashlib.sha256(request).hexdigest(),
        "acceptedRequestHash": hashlib.sha256(request).hexdigest(),
        **({"workspaceAcceptanceKey": args.workspace_acceptance_key} if getattr(args, "workspace_acceptance_key", None) else {}),
        "capabilityBindings": capability_bindings,
        "workAgentId": args.work_agent,
        "verificationAgentId": args.verification_agent,
        "latestWorkRunId": None,
        "latestVerificationRunId": None,
        "lastVerificationDecision": None,
        "pendingFindingIds": [],
        "revisionCount": 0,
        "currentChild": None,
        "humanSkip": None,
        "pendingDispatch": None,
        "controlPlaneError": None,
        "receiptRecovery": None,
        "terminalReason": None,
        "contract": copy.deepcopy(task_document.get("contract")),
        "workflow": {"id": task_document["id"], "title": task_document["title"], "index": 0, "tasks": workflow_tasks},
        "parentStatePath": os.environ.get(agent_exec.execution_policy.PARENT_STATE_ENV),
        "execution": {"taskListPath": str(task_list_path), "taskBinding": binding, "taskMode": mode, "codex": args.codex, "model": args.model,
                      "contextWorkingDirectory": agent_exec.safe_read_json(agent_exec.state_file(root, parent["agentId"], parent["runId"])).get("workingDirectory", str(root)) if parent else str(root),
                      **({"workspacePlan": workspace_plan} if workspace_plan else {}),
                      **({"defaultWorkspacePlan": getattr(args, "captured_workspace_plan", None)} if getattr(args, "workspace_file", None) else {}),
                      **({"workspacePlans": workspace_plans} if workspace_plans else {}),
                      # Present only when the Human turned Work isolation on; integration then never waits for a Human.
                      **({"workIsolation": True} if isolation else {}),
                      "agentModels": {role: {key: value for key, value in {"model": getattr(args, role + "_model", None), "reasoningEffort": getattr(args, role + "_reasoning_effort", None), "fast": getattr(args, role + "_fast", None)}.items() if value is not None} for role in ("work", "verification")},
                      "executionPolicy": policy, "executionPolicyPath": str(policy_path), "agentPermissions": role_permissions,
                      # Loops persisted before these fields keep the unbounded, explicit-recovery graph.
                      "maxRevisions": max_revisions, "receiptRecovery": getattr(args, "receipt_recovery", "auto"),
                      # Captured once; every Work run of this loop is dispatched under it.
                      "responseContract": agent_exec.receipt_contracts.RESPONSE_CONTRACTS[-1],
                      # Loops started without the flag keep no profile record.
                      **({"workProfile": work_profile} if work_profile else {})},
        "createdAt": created,
        "updatedAt": created,
    }
    save_loop_state(path, state)
    try:
        dispatch(state, path, AgentRuntime(root, state["parentStatePath"]), role="work", request_file=original)
    except (agent_exec.ContractError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        # No driver exists yet: stop explicitly so the loop never stays active without one.
        # A recorded dispatch intent stays for `reconcile`, which never retries it blindly.
        with agent_exec.file_lock(directory / ".loop.lock"):
            state = agent_exec.safe_read_json(path)
            if state["status"] == "active":
                state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus"] = "blocked"
                state.update(status="runtime-error", phase="control-plane-error", updatedAt=now(), controlPlaneError={
                    "code": getattr(error, "code", "driver_error"), "message": str(error)})
                save_loop_state(path, state)
        raise
    return public_state(state, state["currentChild"])


def verification_request(
    state: dict[str, Any], work: dict[str, Any], directory: Path,
    addressed_finding_ids: Sequence[str] = (),
) -> Path:
    revision_context = ""
    if addressed_finding_ids:
        # Context only: the verifier still judges the whole request. Stable ids let Work,
        # the Human and the revision limit tell an unresolved finding from a new one.
        revision_context = f"""
Revision context:
- This Work run revises the Work that failed your Verification run {state.get('latestVerificationRunId')}.
- Finding IDs Work reports as addressed: {json.dumps(list(addressed_finding_ids), ensure_ascii=False)}
- Check each of them first, then regressions the revision may have caused and the rest of the request.
- A finding that is still unresolved keeps its original id; use a new id only for a new defect.
"""
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
{revision_context}{recovery_evidence}
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
Preserved receipt (absent when none was published): {failed['receiptPath']}
Failure: {error['code']}: {error['message']}
Required addressed finding IDs: {finding_ids}

Do not repeat any already performed tool effect, external action, or project modification.
Do not modify the failed run or its artifacts. Use the preserved evidence to return a
fresh result and a corrected receipt for this recovery run, delivered the way this
run's instructions require. In `changedPaths`, report
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
        runtime = AgentRuntime(root, state.get("parentStatePath"))
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
        request = prepare_receipt_recovery(state, path, runtime, root)
        # The accepted recovery intent is durable before any legacy policy publication.
        upgrade_execution_policy(state, path, args, root)
        dispatch(
            state, path, runtime, role="work", request_file=request,
            recovery_of_run_id=state["receiptRecovery"]["failedWorkRunId"],
        )
        return public_state(state, state["currentChild"])


def prepare_receipt_recovery(
    state: dict[str, Any], path: Path, runtime: AgentRuntime, root: Path, *, automatic: bool = False,
) -> Path:
    """Validate a loop stopped on an allowlisted receipt failure and durably record the recovery intent."""
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
    if automatic:
        state["receiptRecovery"]["automatic"] = True
    state["updatedAt"] = now()
    save_loop_state(path, state)
    return request


def automatic_receipt_recovery(
    state: dict[str, Any], path: Path, runtime: AgentRuntime, root: Path,
) -> dict[str, Any] | None:
    """Give Work one repair turn for a deterministic receipt defect instead of stopping the loop.

    Uses the explicit recovery's allowlist and durable dispatch. A task gets one recovery,
    automatic or explicit; a second receipt failure, or any other failure, stays stopped.
    """
    if state.get("execution", {}).get("receiptRecovery") != "auto" or state.get("receiptRecovery") is not None:
        return None
    try:
        request = prepare_receipt_recovery(state, path, runtime, root, automatic=True)
    except agent_exec.ContractError:
        # Not an allowlisted, safely bound receipt failure: keep the recorded stop.
        return None
    dispatch(
        state, path, runtime, role="work", request_file=request,
        recovery_of_run_id=state["receiptRecovery"]["failedWorkRunId"],
    )
    return public_state(state, state["currentChild"])


def preserve_integration(state, path, code, message, files=None):
    """Work isolation: end the task without a Human wait, keeping every unmerged Work Unit branch and path."""
    value = state.get("taskWorkspaces", {}).get(state["execution"]["taskBinding"]["taskId"]) or {}
    preserved = [{"repositoryRoot": unit["repositoryRoot"], "targetBranch": unit["targetBranch"], "branch": unit["branch"],
                  "path": unit["path"], "phase": unit["phase"]} for unit in value.get("repositories", []) if unit["phase"] != "merged"]
    merged = [unit["repositoryRoot"] for unit in value.get("repositories", []) if unit["phase"] == "merged"]
    if value:
        value.update(preserved=True, preservedReason={"code": code, "message": message})
    workflow = state.get("workflow")
    if workflow:
        workflow["tasks"][workflow["index"]]["workStatus"] = "completed"
        # Later tasks may depend on the unmerged changes; they do not start.
        for remaining in workflow["tasks"][workflow["index"] + 1:]:
            remaining.update(workStatus="cancelled", verificationStatus="cancelled")
    summary = ("Work completed but was not merged (" + code + "): " + message + ". Preserved unmerged branches: "
               + "; ".join(item["branch"] + " at " + item["path"] + " (target " + item["targetBranch"] + " in " + item["repositoryRoot"] + ")" for item in preserved)
               + (". Already merged: " + ", ".join(merged) if merged else ""))
    if state.get("lifecycleVersion"):
        state["completion"] = {"work": "completed", "integration": "partial" if merged else "preserved",
                               "nextAction": "Resolve the recorded cause and reconcile the same loop"}
    state.update(status="runtime-error" if state.get("lifecycleVersion") else "completed", phase="ended", currentChild=None, controlPlaneError=None, updatedAt=now(),
                 terminalReason={"code": "integration_preserved", "message": summary, "cause": code,
                                 "preserved": preserved, "merged": merged, **({"files": files} if files else {})})
    save_loop_state(path, state)
    return public_state(state)


def finish_workflow_task(state, path, runtime, reason):
    if state.get("taskWorkspaces"):
        state["phase"] = "integrating"
        if state.get("lifecycleVersion"):
            state["completion"] = {"work": "completed", "integration": "checking"}
        save_loop_state(path, state)
        from tasks import workspaces
        root = Path(state["projectRoot"])
        isolation = state["execution"].get("workIsolation") is True
        work = runtime.status(assigned_agent(state, "work"), state["latestWorkRunId"])
        receipt = agent_exec.validate_receipt(root, work, agent_id=work["agentId"], run_id=work["runId"])
        if state.get("workflow") and work.get("status") == "completed":
            state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus"] = "completed"
        try:
            outcome = workspaces.integrate(agent_exec, state, work, receipt, lambda: save_loop_state(path, state))
        except agent_exec.ContractError as error:
            if state.get("lifecycleVersion") and error.code == "task_integration_check_failed":
                units = state["taskWorkspaces"][state["execution"]["taskBinding"]["taskId"]]["repositories"]
                failed = [unit.get(stage + "CheckOperation") for unit in units for stage in ("work", "integration")
                          if (unit.get(stage + "CheckOperation") or {}).get("status") == "failed"]
                evidence = hashlib.sha256(json.dumps(failed, sort_keys=True).encode()).hexdigest()
                if failed and evidence not in state.get("integrationFailureRepairs", []):
                    state.setdefault("integrationFailureRepairs", []).append(evidence)
                    state.update(integrationRevisionPending=True, status="active", controlPlaneError=None)
                    request = write_request(path.parent, "check-repair-" + evidence + ".md",
                        agent_exec.safe_read_bytes(Path(state["originalRequestPath"]), agent_exec.MAX_REQUEST_BYTES).decode("utf-8")
                        + "\n\nRuntime integration checks failed. Repair these failures within the original scope, "
                        "rerun affected checks, and submit a new result. Preserve prior evidence.\n"
                        + json.dumps(failed, ensure_ascii=False))
                    dispatch(state, path, runtime, role="work", request_file=request)
                    return public_state(state, state["currentChild"])
            if error.code in INTEGRATION_WAIT_ERRORS:
                owners = getattr(error, "owners", [])
                verified_wait = bool(owners) and all(owner["evidence"] == "live" for owner in owners)
                attempts = state.get("integrationWaitAttempts", 0) + (0 if verified_wait else 1)
                state["integrationWaitAttempts"] = attempts
                state["integrationWait"] = {"code": error.code, "message": error.message,
                                            "attempts": attempts, "limit": INTEGRATION_WAIT_ATTEMPTS,
                                            "verifiedLive": verified_wait, "owners": owners}
                if attempts >= INTEGRATION_WAIT_ATTEMPTS and not state.get("lifecycleVersion"):
                    if isolation:
                        return preserve_integration(state, path, error.code + "_timeout", error.message)
                    state.update(status="runtime-error", controlPlaneError={"code": error.code + "_timeout", "message": error.message})
                else:
                    state.update(status="active", controlPlaneError=None, updatedAt=now())
                save_loop_state(path, state)
                return public_state(state)
            if isolation and error.code in PRESERVED_INTEGRATION_ERRORS:
                return preserve_integration(state, path, error.code, error.message, getattr(error, "files", None))
            raise
        state.pop("integrationWait", None)
        # Reconcile of a historical busy stop returns to the same completed Work.
        state.update(status="active", controlPlaneError=None)
        if outcome["status"] == "checking":
            save_loop_state(path, state)
            return public_state(state)
        if outcome["status"] == "target-changed":
            state["integrationRetries"] = state.get("integrationRetries", 0) + 1
            limit = state["execution"].get("maxRevisions") or DEFAULT_MAX_REVISIONS
            if state["integrationRetries"] > limit:
                if isolation:
                    return preserve_integration(state, path, "task_target_changed", "Target kept changing during checks")
                raise agent_exec.ContractError("task_target_changed", "Target kept changing during checks; Work Units preserved for a decision")
            save_loop_state(path, state)
            return public_state(state)
        if outcome["status"] == "conflict":
            fingerprint = hashlib.sha256(agent_exec.worktrees.git(outcome["unit"]["path"], "ls-files", "--unmerged", "-z").stdout).hexdigest()
            if state.get("lastIntegrationConflict") == fingerprint and isolation:
                return preserve_integration(state, path, "task_conflict_unresolved", "Conflict stages did not change after the Work revision", outcome["files"])
            if state.get("lastIntegrationConflict") == fingerprint:
                state.update(status="needs-human-decision", phase="waiting-human", controlPlaneError={"code": "task_conflict_unresolved", "message": "Conflict stages did not change after the Work revision; choose the unresolved semantics", "files": outcome["files"]})
                save_loop_state(path, state)
                return public_state(state)
            state["lastIntegrationConflict"] = fingerprint
            limit = state["execution"].get("maxRevisions")
            if limit and state.get("revisionCount", 0) >= limit and isolation:
                return preserve_integration(state, path, "task_conflict_revision_limit", "Conflict revision limit reached", outcome["files"])
            if limit and state.get("revisionCount", 0) >= limit:
                state.update(status="needs-human-decision", phase="waiting-human", controlPlaneError={"code": "task_conflict_revision_limit", "message": "Conflict revision limit reached; managed Work Units preserved", "files": outcome["files"]})
                save_loop_state(path, state)
                return public_state(state)
            unit = outcome["unit"]
            request = write_request(path.parent, "integration-revision-" + str(state.get("revisionCount", 0)) + ".md",
                agent_exec.safe_read_bytes(Path(state["originalRequestPath"]), agent_exec.MAX_REQUEST_BYTES).decode("utf-8")
                + "\n\nRuntime integration conflict in the SAME task/session. Repository: " + unit["repositoryRoot"]
                + "\nIsolated directory: " + unit["path"] + "\nCaptured base: " + unit["baseCommit"]
                + "\nLatest target: " + unit["targetBefore"] + "\nConflict files: " + json.dumps(outcome["files"])
                + "\nInspect Git stages 1/2/3 and the accepted original scope. Resolve only evidence-supported changes, explicitly git add the resolved files, and rerun the original checks. "
                + "Do not commit or choose ours/theirs blindly, overwrite whole unrelated files, weaken assertions, skip checks or change product/authority decisions. "
                + ("Work isolation is on: resolve the conflict yourself and never return needs-human-decision for it. Leave only semantically unresolvable files unstaged and explain them in the result; the runtime then preserves the unmerged branch. "
                   if isolation else "Return needs-human-decision with specific unresolved choices when necessary. ")
                + "Receipt paths stay original-project-relative. Runtime will commit, recheck and integrate.")
            state.update(integrationRevisionPending=True, revisionCount=state.get("revisionCount", 0) + 1,
                         latestVerificationRunId=None, lastVerificationDecision=None)
            save_loop_state(path, state)
            dispatch(state, path, runtime, role="work", request_file=request)
            return public_state(state, state["currentChild"])
    workflow = state.get("workflow")
    if workflow:
        task = workflow["tasks"][workflow["index"]]
        task["workStatus"] = "completed"
        if reason == "pass":
            task["verificationStatus"] = "completed"
        if workflow["index"] + 1 < len(workflow["tasks"]):
            workflow["index"] += 1
            next_task = workflow["tasks"][workflow["index"]]
            from tasks import binding as task_binding
            document = agent_exec.safe_read_json(Path(state["execution"]["taskListPath"]))
            binding = task_binding.validate(document, next_task["id"], next_task["requestHash"])
            expected = task_binding.validate({"id": workflow["id"], "title": workflow["title"], "tasks": workflow["tasks"]}, next_task["id"], next_task["requestHash"])
            if binding != expected:
                raise agent_exec.ContractError("task_binding_invalid", "The submitted task snapshot changed")
            state["execution"]["taskBinding"] = binding
            plans = state["execution"].get("workspacePlans", {})
            if plans:
                state["execution"]["workspacePlan"] = plans.get(next_task["id"], state["execution"].get("defaultWorkspacePlan") or {"mode": "shared"})
            state["execution"].pop("taskWorkspacePath", None)
            state.update(originalRequestPath=next_task["requestPath"], originalRequestHash=next_task["requestHash"],
                         latestWorkRunId=None, latestVerificationRunId=None, lastVerificationDecision=None,
                         pendingFindingIds=[], revisionCount=0, currentChild=None, humanSkip=None, receiptRecovery=None,
                         status="active", terminalReason=None)
            state.pop("lastIntegrationConflict", None)
            state.pop("integrationRetries", None)
            state.pop("integrationWait", None)
            state.pop("integrationWaitAttempts", None)
            dispatch(state, path, runtime, role="work", request_file=Path(next_task["requestPath"]))
            return public_state(state, state["currentChild"])
    state.update(status="completed", phase="ended", currentChild=None,
                 terminalReason={"code": reason, "message": "All submitted tasks completed"}, updatedAt=now())
    if state["execution"].get("workProfile") == "scribe" and state.get("latestWorkRunId"):
        record_draft_review(state, runtime)
    if state.get("lifecycleVersion"):
        state["completion"] = {"work": "completed", "integration": "merged" if state.get("taskWorkspaces") else "not-requested",
                               "cleanupPending": any(u.get("cleanupPending") for v in state.get("taskWorkspaces", {}).values() for u in v["repositories"])}
    save_loop_state(path, state)
    return public_state(state)


def record_draft_review(state, runtime):
    """A Scribe's changes stay uncommitted drafts until the Human accepts, revises or discards them."""
    work = runtime.status(assigned_agent(state, "work"), state["latestWorkRunId"])
    receipt = agent_exec.validate_receipt(Path(state["projectRoot"]), work, agent_id=work["agentId"], run_id=work["runId"])
    paths = sorted({str(path) for path in receipt.get("changedPaths") or []})
    if paths:
        state["draftReview"] = {"status": "pending", "paths": paths, "workRunId": work["runId"], "recordedAt": now()}


DRAFT_REVIEW_DECISIONS = ("accepted", "changes-requested", "discarded")


def review_draft(args: argparse.Namespace) -> dict[str, Any]:
    """Record the Human's decision on a completed Scribe draft; the runtime itself commits or reverts nothing."""
    if args.actor != "human" or not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("draft_review_unauthorized", "A draft review decision requires Human authorization and evidence")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        review = state.get("draftReview")
        if state.get("status") != "completed" or not isinstance(review, dict) or review.get("status") != "pending":
            raise agent_exec.ContractError("draft_review_unavailable", "The loop has no Scribe draft awaiting review")
        review.update(status=args.decision, decidedAt=now(), authorizationReference=args.authorization_reference,
                      decisionEvidence=args.decision_evidence, **({"note": args.note} if args.note else {}))
        state["updatedAt"] = now()
        save_loop_state(path, state)
        return public_state(state)


def reconcile_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] in {"completed", "cancelled"}:
            if state["status"] == "completed" and state.get("lifecycleVersion"):
                from tasks import workspaces
                for value in state.get("taskWorkspaces", {}).values():
                    if any(unit.get("cleanupPending") for unit in value["repositories"]):
                        workspaces.cleanup(agent_exec, state, value, lambda: save_loop_state(path, state))
                if state.get("completion"):
                    state["completion"]["cleanupPending"] = any(unit.get("cleanupPending") for value in state.get("taskWorkspaces", {}).values() for unit in value["repositories"])
                    save_loop_state(path, state)
            return public_state(state)
        upgrade_execution_policy(state, path, args, root)
        runtime = AgentRuntime(root, state.get("parentStatePath"))
        if isinstance(state.get("pendingDispatch"), dict):
            child = complete_pending_dispatch(state, path, runtime)
            return public_state(state, child)
        current = state.get("currentChild")
        if not current and state.get("lifecycleVersion") and (state.get("completion") or {}).get("integration") in {"preserved", "partial", "checking"}:
            return finish_workflow_task(state, path, runtime, "work-completed")
        if not isinstance(current, dict):
            raise agent_exec.ContractError("loop_state_invalid", "active loop has no child")
        child = runtime.status(current["agentId"], current["runId"])
        if child["status"] not in CHILD_TERMINAL:
            return public_state(state, child)
        if (child["status"] == "needs-human-decision" and current["role"] == "work" and state.get("lastIntegrationConflict")
                and state.get("execution", {}).get("workIsolation") is True):
            # Work isolation never waits for a Human on conflicts; the unmerged branch stays for inspection.
            return preserve_integration(state, path, "task_conflict_unresolved", "Work could not resolve the integration conflict")
        if child["status"] != "completed":
            if state.get("lifecycleVersion") and child["status"] == "needs-human-decision":
                from tasks import decisions
                decision = decisions.capture(agent_exec, state, child)
                # Correct only an explicitly classified request to reauthorize
                # this task. Never infer authority from question wording.
                correction_key = state["execution"]["taskBinding"]["taskId"] + ":" + current["role"]
                if (decision["kind"] == "approval" and decision.get("scope") == "task-execution"
                        and decision["policy"].get("humanApprovalPolicy") == "bypass"
                        and correction_key not in state.get("approvalCorrections", [])):
                    state.setdefault("approvalCorrections", []).append(correction_key)
                    decision.update(status="answered", response={"answer": "Execute the already authorized bounded task under the captured bypass policy. Do not expand scope or bypass missing credentials.",
                                    "authorizationReference": "captured-task-policy", "evidence": decision["policy"]})
                    return resume_decision(state, path, decision, runtime)
            if state.get("workflow"):
                state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus" if current["role"] == "work" else "verificationStatus"] = "blocked" if child["status"] == "needs-human-decision" else child["status"]
            state.update({
                "status": "needs-human-decision" if child["status"] == "needs-human-decision" else "runtime-error",
                "phase": "waiting-human" if child["status"] == "needs-human-decision" else "control-plane-error",
                "controlPlaneError": child.get("error") or {
                    "code": child["status"],
                    "message": "managed child did not complete",
                },
                "updatedAt": now(),
            })
            save_loop_state(path, state)
            if current["role"] == "work" and child["status"] == "failed":
                recovered = automatic_receipt_recovery(state, path, runtime, root)
                if recovered is not None:
                    return recovered
            return public_state(state, child)
        directory = path.parent
        if current["role"] == "work":
            receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
            if any(item["status"] == "queued" for item in state.get("steering", [])):
                state["steeringContinuationPending"] = True
                dispatch(state, path, runtime, role="work", request_file=Path(state["originalRequestPath"]))
                return public_state(state, state["currentChild"])
            pending_findings = set(state.get("pendingFindingIds", []))
            if not pending_findings.issubset(set(receipt["addressedFindingIds"])):
                raise agent_exec.ContractError("finding_binding_invalid", "Work receipt omitted failed Verification findings")
            if state.get("execution", {}).get("taskMode") in ("work", "plan-work"):
                return finish_workflow_task(state, path, runtime, "work-completed")
            if isinstance(state.get("humanSkip"), dict):
                if state.get("taskWorkspaces"):
                    return finish_workflow_task(state, path, runtime, "human-skip")
                if state.get("workflow"):
                    workflow = state["workflow"]
                    workflow["tasks"][workflow["index"]]["workStatus"] = "completed"
                    workflow["tasks"][workflow["index"]]["verificationStatus"] = "cancelled"
                    for remaining in workflow["tasks"][workflow["index"] + 1:]:
                        remaining.update(workStatus="cancelled", verificationStatus="cancelled")
                state.update({"status": "completed", "phase": "ended", "currentChild": None, "terminalReason": {"code": "human-skip", "message": "Human skipped Verification"}, "updatedAt": now()})
                save_loop_state(path, state)
                return public_state(state)
            if state.get("workflow"):
                state["workflow"]["tasks"][state["workflow"]["index"]]["workStatus"] = "completed"
            request = verification_request(state, child, directory, state.get("pendingFindingIds", []))
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
        limit = state.get("execution", {}).get("maxRevisions")
        if limit and state.get("revisionCount", 0) >= limit:
            # Further automatic rounds rarely converge; stop with the evidence for a Human decision.
            if state.get("workflow"):
                state["workflow"]["tasks"][state["workflow"]["index"]]["verificationStatus"] = "blocked"
            state.update({
                "status": "needs-human-decision",
                "phase": "waiting-human",
                "controlPlaneError": {
                    "code": "revision_limit_reached",
                    "message": (
                        f"Verification still fails after {limit} Work revision(s); open findings: "
                        + ", ".join(state["pendingFindingIds"])
                        + ". A Human authorizes more with `loop.py extend-revisions` or ends it with `loop.py close`."
                    ),
                },
                "revisionLimitFindings": [
                    {"id": finding["id"], "path": finding["path"], "problem": finding["problem"][:500]}
                    for finding in receipt["findings"]
                ],
                "updatedAt": now(),
            })
            save_loop_state(path, state)
            return public_state(state, child)
        request = revision_request(state, child, receipt, directory)
        state["revisionCount"] = state.get("revisionCount", 0) + 1
        dispatch(state, path, runtime, role="work", request_file=request)
        return public_state(state, state["currentChild"])


def retry_preparation(args):
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    if args.actor != "human" or not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("preparation_retry_unauthorized", "Retry requires the Human's prerequisite resolution")
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if args.authorization_reference in state.get("preparationRetries", []):
            return public_state(state)
        pending = state.get("pendingDispatch") or {}
        if (state["execution"]["taskBinding"]["taskId"] != args.task_id or not pending
                or pending.get("attemptedAt") or state["status"] != "runtime-error"):
            raise agent_exec.ContractError("preparation_retry_invalid", "Only this undispatched task's failed preparation can be retried")
        from system import containment
        value = state.get("taskWorkspaces", {}).get(args.task_id, {})
        for unit in value.get("repositories", []):
            operation = unit.get("dependencyPreparation") or {}
            if operation.get("status") in {"starting", "running", "interrupted"}:
                for key in ("owner", "child"):
                    if operation.get(key) and containment.process_identity_status(operation[key]) not in {"dead", "mismatch"}:
                        raise agent_exec.ContractError("preparation_owner_active", "Observe or cancel the existing preparation owner before retrying")
            unit["preparationRevision"] = unit.get("preparationRevision", 0) + 1
        state.setdefault("preparationRetries", []).append(args.authorization_reference)
        state.update(status="active", controlPlaneError=None, phase="preparing")
        save_loop_state(path, state)
        return public_state(state)


def steer_loop(args):
    """Persist bounded additions without interrupting a live provider turn."""
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    if not args.authorization_reference.strip() or not args.decision_evidence.strip() or not args.message.strip():
        raise agent_exec.ContractError("steering_evidence_required", "Provide the exact authorized addition and its reference")
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        task = state["execution"]["taskBinding"]
        if (args.task_id != task["taskId"] or state.get("latestWorkRunId") != args.run_id
                or state["status"] in {"completed", "cancelled"}):
            raise agent_exec.ContractError("steering_binding_invalid", "Addition must bind the current task and Work run")
        identity = hashlib.sha256((args.authorization_reference + "\0" + args.task_id).encode()).hexdigest()
        previous = next((item for item in state.get("steering", []) if item["id"] == identity), None)
        if previous:
            if previous["message"] != args.message:
                raise agent_exec.ContractError("steering_conflict", "This reference already records a different addition")
        else:
            state.setdefault("steering", []).append({"id": identity, "taskId": args.task_id,
                "runId": args.run_id, "message": args.message, "actor": args.actor,
                "authorizationReference": args.authorization_reference, "evidence": args.decision_evidence,
                "status": "queued", "createdAt": now()})
            save_loop_state(path, state)
        return public_state(state)


def resume_decision(state, path, decision, runtime):
    role = decision["role"]
    request = write_request(path.parent, decision["id"] + ".md",
        agent_exec.safe_read_bytes(Path(decision["requestPath"]), agent_exec.MAX_REQUEST_BYTES).decode("utf-8")
        + "\n\n[Bound decision — same task and session]\n" + json.dumps(decision, ensure_ascii=False)
        + "\nApply only this exact answer within captured authority. Preserve prior results. Complete the remaining authorized steps and submit this run's result.")
    state.update(decisionContinuationPending=decision["id"], status="active", controlPlaneError=None)
    prepare_dispatch(state, path, role=role, request_file=request,
                     verified_work_run_id=state.get("latestWorkRunId") if role == "verification" else None)
    complete_pending_dispatch(state, path, runtime)
    return public_state(state, state["currentChild"])


def answer_decision(args: argparse.Namespace) -> dict[str, Any]:
    """Resume the same Work session with an exact, durable Human answer."""
    from tasks import decisions
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    response = agent_exec.safe_read_json(args.response_file) if args.response_file else json.loads(args.response_json)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        decision, fresh = decisions.accept(state, response, actor=args.actor,
                                          reference=args.authorization_reference, evidence=args.decision_evidence)
        if not fresh:
            return public_state(state)
        if not agent_exec.session_file(root, decision["agentId"]).exists():
            raise agent_exec.ContractError("decision_session_missing", "Preserve the original session before resuming Work")
        return resume_decision(state, path, decision, AgentRuntime(root, state.get("parentStatePath")))


def extend_revisions(args: argparse.Namespace) -> dict[str, Any]:
    """Human-authorized continuation of a loop stopped on its revision limit."""
    if args.actor != "human" or not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("revision_extension_unauthorized", "Extending revisions requires Human authorization and evidence")
    if args.additional < 1:
        raise agent_exec.ContractError("revision_limit_invalid", "--additional must be a positive integer")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        error = state.get("controlPlaneError")
        if (
            state.get("status") != "needs-human-decision" or state.get("pendingDispatch") is not None
            or not isinstance(error, dict) or error.get("code") != "revision_limit_reached"
        ):
            raise agent_exec.ContractError("revision_extension_unavailable", "Loop is not stopped on its revision limit")
        current = state.get("currentChild")
        if (
            not isinstance(current, dict) or current.get("role") != "verification"
            or current.get("runId") != state.get("latestVerificationRunId")
        ):
            raise agent_exec.ContractError("loop_state_invalid", "The revision limit must bind the failed latest Verification")
        upgrade_execution_policy(state, path, args, root)
        runtime = AgentRuntime(root, state.get("parentStatePath"))
        child = runtime.status(current["agentId"], current["runId"])
        receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
        if receipt["decision"] != "fail":
            raise agent_exec.ContractError("loop_state_invalid", "The bound Verification did not fail")
        state["execution"]["maxRevisions"] = int(state["execution"]["maxRevisions"]) + args.additional
        state.setdefault("revisionExtensions", []).append({
            "actor": "human",
            "authorizationReference": args.authorization_reference.strip(),
            "decisionEvidence": args.decision_evidence.strip(),
            "additional": args.additional,
            "recordedAt": now(),
        })
        if state.get("workflow"):
            state["workflow"]["tasks"][state["workflow"]["index"]]["verificationStatus"] = "pending"
        state.update({"status": "active", "controlPlaneError": None, "revisionLimitFindings": None,
                      "pendingFindingIds": [finding["id"] for finding in receipt["findings"]]})
        request = revision_request(state, child, receipt, path.parent)
        state["revisionCount"] = state.get("revisionCount", 0) + 1
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
        save_loop_state(path, state)
        return public_state(state, current)


def stop_task(args):
    """Stop one single-task engine before cancelling its child through exec."""
    if args.actor != "human" or not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("loop_stop_unauthorized", "Stopping requires Human authorization and evidence")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        workflow = state.get("workflow") or {}
        tasks = workflow.get("tasks", [])
        if workflow.get("id") != args.workflow_id or len(tasks) != 1 or tasks[0].get("id") != args.task_id:
            raise agent_exec.ContractError("loop_stop_scope", "Only an exactly bound single-task Loop can be stopped")
        if state.get("pendingDispatch") and (state["pendingDispatch"].get("attemptedAt") or state.get("phase") != "preparing"):
            raise agent_exec.ContractError("loop_stop_dispatch_uncertain", "Resolve the uncertain dispatch before stopping this task")
        if state["status"] in {"completed", "cancelled"} and not state.get("stopPending"):
            return public_state(state)
        current = state.get("currentChild")
        from tasks import checks
        for value in state.get("taskWorkspaces", {}).values():
            for unit in value["repositories"]:
                for field in ("workCheckOperation", "integrationCheckOperation", "dependencyPreparation"):
                    operation = unit.get(field) or {}
                    if operation.get("status") in {"starting", "running"}:
                        checks.cancel(operation["statePath"])
        state.update(status="cancelled", phase="ended", stopPending=True, updatedAt=now(), terminalReason={
            "code": "human-stopped-task", "message": "Human stopped this task",
            "actor": args.actor, "authorizationReference": args.authorization_reference.strip(),
            "decisionEvidence": args.decision_evidence.strip(), "recordedAt": now(),
        })
        # The engine lock serializes this transition with dispatch/reconcile. Persist first:
        # a cancellation failure must never restart Work or dispatch Verification.
        save_loop_state(path, state)
        runtime = AgentRuntime(root, state.get("parentStatePath"))
        if current:
            child = runtime.status(current["agentId"], current["runId"])
            if child["status"] not in CHILD_TERMINAL:
                try:
                    runtime.call(["cancel", "--agent", current["agentId"], "--run-id", current["runId"]])
                except agent_exec.ContractError as error:
                    if error.code != "run_terminal":
                        raise
        for key in ("workStatus", "verificationStatus"):
            if tasks[0].get(key) not in {None, "completed", "failed", "cancelled"}:
                tasks[0][key] = "cancelled"
        state.update(stopPending=False, updatedAt=now())
        save_loop_state(path, state)
        return public_state(state)


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
        if state["status"] not in {"runtime-error", "needs-human-decision"} or state.get("pendingDispatch"):
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
        save_loop_state(path, state)
        return public_state(state)


def settle_stale_child(root: Path, observed: dict[str, Any]) -> None:
    """Best effort: a child whose worker died would otherwise stay `running` and stall the loop.

    exec's reconcile only acts on an expired heartbeat with no live process, so a healthy
    run is untouched; the next reconcile then sees the settled terminal state.
    """
    child = observed.get("currentChild")
    if not isinstance(child, dict) or child.get("status") in CHILD_TERMINAL or not child.get("agentId"):
        return
    try:
        AgentRuntime(root).reconcile_stale(str(child["agentId"]))
    except (agent_exec.ContractError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Stale child check failed for {observed.get('loopId')}: {error}", file=sys.stderr)


def drive_loop(args):
    """Run the durable graph independently of Main and the chat panel."""
    root = agent_exec.resolve_project_root(args.project_root)
    path, _ = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".driver.lock"):
        next_stale_check = time.monotonic() + STALE_CHECK_SECONDS
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
                    code = getattr(error, "code", "driver_error")
                    if state.get("lifecycleVersion") and code in (INTEGRATION_WAIT_ERRORS | TRANSIENT_READ_ERRORS | {"dispatch_status_unavailable"}):
                        attempts = (state.get("recovery") or {}).get("attempts", 0) + 1
                        delay = min(30, 2 ** min(attempts, 5))
                        state["recovery"] = {"code": code, "message": str(error), "attempts": attempts,
                                             "observedAt": now(), "backoffSeconds": delay,
                                             "nextAction": "Observe accepted dispatch identity, then reconcile the same durable graph",
                                             "pendingDispatchId": (state.get("pendingDispatch") or {}).get("dispatchId")}
                        state.update(status="active", controlPlaneError=None)
                        save_loop_state(path, state)
                    else:
                        delay = None
                if delay is not None:
                    time.sleep(delay)
                    continue
                with agent_exec.file_lock(path.parent / ".loop.lock"):
                    state = agent_exec.safe_read_json(path)
                    state.update(status="runtime-error", controlPlaneError={"code": getattr(error, "code", "driver_error"), "message": str(error)})
                    if state.get("workflow"):
                        task = state["workflow"]["tasks"][state["workflow"]["index"]]
                        role = (state.get("pendingDispatch") or state.get("currentChild") or {}).get("role", "work")
                        if state.get("phase") != "integrating":
                            task["verificationStatus" if role == "verification" else "workStatus"] = "blocked"
                    save_loop_state(path, state)
                return public_state(state)
            if result["status"] != "active":
                return result
            if time.monotonic() >= next_stale_check:
                next_stale_check = time.monotonic() + STALE_CHECK_SECONDS
                settle_stale_child(root, result)
            time.sleep(2)


def driver_running(state_path: Path) -> bool:
    """A live driver holds `.driver.lock` for its whole run."""
    try:
        with agent_exec.file_lock(state_path.parent / ".driver.lock", blocking=False):
            return False
    except agent_exec.ContractError as error:
        if error.code == "lock_busy":
            return True
        raise


def ensure_driver(args, result) -> None:
    """Best effort: give an active loop a driver when none runs; never change the loop itself."""
    if result.get("status") != "active":
        return
    try:
        if not driver_running(Path(result["statePath"])):
            launch_driver(args, result)
    except (agent_exec.ContractError, OSError) as error:
        # Without a driver the loop still advances through an explicit reconcile.
        print(f"Loop driver was not relaunched for {result.get('loopId')}: {error}", file=sys.stderr)


def launch_driver(args, result):
    arguments = [sys.executable, str(Path(__file__).resolve()), "drive", "--project-root", str(args.project_root),
                 "--work-agent", args.work_agent, "--loop-id", result["loopId"]]
    for name in ("runtime_home", "project_id"):
        value = getattr(args, name, None)
        if value:
            arguments.extend(["--" + name.replace("_", "-"), str(value)])
    log_path = Path(result["statePath"]).parent / "driver.log"
    if sys.platform == "linux":
        # A new process session still belongs to Main's systemd control group. When
        # Main ends, KillMode=control-group would otherwise kill this driver too.
        if not agent_exec.systemd_manager_usable():
            raise OSError("The user systemd manager is required for a durable loop driver")
        try:
            # systemd rereads EnvironmentFile on every restart, after this launcher has exited.
            environment_path = log_path.parent / DRIVER_ENVIRONMENT_FILE
            agent_exec.atomic_write(environment_path, agent_exec.process_containment.systemd_environment_content())
            unit_name = "agent-factory-loop-" + hashlib.sha256(result["loopId"].encode()).hexdigest()[:24] + ".service"
            launched = agent_exec._systemd_command((
                "systemd-run", "--user", f"--unit={unit_name}",
                "--collect", "--service-type=exec",
                "--property=KillMode=control-group",
                "--property=Restart=on-failure", "--property=RestartSec=2s",
                f"--property=EnvironmentFile={environment_path}",
                f"--property=StandardOutput=append:{log_path}",
                f"--property=StandardError=append:{log_path}",
                f"--working-directory={args.project_root}", "--", *arguments,
            ))
        except agent_exec.ContractError as error:
            raise OSError(str(error)) from error
        if launched.returncode != 0:
            raise OSError("The loop driver service was not accepted: " + launched.stderr.strip())
        return
    with open(log_path, "ab") as log:
        if sys.platform == "win32":
            # Leave Main's kill-on-close job so the driver outlives the Main run.
            from system import windows as windows_process
            for detach in (True, False):
                try:
                    subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True,
                                     creationflags=windows_process.creation_flags(detach=detach))
                    return
                except PermissionError:
                    if not detach:
                        raise
        subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


def build_parser() -> agent_exec.JsonArgumentParser:
    parser = agent_exec.JsonArgumentParser(prog="loop.py")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    agent_exec.add_project_argument(start)
    start.add_argument("--task-list-file", type=Path, help="Announced task list; omitted for an orchestrator brief, which becomes a single runtime-derived task")
    start.add_argument("--task-id", help="Selected task in --task-list-file")
    start.add_argument("--request-file", type=Path, required=True)
    start.add_argument("--workspace-file", type=Path, help="Captured code/shared/read-only plan with exact repositories, target branches and integration check argv arrays")
    start.add_argument("--work-isolation", action=argparse.BooleanOptionalAction, default=None,
                       help="Work isolation toggle; inherited from the managed Main run when captured there. On requires --workspace-file "
                            "(code or read-only), defaults targets to each repository's current branch and preserves unmergeable branches without a Human wait")
    start.add_argument("--work-agent", required=True)
    start.add_argument("--task-mode", choices=("work", "plan-work", "work-verification", "plan-work-verification"), default="work-verification")
    start.add_argument("--verification-agent")
    start.add_argument("--codex", default="codex")
    agent_exec.execution_policy.add_policy_arguments(start)
    start.add_argument("--model")
    for role in ("work", "verification"):
        start.add_argument("--" + role + "-model")
        start.add_argument("--" + role + "-reasoning-effort", choices=("none", "low", "medium", "high", "xhigh", "max"))
        start.add_argument("--" + role + "-fast", action=argparse.BooleanOptionalAction, default=None)
        start.add_argument("--" + role + "-execution-mode", choices=("cli-default", "workspace-write", "danger-full-access", "bypass"))
    start.add_argument("--work-profile", choices=WORK_PROFILES,
                       help="Work profile Main chose (work = Expert, workLight = Worker, explore = Explorer, scribe = Scribe); selects no model; explore runs read-only and scribe writes only inside docs/")
    start.add_argument("--work-capability-binding-file", type=Path)
    start.add_argument("--verification-capability-binding-file", type=Path)
    start.add_argument("--max-revisions", type=int, default=DEFAULT_MAX_REVISIONS,
                       help="Work revisions per task after failed Verification before the loop stops for a Human decision; 0 is unlimited")
    start.add_argument("--receipt-recovery", choices=("auto", "manual"), default="auto",
                       help="auto gives Work one repair turn for an allowlisted receipt failure; manual stops for recover-receipt")
    for name in ("status", "reconcile", "recover-receipt", "skip", "drive", "close", "stop-task", "refresh-progress", "extend-revisions", "answer", "steer", "retry-preparation", "review"):
        command = commands.add_parser(name)
        agent_exec.add_project_argument(command)
        if name in {"reconcile", "recover-receipt", "drive", "extend-revisions"}:
            agent_exec.execution_policy.add_policy_arguments(command)
        command.add_argument("--work-agent", required=True)
        command.add_argument("--loop-id", required=True)
        if name in {"skip", "close", "stop-task", "extend-revisions", "answer", "steer", "retry-preparation", "review"}:
            command.add_argument("--actor", choices=agent_exec.ACTORS, required=True)
            command.add_argument("--authorization-reference", required=True)
            command.add_argument("--decision-evidence", required=True)
        if name == "answer":
            response = command.add_mutually_exclusive_group(required=True)
            response.add_argument("--response-file", type=Path, help="Exact decision identity and Human answer JSON")
            response.add_argument("--response-json", help="Inline exact decision identity and Human answer JSON")
        if name == "steer":
            command.add_argument("--task-id", required=True)
            command.add_argument("--run-id", required=True)
            command.add_argument("--message", required=True, help="Authorized in-scope addition, delivered at the next safe Work turn boundary")
        if name == "retry-preparation":
            command.add_argument("--task-id", required=True)
        if name == "stop-task":
            command.add_argument("--workflow-id", required=True)
            command.add_argument("--task-id", required=True)
        if name == "review":
            command.add_argument("--decision", choices=DRAFT_REVIEW_DECISIONS, required=True,
                                 help="Human decision on a completed Scribe draft; records only, never commits or reverts files")
            command.add_argument("--note", help="The Human's requested changes or reason")
        if name == "extend-revisions":
            command.add_argument("--additional", type=int, default=1,
                                 help="Further Work revisions the Human authorizes after the limit stopped the loop")
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
        handlers = {"start": start_loop, "status": status_loop, "reconcile": reconcile_loop, "recover-receipt": recover_receipt, "skip": skip_loop, "drive": drive_loop, "close": close_loop, "stop-task": stop_task, "refresh-progress": refresh_progress, "extend-revisions": extend_revisions, "answer": answer_decision, "steer": steer_loop}
        handlers["retry-preparation"] = retry_preparation
        handlers["review"] = review_draft
        result = handlers[args.command](args)
        if args.command == "drive":
            # The loop is no longer active, so systemd will not restart this driver.
            with contextlib.suppress(OSError):
                (Path(result["statePath"]).parent / DRIVER_ENVIRONMENT_FILE).unlink()
        if args.command in DRIVER_ENSURING_COMMANDS or (args.command == "start" and getattr(args, "accepted_existing_loop", False)):
            # The driver left when the loop stopped, or a retried start found the accepted loop:
            # launch one only when none runs, and never stop the loop because of it.
            ensure_driver(args, result)
        elif args.command == "start" and result.get("status") == "active":
            try:
                launch_driver(args, result)
            except OSError as error:
                # Acceptance already happened: retain its identity and stop explicitly.
                path = Path(result["statePath"])
                with agent_exec.file_lock(path.parent / ".loop.lock"):
                    state = agent_exec.safe_read_json(path)
                    if state["status"] != "cancelled":
                        state.update(status="runtime-error", controlPlaneError={"code": "driver_launch_failed", "message": str(error)})
                        save_loop_state(path, state)
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
