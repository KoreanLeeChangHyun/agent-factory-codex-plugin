#!/usr/bin/env python3
"""Integrate a reviewed Work Package once and register its canonical receipt."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


WORK_PACKAGE_MANAGER = (
    Path(__file__).resolve().parents[2]
    / "work-units"
    / "scripts"
    / "work_package.py"
)


class IntegrationError(RuntimeError):
    pass


def git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def resolve_commit(repository: Path, ref: str) -> str:
    result = git(repository, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise IntegrationError(f"cannot resolve Git ref: {ref}")
    return result.stdout.strip()


def is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    result = git(repository, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode not in {0, 1}:
        raise IntegrationError("cannot determine Git ancestry")
    return result.returncode == 0


def noncanonical_changes(repository: Path) -> list[str]:
    result = git(repository, "status", "--porcelain=v1", "-z")
    if result.returncode != 0:
        raise IntegrationError("cannot inspect target repository status")
    entries = [entry for entry in result.stdout.split("\0") if entry]
    changed = []
    for entry in entries:
        path = entry[3:].split(" -> ")[-1]
        # Canonical manager writes are expected on the primary root and are
        # orthogonal to the reviewed code branch being integrated.
        if not path.startswith(".agent-factory/"):
            changed.append(path)
    return changed


def target_worktree(repository: Path, target_branch: str) -> Path | None:
    listing = git(repository, "worktree", "list", "--porcelain")
    if listing.returncode != 0:
        raise IntegrationError("cannot inspect registered Git worktrees")
    target_ref = f"refs/heads/{target_branch}"
    matches: list[Path] = []
    current_path: Path | None = None
    for line in [*listing.stdout.splitlines(), ""]:
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve()
        elif line == f"branch {target_ref}" and current_path is not None:
            matches.append(current_path)
        elif not line:
            current_path = None
    if len(matches) > 1:
        raise IntegrationError("target branch is checked out in multiple worktrees")
    return matches[0] if matches else None


def remove_temporary_worktree(repository: Path, path: Path) -> None:
    removed = git(repository, "worktree", "remove", str(path))
    if removed.returncode != 0:
        raise IntegrationError(
            f"cannot remove temporary target worktree: {removed.stderr.strip()}"
        )
    try:
        path.parent.rmdir()
    except OSError as error:
        raise IntegrationError("temporary target worktree parent is not empty") from error


def integrate(
    *,
    repository: Path,
    package_id: str,
    source_branch: str,
    target_branch: str,
) -> dict[str, Any]:
    repository = repository.resolve()
    top = git(repository, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != repository:
        raise IntegrationError("repository must be the primary Git root")
    source_commit = resolve_commit(repository, source_branch)
    target_before = resolve_commit(repository, target_branch)
    operations: list[list[str]] = []
    # Ancestry, not branch names or timestamps, selects the only permitted
    # integration strategy and makes an already-integrated retry idempotent.
    if is_ancestor(repository, source_commit, target_before):
        relationship = "already-integrated"
        strategy = "none"
    elif is_ancestor(repository, target_before, source_commit):
        relationship = "fast-forwardable"
        strategy = "ff-only"
    else:
        relationship = "diverged"
        strategy = "no-ff"

    target_path = target_worktree(repository, target_branch)
    temporary_target = target_path is None and relationship != "already-integrated"
    if target_path is not None:
        dirty = noncanonical_changes(target_path)
        if dirty:
            raise IntegrationError(
                f"target has non-canonical changes: {', '.join(sorted(dirty))}"
            )
    if temporary_target:
        temporary_root = Path(tempfile.mkdtemp(prefix="agent-factory-package-target-"))
        target_path = temporary_root / target_branch.replace("/", "-")
        arguments = ["worktree", "add", "--detach", str(target_path), target_before]
        added = git(repository, *arguments)
        operations.append(arguments)
        if added.returncode != 0:
            temporary_root.rmdir()
            raise IntegrationError(
                f"cannot prepare temporary target worktree: {added.stderr.strip()}"
            )

    if relationship != "already-integrated":
        assert target_path is not None
        arguments = (
            ["merge", "--ff-only", source_commit]
            if relationship == "fast-forwardable"
            else ["merge", "--no-ff", "--no-edit", source_commit]
        )
        result = git(target_path, *arguments)
        operations.append(arguments)
        if result.returncode != 0:
            if relationship == "diverged":
                git(target_path, "merge", "--abort")
            if temporary_target:
                remove_temporary_worktree(repository, target_path)
            raise IntegrationError(
                f"package integration conflict: {result.stderr.strip()}"
            )

    if temporary_target:
        assert target_path is not None
        detached_after = resolve_commit(target_path, "HEAD")
        arguments = [
            "update-ref",
            f"refs/heads/{target_branch}",
            detached_after,
            target_before,
        ]
        updated = git(repository, *arguments)
        operations.append(arguments)
        if updated.returncode != 0:
            remove_temporary_worktree(repository, target_path)
            raise IntegrationError("target branch changed during package integration")
        remove_temporary_worktree(repository, target_path)

    target_after = resolve_commit(repository, target_branch)
    return {
        "schemaVersion": "1.0.0",
        "packageId": package_id,
        "repository": str(repository),
        "sourceBranch": source_branch,
        "sourceCommit": source_commit,
        "targetBranch": target_branch,
        "targetCommitBefore": target_before,
        "targetCommitAfter": target_after,
        "relationship": relationship,
        "strategy": strategy,
        "operationResult": "integrated",
        "operations": operations,
    }


def manager_json(*arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(WORK_PACKAGE_MANAGER), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise IntegrationError(result.stderr.strip())
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise IntegrationError(f"Work Package manager returned invalid JSON: {error}")
    if not isinstance(value, dict):
        raise IntegrationError("Work Package manager returned a non-object")
    return value


def definition(package: Path) -> dict[str, Any]:
    section = manager_json("show", str(package), "--section", "definition")
    matches = [
        item
        for container in [section, *section.get("subsections", [])]
        for item in container["content"]
        if item["kind"] == "package-definition"
    ]
    if len(matches) != 1 or not isinstance(matches[0]["content"], dict):
        raise IntegrationError("canonical package-definition is invalid")
    return matches[0]["content"]


def require_passing_review(package: Path) -> None:
    section = manager_json("show", str(package), "--section", "ai-review")
    matches = [
        item
        for container in [section, *section.get("subsections", [])]
        for item in container.get("content", [])
        if item.get("kind") == "ai-review-result"
    ]
    if len(matches) != 1:
        raise IntegrationError("Work Package has no canonical AI review result")
    attributes = matches[0].get("attributes")
    if not isinstance(attributes, dict) or (
        attributes.get("result") != "pass"
        or attributes.get("checklistResult") != "pass"
    ):
        raise IntegrationError("Work Package AI review did not pass")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = Path(os.path.abspath(args.repository))
    package = (
        repository / ".agent-factory" / "work-packages" / args.package_id
    )
    manager_json("validate", str(package), "--full")
    require_passing_review(package)
    contract = definition(package)
    receipt = integrate(
        repository=repository,
        package_id=args.package_id,
        source_branch=contract["integrationBranch"],
        target_branch=contract["targetBranch"],
    )
    descriptor, name = tempfile.mkstemp(
        prefix="work-package-integration-", suffix=".json"
    )
    os.close(descriptor)
    path = Path(name)
    try:
        path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        manager_json("complete", str(package), "--receipt", str(path))
    finally:
        path.unlink(missing_ok=True)
    return receipt


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Integrate a completed Agent Factory Work Package"
    )
    root.add_argument("--repository", required=True)
    root.add_argument("--package-id", required=True)
    root.add_argument("--review-decision", required=True, choices=["complete"])
    return root


def main() -> int:
    try:
        receipt = execute(parser().parse_args())
        print(json.dumps(receipt, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (IntegrationError, OSError, ValueError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
