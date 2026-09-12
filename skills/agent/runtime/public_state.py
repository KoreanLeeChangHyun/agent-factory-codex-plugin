"""Projection of private managed run state into the stable public status shape."""

from __future__ import annotations

from pathlib import Path
from typing import Any

def public_state(state: dict[str, Any], runtime: Any) -> dict[str, Any]:
    keys = (
        "runId",
        "agentId",
        "role",
        "actor",
        "status",
        "attempt",
        "startDisposition",
        "maxAttempts",
        "sessionId",
        "executionOptions",
        "executionPolicy",
        "humanApprovalPolicy",
        "executionPreflight",
        "backend",
        "goal",
        "goalObservedAt",
        "goalError",
        "goalControl",
        "requestPath",
        "statePath",
        "resultPath",
        "receiptPath",
        "receiptSchemaPath",
        "receiptRequestHash",
        "capabilityBindingPath",
        "capabilityBindingHash",
        "verifiedWorkRunId",
        "dispatchId",
        "dispatchTuple",
        "eventsPath",
        "heartbeatPath",
        "acceptedAt",
        "startedAt",
        "finishedAt",
        "updatedAt",
        "workerPid",
        "workerIdentity",
        "containmentAttempt",
        "containment",
        "containmentLaunchDisposition",
        "codexPid",
        "codexIdentity",
        "lastCodexIdentity",
        "unread",
        "error",
    )
    public = {key: state.get(key) for key in keys if key in state}
    if state.get("role") not in {"work", "verification"}:
        public.pop("statePath", None)
    if state.get("cloudReporting"):
        public["reporting"] = runtime.cloud_reporting.status(
            runtime, runtime.runtime_paths.project_for(Path(state["statePath"])), state
        )
    return public

