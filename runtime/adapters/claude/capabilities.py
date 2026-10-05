"""Claude CLI capabilities and supported public model aliases."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import time

from tasks.modes import TASK_MODES
from tasks.subagent_guard import ALLOWED_TYPE

MODELS = {"claude-opus": "opus", "claude-sonnet": "sonnet", "claude-haiku": "haiku"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Codex-only effort names map to the nearest Claude level; "none" leaves Claude's default.
EFFORT_ALIASES = {"none": None, "minimal": "low", "ultra": "max"}


REQUIRED_OPTIONS = ("--print", "--output-format", "--input-format", "--json-schema", "--permission-prompts",
                    "--system-prompt-snapshot", "--replay-user-messages", "--include-partial-messages")
CAPABILITY_CACHE_TTL = 60
# `--thinking-display` is absent from `--help`; 2.1.39 and older reject it as an unknown option.
THINKING_DISPLAY_VERSION = (2, 1, 40)


def inspect_capabilities(executable, *, refresh=False, runtime_home=None, **_kwargs):
    """Probe `claude --help`; reuse a recent successful probe of the same binary and config home."""
    identity = file = None
    try:
        from storage import paths
        identity = _identity(executable)
        file = paths.home_path(runtime_home) / "cache" / "native-capabilities" / "claude.json"
    except (OSError, ValueError):
        file = None
    if file is not None and not refresh:
        try:
            cached = paths.read(file)
            if (isinstance(cached, dict) and cached.get("identity") == identity
                    and isinstance(cached.get("created"), (int, float))
                    and 0 <= time.time() - cached["created"] < CAPABILITY_CACHE_TTL):
                return cached["capabilities"]
        except (OSError, ValueError, TypeError, KeyError):
            pass  # Missing or unreadable cache: probe again.
    result = _probe(executable)
    if file is not None and result["diagnostic"] is None:
        try:
            paths.mkdir(file.parent)
            paths.write(file, {"identity": identity, "created": time.time(), "capabilities": result})
        except (OSError, ValueError):
            pass  # A cache is an optimization; a failed write never fails the probe.
    return result


def _identity(executable):
    path = Path(shutil.which(executable) or executable).resolve(strict=True)
    info = path.stat()
    return {"path": str(path), "size": info.st_size, "mtimeNs": info.st_mtime_ns,
            "configDir": os.environ.get("CLAUDE_CONFIG_DIR", "")}


def _probe(executable):
    diagnostic = None
    available = False
    try:
        result = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=10)
        missing = [flag for flag in REQUIRED_OPTIONS if flag not in result.stdout]
        available = result.returncode == 0 and not missing
        if not available:
            diagnostic = ("Installed Claude CLI lacks required print protocol options: " + ", ".join(missing)
                          if missing else f"Claude CLI --help exited with {result.returncode}")
    except (OSError, subprocess.TimeoutExpired) as error:
        diagnostic = f"Claude CLI unavailable: {error}"
    thinking_display = available and (_version(executable) or ()) >= THINKING_DISPLAY_VERSION
    # Claude has no Fast tier. Goal uses Claude's own /goal command, which print mode supports.
    # workSubagents: the only sub-agent type a Work launch lets the model start.
    supported = {"model": available, "reasoning": available, "fast": False, "goal": available,
                 "plan": available, "instructionDelivery": available, "images": available,
                 "taskModes": list(TASK_MODES) if available else [], "automaticRequestHash": True,
                 "worktrees": available, "workSubagents": ALLOWED_TYPE, "thinkingDisplay": thinking_display}
    return {"schemaVersion": "0.1.0", "kind": "execution-capabilities", "backend": "claude-print",
            "submit": supported, "send": dict(supported), "diagnostic": diagnostic}


def _version(executable):
    """Return `claude --version` as a tuple such as (2, 1, 285), or None when it cannot be read."""
    try:
        result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.match(r"\s*(\d+)\.(\d+)\.(\d+)", result.stdout or "") if result.returncode == 0 else None
    return tuple(int(part) for part in match.groups()) if match else None
