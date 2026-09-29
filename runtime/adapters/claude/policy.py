"""Claude permission mapping and unrestricted host readiness check."""
from execution import policy as execution_policy
from storage.errors import ContractError
from .capabilities import EFFORTS, EFFORT_ALIASES

# Nearest Claude permission mode for each Agent Factory sandbox type. Claude tool permissions are
# not an OS sandbox: network access is not confined and writable_roots only extend tool access.
PERMISSION_MODES = {"danger-full-access": "bypassPermissions", "workspace-write": "acceptEdits", "read-only": "dontAsk"}
# Claude's configured permissions.defaultMode -> inherited sandbox type. "default" asks before
# each change and "plan"/"dontAsk" never change files, so none of them grants write access.
POLICY_FOR_MODE = {"bypassPermissions": "danger-full-access", "acceptEdits": "workspace-write", "auto": "workspace-write",
                   "default": "read-only", "plan": "read-only", "dontAsk": "read-only"}


def validate(session):
    model = session.get("model")
    if model and (not isinstance(model, str) or not model.startswith("claude-") or any(c.isspace() for c in model)):
        raise ContractError("provider_model_mismatch", "Claude model must be a claude-* identifier")
    requested = session.get("reasoningEffort")
    if requested not in (None, "") and requested not in EFFORTS and requested not in EFFORT_ALIASES:
        raise ContractError("reasoning_effort_invalid", f"Claude does not support reasoning effort {requested!r}")


def effort(value):
    if value in EFFORTS:
        return value
    return EFFORT_ALIASES.get(value)


def permission_arguments(session, working_directory):
    policy = execution_policy.session_policy(session)["sandboxPolicy"]
    arguments = ["--permission-mode", PERMISSION_MODES[policy["type"]], "--permission-prompts", "none"]
    if policy["type"] == "workspace-write":
        for root in policy.get("writable_roots", []):
            if str(root) != str(working_directory):
                arguments += ["--add-dir", str(root)]
    return arguments
