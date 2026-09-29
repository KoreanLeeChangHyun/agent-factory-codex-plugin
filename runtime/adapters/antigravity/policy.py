"""Antigravity permission mapping. agy permissions are tool approvals, not an OS sandbox."""
from execution import policy as execution_policy
from storage.errors import ContractError
from .capabilities import EFFORTS, EFFORT_ALIASES

# Print mode cannot prompt: in agy's default (request-review) mode it keeps file reads and
# workspace edits and auto-denies commands and other approval-gated tools. Only
# --dangerously-skip-permissions approves every tool.
SKIP_PERMISSIONS = "danger-full-access"
# agy ends a print turn without a result once it denies a tool, so state the limits up front.
NOTICES = {
    "plan": ("This is a planning phase: do not create or modify any file (including receipts) and do not run "
             "shell commands; a denied call ends this turn without a result. Only read and plan."),
    "workspace-write": ("Execution policy is workspace-write: shell commands, other approval-gated tools and reads "
                        "outside the workspace and run directory are denied; a denied call ends this turn without "
                        "a result. Use file tools inside those directories only."),
    "read-only": ("Execution policy is read-only: do not create, modify or delete files, run shell commands or "
                  "read outside the workspace and run directory; a denied call ends this turn without a result. "
                  "The Antigravity CLI does not enforce this policy for workspace file edits."),
}


def validate(session):
    model = session.get("model")
    if model and (not isinstance(model, str) or any(c.isspace() for c in model) or not native_model(model)):
        raise ContractError("provider_model_mismatch", "Antigravity model must be an identifier listed by `agy models`")
    requested = session.get("reasoningEffort")
    if requested not in (None, "") and requested not in EFFORTS and requested not in EFFORT_ALIASES:
        raise ContractError("reasoning_effort_invalid", f"Antigravity does not support reasoning effort {requested!r}")


def effort(value):
    if value in EFFORTS:
        return value
    return EFFORT_ALIASES.get(value)


QUALIFIER = "antigravity/"


def native_model(model):
    """The agy model identifier: `antigravity/<id>` names it explicitly for provider selection."""
    return model[len(QUALIFIER):] if isinstance(model, str) and model.startswith(QUALIFIER) else model


def effort_arguments(session):
    """agy takes --effort only for its default model and base Gemini IDs (gemini-3.8-flash, which
    require it). IDs ending in a level (gemini-3.8-flash-low) fix their effort; other families reject it."""
    model, level = native_model(session.get("model")), effort(session.get("reasoningEffort"))
    if not level:
        return []
    if model and (not model.startswith("gemini-") or model.rsplit("-", 1)[-1] in EFFORTS):
        return []
    return ["--effort", nearest_level(level, (session.get("effortLevels") or {}).get(model))]


def nearest_level(level, offered):
    """The offered level closest to the requested one, preferring the higher on a tie."""
    if not offered or level in offered:
        return level
    rank = {name: index for index, name in enumerate(EFFORTS)}
    return min((item for item in offered if item in rank),
               key=lambda item: (abs(rank[item] - rank[level]), -rank[item]), default=level)


def sandbox(session):
    return execution_policy.session_policy(session)["sandboxPolicy"]


def permission_arguments(session, working_directory):
    policy = sandbox(session)
    if policy["type"] == SKIP_PERMISSIONS:
        return ["--dangerously-skip-permissions"]
    arguments = []
    if policy["type"] == "workspace-write":
        for root in policy.get("writable_roots", []):
            if str(root) != str(working_directory):
                arguments += ["--add-dir", str(root)]
    return arguments
