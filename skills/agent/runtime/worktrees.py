"""Conversation-owned Git worktrees; project identity and history never move."""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from runtime_errors import ContractError


def git(root, *arguments, check=True, data=None):
    result = subprocess.run(["git", "-C", str(root), *arguments], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    if check and result.returncode:
        raise ContractError("worktree_git_failed", result.stderr.decode("utf-8", "replace").strip()
                            or result.stdout.decode("utf-8", "replace").strip())
    return result


def branch(root):
    result = git(root, "symbolic-ref", "--quiet", "HEAD", check=False)
    return result.stdout.decode().strip().removeprefix("refs/heads/") if result.returncode == 0 else None


def dirty(root):
    return bool(git(root, "status", "--porcelain", "--untracked-files=all").stdout)


def merge_pending(root):
    return git(root, "rev-parse", "--verify", "MERGE_HEAD", check=False).returncode == 0


def checked_path(session):
    root = Path(session["projectRoot"])
    value = session.get("worktree")
    if not value or value.get("phase") == "merged":
        return root
    path = Path(value["path"])
    if value.get("phase") == "creating":
        raise ContractError("worktree_incomplete", "Retry worktree creation before sending another request")
    if not path.is_dir() or path.is_symlink():
        raise ContractError("worktree_missing", "The conversation's worktree is missing; restore it before continuing")
    if git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout != git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout:
        raise ContractError("worktree_binding_invalid", "The worktree belongs to a different repository")
    if Path(git(path, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != path:
        raise ContractError("worktree_binding_invalid", "The saved directory is not the worktree root")
    if branch(path) != value["branch"]:
        raise ContractError("worktree_branch_changed", "Restore the conversation's worktree branch before continuing")
    return path


def status(session):
    value = session.get("worktree")
    path = Path(session["projectRoot"]) if not value or value.get("phase") == "merged" else Path(value["path"])
    available = path.is_dir()
    conflicts = git(path, "diff", "--name-only", "--diff-filter=U", "-z", check=False).stdout if available else b""
    return {"schemaVersion": 1, "kind": "worktree", "agentId": session["agentId"],
            "workspaceRoot": session["projectRoot"], "workingDirectory": str(path),
            "branch": branch(path) if available else None,
            "dirty": dirty(path) if available else False,
            "worktree": value, "conflicts": [os.fsdecode(p) for p in conflicts.split(b"\0") if p],
            "available": available}


def relocate_policy(policy, original, destination):
    if not policy or policy["sandboxPolicy"]["type"] != "workspace-write" or original == destination:
        return policy
    roots = policy["sandboxPolicy"]["writable_roots"]
    moved = [str(Path(destination) / Path(p).relative_to(original)) if Path(p).is_relative_to(original) else p for p in roots]
    if not any(Path(destination).is_relative_to(p) for p in moved):
        moved.append(str(destination))
    return {**policy, "sandboxPolicy": {**policy["sandboxPolicy"], "writable_roots": sorted(set(moved))}}


def inherit(session, parent):
    previous = session.get("worktree")
    original = Path(previous["path"]) if previous and previous["phase"] != "merged" else Path(session["projectRoot"])
    destination = checked_path(parent)
    result = {**session, "worktree": parent.get("worktree")}
    if session.get("executionPolicy"):
        result["executionPolicy"] = relocate_policy(session["executionPolicy"], original, destination)
    return result


def save(runtime, root, agent, value):
    directory = runtime.agent_directory(root, agent)
    def update(session):
        previous = session.get("worktree")
        old_path = root if not previous or previous["phase"] in ("creating", "merged") else Path(previous["path"])
        new_path = root if value["phase"] in ("creating", "merged") else Path(value["path"])
        if session.get("executionPolicy"):
            session["executionPolicy"] = relocate_policy(session["executionPolicy"], old_path, new_path)
        session.update({"worktree": value, "updatedAt": runtime.now()})
    runtime.update_json(directory / "session.json", directory / ".session-state.lock", update)


def copy_changes(root, path):
    # Copy, never stash/reset the source. The new worktree starts at the same HEAD.
    patch = git(root, "diff", "--binary", "HEAD", "--").stdout
    if patch:
        git(path, "apply", "--binary", "-", data=patch)
    files = git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0")
    for name in filter(None, files):
        relative = Path(os.fsdecode(name))
        source, target = root / relative, path / relative
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ContractError("worktree_copy_unsafe", "Untracked symlinks cannot be copied automatically")
        if target.exists() or target.is_symlink() or not target.resolve().is_relative_to(path):
            raise ContractError("worktree_copy_unsafe", "A copied file would overwrite an existing path")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def create(runtime, root, session, args):
    value = session.get("worktree")
    if value and value["phase"] != "merged":
        if value["phase"] != "creating":
            checked_path(session)
            return
        # Interrupted creation is recoverable without allocating a second branch.
        path = Path(value["path"])
        if path.exists():
            checked_path({**session, "worktree": {**value, "phase": "active"}})
            if dirty(path):
                raise ContractError("worktree_creation_incomplete", "Preserved worktree has changes; inspect them before retrying creation")
    else:
        if Path(git(root, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != root:
            raise ContractError("worktree_repository_root", "Open the Git repository root before creating a worktree")
        target = branch(root)
        if not target:
            raise ContractError("worktree_detached", "Select a branch in the workspace before creating a worktree")
        if merge_pending(root):
            raise ContractError("worktree_merge_pending", "Finish the workspace merge before creating a worktree")
        if dirty(root) and args.changes == "reject":
            raise ContractError("worktree_dirty", "Choose whether to keep changes in the workspace or copy them into the worktree")
        identity = "worktree-" + uuid.uuid4().hex
        location = runtime.runtime_paths.resolve(root)
        path = Path(args.path).expanduser().absolute() if args.path else Path(location["runtimeRoot"]) / "worktrees" / identity
        runtime.runtime_paths.inspect(path, missing=True)
        if path.exists() or path.is_relative_to(root):
            raise ContractError("worktree_path_invalid", "Choose a new directory outside the workspace")
        value = {"id": identity, "path": str(path), "branch": "agent-factory/" + identity,
                 "targetBranch": target, "baseCommit": git(root, "rev-parse", "HEAD").stdout.decode().strip(),
                 "phase": "creating", "changes": args.changes}
        save(runtime, root, session["agentId"], value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        git(root, "worktree", "add", "-b", value["branch"], str(path), value["baseCommit"])
    if (path / ".gitmodules").exists():
        git(path, "submodule", "update", "--init", "--recursive")
    # Binding is retained even when copying fails, so partial data is never lost.
    value["phase"] = "active"
    save(runtime, root, session["agentId"], value)
    if value["changes"] == "copy":
        if git(root, "rev-parse", "HEAD").stdout.decode().strip() != value["baseCommit"]:
            raise ContractError("worktree_source_changed", "Workspace HEAD changed during creation; original changes were preserved")
        copy_changes(root, path)


def merge(runtime, root, session):
    value = session.get("worktree")
    if not value or value["phase"] == "merged":
        return
    path = checked_path(session)
    if branch(root) != value["targetBranch"]:
        raise ContractError("worktree_target_changed", "Restore the original workspace branch before merging")
    if dirty(root) or merge_pending(root):
        raise ContractError("worktree_target_dirty", "Commit or move the workspace changes before merging; existing changes were preserved")
    if dirty(path) or merge_pending(path):
        raise ContractError("worktree_changes_pending", "Resolve conflicts and commit the worktree changes in this conversation, then retry Merge")
    # Conflict resolution happens in the isolated directory, never in the workspace.
    value = {**value, "phase": "merging"}
    save(runtime, root, session["agentId"], value)
    integrated = git(path, "merge", "--no-edit", "--no-autostash", "--no-overwrite-ignore", "--", "refs/heads/" + value["targetBranch"], check=False)
    if integrated.returncode:
        value["phase"] = "conflict" if merge_pending(path) else "active"
        save(runtime, root, session["agentId"], value)
        if value["phase"] != "conflict":
            raise ContractError("worktree_git_failed", integrated.stderr.decode("utf-8", "replace"))
        return
    # Recheck external changes before touching the workspace. Git additionally refuses
    # a non-fast-forward or overlapping dirty update.
    if branch(root) != value["targetBranch"] or dirty(root):
        raise ContractError("worktree_target_changed", "Workspace changed during merge; retry when it is ready")
    git(root, "merge", "--ff-only", "--no-autostash", "--no-overwrite-ignore", "--", "refs/heads/" + value["branch"])
    value["phase"] = "merged"
    save(runtime, root, session["agentId"], value)


def command(runtime, args):
    root = runtime.resolve_project_root(args.project_root)
    runtime.validate_id(args.agent, runtime.AGENT_ID, "agent_id")
    location = runtime.runtime_paths.resolve(root, create=True)
    directory = runtime.agent_directory(root, args.agent, create=True)
    with runtime.file_lock(Path(location["runtimeRoot"]) / ".worktree.lock"), runtime.file_lock(directory / ".dispatch.lock"):
        if not (directory / "session.json").exists():
            if args.action != "create":
                raise ContractError("session_missing", "Create a conversation first")
            options = runtime.parse_args(["submit", "--agent", args.agent, "--role", "main", "--codex", args.codex])
            options.resolved_execution_policy = runtime.resolve_execution_policy(args, root)
            options.resolved_human_approval_policy = args.human_approval_policy or "required"
            session = runtime.create_session(options, root)
        else:
            session = runtime.load_session(root, args.agent)
        if args.action == "status":
            runtime.emit(status(session))
            return 0
        if session["role"] != "main":
            raise ContractError("worktree_role_invalid", "Only Main conversations can change worktrees")
        runs = list(runtime.iter_run_states(root))
        if any(s.get("status") in runtime.ACTIVE_STATES and
               (s.get("agentId") == args.agent or s.get("parentAgentId") == args.agent or
                s.get("workingDirectory", str(root)) == str(root)) for s in runs):
            raise ContractError("session_busy", "Finish active runs before changing this conversation's working directory")
        if session.get("goalError") or (session.get("goal") or {}).get("status") == "active":
            raise ContractError("goal_active", "Pause the active Goal before changing working directories")
        if args.action == "create":
            create(runtime, root, session, args)
        else:
            merge(runtime, root, session)
        runtime.emit(status(runtime.load_session(root, args.agent)))
    return 0
