"""Physical deletion of one ended task's runtime history, retaining shared sessions."""
from __future__ import annotations

import copy
import contextlib
import re
import shutil
from pathlib import Path

from storage.errors import ContractError

ENDED = {"completed", "failed", "cancelled", "runtime-error"}
TASK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def delete(runtime, args):
    """The Host supplies the owning Main and exact workflow/task from the trash click.

    All revisions of this tuple are removed. No caller-supplied filesystem paths
    are accepted. Locks and process checks precede any destructive change.
    """
    if args.actor != "human" or not args.authorization_reference:
        raise ContractError("task_delete_authority", "Task deletion requires the Human's exact trash selection")
    root = runtime.resolve_project_root(args.project_root)
    for value in (args.workflow_id, args.task_id):
        if not TASK_ID.fullmatch(value):
            raise ContractError("task_delete_identity", "Invalid workflow or task identifier")
    main = runtime.agent_directory(root, args.main_agent)
    runtime.runtime_paths.inspect(main)
    if runtime.safe_read_json(main / "session.json").get("role") != "main":
        raise ContractError("task_delete_owner", "Task history must belong to a Main conversation")
    agents = runtime.agent_root(root)
    with contextlib.ExitStack() as locks:
        # Match submit's order; also excludes Work Unit integration and new dispatch.
        locks.enter_context(runtime.file_lock(agents.parent / ".worktree.lock", blocking=False))
        locks.enter_context(runtime.file_lock(main / ".dispatch.lock", blocking=False))
        runs, loops = [], []
        for agent in sorted(agents.iterdir()):
            runtime.runtime_paths.inspect(agent)
            if not agent.is_dir():
                continue
            for path in sorted((agent / "runs").glob("*/state.json")):
                runtime.runtime_paths.inspect(path)
                state = runtime.safe_read_json(path)
                binding = state.get("taskBinding") or {}
                if (state.get("parentAgentId") == args.main_agent
                        and binding.get("workflowId") == args.workflow_id
                        and binding.get("taskId") == args.task_id):
                    runtime.find_run(root, agent.name, path.parent.name)
                    if state.get("role") not in {"work", "verification"}:
                        raise ContractError("task_delete_owner", "Refusing to delete a shared Main run")
                    runs.append((path, state))
            for path in sorted((agent / "loops").glob("*/state.json")):
                runtime.runtime_paths.inspect(path)
                state = runtime.safe_read_json(path)
                workflow = state.get("workflow") or {}
                parent = Path(state.get("parentStatePath") or "/")
                if (parent.parent.parent == main / "runs"
                        and workflow.get("id") == args.workflow_id
                        and any(task.get("id") == args.task_id for task in workflow.get("tasks", []))):
                    loops.append((path, state))
        if not runs and not loops:
            raise ContractError("task_delete_missing", "Task no longer exists; refresh its history")
        for agent in sorted({path.parent.parent.parent for path, _ in runs}):
            locks.enter_context(runtime.file_lock(agent / ".dispatch.lock", blocking=False))
        for path, state in loops:
            # An active driver may keep running a different task. Only remove a
            # prior task, under its transition lock, without touching its owner.
            if state.get("status") != "active":
                locks.enter_context(runtime.file_lock(path.parent / ".driver.lock", blocking=False))
            locks.enter_context(runtime.file_lock(path.parent / ".loop.lock", blocking=False))
            workflow = state["workflow"]
            selected_index = next(index for index, task in enumerate(workflow["tasks"]) if task["id"] == args.task_id)
            prior_ended = (state.get("status") == "active" and selected_index < workflow.get("index", 0)
                           and workflow["tasks"][selected_index].get("workStatus") in ENDED
                           and (state.get("execution", {}).get("taskMode") in {"work", "plan-work"}
                                or workflow["tasks"][selected_index].get("workStatus") != "completed"
                                or workflow["tasks"][selected_index].get("verificationStatus") in ENDED))
            if runtime.safe_read_json(path) != state or (state.get("status") not in ENDED and not prior_ended):
                raise ContractError("task_delete_active", "Finish the workflow before deleting its task history")
        closed_runs = set()
        for _, state in loops:
            if state.get("status") in ENDED:
                task = next(task for task in state["workflow"]["tasks"] if task["id"] == args.task_id)
                for stage in ("work", "verification"):
                    closed_runs.add((task.get(stage + "AgentId", state.get(stage + "AgentId")), task.get(stage + "RunId")))
        for path, state in runs:
            locks.enter_context(runtime.file_lock(path.parent / ".state.lock", blocking=False))
            fresh = runtime.safe_read_json(path)
            ended = fresh.get("status") in ENDED or (fresh.get("status") == "needs-human-decision"
                and (fresh.get("agentId"), fresh.get("runId")) in closed_runs)
            if fresh != state or not ended:
                raise ContractError("task_delete_active", "Finish or stop the task before deleting its history")
            for key in ("workerIdentity", "codexIdentity"):
                identity = state.get(key)
                pid = state.get(key.replace("Identity", "Pid"))
                if identity is not None:
                    if runtime.process_identity_status(identity) not in {"dead", "mismatch"}:
                        raise ContractError("task_delete_process", "Task process is still alive or its termination is uncertain")
                elif pid and runtime.pid_alive(pid):
                    raise ContractError("task_delete_process", "Task process has not exited")
            if state.get("containment") and not runtime.containment_is_empty(state["containment"]):
                raise ContractError("task_delete_process", "Task containment has not exited")

        removed = {(state["agentId"], state["runId"]) for _, state in runs}
        writes, byte_writes, files, directories = {}, {}, set(), set()
        for path, state in runs:
            directories.add(path.parent)
            # Dispatch receipts/reservations are task-owned only when they resolve
            # to this run or the exact task binding, never by Agent name alone.
            for dispatch in (path.parent.parent.parent / "dispatches").glob("*.json"):
                runtime.runtime_paths.inspect(dispatch)
                value = runtime.safe_read_json(dispatch)
                binding = (value.get("dispatchTuple") or {}).get("taskBinding") or {}
                if (value.get("runId") == state["runId"] or
                        (binding.get("workflowId") == args.workflow_id and binding.get("taskId") == args.task_id
                         and (value.get("dispatchTuple") or {}).get("parentAgentId") == args.main_agent)):
                    files.add(dispatch)
        # A different task must not lose a run it still references (for example
        # a standalone verifier of a historical Work result).
        removed_ids = {run for _, run in removed}
        for agent in sorted(agents.iterdir()):
            if not agent.is_dir():
                continue
            for path in (agent / "runs").glob("*/state.json"):
                state = runtime.safe_read_json(path)
                if (state.get("agentId"), state.get("runId")) not in removed and state.get("verifiedWorkRunId") in removed_ids:
                    raise ContractError("task_delete_shared_run", "Another task still references this Work result")
        for parent in (main / "runs").glob("*"):
            runtime.runtime_paths.inspect(parent)
            for reference in (parent / "children").glob("*.json"):
                runtime.runtime_paths.inspect(reference)
                value = runtime.safe_read_json(reference)
                if (value.get("agentId"), value.get("runId")) in removed:
                    candidates = []
                    for surviving_path in (runtime.agent_directory(root, value["agentId"]) / "runs").glob("*/state.json"):
                        surviving = runtime.safe_read_json(surviving_path)
                        if ((surviving.get("agentId"), surviving.get("runId")) not in removed
                                and surviving.get("parentAgentId") == args.main_agent
                                and surviving.get("parentRunId") == parent.name):
                            candidates.append(surviving)
                    if candidates:
                        latest = max(candidates, key=lambda item: (item.get("acceptedAt", ""), item["runId"]))
                        writes[reference] = {**value, "runId": latest["runId"], "role": latest["role"]}
                    else:
                        files.add(reference)
            announcement = parent / "task-announcements" / args.workflow_id
            if announcement.exists():
                runtime.runtime_paths.inspect(announcement)
                prune_announcement(runtime, announcement, args.task_id, writes, files, directories)
        for path, state in loops:
            tasks = state["workflow"]["tasks"]
            remaining = [task for task in tasks if task["id"] != args.task_id]
            for workspace in path.parent.glob("workspace-*.json"):
                runtime.runtime_paths.inspect(workspace)
                value = runtime.safe_read_json(workspace)
                if value.get("mode") != "code" and selected_reference(value, removed, args.workflow_id, args.task_id):
                    files.add(workspace)
            if not remaining:
                # Workspace bindings are the recovery authority for retained
                # branches. Keep those exact records even when history is gone.
                if state.get("taskWorkspaces"):
                    writes[path] = {key: state[key] for key in ("schemaVersion", "loopId", "status", "phase", "projectRoot", "statePath", "taskWorkspaces") if key in state}
                    for child in path.parent.iterdir():
                        if child == path or child.name.startswith("workspace-") or child.name.endswith(".lock"):
                            continue
                        (directories if child.is_dir() else files).add(child)
                else:
                    directories.add(path.parent)
                continue
            replacement = copy.deepcopy(state)
            replacement["workflow"]["tasks"] = remaining
            replacement["workflow"]["index"] = min(sum(task["id"] != args.task_id for task in tasks[:state["workflow"].get("index", 0)]), len(remaining) - 1)
            replacement = prune_references(replacement, removed, args.workflow_id, args.task_id)
            # Recovery metadata is retained independently of task history.
            if "taskWorkspaces" in state:
                replacement["taskWorkspaces"] = state["taskWorkspaces"]
            replacement["stateRevision"] = state.get("stateRevision", 0) + 1
            writes[path] = replacement
            task_list = path.parent / "task-list.json"
            if task_list.exists():
                value = runtime.safe_read_json(task_list)
                value["tasks"] = [task for task in value["tasks"] if task["id"] != args.task_id]
                writes[task_list] = value
            for task in tasks:
                if task["id"] == args.task_id:
                    request = Path(task.get("requestPath") or "/")
                    if request.parent == path.parent:
                        files.add(request)
            if tasks[0]["id"] == args.task_id:
                files.add(path.parent / "original-request.md")
            if Path(state.get("originalRequestPath") or "/") in files:
                for key in ("originalRequestPath", "originalRequestHash"):
                    replacement.pop(key, None)
            for view_path in [path.parent / "progress-state.json", *sorted((path.parent / "progress-history").glob("*.json"))]:
                if view_path.exists():
                    runtime.runtime_paths.inspect(view_path)
                    view = runtime.safe_read_json(view_path)
                    view["tasks"] = [task for task in view.get("tasks", []) if task.get("id") != args.task_id]
                    writes[view_path] = prune_references(view, removed, args.workflow_id, args.task_id)
            markdown = path.parent / "progress.md"
            if markdown.exists():
                from tasks import progress
                current = progress.snapshot(replacement)
                writes[path.parent / "progress-state.json"] = current
                if (path.parent / "progress-history").is_dir():
                    writes[path.parent / "progress-history" / f"revision-{current['stateRevision']:08d}.json"] = current
                byte_writes[markdown] = progress.render(current).encode("utf-8")

        # Never follow a link, including links buried in a run's attachments.
        for directory in directories:
            runtime.runtime_paths.inspect(directory)
            for child in directory.rglob("*"):
                runtime.runtime_paths.inspect(child)
        for file in files | set(writes) | set(byte_writes):
            runtime.runtime_paths.inspect(file, missing=True)
        # Persist shared-record pruning before unlinking private records. Any error
        # is propagated; the Host must not acknowledge success on partial failure.
        for path, value in writes.items():
            runtime.atomic_write_json(path, value)
        for path, value in byte_writes.items():
            runtime.atomic_write(path, value)
        for file in sorted(files):
            if not any(file.is_relative_to(directory) for directory in directories):
                file.unlink(missing_ok=True)
        for directory in sorted(directories):
            shutil.rmtree(directory)
        return {"kind": "task-history-deleted", "mainAgentId": args.main_agent,
                "workflowId": args.workflow_id, "taskId": args.task_id,
                "deletedRuns": [{"agentId": agent, "runId": run} for agent, run in sorted(removed)]}


def prune_references(value, removed, workflow, task):
    if isinstance(value, list):
        return [prune_references(item, removed, workflow, task) for item in value if not selected_reference(item, removed, workflow, task)]
    if isinstance(value, dict):
        return {key: prune_references(item, removed, workflow, task) for key, item in value.items()
                if not selected_reference(item, removed, workflow, task)
                and not (key in {"latestWorkRunId", "latestVerificationRunId", "workRunId", "verificationRunId"}
                         and item in {run for _, run in removed})}
    return value


def selected_reference(value, removed, workflow, task):
    return isinstance(value, dict) and ((value.get("agentId"), value.get("runId")) in removed
        or (value.get("workflowId") == workflow and value.get("taskId") == task)
        or ((value.get("taskBinding") or {}).get("workflowId") == workflow
            and (value.get("taskBinding") or {}).get("taskId") == task))


def prune_announcement(runtime, directory, task_id, writes, files, directories):
    path = directory / "task-list.json"
    value = runtime.safe_read_json(path)
    tasks = value.get("tasks", [])
    if not any(task.get("id") == task_id for task in tasks):
        return
    remaining = [task for task in tasks if task.get("id") != task_id]
    if not remaining:
        directories.add(directory)
        return
    value["tasks"] = remaining
    writes[path] = value
    record_path = directory / "announcement.json"
    record = runtime.safe_read_json(record_path)
    record["taskList"] = value
    writes[record_path] = record
    for task in tasks:
        if task.get("id") == task_id:
            request = Path(task.get("requestFile") or "/")
            if request.parent == directory:
                files.add(request)
