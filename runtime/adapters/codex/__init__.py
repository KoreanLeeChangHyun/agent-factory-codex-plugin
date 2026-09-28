"""Codex provider lifecycle; native implementation lives inside this package."""
from . import transport as native_codex
from . import preflight
from . import command


def inspect_capabilities(executable, **kwargs):
    capabilities = dict(native_codex.inspect_capabilities(executable, **kwargs))
    from task_modes import TASK_MODES
    modes = [mode for mode in TASK_MODES if mode not in ("plan", "plan-work", "plan-work-verification")
             or capabilities.get("submit", {}).get("plan") is True]
    for operation in ("submit", "send"):
        capabilities[operation] = {**capabilities.get(operation, {}), "images": True, "taskModes": modes,
                                   "automaticRequestHash": True, "worktrees": True}
    return capabilities


def check(session, policy, working_directory, run_directory, request_path):
    return preflight.check(session["codex"], policy, working_directory, run_directory, request_path)


def build_command(session, state, session_id, *, prompt_parts=False):
    return command.build_codex_command(session, state, session_id, prompt_parts=prompt_parts)


def executable(args, session=None):
    return (session or {}).get("codex", getattr(args, "codex", "codex"))


def session_fields(executable, capabilities=None):
    fields = {"provider": "codex", "codex": executable}
    if capabilities is None or capabilities.get("submit", {}).get("instructionDelivery") is True:
        fields["backend"] = "app-server"
    return fields


def validate(session, **kwargs):
    # Common task/role validation remains in the orchestrator.
    pass


def validate_execution(session, goal_action=None):
    from runtime_errors import ContractError
    required = {"plan": session.get("taskMode") in ("plan", "plan-work", "plan-work-verification"),
                "fast": session.get("fast") is True and goal_action in (None, "resume", "reopen"),
                "goal": session.get("goalMode") is True or bool(goal_action)}
    if any(required.values()) or session.get("backend") == "app-server":
        capabilities = inspect_capabilities(str(session["codex"]))
        for field, needed in required.items():
            if needed and not capabilities["send"].get(field, False):
                raise ContractError("native_unsupported", capabilities["diagnostic"] or f"Native {field} unsupported")


def discover_policy(args, working_root, **kwargs):
    # Compatibility entry point also preserves existing policy-discovery mocks.
    from execution_policy import _configured_policy
    return _configured_policy(getattr(args, "codex", None) or "codex", working_root, **kwargs)


def prepare(session, state, request):
    from pathlib import Path
    from runtime_storage import atomic_write_json, update_json
    execution = state.get("executionOptions", {})
    if (execution.get("taskMode") in ("plan", "plan-work", "plan-work-verification")
            or session.get("backend") == "app-server" or session.get("fast") is True
            or session.get("goalMode") is True or state.get("goalAction")):
        session["backend"] = "app-server"
    if session.get("backend") != "app-server":
        return
    path = Path(state["statePath"])
    session["nativeCapabilities"] = inspect_capabilities(str(session["codex"]))["send"]
    state["nativeSessionPath"] = str(path.parent / "native-session.json")
    objective = execution.get("goalObjective")
    if session.get("goalMode") is True and not objective and not session.get("goal"):
        objective = request.decode("utf-8")
    if objective:
        state["goalObjective"] = objective
    atomic_write_json(Path(state["nativeSessionPath"]), session)
    update_json(path, path.parent / ".state.lock", lambda value: value.update({
        "nativeSessionPath": state["nativeSessionPath"], "goalObjective": objective, "backend": "app-server",
        "goal": session.get("goal"), "goalError": session.get("goalError"),
        "nativeGoalExpected": session.get("goalMode") is True or bool(session.get("goal"))}))


def uses_prompt_parts(session):
    return session.get("backend") == "app-server"


def fatal_error_events(session):
    return uses_prompt_parts(session)


def before_stop(state_path, state, *, cancel=False):
    if state.get("backend") != "app-server":
        return
    from . import control
    import contextlib
    try:
        if not cancel:
            control.request_native_pause(state_path)
        control.wait_native_pause(state_path)
    except Exception:
        with contextlib.suppress(Exception):
            control.record_goal_uncertainty(state_path, "Native pause could not be confirmed; refresh Goal before reopening")


def persisted_fields(session):
    return {key: session[key] for key in ("provider", "backend", "codex") if key in session}


def goal_command(runtime, args, root, session):
    from .control import goal_command as command
    return command(runtime, args, root, session)
