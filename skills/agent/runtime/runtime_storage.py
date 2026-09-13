"""Managed runtime filesystem, identity, and atomic persistence primitives."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, IO, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

from process_containment import now
from runtime_errors import ContractError
from capability_contracts import safe_read_caller_file

SCHEMA_VERSION = "0.1.0"
AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ROLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_REQUEST_BYTES = 8 * 1024 * 1024
SKILL_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = SKILL_ROOT / "prompt"
VALID_ROLES = {"main", "work", "verification"}
if sys.platform == "linux":
    import paths as runtime_paths

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
    runtime_paths.inspect(anchor)
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
    return runtime_paths.anchor(path)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
    )


def safe_read_bytes(path: Path, limit: int) -> bytes:
    try:
        return safe_read_caller_file(path, limit)
    except ContractError as error:
        if not path.exists():
            raise ContractError("file_not_found", f"required file was not found: {path}") from error
        raise


def safe_read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(safe_read_bytes(path, 1024 * 1024))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("state_invalid", f"state file is invalid: {path}") from error
    if not isinstance(value, dict):
        raise ContractError("state_invalid", f"state file is invalid: {path}")
    return runtime_paths.project_json(path, value)


def agent_root(project_root: Path, create: bool = True) -> Path:
    binding = runtime_paths.resolve(project_root, create=create)
    runtime_paths.require_ready(binding)
    if not binding["registered"]:
        raise ContractError("project_uninitialized", "project has no registered runtime; use exec.py init")
    return Path(binding["agentsRoot"])


def agent_directory(project_root: Path, agent_id: str, create: bool = False) -> Path:
    validate_id(agent_id, AGENT_ID, "agent_id")
    path = agent_root(project_root, create=create) / agent_id
    if create:
        ensure_directory(path, find_project_anchor(path))
    return path


def run_directory(
    project_root: Path, agent_id: str, run_id: str, create: bool = False
) -> Path:
    validate_id(run_id, AGENT_ID, "run_id")
    path = agent_directory(project_root, agent_id, create=create) / "runs" / run_id
    if create:
        ensure_directory(path, find_project_anchor(path))
    return path


@contextlib.contextmanager
def file_lock(path: Path, *, blocking: bool = True) -> Iterator[None]:
    reject_symlink(path)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        os.close(descriptor)
        raise ContractError("runtime_path_unsafe", "runtime lock must be a regular file")
    stream = os.fdopen(descriptor, "a+")
    try:
        try:
            if fcntl is not None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            else:
                stream.seek(0)
                if stream.read(1) == "":
                    stream.write("\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        except (BlockingIOError, OSError) as error:
            raise ContractError("lock_busy", "session is busy") from error
        yield
    finally:
        if fcntl is None:
            with contextlib.suppress(OSError):
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
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
    if role not in VALID_ROLES:
        raise ContractError("role_not_found", f"Agent role was not found: {role}")
    path = PROMPTS / f"{role}.md"
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
        return safe_read_bytes(args.request_file, MAX_REQUEST_BYTES)
    if args.message is not None:
        content = args.message.encode()
    elif not sys.stdin.isatty():
        content = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    else:
        raise ContractError(
            "request_missing", "provide --request-file, --message, --input-file, or piped stdin"
        )
    if len(content) > MAX_REQUEST_BYTES:
        raise ContractError("request_too_large", "request exceeds the size limit")
    return content


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def session_file(project_root: Path, agent_id: str) -> Path:
    return agent_directory(project_root, agent_id) / "session.json"


def dispatch_reservation_file(
    project_root: Path, agent_id: str, dispatch_id: str
) -> Path:
    return agent_directory(project_root, agent_id, create=True) / "dispatches" / f"{dispatch_id}.json"


def state_file(project_root: Path, agent_id: str, run_id: str) -> Path:
    return run_directory(project_root, agent_id, run_id) / "state.json"
