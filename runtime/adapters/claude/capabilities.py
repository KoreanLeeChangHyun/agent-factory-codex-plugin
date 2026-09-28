"""Claude CLI capabilities and supported public model aliases."""
import subprocess

from task_modes import TASK_MODES

MODELS = {"claude-opus": "opus", "claude-sonnet": "sonnet", "claude-haiku": "haiku"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Codex-only effort names map to the nearest Claude level; "none" leaves Claude's default.
EFFORT_ALIASES = {"none": None, "minimal": "low", "ultra": "max"}


def inspect_capabilities(executable, **_kwargs):
    diagnostic = None
    available = False
    try:
        result = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=10)
        required = ("--print", "--output-format", "--input-format", "--json-schema", "--permission-prompts", "--system-prompt-snapshot", "--replay-user-messages")
        available = result.returncode == 0 and all(flag in result.stdout for flag in required)
        if not available:
            diagnostic = "Installed Claude CLI lacks the required print protocol options"
    except (OSError, subprocess.TimeoutExpired) as error:
        diagnostic = f"Claude CLI unavailable: {error}"
    # Fast and native Goal controls have no Claude equivalent; a print run already continues to completion.
    supported = {"model": available, "reasoning": available, "fast": False, "goal": False,
                 "plan": available, "instructionDelivery": available, "images": available,
                 "taskModes": list(TASK_MODES) if available else [], "automaticRequestHash": True,
                 "worktrees": available}
    return {"schemaVersion": "0.1.0", "kind": "execution-capabilities", "backend": "claude-print",
            "submit": supported, "send": dict(supported), "diagnostic": diagnostic}

