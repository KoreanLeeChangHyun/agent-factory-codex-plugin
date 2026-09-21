"""Runtime-owned source for Main's task-flow presentation and task-list submission."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

import task_binding
from runtime_errors import ContractError


def check_submission(read_json, parent_path, parent, document):
    """Check the full list against the owning Main run, never a caller snapshot path.

    Historical parents without the version marker remain compatible unless they have
    explicitly prepared announcements. Unparented CLI submissions retain their contract.
    """
    if parent is None:
        return
    state = read_json(parent_path)
    directory = parent_path.parent / "task-announcements"
    if not state.get("taskAnnouncementContract") and not directory.exists():
        return
    if (state.get("role") != "main" or state.get("agentId") != parent["agentId"]
            or state.get("runId") != parent["runId"]):
        raise ContractError("task_announcement_parent_invalid", "Task list must belong to the bound Main run")
    workflow_id = document.get("id") if isinstance(document, dict) else None
    if not isinstance(workflow_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", workflow_id):
        raise ContractError("task_announcement_workflow_invalid", "Submit the announced workflow ID")
    path = directory / workflow_id / "announcement.json"
    if not path.is_file():
        raise ContractError("task_announcement_required", f"Workflow {workflow_id!r} has no announcement in this Main run; use announce-tasks before dispatch")
    record = read_json(path)
    if (record.get("schemaVersion") != 1 or record.get("kind") != "task-announcement"
            or record.get("parentAgentId") != parent["agentId"] or record.get("parentRunId") != parent["runId"]
            or record.get("runtimeBinding") != state.get("runtimeBinding")):
        raise ContractError("task_announcement_binding_invalid", "Announcement does not belong to this runtime and Main run")
    expected = record.get("taskList")
    if not isinstance(expected, dict) or expected.get("id") != workflow_id or not expected.get("tasks"):
        raise ContractError("task_announcement_invalid", "Stored announcement is invalid")
    task_binding.resolve(expected, expected["tasks"][0]["id"], "0" * 64)
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(task, dict) and isinstance(task.get("id"), str) for task in tasks):
        raise ContractError("task_announcement_tasks_invalid", "Submit the complete structured announced task list")
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ContractError("task_announcement_duplicate", "Submitted task IDs contain duplicates")
    expected_ids = [task["id"] for task in expected["tasks"]]
    if len(ids) != len(expected_ids):
        raise ContractError("task_announcement_count_mismatch", f"Announced {len(expected_ids)} tasks but submitted {len(ids)}; tasks must not be omitted or merged")
    if set(ids) != set(expected_ids):
        raise ContractError("task_announcement_ids_mismatch", f"Task IDs differ: missing {sorted(set(expected_ids) - set(ids))}, unexpected {sorted(set(ids) - set(expected_ids))}")
    if ids != expected_ids:
        raise ContractError("task_announcement_order_mismatch", f"Submit tasks in announced order: {expected_ids}")
    if document.get("title") != expected.get("title"):
        raise ContractError("task_announcement_title_mismatch", "Workflow title differs from the announcement")
    for task, announced in zip(tasks, expected["tasks"]):
        for key in ("title", "description", "completionCriteria"):
            if task.get(key) != announced.get(key):
                raise ContractError("task_announcement_metadata_mismatch", f"Task {task['id']!r} field {key!r} differs from the announcement")


def task_flow(document):
    """Project immutable task metadata; execution status is added only after acceptance."""
    return {"id": document["id"], "title": document["title"], "tasks": [
        {**{key: task[key] for key in ("id", "title", "description", "completionCriteria")},
         "status": "pending"} for task in document["tasks"]]}


def prepare(runtime, args):
    root = runtime.resolve_project_root(args.project_root)
    parent = runtime.managed_parent_identity(root)
    if parent is None:
        raise ContractError("task_announcement_parent_required", "Task announcements require a managed Main run")
    parent_path = runtime.state_file(root, parent["agentId"], parent["runId"])
    # Use the same parent lock as child acceptance and conversation reset.
    with runtime.file_lock(runtime.agent_directory(root, parent["agentId"]) / ".dispatch.lock"):
        runtime.require_current_parent_conversation(root, parent)
        state = runtime.safe_read_json(parent_path)
        if state.get("role") != "main" or state.get("status") not in runtime.ACTIVE_STATES:
            raise ContractError("task_announcement_parent_invalid", "Only an active Main run may prepare a task announcement")
        source = runtime.safe_read_json(args.task_list_file)
        tasks = source.get("tasks") if isinstance(source, dict) else None
        first_id = tasks[0].get("id") if isinstance(tasks, list) and tasks and isinstance(tasks[0], dict) else None
        # Validate all metadata and ignore any caller-provided hashes.
        document, _ = task_binding.resolve(source, first_id, "0" * 64)
        requests = []
        for task in document["tasks"]:
            path = task.get("requestFile")
            if not isinstance(path, str) or not Path(path).is_absolute():
                raise ContractError("task_request_invalid", "Each announced task requires an absolute requestFile")
            content = runtime.safe_read_bytes(Path(path), runtime.MAX_REQUEST_BYTES)
            if not content.decode("utf-8").strip():
                raise ContractError("task_request_invalid", "Task requests must not be empty")
            requests.append(content)
            task["requestHash"] = hashlib.sha256(content).hexdigest()
        directory = parent_path.parent / "task-announcements" / document["id"]
        task_list_path = directory / "task-list.json"
        for index, task in enumerate(document["tasks"]):
            task["requestFile"] = str(directory / f"request-{index}.md")
        snapshot = {"schemaVersion": 1, "kind": "task-announcement",
                    "parentAgentId": parent["agentId"], "parentRunId": parent["runId"],
                    "runtimeBinding": copy.deepcopy(state["runtimeBinding"]),
                    "taskList": document}
        record_path = directory / "announcement.json"
        if record_path.exists():
            if runtime.safe_read_json(record_path) != snapshot:
                raise ContractError("task_announcement_conflict", "This Main run already announced different content for this workflow ID")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            for task, content in zip(document["tasks"], requests):
                runtime.atomic_write(Path(task["requestFile"]), content)
            runtime.atomic_write_json(task_list_path, document)
            # Publish provenance last, after every request and the submission source exist.
            runtime.atomic_write_json(record_path, snapshot)
        return {"schemaVersion": 1, "kind": "task-announcement",
                "parentAgentId": parent["agentId"], "parentRunId": parent["runId"],
                "announcementPath": str(record_path), "taskListFile": str(task_list_path),
                "taskId": document["tasks"][0]["id"],
                "requestFile": document["tasks"][0]["requestFile"],
                "taskFlow": task_flow(document)}
