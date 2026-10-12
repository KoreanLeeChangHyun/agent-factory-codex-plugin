"""Bound continuations: delta delivery with recovery only when session context changed."""
from pathlib import Path

from storage.errors import ContractError


def request(runtime, state, delta, *, agent_id, previous_run_id):
    binding = state["execution"]["taskBinding"]
    root = Path(state["projectRoot"])
    session_path = runtime.session_file(root, agent_id)
    session = runtime.safe_read_json(session_path) if session_path.exists() else {}
    previous = runtime.safe_read_json(runtime.state_file(root, agent_id, previous_run_id))
    previous_binding = previous.get("taskBinding") or (previous.get("dispatchTuple") or {}).get("taskBinding") or {}
    if previous_binding and any(previous_binding.get(key) != binding[key] for key in ("workflowId", "taskId")):
        raise ContractError("revision_binding_invalid", "The previous run belongs to a different accepted task")
    retained = bool(previous_binding and session.get("sessionId")
                    and session["sessionId"] == previous.get("sessionId"))
    header = (
        f"Continue the same accepted task: {binding['workflowId']} / {binding['taskId']}.\n"
        f"Original request reference: {state['originalRequestPath']}\n"
        f"Previous run: {previous_run_id}\n"
        "Preserve the original scope, completion criteria, required execution constraints and captured authority. "
        "This addition changes no permissions or task identity. Complete the whole accepted task, including this correction.\n"
    )
    workflow = state.get("workflow") or {}
    task = next((item for item in workflow.get("tasks", []) if item.get("id") == binding["taskId"]), {})
    if task.get("requestRevision") is not None:
        header += f"Base request revision: {task['requestRevision']}\n"
    previous_workspace = previous.get("taskWorkspace") or {}
    current_workspace = state.get("taskWorkspaces", {}).get(binding["taskId"]) or {}
    if previous_workspace.get("id") and previous_workspace.get("id") != current_workspace.get("id"):
        header += f"Previous Work Unit: {previous_workspace['id']} at {previous_workspace.get('path')}; its result and receipt remain preserved history.\n"
    if retained:
        header += "The same native session retains context; apply the delta below. Consult the original reference only if needed.\n"
    else:
        original = runtime.safe_read_bytes(Path(state["originalRequestPath"]), runtime.MAX_REQUEST_BYTES).decode("utf-8")
        header += (
            "Session context is unavailable or changed. Recover the accepted context below before applying the delta.\n"
            f"Previous result: {previous.get('resultPath')}\nPrevious receipt: {previous.get('receiptPath')}\n"
            f"Completion criteria: {binding['completionCriteria']}\n\n"
            f"[Original accepted request — recovery context]\n{original}\n[End recovery context]\n"
        )
        # Retain earlier corrections as references rather than silently dropping A-1 on A-2.
        for item in state.get("dispatchHistory", []):
            if item.get("taskId") == binding["taskId"] and item.get("role") == "work":
                header += f"Prior correction/result reference: {item['requestPath']} (run {item['runId']})\n"
    return header + "\n[Current delta]\n" + delta, "retained" if retained else "recovery"
