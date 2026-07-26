#!/usr/bin/env python3
"""Create and inspect Human-approved lifecycle artifact checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "1.0.0"
SKILLS_ROOT = Path(__file__).resolve().parents[3]
MANAGERS = {
    "intake": SKILLS_ROOT / "intake" / "scripts" / "intake.py",
    "work-unit": (
        SKILLS_ROOT
        / "work-unit-planner"
        / "assets"
        / "scripts"
        / "work_unit.py"
    ),
}
COLLECTIONS = {"intake": "intakes", "work-unit": "work-units"}


class ContractError(Exception):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


@dataclass
class Execution:
    command: str
    operations: list[dict[str, Any]] = field(default_factory=list)

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        record: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            list(args),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if record:
            self.operations.append(
                {
                    "args": list(args),
                    "returnCode": result.returncode,
                    "stdout": result.stdout.decode(
                        "utf-8", errors="surrogateescape"
                    ).strip(),
                    "stderr": result.stderr.decode(
                        "utf-8", errors="surrogateescape"
                    ).strip(),
                }
            )
        return result

    def git(
        self,
        repository: Path,
        args: Sequence[str],
        *,
        record: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        return self.run(["git", "-C", str(repository), *args], record=record)


def absolute_path(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ContractError(
            "path_not_absolute", f"{label} must be absolute", {"value": value}
        )
    return Path(os.path.abspath(path))


def validate_repository(execution: Execution, value: str) -> Path:
    repository = absolute_path(value, "repository")
    result = execution.git(repository, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise ContractError("invalid_repository", "repository is not a Git worktree")
    actual = Path(
        result.stdout.decode("utf-8", errors="strict").strip()
    ).resolve(strict=False)
    if actual != repository:
        raise ContractError(
            "repository_root_mismatch",
            "repository must be the Git top-level",
            {"expected": str(repository), "actual": str(actual)},
        )
    return repository


def expected_package(
    repository: Path, artifact_type: str, artifact_id: str, value: str
) -> Path:
    package = absolute_path(value, "package")
    expected = (
        repository
        / ".agent-factory"
        / COLLECTIONS[artifact_type]
        / artifact_id
    )
    if package != expected:
        raise ContractError(
            "noncanonical_package_path",
            "package must use the canonical artifact root",
            {"expected": str(expected), "actual": str(package)},
        )
    return package


def reject_symlinks(package: Path) -> None:
    if not package.is_dir() or package.is_symlink():
        raise ContractError(
            "invalid_package", "canonical package must be a non-symlink directory"
        )
    for path in package.rglob("*"):
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise ContractError(
                "package_inspection_failed",
                "unable to inspect canonical package",
                {"path": str(path), "error": str(error)},
            ) from error
        if stat.S_ISLNK(mode):
            raise ContractError(
                "package_symlink",
                "canonical package must not contain symlinks",
                {"path": str(path)},
            )


def read_metadata(package: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            (package / "data" / "metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(
            "invalid_package", "cannot read strict artifact metadata"
        ) from error
    if not isinstance(value, dict):
        raise ContractError("invalid_package", "artifact metadata must be an object")
    return value


def validate_package(
    execution: Execution,
    package: Path,
    artifact_type: str,
    artifact_id: str,
) -> dict[str, Any]:
    reject_symlinks(package)
    metadata = read_metadata(package)
    if (
        metadata.get("artifactType") != artifact_type
        or metadata.get("id") != artifact_id
        or package.name != artifact_id
    ):
        raise ContractError(
            "artifact_identity_mismatch",
            "package identity does not match checkpoint input",
        )
    result = execution.run(
        [
            sys.executable,
            str(MANAGERS[artifact_type]),
            "validate",
            str(package),
            "--full",
        ]
    )
    if result.returncode != 0:
        raise ContractError(
            "artifact_validation_failed",
            "owning manager full validation failed",
            {
                "returnCode": result.returncode,
                "reason": result.stderr.decode(
                    "utf-8", errors="surrogateescape"
                ).strip(),
            },
        )
    try:
        validation = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ContractError(
            "artifact_validation_failed",
            "owning manager returned invalid validation evidence",
        ) from error
    if (
        validation.get("valid") is not True
        or validation.get("validationMode") != "full"
        or metadata.get("lifecycle", {}).get("status") != "ready"
    ):
        raise ContractError(
            "artifact_not_ready",
            "checkpoint requires a full-valid ready artifact",
        )
    return validation


def relative_files(
    repository: Path, package: Path, validation: dict[str, Any]
) -> list[str]:
    package_relative = package.relative_to(repository)
    files = validation.get("files")
    if not isinstance(files, list) or not files:
        raise ContractError(
            "artifact_validation_failed", "validation returned no canonical file set"
        )
    result: list[str] = []
    for value in files:
        if (
            not isinstance(value, str)
            or Path(value).is_absolute()
            or ".." in Path(value).parts
        ):
            raise ContractError(
                "artifact_validation_failed",
                "validation returned an unsafe canonical file path",
            )
        target = package / value
        if not target.is_file() or target.is_symlink():
            raise ContractError(
                "artifact_file_mismatch",
                "validated canonical file is unavailable or unsafe",
                {"path": value},
            )
        result.append((package_relative / value).as_posix())
    return sorted(result)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(repository: Path, paths: list[str]) -> dict[str, str]:
    return {path: sha256(repository / path) for path in paths}


def output_lines(result: subprocess.CompletedProcess[bytes]) -> list[str]:
    return [
        value.decode("utf-8", errors="surrogateescape")
        for value in result.stdout.split(b"\0")
        if value
    ]


def commit_paths(
    execution: Execution, repository: Path, commit: str
) -> list[str]:
    result = execution.git(
        repository,
        ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit],
    )
    if result.returncode != 0:
        raise ContractError("git_inspection_failed", "cannot inspect checkpoint tree")
    return sorted(output_lines(result))


def commit_package_paths(
    execution: Execution,
    repository: Path,
    commit: str,
    package: Path,
) -> list[str]:
    relative = package.relative_to(repository).as_posix()
    result = execution.git(
        repository,
        ["ls-tree", "-r", "--name-only", "-z", commit, "--", relative],
    )
    if result.returncode != 0:
        raise ContractError("git_inspection_failed", "cannot inspect checkpoint tree")
    return sorted(output_lines(result))


def checkpoint_commit_matches(
    execution: Execution,
    repository: Path,
    commit: str,
    package: Path,
    expected_snapshot: dict[str, str],
) -> bool:
    files = sorted(expected_snapshot)
    changed_paths = commit_paths(execution, repository, commit)
    if not changed_paths or not set(changed_paths).issubset(files):
        return False
    if commit_package_paths(execution, repository, commit, package) != files:
        return False
    for path, expected_digest in expected_snapshot.items():
        committed_blob = execution.git(repository, ["show", f"{commit}:{path}"])
        if (
            committed_blob.returncode != 0
            or hashlib.sha256(committed_blob.stdout).hexdigest() != expected_digest
        ):
            return False
    return True


def latest_package_commit(
    execution: Execution, repository: Path, package: Path
) -> str:
    relative = package.relative_to(repository).as_posix()
    result = execution.git(
        repository, ["log", "-1", "--format=%H", "--", relative]
    )
    commit = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or not commit:
        raise ContractError(
            "checkpoint_not_found", "artifact has no reconstructible checkpoint"
        )
    return commit


def verify_work_unit_basis_checkpoint(
    execution: Execution, repository: Path, package: Path, head: str
) -> None:
    basis = json.loads(
        (package / "data" / "sections" / "basis.json").read_text(encoding="utf-8")
    )
    refs = [
        ref
        for item in basis["content"]
        if item.get("kind") == "intake-basis-ref"
        for ref in item.get("sourceRefs", [])
        if ref.get("artifactType") == "intake"
    ]
    if len(refs) != 1:
        raise ContractError(
            "intake_checkpoint_mismatch",
            "Work Unit must reference exactly one checkpointed Intake",
        )
    intake = repository / refs[0]["path"]
    validation = validate_package(
        execution, intake, "intake", refs[0]["id"]
    )
    files = relative_files(repository, intake, validation)
    intake_snapshot = snapshot(repository, files)
    intake_commit = latest_package_commit(execution, repository, intake)
    ancestor = execution.git(
        repository, ["merge-base", "--is-ancestor", intake_commit, head]
    )
    same = execution.git(
        repository,
        ["diff", "--quiet", intake_commit, "--", intake.relative_to(repository).as_posix()],
    )
    if (
        ancestor.returncode != 0
        or same.returncode != 0
        or not checkpoint_commit_matches(
            execution,
            repository,
            intake_commit,
            intake,
            intake_snapshot,
        )
    ):
        raise ContractError(
            "intake_checkpoint_mismatch",
            "referenced ready Intake checkpoint is not the current ancestor basis",
        )


def current_head(execution: Execution, repository: Path) -> str:
    result = execution.git(repository, ["rev-parse", "--verify", "HEAD^{commit}"])
    if result.returncode != 0:
        raise ContractError("git_inspection_failed", "cannot resolve repository HEAD")
    return result.stdout.decode("ascii", errors="strict").strip()


def require_target_branch(
    execution: Execution, repository: Path, target_branch: str
) -> None:
    result = execution.git(repository, ["symbolic-ref", "--short", "HEAD"])
    current = result.stdout.decode("utf-8", errors="strict").strip()
    if result.returncode != 0 or current != target_branch:
        raise ContractError(
            "target_branch_mismatch",
            "target branch must be checked out in the repository",
            {"expected": target_branch, "actual": current},
        )


def receipt_context(
    *,
    artifact_type: str,
    artifact_id: str,
    package: Path,
    validation: dict[str, Any],
    target_branch: str,
    before: str,
    after: str,
    message: str,
    human_decision: str,
) -> dict[str, Any]:
    return {
        "artifactType": artifact_type,
        "artifactId": artifact_id,
        "packagePath": str(package),
        "validationMode": "full",
        "validation": validation,
        "targetBranch": target_branch,
        "beforeCommit": before,
        "afterCommit": after,
        "commitMessage": message,
        "humanDecision": human_decision,
    }


def cleanup_index(execution: Execution, repository: Path, paths: list[str]) -> None:
    reset = execution.git(
        repository, ["reset", "--mixed", "-q", "HEAD", "--", *paths], record=True
    )
    if reset.returncode != 0:
        raise ContractError(
            "index_cleanup_failed",
            "checkpoint failure could not restore the package index",
        )


def checkpoint(execution: Execution, args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(execution, args.repository)
    require_target_branch(execution, repository, args.target_branch)
    package = expected_package(
        repository, args.artifact_type, args.artifact_id, args.package
    )
    if args.human_decision != "approved":
        raise ContractError(
            "missing_human_decision",
            "checkpoint requires --human-decision approved",
        )
    if not args.message:
        raise ContractError("invalid_commit_message", "commit message must be non-empty")
    validation = validate_package(
        execution, package, args.artifact_type, args.artifact_id
    )
    files = relative_files(repository, package, validation)
    staged = execution.git(
        repository, ["diff", "--cached", "--name-only", "-z"]
    )
    if staged.returncode != 0:
        raise ContractError("git_inspection_failed", "cannot inspect staged paths")
    if output_lines(staged):
        raise ContractError(
            "unrelated_staged_changes",
            "checkpoint refuses pre-existing staged changes",
            {"paths": sorted(output_lines(staged))},
        )
    before = current_head(execution, repository)
    if args.artifact_type == "work-unit":
        verify_work_unit_basis_checkpoint(execution, repository, package, before)

    latest: str | None
    try:
        latest = latest_package_commit(execution, repository, package)
    except ContractError as error:
        if error.code != "checkpoint_not_found":
            raise
        latest = None
    package_relative = package.relative_to(repository).as_posix()
    unchanged = execution.git(
        repository, ["diff", "--quiet", "HEAD", "--", package_relative]
    )
    if latest is not None and unchanged.returncode == 0:
        current_snapshot = snapshot(repository, files)
        message = execution.git(repository, ["show", "-s", "--format=%B", latest])
        ancestor = execution.git(
            repository, ["merge-base", "--is-ancestor", latest, before]
        )
        if (
            message.returncode == 0
            and ancestor.returncode == 0
            and message.stdout.decode("utf-8", errors="strict").strip() == args.message
            and checkpoint_commit_matches(
                execution,
                repository,
                latest,
                package,
                current_snapshot,
            )
        ):
            parent = execution.git(repository, ["rev-parse", f"{latest}^"])
            if parent.returncode != 0:
                raise ContractError(
                    "git_inspection_failed",
                    "cannot reconstruct checkpoint parent commit",
                )
            return success(
                execution,
                "already-checkpointed",
                receipt_context(
                    artifact_type=args.artifact_type,
                    artifact_id=args.artifact_id,
                    package=package,
                    validation=validation,
                    target_branch=args.target_branch,
                    before=parent.stdout.decode("ascii", errors="strict").strip(),
                    after=latest,
                    message=args.message,
                    human_decision=args.human_decision,
                ),
            )

    before_snapshot = snapshot(repository, files)
    add = execution.git(repository, ["add", "--", *files], record=True)
    if add.returncode != 0:
        cleanup_index(execution, repository, files)
        raise ContractError("checkpoint_failed", "unable to stage canonical package")
    try:
        staged_after = execution.git(
            repository, ["diff", "--cached", "--name-only", "-z"]
        )
        staged_paths = sorted(output_lines(staged_after))
        if (
            staged_after.returncode != 0
            or not staged_paths
            or not set(staged_paths).issubset(files)
        ):
            raise ContractError(
                "staged_path_mismatch",
                "staged file set is not a changed canonical package subset",
                {"expected": files, "actual": staged_paths},
            )
        if snapshot(repository, files) != before_snapshot:
            raise ContractError(
                "artifact_content_race",
                "canonical package changed after validation",
            )
        for path, expected_digest in before_snapshot.items():
            staged_blob = execution.git(repository, ["show", f":{path}"])
            if (
                staged_blob.returncode != 0
                or hashlib.sha256(staged_blob.stdout).hexdigest() != expected_digest
            ):
                raise ContractError(
                    "artifact_content_race",
                    "staged content differs from validated canonical package",
                    {"path": path},
                )
        commit = execution.git(
            repository,
            ["-c", "core.hooksPath=/dev/null", "commit", "-m", args.message],
            record=True,
        )
        if commit.returncode != 0:
            raise ContractError("checkpoint_failed", "Git checkpoint commit failed")
    except ContractError:
        cleanup_index(execution, repository, files)
        raise
    after = current_head(execution, repository)
    if (
        commit_paths(execution, repository, after) != staged_paths
        or not checkpoint_commit_matches(
            execution,
            repository,
            after,
            package,
            before_snapshot,
        )
    ):
        raise ContractError(
            "checkpoint_verification_failed",
            "checkpoint commit does not preserve the validated canonical package",
        )
    return success(
        execution,
        "checkpointed",
        receipt_context(
            artifact_type=args.artifact_type,
            artifact_id=args.artifact_id,
            package=package,
            validation=validation,
            target_branch=args.target_branch,
            before=before,
            after=after,
            message=args.message,
            human_decision=args.human_decision,
        ),
    )


def inspect(execution: Execution, args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(execution, args.repository)
    package = expected_package(
        repository, args.artifact_type, args.artifact_id, args.package
    )
    validation = validate_package(
        execution, package, args.artifact_type, args.artifact_id
    )
    files = relative_files(repository, package, validation)
    current_snapshot = snapshot(repository, files)
    commit = latest_package_commit(execution, repository, package)
    if not checkpoint_commit_matches(
        execution,
        repository,
        commit,
        package,
        current_snapshot,
    ):
        raise ContractError(
            "checkpoint_scope_mismatch",
            "latest artifact commit does not preserve the canonical package",
        )
    target = execution.git(
        repository, ["rev-parse", "--verify", f"{args.target_branch}^{{commit}}"]
    )
    if target.returncode != 0:
        raise ContractError("target_branch_mismatch", "target branch is unresolved")
    target_commit = target.stdout.decode("ascii", errors="strict").strip()
    ancestor = execution.git(
        repository, ["merge-base", "--is-ancestor", commit, target_commit]
    )
    same = execution.git(
        repository,
        ["diff", "--quiet", commit, "--", package.relative_to(repository).as_posix()],
    )
    if ancestor.returncode != 0 or same.returncode != 0:
        raise ContractError(
            "checkpoint_content_mismatch",
            "current artifact does not match its target-branch checkpoint",
        )
    return success(
        execution,
        "inspected",
        {
            "artifactType": args.artifact_type,
            "artifactId": args.artifact_id,
            "packagePath": str(package),
            "validationMode": "full",
            "validation": validation,
            "targetBranch": args.target_branch,
            "targetCommit": target_commit,
            "checkpointCommit": commit,
            "files": files,
        },
    )


def success(
    execution: Execution, state: str, context: dict[str, Any]
) -> dict[str, Any]:
    return {
        "command": execution.command,
        "context": context,
        "error": None,
        "ok": True,
        "operations": execution.operations,
        "schemaVersion": SCHEMA_VERSION,
        "state": state,
    }


def refusal(execution: Execution, error: ContractError) -> dict[str, Any]:
    return {
        "command": execution.command,
        "context": None,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
        "ok": False,
        "operations": execution.operations,
        "schemaVersion": SCHEMA_VERSION,
        "state": "refused",
    }


def parser() -> JsonArgumentParser:
    root = JsonArgumentParser(prog="artifact_handoff.py")
    commands = root.add_subparsers(
        dest="command", required=True, parser_class=JsonArgumentParser
    )

    def common(name: str) -> argparse.ArgumentParser:
        command = commands.add_parser(name)
        command.add_argument("--repository", required=True)
        command.add_argument(
            "--artifact-type", choices=["intake", "work-unit"], required=True
        )
        command.add_argument("--artifact-id", required=True)
        command.add_argument("--package", required=True)
        command.add_argument("--target-branch", required=True)
        return command

    checkpoint_parser = common("checkpoint")
    checkpoint_parser.add_argument("--message", required=True)
    checkpoint_parser.add_argument("--human-decision")
    common("inspect")
    return root


def main() -> int:
    execution = Execution(sys.argv[1] if len(sys.argv) > 1 else "unknown")
    try:
        args = parser().parse_args()
        payload = (
            checkpoint(execution, args)
            if args.command == "checkpoint"
            else inspect(execution, args)
        )
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except ContractError as error:
        print(json.dumps(refusal(execution, error), ensure_ascii=False, sort_keys=True))
        return 1
    except OSError as error:
        wrapped = ContractError(
            "unexpected_io_error", "artifact handoff I/O failed", {"error": str(error)}
        )
        print(json.dumps(refusal(execution, wrapped), ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
