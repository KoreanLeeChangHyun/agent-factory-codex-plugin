"""Antigravity CLI (agy) provider lifecycle and capability boundary."""
from execution import policy as execution_policy
from .capabilities import inspect_capabilities, EFFORTS
from .policy import validate
from .preflight import check
from .transport import build_command, cli_command, Events


def executable(args, session=None):
    return (session or {}).get("agy", getattr(args, "agy", "agy"))


def session_fields(executable, capabilities=None):
    return {"provider": "antigravity", "agy": executable, "backend": "antigravity-print"}


def validate_execution(session, goal_action=None):
    validate({**session, "goalAction": goal_action})


def discover_policy(args, working_root, *, sandbox=None, approval=None):
    """CLI default: agy's own default mode keeps workspace edits and denies commands."""
    sandbox = sandbox or "workspace-write"
    raw = {"type": sandbox}
    if sandbox == "workspace-write":
        raw["writable_roots"] = [str(working_root)]
    return execution_policy.normalize({"schemaVersion": 1, "sandboxPolicy": raw, "approvalPolicy": approval or "never"})


def prepare(session, state, request):
    from pathlib import Path
    from storage.files import update_json
    from .control import goal_objective
    validate({**session, **state.get("executionOptions", {}), "goalAction": state.get("goalAction")})
    session["backend"] = "antigravity-print"
    objective = goal_objective(session, state, request)
    state["goalObjective"] = objective
    path = Path(state["statePath"])
    update_json(path, path.parent / ".state.lock", lambda value: value.update({
        "goalObjective": objective, "goal": session.get("goal"), "goalError": session.get("goalError")}))


def uses_prompt_parts(session):
    return True


def final_output_schema(session, goal_action=None):
    """`--json-schema` defines the `finish` result of every print turn, Goal included."""
    return True


def fatal_error_events(session):
    return True


def before_stop(state_path, state, *, cancel=False):
    from .control import before_stop as stop
    stop(state_path, state, cancel=cancel)


def goal_command(runtime, args, root, session):
    from .control import goal_command as command
    return command(runtime, args, root, session)


def persisted_fields(session):
    return {key: session[key] for key in ("provider", "backend", "agy", "codex") if key in session}
