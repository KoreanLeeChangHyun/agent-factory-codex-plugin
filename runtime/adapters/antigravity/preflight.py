"""Antigravity host readiness check before a run (unsandboxed; never sandbox evidence)."""
import json
import subprocess
import sys
import uuid

from adapters.antigravity.policy import validate
from storage.errors import ContractError


def check(session, policy, working_directory, run_directory, request_path):
    validate({**session, "executionPolicy": policy})
    # This is an unsandboxed host readiness check, never sandbox evidence.
    from execution.canary import CANARY
    result = subprocess.run([sys.executable, "-I", "-c", CANARY, str(request_path), str(working_directory),
                             str(run_directory), ".agent-factory-preflight-" + uuid.uuid4().hex,
                             "danger-full-access"], capture_output=True, text=True, timeout=8)
    if result.returncode:
        raise ContractError("execution_preflight_failed", result.stderr[-4000:])
    return {**json.loads(result.stdout), "backend": "antigravity-host-unrestricted", "sandbox": "danger-full-access"}
