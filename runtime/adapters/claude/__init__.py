"""Claude provider lifecycle and capability boundary."""
from execution import policy as execution_policy
from storage.errors import ContractError
from .capabilities import inspect_capabilities, MODELS, EFFORTS, TASK_MODES
from .policy import validate, POLICY_FOR_MODE
from .preflight import check
from .transport import build_command, cli_command, Events

def executable(args, session=None):
    return (session or {}).get("claude", getattr(args, "claude", "claude"))


def session_fields(executable, capabilities=None):
    # Older CLIs reject --thinking-display; record support so the launch adds it only when accepted.
    supported = bool(((capabilities or {}).get("submit") or {}).get("thinkingDisplay"))
    return {"provider": "claude", "claude": executable, "backend": "claude-print", "thinkingDisplay": supported}


def validate_execution(session, goal_action=None):
    validate({**session, "goalAction": goal_action})


def discover_policy(args, working_root, *, sandbox=None, approval=None):
    """CLI default: read Claude's configured permissions.defaultMode (later settings files win)."""
    import json
    from pathlib import Path
    mode = None
    import os
    config = Path(os.environ["CLAUDE_CONFIG_DIR"]) if os.environ.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude"
    for path in (config / "settings.json", Path(working_root) / ".claude" / "settings.json",
                 Path(working_root) / ".claude" / "settings.local.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("defaultMode")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str):
            mode = value
    # Unknown or absent modes fall back to read-only rather than widening access.
    sandbox = sandbox or POLICY_FOR_MODE.get(mode, "read-only")
    raw = {"type": sandbox}
    if sandbox == "workspace-write":
        raw["writable_roots"] = [str(working_root)]
    return execution_policy.normalize({"schemaVersion": 1, "sandboxPolicy": raw, "approvalPolicy": approval or "never"})


def prepare(session, state, request):
    from execution.goals import prepare_command_goal
    validate({**session, **state.get("executionOptions", {}), "goalAction": state.get("goalAction")})
    prepare_command_goal(session, state, request, backend="claude-print")


def uses_prompt_parts(session):
    return True


def final_output_schema(session, goal_action=None):
    """`--json-schema` constrains the final result of every print turn, Goal included."""
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
    return {key: session[key] for key in ("provider", "backend", "claude", "codex") if key in session}
