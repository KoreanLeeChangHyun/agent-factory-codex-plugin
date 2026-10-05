"""Required task identity for delegated execution, independent of UI messages."""
from __future__ import annotations
import copy
import hashlib
import re
from storage.errors import ContractError


def validate(document, task_id, request_hash):
    def fail():
        raise ContractError("task_binding_invalid", "Provide a task list with a selected task ID, title, description, completionCriteria and matching requestHash")
    def text(value, limit):
        return isinstance(value, str) and bool(value.strip())
    def identifier(value):
        return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)
    if not isinstance(document, dict) or not identifier(document.get("id")) or not text(document.get("title"), 300):
        fail()
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        fail()
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not identifier(task.get("id")) or task["id"] in ids:
            fail()
        ids.add(task["id"])
        for key in ("workAgentId", "verificationAgentId"):
            if key in task and not identifier(task[key]):
                fail()
        if not all(text(task.get(key), limit) for key, limit in (("title", 300), ("description", 4000), ("completionCriteria", 4000))):
            fail()
        if "requestHash" in task and (not isinstance(task["requestHash"], str) or not re.fullmatch(r"[a-f0-9]{64}", task["requestHash"])):
            fail()
        if "workspace" in task and (not isinstance(task["workspace"], dict) or task["workspace"].get("mode") not in {"code", "shared", "read-only"}):
            fail()
    task = next((task for task in tasks if task["id"] == task_id), None)
    from contracts.preflight import validate_contract
    validate_contract(document)
    if task is None or task.get("requestHash") != request_hash:
        fail()
    return {"workflowId": document["id"], "workflowTitle": document["title"],
            "taskId": task["id"], **{key: task[key] for key in ("title", "description", "completionCriteria", "requestHash")},
            **{key: copy.deepcopy(task[key]) for key in ("workAgentId", "verificationAgentId", "workspace") if key in task}}


def resolve(document, task_id, request_hash):
    """Ignore caller hashes; bind the private snapshot to the captured request internally."""
    snapshot = copy.deepcopy(document)
    if isinstance(snapshot, dict) and isinstance(snapshot.get("tasks"), list):
        for task in snapshot["tasks"]:
            if isinstance(task, dict):
                task.pop("requestHash", None)
                if task.get("id") == task_id:
                    task["requestHash"] = request_hash
    return snapshot, validate(snapshot, task_id, request_hash)


def load(read_json, path, task_id, request_hash):
    if path is None or not task_id:
        raise ContractError("task_binding_required", "Delegated execution requires --task-list-file and --task-id before dispatch")
    return resolve(read_json(path), task_id, request_hash)[1]


def brief_document(request):
    """A single-task list derived from an orchestrator brief.

    The title is the brief's first content line: label-only lines such as "# Brief" or
    "Goal:" are skipped, and a "Goal: text" line contributes its text."""
    text = request.strip()
    title = "Task"
    for line in text.splitlines():
        candidate = re.sub(r"^[#>*\-\s]+", "", line).strip()
        candidate = re.sub(r"^(?:brief|goal|objective|task)\s*[:\-]?\s*", "", candidate, flags=re.I).strip()
        if candidate and not re.fullmatch(r"(?:scope|done|report|constraints?)\s*:?", candidate, flags=re.I):
            title = candidate[:120]
            break
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return {"id": f"brief-{digest}", "title": title, "brief": True, "tasks": [
        {"id": f"task-{digest}", "title": title, "description": text[:4000],
         "completionCriteria": "The brief's stated result is produced and its own checks pass."}]}
