"""Antigravity CLI (agy) capabilities. Model identifiers come from `agy models` and pass through."""
from pathlib import Path
import shutil
import subprocess
import time

from tasks.modes import TASK_MODES

EFFORTS = ("low", "medium", "high", "max")
# Agent Factory effort names without an agy level map to the nearest; "none" leaves agy's default.
EFFORT_ALIASES = {"none": None, "minimal": "low", "xhigh": "max", "ultra": "max"}
REQUIRED_OPTIONS = ("--print", "--output-format", "--input-format", "--json-schema", "--conversation",
                    "--dangerously-skip-permissions", "--add-dir", "--effort", "--disable-slash-commands")
CAPABILITY_CACHE_TTL = 60


def inspect_capabilities(executable, *, refresh=False, runtime_home=None, **_kwargs):
    """Probe `agy --help`; reuse a recent successful probe of the same binary."""
    from adapters.capability_cache import cached_capabilities
    return cached_capabilities(executable, provider="antigravity", identify=_identity, probe=_probe,
                               ttl=CAPABILITY_CACHE_TTL, refresh=refresh, runtime_home=runtime_home)


def _identity(executable):
    path = Path(shutil.which(executable) or executable).resolve(strict=True)
    info = path.stat()
    return {"path": str(path), "size": info.st_size, "mtimeNs": info.st_mtime_ns}


def _probe(executable):
    diagnostic = None
    available = False
    try:
        # agy prints its flag list to stderr.
        result = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=20)
        text = result.stdout + result.stderr
        missing = [flag for flag in REQUIRED_OPTIONS if flag not in text]
        available = result.returncode == 0 and not missing
        if not available:
            diagnostic = ("Installed Antigravity CLI lacks required print options: " + ", ".join(missing)
                          if missing else f"Antigravity CLI --help exited with {result.returncode}")
    except (OSError, subprocess.TimeoutExpired) as error:
        diagnostic = f"Antigravity CLI unavailable: {error}"
    # Print mode accepts only text blocks, so no images. Goal uses agy's own /goal command.
    supported = {"model": available, "reasoning": available, "fast": False, "goal": available,
                 "plan": available, "instructionDelivery": available, "images": False,
                 "taskModes": list(TASK_MODES) if available else [], "automaticRequestHash": True,
                 "worktrees": available}
    return {"schemaVersion": "0.1.0", "kind": "execution-capabilities", "backend": "antigravity-print",
            "submit": supported, "send": dict(supported), "diagnostic": diagnostic}


MODELS_CACHE_TTL = 600


def effort_levels(executable, *, runtime_home=None):
    """Map each base Gemini id to the effort levels `agy models` offers (gemini-3.1-pro: low, high).

    Cached briefly per binary; an unavailable listing returns {} so the requested level is passed as is."""
    file = identity = None
    try:
        from storage import paths
        identity = _identity(executable)
        file = paths.home_path(runtime_home) / "cache" / "native-capabilities" / "antigravity-models.json"
        cached = paths.read(file)
        if (isinstance(cached, dict) and cached.get("identity") == identity
                and isinstance(cached.get("created"), (int, float))
                and 0 <= time.time() - cached["created"] < MODELS_CACHE_TTL and isinstance(cached.get("levels"), dict)):
            return cached["levels"]
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        pass  # Missing or unreadable cache: list again.
    try:
        result = subprocess.run([executable, "models"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    levels = {}
    for line in result.stdout.splitlines():
        model = line.split("\t")[0].strip()
        base, _, level = model.rpartition("-")
        if base.startswith("gemini-") and level in EFFORTS:
            levels.setdefault(base, []).append(level)
    if levels and file is not None:
        try:
            paths.mkdir(file.parent)
            paths.write(file, {"identity": identity, "created": time.time(), "levels": levels})
        except (OSError, ValueError):
            pass  # A cache is an optimization.
    return levels
