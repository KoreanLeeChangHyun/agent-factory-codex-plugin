"""Read the invoking Codex session policy without widening its permissions."""
import os
import re
from pathlib import Path
from execution_policy import PolicyError, _open_regular, _json, _path, normalize

def _last_context(filename):
    # Walk backward so long-running session histories need no full-file scan.
    with _open_regular(filename) as stream:
        position = stream.seek(0, 2)
        buffer = b""
        trailing = False
        if position:
            stream.seek(position - 1)
            trailing = stream.read(1) != b"\n"
        while position:
            length = min(position, 65536)
            position -= length
            stream.seek(position)
            buffer = stream.read(length) + buffer
            lines = buffer.split(b"\n")
            buffer = lines.pop(0)
            for line in reversed(lines):
                partial = trailing
                trailing = False
                if not line.strip():
                    continue
                try:
                    event = _json(line)
                except PolicyError:
                    if partial:
                        continue  # Only an unterminated EOF line may be incomplete.
                    raise
                if isinstance(event, dict) and event.get("type") == "turn_context":
                    return event.get("payload")
            if len(buffer) > 16 * 1024 * 1024:
                raise PolicyError("policy_unavailable", "rollout event exceeds inspection bound")
        if buffer.strip():
            event = _json(buffer)
            if isinstance(event, dict) and event.get("type") == "turn_context":
                return event.get("payload")
    raise PolicyError("policy_unavailable", "parent rollout has no turn_context")


def _rollout_policy(thread_id):
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", thread_id):
        raise PolicyError("policy_invalid", "invalid CODEX_THREAD_ID")
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    files = list((home / "sessions").rglob(f"rollout-*-{thread_id}.jsonl"))
    if not files:
        raise PolicyError("policy_unavailable", "parent Codex rollout is unavailable; cannot infer its permissions")
    filename = max(files, key=lambda item: item.stat().st_mtime_ns)
    _path(filename)
    context = _last_context(filename)
    if not isinstance(context, dict):
        raise PolicyError("policy_invalid", "parent turn_context is invalid")
    sandbox = dict(context.get("sandbox_policy") or {})
    profile = context.get("permission_profile")
    # Stock disabled enforcement is exactly representable by full access. Named
    # profiles and richer filesystem rules still require a managed snapshot.
    disabled_full_access = profile == {"type": "disabled"} and sandbox.get("type") == "danger-full-access"
    if (profile is not None and not disabled_full_access
            or any(context.get(key) is not None for key in ("permissions", "file_system_sandbox_policy"))):
        raise PolicyError("policy_unsupported", "parent uses a permission profile without a canonical managed snapshot")
    if sandbox.get("type") == "workspace-write":
        sandbox["writable_roots"] = [*sandbox.get("writable_roots", []), _path(context.get("cwd"))]
    return normalize({"schemaVersion": 1, "sandboxPolicy": sandbox, "approvalPolicy": context.get("approval_policy")})

