"""Immutable child decisions and exactly-once continuation intents.

Text is evidence, never permission. Responses bind the complete question hash
and task identity; the loop's existing dispatch ledger handles lost ACKs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from storage.errors import ContractError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def capture(runtime, state, child):
    current = state["currentChild"]
    text = runtime.safe_read_bytes(Path(child["resultPath"]), runtime.MAX_REQUEST_BYTES).decode("utf-8")
    binding = {"projectRoot": state["projectRoot"], "loopId": state["loopId"],
               "taskBinding": state["execution"]["taskBinding"], "agentId": current["agentId"],
               "runId": current["runId"], "requestHash": state["originalRequestHash"],
               "role": current["role"],
               "requestPath": child.get("requestPath", state["originalRequestPath"]),
               "policy": state["execution"].get("agentPermissions", {}).get(current["role"], {}),
               "workspacePath": state["execution"].get("taskWorkspacePath"),
               "kind": child.get("decisionKind") or "clarification",
               "scope": child.get("decisionScope"), "question": text}
    identity = "decision-" + digest(binding)[:24]
    decision = state.setdefault("decisions", {}).setdefault(identity, {
        "id": identity, "questionHash": digest(binding), **binding,
        "status": "pending", "createdAt": runtime.now()})
    state["pendingDecisionId"] = identity
    return decision


def accept(state, response, *, actor, reference, evidence):
    if actor != "human" or not reference.strip() or not evidence.strip():
        raise ContractError("decision_unauthorized", "An exact Human answer and authorization reference are required")
    decision = state.get("decisions", {}).get(response.get("decisionId"))
    if not decision or response.get("questionHash") != decision["questionHash"]:
        raise ContractError("decision_binding_invalid", "Decision identity or question changed; reload the exact question")
    if (response.get("taskId") != decision["taskBinding"]["taskId"]
            or response.get("runId") != decision["runId"] or response.get("loopId") != state["loopId"]
            or response.get("projectRoot") != state["projectRoot"]):
        raise ContractError("decision_binding_invalid", "Answer belongs to a different project, task, loop or child run")
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ContractError("decision_answer_required", "Provide the actual answer to this question")
    accepted = {"answer": answer, "authorizationReference": reference, "evidence": evidence}
    if decision.get("response"):
        if decision["response"] != accepted:
            raise ContractError("decision_response_conflict", "This decision already has a different answer")
        return decision, False
    if (state.get("pendingDecisionId") != decision["id"] or state.get("status") != "needs-human-decision"
            or (state.get("currentChild") or {}).get("runId") != decision["runId"] or state.get("pendingDispatch")):
        raise ContractError("decision_stale", "The Work run is no longer waiting for this decision")
    decision.update(response=accepted, status="answered")
    return decision, True
