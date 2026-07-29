#!/usr/bin/env python3
"""Supervise Work Package execution and resume it after process or lease death."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable


EXECUTOR = Path(__file__).resolve().with_name("work_package_exec.py")


class SupervisorError(RuntimeError):
    pass


def supervise(
    *,
    command_factory: Callable[[int], list[str]],
    package_id: str,
    heartbeat_timeout: float,
    emit: Callable[[dict[str, Any]], Any],
    max_restarts: int | None = None,
) -> dict[str, Any]:
    if heartbeat_timeout <= 0:
        raise SupervisorError("heartbeat timeout must be positive")
    restarts = 0
    accepted = False
    while True:
        process = subprocess.Popen(
            command_factory(restarts),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        last_signal = time.monotonic()
        terminal: dict[str, Any] | None = None
        current_ack = False
        timed_out = False
        while True:
            remaining = heartbeat_timeout - (time.monotonic() - last_signal)
            if remaining <= 0:
                timed_out = True
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                break
            selected = selector.select(timeout=remaining)
            if not selected:
                continue
            line = process.stdout.readline()
            if not line:
                process.wait()
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                process.terminate()
                process.wait()
                raise SupervisorError(
                    f"Work Package executor emitted invalid JSON: {error}"
                ) from error
            if not isinstance(event, dict):
                process.terminate()
                process.wait()
                raise SupervisorError("Work Package executor event must be an object")
            if event.get("packageId") != package_id:
                process.terminate()
                process.wait()
                raise SupervisorError("Work Package executor event identity mismatch")
            event_type = event.get("type")
            if event_type == "ack":
                current_ack = True
                accepted = True
            elif not current_ack:
                process.terminate()
                process.wait()
                raise SupervisorError("Work Package executor emitted an event before ACK")
            if event_type in {"ack", "heartbeat", "node", "package", "terminal"}:
                last_signal = time.monotonic()
            emit(event)
            if event_type == "terminal":
                terminal = event
                process.wait()
                break
        selector.close()
        process.stdout.close()
        if terminal is not None:
            if process.stderr is not None:
                process.stderr.close()
            if terminal.get("ok") is not True or terminal.get("state") != "review":
                raise SupervisorError("Work Package terminal event is not successful")
            return terminal
        stderr = ""
        if process.stderr is not None:
            stderr = process.stderr.read().strip()
            process.stderr.close()
        if not accepted:
            raise SupervisorError(
                "Work Package admission ended before ACK"
                + (f": {stderr}" if stderr else "")
            )
        if max_restarts is not None and restarts >= max_restarts:
            raise SupervisorError("Work Package restart budget exhausted")
        restarts += 1
        emit(
            {
                "type": "supervisor-restart",
                "packageId": package_id,
                "restart": restarts,
                "reason": (
                    "heartbeat-timeout"
                    if timed_out
                    else "process-death"
                ),
                "returnCode": process.returncode,
                "stderr": stderr,
            }
        )


def emit_json(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def execute(args: argparse.Namespace) -> dict[str, Any]:
    repository = str(Path(os.path.abspath(args.repository)))
    resume_owner: str | None = None

    def command_factory(_attempt: int) -> list[str]:
        command = [
            sys.executable,
            str(EXECUTOR),
            "--repository",
            repository,
            "--package-id",
            args.package_id,
            "--invocation-id",
            str(uuid.uuid4()),
            "--heartbeat-seconds",
            str(args.heartbeat_seconds),
        ]
        if resume_owner is not None:
            command.extend(["--resume-owner", resume_owner])
        return command

    def forward(event: dict[str, Any]) -> None:
        nonlocal resume_owner
        if event.get("type") == "ack" and isinstance(
            event.get("invocationId"), str
        ):
            resume_owner = event["invocationId"]
        emit_json(event)

    return supervise(
        command_factory=command_factory,
        package_id=args.package_id,
        heartbeat_timeout=args.heartbeat_timeout,
        emit=forward,
        max_restarts=None,
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Supervise an Agent Factory Work Package until review"
    )
    root.add_argument("--repository", required=True)
    root.add_argument("--package-id", required=True)
    root.add_argument("--heartbeat-seconds", type=float, default=10.0)
    root.add_argument("--heartbeat-timeout", type=float, default=30.0)
    return root


def main() -> int:
    try:
        execute(parser().parse_args())
        return 0
    except (SupervisorError, OSError, ValueError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
