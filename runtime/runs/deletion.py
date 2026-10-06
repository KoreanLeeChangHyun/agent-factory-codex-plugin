"""Delete one explicitly selected Main agent's private runtime records."""
from __future__ import annotations

import contextlib
import shutil
import stat
from pathlib import Path

from storage.errors import ContractError
from tasks.history import ENDED


def require_ended(runtime, value):
    if value.get("status") not in ENDED or value.get("pendingDispatch") or value.get("stopPending"):
        raise ContractError("agent_delete_active", "Finish or stop active runs and workflows before deleting this agent")
    for key in ("workerIdentity", "codexIdentity"):
        identity = value.get(key)
        pid = value.get(key.replace("Identity", "Pid"))
        if identity is not None:
            if runtime.process_identity_status(identity) not in {"dead", "mismatch"}:
                raise ContractError("agent_delete_process", "An execution process is alive or its termination is uncertain")
        elif pid and runtime.pid_alive(pid):
            raise ContractError("agent_delete_process", "An execution process has not exited")
    if value.get("containment") and not runtime.containment_is_empty(value["containment"]):
        raise ContractError("agent_delete_process", "Execution containment has not exited")


def require_no_work_unit(value):
    worktree = value.get("worktree") or {}
    workspace = value.get("taskWorkspace") or {}
    if (worktree or workspace.get("mode") == "code" or value.get("taskWorkspaces")
            or value.get("mode") == "code"):
        raise ContractError("agent_delete_work_unit", "Work Unit chats and workspace recovery records must be preserved; this agent cannot be deleted")


def references(value, agent_id, run_ids, directory):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"agentId", "parentAgentId", "mainAgentId", "workAgentId", "verificationAgentId"} and item == agent_id:
                return True
            if key in {"verifiedWorkRunId", "workRunId", "verificationRunId", "latestWorkRunId", "latestVerificationRunId"} and isinstance(item, str) and item in run_ids:
                return True
            if references(item, agent_id, run_ids, directory):
                return True
    elif isinstance(value, list):
        return any(references(item, agent_id, run_ids, directory) for item in value)
    elif isinstance(value, str):
        path = Path(value)
        return path.is_absolute() and path.is_relative_to(directory)
    return False


def delete(runtime, args):
    if args.actor != "human" or not args.authorization_reference.strip():
        raise ContractError("agent_delete_authority", "Agent deletion requires the Human's exact sidebar selection")
    root = runtime.resolve_project_root(args.project_root)
    agents = runtime.agent_root(root, create=False)
    directory = runtime.agent_directory(root, args.agent)
    runtime.runtime_paths.inspect(directory, missing=True)
    with contextlib.ExitStack() as locks:
        # Submit and Work Unit operations take this lock before dispatch locks.
        locks.enter_context(runtime.file_lock(agents.parent / ".worktree.lock", blocking=False))
        if not directory.exists():
            return {"kind": "agent-deleted", "agentId": args.agent, "deletedRuns": [], "alreadyDeleted": True}
        locks.enter_context(runtime.file_lock(directory / ".dispatch.lock", blocking=False))
        locks.enter_context(runtime.file_lock(directory / ".session-state.lock", blocking=False))
        session = runtime.load_session(root, args.agent)
        if session.get("role") != "main":
            raise ContractError("agent_delete_owner", "Only a selected Main sidebar agent can be deleted")
        require_no_work_unit(session)
        if (session.get("goal") or {}).get("status") == "active":
            raise ContractError("agent_delete_active", "Pause the active Goal and finish its execution before deleting this agent")

        # Validate the entire bounded tree, including attachments and incomplete
        # runs, before deleting anything. Never traverse provider/session paths.
        for child in directory.rglob("*"):
            info = runtime.runtime_paths.inspect(child)
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ContractError("agent_delete_path", "Agent storage contains an unsafe filesystem entry")
        run_ids = set()
        for run in sorted((directory / "runs").glob("*")):
            if not run.is_dir():
                raise ContractError("agent_delete_incomplete", "Run storage is incomplete; inspect it before deletion")
            if not (run / "state.json").is_file():
                raise ContractError("agent_delete_incomplete", "An incomplete run has no termination evidence; inspect it before deletion")
            locks.enter_context(runtime.file_lock(run / ".state.lock", blocking=False))
            value = runtime.find_run(root, args.agent, run.name)
            require_ended(runtime, value)
            require_no_work_unit(value)
            run_ids.add(run.name)
        for loop in sorted((directory / "loops").glob("*")):
            if not (loop / "state.json").is_file():
                raise ContractError("agent_delete_incomplete", "An incomplete workflow must be inspected before deletion")
            locks.enter_context(runtime.file_lock(loop / ".driver.lock", blocking=False))
            locks.enter_context(runtime.file_lock(loop / ".loop.lock", blocking=False))
            value = runtime.safe_read_json(loop / "state.json")
            require_ended(runtime, value)
            require_no_work_unit(value)
        for workspace in directory.rglob("workspace-*.json"):
            require_no_work_unit(runtime.safe_read_json(workspace))
        for dispatch in (directory / "dispatches").glob("*.json"):
            value = runtime.safe_read_json(dispatch)
            if value.get("runId") not in run_ids:
                raise ContractError("agent_delete_incomplete", "An unresolved dispatch reservation must be inspected before deletion")

        # Other agents keep their sessions, runs and recovery authority. Refuse
        # deletion when they still reference this agent, including ended children.
        # The task-history API can remove ended task bindings separately.
        for other in sorted(agents.iterdir()):
            runtime.runtime_paths.inspect(other)
            if other == directory or not other.is_dir():
                continue
            candidates = [other / "session.json", *other.glob("runs/*/state.json"),
                          *other.glob("runs/*/children/*.json"), *other.glob("loops/*/state.json"),
                          *other.glob("loops/*/workspace-*.json"),
                          *other.glob("dispatches/*.json")]
            for path in candidates:
                runtime.runtime_paths.inspect(path, missing=True)
                if path.exists() and references(runtime.safe_read_json(path), args.agent, run_ids, directory):
                    raise ContractError("agent_delete_shared", "Another agent or child task still references this agent; finish or remove its task history first")
        # rmtree's errors propagate: partial filesystem failure is never success.
        shutil.rmtree(directory)
        return {"kind": "agent-deleted", "agentId": args.agent,
                "deletedRuns": [{"agentId": args.agent, "runId": run} for run in sorted(run_ids)]}
