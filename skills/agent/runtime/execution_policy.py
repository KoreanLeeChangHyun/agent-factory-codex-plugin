"""Resolve one execution policy for managed CLI/native children without widening it."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

import permissions
from runtime_storage import AGENT_ID

SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
APPROVALS = ("never", "on-request", "untrusted", "on-failure")
SNAPSHOT_ENV = "AGENT_FACTORY_EXECUTION_POLICY"
PARENT_STATE_ENV = "AGENT_FACTORY_PARENT_STATE"
MAX_POLICY_BYTES = 1024 * 1024


class PolicyError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


def _path(value):
    if not isinstance(value, (str, Path)) or not str(value) or "\x00" in str(value):
        raise PolicyError("policy_invalid", "policy path must be an absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.resolve() != path:
        raise PolicyError("policy_invalid", "policy paths must be canonical and cannot traverse symlinks")
    return str(path)


def normalize(value):
    if (not isinstance(value, dict) or set(value) != {"schemaVersion", "sandboxPolicy", "approvalPolicy"}
            or type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1):
        raise PolicyError("policy_invalid", "expected execution policy schemaVersion 1")
    approval = value["approvalPolicy"]
    if not isinstance(approval, str) or approval not in APPROVALS:
        raise PolicyError("policy_unsupported", "unsupported approval policy")
    source = value["sandboxPolicy"]
    if not isinstance(source, dict) or source.get("type") not in SANDBOXES:
        raise PolicyError("policy_unsupported", "unsupported sandbox policy")
    mode = source["type"]
    allowed = {"type", "network_access"}
    if mode == "workspace-write":
        allowed.update(("writable_roots", "exclude_tmpdir_env_var", "exclude_slash_tmp"))
    if set(source) - allowed:
        raise PolicyError("policy_unsupported", "sandbox has restrictions this adapter cannot preserve")
    network = source.get("network_access", mode == "danger-full-access")
    if type(network) is not bool or mode == "danger-full-access" and not network:
        raise PolicyError("policy_invalid", "invalid sandbox network policy")
    sandbox = {"type": mode, "network_access": network}
    if mode == "workspace-write":
        roots = source.get("writable_roots", [])
        if not isinstance(roots, list):
            raise PolicyError("policy_invalid", "writable_roots must be an array")
        sandbox["writable_roots"] = sorted(set(_path(root) for root in roots))
        for key in ("exclude_tmpdir_env_var", "exclude_slash_tmp"):
            setting = source.get(key, False)
            if type(setting) is not bool:
                raise PolicyError("policy_invalid", f"{key} must be boolean")
            sandbox[key] = setting
    return {"schemaVersion": 1, "sandboxPolicy": sandbox, "approvalPolicy": approval}


def _json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PolicyError("policy_invalid", "duplicate JSON policy field")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as error:
        raise PolicyError("policy_invalid", "invalid policy JSON") from error


def _open_regular(path):
    filename = Path(_path(path))
    descriptor = os.open(filename, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise PolicyError("policy_invalid", "policy source must be a regular file")
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _read(path):
    filename = Path(_path(path))
    try:
        with _open_regular(filename) as stream:
            content = stream.read(MAX_POLICY_BYTES + 1)
    except OSError as error:
        raise PolicyError("policy_unavailable", f"cannot read policy source: {filename}") from error
    if len(content) > MAX_POLICY_BYTES:
        raise PolicyError("policy_invalid", "policy source exceeds 1 MiB")
    return _json(content)


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


def _managed_parent(snapshot, project_root):
    locator = os.environ.get(PARENT_STATE_ENV)
    if not locator:
        return
    state_path = Path(_path(locator))
    state = _read(state_path)
    if not isinstance(state, dict) or state.get("statePath") != str(state_path):
        raise PolicyError("policy_parent_mismatch", "managed parent locator does not match its state")
    binding = state.get("runtimeBinding")
    if not isinstance(binding, dict) or binding.get("projectRoot") != project_root:
        raise PolicyError("policy_parent_mismatch", "managed parent belongs to another project")
    import paths
    paths.bind(binding)
    agent_id, run_id = state.get("agentId"), state.get("runId")
    if any(not isinstance(value, str) or not AGENT_ID.fullmatch(value)
           for value in (agent_id, run_id)):
        raise PolicyError("policy_parent_mismatch", "managed parent has invalid agent/run identity")
    agent_root = Path(binding["agentsRoot"]) / agent_id
    if state_path != agent_root / "runs" / run_id / "state.json":
        raise PolicyError("policy_parent_mismatch", "managed parent locator does not match its registered run")
    if normalize(state.get("executionPolicy")) != snapshot:
        raise PolicyError("policy_parent_mismatch", "snapshot differs from managed parent state")
    session = _read(agent_root / "session.json")
    if (not isinstance(session, dict) or session.get("agentId") != agent_id
            or session.get("projectRoot") != project_root or session_policy(session) != snapshot):
        raise PolicyError("policy_parent_mismatch", "snapshot differs from managed parent session")


def _native_selected_policy(rpc, project_root, sandbox, approval):
    params = {"cwd": project_root, "ephemeral": True}
    if sandbox is not None:
        params["sandbox"] = sandbox
    if approval is not None:
        params["approvalPolicy"] = approval
    # Starting an ephemeral thread resolves native defaults without a model turn,
    # transcript persistence, or approximating its permission selection rules.
    response = rpc.call("thread/start", params, timeout=3)
    if not isinstance(response, dict) or response.get("cwd") != project_root:
        raise PolicyError("policy_invalid", "native policy discovery returned a different cwd")
    raw = response.get("sandbox")
    if not isinstance(raw, dict):
        raise PolicyError("policy_invalid", "native policy discovery omitted its sandbox")
    kinds = {"dangerFullAccess": "danger-full-access", "workspaceWrite": "workspace-write", "readOnly": "read-only"}
    keys = {"type": "type", "networkAccess": "network_access", "writableRoots": "writable_roots",
            "excludeSlashTmp": "exclude_slash_tmp", "excludeTmpdirEnvVar": "exclude_tmpdir_env_var"}
    if set(raw) - set(keys) or raw.get("type") not in kinds:
        raise PolicyError("policy_unsupported", "native sandbox cannot be represented by the managed policy")
    value = {keys[key]: setting for key, setting in raw.items()}
    value["type"] = kinds[raw["type"]]
    active = response.get("activePermissionProfile")
    builtin = {"read-only": ":read-only", "workspace-write": ":workspace", "danger-full-access": ":danger-full-access"}
    if active is not None and (not isinstance(active, dict) or active.get("id") != builtin[value["type"]]
                               or active.get("extends") is not None):
        raise PolicyError("policy_unsupported", "selected native permissions require a richer policy snapshot")
    if value["type"] == "workspace-write":
        value["writable_roots"] = [*value.get("writable_roots", []), project_root]
    return normalize({"schemaVersion": 1, "sandboxPolicy": value, "approvalPolicy": response.get("approvalPolicy")})


def _configured_policy(codex, project_root, *, sandbox=None, approval=None):
    """Read effective configuration; resolve missing defaults without a model turn."""
    from native_codex import Rpc, NativeError
    process = None
    try:
        process = subprocess.Popen([codex, "app-server", "--listen", "stdio://"], cwd=project_root,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True)
        rpc = Rpc(process)
        rpc.call("initialize", {"clientInfo": {"name": "agent_factory_policy", "version": "0.1.0"},
                                "capabilities": {"experimentalApi": True}}, timeout=3)
        rpc.write({"method": "initialized"})
        response = rpc.call("config/read", {"cwd": project_root, "includeLayers": False}, timeout=3)
        settings = response.get("config", {})
        if not isinstance(settings, dict):
            raise PolicyError("policy_missing", "Codex effective configuration is unavailable")
        mode = sandbox or settings.get("sandbox_mode")
        selected_approval = approval or settings.get("approval_policy")
        if mode is None or selected_approval is None or settings.get("default_permissions") or settings.get("permissions"):
            return _native_selected_policy(rpc, project_root, sandbox, approval)
        policy = {"type": mode}
        if mode == "workspace-write":
            policy.update(settings.get("sandbox_workspace_write") or {})
            policy["writable_roots"] = [*policy.get("writable_roots", []), project_root]
        return normalize({"schemaVersion": 1, "sandboxPolicy": policy, "approvalPolicy": selected_approval})
    except (OSError, NativeError) as error:
        raise PolicyError("policy_missing", "could not read Codex permissions; provide explicit execution policy") from error
    finally:
        if process is not None:
            if process.stdin:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            if process.stdout:
                process.stdout.close()


def add_policy_arguments(parser):
    parser.add_argument("--sandbox", choices=SANDBOXES, default=None)
    parser.add_argument("--execution-policy-file", type=Path)
    parser.add_argument("--approval-policy", choices=APPROVALS)
    parser.add_argument("--network-access", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--writable-root", action="append", default=None)


def has_explicit_policy(args):
    """A full policy file or sandbox/approval pair authorizes a next-run selection."""
    return bool(getattr(args, "execution_policy_file", None)) or (
        getattr(args, "sandbox", None) is not None and getattr(args, "approval_policy", None) is not None
    )


def resolve(args, project_root, *, fallback_policy=None, allow_session_change=False):
    project_root = _path(project_root)
    parent = None
    snapshot = os.environ.get(SNAPSHOT_ENV)
    thread = os.environ.get("CODEX_THREAD_ID")
    if snapshot is not None:
        if len(snapshot.encode()) > MAX_POLICY_BYTES:
            raise PolicyError("policy_invalid", "parent snapshot exceeds 1 MiB")
        parent = normalize(_json(snapshot))
        _managed_parent(parent, project_root)
    elif os.environ.get(PARENT_STATE_ENV):
        raise PolicyError("policy_missing", "managed parent state requires its policy snapshot")
    elif thread:
        parent = _rollout_policy(thread)
    policy_file = getattr(args, "execution_policy_file", None)
    selected = normalize(_read(policy_file)) if policy_file else parent
    if parent is not None and selected != parent:
        raise PolicyError("policy_parent_mismatch", "explicit policy differs from inherited parent permissions")
    changing_session = allow_session_change and has_explicit_policy(args)
    if fallback_policy is not None and not changing_session:
        fallback = normalize(fallback_policy)
        if selected is not None and selected != fallback:
            raise PolicyError("policy_parent_mismatch", "saved execution policy differs from parent or explicit policy")
        selected = selected or fallback
    sandbox = getattr(args, "sandbox", None)
    approval = getattr(args, "approval_policy", None)
    network = getattr(args, "network_access", None)
    roots = getattr(args, "writable_root", None)
    new_root = selected is None
    if selected is None:
        if sandbox is not None and approval is not None:
            raw = {"type": sandbox}
            if sandbox == "workspace-write":
                raw["writable_roots"] = [project_root, *(roots or [])]
            if network is not None:
                raw["network_access"] = network
            selected = normalize({"schemaVersion": 1, "sandboxPolicy": raw, "approvalPolicy": approval})
        else:
            selected = _configured_policy(getattr(args, "codex", None) or "codex", project_root,
                                          sandbox=sandbox, approval=approval)
    if new_root and (network is not None or roots is not None):
        raw = dict(selected["sandboxPolicy"])
        if network is not None:
            raw["network_access"] = network
        if roots is not None:
            raw["writable_roots"] = [project_root, *roots]
        selected = normalize({**selected, "sandboxPolicy": raw})
    inherited = selected["sandboxPolicy"]
    if sandbox is not None and sandbox != inherited["type"] or approval is not None and approval != selected["approvalPolicy"]:
        raise PolicyError("policy_parent_mismatch", "explicit sandbox/approval differs from resolved policy")
    if network is not None and network != inherited["network_access"]:
        raise PolicyError("policy_parent_mismatch", "explicit network access differs from resolved policy")
    if roots is not None:
        requested = sorted(set([project_root, *(_path(root) for root in roots)]))
        if inherited["type"] != "workspace-write" or requested != inherited["writable_roots"]:
            raise PolicyError("policy_parent_mismatch", "explicit writable roots differ from resolved policy")
    if inherited["type"] == "workspace-write" and not any(Path(project_root).is_relative_to(root) for root in inherited["writable_roots"]):
        raise PolicyError("policy_parent_mismatch", "project is outside the inherited writable roots")
    return selected


def session_policy(session):
    if not isinstance(session, dict) or session.get("executionPolicy") is None:
        raise PolicyError("policy_missing", "legacy session requires an inherited or explicit policy upgrade")
    return normalize(session["executionPolicy"])


def config(policy, run_directory):
    policy = normalize(policy)
    directory = _path(run_directory)
    sandbox = policy["sandboxPolicy"]
    mode = sandbox["type"]
    result = {"approval_policy": policy["approvalPolicy"]}
    if mode == "read-only":
        result.update(permissions.config(directory, network=sandbox["network_access"]))
    else:
        result["sandbox_mode"] = mode
        if mode == "danger-full-access":
            result["default_permissions"] = ":danger-full-access"
        else:
            result["sandbox_workspace_write.writable_roots"] = sorted(set([*sandbox["writable_roots"], directory]))
            for key in ("network_access", "exclude_tmpdir_env_var", "exclude_slash_tmp"):
                result["sandbox_workspace_write." + key] = sandbox[key]
    result["shell_environment_policy.set." + SNAPSHOT_ENV] = json.dumps(policy, sort_keys=True)
    result["shell_environment_policy.set." + PARENT_STATE_ENV] = str(Path(directory) / "state.json")
    return result


def arguments(policy, run_directory):
    result = []
    for key, value in config(policy, run_directory).items():
        result.extend(["-c", key + "=" + permissions.toml(value)])
    return result


def command_params(policy, run_directory):
    """Select the same effective policy for model-free app-server command/exec."""
    policy = normalize(policy)
    sandbox = policy["sandboxPolicy"]
    if sandbox["type"] != "workspace-write":
        return {"permissionProfile": config(policy, run_directory)["default_permissions"]}
    return {"sandboxPolicy": {
        "type": "workspaceWrite",
        "writableRoots": sorted(set([*sandbox["writable_roots"], _path(run_directory)])),
        "networkAccess": sandbox["network_access"],
        "excludeTmpdirEnvVar": sandbox["exclude_tmpdir_env_var"],
        "excludeSlashTmp": sandbox["exclude_slash_tmp"],
    }}
