"""macOS kernel process identity, without shell parsing or PID-only fallback."""
from __future__ import annotations

import ctypes
import errno
import re
from functools import lru_cache

from runtime_errors import ContractError


# Public XNU bsd/sys/proc_info.h: proc_bsdinfo and PROC_PIDTBSDINFO.
class ProcBsdInfo(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint32) for name in (
            "flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
            "ruid", "rgid", "svuid", "svgid", "reserved",
        )
    ] + [
        ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32),
    ] + [
        (name, ctypes.c_uint32) for name in (
            "nfiles", "pgid", "pjobc", "tdev", "tpgid",
        )
    ] + [
        ("nice", ctypes.c_int32),
        ("start_seconds", ctypes.c_uint64), ("start_microseconds", ctypes.c_uint64),
    ]


@lru_cache(maxsize=1)
def _libraries():
    try:
        proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        proc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                     ctypes.c_void_p, ctypes.c_int]
        proc.proc_pidinfo.restype = ctypes.c_int
        system.sysctlbyname.argtypes = [ctypes.c_char_p, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_size_t),
                                       ctypes.c_void_p, ctypes.c_size_t]
        system.sysctlbyname.restype = ctypes.c_int
        return proc, system
    except (OSError, AttributeError) as error:
        raise ContractError("process_identity_unavailable", "macOS process identity APIs are unavailable") from error


def boot_id() -> str:
    _, system = _libraries()
    buffer = ctypes.create_string_buffer(37)
    size = ctypes.c_size_t(len(buffer))
    if system.sysctlbyname(b"kern.bootsessionuuid", buffer, ctypes.byref(size), None, 0) != 0:
        raise ContractError("process_identity_unavailable", "macOS boot identity is unavailable")
    if size.value != 37 or not re.fullmatch(
        rb"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", buffer.value
    ):
        raise ContractError("process_identity_unavailable", "macOS boot identity is invalid")
    return "darwin:" + buffer.value.decode("ascii").lower()


def process_identity(pid: int) -> dict:
    if type(pid) is not int or not 0 < pid <= 2**31 - 1:
        raise ContractError("process_identity_invalid", "process PID is invalid")
    proc, _ = _libraries()
    info = ProcBsdInfo()
    ctypes.set_errno(0)
    size = proc.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
    if size <= 0 and ctypes.get_errno() == errno.ESRCH:
        raise ContractError("process_not_found", "managed process no longer exists")
    if (size != ctypes.sizeof(info) or info.pid != pid
            or info.start_seconds == 0 or info.start_microseconds >= 1_000_000):
        raise ContractError("process_identity_unavailable", "macOS process identity is unreadable or invalid")
    # Keep the persisted identity shape; the Darwin boot prefix separates units
    # from Linux ticks. Microseconds preserve the kernel's full start precision.
    return {"pid": pid, "bootId": boot_id(),
            "startTicks": info.start_seconds * 1_000_000 + info.start_microseconds}
