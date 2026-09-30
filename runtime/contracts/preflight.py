"""Check declared contract write requirements before accepting a task list."""
from pathlib import PurePosixPath

from storage.errors import ContractError


def validate_contract(document):
    contract = document.get("contract")
    if contract is None:
        return  # Historical task lists did not carry structured contract scope.

    def fail(message):
        raise ContractError("contract_scope_invalid", message)

    def path(value):
        if not isinstance(value, str) or not value or "\\" in value:
            fail("Contract paths must be nonempty project-relative paths")
        parsed = PurePosixPath(value)
        if parsed.is_absolute() or ".." in parsed.parts or str(parsed) != value:
            fail("Contract paths must be normalized project-relative paths")
        return value

    if not isinstance(contract, dict) or not isinstance(contract.get("id"), str) or not contract["id"]:
        fail("A structured contract requires its ID")
    if type(contract.get("version")) is not int or contract["version"] < 1:
        fail("A structured contract requires a positive integer version")
    progress = contract.get("progress")
    if not isinstance(progress, dict) or progress.get("owner") != "main":
        fail("Main must own the shared contract progress record")
    progress_path = path(progress.get("path"))
    legacy_path = f"docs/progress/{contract['id']}/progress.md"
    contract_path = f"docs/progress/{contract['id']}/contract-v{contract['version']}.md"
    if progress_path not in {legacy_path, contract_path}:
        fail("Progress path must match the contract ID and version")
    operations = contract.get("fileOperations")
    if not isinstance(operations, list):
        fail("Declare the contract file operations")
    task_ids = {task["id"] for task in document["tasks"]}
    allowed = set()
    for item in operations:
        if not isinstance(item, dict) or item.get("operation") not in {"add", "modify", "delete", "move"}:
            fail("Invalid contract file operation")
        target = path(item.get("path"))
        ids = item.get("taskIds")
        if not isinstance(ids, list) or not ids or any(task not in task_ids for task in ids):
            fail("File operations must identify existing tasks")
        destination = path(item.get("destination")) if item["operation"] == "move" else None
        allowed.update((task, item["operation"], target, destination) for task in ids)
    if not any(item.get("path") == progress_path and item.get("operation") == "modify" for item in operations):
        fail("Include Main's execution record update in the contract file operations")
    for task in document["tasks"]:
        required = task.get("requiredFileOperations")
        if not isinstance(required, list):
            fail(f"Task {task['id']} must declare its required file operations, including an empty list for read-only work")
        for item in required:
            if not isinstance(item, dict):
                fail("Invalid required file operation")
            target = path(item.get("path"))
            if target == progress_path:
                fail(f"Task {task['id']} must report progress in its result; Main owns {progress_path}")
            destination = path(item.get("destination")) if item.get("operation") == "move" else None
            if (task["id"], item.get("operation"), target, destination) not in allowed:
                fail(f"Task {task['id']} requires an operation outside its contract: {target}")
