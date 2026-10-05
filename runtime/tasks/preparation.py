"""Task-bound prerequisites prepared before any model dispatch.

Only local guidance reachable from repository AGENTS.md is snapshotted. Dependency
commands use the same detached, recorded operation as integration checks.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil

from execution import worktrees
from storage.errors import ContractError
from storage.files import atomic_write
from tasks import checks


def guidance(runtime, root, value):
    root = Path(root)
    repositories = value["repositories"]
    # Mirror project-relative links beside the isolated repositories, never in
    # the source checkout or through a symlink to writable source guidance.
    destination = Path(repositories[0]["path"])
    for _ in Path(repositories[0]["relativePath"]).parts:
        destination = destination.parent
    if repositories[0]["relativePath"] == ".":
        destination = Path(repositories[0]["path"])
    pending = [Path(unit["repositoryRoot"]) / "AGENTS.md" for unit in repositories
               if (Path(unit["repositoryRoot"]) / "AGENTS.md").is_file()]
    seen, manifest = set(), []
    while pending:
        source = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        if not source.is_relative_to(root):
            continue  # External policy is not silently copied or granted write authority.
        content = runtime.safe_read_bytes(source, None)
        relative = source.relative_to(root)
        inside_repo = next((u for u in repositories if source.is_relative_to(Path(u["repositoryRoot"]))), None)
        if inside_repo:
            target = Path(inside_repo["path"]) / source.relative_to(Path(inside_repo["repositoryRoot"]))
            # Tracked guidance is pinned to the Git base. Ignored local guidance
            # (commonly AGENTS.md) still belongs in the isolated read-only snapshot.
            if not target.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(target, content)
                target.chmod(0o444)
            content = runtime.safe_read_bytes(target, None)
        else:
            target = destination / relative
            if target.exists() and target.is_symlink():
                raise ContractError("task_guidance_unsafe", "Guidance snapshot cannot follow symlinks: " + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                atomic_write(target, content)
                target.chmod(0o444)
            elif runtime.safe_read_bytes(target, None) != content:
                # Resume keeps the version the first dispatch received.
                content = runtime.safe_read_bytes(target, None)
        manifest.append({"source": str(source), "path": str(target),
                         "sha256": hashlib.sha256(content).hexdigest()})
        if source.suffix == ".md":
            for link in re.findall(r"\]\(([^)]+)\)", content.decode("utf-8")):
                link = link.split("#", 1)[0].strip("<>")
                if not link or "://" in link or link.startswith("#"):
                    continue
                candidate = Path(os.path.abspath(source.parent / link))
                if not candidate.is_relative_to(root):
                    continue
                if candidate.suffix not in {".md", ".json"}:
                    continue  # A source-code citation is not an instruction snapshot.
                if not candidate.is_file():
                    if source.name == "AGENTS.md":
                        raise ContractError("task_guidance_missing", "Required linked guidance is missing: " + str(candidate))
                    manifest[-1].setdefault("unresolvedReferences", []).append(str(candidate))
                    continue
                pending.append(candidate)
    return manifest


def ready(runtime, state, path, save):
    task = state["execution"].get("taskBinding", {})
    value = state.get("taskWorkspaces", {}).get(task.get("taskId"))
    if not value:
        return True
    if "guidance" not in value:
        value["guidance"] = guidance(runtime, state["projectRoot"], value)
        save()
    for unit in value["repositories"]:
        cwd = Path(unit["path"])
        if not os.access(cwd, os.R_OK | os.W_OK | os.X_OK):
            raise ContractError("task_preparation_failed", "Work Unit is not readable and writable: " + str(cwd))
        for argv in unit["checks"]:
            if not shutil.which(argv[0]):
                raise ContractError("task_preparation_failed", "Install the required check executable before dispatch: " + argv[0])
        lockfile = cwd / "package-lock.json"
        if not lockfile.is_file() or not any("npm" in argv for argv in unit["checks"]):
            continue
        lockhash = hashlib.sha256(lockfile.read_bytes()).hexdigest()
        commit = worktrees.git(cwd, "rev-parse", "HEAD").stdout.decode().strip()
        evidence = unit.get("dependencyPreparation")
        if evidence and evidence["inputs"]["commit"] == commit + ":" + lockhash and evidence["status"] == "completed" and (cwd / "node_modules").is_dir():
            continue
        operation = checks.observe({**unit, "checks": [["npm", "ci"]],
                                    "checkCommit": commit + ":" + lockhash,
                                    "checkGeneration": unit.get("preparationRevision", 0)},
                                   path.parent, "dependencies")
        unit["dependencyPreparation"] = operation
        state["preflight"] = {"taskId": task["taskId"], "workspaceId": value["id"],
                              "status": operation["status"], "operation": operation}
        save()
        if operation["status"] in {"starting", "running"}:
            return False
        if operation["status"] != "completed":
            raise ContractError("task_preparation_failed", "Dependency preparation " + operation["status"] + ": " + operation["statePath"])
    # Refresh the exact binding after preparation; a later unrelated workspace's
    # npm result cannot satisfy this prerequisite.
    runtime.atomic_write_json(Path(state["execution"]["taskWorkspacePath"]), value)
    state["preflight"] = {"taskId": task["taskId"], "workspaceId": value["id"], "status": "completed"}
    save()
    return True
