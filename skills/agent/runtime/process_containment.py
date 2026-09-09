"""Linux process identity and containment backends for managed Agent runs."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, IO, Sequence

from runtime_errors import ContractError
import sandbox_diagnostics

PROCESS_TERM_TIMEOUT = 5.0
PROCESS_KILL_TIMEOUT = 5.0
CONTAINMENT_START_TIMEOUT = 5.0
CONTAINMENT_QUERY_TIMEOUT = 2.0
SYSTEMD_UNIT = re.compile(r"^agent-factory-[a-f0-9]{24}\.service$")
SYSTEMD_DESCRIPTION_PREFIX = "Agent Factory containment "
SYSTEMD_REQUIRED_OPTIONS = (
    "--collect", "--service-type=", "--property=", "--working-directory=",
    "--unit=", "--description=", "--user",
)
ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CGROUP_ROOT = Path("/sys/fs/cgroup")
EXEC_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "exec.py"

def require_managed_platform() -> None:
    issue = sandbox_diagnostics.platform_issue()
    if issue:
        raise ContractError(issue["code"], issue["message"])


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
        str(EXEC_SCRIPT),
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
