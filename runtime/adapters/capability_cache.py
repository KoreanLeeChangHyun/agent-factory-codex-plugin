"""Successful print-protocol capability probes cached per provider and binary identity."""
import time

from storage import paths
from tasks.modes import TASK_MODES


def cached_capabilities(executable, *, provider, identify, probe, ttl, refresh=False, runtime_home=None):
    identity = file = None
    try:
        identity = identify(executable)
        file = paths.home_path(runtime_home) / "cache" / "native-capabilities" / f"{provider}.json"
    except (OSError, ValueError):
        file = None
    if file is not None and not refresh:
        try:
            cached = paths.read(file)
            capabilities = cached.get("capabilities") if isinstance(cached, dict) else None
            flags = capabilities.get("submit") if isinstance(capabilities, dict) else None
            expected = {"model": True, "reasoning": True, "fast": False, "goal": True, "plan": True,
                        "instructionDelivery": True, "images": provider == "claude", "worktrees": True,
                        "automaticRequestHash": True}
            if (isinstance(cached, dict) and cached.get("identity") == identity
                    and type(cached.get("created")) in (int, float)
                    and 0 <= time.time() - cached["created"] < ttl
                    and isinstance(capabilities, dict) and capabilities.get("diagnostic", "missing") is None
                    and capabilities.get("schemaVersion") == "0.1.0"
                    and capabilities.get("kind") == "execution-capabilities"
                    and capabilities.get("backend") == f"{provider}-print"
                    and isinstance(flags, dict) and capabilities.get("send") == flags
                    and all(fields.get(key) is value for fields in (flags, capabilities["send"])
                            for key, value in expected.items())
                    and flags.get("taskModes") == list(TASK_MODES)):
                return capabilities
        except (OSError, ValueError, TypeError, KeyError, OverflowError):
            pass  # Missing or unreadable cache: probe again.
    result = probe(executable)
    if file is not None and result["diagnostic"] is None:
        try:
            if identify(executable) == identity:
                paths.mkdir(file.parent)
                paths.write(file, {"identity": identity, "created": time.time(), "capabilities": result})
        except (OSError, ValueError):
            pass  # Failed cache writes never fail the probe.
    return result
