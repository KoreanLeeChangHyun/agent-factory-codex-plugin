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


def repositories(root):
    """Discover roots without following symlinks or recursing through a repository."""
    root = Path(root).resolve()
    found = []
    pending = [root]
    while pending:
        path = pending.pop()
        probe = git(path, "rev-parse", "--show-toplevel", check=False)
        if probe.returncode == 0:
            repo = Path(os.fsdecode(probe.stdout).strip()).resolve()
            if repo not in found:
                found.append(repo)
            continue
        try:
            pending.extend(p for p in path.iterdir() if p.is_dir() and not p.is_symlink() and p.name != ".git")
        except (PermissionError, FileNotFoundError):
            continue
    result = []
    for repo in sorted(found):
        branches = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/").stdout.decode().splitlines()
        remote = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False).stdout.decode().strip().removeprefix("refs/remotes/origin/")
        default = remote if remote in branches else next((b for b in ("main", "master", branch(repo)) if b in branches), None)
        result.append({"path": str(repo), "branches": branches, "defaultBranch": default})
    return result


def repository_root(session):
    return Path((session.get("worktree") or {}).get("repositoryRoot", session["projectRoot"]))


def checked_path(session):
    root = repository_root(session)
    value = session.get("worktree")
    if value and value.get("workUnit") and value.get("phase") == "merged":
        raise ContractError("work_unit_archived", "This Work Unit is read-only; create a new Work Unit")
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
    path = repository_root(session) if not value or value.get("phase") == "merged" else Path(value["path"])
    available = path.is_dir() and git(path, "rev-parse", "--is-inside-work-tree", check=False).returncode == 0
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
    if value and value.get("workUnit") and value["phase"] == "merged":
        raise ContractError("work_unit_archived", "This Work Unit is read-only; create a new Work Unit")
    project_root = root
    if value:
        root = Path(value.get("repositoryRoot", root))
    elif getattr(args, "name", None):
        selected = Path(args.repository or root).resolve()
        if str(selected) not in {r["path"] for r in repositories(root)}:
            raise ContractError("work_unit_repository", "Select a repository in this project")
        root = selected
        if args.changes == "copy" or args.path:
            raise ContractError("work_unit_options", "Work Units preserve source changes and use the managed project directory")
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
        target = (args.base or next((r["defaultBranch"] for r in repositories(root)), None)) if getattr(args, "name", None) else branch(root)
        if not target:
            raise ContractError("worktree_detached", "Select a branch in the workspace before creating a worktree")
        if merge_pending(root):
            raise ContractError("worktree_merge_pending", "Finish the workspace merge before creating a worktree")
        if dirty(root) and args.changes == "reject":
            raise ContractError("worktree_dirty", "Choose whether to keep changes in the workspace or copy them into the worktree")
        unit_branch = args.branch if getattr(args, "name", None) else None
        if getattr(args, "name", None):
            if not args.name.strip() or not unit_branch or git(root, "check-ref-format", "refs/heads/" + unit_branch, check=False).returncode:
                raise ContractError("work_unit_branch", "Enter a valid Work Unit name and Git branch name")
            if git(root, "show-ref", "--verify", "--quiet", "refs/heads/" + unit_branch, check=False).returncode == 0:
                raise ContractError("work_unit_branch_exists", "That branch already exists in this repository; enter a different name")
            git(root, "rev-parse", "--verify", "refs/heads/" + target)
        identity = "worktree-" + uuid.uuid4().hex
        location = runtime.runtime_paths.resolve(project_root)
        path = Path(args.path).expanduser().absolute() if args.path else Path(location["runtimeRoot"]) / "worktrees" / identity
        runtime.runtime_paths.inspect(path, missing=True)
        if path.exists() or path.is_relative_to(root):
            raise ContractError("worktree_path_invalid", "Choose a new directory outside the workspace")
        value = {"id": identity, "path": str(path), "branch": unit_branch or "agent-factory/" + identity,
                 "targetBranch": target, "baseCommit": git(root, "rev-parse", "refs/heads/" + target if unit_branch else "HEAD").stdout.decode().strip(),
                 "phase": "creating", "changes": args.changes}
        if unit_branch:
            value.update({"workUnit": True, "name": args.name.strip(), "repositoryRoot": str(root)})
        save(runtime, project_root, session["agentId"], value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        git(root, "worktree", "add", "-b", value["branch"], str(path), value["baseCommit"])
    if (path / ".gitmodules").exists():
        git(path, "submodule", "update", "--init", "--recursive")
    # Binding is retained even when copying fails, so partial data is never lost.
    value["phase"] = "active"
    save(runtime, project_root, session["agentId"], value)
    if value["changes"] == "copy":
        if git(root, "rev-parse", "HEAD").stdout.decode().strip() != value["baseCommit"]:
            raise ContractError("worktree_source_changed", "Workspace HEAD changed during creation; original changes were preserved")
        copy_changes(root, path)


def merge_unit(runtime, project_root, session, target=None):
    value = dict(session["worktree"])
    root = repository_root(session)
    if value["phase"] == "merged" and target and target != value["targetBranch"]:
        raise ContractError("work_unit_target", "Cleanup must use the completed merge target")
    target = target or value["targetBranch"]
    if target == value["branch"] or git(root, "show-ref", "--verify", "--quiet", "refs/heads/" + target, check=False).returncode:
        raise ContractError("work_unit_target", "Select an existing target branch other than the Work Unit branch")
    # Use the target's existing checkout when present. Never switch a dirty checkout.
    records = git(root, "worktree", "list", "--porcelain").stdout.decode().split("\n\n")
    destination = None
    for record in records:
        lines = record.splitlines()
        if "branch refs/heads/" + target in lines:
            destination = Path(next(line[9:] for line in lines if line.startswith("worktree ")))
    if destination is None:
        if dirty(root) or merge_pending(root):
            raise ContractError("worktree_target_dirty", "Commit or move the workspace changes before selecting another target")
        git(root, "switch", "--", target)
        destination = root
    if any(state.get("status") in runtime.ACTIVE_STATES and state.get("workingDirectory") == str(destination)
           for state in runtime.iter_run_states(project_root)):
        raise ContractError("session_busy", "Finish active runs in the merge target before merging or cleaning up")
    path = Path(value["path"])
    if value["phase"] != "merged":
        checked_path(session)
        if dirty(path) or merge_pending(path):
            raise ContractError("worktree_changes_pending", "Commit the Work Unit changes before merging")
        if dirty(destination) or merge_pending(destination):
            raise ContractError("worktree_target_dirty", "Finish changes or conflicts in the target checkout before merging")
        value.update({"phase": "merging", "targetBranch": target, "mergeDirectory": str(destination)})
        save(runtime, project_root, session["agentId"], value)
        result = git(destination, "merge", "--no-edit", "--no-squash", "--commit", "--no-autostash", "--no-overwrite-ignore", "--", "refs/heads/" + value["branch"], check=False)
        if result.returncode:
            value["phase"] = "conflict" if merge_pending(destination) else "active"
            save(runtime, project_root, session["agentId"], value)
            raise ContractError("work_unit_merge_failed", result.stderr.decode("utf-8", "replace") or "Resolve the merge in the target checkout, then retry")
        value["phase"] = "merged"
        save(runtime, project_root, session["agentId"], value)
    # Ignored files are unpreserved data too. Never use --force or delete a branch
    # whose tip was changed externally after the merge.
    if path.exists() and git(path, "status", "--porcelain", "--untracked-files=all", "--ignored").stdout:
        raise ContractError("work_unit_cleanup_pending", "Merge succeeded; cleanup paused because the worktree contains unpreserved files")
    if git(root, "merge-base", "--is-ancestor", "refs/heads/" + value["branch"], "refs/heads/" + target, check=False).returncode:
        raise ContractError("work_unit_cleanup_pending", "Merge succeeded; the work branch changed, so cleanup was paused")
    if path.exists():
        git(root, "worktree", "remove", str(path))
    git(root, "branch", "-d", "--", value["branch"])
    value["cleaned"] = True
    save(runtime, project_root, session["agentId"], value)


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
    if args.action == "repositories":
        runtime.emit({"schemaVersion": 1, "kind": "worktree-repositories", "repositories": repositories(root)})
        return 0
    directory = runtime.agent_directory(root, args.agent, create=True)
    with runtime.file_lock(Path(location["runtimeRoot"]) / ".worktree.lock"), runtime.file_lock(directory / ".dispatch.lock"):
        if not (directory / "session.json").exists():
            if args.action != "create":
                raise ContractError("session_missing", "Create a conversation first")
            options = runtime.parse_args(["submit", "--agent", args.agent, "--role", "main", "--codex", args.codex,
                                          "--claude", args.claude, *(["--model", args.model] if args.model else [])])
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
                s.get("workingDirectory", str(root)) in {str(root), str((session.get("worktree") or {}).get("path", root))}) for s in runs):
            raise ContractError("session_busy", "Finish active runs before changing this conversation's working directory")
        if session.get("goalError") or (session.get("goal") or {}).get("status") == "active":
            raise ContractError("goal_active", "Pause the active Goal before changing working directories")
        if args.action == "create":
            create(runtime, root, session, args)
        elif (session.get("worktree") or {}).get("workUnit"):
            if not (session.get("worktree") or {}).get("cleaned"):
                merge_unit(runtime, root, session, args.target)
        else:
            merge(runtime, root, session)
        runtime.emit(status(runtime.load_session(root, args.agent)))
    return 0
