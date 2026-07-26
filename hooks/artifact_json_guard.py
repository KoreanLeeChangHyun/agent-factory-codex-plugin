#!/usr/bin/env python3
"""Block direct authoring of canonical Agent Factory artifact JSON."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CANONICAL_COLLECTIONS = {
    "intakes": "intake",
    "work-units": "work-unit",
    "specifications": "specification",
}
MANAGER_SUFFIXES = {
    "skills/intake/scripts/intake.py",
    "skills/work-unit-planner/assets/scripts/work_unit.py",
    "skills/specification/scripts/specification.py",
}
PATCH_PATH = re.compile(
    r"^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(?P<path>.+?)\s*$",
    re.MULTILINE,
)
SHELL_CANONICAL_PATH = re.compile(
    r"""(?P<path>
        (?:[A-Za-z]:)?
        [^\s'"`;|&<>]*
        \.agent-factory[/\\]
        (?:intakes|work-units|specifications)[/\\]
        [^\s'"`;|&<>]+?\.json
    )""",
    re.VERBOSE,
)
PYTHON_NAMES = {"python", "python3", "py"}
PATCH_TOOL_NAMES = {"apply_patch", "Edit", "Write"}
READ_ONLY_COMMANDS = {
    "cat",
    "cmp",
    "cut",
    "diff",
    "grep",
    "head",
    "jq",
    "less",
    "ls",
    "more",
    "rg",
    "sed",
    "sha256sum",
    "sort",
    "stat",
    "tail",
    "test",
    "tr",
    "uniq",
    "wc",
}
READ_ONLY_GIT_SUBCOMMANDS = {
    "cat-file",
    "diff",
    "grep",
    "log",
    "ls-files",
    "rev-parse",
    "show",
    "status",
}
MAX_TTL_SECONDS = 900
STATE_DIRECTORY = "artifact-json-exceptions"


class GuardError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_details(path: Path) -> dict[str, str] | None:
    normalized = Path(os.path.abspath(path))
    parts = normalized.parts
    for index, part in enumerate(parts):
        if part != ".agent-factory" or index + 3 >= len(parts):
            continue
        collection = parts[index + 1]
        artifact_type = CANONICAL_COLLECTIONS.get(collection)
        if artifact_type is None:
            continue
        artifact_id = parts[index + 2]
        if not artifact_id or normalized.suffix.lower() != ".json":
            continue
        return {
            "artifactType": artifact_type,
            "artifactId": artifact_id,
            "path": str(normalized),
        }
    return None


def normalize_candidate(raw: str, cwd: Path) -> Path:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    path = Path(value)
    if not path.is_absolute():
        path = cwd / path
    return Path(os.path.abspath(path))


def patch_targets(command: str, cwd: Path) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for match in PATCH_PATH.finditer(command):
        details = canonical_details(normalize_candidate(match.group("path"), cwd))
        if details is not None:
            found[details["path"]] = details
    return [found[path] for path in sorted(found)]


def shell_targets(command: str, cwd: Path) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for match in SHELL_CANONICAL_PATH.finditer(command):
        details = canonical_details(normalize_candidate(match.group("path"), cwd))
        if details is not None:
            found[details["path"]] = details
    return [found[path] for path in sorted(found)]


def has_broad_canonical_reference(command: str) -> bool:
    lowered = command.lower()
    return ".agent-factory" in lowered


def has_shell_control(command: str) -> bool:
    quote: str | None = None
    escaped = False
    for character in command:
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote != "'":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        if character in {";", "|", "&", "<", ">", "\n", "\r"}:
            return True
    return quote is not None


def command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def candidate_plugin_roots(cwd: Path) -> list[Path]:
    roots: list[Path] = []
    plugin_root_raw = os.environ.get("PLUGIN_ROOT")
    if plugin_root_raw:
        plugin_root = Path(plugin_root_raw)
        if plugin_root.is_absolute():
            roots.append(Path(os.path.abspath(plugin_root)))
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".codex-plugin" / "plugin.json").is_file():
            normalized = Path(os.path.abspath(candidate))
            if normalized not in roots:
                roots.append(normalized)
            break
    return roots


def is_exact_python_script(
    command: str,
    suffixes: Iterable[str],
    cwd: Path,
) -> bool:
    if has_shell_control(command):
        return False
    tokens = command_tokens(command)
    if len(tokens) < 2 or Path(tokens[0]).name not in PYTHON_NAMES:
        return False
    expanded = os.path.expandvars(tokens[1])
    script = Path(expanded)
    if not script.is_absolute():
        script = cwd / script
    normalized = Path(os.path.abspath(script))
    return any(
        normalized == root / Path(suffix)
        for root in candidate_plugin_roots(cwd)
        for suffix in suffixes
    )


def is_exact_manager_command(command: str, cwd: Path) -> bool:
    return is_exact_python_script(command, MANAGER_SUFFIXES, cwd)


def is_exact_grant_command(command: str, cwd: Path) -> bool:
    if not is_exact_python_script(
        command,
        {"hooks/artifact_json_guard.py"},
        cwd,
    ):
        return False
    tokens = command_tokens(command)
    return len(tokens) >= 3 and tokens[2] == "grant"


def is_read_only_command(command: str) -> bool:
    if has_shell_control(command):
        return False
    tokens = command_tokens(command)
    if not tokens:
        return False
    executable = Path(tokens[0]).name
    if executable == "git":
        return len(tokens) >= 2 and tokens[1] in READ_ONLY_GIT_SUBCOMMANDS
    if executable not in READ_ONLY_COMMANDS:
        return False
    if executable == "sed":
        return not any(
            token == "--in-place"
            or token.startswith("--in-place=")
            or (token.startswith("-") and "i" in token[1:])
            for token in tokens[1:]
        )
    return True


def state_root(plugin_data: Path) -> Path:
    return plugin_data / STATE_DIRECTORY


def ensure_state_directories(plugin_data: Path) -> tuple[Path, Path, Path, Path]:
    if not plugin_data.is_absolute():
        raise GuardError("--plugin-data must be an absolute path")
    root = state_root(plugin_data)
    grants = root / "grants"
    consumed = root / "consumed"
    pending = root / "pending"
    grants.mkdir(parents=True, exist_ok=True)
    consumed.mkdir(parents=True, exist_ok=True)
    pending.mkdir(parents=True, exist_ok=True)
    for path in (root, grants, consumed, pending):
        if path.is_symlink():
            raise GuardError(f"exception state path must not be a symlink: {path}")
    return root, grants, consumed, pending


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def append_audit(root: Path, value: dict[str, Any]) -> None:
    path = root / "audit.jsonl"
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(path, flags, 0o600)
    try:
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def audit_value(event: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "event": event,
        "recordedAt": utc_now(),
        "grantId": record["grantId"],
        "sessionId": record["sessionId"],
        "toolName": record["toolName"],
        "artifactType": record["artifactType"],
        "artifactId": record["artifactId"],
        "paths": record["paths"],
        "reason": record["reason"],
        "approvalReference": record["approvalReference"],
        "humanDecision": record["humanDecision"],
        "expiresAtEpoch": record["expiresAtEpoch"],
    }


def grant_exception(args: argparse.Namespace) -> int:
    plugin_data = Path(args.plugin_data)
    if args.human_decision != "approved":
        raise GuardError("--human-decision must be approved")
    if not args.session_id.strip():
        raise GuardError("--session-id must be non-empty")
    if not args.reason.strip():
        raise GuardError("--reason must be non-empty")
    if not args.approval_reference.strip():
        raise GuardError("--approval-reference must be non-empty")
    if args.ttl_seconds < 1 or args.ttl_seconds > MAX_TTL_SECONDS:
        raise GuardError(
            f"--ttl-seconds must be between 1 and {MAX_TTL_SECONDS}"
        )

    details: list[dict[str, str]] = []
    for raw_path in args.path:
        path = Path(raw_path)
        if not path.is_absolute():
            raise GuardError("--path values must be absolute")
        item = canonical_details(path)
        if item is None:
            raise GuardError(
                "--path must identify canonical Intake, Work Unit, or Specification JSON"
            )
        details.append(item)
    identities = {
        (item["artifactType"], item["artifactId"]) for item in details
    }
    if len(identities) != 1:
        raise GuardError("one grant may target exactly one canonical artifact")

    artifact_type, artifact_id = next(iter(identities))
    now_epoch = int(time.time())
    record = {
        "schemaVersion": "1.0.0",
        "grantId": uuid.uuid4().hex,
        "sessionId": args.session_id,
        "toolName": args.tool_name,
        "artifactType": artifact_type,
        "artifactId": artifact_id,
        "paths": sorted({item["path"] for item in details}),
        "reason": args.reason.strip(),
        "approvalReference": args.approval_reference.strip(),
        "humanDecision": "approved",
        "issuedAt": utc_now(),
        "issuedAtEpoch": now_epoch,
        "expiresAtEpoch": now_epoch + args.ttl_seconds,
        "oneShot": True,
    }
    root, grants, _, pending = ensure_state_directories(plugin_data)
    lock_path = root / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        pending_path = pending / f"{record['grantId']}.json"
        write_json_exclusive(pending_path, record)
        append_audit(root, audit_value("granted", record))
        os.replace(pending_path, grants / pending_path.name)
    print(f"grant recorded: {record['grantId']}")
    return 0


def consume_grant(
    plugin_data: Path,
    session_id: str,
    tool_name: str,
    targets: list[dict[str, str]],
) -> bool:
    root = state_root(plugin_data)
    grants = root / "grants"
    consumed = root / "consumed"
    if not grants.is_dir():
        return False
    expected_paths = sorted(item["path"] for item in targets)
    now_epoch = int(time.time())
    lock_path = root / ".lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        for path in sorted(grants.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                record.get("schemaVersion") != "1.0.0"
                or record.get("humanDecision") != "approved"
                or record.get("oneShot") is not True
                or record.get("sessionId") != session_id
                or record.get("toolName") != tool_name
                or record.get("paths") != expected_paths
                or not isinstance(record.get("expiresAtEpoch"), int)
                or record["expiresAtEpoch"] < now_epoch
            ):
                continue
            identities = {
                (item["artifactType"], item["artifactId"]) for item in targets
            }
            if identities != {
                (record.get("artifactType"), record.get("artifactId"))
            }:
                continue
            destination = consumed / path.name
            os.replace(path, destination)
            append_audit(root, audit_value("consumed", record))
            return True
    return False


def denial_reason(
    payload: dict[str, Any],
    targets: list[dict[str, str]],
    *,
    dynamic: bool,
) -> str:
    tool_name = payload["tool_name"]
    session_id = payload["session_id"]
    if dynamic:
        return (
            "Direct canonical Artifact JSON authoring denied: the command has write "
            "intent toward a dynamically constructed canonical path. Use the owning "
            "Intake, Work Unit, or Specification manager with typed semantic arguments. "
            "If the manager cannot express a necessary recovery, ask the Human for "
            "explicit approval and retry with exact absolute JSON paths."
        )

    paths = [item["path"] for item in targets]
    plugin_root = os.environ.get("PLUGIN_ROOT", "<PLUGIN_ROOT>")
    plugin_data = os.environ.get("PLUGIN_DATA", "<PLUGIN_DATA>")
    grant_command = [
        "python3",
        str(Path(plugin_root) / "hooks" / "artifact_json_guard.py"),
        "grant",
        "--plugin-data",
        plugin_data,
        "--session-id",
        session_id,
        "--tool-name",
        tool_name,
    ]
    for path in paths:
        grant_command.extend(["--path", path])
    grant_command.extend(
        [
            "--reason",
            "REPLACE_WITH_NECESSITY",
            "--approval-reference",
            "REPLACE_WITH_EXPLICIT_HUMAN_APPROVAL",
            "--human-decision",
            "approved",
        ]
    )
    rendered = " ".join(shlex.quote(part) for part in grant_command)
    return (
        "Direct canonical Artifact JSON authoring denied for "
        f"{', '.join(paths)}. Use the owning manager with typed semantic arguments. "
        "If the manager cannot express a necessary recovery, ask the Human for "
        "explicit approval first. Only after approval, record an exact one-shot grant: "
        f"{rendered}"
    )


def read_hook_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as error:
        raise GuardError(f"invalid PreToolUse input: {error}") from error
    if not isinstance(value, dict):
        raise GuardError("invalid PreToolUse input: expected an object")
    for field in ("session_id", "cwd", "tool_name", "tool_input"):
        if field not in value:
            raise GuardError(f"invalid PreToolUse input: missing {field}")
    if value.get("hook_event_name") != "PreToolUse":
        raise GuardError("invalid PreToolUse input: wrong hook_event_name")
    if not isinstance(value["tool_input"], dict):
        raise GuardError("invalid PreToolUse input: tool_input must be an object")
    command = value["tool_input"].get("command")
    if not isinstance(command, str):
        raise GuardError("invalid PreToolUse input: tool_input.command must be a string")
    return value


def run_hook() -> int:
    payload = read_hook_payload()
    tool_name = payload["tool_name"]
    cwd = Path(payload["cwd"])
    if not cwd.is_absolute():
        raise GuardError("invalid PreToolUse input: cwd must be absolute")
    command = payload["tool_input"]["command"]

    if tool_name == "Bash" and (
        is_exact_manager_command(command, cwd)
        or is_exact_grant_command(command, cwd)
    ):
        return 0
    if tool_name in PATCH_TOOL_NAMES:
        targets = patch_targets(command, cwd)
        dynamic = False
        if not targets:
            return 0
    elif tool_name == "Bash":
        targets = shell_targets(command, cwd)
        broad_reference = has_broad_canonical_reference(command)
        dynamic = not targets and broad_reference
        if not targets and not broad_reference:
            return 0
        if is_read_only_command(command):
            return 0
    else:
        return 0

    plugin_data_raw = os.environ.get("PLUGIN_DATA")
    if (
        targets
        and plugin_data_raw
        and consume_grant(
            Path(plugin_data_raw),
            payload["session_id"],
            tool_name,
            targets,
        )
    ):
        return 0

    print(
        denial_reason(payload, targets, dynamic=dynamic),
        file=sys.stderr,
    )
    return 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Guard canonical Agent Factory Artifact JSON authoring"
    )
    subparsers = value.add_subparsers(dest="command", required=True)
    subparsers.add_parser("hook")
    grant = subparsers.add_parser("grant")
    grant.add_argument("--plugin-data", required=True)
    grant.add_argument("--session-id", required=True)
    grant.add_argument(
        "--tool-name",
        choices=("Bash", *sorted(PATCH_TOOL_NAMES)),
        required=True,
    )
    grant.add_argument("--path", action="append", required=True)
    grant.add_argument("--reason", required=True)
    grant.add_argument("--approval-reference", required=True)
    grant.add_argument("--human-decision", required=True)
    grant.add_argument("--ttl-seconds", type=int, default=300)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        if args.command == "hook":
            return run_hook()
        return grant_exception(args)
    except GuardError as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        print(
            f"artifact JSON guard internal failure; denying tool call: {error}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
