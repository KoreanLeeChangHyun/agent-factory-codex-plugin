"""Projection of private managed run state into the stable public status shape."""

from __future__ import annotations

from typing import Any

def public_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "runId",
        "agentId",
        "role",
        "actor",
        "status",
        "decisionKind",
        "attempt",
        "startDisposition",
        "maxAttempts",
        "sessionId",
        "executionOptions",
        "taskMode",
        "taskBinding",
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
        "parentAgentId",
        "parentRunId",
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
    return public

