"""Claude host readiness check before a run (unsandboxed; never sandbox evidence)."""
from adapters.claude.policy import validate
from execution.canary import host_readiness


def check(session, policy, working_directory, run_directory, request_path):
    validate({**session, "executionPolicy": policy})
    return host_readiness(working_directory, run_directory, request_path, backend="claude-host-unrestricted")
