"""Resolve one execution policy for managed CLI/native children without widening it."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

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
    descriptor = os.open(filename, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
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


def role_policy(mode, inherited, project_root):
    """Resolve an explicit Human mode, or preserve the full inherited snapshot."""
    if mode == "cli-default":
        return inherited
    if mode not in ("workspace-write", "danger-full-access", "bypass"):
        raise PolicyError("policy_invalid", "invalid role permission mode")
    sandbox = {"type": "danger-full-access" if mode == "bypass" else mode}
    if mode == "workspace-write":
        sandbox["writable_roots"] = [str(project_root)]
    return normalize({"schemaVersion": 1, "sandboxPolicy": sandbox, "approvalPolicy": "never"})


def authorized_role_policy(role, snapshot, project_root):
    locator = os.environ.get(PARENT_STATE_ENV)
    if not locator or role not in ("work", "verification"):
        return None
    _managed_parent(snapshot, project_root)
    state = _read(Path(locator))
    mode = state.get("executionOptions", {}).get("agentPermissions", {}).get(role)
    if mode is None:
        return None
    return role_policy(mode, snapshot, project_root)


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
    working_root = _path(getattr(args, "execution_working_directory", project_root))
    parent = None
    snapshot = os.environ.get(SNAPSHOT_ENV)
    if snapshot is not None:
        if len(snapshot.encode()) > MAX_POLICY_BYTES:
            raise PolicyError("policy_invalid", "parent snapshot exceeds 1 MiB")
        parent = normalize(_json(snapshot))
        _managed_parent(parent, project_root)
    elif os.environ.get(PARENT_STATE_ENV):
        raise PolicyError("policy_missing", "managed parent state requires its policy snapshot")
    else:
        import adapters
        parent = adapters.inherited_host_policy()
    policy_file = getattr(args, "execution_policy_file", None)
    selected = normalize(_read(policy_file)) if policy_file else parent
    authorized = authorized_role_policy(getattr(args, "role", None), parent, project_root) if parent is not None else None
    if authorized is not None:
        from worktrees import relocate_policy
        authorized = relocate_policy(authorized, Path(project_root), Path(working_root))
    if authorized is not None and not policy_file:
        selected = authorized
    if authorized is not None and selected != authorized:
        raise PolicyError("policy_parent_mismatch", "explicit policy differs from captured role permissions")
    if parent is not None and selected != parent and selected != authorized:
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
                raw["writable_roots"] = [working_root, *(roots or [])]
            if network is not None:
                raw["network_access"] = network
            selected = normalize({"schemaVersion": 1, "sandboxPolicy": raw, "approvalPolicy": approval})
        else:
            import adapters
            selected = adapters.adapter(getattr(args, "provider", None) or "codex").discover_policy(
                args, working_root, sandbox=sandbox, approval=approval)
    if new_root and (network is not None or roots is not None):
        raw = dict(selected["sandboxPolicy"])
        if network is not None:
            raw["network_access"] = network
        if roots is not None:
            raw["writable_roots"] = [working_root, *roots]
        selected = normalize({**selected, "sandboxPolicy": raw})
    inherited = selected["sandboxPolicy"]
    if sandbox is not None and sandbox != inherited["type"] or approval is not None and approval != selected["approvalPolicy"]:
        raise PolicyError("policy_parent_mismatch", "explicit sandbox/approval differs from resolved policy")
    if network is not None and network != inherited["network_access"]:
        raise PolicyError("policy_parent_mismatch", "explicit network access differs from resolved policy")
    if roots is not None:
        requested = sorted(set([working_root, *(_path(root) for root in roots)]))
        if inherited["type"] != "workspace-write" or requested != inherited["writable_roots"]:
            raise PolicyError("policy_parent_mismatch", "explicit writable roots differ from resolved policy")
    if inherited["type"] == "workspace-write" and not any(Path(working_root).is_relative_to(root) for root in inherited["writable_roots"]):
        raise PolicyError("policy_parent_mismatch", "project is outside the inherited writable roots")
    return selected


def session_policy(session):
    if not isinstance(session, dict) or session.get("executionPolicy") is None:
        raise PolicyError("policy_missing", "legacy session requires an inherited or explicit policy upgrade")
    return normalize(session["executionPolicy"])


def _native_selected_policy(rpc, project_root, sandbox, approval):
    """Compatibility delegate for existing runtime consumers."""
    from adapters.codex import policy as provider_policy
    return provider_policy._native_selected_policy(rpc, project_root, sandbox, approval)


def _configured_policy(codex, project_root, *, sandbox=None, approval=None):
    """Compatibility delegate for existing runtime consumers."""
    from adapters.codex import policy as provider_policy
    return provider_policy._configured_policy(codex, project_root, sandbox=sandbox, approval=approval)


def config(policy, run_directory):
    """Compatibility delegate for existing runtime consumers."""
    from adapters.codex import policy as provider_policy
    return provider_policy.config(policy, run_directory)


def arguments(policy, run_directory):
    """Compatibility delegate for existing runtime consumers."""
    from adapters.codex import policy as provider_policy
    return provider_policy.arguments(policy, run_directory)


def command_params(policy, run_directory):
    """Compatibility delegate for existing runtime consumers."""
    from adapters.codex import policy as provider_policy
    return provider_policy.command_params(policy, run_directory)


def __getattr__(name):
    if name == "permissions":
        from adapters.codex import permissions
        return permissions
    raise AttributeError(name)


def _last_context(filename):
    """Compatibility delegate for Codex parent permission observations."""
    from adapters.codex import parent_policy
    return parent_policy._last_context(filename)


def _rollout_policy(thread_id):
    """Compatibility delegate for Codex parent permission observations."""
    from adapters.codex import parent_policy
    return parent_policy._rollout_policy(thread_id)
