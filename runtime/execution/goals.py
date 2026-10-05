"""Goal state shared by providers whose native Goal is a `/goal <condition>` command.

Such a Goal keeps the session working until the condition holds and persists in the
provider's conversation across resume. There is no pause, budget or live control API,
so the runtime records the Goal it set and stops the run to pause or clear it mid-run.
"""
from pathlib import Path

from storage.errors import ContractError
from storage.files import session_file, update_json

# Native /goal commands reject longer conditions; the full request still arrives as the run's message.
MAX_OBJECTIVE_CHARACTERS = 4000
BOUNDED_OBJECTIVE = ("Complete this run's bounded request supplied in the current message, including necessary "
                     "own checks and the exact result/receipt contract. Repair in-scope implementation and check failures "
                     "and rerun affected checks until they pass. Preserve progress and stop only for cancellation, "
                     "an unavailable external prerequisite, exhausted provider limits or a required unresolved Human decision.")
GOAL_ROLES = ("main", "work")
PAUSED = "paused"


def goal_objective(session, state, request):
    """The condition to set for this run, or None when the run does not use a Goal."""
    execution = state.get("executionOptions", {})
    if session.get("role") not in GOAL_ROLES or execution.get("taskMode") == "plan":
        return None
    if session.get("goalMode") is not True and state.get("goalAction") not in ("resume", "reopen"):
        return None
    objective = (execution.get("goalObjective") or state.get("goalObjective")
                 or (session.get("goal") or {}).get("objective") or request.decode("utf-8"))
    objective = objective.strip()
    return objective if len(objective) <= MAX_OBJECTIVE_CHARACTERS else BOUNDED_OBJECTIVE


def goal_commands(session, state):
    """Slash commands sent before the request: clear a stale Goal, or set this run's Goal."""
    objective = state.get("goalObjective")
    if objective:
        return [f"/goal {objective}"]
    # A Goal survives resume inside the provider; drop it once the Human stops using Goal mode.
    if (session.get("goal") or {}).get("status") not in (None, "complete"):
        return ["/goal clear"]
    return []


def goal_record(session_id, objective, status, *, tokens=0, seconds=0):
    return {"threadId": session_id, "objective": objective, "status": status,
            "tokensUsed": tokens, "timeUsedSeconds": seconds, "tokenBudget": None}


def publish_goal(state, session, goal, observed_at, error=None):
    """Persist the Goal on the run and Agent session; the caller emits goal.updated."""
    fields = {"goal": goal, "goalObservedAt": observed_at, "goalError": error}
    state_path = Path(state["statePath"])
    update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update(fields))
    target = session_file(Path(session["projectRoot"]), state["agentId"])
    update_json(target, target.parent / ".session-state.lock", lambda value: value.update(fields))


def goal_command(runtime, args, root, session):
    if session["role"] != "main":
        raise ContractError("goal_role_invalid", "Goal controls belong to Main")
    goal = session.get("goal")
    if args.action in ("get", "refresh"):
        runtime.emit({"kind": "goal", "agentId": args.agent, "sessionId": session.get("sessionId"),
                      "goal": goal, "observedAt": session.get("goalObservedAt"),
                      "error": session.get("goalError"), "source": "last-runtime-observation"})
        return 0
    if args.action in ("resume", "reopen"):
        if not goal:
            raise ContractError("goal_missing", "Goal was cleared; send a new objective with Goal enabled")
        send_args = runtime.parse_args(["send", "--project-root", str(root), "--agent", args.agent, "--actor", "human",
                                        "--message", "Continue the existing Goal.", "--goal-mode",
                                        "--goal-objective", goal["objective"]])
        send_args.goal_action = args.action
        return runtime.submit(send_args, False)
    directory = runtime.agent_directory(root, args.agent)
    with runtime.file_lock(directory / ".dispatch.lock"):
        active = [state for state in runtime.iter_run_states(root, args.agent) if state.get("status") in runtime.active_states]
        if len(active) > 1:
            raise ContractError("session_busy", "More than one run is active")
        if active and runtime.stop_run is None:
            raise ContractError("goal_unavailable", "Stop the active run before changing its Goal")
        pause = args.action == "pause"
        changed = {**goal, "status": PAUSED} if pause and goal else None
        fields = {"goal": changed, "goalObservedAt": session.get("goalObservedAt"), "goalError": None}
        if not pause:
            fields["goalMode"] = False
        path = session_file(root, args.agent)
        runtime.update_json(path, path.parent / ".session-state.lock", lambda value: value.update(fields))
        stopped = active[0]["runId"] if active else None
    if stopped:
        # No live pause: stopping ends the turn, and the next run re-sets or clears the Goal.
        runtime.stop_run(args.agent, stopped)
    # Applied synchronously, so report the resulting Goal like a refresh.
    runtime.emit({"kind": "goal", "agentId": args.agent, "sessionId": session.get("sessionId"), "goal": changed,
                  "observedAt": fields["goalObservedAt"], "error": None, "source": "runtime-control",
                  **({"stoppedRunId": stopped} if stopped else {})})
    return 0
