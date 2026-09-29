"""Windows kernel process identity and Job Object containment, without shell parsing.

Identity is the PID plus the kernel creation FILETIME (absolute, 100 ns units),
which is unique across reboots, so no separate boot identity is needed.
Containment is an anonymous Job Object created by the bootstrap process for
itself with KILL_ON_JOB_CLOSE: only the bootstrap holds the job handle, so its
termination (normal or forced) terminates every descendant still in the job.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from functools import lru_cache

from storage.errors import ContractError

BOOT_ID = "windows"
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x0
WAIT_TIMEOUT = 0x102
ERROR_INVALID_PARAMETER = 87
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
CREATE_NO_WINDOW = 0x08000000
TERMINATED_EXIT_CODE = 0xC000013A  # STATUS_CONTROL_C_EXIT, as for an interrupted console process


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    )]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


@lru_cache(maxsize=1)
def _kernel32():
    if sys.platform != "win32":
        raise ContractError("process_identity_unsupported", "Windows process APIs require Windows")
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except OSError as error:
        raise ContractError("process_identity_unavailable", "Windows process APIs are unavailable") from error
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    return kernel32


def _open(pid: int, access: int):
    if type(pid) is not int or not 0 < pid <= 2**32 - 1:
        raise ContractError("process_identity_invalid", "process PID is invalid")
    kernel32 = _kernel32()
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        if ctypes.get_last_error() == ERROR_INVALID_PARAMETER:
            raise ContractError("process_not_found", "managed process no longer exists")
        raise ContractError("process_identity_unavailable", "Windows process identity is unreadable")
    return handle


def _identity_from_handle(kernel32, handle, pid: int) -> dict:
    if kernel32.WaitForSingleObject(handle, 0) == WAIT_OBJECT_0:
        # A handle held elsewhere keeps an exited process object; it is still dead.
        raise ContractError("process_not_found", "managed process no longer exists")
    creation, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exited),
                                    ctypes.byref(kernel), ctypes.byref(user)):
        raise ContractError("process_identity_unavailable", "Windows process identity is unreadable")
    ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
    if ticks <= 0:
        raise ContractError("process_identity_unavailable", "Windows process identity is invalid")
    return {"pid": pid, "bootId": BOOT_ID, "startTicks": ticks}


def boot_id() -> str:
    _kernel32()
    return BOOT_ID


def process_identity(pid: int) -> dict:
    kernel32 = _kernel32()
    handle = _open(pid, PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)
    try:
        return _identity_from_handle(kernel32, handle, pid)
    finally:
        kernel32.CloseHandle(handle)


def pid_exists(pid: int) -> bool:
    try:
        process_identity(pid)
        return True
    except ContractError as error:
        return error.code != "process_not_found"


def terminate_identity(identity: dict) -> bool:
    """Terminate exactly the recorded process; the handle pins it against PID reuse."""
    kernel32 = _kernel32()
    try:
        handle = _open(int(identity["pid"]), PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)
    except ContractError as error:
        if error.code == "process_not_found":
            return False
        raise
    try:
        try:
            observed = _identity_from_handle(kernel32, handle, int(identity["pid"]))
        except ContractError as error:
            if error.code == "process_not_found":
                return False
            raise
        if observed != identity:
            raise ContractError("process_identity_mismatch", "managed process identity changed; refusing to terminate")
        if not kernel32.TerminateProcess(handle, TERMINATED_EXIT_CODE):
            if kernel32.WaitForSingleObject(handle, 0) == WAIT_OBJECT_0:
                return False
            raise ContractError("containment_stop_failed", "Windows process could not be terminated")
        return True
    finally:
        kernel32.CloseHandle(handle)


def contain_current_process() -> int:
    """Place this process in a private kill-on-close job and return the job handle.

    The handle is not inheritable and must stay open for the process lifetime.
    Breakaway stays allowed so detached background workers can leave on purpose.
    """
    kernel32 = _kernel32()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ContractError("containment_start_failed", "Windows job object could not be created")
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
    if not kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                                            ctypes.byref(limits), ctypes.sizeof(limits)):
        kernel32.CloseHandle(job)
        raise ContractError("containment_start_failed", "Windows job limits could not be set")
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        kernel32.CloseHandle(job)
        raise ContractError("containment_start_failed", "process could not join its Windows job object")
    return int(job)


def creation_flags(*, detach: bool) -> int:
    flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    return flags | CREATE_BREAKAWAY_FROM_JOB if detach else flags
