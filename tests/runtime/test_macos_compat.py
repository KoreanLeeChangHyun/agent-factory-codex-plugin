"""Mocked Darwin contracts plus an opt-in-by-host native lifecycle regression."""
import runtime_test_home

import ctypes
import errno
import importlib.util
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'skills/agent/scripts/exec.py'
spec = importlib.util.spec_from_file_location('macos_exec_test', SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)
import macos_process_identity as macos

BOOT = '12345678-1234-1234-1234-123456789abc'


def libraries(*, pid=42, seconds=123, micros=456, size=None, error=0, boot=BOOT):
    proc, system = mock.Mock(), mock.Mock()
    def pidinfo(requested_pid, flavor, argument, buffer, capacity):
        assert (requested_pid, flavor, argument, capacity) == (42, 3, 0, 136)
        # Encode the public C layout independently of the ctypes declaration.
        data = struct.pack('=12I16s32s5Ii2Q', 0, 0, 0, pid, *([0] * 8),
                           b'', b'', *([0] * 6), seconds, micros)
        ctypes.memmove(buffer, data, len(data))
        ctypes.set_errno(error)
        return len(data) if size is None else size
    def sysctl(name, buffer, length, new_value, new_length):
        assert (name, new_value, new_length) == (b'kern.bootsessionuuid', None, 0)
        data = boot.encode() + b'\0'
        ctypes.memmove(buffer, data, len(data))
        ctypes.cast(length, ctypes.POINTER(ctypes.c_size_t))[0] = len(data)
        return 0
    proc.proc_pidinfo.side_effect = pidinfo
    system.sysctlbyname.side_effect = sysctl
    return proc, system


def test_darwin_kernel_identity_keeps_microsecond_precision():
    with mock.patch.object(macos, '_libraries', return_value=libraries()):
        assert macos.process_identity(42) == {'pid': 42, 'bootId': 'darwin:' + BOOT, 'startTicks': 123000456}


def test_missing_native_library_and_denied_boot_identity_fail_closed():
    macos._libraries.cache_clear()
    try:
        with mock.patch.object(ctypes, 'CDLL', side_effect=OSError('unavailable')):
            with pytest.raises(runtime.ContractError) as error:
                macos.process_identity(42)
        assert error.value.code == 'process_identity_unavailable'
    finally:
        macos._libraries.cache_clear()
    proc, system = libraries()
    system.sysctlbyname.side_effect = None
    system.sysctlbyname.return_value = -1
    with mock.patch.object(macos, '_libraries', return_value=(proc, system)):
        with pytest.raises(runtime.ContractError) as error:
            macos.boot_id()
    assert error.value.code == 'process_identity_unavailable'


@pytest.mark.parametrize('options,code', [
    ({'size': 0, 'error': errno.ESRCH}, 'process_not_found'),
    ({'size': 0, 'error': errno.EPERM}, 'process_identity_unavailable'),
    ({'size': 0}, 'process_identity_unavailable'),
    ({'size': 135}, 'process_identity_unavailable'),
    ({'pid': 43}, 'process_identity_unavailable'),
    ({'micros': 1000000}, 'process_identity_unavailable'),
    ({'boot': 'bad'}, 'process_identity_unavailable'),
])
def test_unreadable_identity_is_never_treated_as_a_dead_process(options, code):
    with mock.patch.object(macos, '_libraries', return_value=libraries(**options)):
        with pytest.raises(runtime.ContractError) as error:
            macos.process_identity(42)
    assert error.value.code == code


@pytest.mark.parametrize('change', ['start', 'boot', 'unavailable'])
def test_darwin_reused_or_unverifiable_identity_refuses_signals(change):
    identity = {'pid': 42, 'bootId': 'darwin:' + BOOT, 'startTicks': 123000455}
    options = {'size': 0, 'error': errno.EPERM} if change == 'unavailable' else {}
    if change == 'boot':
        identity['bootId'] = 'darwin:old-boot'
    with mock.patch.object(sys, 'platform', 'darwin'), mock.patch.object(macos, '_libraries', return_value=libraries(**options)), mock.patch.object(os, 'killpg') as kill:
        with pytest.raises(runtime.ContractError, match='refusing to signal'):
            runtime.terminate_verified_group(identity)
    kill.assert_not_called()


def test_darwin_doctor_does_not_probe_linux_or_claim_sandbox_readiness():
    with mock.patch.object(sys, 'platform', 'darwin'), mock.patch.object(macos, 'process_identity', return_value={}), mock.patch.object(runtime.sandbox_diagnostics.shutil, 'which', return_value='/opt/homebrew/bin/codex'), mock.patch.object(subprocess, 'run') as run:
        result = runtime.sandbox_diagnostics.diagnose(probe=True)
        assert runtime.systemd_manager_usable() is False
    assert result['issue'] is None
    assert result['macosProcessIdentityAvailable'] is True
    assert result['weakerDescendantContainment'] is True
    assert result['probe']['status'] == 'not-applicable'
    assert result['sandboxReadiness'] == 'unknown'
    run.assert_not_called()


def test_darwin_doctor_reports_identity_failure():
    with mock.patch.object(sys, 'platform', 'darwin'), mock.patch.object(macos, 'process_identity', side_effect=runtime.ContractError('process_identity_unavailable', 'denied')):
        result = runtime.sandbox_diagnostics.diagnose()
    assert result['macosProcessIdentityAvailable'] is False
    assert result['issue']['code'] == 'process_identity_unavailable'


@pytest.mark.skipif(sys.platform != 'darwin', reason='Requires the real macOS kernel APIs')
def test_native_macos_barrier_release_and_group_cancellation(tmp_path):
    marker = tmp_path / 'started'
    process, identity, release = runtime.spawn_contained_process(
        [sys.executable, '-c', 'import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text("ready"); time.sleep(60)', str(marker)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        assert not marker.exists()
        assert runtime.process_identity_status(identity) == 'match'
        runtime.release_contained_process(process, identity, release)
        release = None
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.read_text() == 'ready'
        runtime.terminate_attempt_group(process, identity)
        assert process.wait(timeout=5) < 0
        assert runtime.process_identity_status(identity) == 'dead'
        assert not runtime.process_group_exists(process.pid)
    finally:
        runtime.abort_contained_process(process, identity, release)
