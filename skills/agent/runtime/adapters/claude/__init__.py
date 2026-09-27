"""Claude provider lifecycle and capability boundary."""
import execution_policy
from runtime_errors import ContractError
from .capabilities import inspect_capabilities, MODELS, EFFORTS, TASK_MODES
from .policy import validate, check, POLICY_FOR_MODE
from .transport import build_command, cli_command, Events

def executable(args, session=None):
    return (session or {}).get("claude", getattr(args, "claude", "claude"))


def session_fields(executable, capabilities=None):
    return {"provider": "claude", "claude": executable, "backend": "claude-print"}


def validate_execution(session, goal_action=None):
    validate({**session, "goalAction": goal_action})


def discover_policy(args, working_root, *, sandbox=None, approval=None):
    """CLI default: read Claude's configured permissions.defaultMode (later settings files win)."""
    import json
    from pathlib import Path
    mode = None
    for path in (Path.home() / ".claude" / "settings.json", Path(working_root) / ".claude" / "settings.json",
                 Path(working_root) / ".claude" / "settings.local.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("defaultMode")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str):
            mode = value
    sandbox = sandbox or POLICY_FOR_MODE.get(mode, "read-only")
    raw = {"type": sandbox}
    if sandbox == "workspace-write":
        raw["writable_roots"] = [str(working_root)]
    return execution_policy.normalize({"schemaVersion": 1, "sandboxPolicy": raw, "approvalPolicy": approval or "never"})


def prepare(session, state, request):
    validate({**session, **state.get("executionOptions", {}), "goalAction": state.get("goalAction")})
    session["backend"] = "claude-print"


def uses_prompt_parts(session):
    return True


def fatal_error_events(session):
    return True


def before_stop(state_path, state, *, cancel=False):
    # Parent containment stops the print process and its tools.
    pass


def goal_command(runtime, args, root, session):
    if args.action == "get":
        runtime.emit({"schemaVersion": runtime.schema_version, "kind": "goal", "agentId": args.agent, "goal": None})
        return 0
    raise ContractError("claude_feature_unsupported", "Claude does not support native Goal controls")


def persisted_fields(session):
    return {key: session[key] for key in ("provider", "backend", "claude", "codex") if key in session}
