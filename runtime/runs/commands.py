"""Run inspection and control commands: status, result, list, inbox, cancel, reset, reconcile and goal."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import time
import uuid
from pathlib import Path
from typing import Any


def command_status(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    dispatch_id = getattr(args, "dispatch_id", None)
    if dispatch_id is not None:
        runtime.validate_id(dispatch_id, runtime.DISPATCH_ID, "dispatch_id")
        matches = [state for state in runtime.iter_run_states(root, args.agent) if state.get("dispatchId") == dispatch_id]
        if not matches:
            raise runtime.ContractError("dispatch_not_found", "dispatch identifier has no managed run")
        if len(matches) != 1:
            raise runtime.ContractError("dispatch_id_collision", "dispatch identifier is not unique")
        state = matches[0]
    else:
        state = runtime.find_run(root, args.agent, args.run_id)
    heartbeat_path = Path(state["heartbeatPath"])
    heartbeat = runtime.safe_read_json(heartbeat_path)
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "status",
            "run": runtime.public_state(state),
            "heartbeat": heartbeat,
        }
    )
    return 0


def command_result(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    state = runtime.find_run(root, args.agent, args.run_id)
    if state.get("status") not in runtime.TERMINAL_STATES:
        raise runtime.ContractError("result_not_ready", "run has no terminal result")
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "result",
            "run": runtime.public_state(state),
        }
    )
    if args.ack:
        path = runtime.state_file(root, args.agent, args.run_id)
        runtime.update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update({"unread": False, "readAt": runtime.now()}),
        )
    return 0


def command_list(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    agents = []
    for directory in runtime.iter_agent_directories(root):
        with contextlib.suppress(runtime.ContractError):
            agents.append(runtime.safe_read_json(directory / "session.json"))
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "agent-list",
            "agents": agents,
        }
    )
    return 0


def command_reset_conversation(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    runtime.validate_id(args.agent, runtime.AGENT_ID, "agent_id")
    directory = runtime.agent_directory(root, args.agent)
    with runtime.file_lock(directory / ".dispatch.lock"):
        session = runtime.load_session(root, args.agent)
        if session.get("role") != "main":
            raise runtime.ContractError("conversation_reset_role_invalid", "Conversation reset is available only for Main Agents")
        if any(state.get("status") in runtime.ACTIVE_STATES for state in runtime.iter_run_states(root, args.agent)):
            raise runtime.ContractError("session_busy", "Finish or cancel the active run before clearing the conversation")
        own_runs = list(runtime.iter_run_states(root, args.agent))
        if own_runs and max(own_runs, key=lambda state: str(state.get("acceptedAt", state.get("runId", "")))).get("status") == "needs-human-decision":
            raise runtime.ContractError("decision_pending", "Resolve the pending Human decision before clearing the conversation")
        active_children = [
            state for state in runtime.iter_run_states(root)
            if state.get("parentAgentId") == args.agent and state.get("status") in runtime.ACTIVE_STATES
        ]
        if active_children:
            raise runtime.ContractError("child_agent_active", "Wait for active child Agents to finish before clearing the conversation")
        if session.get("goalError"):
            raise runtime.ContractError("goal_state_uncertain", "Refresh or resolve the uncertain Goal state before clearing the conversation")
        goal = session.get("goal")
        if isinstance(goal, dict) and goal.get("status") == "active":
            raise runtime.ContractError("goal_active", "Pause or cancel the active Goal before clearing the conversation")
        boundary = f"conversation-{uuid.uuid4().hex}"
        started_at = runtime.now()

        def reset(value: dict[str, Any]) -> None:
            value["sessionId"] = None
            value["conversationId"] = boundary
            value["conversationStartedAt"] = started_at
            for key in ("backend", "goal", "goalObservedAt", "goalError"):
                value.pop(key, None)

        runtime.update_json(directory / "session.json", directory / ".session-state.lock", reset)
    runtime.emit({
        "schemaVersion": runtime.SCHEMA_VERSION,
        "kind": "conversation-reset",
        "agentId": args.agent,
        "conversationId": boundary,
        "startedAt": started_at,
        "historyRetained": True,
    })
    return 0


def command_inbox(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    if args.agent is not None:
        runtime.validate_id(args.agent, runtime.AGENT_ID, "agent_id")
    states = [
        state
        for state in runtime.iter_run_states(root, args.agent)
        if state.get("status") in runtime.TERMINAL_STATES and state.get("unread") is True
    ]
    states.sort(key=lambda value: str(value.get("finishedAt", value.get("updatedAt", ""))))
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "inbox",
            "runs": [runtime.public_state(state) for state in states],
        }
    )
    if args.ack:
        for state in states:
            path = runtime.state_file(root, str(state["agentId"]), str(state["runId"]))
            runtime.update_json(
                path,
                path.parent / ".state.lock",
                lambda value: value.update({"unread": False, "readAt": runtime.now()}),
            )
    return 0


def command_cancel(runtime, args: argparse.Namespace) -> int:
    stop_run(runtime, runtime.resolve_project_root(args.project_root), args.agent, args.run_id)
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "ack",
            "status": "cancelling",
            "agentId": args.agent,
            "runId": args.run_id,
        }
    )
    return 0


def stop_run(runtime, root: Path, agent: str, run_id: str) -> None:
    """Request cancellation and empty the run's containment without emitting a response."""
    path = runtime.state_file(root, agent, run_id)

    def request(value: dict[str, Any]) -> None:
        # Checked under the state lock: a run that just finished must keep its terminal status.
        if value.get("status") in runtime.TERMINAL_STATES:
            raise runtime.ContractError("run_terminal", "run is already terminal")
        value.update({"cancelRequested": True, "status": "cancelling"})

    state = runtime.update_json(path, path.parent / ".state.lock", request)
    runtime.adapters.for_session(state).before_stop(path, state, cancel=True)
    containment_value = state.get("containment")
    if containment_value is None:
        runtime.validate_state_containment_fields(state)
        identities = (
            ("Codex", state.get("codexIdentity")),
            ("worker", state.get("workerIdentity")),
        )
        statuses = [(label, identity, runtime.process_identity_status(identity)) for label, identity in identities if identity is not None]
        if any(status in {"unknown", "mismatch"} for _label, _identity, status in statuses):
            raise runtime.ContractError(
                "process_identity_mismatch",
                "managed process identity could not be verified; refusing to signal",
            )
        if "containmentAttempt" in state and statuses:
            raise runtime.ContractError(
                "containment_identity_unbound",
                "managed processes exist without a bound containment identity; refusing to signal",
            )
        # Migration compatibility for runs accepted before containment binding existed.
        codex_identity = state.get("codexIdentity")
        if isinstance(codex_identity, dict) and runtime.process_identity_status(codex_identity) in {"match", "dead"}:
            runtime.terminate_verified_group(codex_identity)
        worker_identity = state.get("workerIdentity")
        if isinstance(worker_identity, dict) and runtime.process_identity_status(worker_identity) == "match":
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(worker_identity["pid"]), signal.SIGTERM)
    else:
        containment = runtime._validate_state_containment(state)
        if containment["kind"] in {"process-group", "windows-job"}:
            codex_identity = state.get("codexIdentity")
            if codex_identity is not None and runtime.process_identity_status(codex_identity) in {"unknown", "mismatch"}:
                raise runtime.ContractError(
                    "process_identity_mismatch",
                    "managed Codex identity could not be verified; refusing to signal",
                )
            if isinstance(codex_identity, dict):
                runtime.terminate_verified_group(codex_identity)
        runtime.request_containment_stop(containment)
        if not runtime.wait_containment_empty(containment, runtime.PROCESS_TERM_TIMEOUT):
            runtime.force_containment_stop(containment)
        if not runtime.wait_containment_empty(containment, runtime.PROCESS_KILL_TIMEOUT):
            raise runtime.ContractError("containment_not_empty", "managed containment did not become empty")


def heartbeat_stale(runtime, state: dict[str, Any], session: dict[str, Any]) -> bool:
    try:
        heartbeat = runtime.safe_read_json(Path(state["heartbeatPath"]))
    except runtime.ContractError:
        return True
    observed = runtime.parse_time(heartbeat.get("observedAt"))
    return observed is None or time.time() - observed > float(session["heartbeatTimeout"])


def event_stream_has_start_marker(runtime, state: dict[str, Any]) -> bool:
    try:
        content = runtime.safe_read_bytes(Path(state["eventsPath"]), runtime.MAX_REQUEST_BYTES)
    except runtime.ContractError as error:
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


def durably_never_started(runtime, state: dict[str, Any]) -> bool:
    return (
        state.get("startDisposition") == "not-started"
        and state.get("containmentLaunchDisposition") != "launching"
        and state.get("status") in {"accepted", "queued"}
        and state.get("startedAt") is None
        and state.get("sessionId") is None
        and not runtime.event_stream_has_start_marker(state)
    )


def command_reconcile(runtime, args: argparse.Namespace) -> int:
    root = runtime.resolve_project_root(args.project_root)
    if args.agent is not None:
        runtime.validate_id(args.agent, runtime.AGENT_ID, "agent_id")
    reconciled: list[dict[str, Any]] = []
    for state in runtime.iter_run_states(root, args.agent):
        if state.get("status") not in runtime.ACTIVE_STATES:
            continue
        agent_id = str(state["agentId"])
        session = runtime.load_session(root, agent_id)
        if not runtime.heartbeat_stale(state, session):
            continue
        containment_value = state.get("containment")
        if containment_value is not None:
            try:
                containment = runtime._validate_state_containment(state)
                if not runtime.containment_is_empty(containment):
                    reconciled.append(
                        {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
                    )
                    continue
            except runtime.ContractError:
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            # A positively empty bound containment is evaluated below against
            # semantic start evidence; it is never inferred from a numeric PID.
            identity_statuses: list[str] = ["dead"]
        else:
            try:
                runtime.validate_state_containment_fields(state)
            except runtime.ContractError:
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
                runtime.process_identity_status(identity)
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
        if not runtime.durably_never_started(state):
            path = runtime.state_file(root, agent_id, str(state["runId"]))
            started = (
                state.get("startDisposition") == "started"
                or state.get("startedAt") is not None
                or state.get("sessionId") is not None
                or runtime.event_stream_has_start_marker(state)
            )
            code = "started_run_not_replayable" if started else "run_start_unknown"
            runtime.mark_terminal(
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
            path = runtime.state_file(root, agent_id, str(state["runId"]))
            runtime.mark_terminal(
                path,
                "failed",
                {"code": "heartbeat_timeout", "message": "worker heartbeat expired"},
            )
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "failed"}
            )
            continue
        pid = runtime.spawn_worker(root, agent_id, str(state["runId"]))
        reconciled.append(
            {
                "agentId": agent_id,
                "runId": state["runId"],
                "action": "resubmitted",
                "workerPid": pid,
            }
        )
    runtime.emit(
        {
            "schemaVersion": runtime.SCHEMA_VERSION,
            "kind": "reconcile",
            "runs": reconciled,
        }
    )
    return 0


def request_native_pause(runtime, path: Path) -> None:
    """Compatibility delegate for native Goal consumers."""
    from adapters.codex import control
    return control.request_native_pause(path)


def record_goal_uncertainty(runtime, path: Path, message: str) -> None:
    """Compatibility delegate for native Goal consumers."""
    from adapters.codex import control
    return control.record_goal_uncertainty(path, message)


def wait_native_pause(runtime, path: Path) -> None:
    """Compatibility delegate for native Goal consumers."""
    from adapters.codex import control
    return control.wait_native_pause(path)


def command_goal(runtime, args: argparse.Namespace) -> int:
    from adapters.contracts import GoalServices
    root = runtime.resolve_project_root(args.project_root)
    session = runtime.load_session(root, args.agent)
    services = GoalServices(runtime.emit, runtime.agent_directory, runtime.file_lock, runtime.iter_run_states, runtime.update_json,
                            runtime.parse_args, runtime.submit, frozenset(runtime.ACTIVE_STATES), runtime.SCHEMA_VERSION,
                            lambda agent, run_id: stop_run(runtime, root, agent, run_id))
    return runtime.adapters.for_session(session).goal_command(services, args, root, session)
