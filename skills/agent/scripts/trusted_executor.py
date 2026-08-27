#!/usr/bin/env python3
"""Trusted-execution records for the managed Agent runtime.

The workload never supplies evidence.  This module constructs records from the
executor's manifest, observed backend capabilities, exit status, and sealed
files.  Signing keys are referenced by path and are never copied into a run.
"""

from __future__ import annotations

import base64
import contextlib
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "1.0.0"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://agent-factory.dev/attestation/trusted-execution/v1"
PAYLOAD_TYPE = "application/vnd.in-toto+json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARTIFACTS = 10000
IJSON_MAX_INTEGER = (1 << 53) - 1


def _payload_environment_bytes(environment: Mapping[str, str]) -> bytes:
    payload_environment = {key: value for key, value in environment.items() if key != "AF_EXECUTOR_UMASK"}
    return json.dumps(payload_environment, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _python_bootstrap(*, apply_umask: bool) -> str:
    umask = "os.umask(int(os.environ.pop('AF_EXECUTOR_UMASK','0022'),8))" if apply_umask else "os.environ.pop('AF_EXECUTOR_UMASK',None)"
    return "\n".join((
        "import json,os,sys",
        "payload_environment_data=os.fdopen(int(sys.argv[3]),'rb').read()",
        "os.write(int(sys.argv[1]),b'R')",
        "ok=os.read(int(sys.argv[2]),1)",
        "if ok != b'G': sys.exit(125)",
        umask,
        "payload_environment=json.loads(payload_environment_data)",
        "os.execvpe(sys.argv[4],sys.argv[4:],payload_environment)",
    ))


def _write_all(fd: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise OSError("payload environment pipe made no progress")
        remaining = remaining[written:]


def _spawn_python_bootstrap(bootstrap: str, ready_write: int, release_read: int, argv: Sequence[str], *, cwd: Path, environment: Mapping[str, str], stdin: Any = None, stdout: Any = None) -> subprocess.Popen[bytes]:
    environment_read, environment_write = os.pipe()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", bootstrap, str(ready_write), str(release_read), str(environment_read), *argv],
            cwd=cwd,
            env=dict(environment),
            stdin=stdin,
            stdout=stdout,
            pass_fds=(ready_write, release_read, environment_read),
            close_fds=True,
            start_new_session=True,
        )
        os.close(environment_read)
        environment_read = -1
        _write_all(environment_write, _payload_environment_bytes(environment))
        os.close(environment_write)
        environment_write = -1
        return process
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise
    finally:
        if environment_read >= 0:
            os.close(environment_read)
        if environment_write >= 0:
            os.close(environment_write)


class ExecutorError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _exact(value: object, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ExecutorError("manifest_invalid", f"{label} has unknown or missing fields")
    return value


def canonical_bytes(value: object) -> bytes:
    """Serialize the executor's float-free I-JSON domain using RFC 8785/JCS."""
    def string(value: str) -> str:
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ExecutorError("manifest_invalid", "lone UTF-16 surrogates are forbidden")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def utf16_key(value: str) -> bytes:
        string(value)
        return value.encode("utf-16-be")

    def encode(item: object) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            if not -IJSON_MAX_INTEGER <= item <= IJSON_MAX_INTEGER:
                raise ExecutorError("manifest_invalid", "integer is outside the I-JSON exact range")
            return str(item)
        if isinstance(item, float):
            raise ExecutorError("manifest_invalid", "floating point JSON is forbidden")
        if isinstance(item, str):
            return string(item)
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            ordered = sorted(item, key=utf16_key)
            return "{" + ",".join(string(key) + ":" + encode(item[key]) for key in ordered) + "}"
        raise ExecutorError("manifest_invalid", "unsupported JSON value")

    return encode(value).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular(path: Path, maximum: int = MAX_MANIFEST_BYTES) -> bytes:
    try:
        info = os.lstat(path)
    except OSError as error:
        raise ExecutorError("file_not_found", str(path)) from error
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_size > maximum:
        raise ExecutorError("artifact_path_invalid", f"unsafe or oversized file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ExecutorError("artifact_mutated", f"file changed before read: {path}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, maximum + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > maximum:
                raise ExecutorError("artifact_path_invalid", f"file too large: {path}")
            chunks.append(chunk)
        after = os.fstat(fd)
        if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns
        ):
            raise ExecutorError("artifact_mutated", f"file changed during read: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


MANIFEST_FIELDS = {
    "schemaVersion", "kind", "source", "dependencies", "toolchain", "environment",
    "platform", "command", "policy", "outputs", "builder",
}


def load_manifest(path: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = read_regular(path)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutorError("manifest_invalid", "manifest is not valid UTF-8 JSON") from error
    manifest = validate_manifest(value)
    encoded = canonical_bytes(manifest)
    return manifest, encoded, digest_bytes(encoded)


def require_managed_run_directory(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    parts = resolved.parts
    matches = [index for index in range(len(parts) - 4) if parts[index:index + 3] == (".agent-factory", "agent", parts[index + 2]) and parts[index + 3] == "runs"]
    if not matches or matches[-1] + 5 != len(parts):
        raise ExecutorError("artifact_path_invalid", "run directory is not an exact managed Agent run")
    cursor = Path(parts[0])
    for part in parts[1:]:
        cursor /= part
        info = os.lstat(cursor)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ExecutorError("artifact_path_invalid", "managed run path contains an unsafe component")
    return resolved


def _safe_relative(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.replace(os.sep, "/"))
    path = PurePosixPath(normalized)
    if path.is_absolute() or not normalized or ".." in path.parts or any(ord(c) < 32 for c in normalized):
        raise ExecutorError("artifact_path_invalid", f"invalid artifact path: {value!r}")
    return normalized


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes + b" " + str(len(payload)).encode() + b" " + payload


def _openssl(arguments: Sequence[str], *, data: bytes | None = None) -> bytes:
    executable = shutil.which("openssl")
    if executable is None:
        raise ExecutorError("signing_identity_unavailable", "OpenSSL is required for this signing profile")
    completed = subprocess.run([executable, *arguments], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise ExecutorError("signing_failed", completed.stderr.decode("utf-8", "replace").strip() or "OpenSSL failed")
    return completed.stdout


def public_key_id(public_key: Path) -> str:
    der = _openssl(["pkey", "-pubin", "-in", str(public_key), "-outform", "DER"])
    return "sha256:" + digest_bytes(der)


def create_statement(*, run_id: str, manifest_digest: str, terminal_digest: str, manifest: Mapping[str, Any], index: Mapping[str, Any], status: str, capabilities: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": "artifact-set", "digest": {"sha256": index["rootDigest"]}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schemaVersion": SCHEMA_VERSION,
            "runIdentity": {"runId": run_id},
            "manifestDigest": {"sha256": manifest_digest},
            "terminalObservationDigest": {"sha256": terminal_digest},
            "result": {"status": status},
            "command": manifest["command"],
            "requestedPolicy": manifest["policy"],
            "observedCapabilities": capabilities,
            "artifactIndexDigest": {"sha256": digest_bytes(canonical_bytes(index))},
            "artifactSubjects": index["artifacts"],
        },
    }


def _verify_signed_bundle(*, run_dir: Path, bundle_path: Path, public_key: Path, expected_run_id: str, manifest_path: Path, index_path: Path) -> dict[str, Any]:
    try:
        bundle = json.loads(read_regular(bundle_path))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutorError("signature_invalid", "DSSE envelope is malformed") from error
    _exact(bundle, {"payloadType", "payload", "signatures"}, "DSSE envelope")
    if bundle["payloadType"] != PAYLOAD_TYPE or not isinstance(bundle["signatures"], list) or len(bundle["signatures"]) != 1:
        raise ExecutorError("signature_invalid", "DSSE envelope identity is invalid")
    signature = _exact(bundle["signatures"][0], {"keyid", "sig"}, "DSSE signature")
    if signature["keyid"] != public_key_id(public_key):
        raise ExecutorError("signature_invalid", "signature key is not trusted")
    try:
        payload = base64.b64decode(bundle["payload"], validate=True)
        signature_bytes = base64.b64decode(signature["sig"], validate=True)
    except (ValueError, TypeError) as error:
        raise ExecutorError("signature_invalid", "DSSE base64 is invalid") from error
    with tempfile.TemporaryDirectory() as temporary:
        sig_path = Path(temporary) / "signature"
        sig_path.write_bytes(signature_bytes)
        executable = shutil.which("openssl")
        if executable is None:
            raise ExecutorError("signing_identity_unavailable", "OpenSSL is required for verification")
        completed = subprocess.run([executable, "dgst", "-sha256", "-verify", str(public_key), "-signature", str(sig_path)], input=dsse_pae(PAYLOAD_TYPE, payload), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if completed.returncode:
            raise ExecutorError("signature_invalid", "DSSE signature verification failed")
    try:
        statement = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutorError("signature_invalid", "signed payload is malformed") from error
    _exact(statement, {"_type", "subject", "predicateType", "predicate"}, "statement")
    predicate = _exact(statement["predicate"], {"schemaVersion", "runIdentity", "manifestDigest", "terminalObservationDigest", "result", "command", "requestedPolicy", "observedCapabilities", "artifactIndexDigest", "artifactSubjects"}, "predicate")
    if statement["_type"] != STATEMENT_TYPE or statement["predicateType"] != PREDICATE_TYPE or predicate["runIdentity"] != {"runId": expected_run_id}:
        raise ExecutorError("provenance_policy_mismatch", "statement run identity or type differs")
    manifest, manifest_encoded, manifest_digest = _bound_manifest(run_dir, manifest_path)
    index = verify_artifacts(run_dir, index_path)
    journal = Journal(run_dir).read()
    terminal_digest = _bound_terminal_digest(run_dir, journal)
    if predicate["manifestDigest"] != {"sha256": manifest_digest} or predicate["terminalObservationDigest"] != {"sha256": terminal_digest} or predicate["command"] != manifest["command"] or predicate["requestedPolicy"] != manifest["policy"]:
        raise ExecutorError("provenance_policy_mismatch", "manifest binding differs")
    if statement["subject"] != [{"name": "artifact-set", "digest": {"sha256": index["rootDigest"]}}] or predicate["artifactSubjects"] != index["artifacts"] or predicate["artifactIndexDigest"] != {"sha256": digest_bytes(canonical_bytes(index))}:
        raise ExecutorError("provenance_policy_mismatch", "artifact binding differs")
    return {
        "result": {"verified": True, "runId": expected_run_id, "manifestDigest": digest_bytes(manifest_encoded), "artifactRootDigest": index["rootDigest"], "keyId": signature["keyid"]},
        "statement": statement,
    }


def capability_report(backend: str = "auto") -> dict[str, Any]:
    selected = platform.system().lower() if backend == "auto" else backend
    base: dict[str, Any] = {"backend": selected, "filesystemIsolation": "none", "networkIsolation": "none", "timeControl": "none", "randomnessControl": "none", "controlPlaneIsolation": "none", "artifactPublication": "posix-descriptor" if os.name != "nt" else "unavailable", "cgroupDelegated": False}
    if selected == "linux":
        if sys.platform != "linux":
            raise ExecutorError("capability_unsatisfied", "Linux backend is unavailable on this host")
        delegate = os.environ.get("AF_CGROUP_DELEGATE")
        cgroup = Path(delegate) if delegate else Path("/__agent_factory_no_cgroup_delegate__")
        pidfd = hasattr(os, "pidfd_open") and hasattr(__import__("signal"), "pidfd_send_signal")
        delegated = cgroup.is_dir() and os.access(cgroup, os.W_OK) and (cgroup / "cgroup.kill").exists()
        base.update({"processTree": "cgroup-v2" if delegated else "process-group-compatibility", "stableLeaderIdentity": "pidfd" if pidfd else "unavailable", "resourceLimits": [], "grade": "contained" if delegated and pidfd else "best-effort-tree", "cgroupDelegated": delegated})
    elif selected == "windows":
        if sys.platform != "win32":
            raise ExecutorError("capability_unsatisfied", "Windows backend is unavailable on this host")
        backend_instance = WindowsJobBackend()
        handle = backend_instance.create({"cpu": "50000 100000", "memoryBytes": 268435456, "pids": 16})
        backend_instance.kernel32.CloseHandle(handle)
        base.update({"processTree": "job-object", "stableLeaderIdentity": "process-handle", "resourceLimits": ["cpu", "memory", "pids"], "grade": "contained"})
    elif selected in {"darwin", "macos"}:
        if sys.platform != "darwin":
            raise ExecutorError("capability_unsatisfied", "macOS backend is unavailable on this host")
        base.update({"backend": "macos", "processTree": "process-group-best-effort", "stableLeaderIdentity": "process-handle", "resourceLimits": ["per-process"], "grade": "best-effort-tree"})
    else:
        raise ExecutorError("capability_unsatisfied", f"unsupported backend: {selected}")
    return base


def require_capabilities(manifest: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    grades = {"best-effort-tree": 0, "contained": 1, "hermetic": 2}
    required = manifest["builder"]["requiredGrade"]
    if grades.get(str(observed.get("grade")), -1) < grades[required]:
        raise ExecutorError("capability_unsatisfied", f"required {required}, observed {observed.get('grade')}")
    policy = manifest["policy"]
    if manifest["source"]["ignoredPolicy"] == "exclude-and-unmount" and observed.get("filesystemIsolation") == "none":
        raise ExecutorError("capability_unsatisfied", "exclude-and-unmount source closure is not enforced")
    if observed.get("controlPlaneIsolation") == "none":
        raise ExecutorError("capability_unsatisfied", "executor control-plane isolation is unavailable")
    if observed.get("artifactPublication") == "unavailable":
        raise ExecutorError("capability_unsatisfied", "reparse-safe artifact publication is unavailable")
    if policy["network"]["mode"] == "deny" and observed.get("networkIsolation") == "none":
        raise ExecutorError("capability_unsatisfied", "network denial was requested but not enforced")
    if policy["filesystem"]["mode"] != "host" and observed.get("filesystemIsolation") == "none":
        raise ExecutorError("capability_unsatisfied", "filesystem isolation was requested but not enforced")
    if policy["time"]["mode"] == "fixed" and observed.get("timeControl") == "none":
        raise ExecutorError("capability_unsatisfied", "fixed time was requested but not enforced")
    if policy["randomness"]["mode"] == "deterministic" and observed.get("randomnessControl") == "none":
        raise ExecutorError("capability_unsatisfied", "deterministic randomness was requested but not enforced")
    if policy["limits"].get("enforce") and not {"cpu", "memory", "pids"}.issubset(set(observed.get("resourceLimits", []))):
        raise ExecutorError("capability_unsatisfied", "requested resource limits were not enforced")


class WindowsJobBackend:
    """Import-safe ctypes declarations; methods refuse use off Windows."""
    CREATE_SUSPENDED = 0x00000004
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ExecutorError("capability_unsatisfied", "Windows Job Objects are unavailable")
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self.kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        self.kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.kernel32.ResumeThread.argtypes = [ctypes.c_void_p]
        self.kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        self.kernel32.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

    def create(self, limits_policy: Mapping[str, Any] | None = None) -> int:
        handle = self.kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ExecutorError("containment_start_failed", "CreateJobObjectW failed")
        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32), ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        limits = EXTENDED()
        limits.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        cpu_rate = None
        if limits_policy is not None:
            try:
                quota_text, period_text = str(limits_policy["cpu"]).split()
                quota, period = int(quota_text), int(period_text)
                memory, pids = int(limits_policy["memoryBytes"]), int(limits_policy["pids"])
                cpu_rate = max(1, min(10000, quota * 10000 // period))
            except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
                self.kernel32.CloseHandle(handle)
                raise ExecutorError("manifest_invalid", "Windows Job limits are invalid") from error
            limits.BasicLimitInformation.LimitFlags |= self.JOB_OBJECT_LIMIT_ACTIVE_PROCESS | self.JOB_OBJECT_LIMIT_JOB_MEMORY
            limits.BasicLimitInformation.ActiveProcessLimit = pids
            limits.JobMemoryLimit = memory
        if not self.kernel32.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.kernel32.CloseHandle(handle)
            raise ExecutorError("containment_start_failed", "KILL_ON_JOB_CLOSE could not be enabled")
        observed = EXTENDED()
        returned = ctypes.c_uint32()
        expected_flags = limits.BasicLimitInformation.LimitFlags
        if not self.kernel32.QueryInformationJobObject(handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), ctypes.byref(returned)) or observed.BasicLimitInformation.LimitFlags & expected_flags != expected_flags:
            self.kernel32.CloseHandle(handle)
            raise ExecutorError("containment_start_failed", "Job containment settings could not be read back")
        if limits_policy is not None and (observed.BasicLimitInformation.ActiveProcessLimit != pids or observed.JobMemoryLimit != memory):
            self.kernel32.CloseHandle(handle)
            raise ExecutorError("capability_unsatisfied", "Windows memory or PID limit readback differs")
        if cpu_rate is not None:
            class CPU_RATE(ctypes.Structure):
                _fields_ = [("ControlFlags", ctypes.c_uint32), ("CpuRate", ctypes.c_uint32)]
            requested_cpu = CPU_RATE(self.JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | self.JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP, cpu_rate)
            if not self.kernel32.SetInformationJobObject(handle, 15, ctypes.byref(requested_cpu), ctypes.sizeof(requested_cpu)):
                self.kernel32.CloseHandle(handle)
                raise ExecutorError("capability_unsatisfied", "Windows CPU hard cap could not be configured")
            observed_cpu = CPU_RATE()
            if not self.kernel32.QueryInformationJobObject(handle, 15, ctypes.byref(observed_cpu), ctypes.sizeof(observed_cpu), ctypes.byref(returned)) or observed_cpu.ControlFlags != requested_cpu.ControlFlags or observed_cpu.CpuRate != requested_cpu.CpuRate:
                self.kernel32.CloseHandle(handle)
                raise ExecutorError("capability_unsatisfied", "Windows CPU hard cap readback differs")
        return int(handle)

    def spawn_suspended(self, job: int, argv: Sequence[str], cwd: Path, environment: Mapping[str, str], contained: Any = lambda: None, owned: Any = lambda _process, _thread, _assigned: None) -> tuple[int, int, int]:
        class STARTUPINFO(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("lpReserved", ctypes.c_wchar_p), ("lpDesktop", ctypes.c_wchar_p), ("lpTitle", ctypes.c_wchar_p), ("dwX", ctypes.c_uint32), ("dwY", ctypes.c_uint32), ("dwXSize", ctypes.c_uint32), ("dwYSize", ctypes.c_uint32), ("dwXCountChars", ctypes.c_uint32), ("dwYCountChars", ctypes.c_uint32), ("dwFillAttribute", ctypes.c_uint32), ("dwFlags", ctypes.c_uint32), ("wShowWindow", ctypes.c_uint16), ("cbReserved2", ctypes.c_uint16), ("lpReserved2", ctypes.c_void_p), ("hStdInput", ctypes.c_void_p), ("hStdOutput", ctypes.c_void_p), ("hStdError", ctypes.c_void_p)]
        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [("hProcess", ctypes.c_void_p), ("hThread", ctypes.c_void_p), ("dwProcessId", ctypes.c_uint32), ("dwThreadId", ctypes.c_uint32)]
        startup = STARTUPINFO()
        startup.cb = ctypes.sizeof(startup)
        process = PROCESS_INFORMATION()
        command = subprocess.list2cmdline(list(argv))
        buffer = ctypes.create_unicode_buffer(command)
        env_block = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(environment.items())) + "\0\0")
        created = self.kernel32.CreateProcessW(None, buffer, None, None, False, self.CREATE_SUSPENDED | self.CREATE_UNICODE_ENVIRONMENT, env_block, str(cwd), ctypes.byref(startup), ctypes.byref(process))
        if not created:
            raise ExecutorError("containment_start_failed", "CreateProcessW suspended launch failed")
        owned(int(process.hProcess), int(process.hThread), False)
        if not self.kernel32.AssignProcessToJobObject(job, process.hProcess):
            raise ExecutorError("job_assignment_unsupported", "process could not be assigned before release")
        owned(int(process.hProcess), int(process.hThread), True)
        contained()
        if self.kernel32.ResumeThread(process.hThread) == 0xFFFFFFFF:
            raise ExecutorError("containment_start_failed", "suspended process could not be released")
        return int(process.hProcess), int(process.hThread), int(process.dwProcessId)

    def terminate_and_wait(self, job: int, process_handle: int, timeout_ms: int = 5000) -> None:
        if not self.kernel32.TerminateJobObject(job, 1):
            raise ExecutorError("process_identity_lost", "TerminateJobObject failed")
        if self.kernel32.WaitForSingleObject(process_handle, timeout_ms) == 0x102:
            raise ExecutorError("process_identity_lost", "Job process tree did not quiesce")

    def terminate_process_and_wait(self, process_handle: int, timeout_ms: int = 5000) -> None:
        if not self.kernel32.TerminateProcess(process_handle, 125):
            raise ExecutorError("process_identity_lost", "TerminateProcess failed")
        if self.kernel32.WaitForSingleObject(process_handle, timeout_ms) == 0x102:
            raise ExecutorError("process_identity_lost", "unassigned Windows process did not quiesce")

    def active_processes(self, job: int) -> int:
        class ACCOUNTING(ctypes.Structure):
            _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong), ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong), ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32), ("ActiveProcesses", ctypes.c_uint32), ("TotalTerminatedProcesses", ctypes.c_uint32)]
        value = ACCOUNTING()
        returned = ctypes.c_uint32()
        if not self.kernel32.QueryInformationJobObject(job, 1, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(returned)):
            raise ExecutorError("process_identity_lost", "Job active process count is unavailable")
        return int(value.ActiveProcesses)


@dataclass
class LinuxCgroupBackend:
    delegated_root: Path

    def create(self, run_id: str, limits: Mapping[str, Any]) -> Path:
        if sys.platform != "linux" or not (self.delegated_root / "cgroup.kill").exists():
            raise ExecutorError("capability_unsatisfied", "delegated cgroup v2 with cgroup.kill is required")
        target = self.delegated_root / ("agent-factory-" + re.sub(r"[^A-Za-z0-9_.-]", "-", run_id))
        target.mkdir(mode=0o700)
        for key, file_name in (("pids", "pids.max"), ("memoryBytes", "memory.max"), ("cpu", "cpu.max")):
            if key in limits:
                requested = str(limits[key])
                control = target / file_name
                control.write_text(requested, encoding="ascii")
                observed = control.read_text(encoding="ascii").strip()
                if observed.split() != requested.split():
                    self.kill(target)
                    raise ExecutorError("capability_unsatisfied", f"{file_name} readback differs")
        return target

    def attach(self, target: Path, pid: int) -> int:
        if not hasattr(os, "pidfd_open"):
            raise ExecutorError("capability_unsatisfied", "pidfd_open is required")
        pidfd = os.pidfd_open(pid, 0)
        (target / "cgroup.procs").write_text(str(pid), encoding="ascii")
        return pidfd

    def kill(self, target: Path) -> None:
        (target / "cgroup.kill").write_text("1", encoding="ascii")

    def spawn(self, target: Path, argv: Sequence[str], *, cwd: Path, environment: Mapping[str, str], contained: Any = lambda: None) -> tuple[subprocess.Popen[bytes], int]:
        ready_read, ready_write = os.pipe()
        release_read, release_write = os.pipe()
        bootstrap = _python_bootstrap(apply_umask=True)
        process = _spawn_python_bootstrap(bootstrap, ready_write, release_read, argv, cwd=cwd, environment=environment)
        os.close(ready_write)
        os.close(release_read)
        pidfd: int | None = None
        try:
            if os.read(ready_read, 1) != b"R":
                raise ExecutorError("containment_start_failed", "Linux startup barrier failed")
            pidfd = self.attach(target, process.pid)
            contained()
            os.write(release_write, b"G")
            return process, pidfd
        except BaseException:
            self.kill(target)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
            if pidfd is not None:
                os.close(pidfd)
            raise
        finally:
            os.close(ready_read)
            os.close(release_write)


class MacOSProcessBackend:
    """Compatibility cleanup only; this is explicitly not a security sandbox."""
    capabilities = {"processTree": "process-group-best-effort", "stableLeaderIdentity": "process-handle", "resourceLimits": ["per-process"], "filesystemIsolation": "none", "networkIsolation": "none", "timeControl": "none", "randomnessControl": "none", "grade": "best-effort-tree"}

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise ExecutorError("capability_unsatisfied", "macOS process backend is unavailable")

    def spawn(self, argv: Sequence[str], *, cwd: Path, environment: Mapping[str, str]) -> tuple[subprocess.Popen[bytes], int]:
        ready_read, ready_write = os.pipe()
        release_read, release_write = os.pipe()
        bootstrap = _python_bootstrap(apply_umask=False)
        process = _spawn_python_bootstrap(bootstrap, ready_write, release_read, argv, cwd=cwd, environment=environment)
        os.close(ready_write)
        os.close(release_read)
        try:
            if os.read(ready_read, 1) != b"R" or os.getpgid(process.pid) != process.pid:
                raise ExecutorError("containment_start_failed", "macOS startup barrier failed")
            os.write(release_write, b"G")
            return process, process.pid
        finally:
            os.close(ready_read)
            os.close(release_write)

    def terminate_and_wait(self, process: subprocess.Popen[bytes], pgid: int, timeout: float = 5.0) -> None:
        os.killpg(pgid, 15)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(pgid, 9)
            process.wait(timeout=timeout)


def compare_records(left_manifest: Path, right_manifest: Path, left_index: Path, right_index: Path) -> dict[str, Any]:
    _, _, left_identity = load_manifest(left_manifest)
    _, _, right_identity = load_manifest(right_manifest)
    left = verify_artifacts(left_index.resolve().parent, left_index)
    right = verify_artifacts(right_index.resolve().parent, right_index)
    differences = []
    lmap = {item["path"]: item["sha256"] for item in left.get("artifacts", [])}
    rmap = {item["path"]: item["sha256"] for item in right.get("artifacts", [])}
    for path in sorted(set(lmap) | set(rmap)):
        if lmap.get(path) != rmap.get(path):
            differences.append({"path": path, "left": lmap.get(path), "right": rmap.get(path)})
    identical = left_identity == right_identity and left.get("rootDigest") == right.get("rootDigest") and not differences
    if not identical:
        raise ExecutorError("reproducibility_mismatch", json.dumps({"differences": differences}, sort_keys=True))
    return {"comparison": "identical", "executionHash": left_identity, "artifactRootDigest": left["rootDigest"], "differences": []}


# Executor lifecycle and descriptor-safe record implementation.
PHASES = ("prepared", "contained", "launching", "launched", "observed", "quiescent", "sealed", "attested", "verified")
CAPABILITY_FIELDS = {"backend", "processTree", "stableLeaderIdentity", "resourceLimits", "filesystemIsolation", "networkIsolation", "timeControl", "randomnessControl", "controlPlaneIsolation", "artifactPublication", "grade", "cgroupDelegated"}


class Journal:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.path = run_dir / "execution.journal.json"

    def read(self) -> dict[str, Any]:
        try:
            with TrustedDirectory(self.run_dir) as run_cap:
                value = json.loads(run_cap.read("execution.journal.json", MAX_MANIFEST_BYTES))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ExecutorError("journal_invalid", "execution journal is malformed") from error
        _exact(value, {"schemaVersion", "kind", "runId", "phase", "manifestDigest", "capabilities", "result", "terminalObservationDigest"}, "journal")
        if value["schemaVersion"] != SCHEMA_VERSION or value["kind"] != "execution-journal" or value["runId"] != self.run_dir.name or value["phase"] not in PHASES:
            raise ExecutorError("journal_invalid", "execution journal binding is invalid")
        return value

    def create(self, manifest_digest: str) -> dict[str, Any]:
        value = {"schemaVersion": SCHEMA_VERSION, "kind": "execution-journal", "runId": self.run_dir.name, "phase": "prepared", "manifestDigest": manifest_digest, "capabilities": None, "result": None, "terminalObservationDigest": None}
        with TrustedDirectory(self.run_dir) as run_cap:
            try:
                run_cap.publish("execution.journal.json", canonical_bytes(value), 0o400, exclusive=True)
            except ExecutorError as error:
                raise ExecutorError("journal_phase_invalid", "execution journal already exists") from error
        return value

    def advance(self, phase: str, *, capabilities: Mapping[str, Any] | None = None, result: Mapping[str, Any] | None = None, terminal_digest: str | None = None) -> dict[str, Any]:
        value = self.read()
        expected = PHASES.index(value["phase"]) + 1
        terminal_from_launch = phase == "observed" and value["phase"] in {"prepared", "contained", "launching", "launched"}
        if not terminal_from_launch and (expected >= len(PHASES) or PHASES[expected] != phase):
            raise ExecutorError("journal_phase_invalid", f"cannot advance {value['phase']} to {phase}")
        value["phase"] = phase
        if capabilities is not None:
            value["capabilities"] = dict(capabilities)
        if result is not None:
            value["result"] = dict(result)
        if terminal_digest is not None:
            value["terminalObservationDigest"] = _strict_sha(terminal_digest, "terminal observation digest")
        with TrustedDirectory(self.run_dir) as run_cap:
            run_cap.publish("execution.journal.json", canonical_bytes(value), 0o400)
        return value

    def require(self, phase: str) -> dict[str, Any]:
        value = self.read()
        if value["phase"] != phase:
            raise ExecutorError("journal_phase_invalid", f"operation requires journal phase {phase}")
        return value


def _bound_manifest(run_dir: Path, supplied_path: Path | None = None) -> tuple[dict[str, Any], bytes, str]:
    fixed = run_dir.resolve(strict=True) / "execution.manifest.json"
    if supplied_path is not None and supplied_path.resolve(strict=True) != fixed:
        raise ExecutorError("provenance_policy_mismatch", "caller manifest is not the prepared manifest")
    manifest, encoded, identity = load_manifest(fixed)
    if Journal(run_dir).read()["manifestDigest"] != identity:
        raise ExecutorError("provenance_policy_mismatch", "prepared manifest binding differs from the journal")
    return manifest, encoded, identity


def _terminal_observation(run_dir: Path, result: Mapping[str, Any]) -> str:
    observation = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "terminal-observation",
        "runId": run_dir.name,
        "result": dict(result),
    }
    encoded = canonical_bytes(observation)
    with TrustedDirectory(run_dir) as run_cap:
        run_cap.publish("terminal.observation.json", encoded, 0o400)
    return digest_bytes(encoded)


def _bound_terminal_digest(run_dir: Path, journal: Mapping[str, Any]) -> str:
    digest = _strict_sha(journal.get("terminalObservationDigest"), "terminal observation digest")
    with TrustedDirectory(run_dir) as run_cap:
        encoded = run_cap.read("terminal.observation.json", MAX_MANIFEST_BYTES)
    if digest_bytes(encoded) != digest:
        raise ExecutorError("provenance_policy_mismatch", "terminal observation binding differs")
    return digest


class TrustedDirectory:
    """A directory capability used for relative, no-follow publication."""
    def __init__(self, path: Path) -> None:
        self.path = path.resolve(strict=True)
        info = os.lstat(self.path)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ExecutorError("artifact_path_invalid", "trusted directory is unsafe")
        self.identity = (info.st_dev, info.st_ino)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(self.path, flags)
        opened = os.fstat(self.fd)
        if (opened.st_dev, opened.st_ino) != self.identity:
            os.close(self.fd)
            raise ExecutorError("artifact_mutated", "trusted directory changed while opening")

    def close(self) -> None:
        os.close(self.fd)

    def __enter__(self) -> "TrustedDirectory":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _check(self) -> None:
        current = os.fstat(self.fd)
        named = os.lstat(self.path)
        if (current.st_dev, current.st_ino) != self.identity or (named.st_dev, named.st_ino) != self.identity or stat.S_ISLNK(named.st_mode):
            raise ExecutorError("artifact_mutated", "trusted directory was replaced")

    def child(self, relative: str, *, create: bool = False) -> "TrustedDirectory":
        if os.name == "nt":
            raise ExecutorError("capability_unsatisfied", "descriptor-relative artifact operations require a native Windows directory-handle provider")
        relative = _safe_relative(relative)
        cursor_fd = os.dup(self.fd)
        cursor_path = self.path
        try:
            for part in PurePosixPath(relative).parts:
                cursor_path /= part
                try:
                    next_fd = os.open(part, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=cursor_fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(part, 0o700, dir_fd=cursor_fd)
                    next_fd = os.open(part, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=cursor_fd)
                os.close(cursor_fd)
                cursor_fd = next_fd
            child = object.__new__(TrustedDirectory)
            child.path = cursor_path
            child.fd = cursor_fd
            info = os.fstat(cursor_fd)
            child.identity = (info.st_dev, info.st_ino)
            return child
        except Exception:
            os.close(cursor_fd)
            raise

    def read(self, name: str, maximum: int, expected: os.stat_result | None = None) -> bytes:
        if os.name == "nt":
            raise ExecutorError("capability_unsatisfied", "descriptor-relative artifact operations require a native Windows directory-handle provider")
        if "/" in name or name in {"", ".", ".."}:
            raise ExecutorError("artifact_path_invalid", "file name is not a single component")
        self._check()
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=self.fd)
        try:
            before = os.fstat(fd)
            if expected is not None and (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino):
                raise ExecutorError("artifact_mutated", "artifact was replaced before opening")
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
                raise ExecutorError("artifact_path_invalid", "unsafe artifact file")
            content = bytearray()
            while True:
                chunk = os.read(fd, min(1024 * 1024, maximum + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > maximum:
                    raise ExecutorError("artifact_path_invalid", "artifact exceeds size limit")
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ExecutorError("artifact_mutated", "artifact changed during read")
            self._check()
            return bytes(content)
        finally:
            os.close(fd)

    def publish(self, name: str, content: bytes, mode: int = 0o400, *, exclusive: bool = False) -> None:
        if os.name == "nt":
            raise ExecutorError("capability_unsatisfied", "descriptor-relative artifact operations require a native Windows directory-handle provider")
        if "/" in name or name in {"", ".", ".."}:
            raise ExecutorError("artifact_path_invalid", "publication name is invalid")
        self._check()
        temporary = f".{name}.{uuid.uuid4().hex}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, flags, 0o600, dir_fd=self.fd)
        try:
            view = memoryview(content)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
            os.fchmod(fd, mode)
        finally:
            os.close(fd)
        try:
            if exclusive:
                try:
                    os.link(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
                except FileExistsError:
                    raise ExecutorError("artifact_digest_mismatch", "conflicting CAS blob already exists")
                os.unlink(temporary, dir_fd=self.fd)
            else:
                os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(temporary, dir_fd=self.fd)
            raise
        self._check()


def _strict_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise ExecutorError("manifest_invalid", f"{label} must be a SHA-256 digest")
    return value


def validate_manifest(value: object) -> dict[str, Any]:
    manifest = _exact(value, MANIFEST_FIELDS, "manifest")
    if manifest["schemaVersion"] != SCHEMA_VERSION or manifest["kind"] != "agent-factory-execution":
        raise ExecutorError("manifest_invalid", "unsupported manifest identity")
    source = _exact(manifest["source"], {"inputs", "ignoredPolicy", "ignoreFileDigests", "submodules", "snapshotDigest"}, "source")
    if source["ignoredPolicy"] not in {"reject", "exclude-and-unmount", "include-by-digest"} or not isinstance(source["inputs"], list) or not isinstance(source["ignoreFileDigests"], dict) or not isinstance(source["submodules"], list):
        raise ExecutorError("manifest_invalid", "source declaration is invalid")
    seen: set[str] = set()
    for item in source["inputs"]:
        entry = _exact(item, {"path", "sha256"}, "source input")
        path = _safe_relative(entry["path"])
        if path in seen:
            raise ExecutorError("manifest_invalid", "duplicate source input")
        seen.add(path)
        _strict_sha(entry["sha256"], "source input digest")
    for path, digest in source["ignoreFileDigests"].items():
        _safe_relative(path); _strict_sha(digest, "ignore file digest")
    for item in source["submodules"]:
        entry = _exact(item, {"path", "url", "commit", "treeDigest"}, "submodule")
        _safe_relative(entry["path"]); _strict_sha(entry["treeDigest"], "submodule tree digest")
        if not all(isinstance(entry[key], str) and entry[key] for key in ("url", "commit")):
            raise ExecutorError("manifest_invalid", "submodule identity is invalid")
    expected_snapshot = digest_bytes(canonical_bytes(source["inputs"]))
    if _strict_sha(source["snapshotDigest"], "source snapshot digest") != expected_snapshot:
        raise ExecutorError("manifest_invalid", "source snapshot digest does not match declared inputs")
    dependencies = _exact(manifest["dependencies"], {"lockfiles", "noExternalDependencies"}, "dependencies")
    if not isinstance(dependencies["lockfiles"], list) or not isinstance(dependencies["noExternalDependencies"], bool) or (not dependencies["lockfiles"] and not dependencies["noExternalDependencies"]):
        raise ExecutorError("lockfile_missing", "lockfiles or explicit no dependencies are required")
    for item in dependencies["lockfiles"]:
        entry = _exact(item, {"path", "ecosystem", "sha256"}, "lockfile")
        _safe_relative(entry["path"]); _strict_sha(entry["sha256"], "lockfile digest")
        if not isinstance(entry["ecosystem"], str) or not entry["ecosystem"]:
            raise ExecutorError("manifest_invalid", "lockfile ecosystem is invalid")
    toolchain = _exact(manifest["toolchain"], {"executables", "interpreter", "runnerImage"}, "toolchain")
    if not isinstance(toolchain["executables"], list):
        raise ExecutorError("manifest_invalid", "toolchain executables must be an array")
    for item in [*toolchain["executables"], toolchain["interpreter"]]:
        entry = _exact(item, {"path", "version", "sha256"}, "toolchain executable")
        if not isinstance(entry["path"], str) or not Path(entry["path"]).is_absolute() or not isinstance(entry["version"], str):
            raise ExecutorError("manifest_invalid", "toolchain executable identity is invalid")
        _strict_sha(entry["sha256"], "toolchain digest")
    runner = _exact(toolchain["runnerImage"], {"kind", "digest", "sbomDigest"}, "runner image")
    if not isinstance(runner["kind"], str) or not runner["kind"]:
        raise ExecutorError("manifest_invalid", "runner image kind is invalid")
    _strict_sha(runner["digest"], "runner image digest"); _strict_sha(runner["sbomDigest"], "runner SBOM digest")
    environment = _exact(manifest["environment"], {"clear", "allow", "forbidPrefixes"}, "environment")
    if environment["clear"] is not True or not isinstance(environment["allow"], dict) or not isinstance(environment["forbidPrefixes"], list) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in environment["allow"].items()) or any(not isinstance(v, str) or not v for v in environment["forbidPrefixes"]):
        raise ExecutorError("manifest_invalid", "environment declaration is invalid")
    if any(key.startswith(prefix) for key in environment["allow"] for prefix in environment["forbidPrefixes"]):
        raise ExecutorError("manifest_invalid", "forbidden environment prefix was allowlisted")
    platform_value = _exact(manifest["platform"], {"os", "architecture", "runnerImageDigest"}, "platform")
    if not isinstance(platform_value["os"], str) or not isinstance(platform_value["architecture"], str):
        raise ExecutorError("manifest_invalid", "platform identity is invalid")
    _strict_sha(platform_value["runnerImageDigest"], "platform runner image digest")
    if platform_value["runnerImageDigest"] != runner["digest"]:
        raise ExecutorError("manifest_invalid", "runner image identities differ")
    command = _exact(manifest["command"], {"argv", "cwd", "stdin", "umask"}, "command")
    if not isinstance(command["argv"], list) or not command["argv"] or any(not isinstance(v, str) or not v for v in command["argv"]) or command["stdin"] != "closed" or not re.fullmatch(r"0[0-7]{3}", str(command["umask"])):
        raise ExecutorError("manifest_invalid", "command declaration is invalid")
    if command["argv"][0] != toolchain["interpreter"]["path"] and command["argv"][0] not in {item["path"] for item in toolchain["executables"]}:
        raise ExecutorError("toolchain_mismatch", "command executable is outside the sealed toolchain")
    _safe_relative(command["cwd"] if command["cwd"] != "." else "workspace")
    policy = _exact(manifest["policy"], {"network", "time", "randomness", "filesystem", "limits"}, "policy")
    network = _exact(policy["network"], {"mode"}, "network policy")
    clock = _exact(policy["time"], {"mode", "unixSeconds"}, "time policy")
    randomness = _exact(policy["randomness"], {"mode", "seedDigest"}, "randomness policy")
    filesystem = _exact(policy["filesystem"], {"mode"}, "filesystem policy")
    limits = _exact(policy["limits"], {"wallSeconds", "memoryBytes", "pids", "cpu", "enforce"}, "limits")
    if network["mode"] not in {"deny", "inherit"} or clock["mode"] not in {"fixed", "host"} or not isinstance(clock["unixSeconds"], int) or randomness["mode"] not in {"deterministic", "host"} or filesystem["mode"] not in {"isolated", "host"}:
        raise ExecutorError("manifest_invalid", "requested policy is invalid")
    _strict_sha(randomness["seedDigest"], "randomness seed digest")
    if any(not isinstance(limits[key], int) or limits[key] <= 0 for key in ("wallSeconds", "memoryBytes", "pids")) or not isinstance(limits["cpu"], str) or not limits["cpu"] or not isinstance(limits["enforce"], bool):
        raise ExecutorError("manifest_invalid", "resource limits are invalid")
    outputs = _exact(manifest["outputs"], {"root", "symlinks", "specialFiles"}, "outputs")
    _safe_relative(outputs["root"])
    if outputs["symlinks"] != "reject" or outputs["specialFiles"] != "reject":
        raise ExecutorError("manifest_invalid", "only rejecting output policies are supported")
    builder = _exact(manifest["builder"], {"id", "backend", "requiredGrade"}, "builder")
    if not isinstance(builder["id"], str) or not builder["id"] or builder["backend"] not in {"auto", "linux", "windows", "macos"} or builder["requiredGrade"] not in {"hermetic", "contained", "best-effort-tree"}:
        raise ExecutorError("manifest_invalid", "builder declaration is invalid")
    canonical_bytes(manifest)
    return manifest


def _read_project_file(project_root: Path, relative: str, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    relative = _safe_relative(relative)
    parts = PurePosixPath(relative).parts
    cursor = TrustedDirectory(project_root)
    try:
        for part in parts[:-1]:
            next_cursor = cursor.child(part)
            cursor.close()
            cursor = next_cursor
        return cursor.read(parts[-1], maximum)
    finally:
        cursor.close()


def _publish_relative(root: TrustedDirectory, relative: str, content: bytes, mode: int = 0o400) -> None:
    parts = PurePosixPath(_safe_relative(relative)).parts
    cursor = root
    owned: list[TrustedDirectory] = []
    try:
        for part in parts[:-1]:
            cursor = cursor.child(part, create=True)
            owned.append(cursor)
        cursor.publish(parts[-1], content, mode)
    finally:
        for directory in reversed(owned):
            directory.close()


def prepare_execution(manifest_path: Path, project_root: Path, run_dir: Path) -> dict[str, Any]:
    manifest, encoded, identity = load_manifest(manifest_path)
    observed_os = platform.system().lower()
    observed_arch = platform.machine().lower()
    if manifest["platform"]["os"].lower() != observed_os or manifest["platform"]["architecture"].lower() != observed_arch:
        raise ExecutorError("toolchain_mismatch", "manifest platform differs from the executor host")
    declared_image = manifest["toolchain"]["runnerImage"]["digest"]
    observed_image = os.environ.get("AF_RUNNER_IMAGE_DIGEST")
    if observed_image != declared_image:
        raise ExecutorError("image_identity_unpinned", "runner image digest was not independently observed")
    if os.environ.get("AF_RUNNER_SBOM_DIGEST") != manifest["toolchain"]["runnerImage"]["sbomDigest"]:
        raise ExecutorError("image_identity_unpinned", "runner SBOM digest was not independently observed")
    if manifest["source"]["ignoredPolicy"] == "exclude-and-unmount":
        raise ExecutorError("capability_unsatisfied", "this backend cannot unmount undeclared host inputs")
    if manifest["source"]["ignoredPolicy"] != "include-by-digest":
        raise ExecutorError("undeclared_input", "host snapshots require include-by-digest source accounting")
    for item in manifest["source"]["inputs"]:
        content = _read_project_file(project_root, item["path"])
        if digest_bytes(content) != item["sha256"]:
            raise ExecutorError("dirty_source", f"source input differs: {item['path']}")
    for path, digest in manifest["source"]["ignoreFileDigests"].items():
        if digest_bytes(_read_project_file(project_root, path)) != digest:
            raise ExecutorError("undeclared_input", f"ignore policy material differs: {path}")
    if manifest["source"]["submodules"]:
        raise ExecutorError("submodule_mismatch", "submodules require a separately resolved snapshot provider")
    for item in manifest["dependencies"]["lockfiles"]:
        if digest_bytes(_read_project_file(project_root, item["path"])) != item["sha256"]:
            raise ExecutorError("lockfile_missing", f"lockfile differs: {item['path']}")
    for item in [*manifest["toolchain"]["executables"], manifest["toolchain"]["interpreter"]]:
        if digest_bytes(read_regular(Path(item["path"]), MAX_ARTIFACT_BYTES)) != item["sha256"]:
            raise ExecutorError("toolchain_mismatch", f"toolchain differs: {item['path']}")
    with TrustedDirectory(run_dir) as run_cap:
        run_cap.publish("execution.manifest.json", encoded, 0o400)
        workspace = run_cap.child("workspace", create=True)
        try:
            for item in manifest["source"]["inputs"]:
                _publish_relative(workspace, item["path"], _read_project_file(project_root, item["path"]), 0o500 if item["path"] == manifest["command"]["argv"][-1] else 0o400)
        finally:
            workspace.close()
        run_cap.child(manifest["outputs"]["root"], create=True).close()
    Journal(run_dir).create(identity)
    return {"manifestPath": str(run_dir / "execution.manifest.json"), "manifestDigest": identity, "manifest": manifest}


def prepare_manifest(manifest_path: Path, run_dir: Path, project_root: Path | None = None) -> dict[str, Any]:
    return prepare_execution(manifest_path, project_root or Path.cwd(), run_dir)


def _walk_directory(capability: TrustedDirectory, prefix: str = "") -> list[tuple[str, bytes, os.stat_result]]:
    results: list[tuple[str, bytes, os.stat_result]] = []
    for name in sorted(os.listdir(capability.fd)):
        info = os.stat(name, dir_fd=capability.fd, follow_symlinks=False)
        relative = f"{prefix}/{name}" if prefix else name
        if stat.S_ISDIR(info.st_mode):
            child = capability.child(name)
            try:
                results.extend(_walk_directory(child, relative))
            finally:
                child.close()
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            results.append((relative, capability.read(name, MAX_ARTIFACT_BYTES, info), info))
        else:
            raise ExecutorError("artifact_path_invalid", f"unsupported artifact type: {relative}")
    return results


def seal_artifacts(run_dir: Path, artifact_root: Path, *, require_quiescent: bool = True) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=True)
    if require_quiescent:
        Journal(run_dir).require("quiescent")
    relative_root = _safe_relative(artifact_root.relative_to(run_dir).as_posix())
    entries: list[dict[str, Any]] = []
    folded: set[str] = set()
    with TrustedDirectory(run_dir) as run_cap:
        output = run_cap.child(relative_root)
        cas = run_cap.child("cas/sha256", create=True)
        try:
            files = _walk_directory(output)
            if len(files) > MAX_ARTIFACTS:
                raise ExecutorError("artifact_path_invalid", "artifact count limit exceeded")
            for relative, content, info in files:
                relative = _safe_relative(relative)
                if relative.casefold() in folded:
                    raise ExecutorError("artifact_path_invalid", "conflicting artifact subjects")
                folded.add(relative.casefold())
                digest = digest_bytes(content)
                prefix = cas.child(digest[:2], create=True)
                try:
                    try:
                        prefix.publish(digest, content, 0o400, exclusive=True)
                    except ExecutorError as error:
                        if error.code != "artifact_digest_mismatch" or digest_bytes(prefix.read(digest, MAX_ARTIFACT_BYTES)) != digest:
                            raise
                finally:
                    prefix.close()
                entries.append({"path": relative, "type": "file", "size": len(content), "mode": "0755" if info.st_mode & stat.S_IXUSR else "0644", "sha256": digest})
            entries.sort(key=lambda item: item["path"].encode("utf-8"))
            leaves = [hashlib.sha256(b"AF-ARTIFACT-v1\0" + canonical_bytes(entry)).digest() for entry in entries]
            root_digest = digest_bytes(b"AF-ARTIFACT-SET-v1\0" + b"".join(leaves))
            index = {"schemaVersion": SCHEMA_VERSION, "kind": "artifact-index", "rootDigest": root_digest, "artifacts": entries}
            encoded = canonical_bytes(index)
            run_cap.publish("artifact.index.json", encoded, 0o400)
        finally:
            output.close(); cas.close()
    if require_quiescent:
        Journal(run_dir).advance("sealed")
    return {"indexPath": str(run_dir / "artifact.index.json"), "indexDigest": digest_bytes(encoded), "artifactRootDigest": root_digest, "artifacts": entries}


def verify_artifacts(run_dir: Path, index_path: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve(strict=True)
    if index_path.resolve(strict=True) != run_dir / "artifact.index.json":
        raise ExecutorError("provenance_policy_mismatch", "caller index is not the sealed artifact index")
    with TrustedDirectory(run_dir) as run_cap:
        index_name = index_path.relative_to(run_dir).as_posix()
        if "/" in index_name:
            raise ExecutorError("artifact_path_invalid", "artifact index must be directly below run")
        try:
            index = json.loads(run_cap.read(index_name, MAX_MANIFEST_BYTES))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ExecutorError("artifact_digest_mismatch", "artifact index is malformed") from error
        _exact(index, {"schemaVersion", "kind", "rootDigest", "artifacts"}, "artifact index")
        if index["schemaVersion"] != SCHEMA_VERSION or index["kind"] != "artifact-index" or not isinstance(index["artifacts"], list) or not SHA256.fullmatch(str(index["rootDigest"])):
            raise ExecutorError("artifact_digest_mismatch", "artifact index identity is invalid")
        cas = run_cap.child("cas/sha256")
        try:
            leaves = []
            seen: set[str] = set()
            for item in index["artifacts"]:
                entry = _exact(item, {"path", "type", "size", "mode", "sha256"}, "artifact")
                relative = _safe_relative(entry["path"])
                if relative.casefold() in seen or entry["type"] != "file" or entry["mode"] not in {"0644", "0755"} or not isinstance(entry["size"], int) or entry["size"] < 0 or not SHA256.fullmatch(str(entry["sha256"])):
                    raise ExecutorError("artifact_digest_mismatch", "artifact subject is invalid")
                seen.add(relative.casefold())
                prefix = cas.child(entry["sha256"][:2])
                try:
                    content = prefix.read(entry["sha256"], MAX_ARTIFACT_BYTES)
                finally:
                    prefix.close()
                if len(content) != entry["size"] or digest_bytes(content) != entry["sha256"]:
                    raise ExecutorError("artifact_digest_mismatch", f"artifact digest mismatch: {relative}")
                leaves.append(hashlib.sha256(b"AF-ARTIFACT-v1\0" + canonical_bytes(entry)).digest())
            if digest_bytes(b"AF-ARTIFACT-SET-v1\0" + b"".join(leaves)) != index["rootDigest"]:
                raise ExecutorError("artifact_digest_mismatch", "artifact set root mismatch")
            return index
        finally:
            cas.close()


def _strict_capabilities(value: object) -> dict[str, Any]:
    capabilities = _exact(value, CAPABILITY_FIELDS, "capabilities")
    if capabilities["grade"] not in {"best-effort-tree", "contained", "hermetic"} or capabilities["backend"] not in {"linux", "windows", "macos"} or not isinstance(capabilities["resourceLimits"], list) or not isinstance(capabilities["cgroupDelegated"], bool):
        raise ExecutorError("provenance_policy_mismatch", "capability evidence is invalid")
    for field in CAPABILITY_FIELDS - {"resourceLimits", "cgroupDelegated"}:
        if not isinstance(capabilities[field], str):
            raise ExecutorError("provenance_policy_mismatch", "capability evidence field is invalid")
    return capabilities


def _external_private_key(private_key: Path, project_root: Path, run_dir: Path) -> Path:
    original = os.lstat(private_key)
    if stat.S_ISLNK(original.st_mode) or not stat.S_ISREG(original.st_mode):
        raise ExecutorError("signing_identity_unavailable", "private key path is unsafe")
    resolved = private_key.resolve(strict=True)
    for forbidden in (project_root.resolve(strict=True), run_dir.resolve(strict=True)):
        try:
            resolved.relative_to(forbidden)
        except ValueError:
            continue
        raise ExecutorError("signing_identity_unavailable", "private key must be outside repository and managed state")
    return resolved


def attest(*, run_dir: Path, run_id: str, manifest_path: Path, index_path: Path, private_key: Path, public_key: Path, project_root: Path, status: str | None = None, capabilities: Mapping[str, Any] | None = None) -> dict[str, Any]:
    journal = Journal(run_dir).require("sealed")
    if journal["runId"] != run_id or journal["result"] != {"status": "completed", "exitCode": 0}:
        raise ExecutorError("journal_phase_invalid", "only executor-observed successful runs may be attested")
    observed = _strict_capabilities(journal["capabilities"])
    if capabilities is not None and dict(capabilities) != observed:
        raise ExecutorError("provenance_policy_mismatch", "caller capabilities differ from journal")
    private_key = _external_private_key(private_key, project_root, run_dir)
    if observed["controlPlaneIsolation"] == "none":
        raise ExecutorError("capability_unsatisfied", "untrusted run-local observations cannot be attested")
    manifest, _, manifest_digest = _bound_manifest(run_dir, manifest_path)
    terminal_digest = _bound_terminal_digest(run_dir, journal)
    require_capabilities(manifest, observed)
    index = verify_artifacts(run_dir, index_path)
    statement = create_statement(run_id=run_id, manifest_digest=manifest_digest, terminal_digest=terminal_digest, manifest=manifest, index=index, status="completed", capabilities=observed)
    payload = canonical_bytes(statement)
    signature = _openssl(["dgst", "-sha256", "-sign", str(private_key)], data=dsse_pae(PAYLOAD_TYPE, payload))
    bundle = {"payloadType": PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode("ascii"), "signatures": [{"keyid": public_key_id(public_key), "sig": base64.b64encode(signature).decode("ascii")}]}
    with TrustedDirectory(run_dir) as run_cap:
        run_cap.publish("provenance.statement.json", payload, 0o400)
        run_cap.publish("provenance.bundle.json", canonical_bytes(bundle), 0o400)
    Journal(run_dir).advance("attested")
    return {"statementPath": str(run_dir / "provenance.statement.json"), "bundlePath": str(run_dir / "provenance.bundle.json"), "bundleDigest": digest_bytes(canonical_bytes(bundle))}


def load_verifier_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_regular(path))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExecutorError("provenance_policy_mismatch", "verifier policy is malformed") from error
    policy = _exact(value, {"schemaVersion", "expectedBuilderId", "expectedKeyId", "minimumGrade", "allowedBackends"}, "verifier policy")
    if policy["schemaVersion"] != SCHEMA_VERSION or not isinstance(policy["expectedBuilderId"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(policy["expectedKeyId"])) or policy["minimumGrade"] not in {"best-effort-tree", "contained", "hermetic"} or not isinstance(policy["allowedBackends"], list):
        raise ExecutorError("provenance_policy_mismatch", "verifier policy is invalid")
    return policy


def verify_bundle(*, run_dir: Path, bundle_path: Path, public_key: Path, expected_run_id: str, manifest_path: Path, index_path: Path, policy_path: Path) -> dict[str, Any]:
    policy = load_verifier_policy(policy_path)
    if public_key_id(public_key) != policy["expectedKeyId"]:
        raise ExecutorError("signature_invalid", "public key is not authorized by verifier policy")
    verified = _verify_signed_bundle(run_dir=run_dir, bundle_path=bundle_path, public_key=public_key, expected_run_id=expected_run_id, manifest_path=manifest_path, index_path=index_path)
    result = verified["result"]
    statement = verified["statement"]
    predicate = statement["predicate"]
    _exact(predicate["runIdentity"], {"runId"}, "run identity")
    _exact(predicate["manifestDigest"], {"sha256"}, "manifest digest")
    _exact(predicate["terminalObservationDigest"], {"sha256"}, "terminal observation digest")
    result_value = _exact(predicate["result"], {"status"}, "result")
    _exact(predicate["artifactIndexDigest"], {"sha256"}, "artifact index digest")
    capabilities = _strict_capabilities(predicate["observedCapabilities"])
    journal_value = Journal(run_dir).require("attested")
    terminal_digest = _bound_terminal_digest(run_dir, journal_value)
    if predicate["terminalObservationDigest"] != {"sha256": terminal_digest} or capabilities != journal_value["capabilities"] or journal_value["result"] != {"status": "completed", "exitCode": 0}:
        raise ExecutorError("provenance_policy_mismatch", "signed observations differ from executor journal")
    manifest, _, _ = _bound_manifest(run_dir, manifest_path)
    require_capabilities(manifest, capabilities)
    grades = {"best-effort-tree": 0, "contained": 1, "hermetic": 2}
    if manifest["builder"]["id"] != policy["expectedBuilderId"] or capabilities["backend"] not in policy["allowedBackends"] or grades[capabilities["grade"]] < grades[policy["minimumGrade"]] or result_value != {"status": "completed"}:
        raise ExecutorError("provenance_policy_mismatch", "evidence does not satisfy independent verifier policy")
    Journal(run_dir).advance("verified")
    return result


@dataclass
class _SpawnOwnership:
    process: subprocess.Popen[Any] | None = None
    posix_pgid: int | None = None
    job_backend: WindowsJobBackend | None = None
    job_handle: int | None = None
    process_handle: int | None = None
    thread_handle: int | None = None
    windows_assigned: bool = False

    def own_posix(self, process: subprocess.Popen[Any], pgid: int | None) -> None:
        self.process = process
        self.posix_pgid = pgid

    def own_windows(self, process_handle: int, thread_handle: int, assigned: bool) -> None:
        self.process_handle = process_handle
        self.thread_handle = thread_handle
        self.windows_assigned = assigned


def _compatibility_spawn(argv: Sequence[str], cwd: Path, environment: Mapping[str, str], contained: Any, owned: Any = lambda _process, _pgid: None, stdout: Any = None) -> tuple[subprocess.Popen[bytes], int]:
    ready_read, ready_write = os.pipe(); release_read, release_write = os.pipe()
    bootstrap = _python_bootstrap(apply_umask=True)
    process = _spawn_python_bootstrap(bootstrap, ready_write, release_read, argv, cwd=cwd, environment=environment, stdin=subprocess.DEVNULL, stdout=stdout)
    owned(process, None)
    os.close(ready_write); os.close(release_read)
    try:
        if os.read(ready_read, 1) != b"R" or os.getpgid(process.pid) != process.pid:
            raise ExecutorError("containment_start_failed", "startup barrier failed")
        verified_pgid = process.pid
        owned(process, verified_pgid)
        contained()
        os.write(release_write, b"G")
        return process, verified_pgid
    finally:
        os.close(ready_read); os.close(release_write)


def _process_group_exists(pgid: int) -> bool:
    if pgid <= 0:
        raise ExecutorError("process_identity_lost", "process group identity is invalid")
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _quiesce_process_group(process: subprocess.Popen[Any], pgid: int, timeout: float = 5.0) -> None:
    """Signal the startup-verified group and prove that the group is empty."""
    if _process_group_exists(pgid):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, 15)
    deadline = time.monotonic() + min(2.0, timeout)
    while time.monotonic() < deadline and _process_group_exists(pgid):
        process.poll()
        time.sleep(0.05)
    if _process_group_exists(pgid):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, 9)
        deadline = time.monotonic() + max(0.0, timeout - 2.0)
        while time.monotonic() < deadline and _process_group_exists(pgid):
            process.poll()
            time.sleep(0.05)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=0.5)
    if _process_group_exists(pgid):
        raise ExecutorError("output_not_quiescent", "verified process group remained populated")


def _quiesce_unverified_process(process: subprocess.Popen[Any], timeout: float = 5.0) -> None:
    """Bound leader cleanup, then fail closed because group emptiness is unknown."""
    if process.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ExecutorError("output_not_quiescent", "spawned process remained active") from error
    if process.poll() is None:
        raise ExecutorError("output_not_quiescent", "spawned process exit could not be proven")
    raise ExecutorError("process_identity_lost", "POSIX process group identity was not verified; group emptiness cannot be proven")


def _cleanup_spawn_ownership(ownership: _SpawnOwnership) -> None:
    if ownership.job_backend is not None and ownership.job_handle is not None:
        if ownership.process_handle is not None:
            if ownership.windows_assigned:
                ownership.job_backend.terminate_and_wait(ownership.job_handle, ownership.process_handle)
            else:
                ownership.job_backend.terminate_process_and_wait(ownership.process_handle)
        if ownership.job_backend.active_processes(ownership.job_handle) != 0:
            raise ExecutorError("output_not_quiescent", "Job process tree remained active")
    elif ownership.process is not None and ownership.posix_pgid is not None:
        _quiesce_process_group(ownership.process, ownership.posix_pgid)
    elif ownership.process is not None:
        _quiesce_unverified_process(ownership.process)


def _cleanup_record(error: BaseException) -> dict[str, str]:
    return {
        "status": "failed",
        "code": error.code if isinstance(error, ExecutorError) else "cleanup_failed",
        "message": error.message if isinstance(error, ExecutorError) else str(error) or type(error).__name__,
    }


def _record_terminal_result(journal: Journal, run_dir: Path, result: Mapping[str, Any], cleanup_error: BaseException | None) -> dict[str, Any]:
    observed = dict(result)
    if cleanup_error is not None:
        observed["cleanup"] = _cleanup_record(cleanup_error)
    terminal_digest = _terminal_observation(run_dir, observed)
    journal.advance("observed", result=observed, terminal_digest=terminal_digest)
    if cleanup_error is None:
        journal.advance("quiescent")
    return observed


def execute(*, manifest_path: Path, project_root: Path, run_dir: Path, run_id: str, private_key: Path, public_key: Path, verifier_policy: Path) -> dict[str, Any]:
    if run_dir.name != run_id:
        raise ExecutorError("provenance_policy_mismatch", "run ID differs from run directory")
    manifest, _, _ = load_manifest(manifest_path)
    capabilities = _strict_capabilities(capability_report(manifest["builder"]["backend"]))
    require_capabilities(manifest, capabilities)
    prepared = prepare_execution(manifest_path, project_root, run_dir)
    journal = Journal(run_dir)
    workspace = run_dir / "workspace" / ("" if manifest["command"]["cwd"] == "." else manifest["command"]["cwd"])
    argv = list(manifest["command"]["argv"])
    environment = dict(manifest["environment"]["allow"])
    if capabilities["backend"] != "windows":
        environment["AF_EXECUTOR_UMASK"] = manifest["command"]["umask"]
    def contained() -> None:
        journal.advance("contained", capabilities=capabilities)
        # This durable state is written before the release byte/ResumeThread.
        journal.advance("launching")

    ownership = _SpawnOwnership()
    process: subprocess.Popen[Any] | None = None
    linux_target: Path | None = None
    pidfd: int | None = None
    job_backend: WindowsJobBackend | None = None
    job_handle: int | None = None
    process_handle: int | None = None
    thread_handle: int | None = None
    result: dict[str, Any] | None = None
    error: BaseException | None = None
    try:
        if capabilities["backend"] == "linux" and capabilities["processTree"] == "cgroup-v2":
            backend = LinuxCgroupBackend(Path(os.environ["AF_CGROUP_DELEGATE"]))
            linux_target = backend.create(run_id, manifest["policy"]["limits"])
            process, pidfd = backend.spawn(linux_target, argv, cwd=workspace, environment=environment, contained=contained)
        elif capabilities["backend"] == "windows":
            job_backend = WindowsJobBackend()
            job_handle = job_backend.create(manifest["policy"]["limits"] if manifest["policy"]["limits"]["enforce"] else None)
            ownership.job_backend = job_backend
            ownership.job_handle = job_handle
            process_handle, thread_handle, _pid = job_backend.spawn_suspended(job_handle, argv, workspace, environment, contained=contained, owned=ownership.own_windows)
        else:
            process, _posix_pgid = _compatibility_spawn(argv, workspace, environment, contained, owned=ownership.own_posix)
        journal.advance("launched")
        wall = manifest["policy"]["limits"]["wallSeconds"]
        if process is not None:
            try:
                exit_code = process.wait(timeout=wall)
            except subprocess.TimeoutExpired as timeout:
                raise ExecutorError("resource_limit_exceeded", "wall-clock limit exceeded") from timeout
        else:
            assert job_backend is not None and process_handle is not None
            if job_backend.kernel32.WaitForSingleObject(process_handle, wall * 1000) == 0x102:
                raise ExecutorError("resource_limit_exceeded", "wall-clock limit exceeded")
            code = ctypes.c_uint32()
            if not job_backend.kernel32.GetExitCodeProcess(process_handle, ctypes.byref(code)):
                raise ExecutorError("process_identity_lost", "process exit status unavailable")
            exit_code = int(code.value)
        result = {"status": "completed" if exit_code == 0 else "failed", "exitCode": exit_code}
        if exit_code != 0:
            raise ExecutorError("execution_failed", f"payload exited with {exit_code}")
    except BaseException as caught:
        error = caught
        if result is None:
            phase = journal.read()["phase"]
            result = {"status": "ambiguous", "exitCode": None, "releaseState": phase}
    finally:
        cleanup_error: BaseException | None = None
        try:
            if linux_target is not None:
                LinuxCgroupBackend(linux_target.parent).kill(linux_target)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and "populated 0" not in (linux_target / "cgroup.events").read_text(encoding="ascii"):
                    time.sleep(0.05)
                if "populated 0" not in (linux_target / "cgroup.events").read_text(encoding="ascii"):
                    raise ExecutorError("output_not_quiescent", "cgroup process tree remained populated")
            else:
                _cleanup_spawn_ownership(ownership)
        except BaseException as caught:
            cleanup_error = caught
        close_error: BaseException | None = None
        if pidfd is not None:
            try:
                os.close(pidfd)
            except BaseException as caught:
                close_error = caught
        if job_backend is not None:
            for handle in (ownership.thread_handle, ownership.process_handle, ownership.job_handle):
                if handle is not None:
                    try:
                        if not job_backend.kernel32.CloseHandle(handle):
                            raise ExecutorError("process_identity_lost", "Windows containment handle close failed")
                    except BaseException as caught:
                        if close_error is None:
                            close_error = caught
        if cleanup_error is None and close_error is not None:
            cleanup_error = close_error
        if result is not None:
            try:
                result = _record_terminal_result(journal, run_dir, result, cleanup_error)
            except BaseException as journal_error:
                if cleanup_error is None:
                    cleanup_error = journal_error
        if error is None and cleanup_error is not None:
            error = cleanup_error
    if error is not None:
        raise error
    sealed = seal_artifacts(run_dir, run_dir / manifest["outputs"]["root"])
    evidence = attest(run_dir=run_dir, run_id=run_id, manifest_path=Path(prepared["manifestPath"]), index_path=Path(sealed["indexPath"]), private_key=private_key, public_key=public_key, project_root=project_root)
    verified = verify_bundle(run_dir=run_dir, bundle_path=Path(evidence["bundlePath"]), public_key=public_key, expected_run_id=run_id, manifest_path=Path(prepared["manifestPath"]), index_path=Path(sealed["indexPath"]), policy_path=verifier_policy)
    return {**prepared, **sealed, **evidence, "verification": verified, "journalPath": str(journal.path)}
