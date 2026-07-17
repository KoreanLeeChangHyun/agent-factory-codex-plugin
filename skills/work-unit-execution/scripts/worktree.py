#!/usr/bin/env python3
"""Safely prepare, inspect, and clean up Agent Factory linked worktrees."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "1.0.0"


class ContractError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


@dataclass
class GitResult:
    args: list[str]
    returncode: int
    stdout: bytes
    stderr: bytes

    def evidence(self) -> dict[str, Any]:
        return {
            "args": self.args,
            "returnCode": self.returncode,
            "stderr": self.stderr.decode("utf-8", errors="surrogateescape").strip(),
            "stdout": self.stdout.decode("utf-8", errors="surrogateescape").strip(),
        }


@dataclass
class Execution:
    command: str
    operations: list[dict[str, Any]] = field(default_factory=list)

    def git(
        self,
        repository: Path | None,
        args: Sequence[str],
        *,
        record: bool = False,
    ) -> GitResult:
        command = ["git"]
        if repository is not None:
            command.extend(["-C", str(repository)])
        command.extend(args)
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        result = GitResult(command, completed.returncode, completed.stdout, completed.stderr)
        if record:
            self.operations.append(result.evidence())
        return result


def absolute_path(value: str, field_name: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ContractError(
            "path_not_absolute",
            f"{field_name} must be an absolute path",
            {"field": field_name, "value": value},
        )
    return Path(os.path.abspath(path))


def validate_repository(execution: Execution, value: str) -> Path:
    repository = absolute_path(value, "repository")
    if not repository.is_dir():
        raise ContractError("invalid_repository", "repository does not exist or is not a directory")
    result = execution.git(repository, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise ContractError("invalid_repository", "repository is not a Git worktree")
    reported = Path(result.stdout.decode("utf-8", errors="strict").strip()).resolve(strict=False)
    if reported != repository:
        raise ContractError(
            "repository_root_mismatch",
            "repository must resolve to its Git top-level directory",
            {"expected": str(repository), "actual": str(reported)},
        )
    return repository


def resolve_base(execution: Execution, repository: Path, base_ref: str) -> str:
    result = execution.git(
        repository,
        ["rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"],
    )
    if result.returncode != 0:
        raise ContractError("invalid_base_ref", "base ref does not resolve to exactly one commit")
    return result.stdout.decode("ascii", errors="strict").strip()


def validate_branch(execution: Execution, branch: str) -> None:
    result = execution.git(None, ["check-ref-format", "--branch", branch])
    if result.returncode != 0:
        raise ContractError("invalid_branch", "branch name is not valid")


def branch_exists(execution: Execution, repository: Path, branch: str) -> bool:
    result = execution.git(
        repository,
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
    )
    if result.returncode == 0:
        return True
    if result.returncode not in (0, 1):
        raise ContractError("git_validation_failed", "unable to validate branch collision")
    return False


def validate_execution_identity(
    execution: Execution, work_unit_id: str, branch: str | None
) -> str:
    expected_branch = f"work-unit/{work_unit_id}"
    validate_branch(execution, expected_branch)
    if branch is None:
        return expected_branch
    validate_branch(execution, branch)
    if branch != expected_branch:
        raise ContractError(
            "branch_derivation_mismatch",
            "branch must match work-unit/<work-unit-id>",
            {"expected": expected_branch, "actual": branch},
        )
    return expected_branch


def parse_worktree_list(raw: bytes) -> list[dict[str, str | bool]]:
    records: list[dict[str, str | bool]] = []
    for raw_record in raw.split(b"\0\0"):
        if not raw_record:
            continue
        record: dict[str, str | bool] = {}
        for raw_field in raw_record.split(b"\0"):
            if not raw_field:
                continue
            key_raw, separator, value_raw = raw_field.partition(b" ")
            key = key_raw.decode("ascii", errors="strict")
            record[key] = (
                value_raw.decode("utf-8", errors="surrogateescape") if separator else True
            )
        records.append(record)
    return records


def list_worktrees(execution: Execution, repository: Path) -> list[dict[str, str | bool]]:
    result = execution.git(repository, ["worktree", "list", "--porcelain", "-z"])
    if result.returncode != 0:
        raise ContractError("git_validation_failed", "unable to list registered worktrees")
    return parse_worktree_list(result.stdout)


def find_worktree(
    records: list[dict[str, str | bool]], worktree_path: Path
) -> dict[str, str | bool] | None:
    for record in records:
        value = record.get("worktree")
        if isinstance(value, str) and Path(value).resolve(strict=False) == worktree_path:
            return record
    return None


def common_git_dir(execution: Execution, worktree: Path) -> Path | None:
    if not worktree.is_dir():
        return None
    result = execution.git(worktree, ["rev-parse", "--git-common-dir"])
    if result.returncode != 0:
        return None
    raw = Path(result.stdout.decode("utf-8", errors="strict").strip())
    if not raw.is_absolute():
        raw = worktree / raw
    return raw.resolve(strict=False)


def expected_common_git_dir(execution: Execution, repository: Path) -> Path:
    result = execution.git(repository, ["rev-parse", "--git-common-dir"])
    if result.returncode != 0:
        raise ContractError("invalid_repository", "repository has no common Git directory")
    raw = Path(result.stdout.decode("utf-8", errors="strict").strip())
    if not raw.is_absolute():
        raw = repository / raw
    return raw.resolve(strict=False)


def require_registered_worktree(
    execution: Execution,
    repository: Path,
    branch: str,
    worktree_path: Path,
) -> dict[str, str | bool]:
    records = list_worktrees(execution, repository)
    record = find_worktree(records, worktree_path)
    if record is None:
        actual_common = common_git_dir(execution, worktree_path)
        expected_common = expected_common_git_dir(execution, repository)
        if actual_common is not None and actual_common != expected_common:
            raise ContractError(
                "repository_mismatch",
                "worktree belongs to a different repository",
                {"expectedCommonDir": str(expected_common), "actualCommonDir": str(actual_common)},
            )
        raise ContractError("worktree_not_registered", "worktree path is not registered")
    expected_branch = f"refs/heads/{branch}"
    if record.get("branch") != expected_branch:
        raise ContractError(
            "branch_mismatch",
            "registered worktree uses a different branch",
            {"expected": expected_branch, "actual": record.get("branch")},
        )
    return record


def parse_status(raw: bytes) -> list[dict[str, str]]:
    fields = raw.split(b"\0")
    changes: list[dict[str, str]] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        if len(field) < 3 or field[2:3] != b" ":
            raise ContractError("status_parse_failed", "unexpected porcelain status record")
        status = field[:2].decode("ascii", errors="strict")
        path = field[3:].decode("utf-8", errors="surrogateescape")
        change = {"path": path, "status": status}
        if "R" in status or "C" in status:
            if index >= len(fields) or not fields[index]:
                raise ContractError("status_parse_failed", "rename record is incomplete")
            change["originalPath"] = fields[index].decode(
                "utf-8", errors="surrogateescape"
            )
            index += 1
        changes.append(change)
    return changes


def inspect_context(
    execution: Execution,
    repository: Path,
    branch: str,
    worktree_path: Path,
) -> dict[str, Any]:
    record = require_registered_worktree(execution, repository, branch, worktree_path)
    status = execution.git(
        worktree_path,
        ["status", "--porcelain=v1", "-z", "--untracked-files=all"],
    )
    if status.returncode != 0:
        raise ContractError("git_inspection_failed", "unable to inspect worktree status")
    changes = parse_status(status.stdout)
    head = execution.git(worktree_path, ["rev-parse", "--verify", "HEAD^{commit}"])
    if head.returncode != 0:
        raise ContractError("git_inspection_failed", "unable to resolve worktree HEAD")
    return {
        "branch": branch,
        "changes": changes,
        "dirty": bool(changes),
        "headCommit": head.stdout.decode("ascii", errors="strict").strip(),
        "locked": "locked" in record,
        "lockReason": record.get("locked") if isinstance(record.get("locked"), str) else None,
        "repository": str(repository),
        "worktreePath": str(worktree_path),
    }


def prepare(execution: Execution, args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(execution, args.repository)
    worktree_path = absolute_path(args.path, "path")
    base_commit = resolve_base(execution, repository, args.base)
    branch = validate_execution_identity(execution, args.work_unit_id, args.branch)
    exists = branch_exists(execution, repository, branch)
    records = list_worktrees(execution, repository)
    registered = find_worktree(records, worktree_path)

    if registered is not None:
        if registered.get("branch") != f"refs/heads/{branch}":
            raise ContractError(
                "worktree_collision",
                "worktree path is registered to a different branch",
                {"worktreePath": str(worktree_path), "actualBranch": registered.get("branch")},
            )
        if not exists:
            raise ContractError("branch_collision", "registered worktree branch is missing")
        if "locked" not in registered:
            lock_reason = f"Agent Factory Work Unit execution: {branch}"
            lock = execution.git(
                repository,
                ["worktree", "lock", "--reason", lock_reason, str(worktree_path)],
                record=True,
            )
            if lock.returncode != 0:
                raise ContractError(
                    "prepare_failed",
                    "unable to lock reused worktree",
                    {"returnCode": lock.returncode},
                )
        context = inspect_context(execution, repository, branch, worktree_path)
        context.update(
            {
                "baseCommit": base_commit,
                "baseRef": args.base,
                "reused": True,
                "workUnitId": args.work_unit_id,
            }
        )
        return success_payload(execution, "reused", context)

    if exists:
        raise ContractError("branch_collision", "branch already exists", {"branch": branch})
    if os.path.lexists(worktree_path):
        raise ContractError(
            "path_collision",
            "worktree path already exists",
            {"worktreePath": str(worktree_path)},
        )

    lock_reason = f"Agent Factory Work Unit execution: {branch}"
    result = execution.git(
        repository,
        [
            "worktree",
            "add",
            "--lock",
            "--reason",
            lock_reason,
            "-b",
            branch,
            str(worktree_path),
            base_commit,
        ],
        record=True,
    )
    if result.returncode != 0:
        raise ContractError(
            "prepare_failed",
            "git worktree add failed",
            {"returnCode": result.returncode},
        )
    context = inspect_context(execution, repository, branch, worktree_path)
    context.update(
        {
            "baseCommit": base_commit,
            "baseRef": args.base,
            "reused": False,
            "workUnitId": args.work_unit_id,
        }
    )
    return success_payload(execution, "prepared", context)


def inspect(execution: Execution, args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(execution, args.repository)
    worktree_path = absolute_path(args.path, "path")
    branch = validate_execution_identity(execution, args.work_unit_id, args.branch)
    context = inspect_context(execution, repository, branch, worktree_path)
    context["workUnitId"] = args.work_unit_id
    return success_payload(execution, "dirty" if context["dirty"] else "clean", context)


def cleanup(execution: Execution, args: argparse.Namespace) -> dict[str, Any]:
    repository = validate_repository(execution, args.repository)
    worktree_path = absolute_path(args.path, "path")
    branch = validate_execution_identity(execution, args.work_unit_id, args.branch)
    context = inspect_context(execution, repository, branch, worktree_path)
    context["workUnitId"] = args.work_unit_id
    if args.human_decision != "approved":
        raise ContractError(
            "missing_human_decision",
            "cleanup requires --human-decision approved",
        )
    if context["dirty"]:
        raise ContractError(
            "dirty_worktree",
            "cleanup refuses a dirty worktree",
            {"changes": context["changes"]},
        )
    if context["locked"]:
        unlock = execution.git(
            repository,
            ["worktree", "unlock", str(worktree_path)],
            record=True,
        )
        if unlock.returncode != 0:
            raise ContractError(
                "cleanup_failed",
                "git worktree unlock failed",
                {"returnCode": unlock.returncode},
            )
    result = execution.git(
        repository,
        ["worktree", "remove", str(worktree_path)],
        record=True,
    )
    if result.returncode != 0:
        raise ContractError(
            "cleanup_failed",
            "git worktree remove failed",
            {"returnCode": result.returncode},
        )
    context.update(
        {
            "branchRetained": True,
            "dirty": False,
            "humanDecision": args.human_decision,
            "locked": False,
            "lockReason": None,
            "worktreeRemoved": True,
        }
    )
    return success_payload(execution, "cleaned", context)


def success_payload(execution: Execution, state: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "command": execution.command,
        "context": context,
        "error": None,
        "ok": True,
        "operations": execution.operations,
        "schemaVersion": SCHEMA_VERSION,
        "state": state,
    }


def error_payload(execution: Execution, error: ContractError) -> dict[str, Any]:
    return {
        "command": execution.command,
        "context": None,
        "error": {
            "code": error.code,
            "details": error.details,
            "message": error.message,
        },
        "ok": False,
        "operations": execution.operations,
        "schemaVersion": SCHEMA_VERSION,
        "state": "refused",
    }


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="worktree.py")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    def common(command: str) -> argparse.ArgumentParser:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--repository", required=True)
        subparser.add_argument("--work-unit-id", required=True)
        subparser.add_argument("--branch")
        subparser.add_argument("--path", required=True)
        return subparser

    prepare_parser = common("prepare")
    prepare_parser.add_argument("--base", required=True)
    common("inspect")
    cleanup_parser = common("cleanup")
    cleanup_parser.add_argument("--human-decision")
    return parser


def command_hint(argv: Sequence[str]) -> str:
    return argv[0] if argv and argv[0] in {"prepare", "inspect", "cleanup"} else "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    execution = Execution(command_hint(actual_argv))
    try:
        args = build_parser().parse_args(actual_argv)
        execution.command = args.command
        handlers = {"prepare": prepare, "inspect": inspect, "cleanup": cleanup}
        payload = handlers[args.command](execution, args)
        return_code = 0
    except ContractError as error:
        payload = error_payload(execution, error)
        return_code = 2
    except (OSError, UnicodeError) as error:
        payload = error_payload(
            execution,
            ContractError("unexpected_io_error", "unable to complete worktree operation", {"type": type(error).__name__}),
        )
        return_code = 3
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
