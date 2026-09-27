"""Codex Goal controls and persisted observation diagnostics."""
import contextlib
import json
import time
import uuid
from pathlib import Path
import paths as runtime_paths
from runtime_storage import update_json, session_file, safe_read_json
from process_transport import append_event
from runtime_errors import ContractError

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



def goal_command(runtime, args, root, session):
    from pathlib import Path
    import uuid
    if session["role"] != "main":
        raise ContractError("goal_role_invalid", "Goal controls belong to Main")
    if args.action == "get":
        runtime.emit({"kind": "goal", "agentId": args.agent, "sessionId": session.get("sessionId"),
              "goal": session.get("goal"), "observedAt": session.get("goalObservedAt"),
              "error": session.get("goalError"), "source": "last-native-observation"})
        return 0
    if not session.get("sessionId"):
        raise ContractError("session_missing", "Start a Main session with a Goal first")
    directory = runtime.agent_directory(root, args.agent)
    with runtime.file_lock(directory / ".dispatch.lock"):
        active = [state for state in runtime.iter_run_states(root, args.agent) if state.get("status") in runtime.active_states]
        if active:
            if len(active) != 1 or args.action in ("resume", "reopen"):
                raise ContractError("session_busy", "Pause the active run before reopening Goal")
            state = active[0]
            if state.get("backend") != "app-server":
                raise ContractError("goal_unavailable", "The active run does not own a native Goal connection")
            path = Path(state["statePath"])
            control = {"id": str(uuid.uuid4()), "action": "get" if args.action == "refresh" else args.action}
            runtime.update_json(path, path.parent / ".state.lock", lambda value: value.update({"goalControl": control}))
            runtime.emit({"kind": "goal-control", "status": "accepted", "agentId": args.agent, "runId": state["runId"], **control})
            return 0
    # Reuse managed acceptance, locks, process containment, events and run results.
    if args.action in ("resume", "reopen") and not session.get("goal"):
        raise ContractError("goal_missing", "Goal was cleared; send a new objective with Goal enabled")
    send_args = runtime.parse_args(["send", "--project-root", str(root), "--agent", args.agent,
                           "--actor", "human", "--message", "Continue the existing native Goal through the Main → Work → Verification graph.",
                           *(["--goal-mode"] if args.action in ("resume", "reopen") else ["--no-goal-mode"] if args.action in ("clear", "cancel", "disable") else [])])
    send_args.goal_action = "get" if args.action == "refresh" else args.action
    return runtime.submit(send_args, False)

