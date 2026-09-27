"""Claude permission mapping and unrestricted host readiness check."""
import json
import subprocess
import sys
import uuid
import execution_policy
from runtime_errors import ContractError
from .capabilities import EFFORTS, EFFORT_ALIASES

# Nearest Claude permission mode for each Agent Factory sandbox type. Claude tool permissions are
# not an OS sandbox: network access is not confined and writable_roots only extend tool access.
PERMISSION_MODES = {"danger-full-access": "bypassPermissions", "workspace-write": "acceptEdits", "read-only": "dontAsk"}
POLICY_FOR_MODE = {"bypassPermissions": "danger-full-access", "acceptEdits": "workspace-write", "auto": "workspace-write"}


def validate(session, *, images=None):
    model = session.get("model")
    if model and (not isinstance(model, str) or not model.startswith("claude-") or any(c.isspace() for c in model)):
        raise ContractError("provider_model_mismatch", "Claude model must be a claude-* identifier")


def effort(value):
    if value in EFFORTS:
        return value
    return EFFORT_ALIASES.get(value)


def permission_arguments(session, working_directory):
    policy = execution_policy.session_policy(session)["sandboxPolicy"]
    arguments = ["--permission-mode", PERMISSION_MODES[policy["type"]], "--permission-prompts", "none"]
    if policy["type"] == "workspace-write":
        for root in policy.get("writable_roots", []):
            if str(root) != str(working_directory):
                arguments += ["--add-dir", str(root)]
    return arguments


def check(session, policy, working_directory, run_directory, request_path):
    validate({**session, "executionPolicy": policy})
    # This is an unsandboxed host readiness check, never sandbox evidence.
    from execution_canary import CANARY
    result = subprocess.run([sys.executable, "-I", "-c", CANARY, str(request_path), str(working_directory),
                             str(run_directory), ".agent-factory-preflight-" + uuid.uuid4().hex,
                             "danger-full-access"], capture_output=True, text=True, timeout=8)
    if result.returncode:
        raise ContractError("execution_preflight_failed", result.stderr[-4000:])
    return {**json.loads(result.stdout), "backend": "claude-host-unrestricted", "sandbox": "danger-full-access"}

