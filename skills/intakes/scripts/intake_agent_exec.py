#!/usr/bin/env python3
"""Run one delegated Intake Agent session and expose only compact results."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, IO, Iterator, Sequence


SCHEMA_VERSION = "1.0.0"
INTAKE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
CAPABILITIES = ("analysis", "web-search", "user-research")
SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
SKILL_ROOT = Path(__file__).resolve().parents[1]
RESULT_SCHEMA = SKILL_ROOT / "assets" / "intake-agent-result.schema.json"
INTAKE_MANAGER = SKILL_ROOT / "scripts" / "intake.py"


class ContractError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ContractError("invalid_arguments", message)


def load_binding(repository: Path, intake_id: str) -> str | None:
    package = repository / ".agent-factory" / "intakes" / intake_id
    try:
        result = subprocess.run(
            [sys.executable, str(INTAKE_MANAGER), "session-show", str(package)],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
        )
        value = json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("session_binding_invalid", "saved session binding is invalid") from error
    session_id = value.get("sessionId") if isinstance(value, dict) else None
    if result.returncode != 0 or (
        session_id is not None
        and (not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id))
    ):
        raise ContractError("session_binding_invalid", "saved session binding is invalid")
    return session_id


def save_binding(repository: Path, intake_id: str, session_id: str) -> None:
    package = repository / ".agent-factory" / "intakes" / intake_id
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(INTAKE_MANAGER),
                "session-bind",
                str(package),
                session_id,
            ],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise ContractError(
            "session_binding_invalid", "unable to bind the Intake session"
        ) from error
    if result.returncode != 0:
        raise ContractError("session_binding_invalid", "unable to bind the Intake session")


@contextlib.contextmanager
def intake_lock(repository: Path, intake_id: str) -> Iterator[None]:
    identity = hashlib.sha256(
        f"{repository.resolve()}\0{intake_id}".encode()
    ).hexdigest()
    directory = (
        Path(tempfile.gettempdir())
        / f"agent-factory-{os.getuid()}"
        / "intake-agent-locks"
    )
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stream = (directory / f"{identity}.lock").open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ContractError("intake_writer_busy", "another delegated writer owns this Intake") from error
        yield
    finally:
        stream.close()


def build_command(
    *,
    codex: str,
    repository: Path,
    session_id: str | None,
    capability: str,
    sandbox: str = "workspace-write",
) -> list[str]:
    network = "true" if capability == "web-search" else "false"
    common = [
        "--sandbox",
        sandbox,
        "-c",
        f"sandbox_workspace_write.network_access={network}",
        "--json",
        "--output-schema",
        str(RESULT_SCHEMA),
    ]
    if session_id is None:
        return [codex, "exec", "-C", str(repository), *common, "-"]
    return [codex, "exec", "resume", *common, session_id, "-"]


def build_prompt(repository: Path, intake_id: str, capability: str, request: str) -> str:
    routes = {
        "analysis": "internal code, documents, and runtime analysis",
        "web-search": "authoritative external web search",
        "user-research": "authorized user and operator research evidence",
    }
    return f"""You are the Intake Agent for Agent Factory.

Work only on Intake `{intake_id}` in `{repository}` and perform this delegated request:
{request}

Use the `intakes` skill and its `{capability}` capability for {routes[capability]}.
All canonical Intake reads, appends, validation, and blocks must use
`skills/intakes/scripts/intake.py`; never edit canonical JSON directly. You are
the single writer only for the duration of this delegated run.

Return evidence and analysis to the Main Agent. If a Human-owned choice is
required, return exactly one focused question in the structured result and stop.
Do not interview the Human directly. The Main Agent owns topic-boundary and
sufficiency judgment unless the Human explicitly supplies a condition. Do not
create or execute a Work Unit, launch a Goal, perform Human result review,
integrate Git, push, deploy, or restart a runtime.
"""


def emit(stream: IO[str], value: dict[str, Any]) -> None:
    stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    stream.flush()


def start_process(command: list[str], repository: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        command,
        cwd=repository,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="strict",
        shell=False,
    )


def iter_lines_until(stream: IO[str], deadline: float) -> Iterator[str]:
    items: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def read() -> None:
        try:
            for line in stream:
                items.put(("line", line))
        except (OSError, UnicodeError):
            items.put(("error", None))
        finally:
            items.put(("eof", None))

    threading.Thread(target=read, daemon=True).start()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ContractError("codex_exec_timeout", "codex exec timed out")
        try:
            kind, value = items.get(timeout=remaining)
        except queue.Empty as error:
            raise ContractError("codex_exec_timeout", "codex exec timed out") from error
        if kind == "line" and value is not None:
            yield value
        elif kind == "error":
            raise ContractError("codex_exec_read_failed", "unable to read codex exec output")
        else:
            return


def error_document(intake_id: str, code: str, message: str) -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "kind": "result", "status": "failed", "intakeId": intake_id, "error": {"code": code, "message": message}}


def read_terminal_result(events: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for event in events:
        item = event.get("item") if event.get("type") == "item.completed" else None
        if isinstance(item, dict) and item.get("type") in (None, "agent_message") and isinstance(item.get("text"), str):
            candidates.append(item["text"])
    if not candidates:
        raise ContractError("missing_terminal_result", "codex exec returned no structured result")
    try:
        value = json.loads(candidates[-1])
    except json.JSONDecodeError as error:
        raise ContractError("malformed_terminal_result", "codex exec returned an invalid structured result") from error
    required = {"status", "summary", "question", "evidence", "limitations"}
    valid = (
        isinstance(value, dict)
        and set(value) == required
        and value.get("status") in {"completed", "needs-human-decision", "failed"}
        and isinstance(value.get("summary"), str)
        and (value.get("question") is None or isinstance(value.get("question"), str))
        and isinstance(value.get("evidence"), list)
        and all(isinstance(item, str) for item in value.get("evidence", []))
        and isinstance(value.get("limitations"), list)
        and all(isinstance(item, str) for item in value.get("limitations", []))
    )
    if not valid:
        raise ContractError("malformed_terminal_result", "codex exec returned an invalid structured result")
    return value


def run(
    *,
    repository: Path,
    intake_id: str,
    capability: str,
    request: str,
    session_id: str | None,
    codex: str,
    sandbox: str = "workspace-write",
    timeout: float,
    output: IO[str],
) -> int:
    process: subprocess.Popen[str] | None = None
    try:
        repository = repository.resolve()
        if not INTAKE_ID.fullmatch(intake_id):
            raise ContractError("invalid_intake_id", "Intake id is invalid")
        if session_id is not None and not SESSION_ID.fullmatch(session_id):
            raise ContractError("invalid_session_id", "session id is invalid")
        if capability not in CAPABILITIES:
            raise ContractError("invalid_capability", "capability is invalid")
        if sandbox not in SANDBOXES:
            raise ContractError("invalid_sandbox", "sandbox is invalid")
        if timeout <= 0:
            raise ContractError("invalid_timeout", "timeout must be positive")
        if not (repository / ".agent-factory" / "intakes" / intake_id).is_dir():
            raise ContractError("intake_not_found", "canonical Intake package was not found")
        with intake_lock(repository, intake_id):
            bound_session = load_binding(repository, intake_id)
            if session_id is not None and bound_session != session_id:
                raise ContractError("session_mismatch", "selected session is not bound to this Intake")
            command = build_command(
                codex=codex,
                repository=repository,
                session_id=session_id,
                capability=capability,
                sandbox=sandbox,
            )
            try:
                process = start_process(command, repository)
            except OSError as error:
                raise ContractError("codex_exec_start_failed", "unable to start codex exec") from error
            if process.stdin is None or process.stdout is None:
                process.kill()
                raise ContractError("codex_exec_start_failed", "codex exec pipes are unavailable")
            process.stdin.write(build_prompt(repository, intake_id, capability, request))
            process.stdin.close()
            events: list[dict[str, Any]] = []
            active_session: str | None = None
            deadline = time.monotonic() + timeout
            for line in iter_lines_until(process.stdout, deadline):
                if len(line) > 1_048_576:
                    process.kill()
                    raise ContractError("codex_event_too_large", "codex exec emitted an oversized event")
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as error:
                    process.kill()
                    raise ContractError("malformed_codex_event", "codex exec emitted invalid JSON") from error
                if not isinstance(event, dict):
                    process.kill()
                    raise ContractError("malformed_codex_event", "codex exec emitted an invalid event")
                item = event.get("item") if event.get("type") == "item.completed" else None
                if isinstance(item, dict) and item.get("type") in (None, "agent_message"):
                    events.append(event)
                if event.get("type") == "thread.started":
                    observed = event.get("thread_id")
                    if not isinstance(observed, str) or not SESSION_ID.fullmatch(observed):
                        process.kill()
                        raise ContractError("malformed_codex_event", "codex exec emitted an invalid session id")
                    if session_id is not None and observed != session_id:
                        process.kill()
                        raise ContractError("session_mismatch", "resumed session did not match the selected session")
                    if active_session is None:
                        active_session = observed
                        save_binding(repository, intake_id, observed)
                        emit(output, {"schemaVersion": SCHEMA_VERSION, "kind": "ack", "status": "accepted", "intakeId": intake_id, "sessionId": observed, "mode": "resume" if session_id else "new", "capability": capability})
            try:
                returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as error:
                process.kill()
                raise ContractError("codex_exec_timeout", "codex exec timed out") from error
            if returncode != 0:
                raise ContractError("codex_exec_failed", "codex exec failed")
            if active_session is None:
                raise ContractError("missing_session_ack", "codex exec returned no session acknowledgement")
            result = read_terminal_result(events)
            emit(output, {"schemaVersion": SCHEMA_VERSION, "kind": "result", "intakeId": intake_id, "sessionId": active_session, **result})
            return 0 if result["status"] != "failed" else 1
    except ContractError as error:
        if process is not None:
            with contextlib.suppress(OSError):
                process.kill()
        emit(output, error_document(intake_id, error.code, error.message))
        refusal = {
            "invalid_arguments",
            "invalid_intake_id",
            "invalid_session_id",
            "invalid_capability",
            "invalid_sandbox",
            "invalid_timeout",
            "intake_not_found",
            "intake_writer_busy",
            "session_binding_invalid",
            "session_mismatch",
        }
        return 2 if error.code in refusal else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = JsonArgumentParser(prog="intake_agent_exec.py")
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--intake-id", required=True)
    parser.add_argument("--capability", required=True, choices=CAPABILITIES)
    parser.add_argument("--request", required=True)
    parser.add_argument("--session-id")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--sandbox", choices=SANDBOXES, default="workspace-write")
    parser.add_argument("--timeout", type=float, default=1800.0)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        return run(
            repository=args.repository,
            intake_id=args.intake_id,
            capability=args.capability,
            request=args.request,
            session_id=args.session_id,
            codex=args.codex,
            sandbox=args.sandbox,
            timeout=args.timeout,
            output=sys.stdout,
        )
    except ContractError as error:
        emit(sys.stdout, error_document("unknown", error.code, error.message))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
