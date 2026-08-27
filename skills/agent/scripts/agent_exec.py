#!/usr/bin/env python3
"""Manage resumable Codex exec agents without blocking the Main Agent."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import queue
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, IO, Iterator, Sequence


SCHEMA_VERSION = "0.1.0"
AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ROLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
ACTORS = ("main", "human")
ACTIVE_STATES = {"accepted", "queued", "starting", "running", "cancelling"}
TERMINAL_STATES = {"completed", "needs-human-decision", "failed", "cancelled"}
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
SANDBOX_UNAVAILABLE_STDERR = (
    "fs sandbox helper failed with status",
    "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted",
)
SKILL_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references"


class ContractError(Exception):
    """Represent a stable machine-readable refusal or runtime failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def emit(value: dict[str, Any], stream: IO[str] = sys.stdout) -> None:
    stream.write(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    stream.flush()


def error_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "error",
        "error": {"code": code, "message": message},
    }


def validate_id(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not pattern.fullmatch(value):
        raise ContractError(f"invalid_{label}", f"{label.replace('_', ' ')} is invalid")
    return value


def resolve_project_root(value: Path) -> Path:
    try:
        root = value.resolve(strict=True)
    except OSError as error:
        raise ContractError("project_root_not_found", "project root was not found") from error
    if not root.is_dir():
        raise ContractError("project_root_invalid", "project root is not a directory")
    return root


def ensure_directory(path: Path, anchor: Path) -> None:
    try:
        relative = path.relative_to(anchor)
    except ValueError as error:
        raise ContractError("path_outside_project", "runtime path escaped the project root") from error
    cursor = anchor
    for part in relative.parts:
        cursor = cursor / part
        try:
            current = os.lstat(cursor)
        except FileNotFoundError:
            try:
                os.mkdir(cursor, 0o700)
            except FileExistsError:
                current = os.lstat(cursor)
                if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
                    raise ContractError("runtime_path_unsafe", "runtime path is unsafe")
            continue
        if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
            raise ContractError("runtime_path_unsafe", "runtime path is unsafe")


def reject_symlink(path: Path) -> None:
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(current.st_mode):
        raise ContractError("runtime_path_unsafe", "runtime file must not be a symlink")


def atomic_write(path: Path, content: bytes) -> None:
    ensure_directory(path.parent, find_project_anchor(path))
    reject_symlink(path)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def find_project_anchor(path: Path) -> Path:
    cursor = path.resolve(strict=False)
    for parent in (cursor, *cursor.parents):
        if parent.name == ".agent-factory":
            return parent.parent
    raise ContractError("runtime_path_invalid", "runtime path is not below .agent-factory")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
    )


def safe_read_bytes(path: Path, limit: int) -> bytes:
    reject_symlink(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError as error:
        raise ContractError("file_not_found", f"required file was not found: {path}") from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ContractError("file_invalid", f"required path is not a regular file: {path}")
        if info.st_size > limit:
            raise ContractError("file_too_large", f"file exceeds the size limit: {path}")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > limit:
            raise ContractError("file_too_large", f"file exceeds the size limit: {path}")
        return content
    finally:
        os.close(descriptor)


def safe_read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(safe_read_bytes(path, 1024 * 1024))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("state_invalid", f"state file is invalid: {path}") from error
    if not isinstance(value, dict):
        raise ContractError("state_invalid", f"state file is invalid: {path}")
    return value


def agent_root(project_root: Path, create: bool = True) -> Path:
    root = project_root / ".agent-factory" / "agent"
    if create:
        ensure_directory(root, project_root)
    return root


def agent_directory(project_root: Path, agent_id: str, create: bool = False) -> Path:
    validate_id(agent_id, AGENT_ID, "agent_id")
    path = agent_root(project_root, create=create) / agent_id
    if create:
        ensure_directory(path, project_root)
    return path


def run_directory(
    project_root: Path, agent_id: str, run_id: str, create: bool = False
) -> Path:
    validate_id(run_id, AGENT_ID, "run_id")
    path = agent_directory(project_root, agent_id, create=create) / "runs" / run_id
    if create:
        ensure_directory(path, project_root)
    return path


@contextlib.contextmanager
def file_lock(path: Path) -> Iterator[None]:
    reject_symlink(path)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    stream = os.fdopen(descriptor, "a+")
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        except BlockingIOError as error:
            raise ContractError("lock_busy", "session is busy") from error
        yield
    finally:
        stream.close()


def update_json(
    path: Path, lock_path: Path, change: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    with file_lock(lock_path):
        value = safe_read_json(path)
        change(value)
        value["updatedAt"] = now()
        atomic_write_json(path, value)
        return value


def role_path(role: str) -> Path:
    validate_id(role, ROLE_ID, "role")
    path = REFERENCES / f"{role}.md"
    reject_symlink(path)
    try:
        info = path.stat()
    except FileNotFoundError as error:
        raise ContractError("role_not_found", f"Agent role was not found: {role}") from error
    if not stat.S_ISREG(info.st_mode):
        raise ContractError("role_invalid", "Agent role is not a regular file")
    return path


def read_request(args: argparse.Namespace) -> bytes:
    if args.request_file is not None:
        source = args.request_file.resolve(strict=False)
        return safe_read_bytes(source, MAX_REQUEST_BYTES)
    if args.message is not None:
        content = args.message.encode()
    elif not sys.stdin.isatty():
        content = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    else:
        raise ContractError(
            "request_missing", "provide --request-file, --message, or piped stdin"
        )
    if len(content) > MAX_REQUEST_BYTES:
        raise ContractError("request_too_large", "request exceeds the size limit")
    return content


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def session_file(project_root: Path, agent_id: str) -> Path:
    return agent_directory(project_root, agent_id) / "session.json"


def state_file(project_root: Path, agent_id: str, run_id: str) -> Path:
    return run_directory(project_root, agent_id, run_id) / "state.json"


def create_run(
    *,
    project_root: Path,
    agent_id: str,
    actor: str,
    request: bytes,
    session: dict[str, Any],
    receipt_request_hash: str | None = None,
    reviewed_work_run_id: str | None = None,
) -> dict[str, Any]:
    run_id = new_run_id()
    directory = run_directory(project_root, agent_id, run_id, create=True)
    request_path = directory / "request.md"
    result_path = directory / "result.md"
    events_path = directory / "events.jsonl"
    heartbeat_path = directory / "heartbeat.json"
    response_schema = directory / "response.schema.json"
    receipt_path = directory / "receipt.json"
    receipt_schema = directory / "receipt.schema.json"
    request_hash = hashlib.sha256(request).hexdigest()
    atomic_write(request_path, request)
    atomic_write_json(
        response_schema,
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["completed", "needs-human-decision", "failed"],
                },
                "resultPath": {"type": "string", "const": str(result_path)},
            },
            "required": ["status", "resultPath"],
            "additionalProperties": False,
        },
    )
    role = str(session["role"])
    if role in {"work", "review"}:
        atomic_write_json(
            receipt_schema,
            receipt_schema_document(
                role=role,
                run_id=run_id,
                request_hash=receipt_request_hash or request_hash,
                reviewed_work_run_id=reviewed_work_run_id,
            ),
        )
    accepted_at = now()
    state = {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "agentId": agent_id,
        "role": session["role"],
        "actor": actor,
        "status": "accepted",
        "attempt": 0,
        "maxAttempts": session["maxAttempts"],
        "requestPath": str(request_path),
        "requestHash": request_hash,
        "statePath": str(directory / "state.json"),
        "resultPath": str(result_path),
        "eventsPath": str(events_path),
        "heartbeatPath": str(heartbeat_path),
        "responseSchemaPath": str(response_schema),
        "acceptedAt": accepted_at,
        "updatedAt": accepted_at,
        "workerPid": None,
        "codexPid": None,
        "cancelRequested": False,
        "unread": False,
        "error": None,
    }
    if role in {"work", "review"}:
        state.update(
            {
                "receiptPath": str(receipt_path),
                "receiptSchemaPath": str(receipt_schema),
                "receiptRequestHash": receipt_request_hash or request_hash,
            }
        )
    if role == "review":
        state["reviewedWorkRunId"] = reviewed_work_run_id
    atomic_write_json(directory / "state.json", state)
    atomic_write_json(
        heartbeat_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "runId": run_id,
            "attempt": 0,
            "sequence": 0,
            "status": "accepted",
            "workerPid": None,
            "codexPid": None,
            "observedAt": accepted_at,
        },
    )
    return state


def receipt_schema_document(
    *, role: str, run_id: str, request_hash: str, reviewed_work_run_id: str | None
) -> dict[str, Any]:
    tests = {
        "type": "object",
        "properties": {
            "run": {"const": False},
            "reason": {
                "const": (
                    "work-agent-prohibited" if role == "work" else "static-review-only"
                )
            },
        },
        "required": ["run", "reason"],
        "additionalProperties": False,
    }
    if role == "work":
        properties: dict[str, Any] = {
            "schemaVersion": {"const": SCHEMA_VERSION},
            "kind": {"const": "work-receipt"},
            "runId": {"const": run_id},
            "requestHash": {"const": request_hash},
            "outcome": {"const": "implemented"},
            "changedPaths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "addressedFindingIds": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "tests": tests,
        }
        required = list(properties)
    else:
        finding = {
            "type": "object",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "severity": {"enum": ["blocking", "advisory"]},
                "path": {"type": "string"},
                "location": {"type": "string"},
                "problem": {"type": "string", "minLength": 1},
                "evidence": {"type": "string", "minLength": 1},
                "correction": {"type": "string", "minLength": 1},
            },
            "required": [
                "id", "severity", "path", "location", "problem", "evidence", "correction"
            ],
            "additionalProperties": False,
        }
        reviewed_id_schema: dict[str, Any] = {"type": "string", "minLength": 1}
        if reviewed_work_run_id is not None:
            reviewed_id_schema = {"const": reviewed_work_run_id}
        properties = {
            "schemaVersion": {"const": SCHEMA_VERSION},
            "kind": {"const": "review-receipt"},
            "runId": {"const": run_id},
            "reviewedWorkRunId": reviewed_id_schema,
            "reviewedRequestHash": {"const": request_hash},
            "decision": {"enum": ["approved", "changes_requested"]},
            "findings": {"type": "array", "items": finding},
            "resolvedFindingIds": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "tests": tests,
        }
        required = list(properties)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ContractError("receipt_invalid", f"{label} contains unknown or missing fields")


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ContractError("receipt_invalid", f"{label} must be a string array")
    if len(set(value)) != len(value):
        raise ContractError("receipt_invalid", f"{label} must contain unique values")
    return value


def _require_managed_directory(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        raise ContractError("receipt_path_invalid", "managed run directory is missing") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ContractError("receipt_path_invalid", "managed run directory is unsafe")


def _require_managed_file(path: Path, *, allow_missing: bool = False) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        if allow_missing:
            return
        raise ContractError("receipt_path_invalid", "managed run file is missing") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ContractError("receipt_path_invalid", "managed run file is unsafe")


def validate_receipt(
    project_root: Path,
    state: dict[str, Any],
    *,
    agent_id: str,
    run_id: str,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    role = state.get("role")
    if role not in {"work", "review"}:
        raise ContractError("receipt_unexpected", "this Agent role has no receipt contract")
    validate_id(agent_id, AGENT_ID, "agent_id")
    validate_id(run_id, AGENT_ID, "run_id")
    if state.get("agentId") != agent_id or state.get("runId") != run_id:
        raise ContractError("receipt_path_invalid", "receipt Agent/run binding is invalid")
    managed_root = root / ".agent-factory" / "agent"
    agent_path = managed_root / agent_id
    runs_path = agent_path / "runs"
    run_path = runs_path / run_id
    for directory in (root / ".agent-factory", managed_root, agent_path, runs_path, run_path):
        _require_managed_directory(directory)
    canonical = {
        "statePath": run_path / "state.json",
        "resultPath": run_path / "result.md",
        "receiptSchemaPath": run_path / "receipt.schema.json",
        "receiptPath": run_path / "receipt.json",
    }
    for field, expected in canonical.items():
        if state.get(field) != str(expected):
            raise ContractError("receipt_path_invalid", f"{field} is not canonically bound")
    _require_managed_file(canonical["statePath"])
    _require_managed_file(canonical["resultPath"])
    _require_managed_file(canonical["receiptSchemaPath"])
    _require_managed_file(canonical["receiptPath"])
    receipt_path = canonical["receiptPath"]
    try:
        receipt = json.loads(safe_read_bytes(receipt_path, MAX_RECEIPT_BYTES))
    except FileNotFoundError as error:
        raise ContractError("receipt_missing", "Agent did not publish its receipt") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("receipt_invalid", "Agent receipt is malformed JSON") from error
    except ContractError as error:
        if error.code == "file_not_found":
            raise ContractError("receipt_missing", "Agent did not publish its receipt") from error
        raise ContractError("receipt_path_invalid", "Agent receipt path is unsafe") from error
    if not isinstance(receipt, dict):
        raise ContractError("receipt_invalid", "Agent receipt must be a JSON object")
    expected_hash = state.get("receiptRequestHash") or state.get("requestHash")
    tests = receipt.get("tests")
    if not isinstance(tests, dict):
        raise ContractError("receipt_invalid", "receipt tests proof is missing")
    _exact_keys(tests, {"run", "reason"}, "tests")
    expected_reason = "work-agent-prohibited" if role == "work" else "static-review-only"
    if tests != {"run": False, "reason": expected_reason}:
        raise ContractError("receipt_tests_invalid", "receipt must prove this role ran no tests")
    if role == "work":
        _exact_keys(
            receipt,
            {
                "schemaVersion", "kind", "runId", "requestHash", "outcome",
                "changedPaths", "addressedFindingIds", "tests",
            },
            "work receipt",
        )
        if (
            receipt.get("schemaVersion") != SCHEMA_VERSION
            or receipt.get("kind") != "work-receipt"
            or receipt.get("runId") != state.get("runId")
            or receipt.get("requestHash") != expected_hash
            or receipt.get("outcome") != "implemented"
        ):
            raise ContractError("receipt_binding_invalid", "work receipt binding is invalid")
        changed = _string_list(receipt.get("changedPaths"), "changedPaths")
        for changed_path in changed:
            candidate = Path(changed_path)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ContractError("receipt_invalid", "changedPaths must be bounded relative paths")
        _string_list(receipt.get("addressedFindingIds"), "addressedFindingIds")
        return receipt
    _exact_keys(
        receipt,
        {
            "schemaVersion", "kind", "runId", "reviewedWorkRunId",
            "reviewedRequestHash", "decision", "findings", "resolvedFindingIds", "tests",
        },
        "review receipt",
    )
    reviewed_work_run_id = receipt.get("reviewedWorkRunId")
    expected_work_run_id = state.get("reviewedWorkRunId")
    if (
        receipt.get("schemaVersion") != SCHEMA_VERSION
        or receipt.get("kind") != "review-receipt"
        or receipt.get("runId") != state.get("runId")
        or not isinstance(reviewed_work_run_id, str)
        or not AGENT_ID.fullmatch(reviewed_work_run_id)
        or (expected_work_run_id is not None and reviewed_work_run_id != expected_work_run_id)
        or receipt.get("reviewedRequestHash") != expected_hash
    ):
        raise ContractError("receipt_binding_invalid", "review receipt binding is invalid")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        raise ContractError("receipt_invalid", "findings must be an array")
    finding_ids: list[str] = []
    blocking = 0
    finding_fields = {"id", "severity", "path", "location", "problem", "evidence", "correction"}
    for finding in findings:
        if not isinstance(finding, dict):
            raise ContractError("receipt_invalid", "each finding must be an object")
        _exact_keys(finding, finding_fields, "finding")
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not finding_id:
            raise ContractError("receipt_invalid", "finding id is invalid")
        finding_ids.append(finding_id)
        if finding.get("severity") not in {"blocking", "advisory"}:
            raise ContractError("receipt_invalid", "finding severity is invalid")
        blocking += finding.get("severity") == "blocking"
        for field in ("path", "location", "problem", "evidence", "correction"):
            if not isinstance(finding.get(field), str):
                raise ContractError("receipt_invalid", f"finding {field} must be a string")
        if not finding["problem"] or not finding["evidence"] or not finding["correction"]:
            raise ContractError("receipt_invalid", "finding details must not be empty")
    if len(set(finding_ids)) != len(finding_ids):
        raise ContractError("receipt_invalid", "finding identifiers must be unique")
    resolved = _string_list(receipt.get("resolvedFindingIds"), "resolvedFindingIds")
    if set(resolved) & set(finding_ids):
        raise ContractError("receipt_invalid", "resolved and current finding identifiers overlap")
    decision = receipt.get("decision")
    if decision == "approved" and blocking != 0:
        raise ContractError("receipt_decision_invalid", "approved review has blocking findings")
    if decision == "changes_requested" and blocking == 0:
        raise ContractError("receipt_decision_invalid", "changes requested requires a blocking finding")
    if decision not in {"approved", "changes_requested"}:
        raise ContractError("receipt_decision_invalid", "review decision is invalid")
    return receipt


def create_session(args: argparse.Namespace, project_root: Path) -> dict[str, Any]:
    directory = agent_directory(project_root, args.agent, create=True)
    path = directory / "session.json"
    if path.exists():
        raise ContractError("agent_exists", "Agent already exists; use send")
    role = validate_id(args.role, ROLE_ID, "role")
    role_path(role)
    codex = args.codex
    if os.sep not in codex:
        from shutil import which

        resolved = which(codex)
        if resolved is None:
            raise ContractError("codex_not_found", "codex executable was not found")
        codex = resolved
    else:
        codex = str(Path(codex).resolve(strict=True))
    created_at = now()
    session = {
        "schemaVersion": SCHEMA_VERSION,
        "agentId": args.agent,
        "role": role,
        "sessionId": None,
        "projectRoot": str(project_root),
        "codex": codex,
        "sandbox": args.sandbox,
        "model": args.model,
        "heartbeatInterval": args.heartbeat_interval,
        "heartbeatTimeout": args.heartbeat_timeout,
        "startTimeout": args.start_timeout,
        "turnTimeout": args.turn_timeout,
        "maxAttempts": args.max_attempts,
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    atomic_write_json(path, session)
    return session


def load_session(project_root: Path, agent_id: str) -> dict[str, Any]:
    path = session_file(project_root, agent_id)
    session = safe_read_json(path)
    if session.get("agentId") != agent_id or session.get("projectRoot") != str(project_root):
        raise ContractError("session_invalid", "Agent session binding is invalid")
    session_id = session.get("sessionId")
    if session_id is not None and (
        not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id)
    ):
        raise ContractError("session_invalid", "Codex session identifier is invalid")
    role_path(str(session.get("role", "")))
    return session


def spawn_worker(project_root: Path, agent_id: str, run_id: str) -> int:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--project-root",
        str(project_root),
        "--agent",
        agent_id,
        "--run-id",
        run_id,
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as error:
        raise ContractError("worker_start_failed", "background worker could not start") from error
    path = state_file(project_root, agent_id, run_id)
    update_json(
        path,
        path.parent / ".state.lock",
        lambda state: state.update({"workerPid": process.pid, "status": "queued"}),
    )
    return process.pid


def submit(args: argparse.Namespace, new_agent: bool) -> int:
    project_root = resolve_project_root(args.project_root)
    validate_id(args.agent, AGENT_ID, "agent_id")
    if args.actor not in ACTORS:
        raise ContractError("actor_invalid", "actor is invalid")
    request = read_request(args)
    try:
        request_text = request.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("request_invalid", "request must be UTF-8 text") from error
    if not request_text.strip():
        raise ContractError("request_invalid", "request must not be empty")
    receipt_request_hash = getattr(args, "receipt_request_hash", None)
    reviewed_work_run_id = getattr(args, "reviewed_work_run_id", None)
    if receipt_request_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", receipt_request_hash):
        raise ContractError("receipt_binding_invalid", "receipt request hash is invalid")
    if reviewed_work_run_id is not None:
        validate_id(reviewed_work_run_id, AGENT_ID, "run_id")
    role = args.role if new_agent else load_session(project_root, args.agent).get("role")
    if role == "review" and reviewed_work_run_id is None:
        raise ContractError(
            "receipt_binding_invalid",
            "Review runs require the exact reviewed Work run identifier",
        )
    if role != "review" and reviewed_work_run_id is not None:
        raise ContractError(
            "receipt_binding_invalid",
            "reviewed Work run binding is valid only for Review runs",
        )
    session = create_session(args, project_root) if new_agent else load_session(
        project_root, args.agent
    )
    state = create_run(
        project_root=project_root,
        agent_id=args.agent,
        actor=args.actor,
        request=request,
        session=session,
        receipt_request_hash=receipt_request_hash,
        reviewed_work_run_id=reviewed_work_run_id,
    )
    worker_pid = spawn_worker(project_root, args.agent, state["runId"])
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "ack",
            "status": "accepted",
            "agentId": args.agent,
            "runId": state["runId"],
            "workerPid": worker_pid,
            "statePath": str(state_file(project_root, args.agent, state["runId"])),
        }
    )
    return 0


class Heartbeat:
    def __init__(self, path: Path, state_path: Path, interval: float) -> None:
        self.path = path
        self.state_path = state_path
        self.interval = interval
        self.stop_event = threading.Event()
        self.sequence = 0
        self.status = "queued"
        self.attempt = 0
        self.codex_pid: int | None = None
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._write()
        self.thread.start()

    def update(self, *, status: str, attempt: int, codex_pid: int | None) -> None:
        with self.lock:
            self.status = status
            self.attempt = attempt
            self.codex_pid = codex_pid
        self._write()

    def close(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=max(1.0, self.interval * 2))
        self._write()

    def _run(self) -> None:
        while not self.stop_event.wait(self.interval):
            with contextlib.suppress(Exception):
                self._write()

    def _write(self) -> None:
        with self.lock:
            self.sequence += 1
            value = {
                "schemaVersion": SCHEMA_VERSION,
                "runId": self.state_path.parent.name,
                "attempt": self.attempt,
                "sequence": self.sequence,
                "status": self.status,
                "workerPid": os.getpid(),
                "codexPid": self.codex_pid,
                "observedAt": now(),
            }
        atomic_write_json(self.path, value)


class AttemptFailure(Exception):
    def __init__(self, code: str, message: str, started: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.started = started


def build_prompt(
    *,
    agent_id: str,
    role: str,
    request_path: Path,
    result_path: Path,
    run_id: str,
    receipt_path: Path | None = None,
    receipt_schema_path: Path | None = None,
) -> str:
    receipt_obligation = ""
    if receipt_path is not None and receipt_schema_path is not None:
        receipt_obligation = f"""
For a `completed` result, also write the role-specific machine receipt to
`{receipt_path}`. Its exact contract is `{receipt_schema_path}`. The receipt
must bind this run and request exactly, contain no unknown fields, and prove
that this role ran no tests. A completed run with a missing or invalid receipt
will fail at the runtime boundary.
"""
    return f"""Act as Agent `{agent_id}` for Agent Factory.

Read the common Agent contract at `{SKILL_ROOT / 'SKILL.md'}` and the complete
role contract at `{role_path(role)}`. Read the delegated request from
`{request_path}`. Keep its scope and authority unchanged.

Write the detailed result to `{result_path}`. Then return only the compact JSON
required by the supplied output schema. Run ID: `{run_id}`.
{receipt_obligation}"""


def build_codex_command(
    session: dict[str, Any], state: dict[str, Any], session_id: str | None
) -> list[str]:
    codex = str(session["codex"])
    common = ["--json", "--output-schema", str(state["responseSchemaPath"])]
    model = session.get("model")
    if model:
        common.extend(["--model", str(model)])
    if session_id is None:
        return [
            codex,
            "exec",
            "--cd",
            str(session["projectRoot"]),
            "--sandbox",
            str(session["sandbox"]),
            *common,
            "-",
        ]
    return [
        codex,
        "exec",
        "--cd",
        str(session["projectRoot"]),
        "--sandbox",
        str(session["sandbox"]),
        "resume",
        *common,
        session_id,
        "-",
    ]


def stderr_reports_sandbox_unavailable(path: Path) -> bool:
    try:
        stderr = safe_read_bytes(path, MAX_EVENT_BYTES).decode("utf-8")
    except (ContractError, UnicodeDecodeError):
        return False
    return all(fragment in stderr for fragment in SANDBOX_UNAVAILABLE_STDERR)


def missing_result_failure(stderr_path: Path) -> AttemptFailure:
    if stderr_reports_sandbox_unavailable(stderr_path):
        return AttemptFailure(
            "sandbox_unavailable",
            "Codex filesystem sandbox is unavailable",
            True,
        )
    return AttemptFailure(
        "result_file_missing",
        "Agent did not publish its result file",
        True,
    )


def append_event(path: Path, line: str) -> None:
    reject_symlink(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, line.encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_process_lines(stream: IO[str], output: queue.Queue[tuple[str, str | None]]) -> None:
    try:
        for line in stream:
            output.put(("line", line))
    except (OSError, UnicodeError):
        output.put(("error", None))
    finally:
        output.put(("eof", None))


def terminate_process(process: subprocess.Popen[str]) -> None:
    with contextlib.suppress(OSError):
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)


def cancel_requested(state_path: Path, cancel_event: threading.Event) -> bool:
    if cancel_event.is_set():
        return True
    with contextlib.suppress(ContractError):
        return bool(safe_read_json(state_path).get("cancelRequested"))
    return False


def run_codex_attempt(
    *,
    project_root: Path,
    session: dict[str, Any],
    state: dict[str, Any],
    attempt: int,
    heartbeat: Heartbeat,
    cancel_event: threading.Event,
    expected_agent_id: str,
    expected_run_id: str,
) -> tuple[str, str]:
    state_path = Path(state["requestPath"]).parent / "state.json"
    request = safe_read_bytes(Path(state["requestPath"]), MAX_REQUEST_BYTES)
    if hashlib.sha256(request).hexdigest() != state.get("requestHash"):
        raise AttemptFailure("request_changed", "managed request content changed", False)
    existing_session = session.get("sessionId")
    command = build_codex_command(session, state, existing_session)
    stderr_path = state_path.parent / "stderr.log"
    reject_symlink(stderr_path)
    stderr_flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        stderr_flags |= os.O_NOFOLLOW
    stderr_fd = os.open(stderr_path, stderr_flags, 0o600)
    stderr_stream = os.fdopen(stderr_fd, "a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            command,
            cwd=project_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_stream,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
        )
    except OSError as error:
        stderr_stream.close()
        raise AttemptFailure("codex_start_failed", "codex exec could not start", False) from error
    heartbeat.update(status="starting", attempt=attempt, codex_pid=process.pid)
    update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"status": "starting", "attempt": attempt, "codexPid": process.pid}
        ),
    )
    if process.stdin is None or process.stdout is None:
        terminate_process(process)
        stderr_stream.close()
        raise AttemptFailure("codex_start_failed", "codex exec pipes are unavailable", False)
    prompt = build_prompt(
        agent_id=str(state["agentId"]),
        role=str(state["role"]),
        request_path=Path(state["requestPath"]),
        result_path=Path(state["resultPath"]),
        run_id=str(state["runId"]),
        receipt_path=(Path(state["receiptPath"]) if state.get("receiptPath") else None),
        receipt_schema_path=(
            Path(state["receiptSchemaPath"]) if state.get("receiptSchemaPath") else None
        ),
    )
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except (BrokenPipeError, OSError, UnicodeError) as error:
        terminate_process(process)
        stderr_stream.close()
        raise AttemptFailure("codex_write_failed", "codex exec rejected the prompt", False) from error
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threading.Thread(
        target=read_process_lines, args=(process.stdout, lines), daemon=True
    ).start()
    started = False
    active_session: str | None = None
    final_messages: list[str] = []
    started_at = time.monotonic()
    start_deadline = started_at + float(session["startTimeout"])
    turn_deadline = started_at + float(session["turnTimeout"])
    try:
        while True:
            if cancel_requested(state_path, cancel_event):
                terminate_process(process)
                raise AttemptFailure("cancelled", "run was cancelled", started)
            current = time.monotonic()
            if not started and current >= start_deadline:
                terminate_process(process)
                raise AttemptFailure("start_timeout", "codex exec sent no start ACK", False)
            if current >= turn_deadline:
                terminate_process(process)
                raise AttemptFailure("turn_timeout", "codex exec exceeded its turn timeout", started)
            try:
                kind, line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "error":
                terminate_process(process)
                raise AttemptFailure("event_read_failed", "codex event stream failed", started)
            if kind == "eof":
                break
            if line is None or len(line.encode()) > MAX_EVENT_BYTES:
                terminate_process(process)
                raise AttemptFailure("event_invalid", "codex emitted an invalid event", started)
            append_event(Path(state["eventsPath"]), line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                terminate_process(process)
                raise AttemptFailure("event_invalid", "codex emitted malformed JSONL", started) from error
            if not isinstance(event, dict):
                terminate_process(process)
                raise AttemptFailure("event_invalid", "codex emitted an invalid event", started)
            if event.get("type") == "thread.started":
                observed = event.get("thread_id")
                if not isinstance(observed, str) or not SESSION_ID.fullmatch(observed):
                    terminate_process(process)
                    raise AttemptFailure("session_invalid", "codex returned an invalid session", started)
                if existing_session is not None and observed != existing_session:
                    terminate_process(process)
                    raise AttemptFailure("session_mismatch", "codex resumed a different session", started)
                active_session = observed
                started = True
                heartbeat.update(status="running", attempt=attempt, codex_pid=process.pid)
                update_json(
                    state_path,
                    state_path.parent / ".state.lock",
                    lambda value: value.update(
                        {"status": "running", "sessionId": observed, "startedAt": now()}
                    ),
                )
                if existing_session is None:
                    session_path = session_file(project_root, str(state["agentId"]))
                    session = update_json(
                        session_path,
                        session_path.parent / ".session-state.lock",
                        lambda value: value.update({"sessionId": observed}),
                    )
            item = event.get("item") if event.get("type") == "item.completed" else None
            if isinstance(item, dict) and item.get("type") in (None, "agent_message"):
                text = item.get("text")
                if isinstance(text, str):
                    final_messages.append(text)
        return_code = process.wait(timeout=10)
    except subprocess.TimeoutExpired as error:
        terminate_process(process)
        raise AttemptFailure("codex_exit_timeout", "codex exec did not exit", started) from error
    finally:
        stderr_stream.close()
    if return_code != 0:
        raise AttemptFailure("codex_failed", f"codex exec exited with {return_code}", started)
    if not started or active_session is None:
        raise AttemptFailure("start_ack_missing", "codex exec returned no start ACK", False)
    if not final_messages:
        raise AttemptFailure("result_missing", "codex exec returned no terminal result", True)
    try:
        terminal = json.loads(final_messages[-1])
    except json.JSONDecodeError as error:
        raise AttemptFailure("result_invalid", "codex returned invalid terminal JSON", True) from error
    valid = (
        isinstance(terminal, dict)
        and set(terminal) == {"status", "resultPath"}
        and terminal.get("status") in {"completed", "needs-human-decision", "failed"}
        and terminal.get("resultPath") == state["resultPath"]
    )
    if not valid:
        raise AttemptFailure("result_invalid", "codex returned an invalid terminal result", True)
    result_path = Path(state["resultPath"])
    try:
        result_info = os.lstat(result_path)
    except FileNotFoundError as error:
        raise missing_result_failure(stderr_path) from error
    if (
        stat.S_ISLNK(result_info.st_mode)
        or not stat.S_ISREG(result_info.st_mode)
        or result_info.st_size == 0
    ):
        raise AttemptFailure("result_file_invalid", "Agent result path is unsafe", True)
    if terminal["status"] == "completed" and state.get("role") in {"work", "review"}:
        try:
            validate_receipt(
                project_root,
                state,
                agent_id=expected_agent_id,
                run_id=expected_run_id,
            )
        except ContractError as error:
            raise AttemptFailure(error.code, error.message, True) from error
    return str(terminal["status"]), active_session


def mark_terminal(
    state_path: Path, status: str, error: dict[str, str] | None = None
) -> None:
    def change(value: dict[str, Any]) -> None:
        value.update(
            {
                "status": status,
                "codexPid": None,
                "finishedAt": now(),
                "unread": True,
                "error": error,
            }
        )

    update_json(state_path, state_path.parent / ".state.lock", change)


def worker(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state_path = state_file(project_root, args.agent, args.run_id)
    state = safe_read_json(state_path)
    session = load_session(project_root, args.agent)
    heartbeat = Heartbeat(
        Path(state["heartbeatPath"]), state_path, float(session["heartbeatInterval"])
    )
    cancel_event = threading.Event()

    def request_cancel(_signum: int, _frame: object) -> None:
        cancel_event.set()

    signal.signal(signal.SIGTERM, request_cancel)
    signal.signal(signal.SIGINT, request_cancel)
    heartbeat.start()
    lock_path = agent_directory(project_root, args.agent) / ".session.lock"
    try:
        with file_lock(lock_path):
            state = safe_read_json(state_path)
            if state.get("status") in TERMINAL_STATES:
                return 0
            if state.get("cancelRequested") is True:
                mark_terminal(state_path, "cancelled")
                heartbeat.update(status="cancelled", attempt=0, codex_pid=None)
                return 1
            max_attempts = int(state["maxAttempts"])
            last_failure: AttemptFailure | None = None
            while int(state.get("attempt", 0)) < max_attempts:
                attempt = int(state.get("attempt", 0)) + 1
                try:
                    terminal_status, _session_id = run_codex_attempt(
                        project_root=project_root,
                        session=load_session(project_root, args.agent),
                        state=safe_read_json(state_path),
                        attempt=attempt,
                        heartbeat=heartbeat,
                        cancel_event=cancel_event,
                        expected_agent_id=args.agent,
                        expected_run_id=args.run_id,
                    )
                    mark_terminal(state_path, terminal_status)
                    heartbeat.update(
                        status=terminal_status, attempt=attempt, codex_pid=None
                    )
                    return 0 if terminal_status != "failed" else 1
                except AttemptFailure as failure:
                    last_failure = failure
                    state = update_json(
                        state_path,
                        state_path.parent / ".state.lock",
                        lambda value: value.update(
                            {"attempt": attempt, "codexPid": None, "status": "queued"}
                        ),
                    )
                    if failure.code == "cancelled":
                        mark_terminal(state_path, "cancelled")
                        heartbeat.update(status="cancelled", attempt=attempt, codex_pid=None)
                        return 1
                    if failure.started or attempt >= max_attempts:
                        break
                    heartbeat.update(status="queued", attempt=attempt, codex_pid=None)
            failure = last_failure or AttemptFailure(
                "attempts_exhausted", "no execution attempt remained", False
            )
            mark_terminal(
                state_path,
                "failed",
                {"code": failure.code, "message": failure.message},
            )
            heartbeat.update(
                status="failed", attempt=int(state.get("attempt", 0)), codex_pid=None
            )
            return 1
    except ContractError as error:
        with contextlib.suppress(Exception):
            mark_terminal(
                state_path, "failed", {"code": error.code, "message": error.message}
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        with contextlib.suppress(Exception):
            mark_terminal(
                state_path,
                "failed",
                {"code": "worker_failure", "message": str(error)},
            )
        heartbeat.update(status="failed", attempt=0, codex_pid=None)
        return 1
    finally:
        heartbeat.close()


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "runId",
        "agentId",
        "role",
        "actor",
        "status",
        "attempt",
        "maxAttempts",
        "sessionId",
        "requestPath",
        "statePath",
        "resultPath",
        "receiptPath",
        "receiptSchemaPath",
        "receiptRequestHash",
        "reviewedWorkRunId",
        "eventsPath",
        "heartbeatPath",
        "acceptedAt",
        "startedAt",
        "finishedAt",
        "updatedAt",
        "workerPid",
        "codexPid",
        "unread",
        "error",
    )
    public = {key: state.get(key) for key in keys if key in state}
    if state.get("role") not in {"work", "review"}:
        public.pop("statePath", None)
    return public


def find_run(project_root: Path, agent_id: str, run_id: str) -> dict[str, Any]:
    return safe_read_json(state_file(project_root, agent_id, run_id))


def command_status(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    state = find_run(root, args.agent, args.run_id)
    heartbeat_path = Path(state["heartbeatPath"])
    heartbeat = safe_read_json(heartbeat_path)
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "status",
            "run": public_state(state),
            "heartbeat": heartbeat,
        }
    )
    return 0


def command_result(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    state = find_run(root, args.agent, args.run_id)
    if state.get("status") not in TERMINAL_STATES:
        raise ContractError("result_not_ready", "run has no terminal result")
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "result",
            "run": public_state(state),
        }
    )
    if args.ack:
        path = state_file(root, args.agent, args.run_id)
        update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update({"unread": False, "readAt": now()}),
        )
    return 0


def iter_agent_directories(root: Path) -> Iterator[Path]:
    agents = agent_root(root, create=False)
    if not agents.exists():
        return
    reject_symlink(agents)
    for item in sorted(agents.iterdir(), key=lambda path: path.name):
        if AGENT_ID.fullmatch(item.name) and item.is_dir() and not item.is_symlink():
            yield item


def command_list(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    agents = []
    for directory in iter_agent_directories(root):
        with contextlib.suppress(ContractError):
            agents.append(safe_read_json(directory / "session.json"))
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "agent-list",
            "agents": agents,
        }
    )
    return 0


def iter_run_states(root: Path, selected_agent: str | None = None) -> Iterator[dict[str, Any]]:
    for directory in iter_agent_directories(root):
        if selected_agent is not None and directory.name != selected_agent:
            continue
        runs = directory / "runs"
        if not runs.exists() or runs.is_symlink():
            continue
        for item in sorted(runs.iterdir(), key=lambda path: path.name):
            if item.is_dir() and not item.is_symlink():
                with contextlib.suppress(ContractError):
                    yield safe_read_json(item / "state.json")


def command_inbox(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    if args.agent is not None:
        validate_id(args.agent, AGENT_ID, "agent_id")
    states = [
        state
        for state in iter_run_states(root, args.agent)
        if state.get("status") in TERMINAL_STATES and state.get("unread") is True
    ]
    states.sort(key=lambda value: str(value.get("finishedAt", value.get("updatedAt", ""))))
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "inbox",
            "runs": [public_state(state) for state in states],
        }
    )
    if args.ack:
        for state in states:
            path = state_file(root, str(state["agentId"]), str(state["runId"]))
            update_json(
                path,
                path.parent / ".state.lock",
                lambda value: value.update({"unread": False, "readAt": now()}),
            )
    return 0


def pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def command_cancel(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    path = state_file(root, args.agent, args.run_id)
    state = safe_read_json(path)
    if state.get("status") in TERMINAL_STATES:
        raise ContractError("run_terminal", "run is already terminal")
    state = update_json(
        path,
        path.parent / ".state.lock",
        lambda value: value.update({"cancelRequested": True, "status": "cancelling"}),
    )
    worker_pid = state.get("workerPid")
    if isinstance(worker_pid, int) and worker_pid > 0:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(worker_pid, signal.SIGTERM)
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "ack",
            "status": "cancelling",
            "agentId": args.agent,
            "runId": args.run_id,
        }
    )
    return 0


def heartbeat_stale(state: dict[str, Any], session: dict[str, Any]) -> bool:
    try:
        heartbeat = safe_read_json(Path(state["heartbeatPath"]))
    except ContractError:
        return True
    observed = parse_time(heartbeat.get("observedAt"))
    return observed is None or time.time() - observed > float(session["heartbeatTimeout"])


def command_reconcile(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    if args.agent is not None:
        validate_id(args.agent, AGENT_ID, "agent_id")
    reconciled: list[dict[str, Any]] = []
    for state in iter_run_states(root, args.agent):
        if state.get("status") not in ACTIVE_STATES:
            continue
        agent_id = str(state["agentId"])
        session = load_session(root, agent_id)
        if not heartbeat_stale(state, session):
            continue
        if pid_alive(state.get("workerPid")) or pid_alive(state.get("codexPid")):
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
            )
            continue
        if int(state.get("attempt", 0)) >= int(state.get("maxAttempts", 1)):
            path = state_file(root, agent_id, str(state["runId"]))
            mark_terminal(
                path,
                "failed",
                {"code": "heartbeat_timeout", "message": "worker heartbeat expired"},
            )
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "failed"}
            )
            continue
        pid = spawn_worker(root, agent_id, str(state["runId"]))
        reconciled.append(
            {
                "agentId": agent_id,
                "runId": state["runId"],
                "action": "resubmitted",
                "workerPid": pid,
            }
        )
    emit(
        {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "reconcile",
            "runs": reconciled,
        }
    )
    return 0


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-root", type=Path, default=Path.cwd())


def add_request_arguments(parser: argparse.ArgumentParser) -> None:
    request = parser.add_mutually_exclusive_group()
    request.add_argument("--request-file", type=Path)
    request.add_argument("--message")
    parser.add_argument("--actor", choices=ACTORS, default="main")
    parser.add_argument(
        "--receipt-request-hash",
        help="SHA-256 identity the role receipt must bind (defaults to this run request)",
    )
    parser.add_argument(
        "--reviewed-work-run-id",
        help="exact Work run reviewed by a Review Agent (required for Review runs)",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(prog="agent_exec.py")
    commands = parser.add_subparsers(dest="command", required=True)

    submit_parser = commands.add_parser("submit")
    add_project_argument(submit_parser)
    add_request_arguments(submit_parser)
    submit_parser.add_argument("--agent", required=True)
    submit_parser.add_argument("--role", required=True)
    submit_parser.add_argument("--codex", default="codex")
    submit_parser.add_argument("--sandbox", choices=SANDBOXES, default="workspace-write")
    submit_parser.add_argument("--model")
    submit_parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    submit_parser.add_argument("--heartbeat-timeout", type=float, default=20.0)
    submit_parser.add_argument("--start-timeout", type=float, default=60.0)
    submit_parser.add_argument("--turn-timeout", type=float, default=1800.0)
    submit_parser.add_argument("--max-attempts", type=int, default=2)

    send_parser = commands.add_parser("send")
    add_project_argument(send_parser)
    add_request_arguments(send_parser)
    send_parser.add_argument("--agent", required=True)

    for name in ("status", "result", "cancel"):
        command_parser = commands.add_parser(name)
        add_project_argument(command_parser)
        command_parser.add_argument("--agent", required=True)
        command_parser.add_argument("--run-id", required=True)
        if name == "result":
            command_parser.add_argument("--ack", action="store_true")

    list_parser = commands.add_parser("list")
    add_project_argument(list_parser)

    inbox_parser = commands.add_parser("inbox")
    add_project_argument(inbox_parser)
    inbox_parser.add_argument("--agent")
    inbox_parser.add_argument("--ack", action="store_true")

    reconcile_parser = commands.add_parser("reconcile")
    add_project_argument(reconcile_parser)
    reconcile_parser.add_argument("--agent")

    worker_parser = commands.add_parser("_worker", help=argparse.SUPPRESS)
    add_project_argument(worker_parser)
    worker_parser.add_argument("--agent", required=True)
    worker_parser.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def validate_submit_options(args: argparse.Namespace) -> None:
    positive = {
        "heartbeat interval": args.heartbeat_interval,
        "heartbeat timeout": args.heartbeat_timeout,
        "start timeout": args.start_timeout,
        "turn timeout": args.turn_timeout,
    }
    for label, value in positive.items():
        if value <= 0:
            raise ContractError("invalid_timeout", f"{label} must be positive")
    if args.heartbeat_timeout <= args.heartbeat_interval:
        raise ContractError(
            "invalid_timeout", "heartbeat timeout must exceed heartbeat interval"
        )
    if args.max_attempts < 1 or args.max_attempts > 10:
        raise ContractError("invalid_attempts", "max attempts must be between 1 and 10")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        if args.command == "submit":
            validate_submit_options(args)
            return submit(args, True)
        if args.command == "send":
            return submit(args, False)
        if args.command == "status":
            return command_status(args)
        if args.command == "result":
            return command_result(args)
        if args.command == "list":
            return command_list(args)
        if args.command == "inbox":
            return command_inbox(args)
        if args.command == "cancel":
            return command_cancel(args)
        if args.command == "reconcile":
            return command_reconcile(args)
        if args.command == "_worker":
            return worker(args)
        raise ContractError("invalid_command", "command is invalid")
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        emit(error_document("runtime_failure", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
