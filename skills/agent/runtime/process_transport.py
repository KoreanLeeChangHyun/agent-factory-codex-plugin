"""Prompt construction, Codex command wiring, stream bounds, and attempt teardown."""

from __future__ import annotations

import contextlib
import json
import os
import queue
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, IO

import execution_policy
import sandbox_diagnostics
from process_containment import (
    process_group_exists,
    terminate_attempt_group,
    terminate_verified_group,
)
from runtime_errors import ContractError
from runtime_storage import reject_symlink, role_path, safe_read_bytes

HUMAN_APPROVAL_POLICIES = ("required", "bypass")
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_EVENTS_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 4 * 1024 * 1024
SKILL_ROOT = Path(__file__).resolve().parents[1]
EXEC_SCRIPT = SKILL_ROOT / "scripts" / "exec.py"
if sys.platform == "linux":
    import paths as runtime_paths

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
    human_approval_policy: str = "required",
) -> str:
    prompt_path = role_path(role)
    try:
        role_prompt = safe_read_bytes(prompt_path, MAX_REQUEST_BYTES).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("role_invalid", "Agent role prompt must be UTF-8 text") from error
    if not role_prompt.strip():
        raise ContractError("role_invalid", "Agent role prompt must not be empty")
    if human_approval_policy not in HUMAN_APPROVAL_POLICIES:
        raise ContractError("human_approval_policy_invalid", "Human approval policy is invalid")
    if human_approval_policy == "bypass" and role != "main":
        raise ContractError("human_approval_policy_invalid", "Human approval bypass is valid only for Main")
    human_approval_obligation = ""
    if human_approval_policy == "bypass":
        human_approval_obligation = """
This Main run has Human approval policy `bypass`. The Human has authorized direct
execution of the current request without a separate proposal or plan-approval turn.
Treat the current request as satisfying the Delegation gate's execute instruction and
proceed through Main -> Work -> Verification immediately. Do not return
`needs-human-decision` merely to approve a plan, scope restatement, delegation, tool
calls or ordinary in-scope actions. Make bounded reasonable assumptions. Request Human
input only when execution truly cannot continue because required credentials or a
Human-owned choice with materially different outcomes is absent. This policy does not
expand the request or permit skipping Work or Verification.
"""
    receipt_obligation = ""
    if receipt_path is not None and receipt_schema_path is not None:
        receipt_obligation = f"""
For a `completed` result, also write the role-specific machine receipt to
`{receipt_path}`. Its exact contract is `{receipt_schema_path}`. The receipt
must bind this run and request exactly and contain no unknown fields. A
completed run with a missing or invalid receipt will fail at the runtime
boundary.
"""
        if role == "work":
            receipt_obligation += """
In a Work receipt, `changedPaths` contains only paths changed inside the project,
relative to the project root. Record run-directory and other runtime-only artifacts
in `result.md`; if the project was untouched, use an empty `changedPaths` array.
"""
    binding_obligation = ""
    if capability_binding_path is not None:
        binding_obligation = f"""
This run has a strict capability binding at `{capability_binding_path}`. Use
only its exact capability, authority, invocation route, target, allowed effects
and scopes, and approval reference. Preserve its binding in the required receipt.
"""
    migration_obligation = ""
    with contextlib.suppress(ValueError):
        runtime_root = runtime_paths.anchor(request_path)
        if (runtime_root / "migration.json").exists():
            root = runtime_paths.project_for(request_path)
            migration_obligation = f"""
Historical evidence paths may have moved. Resolve an exact historical path with
`{EXEC_SCRIPT}` command `map-path --project-root {root} --path OLD_PATH`.
Use its manifest-bound archivePath and digest; do not rewrite historical requests,
results, receipts or their hashes. New output still belongs to this exact run.
"""
    return f"""Act as Agent `{agent_id}` for Agent Factory.

The following validated content is the complete `{role}` system-prompt source:

<agent-factory-role-prompt>
{role_prompt}
</agent-factory-role-prompt>

Read the delegated request from `{request_path}`. Keep its scope and authority unchanged.

Write the detailed result to `{result_path}`. Then return only the compact JSON
required by the supplied output schema. Run ID: `{run_id}`.
{human_approval_obligation}{binding_obligation}{receipt_obligation}{migration_obligation}"""


def build_codex_command(
    session: dict[str, Any], state: dict[str, Any], session_id: str | None
) -> list[str]:
    codex = str(session["codex"])
    common = ["--json", "--output-schema", str(state["responseSchemaPath"])]
    if session.get("backend") == "app-server":
        return [sys.executable, str(SKILL_ROOT / "runtime" / "native_codex.py"), str(state["statePath"])]
    policy = execution_policy.session_policy(session)
    common.extend(execution_policy.arguments(policy, Path(state["statePath"]).parent))
    if session.get("fast") is False:
        common.extend(["-c", 'service_tier="default"'])
    if session.get("reasoningEffort"):
        common.extend(["-c", "model_reasoning_effort=" + json.dumps(session["reasoningEffort"])])
    # Bounded roles must never inherit native goal auto-continuation from config.
    common.extend(["-c", "features.goals=false"])
    model = session.get("model")
    if model:
        common.extend(["--model", str(model)])
    if session_id is None:
        return [
            codex,
            "exec",
            "--cd",
            str(session["projectRoot"]),
            *common,
            "-",
        ]
    return [
        codex,
        "exec",
        "--cd",
        str(session["projectRoot"]),
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
    return sandbox_diagnostics.sandbox_failure(stderr) is not None


def process_exit_failure(return_code: int, stderr_path: Path, started: bool) -> AttemptFailure:
    if stderr_reports_sandbox_unavailable(stderr_path):
        return AttemptFailure("sandbox_unavailable", sandbox_diagnostics.sandbox_failure("fs sandbox helper failed"), started, True)
    return AttemptFailure("codex_failed", f"codex exec exited with {return_code}", started, True)


def missing_result_failure(stderr_path: Path, publication_failed: bool = False) -> AttemptFailure:
    if stderr_reports_sandbox_unavailable(stderr_path):
        return AttemptFailure(
            "sandbox_unavailable",
            sandbox_diagnostics.sandbox_failure("fs sandbox helper failed"),
            True,
        )
    if publication_failed:
        return AttemptFailure(
            "result_file_write_failed",
            "Codex reported a failed write to the managed result file; no result was published. "
            "Inspect the failed file-change event, tool output and host sandbox diagnostics "
            "(exec.py doctor --probe). A failed write alone does not identify the host policy cause.",
            True,
        )
    return AttemptFailure(
        "result_file_missing",
        "Agent did not publish its result file",
        True,
    )


def result_publication_failure(event: dict[str, Any], result_path: str) -> bool | None:
    """Read only structured completion evidence for the exact managed result path."""
    if event.get("type") != "item.completed":
        return None
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "file_change":
        return None
    changes = item.get("changes")
    if not isinstance(changes, list) or not any(
        isinstance(change, dict) and change.get("path") == result_path for change in changes
    ):
        return None
    if item.get("status") == "failed":
        return True
    if item.get("status") == "completed":
        return False
    return None


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
