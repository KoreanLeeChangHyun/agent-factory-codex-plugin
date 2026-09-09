"""Exercise the selected local execution policy without calling a model/provider."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import execution_policy

TIMEOUT = 8


class PreflightError(ValueError):
    code = "execution_preflight_failed"


# argv carries paths and expectations; no shell interpolation or project code.
CANARY = r'''
import errno,json,os,sys
from pathlib import Path
request,project,run,marker,mode=sys.argv[1:]
with open(request,'rb') as stream:
    stream.read(1)
with os.scandir(project) as entries:
    next(entries,None)

def write_canary(directory):
    path=Path(directory)/marker
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        os.write(descriptor,b'agent-factory-preflight\n')
    finally:
        os.close(descriptor)
        path.unlink()

write_canary(run)
try:
    write_canary(project)
    project_write='allowed'
except OSError as error:
    if error.errno not in (errno.EACCES,errno.EPERM,errno.EROFS):
        raise
    project_write='denied'
expected='denied' if mode=='read-only' else 'allowed'
if project_write!=expected:
    raise RuntimeError('project write policy mismatch: expected '+expected+', observed '+project_write)
print(json.dumps({'schemaVersion':1,'passed':True,'checks':{
    'requestRead':True,'projectDirectoryRead':True,'runWrite':True,'projectWrite':project_write}}))
'''


def _native_command(codex, policy, directory, project, canary):
    from native_codex import Rpc, NativeError
    deadline = time.monotonic() + TIMEOUT - 1
    process = None
    rpc = None
    try:
        process = subprocess.Popen([str(codex), "app-server", "--listen", "stdio://",
                                    *execution_policy.arguments(policy, directory)], cwd=project,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, start_new_session=True)
        rpc = Rpc(process)
        rpc.call("initialize", {"clientInfo": {"name": "agent_factory_preflight", "version": "0.1.0"},
                                "capabilities": {"experimentalApi": True}}, timeout=min(3, max(0.01, deadline - time.monotonic())))
        rpc.write({"method": "initialized"})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PreflightError("execution preflight timed out")
        result = rpc.call("command/exec", {"command": canary, "cwd": project,
                         **execution_policy.command_params(policy, directory),
                         "timeoutMs": max(1, int((remaining - 0.1) * 1000)), "outputBytesCap": 8192}, timeout=remaining)
        if not isinstance(result, dict) or type(result.get("exitCode")) is not int:
            raise PreflightError("Codex command preflight returned invalid evidence")
        return result["exitCode"], result.get("stdout", ""), result.get("stderr", "")
    except NativeError as error:
        raise PreflightError(f"selected Codex execution policy failed preflight: {error}") from error
    finally:
        if process is not None:
            if process.stdin:
                process.stdin.close()
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=0.5)
            if rpc is not None:
                rpc.reader.join(timeout=0.1)
            if process.stdout:
                process.stdout.close()


def check(codex, policy, project_root, run_directory, request_path):
    policy = execution_policy.normalize(policy)
    project = execution_policy._path(project_root)
    directory = execution_policy._path(run_directory)
    request = execution_policy._path(request_path)
    if not Path(request).is_relative_to(directory):
        raise PreflightError("preflight request must belong to the exact run directory")
    mode = policy["sandboxPolicy"]["type"]
    marker = ".agent-factory-preflight-" + uuid.uuid4().hex
    canary = [sys.executable, "-I", "-c", CANARY, request, project, directory, marker, mode]
    try:
        # Every mode exercises the selected Codex configuration and its actual
        # command sandbox, without a model turn or a second policy resolver.
        returncode, stdout, stderr = _native_command(codex, policy, directory, project, canary)
        if returncode:
            detail = (stderr or stdout or "no diagnostic")[-4000:].strip()
            raise PreflightError(f"selected execution policy failed preflight: {detail}")
        try:
            result = json.loads(stdout)
        except (ValueError, TypeError) as error:
            raise PreflightError("execution preflight returned invalid evidence") from error
        expected = {"requestRead": True, "projectDirectoryRead": True, "runWrite": True,
                    "projectWrite": "denied" if mode == "read-only" else "allowed"}
        if (not isinstance(result, dict) or result.get("schemaVersion") != 1
                or result.get("passed") is not True or result.get("checks") != expected):
            raise PreflightError("execution preflight did not prove the selected policy")
        return {**result, "backend": "codex-command-exec",
                "sandbox": mode}
    except OSError as error:
        raise PreflightError(f"execution preflight could not start: {error}") from error
