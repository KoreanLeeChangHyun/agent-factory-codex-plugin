"""Read-only conductor view over accepted tasks and existing execution records.

This is a projection, never a scheduler or receipt validator. A run's reported
completion and the loop's processed outcome are deliberately separate facts.
"""
from __future__ import annotations

import copy
from pathlib import Path

from storage.errors import ContractError
from tasks import progress


def snapshot(state, read_run):
    """Return schema 1; read_run(agent_id, run_id) must use managed run lookup.

    Reads are sequential observations, not a transaction or a process-liveness
    check. References identify recorded artifacts; they do not certify that an
    artifact exists. Consumers must use the existing result/receipt read paths.
    Missing history stays unavailable rather than reverting to planned state.
    """
    workflow = state.get("workflow") or {}
    route = state.get("execution", {}).get("taskMode", "work-verification")
    parent = state.get("parentStatePath")
    owner = None
    if parent:
        path = Path(parent)
        owner = {"agentId": path.parent.parent.parent.name,
                 "runId": path.parent.name, "statePath": parent}
    rows = []
    for task in workflow.get("tasks", []):
        allocation = task.get("allocation")
        stages = {}
        for role in ("work", "verification"):
            agent = task.get(role + "AgentId", state.get(role + "AgentId"))
            run_id = task.get(role + "RunId")
            requested = role == "work" or route not in {"work", "plan-work"}
            stage = {"requested": requested, "agentId": agent, "runId": run_id,
                     "processedStatus": task.get(role + "Status"),
                     "observation": "not-dispatched" if not run_id else "unavailable",
                     "runStatus": None, "resultPath": None, "receiptPath": None}
            if run_id:
                try:
                    run = read_run(agent, run_id)
                    bound = run.get("taskBinding") or {}
                    if (run.get("agentId") != agent or run.get("runId") != run_id
                            or run.get("role") != role
                            or bound.get("workflowId") != workflow.get("id")
                            or bound.get("taskId") != task["id"]
                            or (owner and (run.get("parentAgentId"), run.get("parentRunId"))
                                != (owner["agentId"], owner["runId"]))):
                        raise ContractError("control_center_run_binding", "Run does not belong to this task and conductor")
                    stage.update(observation="recorded", runStatus=run.get("status"),
                                 observedAt=run.get("updatedAt", run.get("acceptedAt")),
                                 statePath=run.get("statePath"),
                                 startDisposition=run.get("startDisposition"),
                                 cancelRequested=run.get("cancelRequested", False),
                                 error=copy.deepcopy(run.get("error")),
                                 decisionKind=run.get("decisionKind"),
                                 decisionScope=run.get("decisionScope"))
                    if run.get("status") in {"completed", "failed", "cancelled", "runtime-error", "needs-human-decision"}:
                        stage.update(resultPath=run.get("resultPath"), receiptPath=run.get("receiptPath"))
                except (ContractError, OSError, ValueError) as error:
                    stage["error"] = {"code": getattr(error, "code", "run_unavailable"), "message": str(error)}
            if not requested:
                stage["disposition"] = "not-requested"
            elif role == "verification" and state.get("humanSkip") and task.get("workStatus") == "completed" and task.get("verificationStatus") != "completed":
                stage["disposition"] = "human-skipped"
            elif stage["observation"] == "recorded" and stage["runStatus"] == "completed" and stage["processedStatus"] == "completed":
                stage["disposition"] = "plan-completed" if route == "plan-work" else "processed-completed"
            elif run_id:
                stage["disposition"] = "dispatched"
            else:
                stage["disposition"] = "planned"
            stages[role] = stage
        rows.append({"id": task["id"], "title": task.get("title"),
                     "description": task.get("description"),
                     "completionCriteria": task.get("completionCriteria"),
                     "dependencies": copy.deepcopy((allocation or {}).get("dependencies", [])),
                     "allocation": copy.deepcopy(allocation), "assignedBy": copy.deepcopy(owner),
                     "stages": stages})
    return {"schemaVersion": 1, "kind": "control-center", "source": "runtime-records",
            "consistency": "sequential-observations", "loopId": state["loopId"],
            "statePath": state.get("statePath"), "stateRevision": state.get("stateRevision", 0),
            "observedAt": state.get("updatedAt"), "conductor": owner,
            "goal": {"workflowId": workflow.get("id"), "title": workflow.get("title"),
                     "requestPath": state.get("originalRequestPath"),
                     "requestHash": state.get("originalRequestHash")},
            "taskMode": route, "deliveryKind": "plan" if route == "plan-work" else "work",
            "progress": copy.deepcopy(progress.snapshot(state)), "tasks": rows,
            "pendingDispatch": copy.deepcopy(state.get("pendingDispatch")),
            "pendingDecision": copy.deepcopy((state.get("decisions") or {}).get(state.get("pendingDecisionId"))),
            "integrationWait": copy.deepcopy(state.get("integrationWait")),
            "lastVerificationDecision": state.get("lastVerificationDecision"),
            "pendingFindingIds": copy.deepcopy(state.get("pendingFindingIds", [])),
            "revisionCount": state.get("revisionCount", 0),
            "receiptRecovery": copy.deepcopy(state.get("receiptRecovery")),
            "completion": copy.deepcopy(state.get("completion")),
            "stopPending": state.get("stopPending", False),
            "humanSkip": copy.deepcopy(state.get("humanSkip"))}
