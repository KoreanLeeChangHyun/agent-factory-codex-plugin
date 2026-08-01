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
        if not path.startswith(".agent-factory/"):
            changed.append(path)
    return changed


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
    current = git(repository, "branch", "--show-current")
    if current.returncode != 0 or current.stdout.strip() != target_branch:
        raise IntegrationError(f"target branch must be checked out: {target_branch}")
    dirty = noncanonical_changes(repository)
    if dirty:
        raise IntegrationError(
            f"target has non-canonical changes: {', '.join(sorted(dirty))}"
        )
    source_commit = resolve_commit(repository, source_branch)
    target_before = resolve_commit(repository, target_branch)
    operations: list[list[str]] = []
    if is_ancestor(repository, source_commit, target_before):
        relationship = "already-integrated"
        strategy = "none"
    elif is_ancestor(repository, target_before, source_commit):
        relationship = "fast-forwardable"
        strategy = "ff-only"
        arguments = ["merge", "--ff-only", source_branch]
        result = git(repository, *arguments)
        operations.append(arguments)
        if result.returncode != 0:
            raise IntegrationError(f"package integration failed: {result.stderr.strip()}")
    else:
        relationship = "diverged"
        strategy = "no-ff"
        arguments = ["merge", "--no-ff", "--no-edit", source_branch]
        result = git(repository, *arguments)
        operations.append(arguments)
        if result.returncode != 0:
            git(repository, "merge", "--abort")
            raise IntegrationError(
                f"package integration conflict: {result.stderr.strip()}"
            )
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


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = Path(os.path.abspath(args.repository))
    package = (
        repository / ".agent-factory" / "work-packages" / args.package_id
    )
    manager_json("validate", str(package), "--full")
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
