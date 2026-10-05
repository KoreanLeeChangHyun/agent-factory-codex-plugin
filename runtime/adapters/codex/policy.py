"""Codex configuration discovery and canonical-policy translation."""
import json
import subprocess
from pathlib import Path
from execution.policy import PolicyError, normalize, _path, session_policy, SNAPSHOT_ENV, PARENT_STATE_ENV  # noqa: F401 - session_policy is re-exported; the native bridge calls it through this module
import hashlib
import os
import re
from execution.policy import _open_regular, _json
from tasks import orchestrator_guard


# Exact-run named permissions; never grant the read-only code root write access.
def permission_profile(run_directory, *, network=False):
    directory = Path(run_directory)
    if not directory.is_absolute() or '..' in directory.parts:
        raise ValueError('managed permission target must be absolute')
    name = 'agent_factory_run_' + hashlib.sha256(str(directory).encode()).hexdigest()[:24]
    policy = {'filesystem': {'/': 'read', str(directory): 'write'}, 'network': {'enabled': network}}
    return name, policy


def permission_config(run_directory, *, network=False):
    name, policy = permission_profile(run_directory, network=network)
    return {'default_permissions': name, 'permissions.' + name: policy}


def permission_toml(value):
    if isinstance(value, dict):
        return '{' + ', '.join(json.dumps(k) + '=' + permission_toml(v) for k, v in value.items()) + '}'
    return json.dumps(value)


def permission_arguments(run_directory, *, network=False):
    result = []
    for key, value in permission_config(run_directory, network=network).items():
        result.extend(['-c', key + '=' + permission_toml(value)])
    return result


# Read the invoking Codex session policy without widening its permissions.
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
    from .transport import Rpc, NativeError
    process = None
    try:
        process = subprocess.Popen([codex, "app-server", "--listen", "stdio://"], cwd=project_root,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, encoding="utf-8")
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


def config(policy, run_directory):
    policy = normalize(policy)
    directory = _path(run_directory)
    sandbox = policy["sandboxPolicy"]
    mode = sandbox["type"]
    result = {"approval_policy": policy["approvalPolicy"]}
    if mode == "read-only":
        result.update(permission_config(directory, network=sandbox["network_access"]))
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
        result.extend(["-c", key + "=" + permission_toml(value)])
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


# Orchestrator-mode Main and Work enforcement through one session-flag PreToolUse hook. Codex keeps a
# single trust hash for the session-flag hook key, so both roles carry this exact definition and the
# guard script picks its rules from the arming variable.
GUARD_MATCHER = "^(Bash|apply_patch|.*(spawn|resume)_agent.*)$"


def guard_hook_toml():
    handler = f'{{type="command", command={json.dumps(orchestrator_guard.HOOK_COMMAND)}, timeout=30}}'
    return f'hooks.PreToolUse=[{{matcher={json.dumps(GUARD_MATCHER)}, hooks=[{handler}]}}]'


def guard_environment(state, session=None):
    """Variables arming the guard for this run: orchestrate Main rules, Work rules or none."""
    if orchestrator_guard.orchestrating(state, session):
        return orchestrator_guard.environment(state)
    if orchestrator_guard.working(state, session):
        return dict(orchestrator_guard.WORK_ENVIRONMENT)
    return {}


def app_server(session, state):
    """App-server argv and environment; only orchestrate Main and Work runs carry the hook and its arming variable."""
    command = [session["codex"], "app-server", "--listen", "stdio://"]
    environment = dict(os.environ)
    environment.pop(orchestrator_guard.ENV, None)
    arming = guard_environment(state, session)
    if arming:
        command += ["-c", guard_hook_toml()]
        environment.update(arming)
    return command, environment


def guard_signature(state, session):
    return json.dumps(app_server({"codex": ""}, state)[0] + [json.dumps(guard_environment(state, session))])


def ensure_guard_trusted(rpc, cwd):
    """Codex runs session-flag hooks only when the user config trusts their exact hash.

    Trust exactly this hook definition (an additive hooks.state entry), then confirm it is active."""
    def ours():
        listing = rpc.call("hooks/list", {"cwds": [cwd]})
        for entry in listing.get("data", []):
            for hook in entry.get("hooks", []):
                if (hook.get("source") == "sessionFlags" and hook.get("eventName") == "preToolUse"
                        and hook.get("command") == orchestrator_guard.HOOK_COMMAND):
                    return hook
        return None
    hook = ours()
    if hook is None:
        raise RuntimeError("Codex did not load the Agent Factory guard hook")
    if hook.get("trustStatus") in ("trusted", "managed"):
        return
    rpc.call("config/value/write", {"keyPath": "hooks.state", "mergeStrategy": "upsert",
                                    "value": {hook["key"]: {"trusted_hash": hook["currentHash"]}}})
    hook = ours()
    if not hook or hook.get("trustStatus") not in ("trusted", "managed"):
        raise RuntimeError("Codex did not trust the Agent Factory guard hook; its Main and Work rules cannot be enforced")
