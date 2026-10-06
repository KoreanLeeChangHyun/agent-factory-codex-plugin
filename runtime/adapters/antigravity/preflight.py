"""Antigravity host readiness check before a run (unsandboxed; never sandbox evidence)."""
from adapters.antigravity.policy import validate
from execution.canary import host_readiness


def check(session, policy, working_directory, run_directory, request_path):
    validate({**session, "executionPolicy": policy})
    return host_readiness(working_directory, run_directory, request_path, backend="antigravity-host-unrestricted")
