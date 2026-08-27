#!/usr/bin/env python3
"""Bounded native containment launch/quiescence smoke used by CI."""

from __future__ import annotations

import os
import argparse
import json
import sys
from pathlib import Path

import trusted_executor as executor


def strict_linux_record(path: Path) -> int:
    delegate = os.environ.get("AF_CGROUP_DELEGATE")
    if not delegate:
        path.write_text(json.dumps({"status": "refused", "code": "capability_unsatisfied", "reason": "AF_CGROUP_DELEGATE was not explicitly delegated"}, sort_keys=True))
        return 0
    backend = executor.LinuxCgroupBackend(Path(delegate))
    target = backend.create("strict-native-smoke", {"pids": 8, "memoryBytes": 268435456, "cpu": "100000 100000"})
    process = None
    pidfd = None
    try:
        process, pidfd = backend.spawn(target, [sys.executable, "-c", "import os; assert os.environ == {'ALLOWED': 'yes'}"], cwd=Path.cwd(), environment={"ALLOWED": "yes"})
        member = (target / "cgroup.procs").read_text(encoding="ascii").splitlines()
        if str(process.pid) not in member or process.wait(timeout=10) != 0:
            raise RuntimeError("strict payload was not observed in the delegated cgroup")
        backend.kill(target)
        if "populated 0" not in (target / "cgroup.events").read_text(encoding="ascii"):
            raise RuntimeError("strict delegated cgroup did not quiesce")
        path.write_text(json.dumps({"status": "completed", "delegate": str(Path(delegate).resolve()), "pidfd": True, "limits": ["cpu", "memory", "pids"], "populated": 0}, sort_keys=True))
        return 0
    finally:
        if pidfd is not None:
            os.close(pidfd)
        if process is not None and process.poll() is None:
            backend.kill(target)
        target.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-linux-record", type=Path)
    arguments = parser.parse_args()
    if arguments.strict_linux_record is not None:
        return strict_linux_record(arguments.strict_linux_record)
    capabilities = executor.capability_report()
    environment = dict(os.environ)
    if capabilities["backend"] == "windows":
        backend = executor.WindowsJobBackend()
        job = backend.create({"cpu": "50000 100000", "memoryBytes": 268435456, "pids": 8})
        process, thread, _pid = backend.spawn_suspended(job, [sys.executable, "-c", "pass"], Path.cwd(), environment)
        if backend.kernel32.WaitForSingleObject(process, 10000) == 0x102 or backend.active_processes(job) != 0:
            backend.terminate_and_wait(job, process)
            raise RuntimeError("Windows Job did not quiesce")
        backend.kernel32.CloseHandle(thread); backend.kernel32.CloseHandle(process); backend.kernel32.CloseHandle(job)
        return 0
    if capabilities["backend"] == "linux" and capabilities["processTree"] == "cgroup-v2":
        backend = executor.LinuxCgroupBackend(Path(os.environ["AF_CGROUP_DELEGATE"]))
        target = backend.create("native-smoke", {"pids": 8, "memoryBytes": 268435456, "cpu": "100000 100000"})
        process, pidfd = backend.spawn(target, [sys.executable, "-c", "pass"], cwd=Path.cwd(), environment=environment)
        if process.wait(timeout=10) != 0:
            raise RuntimeError("Linux contained payload failed")
        os.close(pidfd)
        if "populated 0" not in (target / "cgroup.events").read_text(encoding="ascii"):
            backend.kill(target)
            raise RuntimeError("Linux cgroup did not quiesce")
        target.rmdir()
        return 0
    process, pgid = executor._compatibility_spawn([sys.executable, "-c", "pass"], Path.cwd(), environment, lambda: None)
    if process.wait(timeout=10) != 0 or pgid != process.pid:
        raise RuntimeError("compatibility backend did not preserve exact group identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
