"""Codex configuration discovery and canonical-policy translation."""
import json
import subprocess
from pathlib import Path
from . import permissions
from execution_policy import PolicyError, normalize, _path, session_policy, SNAPSHOT_ENV, PARENT_STATE_ENV

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

