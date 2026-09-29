"""Codex app-server capability probing, with a short per-binary cache."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from system import portable


# Codex adapter errors, shared by capability probing and the transport.
class NativeError(Exception):
    pass


class RpcError(NativeError):
    def __init__(self, method, error):
        self.code = error.get("code") if isinstance(error, dict) else None
        super().__init__(f"{method}: {json.dumps(error)[:2000]}")


def _probe_capabilities(codex: str) -> dict:
    """Inspect this executable's protocol, never infer support from wrapper flags."""
    supported = {"model": True, "reasoning": True, "fast": False, "goal": False, "plan": False,
                 "instructionDelivery": False}
    reason = None
    try:
        with tempfile.TemporaryDirectory(prefix="agent-factory-codex-schema-") as directory:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run([codex, "app-server", "generate-json-schema", "--experimental", "--out", directory],
                                        stdout=output, stderr=output, check=False)
                if result.returncode:
                    raise NativeError("installed Codex cannot generate the experimental app-server schema")
            def schema(name):
                path = Path(directory) / name
                return json.loads(path.read_text())
            for feature in ("fast", "goal", "plan"):
                try:
                    turn = schema("v2/TurnStartParams.json")["properties"]
                    if feature == "fast":
                        start = schema("v2/ThreadStartParams.json")["properties"]
                        resume = schema("v2/ThreadResumeParams.json")["properties"]
                        catalog = schema("v2/ModelListResponse.json")["definitions"]["Model"]["properties"]
                        supported[feature] = all("serviceTier" in fields for fields in (start, resume, turn)) and "serviceTiers" in catalog
                    elif feature == "plan":
                        methods = json.dumps(schema("ClientRequest.json"))
                        definition = schema("v2/TurnStartParams.json")
                        modes = definition.get("definitions", {}).get("ModeKind", {}).get("enum", [])
                        supported[feature] = "outputSchema" in turn and "collaborationMode" in turn and "collaborationMode/list" in methods and all(mode in modes for mode in ("plan", "default"))
                    else:
                        methods = json.dumps(schema("ClientRequest.json"))
                        statuses = schema("v2/ThreadGoalSetParams.json")["definitions"]["ThreadGoalStatus"]["enum"]
                        supported[feature] = all(method in methods for method in ("thread/goal/set", "thread/goal/get", "thread/goal/clear")) and all(status in statuses for status in ("active", "paused", "complete")) and "outputSchema" in turn
                except (OSError, ValueError, KeyError, NativeError):
                    supported[feature] = False
            try:
                methods = json.dumps(schema("ClientRequest.json"))
                start = schema("v2/ThreadStartParams.json")["properties"]
                resume = schema("v2/ThreadResumeParams.json")["properties"]
                turn = schema("v2/TurnStartParams.json")["properties"]
                read = schema("v2/ConfigReadParams.json")["properties"]
                effective = schema("v2/ConfigReadResponse.json")["definitions"]["Config"]["properties"]
                supported["instructionDelivery"] = (
                    all(method in methods for method in ("config/read", "thread/inject_items"))
                    and all("developerInstructions" in fields for fields in (start, resume))
                    and "outputSchema" in turn and "cwd" in read and "developer_instructions" in effective)
            except (OSError, ValueError, KeyError, NativeError):
                pass

    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired, NativeError) as error:
        reason = f"Native Fast/Goal/Plan requires compatible Codex app-server schemas: {error}. Update/select Codex, then retry."
    if not all(supported[key] for key in ("model", "reasoning", "fast", "goal", "plan")) and reason is None:
        reason = "Installed Codex protocol lacks required native fields. Update/select Codex, then retry."
    return {"schemaVersion": "0.1.0", "kind": "execution-capabilities", "backend": "codex-app-server-stdio",
            "submit": supported, "send": dict(supported), "diagnostic": reason}



# One bounded entry per operational home; account/model availability is never stored.
CAPABILITY_CACHE_TTL = 60


def _capability_identity(codex):
    executable = shutil.which(codex)
    if not executable:
        raise OSError("Codex executable not found")
    path = Path(executable).resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise OSError("Codex executable is not a regular file")
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino,
            "size": info.st_size, "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns,
            "codexHome": str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve())}


def _cached_capabilities(paths, file, identity):
    try:
        value = paths.read(file)
        if (not isinstance(value, dict) or set(value) != {"version", "identity", "created", "capabilities"}
                or value["version"] != 1 or value["identity"] != identity
                or type(value["created"]) not in (int, float)
                or not 0 <= time.time() - value["created"] < CAPABILITY_CACHE_TTL):
            return None
        caps = value["capabilities"]
        expected = {"model": True, "reasoning": True, "fast": True, "goal": True, "plan": True}
        if (not isinstance(caps, dict) or set(caps) != {"schemaVersion", "kind", "backend", "submit", "send", "diagnostic"}
                or caps["schemaVersion"] != "0.1.0" or caps["kind"] != "execution-capabilities"
                or caps["backend"] != "codex-app-server-stdio" or caps["diagnostic"] is not None):
            return None
        for verb in ("submit", "send"):
            fields = caps[verb]
            if (not isinstance(fields, dict) or set(fields) != {*expected, "instructionDelivery"}
                    or any(fields.get(key) != value for key, value in expected.items())
                    or any(type(v) is not bool for v in fields.values())):
                return None
        if caps["submit"]["instructionDelivery"] != caps["send"]["instructionDelivery"]:
            return None
        return caps
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


def inspect_capabilities(codex: str, *, refresh: bool = False, runtime_home=None) -> dict:
    """Reuse only recent successful protocol probes for this binary and Codex home."""
    if os.environ.get("AF_CODEX_CAPABILITY_CACHE") == "0":
        return _probe_capabilities(codex)
    result = None
    try:
        from storage import paths
        identity = _capability_identity(codex)
        directory = paths.home_path(runtime_home) / "cache" / "native-capabilities"
        file = directory / "capabilities.json"
        cached = _cached_capabilities(paths, file, identity)
        if cached is not None:
            return cached
        if not refresh:
            return _probe_capabilities(codex)
        paths.mkdir(directory)
        # A short bounded wait coalesces ordinary concurrent probes; a stuck
        # writer cannot add its full probe timeout to another caller's latency.
        fd = os.open(directory / ".lock", os.O_RDWR | os.O_CREAT | portable.O_NOFOLLOW | portable.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not portable.private_to_user(info):
                raise ValueError("unsafe capability cache lock")
            try:
                portable.lock_descriptor(fd, timeout=.5)
            except BlockingIOError:
                raise OSError("capability cache lock busy") from None
            cached = _cached_capabilities(paths, file, identity)
            if cached is not None:
                return cached
            result = _probe_capabilities(codex)
            # Missing/failed/partial schemas are retried next time. A replacement
            # during inspection cannot publish support for the old identity.
            if result["diagnostic"] is None and _capability_identity(codex) == identity:
                paths.write(file, {"version": 1, "identity": identity, "created": time.time(), "capabilities": result})
            return result
        finally:
            os.close(fd)
    except (OSError, ValueError, ImportError):
        return result if result is not None else _probe_capabilities(codex)
