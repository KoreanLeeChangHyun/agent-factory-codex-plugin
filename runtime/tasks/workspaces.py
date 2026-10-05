"""Task-owned Work Units and runtime-owned, recoverable local integration.

Plans are captured by Main before dispatch. Legacy/shared and research tasks do
not acquire Git authority merely because the runtime supports this module.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from execution import worktrees
from storage.errors import ContractError


def plan(root, value, selected_unit=None, isolation=False):
    if not isinstance(value, dict) or value.get("mode") not in {"code", "shared", "read-only"}:
        raise ContractError("task_workspace_invalid", "Select code, shared or read-only task workspace mode")
    if isolation and value["mode"] == "shared":
        # The Human's isolation toggle excludes the shared checkout for delegated Work.
        raise ContractError("task_workspace_invalid", "Work isolation is on; select code or read-only task workspace mode")
    if value["mode"] != "code":
        if value.get("repositories"):
            raise ContractError("task_workspace_invalid", "Only code tasks may select integration repositories")
        return {"mode": value["mode"]}
    selected = value.get("repositories")
    if not isinstance(selected, list) or not selected:
        raise ContractError("task_repository_required", "Select exact repositories and integration checks before code Work")
    repositories, seen = [], set()
    for item in selected:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ContractError("task_repository_invalid", "Repository path must be explicit")
        path = Path(item["path"])
        if not path.is_absolute():
            path = root / path
        if path.resolve() != path or not path.is_relative_to(root):
            raise ContractError("task_repository_invalid", "Select a canonical repository within the bound project; do not switch project-root to bypass the parent binding")
        actual = worktrees.git(path, "rev-parse", "--show-toplevel").stdout.decode().strip()
        if Path(actual) != path or str(path) in seen:
            raise ContractError("task_repository_invalid", "Select each repository root once")
        if any(path.is_relative_to(Path(p)) or Path(p).is_relative_to(path) for p in seen):
            raise ContractError("task_repository_overlap", "Nested repositories require separate bounded tasks")
        seen.add(str(path))
        target = (item.get("targetBranch") or ((selected_unit or {}).get("targetBranch") if (selected_unit or {}).get("repositoryRoot") == str(path) else None)
                  or (worktrees.branch(path) if isolation else None) or worktrees.repositories(path)[0]["defaultBranch"])
        if not target or worktrees.git(path, "check-ref-format", "refs/heads/" + target, check=False).returncode:
            raise ContractError("task_target_required", "Select an existing integration branch")
        worktrees.git(path, "rev-parse", "--verify", "refs/heads/" + target)
        checks = item.get("checks")
        if (not isinstance(checks, list) or not checks or
                any(not isinstance(argv, list) or not argv or any(not isinstance(a, str) or not a or "\0" in a for a in argv) for argv in checks)):
            raise ContractError("task_checks_required", "Provide nonempty integration check argv arrays for each repository")
        repositories.append({"repositoryRoot": str(path), "relativePath": str(path.relative_to(root)),
                             "targetBranch": target, "checks": checks})
    return {"mode": "code", "repositories": repositories}


def prepare(runtime, state, loop_path, save):
    config = state["execution"].get("workspacePlan")
    if not config:
        return None
    task = state["execution"]["taskBinding"]
    if config["mode"] != "code":
        # An explicit non-code task can follow an archived code task in the same
        # session without keeping its removed CWD or acquiring Git authority.
        identity = hashlib.sha256((state["loopId"] + "\0" + task["taskId"] + "\0" + config["mode"]).encode()).hexdigest()[:24]
        value = {"id": identity, "mode": config["mode"], "projectRoot": state["projectRoot"], "path": state["execution"].get("contextWorkingDirectory", state["projectRoot"]),
                 "workflowId": task["workflowId"], "taskId": task["taskId"], "loopStatePath": str(loop_path), "repositories": []}
        state.setdefault("taskContexts", {})[task["taskId"]] = value
        binding_path = loop_path.parent / ("workspace-" + identity + ".json")
        runtime.atomic_write_json(binding_path, value)
        state["execution"]["taskWorkspacePath"] = str(binding_path)
        save()
        return value
    records = state.setdefault("taskWorkspaces", {})
    value = records.get(task["taskId"])
    root = Path(state["projectRoot"])
    if value is None:
        identity = hashlib.sha256((str(root) + "\0" + state["loopId"] + "\0" + task["workflowId"] + "\0" + task["taskId"]).encode()).hexdigest()[:24]
        home = Path(runtime.runtime_paths.resolve(root)["runtimeRoot"]) / "worktrees" / ("task-" + identity)
        units = []
        for repo in config["repositories"]:
            source = Path(repo["repositoryRoot"])
            suffix = hashlib.sha256(str(source).encode()).hexdigest()[:12]
            branch = "agent-factory/task-" + identity + "-" + suffix
            if worktrees.git(source, "show-ref", "--verify", "--quiet", "refs/heads/" + branch, check=False).returncode == 0:
                raise ContractError("task_branch_exists", "Task branch collision; preserve the existing branch: " + branch)
            destination = home / "workspace" / (repo["relativePath"] if repo["relativePath"] != "." else "repository")
            if destination.exists():
                raise ContractError("task_workspace_exists", "Managed task path already exists; inspect its binding")
            units.append({**repo, "id": identity + "-" + suffix, "path": str(destination), "branch": branch,
                          "baseCommit": worktrees.git(source, "rev-parse", "refs/heads/" + repo["targetBranch"]).stdout.decode().strip(),
                          "sourceDirty": worktrees.dirty(source), "changesIncluded": False, "phase": "creating"})
        value = {"id": identity, "mode": "code", "projectRoot": str(root), "workflowId": task["workflowId"], "taskId": task["taskId"],
                 "workAgentId": task.get("workAgentId", state["workAgentId"]), "loopStatePath": str(loop_path), "repositories": units,
                 "path": units[0]["path"] if len(units) == 1 else str(home / "workspace"), "phase": "creating"}
        records[task["taskId"]] = value
        save()
    for unit in value["repositories"]:
        if unit["phase"] != "creating":
            continue
        destination = Path(unit["path"])
        runtime.runtime_paths.inspect(destination, missing=True)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            ref = "refs/heads/" + unit["branch"]
            if worktrees.git(unit["repositoryRoot"], "show-ref", "--verify", "--quiet", ref, check=False).returncode == 0:
                if worktrees.git(unit["repositoryRoot"], "rev-parse", ref).stdout.decode().strip() != unit["baseCommit"]:
                    raise ContractError("task_workspace_binding", "Interrupted creation branch changed; preserve it for inspection")
                worktrees.git(unit["repositoryRoot"], "worktree", "add", str(destination), unit["branch"])
            else:
                worktrees.git(unit["repositoryRoot"], "worktree", "add", "-b", unit["branch"], str(destination), unit["baseCommit"])
        validate_unit(unit)
        unit["phase"] = "active"
        save()
    value["phase"] = "active"
    binding_path = loop_path.parent / ("workspace-" + value["id"] + ".json")
    runtime.atomic_write_json(binding_path, value)
    state["execution"]["taskWorkspacePath"] = str(binding_path)
    save()
    return value


def validate_unit(unit):
    path = Path(unit["path"])
    if not path.is_dir() or path.is_symlink() or Path(worktrees.git(path, "rev-parse", "--show-toplevel").stdout.decode().strip()) != path:
        raise ContractError("task_workspace_missing", "Restore the exact managed Work Unit before continuing")
    if worktrees.branch(path) != unit["branch"] or worktrees.git(path, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout != worktrees.git(unit["repositoryRoot"], "rev-parse", "--path-format=absolute", "--git-common-dir").stdout:
        raise ContractError("task_workspace_binding", "Work Unit repository or branch binding changed")


def checked_path(value):
    for unit in value["repositories"]:
        validate_unit(unit)
    path = Path(value["path"])
    if not path.is_dir() or path.is_symlink():
        raise ContractError("task_workspace_missing", "Managed task working directory is missing")
    return path


def dispatch_binding(runtime, args, root):
    filename = getattr(args, "task_workspace_file", None)
    if filename is None:
        return None
    value = runtime.safe_read_json(filename)
    location = Path(runtime.runtime_paths.resolve(root)["runtimeRoot"])
    path = Path(value["loopStatePath"])
    if not path.is_relative_to(location) or path.name != "state.json":
        raise ContractError("task_workspace_binding", "Workspace must belong to the registered loop")
    state = runtime.safe_read_json(path)
    task = state["execution"]["taskBinding"]
    current = state.get("taskWorkspaces", {}).get(task["taskId"]) or state.get("taskContexts", {}).get(task["taskId"])
    role = getattr(args, "role", None) or runtime.load_session(root, args.agent)["role"]
    expected_agent = task.get("workAgentId", state["workAgentId"]) if role == "work" else task.get("verificationAgentId", state.get("verificationAgentId"))
    if (role not in {"work", "verification"} or current is None or value["id"] != current["id"] or args.agent != expected_agent or
            args.task_id != task["taskId"] or str(filename) != state["execution"].get("taskWorkspacePath") or
            value["projectRoot"] != str(root) or value != current):
        raise ContractError("task_workspace_binding", "Task workspace differs from accepted loop identity")
    checked_path(value)
    return value


def bind(session, value):
    if value is None:
        return session
    original = Path(session.get("taskWorkspace", {}).get("path", session["projectRoot"]))
    return {**session, "taskWorkspace": value,
            **({"executionPolicy": worktrees.relocate_policy(session["executionPolicy"], original, Path(value["path"]))} if session.get("executionPolicy") else {})}


def paths_changed(unit):
    path = unit["path"]
    names = worktrees.git(path, "diff", "--name-only", "HEAD", "-z").stdout
    names += worktrees.git(path, "ls-files", "--others", "--exclude-standard", "-z").stdout
    return sorted({os.fsdecode(name) for name in names.split(b"\0") if name})


def check(unit, save, stage):
    if unit.get("checkDirectory"):
        from tasks import checks
        unit["checkCommit"] = worktrees.git(unit["path"], "rev-parse", "HEAD").stdout.decode().strip()
        operation = checks.observe(unit, Path(unit["checkDirectory"]), stage)
        unit[stage + "CheckOperation"] = operation
        unit[stage + "Checks"] = operation["results"]
        save()
        if operation["status"] in {"starting", "running"}:
            return False
        if operation["status"] != "completed":
            raise ContractError("task_integration_check_failed", "Check " + operation["status"] + "; evidence: " + operation["statePath"])
        if paths_changed(unit) or worktrees.merge_pending(unit["path"]):
            raise ContractError("task_check_modified_sources", "Checks changed nonignored files; preserve and inspect before integration")
        return True
    evidence = []
    for argv in unit["checks"]:
        # No shell expansion; stdin is closed and the bounded output stays in runtime evidence.
        try:
            result = subprocess.run(argv, cwd=unit["path"], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as error:
            unit.update(phase="check-failed", error=str(error))
            save()
            raise ContractError("task_integration_check_failed", "Integration check could not finish; Work Unit preserved") from error
        evidence.append({"argv": argv, "exitCode": result.returncode, "output": result.stdout.decode("utf-8", "replace")[-12000:]})
        unit[stage + "Checks"] = evidence
        save()
        if result.returncode:
            unit.update(phase="check-failed", error="integration check exited " + str(result.returncode))
            save()
            raise ContractError("task_integration_check_failed", "Integration check failed; Work Unit preserved: " + unit["path"])
    if paths_changed(unit) or worktrees.merge_pending(unit["path"]):
        raise ContractError("task_check_modified_sources", "Checks changed nonignored files; preserve and inspect them before integration")
    return True


def target_checkout(unit, create=False):
    for record in worktrees.git(unit["repositoryRoot"], "worktree", "list", "--porcelain").stdout.decode().split("\n\n"):
        lines = record.splitlines()
        if "branch refs/heads/" + unit["targetBranch"] in lines:
            return Path(next(line[9:] for line in lines if line.startswith("worktree ")))
    if create:
        destination = Path(unit["path"]).parent / ("integration-" + unit["id"])
        if destination.exists():
            raise ContractError("task_target_checkout_exists", "Preserve the unregistered integration directory for inspection")
        worktrees.git(unit["repositoryRoot"], "worktree", "add", "--", str(destination), unit["targetBranch"])
        unit["integrationDirectory"] = str(destination)
        return destination
    raise ContractError("task_target_checkout_required", "Open the captured target branch in a checkout before integration")


def target_overlap(target, target_tip, candidate):
    """Uncommitted or untracked target paths that the target tip -> candidate merge would change."""
    entries = worktrees.git(target, "status", "--porcelain", "-z", "--untracked-files=all").stdout.split(b"\0")
    dirty, index = set(), 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        dirty.add(os.fsdecode(entry[3:]))
        if b"R" in entry[:2] or b"C" in entry[:2]:
            # Porcelain -z lists a rename or copy source as the next entry.
            dirty.add(os.fsdecode(entries[index]))
            index += 1
    merged = {os.fsdecode(name) for name in worktrees.git(target, "diff", "--name-only", "--no-renames", "-z",
              target_tip, candidate).stdout.split(b"\0") if name}
    # A path also collides with a file or directory that contains it.
    return sorted(path for path in dirty if any(path == name or path.startswith(name + "/") or name.startswith(path + "/")
                                                 for name in merged))


def refuse_target_overlap(unit, target, overlap, save):
    unit["targetOverlap"] = overlap
    save()
    error = ContractError("task_target_dirty", "Target checkout has uncommitted changes the merge would change; Work Unit retained: "
                          + str(target) + " (" + ", ".join(overlap) + ")")
    error.files = overlap
    raise error


def task_message(english, korean, value, korean_suffix=""):
    # Runtime commits follow the project's bilingual English / Korean message format.
    name = value["workflowId"] + "/" + value["taskId"]
    return english + " " + name + " / " + korean + " " + name + korean_suffix


def target_merge_message(unit, value):
    return task_message("Merge " + unit["targetBranch"] + " into task", "작업", value, "에 " + unit["targetBranch"] + " 병합")


def run_owner_evidence(runtime, run, root):
    """Unknown/queued owners block; only expired, positively empty runs can be ignored.

    This is observation only: integration never reconciles or replays another run.
    Numeric PIDs and old timestamps alone are not evidence of an empty checkout.
    """
    if run.get("status") not in runtime.ACTIVE_STATES:
        return "inactive"
    try:
        runtime.validate_state_containment_fields(run)
        if run.get("containment") is not None:
            empty = runtime.containment_is_empty(runtime._validate_state_containment(run))
            if not empty:
                return "live"
        else:
            identities = [run[key] for key in ("workerIdentity", "codexIdentity") if run.get(key) is not None]
            statuses = [runtime.process_identity_status(identity) for identity in identities]
            if "match" in statuses:
                return "live"
            empty = bool(statuses) and all(status == "dead" for status in statuses)
        if not empty or run.get("status") in {"accepted", "queued"}:
            return "uncertain"
        session = runtime.load_session(root, run["agentId"])
        return "inactive" if runtime.heartbeat_stale(run, session) else "uncertain"
    except (ContractError, OSError, ValueError, KeyError, TypeError):
        return "uncertain"


def run_owns_checkout(runtime, run, root):
    return run_owner_evidence(runtime, run, root) != "inactive"


def checkout_owners(runtime, state, checkout, *, target=False):
    root = Path(state["projectRoot"])
    parent = state.get("parentStatePath")
    child = None
    if target and parent and state.get("latestWorkRunId"):
        agent = state["execution"]["taskBinding"].get("workAgentId", state["workAgentId"])
        child = runtime.safe_read_json(runtime.state_file(root, agent, state["latestWorkRunId"]))
    owners = []
    for run in runtime.iter_run_states(root, strict=True):
        cwd = Path(run.get("workingDirectory", str(root)))
        if not (cwd.is_relative_to(checkout) or checkout.is_relative_to(cwd)):
            continue
        # The exact accepted Main is the coordinator of this integration, not a
        # competing worker. Never exempt the caller, another Main, or a Work run.
        if (target and child and run.get("role") == "main"
                and child.get("parentAgentId") == run.get("agentId")
                and child.get("parentRunId") == run.get("runId")
                and str(runtime.state_file(root, run["agentId"], run["runId"])) == parent):
            continue
        evidence = run_owner_evidence(runtime, run, root)
        if evidence != "inactive":
            owners.append({"agentId": run["agentId"], "runId": run["runId"], "status": run["status"],
                           "workingDirectory": str(cwd), "evidence": evidence})
    return owners


def require_checkout_idle(runtime, state, checkout, code, *, target=False):
    owners = checkout_owners(runtime, state, checkout, target=target)
    if owners:
        error = ContractError(code, "Checkout has an active run or unproven owner; integration paused: " + str(checkout))
        error.owners = owners
        raise error


def integrate(runtime, state, work, receipt, save):
    value = state.get("taskWorkspaces", {}).get(state["execution"]["taskBinding"]["taskId"])
    if value is None:
        return {"status": "complete"}
    if work.get("status") != "completed" or not receipt["tests"]["run"]:
        raise ContractError("task_checks_required", "Completed Work with actual own checks is required before integration")
    mode = state["execution"]["taskMode"]
    if mode not in {"work", "plan-work"} and state.get("lastVerificationDecision") != "pass" and not state.get("humanSkip"):
        raise ContractError("task_verification_required", "Wait for the requested Verification pass or recorded Human skip")
    value["workRunId"] = work["runId"]
    value["verification"] = "not requested" if mode in {"work", "plan-work"} else "skipped" if state.get("humanSkip") else "pass"
    # Lessons the runtime recorded into this Work Unit are committed with the task.
    allowed = set(receipt["changedPaths"]) | runtime.lesson_capture.recorded_paths(runtime.iter_run_states(Path(state["projectRoot"])), value["id"])
    require_checkout_idle(runtime, state, Path(value["path"]), "task_workspace_busy")
    for unit in value["repositories"]:
        if unit["phase"] == "merged":
            continue
        validate_unit(unit)
        root = Path(unit["repositoryRoot"])
        common = worktrees.git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.decode().strip()
        with runtime.file_lock(Path(common) / ".agent-factory-integration.lock", blocking=False):
            for stage in ("work", "integration"):
                operation = unit.get(stage + "CheckOperation") or {}
                if operation.get("status") in {"starting", "running"}:
                    current_tip = worktrees.git(unit["path"], "rev-parse", "HEAD").stdout.decode().strip()
                    if operation["inputs"]["commit"] != current_tip:
                        raise ContractError("task_check_input_changed", "Checkout changed during an owned check; preserve both operations")
                    if check(unit, save, stage) is False:
                        return {"status": "checking", "unit": unit}
            target = target_checkout(unit, create=True)
            save()
            # Uncommitted target files block only when the merge would change them (checked below).
            if worktrees.merge_pending(target):
                raise ContractError("task_target_dirty", "Target checkout has a pending merge; Work Unit retained: " + str(target))
            require_checkout_idle(runtime, state, target, "task_target_busy", target=True)
            names = paths_changed(unit)
            prefix = Path(unit["relativePath"])
            changed = {str(prefix / name) for name in names}
            inherited = set(unit.get("mergePaths", []))
            if not changed.issubset(allowed | inherited):
                raise ContractError("task_changes_outside_receipt", "Unreported Work Unit changes require a corrected receipt: " + ", ".join(sorted(changed - allowed)))
            if worktrees.merge_pending(unit["path"]):
                unresolved = worktrees.git(unit["path"], "diff", "--name-only", "--diff-filter=U", "-z").stdout
                # Conflict stages require explicit staging by Work; writing a file alone is insufficient evidence.
                if unresolved:
                    return {"status": "conflict", "unit": unit, "files": [os.fsdecode(p) for p in unresolved.split(b"\0") if p]}
                worktrees.git(unit["path"], "commit", "-m", target_merge_message(unit, value))
            elif names:
                unit["phase"] = "committing"
                save()
                worktrees.git(unit["path"], "add", "--", *names)
                worktrees.git(unit["path"], "commit", "-m", task_message("Task", "작업", value))
            unit["resultCommit"] = worktrees.git(unit["path"], "rev-parse", "HEAD").stdout.decode().strip()
            unit["phase"] = "checking"
            save()
            if state.get("lifecycleVersion"):
                unit["checkDirectory"] = str(Path(state["statePath"]).parent)
            # An integration check may still own this checkout after the loop
            # process restarted. Observe it before any new repository mutation.
            integration_check = unit.get("integrationCheckOperation") or {}
            integration_inputs = integration_check.get("inputs", {})
            already_combined = integration_inputs.get("commit") == unit["resultCommit"]
            if not already_combined and check(unit, save, "work") is False:
                return {"status": "checking", "unit": unit}
            target_tip = worktrees.git(target, "rev-parse", "HEAD").stdout.decode().strip()
            # A crash after the target update is recovered by ancestry, not a second merge.
            if unit.get("candidateCommit") and worktrees.git(target, "merge-base", "--is-ancestor", unit["candidateCommit"], "HEAD", check=False).returncode == 0:
                unit.update(phase="merged", mergeCommit=None if unit.get("noChanges") else unit["candidateCommit"], targetResultCommit=target_tip)
                save()
                continue
            unit.update(phase="integrating", targetBefore=target_tip)
            save()
            merged = worktrees.git(unit["path"], "merge", "-m", target_merge_message(unit, value), "--no-ff", "--no-autostash", "--no-overwrite-ignore", "--", "refs/heads/" + unit["targetBranch"], check=False)
            if merged.returncode:
                unit["phase"] = "conflict" if worktrees.merge_pending(unit["path"]) else "failed"
                unit["error"] = merged.stderr.decode("utf-8", "replace")
                save()
                if unit["phase"] == "failed":
                    raise ContractError("task_merge_failed", unit["error"])
                files = worktrees.git(unit["path"], "diff", "--name-only", "--diff-filter=U", "-z").stdout
                unit["mergePaths"] = [str(Path(unit["relativePath"]) / name) for name in paths_changed(unit)]
                unit["conflictFiles"] = [os.fsdecode(p) for p in files.split(b"\0") if p]
                save()
                return {"status": "conflict", "unit": unit, "files": [os.fsdecode(p) for p in files.split(b"\0") if p]}
            merged_tip = worktrees.git(unit["path"], "rev-parse", "HEAD").stdout.decode().strip()
            # Prepare the ordinary two-parent target merge without touching its
            # checkout. The object uses exactly the tree checked in the Work Unit.
            tree = worktrees.git(unit["path"], "rev-parse", "HEAD^{tree}").stdout.decode().strip()
            if worktrees.git(target, "merge-base", "--is-ancestor", merged_tip, "HEAD", check=False).returncode == 0:
                unit["candidateCommit"] = target_tip
                unit["noChanges"] = True
            else:
                unit["noChanges"] = False
                unit["candidateCommit"] = worktrees.git(unit["path"], "commit-tree", tree, "-p", target_tip, "-p", merged_tip,
                    data=(task_message("Merge task", "작업", value, " 병합") + "\n").encode()).stdout.decode().strip()
            save()
            overlap = target_overlap(target, target_tip, unit["candidateCommit"])
            if overlap:
                refuse_target_overlap(unit, target, overlap, save)
            if check(unit, save, "integration") is False:
                return {"status": "checking", "unit": unit}
            require_checkout_idle(runtime, state, Path(value["path"]), "task_workspace_busy")
            require_checkout_idle(runtime, state, target, "task_target_busy", target=True)
            if worktrees.branch(target) != unit["targetBranch"] or worktrees.merge_pending(target) or worktrees.git(target, "rev-parse", "HEAD").stdout.decode().strip() != target_tip:
                return {"status": "target-changed", "unit": unit}
            overlap = target_overlap(target, target_tip, unit["candidateCommit"])
            if overlap:
                refuse_target_overlap(unit, target, overlap, save)
            # Non-overlapping local files stay untouched; Git still refuses to overwrite any of them.
            updated = worktrees.git(target, "merge", "--ff-only", "--no-autostash", "--no-overwrite-ignore", "--", unit["candidateCommit"], check=False)
            if updated.returncode:
                unit["error"] = updated.stderr.decode("utf-8", "replace")
                save()
                raise ContractError("task_target_dirty", "Target checkout refused the update; Work Unit retained: " + str(target) + ": " + unit["error"].strip())
            unit.pop("targetOverlap", None)
            unit.update(phase="merged", mergeCommit=None if unit["noChanges"] else unit["candidateCommit"], targetResultCommit=unit["candidateCommit"], integratedAt=runtime.now())
            save()
    value["phase"] = "merged"
    save()
    cleanup(runtime, state, value, save)
    return {"status": "complete"}


def cleanup(runtime, state, value, save):
    # Use the same repository lock for integration and cleanup.
    for unit in value["repositories"]:
        common = worktrees.git(unit["repositoryRoot"], "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.decode().strip()
        try:
            with runtime.file_lock(Path(common) / ".agent-factory-integration.lock", blocking=False):
                cleanup_unit(runtime, state, value, unit, save)
        except ContractError as error:
            if error.code != "lock_busy":
                raise
            # The target update is already durable. Deferred cleanup must never
            # masquerade as unmerged Work or make a completed task wait again.
            unit["cleanupPending"] = "integration lock busy"
            save()


def cleanup_unit(runtime, state, value, unit, save):
    integration = unit.get("integrationDirectory")
    if unit.get("cleaned") and (not integration or unit.get("integrationCleaned")):
        return
    path = Path(unit["path"])
    if (unit["phase"] != "merged" or checkout_owners(runtime, state, Path(value["path"]))
            or (integration and checkout_owners(runtime, state, Path(integration), target=True))):
        unit["cleanupPending"] = "active run or incomplete integration"
        save()
        return
    if not unit.get("cleaned") and path.exists() and worktrees.git(path, "status", "--porcelain", "--untracked-files=all", "--ignored").stdout:
        unit["cleanupPending"] = "unpreserved files (including ignored files)"
        save()
        return
    branch_exists = worktrees.git(unit["repositoryRoot"], "show-ref", "--verify", "--quiet", "refs/heads/" + unit["branch"], check=False).returncode == 0
    if not unit.get("cleaned") and not branch_exists and not path.exists():
        unit["cleaned"] = True
    if not unit.get("cleaned") and worktrees.git(unit["repositoryRoot"], "merge-base", "--is-ancestor", "refs/heads/" + unit["branch"], "refs/heads/" + unit["targetBranch"], check=False).returncode:
        unit["cleanupPending"] = "work branch changed after integration"
        save()
        return
    if not unit.get("cleaned"):
        if path.exists():
            worktrees.git(unit["repositoryRoot"], "worktree", "remove", str(path))
        worktrees.git(target_checkout(unit), "branch", "-d", "--", unit["branch"])
        unit["cleaned"] = True
    if integration and Path(integration).exists():
        if worktrees.branch(integration) != unit["targetBranch"] or worktrees.dirty(integration) or worktrees.git(integration, "status", "--porcelain", "--untracked-files=all", "--ignored").stdout:
            unit["cleanupPending"] = "integration checkout contains unpreserved files"
        else:
            worktrees.git(unit["repositoryRoot"], "worktree", "remove", integration)
            unit["integrationCleaned"] = True
    if not integration or not Path(integration).exists():
        unit.pop("cleanupPending", None)
    save()
