"""Claude permission mapping and unrestricted host readiness check."""
import json

from execution import policy as execution_policy
from storage.errors import ContractError
from tasks import orchestrator_guard, subagent_guard
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


def work_subagent_arguments(restricted=False):
    """Work may start only the read-only Explore sub-agent; every other sub-agent type is denied.

    Claude's `Agent(type)` allowlist applies only to a `--agent` main thread and deny rules name single
    types, so a PreToolUse hook decides. Hooks run before the permission mode, so the denial holds under
    bypassPermissions, acceptEdits, dontAsk and plan. Workflow scripts start sub-agents without the
    Agent tool, so that tool is removed."""
    hook = {"matcher": subagent_guard.MATCHER,
            "hooks": [{"type": "command", "command": subagent_guard.HOOK_COMMAND, "timeout": 30}]}
    hooks = [hook]
    if restricted:
        hooks.append({"matcher": "Bash|Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": orchestrator_guard.HOOK_COMMAND, "timeout": 30}]})
    return ["--settings", json.dumps({"hooks": {"PreToolUse": hooks}}), "--disallowedTools", "Workflow"]


def inspection_arguments(plugin_root):
    """Allow only the existing read-only inspectors, including their page options."""
    script = str(plugin_root / "scripts" / "exec.py")
    return ["--allowedTools", ",".join(f"Bash(python3 {script} {command} *)" for command in ("status", "list"))]


# Read-only Git inspection shared by every allowlist below.
GIT_READS = ["Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git show*)"]


def profile_arguments(plugin_root, profile, write_root, write_paths=(), run_directory=None):
    """Explorer reads, searches and edits exact assigned evidence files; Scribe edits docs/ without web tools.

    dontAsk denies every tool not listed, under any authorized permission mode, so the profile only narrows it.
    Each may run only its Agent Factory Document scripts, never exec.py or loop.py."""
    tools = ["Read", "Grep", "Glob", *GIT_READS,
             *(f"Bash(python3 {plugin_root}/scripts/{name} *)" for name in orchestrator_guard.PROFILE_SCRIPTS[profile])]
    if profile == "explore":
        tools += ["WebSearch", "WebFetch"]
        for path in write_paths:
            tools += [f"Edit(/{path})", f"Write(/{path})"]
        if run_directory:
            tools += [f"Edit(/{run_directory}/**)", f"Write(/{run_directory}/**)"]
    elif write_root:
        files = "/" + str(write_root) + "/**"
        tools += [f"Edit({files})", f"Write({files})"]
    return ["--permission-mode", "dontAsk", "--permission-prompts", "none", "--allowedTools", ",".join(tools)]


def orchestrator_arguments(plugin_root, run_directory):
    """Orchestrate Main reads/confirms links, writes own records and runs guarded managed scripts.

    The run's sandbox policy is unchanged so delegated Work keeps its own permissions."""
    # Claude permission rules spell absolute paths with a leading "//".
    run_files = "/" + str(run_directory) + "/**"
    # Web tools support bounded known-context fact/link confirmation.
    tools = ["Read", "Grep", "Glob", "WebSearch", "WebFetch", f"Edit({run_files})", f"Write({run_files})",
             f"Bash(python3 {plugin_root}/scripts/*)", *GIT_READS]
    return ["--permission-mode", "dontAsk", "--permission-prompts", "none", "--allowedTools", ",".join(tools)]


def orchestrator_hook_arguments():
    hook = {"matcher": "Bash|Write|Edit|MultiEdit", "hooks": [
        {"type": "command", "command": orchestrator_guard.HOOK_COMMAND, "timeout": 30}]}
    return ["--settings", json.dumps({"hooks": {"PreToolUse": [hook]}})]
