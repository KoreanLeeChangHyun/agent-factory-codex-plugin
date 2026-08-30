#!/usr/bin/env python3
"""Manage resumable Codex exec roles without blocking the Main Agent."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import queue
import re
import select
import shutil
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

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]
    import msvcrt


SCHEMA_VERSION = "0.1.0"
AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ROLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
DISPATCH_ID = re.compile(r"^dispatch-[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
DEFAULT_SANDBOX = "danger-full-access"
ACTORS = ("main", "human")
ACTIVE_STATES = {"accepted", "queued", "starting", "running", "cancelling"}
TERMINAL_STATES = {"completed", "needs-human-decision", "failed", "cancelled"}
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_EVENTS_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 4 * 1024 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_CAPABILITY_BINDING_BYTES = 256 * 1024
PROCESS_TERM_TIMEOUT = 5.0
PROCESS_KILL_TIMEOUT = 5.0
CONTAINMENT_START_TIMEOUT = 5.0
CONTAINMENT_QUERY_TIMEOUT = 2.0
SYSTEMD_UNIT = re.compile(r"^agent-factory-[a-f0-9]{24}\.service$")
SYSTEMD_DESCRIPTION_PREFIX = "Agent Factory containment "
SYSTEMD_REQUIRED_OPTIONS = (
    "--collect",
    "--service-type=",
    "--property=",
    "--working-directory=",
    "--unit=",
    "--description=",
    "--user",
)
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CGROUP_ROOT = Path("/sys/fs/cgroup")
SANDBOX_UNAVAILABLE_STDERR = (
    "fs sandbox helper failed with status",
    "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted",
)
SKILL_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = SKILL_ROOT / "prompt"
VALID_ROLES = {"main", "work", "verification"}
CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AUTHORITY_KINDS = {
    "native-executable", "project-cli", "mcp-server", "plugin",
    "host-capability", "external-provider",
}
CAPABILITY_OUTCOMES = {"succeeded", "failed", "unknown", "not-invoked"}


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


def linux_boot_id() -> str:
    if sys.platform != "linux":
        raise ContractError(
            "process_identity_unsupported",
            "managed process identity requires Linux /proc",
        )
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii"
        ).strip()
    except (OSError, UnicodeError) as error:
        raise ContractError(
            "process_identity_unavailable", "Linux boot identity is unavailable"
        ) from error
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        raise ContractError(
            "process_identity_unavailable", "Linux boot identity is invalid"
        )
    return value.lower()


def linux_process_identity(pid: int) -> dict[str, Any]:
    if not isinstance(pid, int) or pid <= 0:
        raise ContractError("process_identity_invalid", "process PID is invalid")
    try:
        stat_line = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError as error:
        raise ContractError(
            "process_not_found", "managed process no longer exists"
        ) from error
    except (OSError, UnicodeError) as error:
        raise ContractError(
            "process_identity_unavailable", "managed process identity is unreadable"
        ) from error
    closing = stat_line.rfind(")")
    fields = stat_line[closing + 2 :].split() if closing >= 0 else []
    if len(fields) <= 19 or not fields[19].isdigit():
        raise ContractError(
            "process_identity_unavailable", "managed process stat identity is invalid"
        )
    return {"pid": pid, "bootId": linux_boot_id(), "startTicks": int(fields[19])}


def process_identity_status(identity: object) -> str:
    if not isinstance(identity, dict) or set(identity) != {
        "pid",
        "bootId",
        "startTicks",
    }:
        return "unknown"
    pid = identity.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return "unknown"
    try:
        observed = linux_process_identity(pid)
    except ContractError as error:
        if error.code == "process_not_found":
            return "dead"
        return "unknown"
    return "match" if observed == identity else "mismatch"


def _systemd_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), capture_output=True, text=True, encoding="utf-8",
            errors="strict", timeout=CONTAINMENT_QUERY_TIMEOUT, check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        raise ContractError(
            "containment_backend_unavailable", "the user systemd manager is unavailable"
        ) from error


def systemd_environment_supported(environment: dict[str, str] | None = None) -> bool:
    values = os.environ if environment is None else environment
    return hasattr(os, "memfd_create") and all(
        ENVIRONMENT_NAME.fullmatch(name) is not None
        and "\0" not in value
        and "\n" not in value
        and "\r" not in value
        for name, value in values.items()
    )


def cgroup_v2_available() -> bool:
    return (CGROUP_ROOT / "cgroup.controllers").is_file()


def systemd_manager_usable() -> bool:
    if sys.platform != "linux" or shutil.which("systemd-run") is None or shutil.which("systemctl") is None:
        return False
    if not cgroup_v2_available() or not systemd_environment_supported():
        return False
    try:
        manager_probe = _systemd_command(("systemctl", "--user", "show-environment"))
        feature_probe = _systemd_command(("systemd-run", "--help"))
    except ContractError:
        return False
    return (
        manager_probe.returncode == 0
        and feature_probe.returncode == 0
        and all(option in feature_probe.stdout for option in SYSTEMD_REQUIRED_OPTIONS)
    )


def _systemd_environment_line(name: str, value: str) -> bytes:
    if ENVIRONMENT_NAME.fullmatch(name) is None or any(character in value for character in "\0\n\r"):
        raise ContractError("containment_environment_invalid", "caller environment is not safely transferable")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{name}="{escaped}"\n'.encode("utf-8")


def create_systemd_environment_file(environment: dict[str, str] | None = None) -> tuple[int, str]:
    values = dict(os.environ if environment is None else environment)
    if not systemd_environment_supported(values):
        raise ContractError("containment_environment_invalid", "caller environment is not safely transferable")
    try:
        descriptor = os.memfd_create("agent-factory-environment", flags=getattr(os, "MFD_CLOEXEC", 0))
        for name, value in sorted(values.items()):
            remaining = memoryview(_systemd_environment_line(name, value))
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("short environment write")
                remaining = remaining[written:]
        os.lseek(descriptor, 0, os.SEEK_SET)
    except (OSError, UnicodeError) as error:
        if "descriptor" in locals():
            os.close(descriptor)
        raise ContractError("containment_environment_unavailable", "caller environment could not be transferred") from error
    return descriptor, f"/proc/{os.getpid()}/fd/{descriptor}"


def systemd_unit_name(agent_id: str, run_id: str, attempt: int) -> str:
    material = f"{agent_id}\0{run_id}\0{attempt}".encode()
    return f"agent-factory-{hashlib.sha256(material).hexdigest()[:24]}.service"


def validate_containment(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("containment_identity_unbound", "containment identity is not bound")
    kind = value.get("kind")
    if kind == "systemd-user-service":
        expected = {"kind", "unitName", "bindingToken", "invocationId", "weakerDescendantContainment"}
        if set(value) != expected or value.get("weakerDescendantContainment") is not False:
            raise ContractError("containment_identity_invalid", "systemd containment identity is invalid")
        unit = value.get("unitName")
        token = value.get("bindingToken")
        invocation = value.get("invocationId")
        if (
            not isinstance(unit, str) or not SYSTEMD_UNIT.fullmatch(unit)
            or not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token)
            or (invocation is not None and (not isinstance(invocation, str) or not re.fullmatch(r"[a-f0-9]{32}", invocation)))
        ):
            raise ContractError("containment_identity_invalid", "systemd containment identity is invalid")
        return value
    if kind == "process-group":
        expected = {"kind", "identity", "weakerDescendantContainment"}
        if set(value) != expected or value.get("weakerDescendantContainment") is not True:
            raise ContractError("containment_identity_invalid", "fallback containment identity is invalid")
        identity = value.get("identity")
        if not isinstance(identity, dict) or set(identity) != {"pid", "bootId", "startTicks"}:
            raise ContractError("containment_identity_invalid", "fallback containment identity is invalid")
        return value
    raise ContractError("containment_backend_invalid", "containment backend kind is invalid")


def _parse_systemd_show(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def systemd_cgroup_populated(control_group: str) -> bool:
    if not control_group.startswith("/"):
        raise ContractError("containment_query_invalid", "systemd returned an invalid control group")
    relative = Path(control_group.lstrip("/"))
    if not relative.parts or ".." in relative.parts or relative.is_absolute():
        raise ContractError("containment_query_invalid", "systemd returned an invalid control group")
    events_path = CGROUP_ROOT / relative / "cgroup.events"
    try:
        content = events_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise ContractError("containment_query_unknown", "systemd control-group population is unavailable") from error
    populated: str | None = None
    for line in content.splitlines():
        key, separator, value = line.partition(" ")
        if key == "populated" and separator:
            populated = value
    if populated not in {"0", "1"}:
        raise ContractError("containment_query_invalid", "systemd control-group population is invalid")
    return populated == "1"


def query_systemd_containment(containment: dict[str, Any]) -> dict[str, Any]:
    bound = validate_containment(containment)
    if bound["kind"] != "systemd-user-service":
        raise ContractError("containment_backend_mismatch", "containment backend does not match")
    result = _systemd_command((
        "systemctl", "--user", "show", bound["unitName"],
        "--property=LoadState,ActiveState,SubState,MainPID,Description,InvocationID,ControlGroup",
        "--no-pager",
    ))
    values = _parse_systemd_show(result.stdout)
    if values.get("LoadState") == "not-found":
        return {"active": False, "empty": True, "mainPid": None, "invocationId": None}
    if result.returncode != 0:
        raise ContractError("containment_query_unknown", "systemd containment query failed")
    required = {
        "LoadState", "ActiveState", "SubState", "MainPID", "Description",
        "InvocationID", "ControlGroup",
    }
    if not required.issubset(values) or values.get("LoadState") != "loaded":
        raise ContractError("containment_query_invalid", "systemd containment query is incomplete")
    expected_description = SYSTEMD_DESCRIPTION_PREFIX + bound["bindingToken"]
    if values.get("Description") != expected_description:
        raise ContractError("containment_identity_mismatch", "systemd unit binding does not match")
    observed_invocation = values.get("InvocationID") or None
    recorded_invocation = bound.get("invocationId")
    if recorded_invocation is not None and observed_invocation != recorded_invocation:
        raise ContractError("containment_identity_mismatch", "systemd invocation identity does not match")
    active = values.get("ActiveState") in {"activating", "active", "deactivating", "reloading"}
    main_pid_text = values.get("MainPID", "0")
    main_pid = int(main_pid_text) if main_pid_text.isdigit() and int(main_pid_text) > 0 else None
    populated = systemd_cgroup_populated(values["ControlGroup"])
    return {"active": active, "empty": not populated, "mainPid": main_pid, "invocationId": observed_invocation}


def _systemd_signal(containment: dict[str, Any], signal_name: str) -> None:
    status = query_systemd_containment(containment)
    if status["empty"]:
        return
    bound = validate_containment(containment)
    result = _systemd_command((
        "systemctl", "--user", "kill", f"--signal={signal_name}",
        "--kill-whom=all", bound["unitName"],
    ))
    if result.returncode != 0:
        raise ContractError("containment_stop_failed", "systemd containment could not be stopped")


def wait_containment_empty(containment: dict[str, Any], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if containment_is_empty(containment):
            return True
        time.sleep(0.05)
    return containment_is_empty(containment)


def containment_is_empty(containment: dict[str, Any]) -> bool:
    bound = validate_containment(containment)
    if bound["kind"] == "systemd-user-service":
        return bool(query_systemd_containment(bound)["empty"])
    identity = bound["identity"]
    status = process_identity_status(identity)
    if status in {"unknown", "mismatch"}:
        raise ContractError("containment_identity_mismatch", "fallback containment identity does not match")
    return status == "dead" and not process_group_exists(int(identity["pid"]))


def request_containment_stop(containment: dict[str, Any]) -> None:
    bound = validate_containment(containment)
    if bound["kind"] == "systemd-user-service":
        _systemd_signal(bound, "TERM")
        return
    terminate_verified_group(bound["identity"])


def force_containment_stop(containment: dict[str, Any]) -> None:
    bound = validate_containment(containment)
    if bound["kind"] == "systemd-user-service":
        _systemd_signal(bound, "KILL")
        return
    terminate_verified_group(bound["identity"])


def containment_bootstrap(args: argparse.Namespace) -> int:
    target = list(args.target)
    if target and target[0] == "--":
        target = target[1:]
    if not target:
        raise ContractError("containment_target_invalid", "contained target is empty")
    release = b""
    try:
        os.write(args.ready_fd, b"R")
        release = os.read(args.release_fd, 1)
    finally:
        with contextlib.suppress(OSError):
            os.close(args.ready_fd)
        with contextlib.suppress(OSError):
            os.close(args.release_fd)
    if release != b"G":
        return 125
    os.execvp(target[0], target)
    return 125


def spawn_contained_process(
    command: Sequence[str], **popen_options: Any
) -> tuple[subprocess.Popen[str], dict[str, Any], int]:
    linux_boot_id()
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    bootstrap_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_bootstrap",
        "--ready-fd",
        str(ready_write),
        "--release-fd",
        str(release_read),
        "--",
        *command,
    ]
    process: subprocess.Popen[str] | None = None
    try:
        try:
            process = subprocess.Popen(
                bootstrap_command,
                pass_fds=(ready_write, release_read),
                start_new_session=True,
                close_fds=True,
                **popen_options,
            )
        finally:
            os.close(ready_write)
            os.close(release_read)
    except Exception:
        os.close(ready_read)
        os.close(release_write)
        raise
    try:
        identity = linux_process_identity(process.pid)
        if process_identity_status(identity) != "match":
            raise ContractError(
                "process_identity_mismatch",
                "bootstrap identity changed immediately after process launch",
            )
        if os.getpgid(process.pid) != process.pid:
            raise ContractError(
                "process_group_invalid", "bootstrap process group is not isolated"
            )
        readable, _, _ = select.select(
            [ready_read], [], [], CONTAINMENT_START_TIMEOUT
        )
        ready = os.read(ready_read, 1) if readable else b""
        if ready != b"R":
            raise ContractError(
                "containment_start_failed",
                "contained process did not enter the startup barrier",
            )
        return process, identity, release_write
    except Exception:
        if "identity" in locals():
            abort_contained_process(process, identity, release_write)
        else:
            os.close(release_write)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=PROCESS_TERM_TIMEOUT)
        raise
    finally:
        os.close(ready_read)


def release_contained_process(
    process: subprocess.Popen[str], identity: dict[str, Any], release_fd: int
) -> None:
    try:
        if process_identity_status(identity) != "match":
            raise ContractError(
                "process_identity_mismatch",
                "contained process identity changed before startup release",
            )
        if os.getpgid(process.pid) != process.pid:
            raise ContractError(
                "process_group_invalid", "contained process group is not isolated"
            )
        os.write(release_fd, b"G")
    finally:
        os.close(release_fd)


def abort_contained_process(
    process: subprocess.Popen[str],
    identity: dict[str, Any],
    release_fd: int | None,
) -> None:
    if release_fd is not None:
        with contextlib.suppress(OSError):
            os.close(release_fd)
    try:
        process.wait(timeout=PROCESS_TERM_TIMEOUT)
    except subprocess.TimeoutExpired:
        terminate_attempt_group(process, identity)


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
            if fcntl is not None:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            else:
                stream.seek(0)
                if stream.read(1) == "":
                    stream.write("\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
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


def dispatch_reservation_file(
    project_root: Path, agent_id: str, dispatch_id: str
) -> Path:
    return agent_directory(project_root, agent_id, create=True) / "dispatches" / f"{dispatch_id}.json"


def state_file(project_root: Path, agent_id: str, run_id: str) -> Path:
    return run_directory(project_root, agent_id, run_id) / "state.json"


def _bounded_text(value: object, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096:
        raise ContractError("capability_binding_invalid", f"{label} is invalid")
    if any(character in value for character in "\x00\r\n"):
        raise ContractError("capability_binding_invalid", f"{label} contains control characters")
    return value


def validate_capability_bindings(document: object) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "bindings"}:
        raise ContractError("capability_binding_invalid", "capability binding document has unknown or missing fields")
    if document.get("schemaVersion") != SCHEMA_VERSION or not isinstance(document.get("bindings"), list):
        raise ContractError("capability_binding_invalid", "capability binding document is invalid")
    bindings = document["bindings"]
    if not 1 <= len(bindings) <= 32:
        raise ContractError("capability_binding_invalid", "capability bindings must contain 1 through 32 entries")
    identities: set[str] = set()
    fields = {
        "capabilityId", "authority", "invocationRoute", "exactTarget",
        "allowedEffects", "allowedScopes", "approvalReference",
    }
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != fields:
            raise ContractError("capability_binding_invalid", "capability binding has unknown or missing fields")
        capability_id = binding.get("capabilityId")
        if not isinstance(capability_id, str) or CAPABILITY_ID.fullmatch(capability_id) is None:
            raise ContractError("capability_binding_invalid", "capabilityId is invalid")
        if capability_id in identities:
            raise ContractError("capability_binding_invalid", "capabilityId bindings must be unique")
        identities.add(capability_id)
        authority = binding.get("authority")
        if not isinstance(authority, dict) or set(authority) != {"kind", "reference"}:
            raise ContractError("capability_binding_invalid", "authority has unknown or missing fields")
        if authority.get("kind") not in AUTHORITY_KINDS:
            raise ContractError("capability_binding_invalid", "authority kind is invalid")
        _bounded_text(authority.get("reference"), "authority reference")
        _bounded_text(binding.get("invocationRoute"), "invocation route")
        _bounded_text(binding.get("exactTarget"), "exact target")
        _bounded_text(binding.get("approvalReference"), "approval reference", nullable=True)
        for field in ("allowedEffects", "allowedScopes"):
            values = binding.get(field)
            if not isinstance(values, list) or len(values) > 64:
                raise ContractError("capability_binding_invalid", f"{field} must be a bounded array")
            checked = [_bounded_text(value, field) for value in values]
            if len(set(checked)) != len(checked):
                raise ContractError("capability_binding_invalid", f"{field} must contain unique values")
    return document


def read_capability_bindings(path: Path | None) -> tuple[dict[str, Any] | None, bytes | None]:
    if path is None:
        return None, None
    raw = safe_read_caller_file(path, MAX_CAPABILITY_BINDING_BYTES)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("capability_binding_invalid", "capability binding file is invalid JSON") from error
    validated = validate_capability_bindings(document)
    canonical = (json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return validated, canonical


def safe_read_caller_file(path: Path, limit: int) -> bytes:
    """Read an explicit caller file without following any path component."""
    if ".." in path.parts:
        raise ContractError("capability_binding_invalid", "capability binding path contains traversal")
    if (
        not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NONBLOCK")
        or os.open not in os.supports_dir_fd
    ):
        raise ContractError(
            "capability_binding_unsupported",
            "safe capability binding file traversal is unavailable on this platform",
        )
    absolute = path if path.is_absolute() else Path.cwd() / path
    components = [part for part in absolute.parts if part not in {absolute.anchor, "."}]
    if not components:
        raise ContractError("capability_binding_invalid", "capability binding path is invalid")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = -1
    try:
        descriptor = os.open(absolute.anchor or os.sep, directory_flags)
        for component in components[:-1]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise ContractError("capability_binding_invalid", "capability binding parent is unsafe")
        file_descriptor = os.open(components[-1], file_flags, dir_fd=descriptor)
        os.close(descriptor)
        descriptor = file_descriptor
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ContractError("capability_binding_invalid", "capability binding is not a regular file")
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
    except (FileNotFoundError, NotADirectoryError, OSError) as error:
        raise ContractError(
            "capability_binding_invalid",
            "capability binding path is missing or contains an unsafe component",
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def create_run(
    *,
    project_root: Path,
    agent_id: str,
    actor: str,
    request: bytes,
    session: dict[str, Any],
    receipt_request_hash: str | None = None,
    verified_work_run_id: str | None = None,
    dispatch_id: str | None = None,
    dispatch_operation: str | None = None,
    capability_bindings: bytes | None = None,
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
    capability_binding_path = directory / "capability-bindings.json"
    request_hash = hashlib.sha256(request).hexdigest()
    atomic_write(request_path, request)
    capability_binding_hash = None
    capability_binding_document = None
    if capability_bindings is not None:
        capability_binding_document = validate_capability_bindings(json.loads(capability_bindings))
        atomic_write(capability_binding_path, capability_bindings)
        capability_binding_hash = hashlib.sha256(capability_bindings).hexdigest()
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
    if role in {"work", "verification"}:
        atomic_write_json(
            receipt_schema,
            receipt_schema_document(
                role=role,
                run_id=run_id,
                request_hash=receipt_request_hash or request_hash,
                verified_work_run_id=verified_work_run_id,
                capability_bindings=capability_binding_document,
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
        "startDisposition": "not-started",
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
        "workerIdentity": None,
        "containmentAttempt": 0,
        "containment": None,
        "containmentLaunchDisposition": "not-launched",
        "codexPid": None,
        "codexIdentity": None,
        "lastCodexIdentity": None,
        "cancelRequested": False,
        "unread": False,
        "error": None,
    }
    if dispatch_id is not None:
        state["dispatchId"] = dispatch_id
        state["dispatchTuple"] = {
            "agentId": agent_id,
            "role": role,
            "actor": actor,
            "requestHash": request_hash,
            "receiptRequestHash": receipt_request_hash or request_hash,
            "verifiedWorkRunId": verified_work_run_id,
            "operation": dispatch_operation,
        }
        if capability_binding_hash is not None:
            state["dispatchTuple"]["capabilityBindingHash"] = capability_binding_hash
    if role in {"work", "verification"}:
        state.update(
            {
                "receiptPath": str(receipt_path),
                "receiptSchemaPath": str(receipt_schema),
                "receiptRequestHash": receipt_request_hash or request_hash,
            }
        )
    if role == "verification":
        state["verifiedWorkRunId"] = verified_work_run_id
    if capability_binding_hash is not None:
        state.update({
            "capabilityBindingPath": str(capability_binding_path),
            "capabilityBindingHash": capability_binding_hash,
        })
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
    *, role: str, run_id: str, request_hash: str, verified_work_run_id: str | None,
    capability_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tests = {
        "type": "object",
        "properties": {
            "run": {"const": False},
            "reason": {
                "const": (
                    "work-agent-prohibited" if role == "work" else "verification-recorded-separately"
                )
            },
        },
        "required": ["run", "reason"],
        "additionalProperties": False,
    }
    capability_outcomes = None
    if capability_bindings is not None:
        outcome_items = []
        for binding in capability_bindings["bindings"]:
            outcome_items.append({
                "type": "object",
                "properties": {
                    "requestHash": {"const": request_hash},
                    "runId": {"const": run_id},
                    "capabilityId": {"const": binding["capabilityId"]},
                    "authority": {"const": binding["authority"]},
                    "exactTarget": {"const": binding["exactTarget"]},
                    "outcome": {"enum": sorted(CAPABILITY_OUTCOMES)},
                },
                "required": ["requestHash", "runId", "capabilityId", "authority", "exactTarget", "outcome"],
                "additionalProperties": False,
            })
        capability_outcomes = {
            "type": "array", "prefixItems": outcome_items,
            "minItems": len(outcome_items), "maxItems": len(outcome_items),
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
                "path": {"type": "string"},
                "location": {"type": "string"},
                "problem": {"type": "string", "minLength": 1},
                "evidence": {"type": "string", "minLength": 1},
                "correction": {"type": "string", "minLength": 1},
            },
            "required": [
                "id", "path", "location", "problem", "evidence", "correction"
            ],
            "additionalProperties": False,
        }
        verified_id_schema: dict[str, Any] = {"type": "string", "minLength": 1}
        if verified_work_run_id is not None:
            verified_id_schema = {"const": verified_work_run_id}
        properties = {
            "schemaVersion": {"const": SCHEMA_VERSION},
            "kind": {"const": "verification-receipt"},
            "runId": {"const": run_id},
            "verifiedWorkRunId": verified_id_schema,
            "verifiedRequestHash": {"const": request_hash},
            "decision": {"enum": ["pass", "fail"]},
            "findings": {"type": "array", "items": finding},
        }
        required = list(properties)
    if capability_outcomes is not None:
        properties["capabilityOutcomes"] = capability_outcomes
        required.append("capabilityOutcomes")
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
    if role not in {"work", "verification"}:
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
    binding_document = None
    binding_hash = state.get("capabilityBindingHash")
    if binding_hash is not None:
        binding_path = canonical["statePath"].parent / "capability-bindings.json"
        if state.get("capabilityBindingPath") != str(binding_path):
            raise ContractError("receipt_path_invalid", "capability binding path is not canonically bound")
        _require_managed_file(binding_path)
        binding_bytes = safe_read_bytes(binding_path, MAX_CAPABILITY_BINDING_BYTES)
        if hashlib.sha256(binding_bytes).hexdigest() != binding_hash:
            raise ContractError("capability_binding_invalid", "capability binding hash does not match")
        try:
            binding_document = validate_capability_bindings(json.loads(binding_bytes))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContractError("capability_binding_invalid", "capability binding is invalid JSON") from error
    expected_fields = {
        "schemaVersion", "kind", "runId", "requestHash", "outcome",
        "changedPaths", "addressedFindingIds", "tests",
    }
    if binding_document is not None:
        expected_fields.add("capabilityOutcomes")
    if role == "work":
        tests = receipt.get("tests")
        if not isinstance(tests, dict):
            raise ContractError("receipt_invalid", "receipt tests proof is missing")
        _exact_keys(tests, {"run", "reason"}, "tests")
        if tests != {"run": False, "reason": "work-agent-prohibited"}:
            raise ContractError("receipt_tests_invalid", "Work receipt must prove Work ran no tests")
        _exact_keys(receipt, expected_fields, "work receipt")
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
    else:
        expected_fields = {
            "schemaVersion", "kind", "runId", "verifiedWorkRunId",
            "verifiedRequestHash", "decision", "findings",
        }
        if binding_document is not None:
            expected_fields.add("capabilityOutcomes")
        _exact_keys(receipt, expected_fields, "verification receipt")
    if role == "work":
        validated_receipt = receipt
    else:
        verified_work_run_id = receipt.get("verifiedWorkRunId")
        expected_work_run_id = state.get("verifiedWorkRunId")
        if (
            receipt.get("schemaVersion") != SCHEMA_VERSION
            or receipt.get("kind") != "verification-receipt"
            or receipt.get("runId") != state.get("runId")
            or not isinstance(verified_work_run_id, str)
            or not AGENT_ID.fullmatch(verified_work_run_id)
            or (expected_work_run_id is not None and verified_work_run_id != expected_work_run_id)
            or receipt.get("verifiedRequestHash") != expected_hash
        ):
            raise ContractError("receipt_binding_invalid", "verification receipt binding is invalid")
        findings = receipt.get("findings")
        if not isinstance(findings, list):
            raise ContractError("receipt_invalid", "findings must be an array")
        finding_ids: list[str] = []
        finding_fields = {"id", "path", "location", "problem", "evidence", "correction"}
        for finding in findings:
            if not isinstance(finding, dict):
                raise ContractError("receipt_invalid", "each finding must be an object")
            _exact_keys(finding, finding_fields, "finding")
            finding_id = finding.get("id")
            if not isinstance(finding_id, str) or not finding_id:
                raise ContractError("receipt_invalid", "finding id is invalid")
            finding_ids.append(finding_id)
            for field in ("path", "location", "problem", "evidence", "correction"):
                if not isinstance(finding.get(field), str):
                    raise ContractError("receipt_invalid", f"finding {field} must be a string")
            if not finding["problem"] or not finding["evidence"] or not finding["correction"]:
                raise ContractError("receipt_invalid", "finding details must not be empty")
        if len(set(finding_ids)) != len(finding_ids):
            raise ContractError("receipt_invalid", "finding identifiers must be unique")
        decision = receipt.get("decision")
        if decision == "pass" and findings:
            raise ContractError("receipt_decision_invalid", "passing verification has findings")
        if decision == "fail" and not findings:
            raise ContractError("receipt_decision_invalid", "failed verification requires a finding")
        if decision not in {"pass", "fail"}:
            raise ContractError("receipt_decision_invalid", "verification decision is invalid")
        validated_receipt = receipt
    if binding_document is not None:
        outcomes = receipt.get("capabilityOutcomes")
        bindings = binding_document["bindings"]
        if not isinstance(outcomes, list) or len(outcomes) != len(bindings):
            raise ContractError("receipt_invalid", "capability outcomes must match bound capabilities")
        for outcome, binding in zip(outcomes, bindings):
            expected_outcome_fields = {"requestHash", "runId", "capabilityId", "authority", "exactTarget", "outcome"}
            if not isinstance(outcome, dict):
                raise ContractError("receipt_invalid", "capability outcome must be an object")
            _exact_keys(outcome, expected_outcome_fields, "capability outcome")
            if (
                outcome.get("requestHash") != expected_hash
                or outcome.get("runId") != state.get("runId")
                or outcome.get("capabilityId") != binding["capabilityId"]
                or outcome.get("authority") != binding["authority"]
                or outcome.get("exactTarget") != binding["exactTarget"]
                or outcome.get("outcome") not in CAPABILITY_OUTCOMES
            ):
                raise ContractError("receipt_binding_invalid", "capability outcome binding is invalid")
    return validated_receipt


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


def validate_state_containment_fields(state: dict[str, Any]) -> None:
    fields = {"containmentAttempt", "containment", "containmentLaunchDisposition"}
    present = fields.intersection(state)
    if not present:
        return
    if present != fields:
        raise ContractError("containment_state_invalid", "containment state fields are incomplete")
    attempt = state.get("containmentAttempt")
    disposition = state.get("containmentLaunchDisposition")
    if not isinstance(attempt, int) or attempt < 0 or disposition not in {
        "not-launched", "launching", "launched"
    }:
        raise ContractError("containment_state_invalid", "containment state fields are invalid")
    containment = state.get("containment")
    if containment is None:
        if attempt != 0 or disposition != "not-launched":
            raise ContractError("containment_identity_unbound", "launched containment identity is not bound")
        return
    validate_containment(containment)
    if attempt < 1 or disposition == "not-launched":
        raise ContractError("containment_state_invalid", "containment launch state is invalid")


def _validate_state_containment(state: dict[str, Any]) -> dict[str, Any]:
    validate_state_containment_fields(state)
    containment = validate_containment(state.get("containment"))
    if containment["kind"] == "systemd-user-service":
        attempt = state.get("containmentAttempt")
        if not isinstance(attempt, int) or attempt < 1 or containment["unitName"] != systemd_unit_name(
            str(state.get("agentId")), str(state.get("runId")), attempt
        ):
            raise ContractError("containment_identity_mismatch", "systemd unit is not bound to this run attempt")
    elif containment["identity"] != state.get("workerIdentity"):
        raise ContractError("containment_identity_mismatch", "fallback containment is not bound to this worker")
    return containment


def _launch_systemd_worker(
    project_root: Path,
    agent_id: str,
    run_id: str,
    command: Sequence[str],
    environment_resource: tuple[int, str],
) -> int:
    environment_fd, environment_path = environment_resource
    try:
        path = state_file(project_root, agent_id, run_id)
        state = safe_read_json(path)
        attempt = int(state.get("containmentAttempt", 0)) + 1
        containment = {
            "kind": "systemd-user-service",
            "unitName": systemd_unit_name(agent_id, run_id, attempt),
            "bindingToken": uuid.uuid4().hex,
            "invocationId": None,
            "weakerDescendantContainment": False,
        }
        update_json(
            path,
            path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "containmentAttempt": attempt,
                    "containment": containment,
                    "containmentLaunchDisposition": "launching",
                    "status": "starting",
                }
            ),
        )
        result = _systemd_command((
            "systemd-run", "--user", f"--unit={containment['unitName']}",
            f"--description={SYSTEMD_DESCRIPTION_PREFIX}{containment['bindingToken']}",
            "--collect", "--service-type=exec",
            "--property=KillMode=control-group",
            f"--property=TimeoutStopSec={PROCESS_TERM_TIMEOUT}s",
            "--property=SendSIGKILL=no",
            f"--property=EnvironmentFile={environment_path}",
            f"--working-directory={project_root}", "--", *command,
        ))
    finally:
        with contextlib.suppress(OSError):
            os.close(environment_fd)
    if result.returncode != 0:
        raise ContractError(
            "containment_launch_failed",
            "the bound systemd service launch was not acknowledged; the run will not be replayed without reconciliation",
        )
    observed = query_systemd_containment(containment)
    if observed["invocationId"] is None:
        raise ContractError("containment_launch_ack_missing", "systemd returned no invocation identity")
    containment = {**containment, "invocationId": observed["invocationId"]}
    state = update_json(
        path,
        path.parent / ".state.lock",
        lambda value: value.update(
            {
                "containment": containment,
                "containmentLaunchDisposition": "launched",
                "workerPid": observed["mainPid"],
                "status": "queued",
            }
        ),
    )
    worker_pid = state.get("workerPid")
    return worker_pid if isinstance(worker_pid, int) and worker_pid > 0 else 0


def _launch_fallback_worker(
    project_root: Path, agent_id: str, run_id: str, command: Sequence[str]
) -> int:
    command = [
        *command,
    ]
    try:
        process, identity, release_fd = spawn_contained_process(
            command,
            cwd=project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except ContractError as error:
        raise ContractError(error.code, error.message) from error
    except OSError as error:
        raise ContractError("worker_start_failed", "background worker could not start") from error
    release_attempted = False
    try:
        path = state_file(project_root, agent_id, run_id)
        update_json(
            path,
            path.parent / ".state.lock",
            lambda state: state.update(
                {
                    "workerPid": process.pid,
                    "workerIdentity": identity,
                    "containmentAttempt": int(state.get("containmentAttempt", 0)) + 1,
                    "containment": {
                        "kind": "process-group",
                        "identity": identity,
                        "weakerDescendantContainment": True,
                    },
                    "containmentLaunchDisposition": "launched",
                    "status": "queued",
                }
            ),
        )
        release_attempted = True
        release_contained_process(process, identity, release_fd)
    except (ContractError, OSError) as error:
        abort_contained_process(
            process,
            identity,
            None if release_attempted else release_fd,
        )
        if isinstance(error, ContractError):
            raise ContractError(error.code, error.message) from error
        raise ContractError("worker_start_failed", "background worker could not start") from error
    return process.pid


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
    if systemd_manager_usable():
        try:
            environment_resource = create_systemd_environment_file()
        except ContractError as error:
            if error.code not in {
                "containment_environment_invalid",
                "containment_environment_unavailable",
            }:
                raise
        else:
            return _launch_systemd_worker(
                project_root, agent_id, run_id, command, environment_resource
            )
    return _launch_fallback_worker(project_root, agent_id, run_id, command)


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
    verified_work_run_id = getattr(args, "verified_work_run_id", None)
    dispatch_id = getattr(args, "dispatch_id", None)
    _capability_document, capability_bindings = read_capability_bindings(
        getattr(args, "capability_binding_file", None)
    )
    capability_binding_hash = (
        hashlib.sha256(capability_bindings).hexdigest()
        if capability_bindings is not None else None
    )
    if dispatch_id is not None:
        validate_id(dispatch_id, DISPATCH_ID, "dispatch_id")
    if receipt_request_hash is not None and not re.fullmatch(r"[0-9a-f]{64}", receipt_request_hash):
        raise ContractError("receipt_binding_invalid", "receipt request hash is invalid")
    if verified_work_run_id is not None:
        validate_id(verified_work_run_id, AGENT_ID, "run_id")
    if new_agent:
        role = validate_id(args.role, ROLE_ID, "role")
        role_path(role)
    else:
        role = load_session(project_root, args.agent).get("role")
    if role == "verification" and verified_work_run_id is None:
        raise ContractError(
            "receipt_binding_invalid",
            "Verification runs require the exact Work run identifier",
        )
    if role != "verification" and verified_work_run_id is not None:
        raise ContractError(
            "receipt_binding_invalid",
            "verified Work run binding is valid only for Verification runs",
        )
    operation = "submit" if new_agent else "send"
    request_hash = hashlib.sha256(request).hexdigest()
    dispatch_tuple = {
        "agentId": args.agent,
        "role": role,
        "actor": args.actor,
        "requestHash": request_hash,
        "receiptRequestHash": receipt_request_hash or request_hash,
        "verifiedWorkRunId": verified_work_run_id,
        "operation": operation,
    }
    if capability_binding_hash is not None:
        dispatch_tuple["capabilityBindingHash"] = capability_binding_hash
    agent_path = agent_directory(project_root, args.agent, create=True)
    with file_lock(agent_path / ".dispatch.lock"):
        reservation_path: Path | None = None
        if new_agent and dispatch_id is not None:
            reservation_path = dispatch_reservation_file(
                project_root, args.agent, dispatch_id
            )
            if reservation_path.exists():
                reservation = safe_read_json(reservation_path)
                if (
                    set(reservation)
                    != {"schemaVersion", "kind", "dispatchId", "dispatchTuple"}
                    or reservation.get("schemaVersion") != SCHEMA_VERSION
                    or reservation.get("kind") != "dispatch-reservation"
                    or reservation.get("dispatchId") != dispatch_id
                    or reservation.get("dispatchTuple") != dispatch_tuple
                ):
                    raise ContractError(
                        "dispatch_id_collision",
                        "dispatch identifier was reserved with a different immutable tuple",
                    )
            else:
                if session_file(project_root, args.agent).exists():
                    prior = [
                        value
                        for value in iter_run_states(project_root, args.agent)
                        if value.get("dispatchId") == dispatch_id
                    ]
                    if len(prior) > 1:
                        raise ContractError(
                            "dispatch_id_collision", "dispatch identifier is not unique"
                        )
                    if prior:
                        state = prior[0]
                        if state.get("dispatchTuple") != dispatch_tuple:
                            raise ContractError(
                                "dispatch_id_collision",
                                "dispatch identifier was used with a different immutable tuple",
                            )
                        emit({
                            "schemaVersion": SCHEMA_VERSION,
                            "kind": "ack",
                            "status": "accepted",
                            "agentId": args.agent,
                            "runId": state["runId"],
                            "workerPid": state.get("workerPid"),
                            "statePath": str(
                                state_file(project_root, args.agent, state["runId"])
                            ),
                            "dispatchId": dispatch_id,
                            "deduplicated": True,
                        })
                        return 0
                    raise ContractError("agent_exists", "Agent already exists; use send")
                reservation_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json(
                    reservation_path,
                    {
                        "schemaVersion": SCHEMA_VERSION,
                        "kind": "dispatch-reservation",
                        "dispatchId": dispatch_id,
                        "dispatchTuple": dispatch_tuple,
                    },
                )
        if dispatch_id is not None:
            matches = [
                value for value in iter_run_states(project_root, args.agent)
                if value.get("dispatchId") == dispatch_id
            ]
            if len(matches) > 1:
                raise ContractError("dispatch_id_collision", "dispatch identifier is not unique")
            if matches:
                state = matches[0]
                if state.get("dispatchTuple") != dispatch_tuple:
                    raise ContractError("dispatch_id_collision", "dispatch identifier was used with a different immutable tuple")
                emit({
                    "schemaVersion": SCHEMA_VERSION,
                    "kind": "ack",
                    "status": "accepted",
                    "agentId": args.agent,
                    "runId": state["runId"],
                    "workerPid": state.get("workerPid"),
                    "statePath": str(state_file(project_root, args.agent, state["runId"])),
                    "dispatchId": dispatch_id,
                    "deduplicated": True,
                })
                return 0
        if new_agent:
            session = (
                load_session(project_root, args.agent)
                if reservation_path is not None
                and session_file(project_root, args.agent).exists()
                else create_session(args, project_root)
            )
        else:
            session = load_session(project_root, args.agent)
        state = create_run(
            project_root=project_root,
            agent_id=args.agent,
            actor=args.actor,
            request=request,
            session=session,
            receipt_request_hash=receipt_request_hash,
            verified_work_run_id=verified_work_run_id,
            dispatch_id=dispatch_id,
            dispatch_operation=operation,
            capability_bindings=capability_bindings,
        )
        worker_pid = spawn_worker(project_root, args.agent, state["runId"])
    document = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "ack",
            "status": "accepted",
            "agentId": args.agent,
            "runId": state["runId"],
            "workerPid": worker_pid,
            "statePath": str(state_file(project_root, args.agent, state["runId"])),
        }
    if dispatch_id is not None:
        document.update({"dispatchId": dispatch_id, "deduplicated": False})
    emit(document)
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
        self.codex_identity: dict[str, Any] | None = None
        self.worker_identity = linux_process_identity(os.getpid())
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._write()
        self.thread.start()

    def update(
        self,
        *,
        status: str,
        attempt: int,
        codex_pid: int | None,
        codex_identity: dict[str, Any] | None = None,
    ) -> None:
        with self.lock:
            self.status = status
            self.attempt = attempt
            self.codex_pid = codex_pid
            self.codex_identity = codex_identity
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
                "workerIdentity": self.worker_identity,
                "codexPid": self.codex_pid,
                "codexIdentity": self.codex_identity,
                "observedAt": now(),
            }
        atomic_write_json(self.path, value)


class AttemptFailure(Exception):
    def __init__(
        self, code: str, message: str, started: bool, launched: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.started = started
        self.launched = launched


def build_prompt(
    *,
    agent_id: str,
    role: str,
    request_path: Path,
    result_path: Path,
    run_id: str,
    receipt_path: Path | None = None,
    receipt_schema_path: Path | None = None,
    capability_binding_path: Path | None = None,
) -> str:
    prompt_path = role_path(role)
    try:
        role_prompt = safe_read_bytes(prompt_path, MAX_REQUEST_BYTES).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("role_invalid", "Agent role prompt must be UTF-8 text") from error
    if not role_prompt.strip():
        raise ContractError("role_invalid", "Agent role prompt must not be empty")
    receipt_obligation = ""
    if receipt_path is not None and receipt_schema_path is not None:
        receipt_obligation = f"""
For a `completed` result, also write the role-specific machine receipt to
`{receipt_path}`. Its exact contract is `{receipt_schema_path}`. The receipt
must bind this run and request exactly and contain no unknown fields. A
completed run with a missing or invalid receipt will fail at the runtime
boundary.
"""
    binding_obligation = ""
    if capability_binding_path is not None:
        binding_obligation = f"""
This run has a strict capability binding at `{capability_binding_path}`. Use
only its exact capability, authority, invocation route, target, allowed effects
and scopes, and approval reference. Preserve its binding in the required receipt.
"""
    return f"""Act as Agent `{agent_id}` for Agent Factory.

The following validated content is the complete `{role}` system-prompt source:

<agent-factory-role-prompt>
{role_prompt}
</agent-factory-role-prompt>

Read the delegated request from `{request_path}`. Keep its scope and authority unchanged.

Write the detailed result to `{result_path}`. Then return only the compact JSON
required by the supplied output schema. Run ID: `{run_id}`.
{binding_obligation}{receipt_obligation}"""


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


def append_bounded(path: Path, content: bytes, limit: int) -> bool:
    reject_symlink(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ContractError("runtime_path_unsafe", "runtime log is not a regular file")
        if info.st_size > limit or len(content) > limit - info.st_size:
            return False
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short runtime log write")
            view = view[written:]
        os.fsync(descriptor)
        return True
    finally:
        os.close(descriptor)


def append_event(path: Path, line: str) -> bool:
    return append_bounded(path, line.encode(), MAX_EVENTS_BYTES)


def read_process_lines(stream: IO[str], output: queue.Queue[tuple[str, str | None]]) -> None:
    try:
        for line in stream:
            output.put(("line", line))
    except (OSError, UnicodeError):
        output.put(("error", None))
    finally:
        output.put(("stdout_eof", None))


def stream_stderr(
    stream: IO[str], path: Path, output: queue.Queue[tuple[str, str | None]]
) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            if not append_bounded(path, chunk.encode(), MAX_STDERR_BYTES):
                output.put(("stderr_overflow", None))
                return
    except (ContractError, OSError, UnicodeError):
        output.put(("stderr_error", None))
    finally:
        output.put(("stderr_eof", None))


def process_group_exists(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_attempt_group(
    process: subprocess.Popen[str], identity: dict[str, Any]
) -> None:
    terminate_verified_group(identity, process)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=0.1)


def terminate_verified_group(
    identity: dict[str, Any], process: subprocess.Popen[str] | None = None
) -> None:
    identity_status = process_identity_status(identity)
    if identity_status not in {"match", "dead"}:
        raise ContractError(
            "process_identity_mismatch",
            "active Codex identity no longer matches; refusing to signal",
        )
    group_id = int(identity["pid"])
    if identity_status == "dead":
        if not process_group_exists(group_id):
            return
    else:
        try:
            observed_group = os.getpgid(group_id)
        except ProcessLookupError:
            return
        if observed_group != group_id:
            raise ContractError(
                "process_group_invalid", "active Codex process group is not isolated"
            )
    if not process_group_exists(group_id):
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(group_id, signal.SIGTERM)
    deadline = time.monotonic() + PROCESS_TERM_TIMEOUT
    while process_group_exists(group_id) and time.monotonic() < deadline:
        if process is not None:
            process.poll()
        time.sleep(0.05)
    if process_group_exists(group_id):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(group_id, signal.SIGKILL)
        deadline = time.monotonic() + PROCESS_KILL_TIMEOUT
        while process_group_exists(group_id) and time.monotonic() < deadline:
            if process is not None:
                process.poll()
            time.sleep(0.05)


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
    update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"status": "starting", "attempt": attempt, "startDisposition": "launching"}
        ),
    )
    try:
        process, codex_identity, release_fd = spawn_contained_process(
            command,
            cwd=project_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            shell=False,
        )
    except ContractError as error:
        raise AttemptFailure(error.code, error.message, False) from error
    except OSError as error:
        raise AttemptFailure(
            "codex_start_failed", "codex exec could not start", False
        ) from error
    release_attempted = False
    try:
        update_json(
            state_path,
            state_path.parent / ".state.lock",
            lambda value: value.update(
                {
                    "status": "starting",
                    "attempt": attempt,
                    "codexPid": process.pid,
                    "codexIdentity": codex_identity,
                    "lastCodexIdentity": codex_identity,
                }
            ),
        )
        heartbeat.update(
            status="starting",
            attempt=attempt,
            codex_pid=process.pid,
            codex_identity=codex_identity,
        )
        release_attempted = True
        release_contained_process(process, codex_identity, release_fd)
    except (ContractError, OSError) as error:
        abort_contained_process(
            process,
            codex_identity,
            None if release_attempted else release_fd,
        )
        code = error.code if isinstance(error, ContractError) else "codex_start_failed"
        message = (
            error.message
            if isinstance(error, ContractError)
            else "codex exec could not start"
        )
        raise AttemptFailure(code, message, False, False) from error
    if process.stdin is None or process.stdout is None or process.stderr is None:
        terminate_attempt_group(process, codex_identity)
        raise AttemptFailure(
            "codex_start_failed", "codex exec pipes are unavailable", False, True
        )
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
        capability_binding_path=(
            Path(state["capabilityBindingPath"])
            if state.get("capabilityBindingPath") else None
        ),
    )
    try:
        process.stdin.write(prompt)
        process.stdin.close()
    except (BrokenPipeError, OSError, UnicodeError) as error:
        terminate_attempt_group(process, codex_identity)
        raise AttemptFailure(
            "codex_write_failed", "codex exec rejected the prompt", False, True
        ) from error
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threading.Thread(
        target=read_process_lines, args=(process.stdout, lines), daemon=True
    ).start()
    threading.Thread(
        target=stream_stderr, args=(process.stderr, stderr_path, lines), daemon=True
    ).start()
    started = False
    active_session: str | None = None
    final_messages: list[str] = []
    started_at = time.monotonic()
    start_deadline = started_at + float(session["startTimeout"])
    turn_deadline = started_at + float(session["turnTimeout"])
    stdout_eof = False
    stderr_eof = False
    try:
        while True:
            if cancel_requested(state_path, cancel_event):
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure("cancelled", "run was cancelled", started, True)
            current = time.monotonic()
            if not started and current >= start_deadline:
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "start_timeout", "codex exec sent no start ACK", False, True
                )
            if current >= turn_deadline:
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "turn_timeout", "codex exec exceeded its turn timeout", started, True
                )
            try:
                kind, line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if kind == "error":
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "event_read_failed", "codex event stream failed", started, True
                )
            if kind == "stderr_error":
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "stderr_log_failed", "Codex stderr log could not be persisted", started, True
                )
            if kind == "stderr_overflow":
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "stderr_log_limit_exceeded",
                    "Codex stderr exceeded the per-run byte limit",
                    started,
                    True,
                )
            if kind == "stdout_eof":
                stdout_eof = True
                if stderr_eof:
                    break
                continue
            if kind == "stderr_eof":
                stderr_eof = True
                if stdout_eof:
                    break
                continue
            if line is None or len(line.encode()) > MAX_EVENT_BYTES:
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            if not append_event(Path(state["eventsPath"]), line):
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "event_log_limit_exceeded",
                    "Codex events exceeded the per-run byte limit",
                    started,
                    True,
                )
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "event_invalid", "codex emitted malformed JSONL", started, True
                ) from error
            if not isinstance(event, dict):
                terminate_attempt_group(process, codex_identity)
                raise AttemptFailure(
                    "event_invalid", "codex emitted an invalid event", started, True
                )
            if event.get("type") == "thread.started":
                observed = event.get("thread_id")
                if not isinstance(observed, str) or not SESSION_ID.fullmatch(observed):
                    terminate_attempt_group(process, codex_identity)
                    raise AttemptFailure(
                        "session_invalid", "codex returned an invalid session", started, True
                    )
                if existing_session is not None and observed != existing_session:
                    terminate_attempt_group(process, codex_identity)
                    raise AttemptFailure(
                        "session_mismatch", "codex resumed a different session", started, True
                    )
                active_session = observed
                started = True
                heartbeat.update(
                    status="running",
                    attempt=attempt,
                    codex_pid=process.pid,
                    codex_identity=codex_identity,
                )
                update_json(
                    state_path,
                    state_path.parent / ".state.lock",
                    lambda value: value.update(
                        {
                            "status": "running", "sessionId": observed,
                            "startedAt": now(), "startDisposition": "started",
                        }
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
        terminate_attempt_group(process, codex_identity)
        raise AttemptFailure(
            "codex_exit_timeout", "codex exec did not exit", started, True
        ) from error
    # The leader may exit while descendants keep its isolated process group.
    # Contain that group before validating or returning any post-exit outcome.
    terminate_attempt_group(process, codex_identity)
    if return_code != 0:
        raise AttemptFailure(
            "codex_failed", f"codex exec exited with {return_code}", started, True
        )
    if not started or active_session is None:
        raise AttemptFailure(
            "start_ack_missing", "codex exec returned no start ACK", False, True
        )
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
    if terminal["status"] == "completed" and state.get("role") in {"work", "verification"}:
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
    state_path: Path,
    status: str,
    error: dict[str, str] | None = None,
    *,
    attempt: int | None = None,
    start_disposition: str | None = None,
) -> None:
    def change(value: dict[str, Any]) -> None:
        value.update(
            {
                "status": status,
                "codexPid": None,
                "codexIdentity": None,
                "finishedAt": now(),
                "unread": True,
                "error": error,
            }
        )
        if attempt is not None:
            value["attempt"] = attempt
        if start_disposition is not None:
            value["startDisposition"] = start_disposition

    update_json(state_path, state_path.parent / ".state.lock", change)


def worker(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project_root)
    state_path = state_file(project_root, args.agent, args.run_id)
    state = safe_read_json(state_path)
    worker_identity = linux_process_identity(os.getpid())
    update_json(
        state_path,
        state_path.parent / ".state.lock",
        lambda value: value.update(
            {"workerPid": os.getpid(), "workerIdentity": worker_identity}
        ),
    )
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
                    disposition = (
                        "started"
                        if failure.started
                        else "launching"
                        if failure.launched
                        else "not-started"
                    )
                    if failure.code == "cancelled":
                        mark_terminal(
                            state_path,
                            "cancelled",
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(status="cancelled", attempt=attempt, codex_pid=None)
                        return 1
                    if failure.started or failure.launched or attempt >= max_attempts:
                        mark_terminal(
                            state_path,
                            "failed",
                            {"code": failure.code, "message": failure.message},
                            attempt=attempt,
                            start_disposition=disposition,
                        )
                        heartbeat.update(
                            status="failed", attempt=attempt, codex_pid=None
                        )
                        return 1
                    state = update_json(
                        state_path,
                        state_path.parent / ".state.lock",
                        lambda value: value.update(
                            {
                                "attempt": attempt,
                                "codexPid": None,
                                "codexIdentity": None,
                                "status": "queued",
                                "startDisposition": disposition,
                            }
                        ),
                    )
                    heartbeat.update(status="queued", attempt=attempt, codex_pid=None)
            failure = AttemptFailure(
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
        "startDisposition",
        "maxAttempts",
        "sessionId",
        "requestPath",
        "statePath",
        "resultPath",
        "receiptPath",
        "receiptSchemaPath",
        "receiptRequestHash",
        "capabilityBindingPath",
        "capabilityBindingHash",
        "verifiedWorkRunId",
        "dispatchId",
        "dispatchTuple",
        "eventsPath",
        "heartbeatPath",
        "acceptedAt",
        "startedAt",
        "finishedAt",
        "updatedAt",
        "workerPid",
        "workerIdentity",
        "containmentAttempt",
        "containment",
        "containmentLaunchDisposition",
        "codexPid",
        "codexIdentity",
        "lastCodexIdentity",
        "unread",
        "error",
    )
    public = {key: state.get(key) for key in keys if key in state}
    if state.get("role") not in {"work", "verification"}:
        public.pop("statePath", None)
    return public


def find_run(project_root: Path, agent_id: str, run_id: str) -> dict[str, Any]:
    return safe_read_json(state_file(project_root, agent_id, run_id))


def command_status(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.project_root)
    dispatch_id = getattr(args, "dispatch_id", None)
    if dispatch_id is not None:
        validate_id(dispatch_id, DISPATCH_ID, "dispatch_id")
        matches = [state for state in iter_run_states(root, args.agent) if state.get("dispatchId") == dispatch_id]
        if not matches:
            raise ContractError("dispatch_not_found", "dispatch identifier has no managed run")
        if len(matches) != 1:
            raise ContractError("dispatch_id_collision", "dispatch identifier is not unique")
        state = matches[0]
    else:
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
    containment_value = state.get("containment")
    if containment_value is None:
        validate_state_containment_fields(state)
        identities = (
            ("Codex", state.get("codexIdentity")),
            ("worker", state.get("workerIdentity")),
        )
        statuses = [(label, identity, process_identity_status(identity)) for label, identity in identities if identity is not None]
        if any(status in {"unknown", "mismatch"} for _label, _identity, status in statuses):
            raise ContractError(
                "process_identity_mismatch",
                "managed process identity could not be verified; refusing to signal",
            )
        if "containmentAttempt" in state and statuses:
            raise ContractError(
                "containment_identity_unbound",
                "managed processes exist without a bound containment identity; refusing to signal",
            )
        # Migration compatibility for runs accepted before containment binding existed.
        codex_identity = state.get("codexIdentity")
        if isinstance(codex_identity, dict) and process_identity_status(codex_identity) in {"match", "dead"}:
            terminate_verified_group(codex_identity)
        worker_identity = state.get("workerIdentity")
        if isinstance(worker_identity, dict) and process_identity_status(worker_identity) == "match":
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(worker_identity["pid"]), signal.SIGTERM)
    else:
        containment = _validate_state_containment(state)
        if containment["kind"] == "process-group":
            codex_identity = state.get("codexIdentity")
            if codex_identity is not None and process_identity_status(codex_identity) in {"unknown", "mismatch"}:
                raise ContractError(
                    "process_identity_mismatch",
                    "managed Codex identity could not be verified; refusing to signal",
                )
            if isinstance(codex_identity, dict):
                terminate_verified_group(codex_identity)
        request_containment_stop(containment)
        if not wait_containment_empty(containment, PROCESS_TERM_TIMEOUT):
            force_containment_stop(containment)
        if not wait_containment_empty(containment, PROCESS_KILL_TIMEOUT):
            raise ContractError("containment_not_empty", "managed containment did not become empty")
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


def event_stream_has_start_marker(state: dict[str, Any]) -> bool:
    try:
        content = safe_read_bytes(Path(state["eventsPath"]), MAX_REQUEST_BYTES)
    except ContractError as error:
        if error.code == "file_not_found":
            return False
        return True
    try:
        lines = content.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError:
        return True
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return True
        if isinstance(event, dict) and event.get("type") == "thread.started":
            return True
    return False


def durably_never_started(state: dict[str, Any]) -> bool:
    return (
        state.get("startDisposition") == "not-started"
        and state.get("containmentLaunchDisposition") != "launching"
        and state.get("status") in {"accepted", "queued"}
        and state.get("startedAt") is None
        and state.get("sessionId") is None
        and not event_stream_has_start_marker(state)
    )


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
        containment_value = state.get("containment")
        if containment_value is not None:
            try:
                containment = _validate_state_containment(state)
                if not containment_is_empty(containment):
                    reconciled.append(
                        {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
                    )
                    continue
            except ContractError:
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            # A positively empty bound containment is evaluated below against
            # semantic start evidence; it is never inferred from a numeric PID.
            identity_statuses: list[str] = ["dead"]
        else:
            try:
                validate_state_containment_fields(state)
            except ContractError:
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            if "containmentAttempt" in state and (
                state.get("workerIdentity") is not None or state.get("codexIdentity") is not None
            ):
                reconciled.append(
                    {"agentId": agent_id, "runId": state["runId"], "action": "stale-containment-unknown"}
                )
                continue
            # Legacy states retain their exact boot-ID/start-ticks behavior.
            identity_statuses = [
                process_identity_status(identity)
                for identity in (state.get("workerIdentity"), state.get("codexIdentity"))
                if identity is not None
            ]
        if any(status == "match" for status in identity_statuses):
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "stale-alive"}
            )
            continue
        if not identity_statuses or any(status == "unknown" for status in identity_statuses):
            reconciled.append(
                {
                    "agentId": agent_id,
                    "runId": state["runId"],
                    "action": "stale-identity-unknown",
                }
            )
            continue
        if not durably_never_started(state):
            path = state_file(root, agent_id, str(state["runId"]))
            started = (
                state.get("startDisposition") == "started"
                or state.get("startedAt") is not None
                or state.get("sessionId") is not None
                or event_stream_has_start_marker(state)
            )
            code = "started_run_not_replayable" if started else "run_start_unknown"
            mark_terminal(
                path,
                "failed",
                {
                    "code": code,
                    "message": "stale managed run cannot be replayed without durable proof that its semantic turn never started",
                },
            )
            reconciled.append(
                {"agentId": agent_id, "runId": state["runId"], "action": "failed-not-replayable"}
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
        "--verified-work-run-id",
        help="exact Work run checked by a Verification Agent (required for Verification runs)",
    )
    parser.add_argument("--dispatch-id", help="idempotency key scoped to this managed Agent")
    parser.add_argument(
        "--capability-binding-file", type=Path,
        help="strict Agent capability/authority/effects binding to preserve in this run",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(prog="exec.py")
    commands = parser.add_subparsers(dest="command", required=True)

    submit_parser = commands.add_parser("submit")
    add_project_argument(submit_parser)
    add_request_arguments(submit_parser)
    submit_parser.add_argument("--agent", required=True)
    submit_parser.add_argument("--role", required=True)
    submit_parser.add_argument("--codex", default="codex")
    submit_parser.add_argument("--sandbox", choices=SANDBOXES, default=DEFAULT_SANDBOX)
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
        if name == "status":
            identity = command_parser.add_mutually_exclusive_group(required=True)
            identity.add_argument("--run-id")
            identity.add_argument("--dispatch-id")
        else:
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

    bootstrap_parser = commands.add_parser("_bootstrap", help=argparse.SUPPRESS)
    bootstrap_parser.add_argument("--ready-fd", required=True, type=int)
    bootstrap_parser.add_argument("--release-fd", required=True, type=int)
    bootstrap_parser.add_argument("target", nargs=argparse.REMAINDER)

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
        if args.command == "_bootstrap":
            return containment_bootstrap(args)
        raise ContractError("invalid_command", "command is invalid")
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        emit(error_document("runtime_failure", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
