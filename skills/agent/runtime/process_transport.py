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
from task_modes import route_instruction
import sandbox_diagnostics
from process_containment import (
    process_group_exists,
    terminate_attempt_group,
    terminate_verified_group,
)
from runtime_errors import ContractError
from prompt_delivery import PromptParts
from runtime_storage import reject_symlink, role_path, safe_read_bytes, safe_read_json, atomic_write

HUMAN_APPROVAL_POLICIES = ("required", "bypass")
MAX_REQUEST_BYTES = 8 * 1024 * 1024
# Keep unusually large requests on the existing file-based path.
MAX_INLINE_REQUEST_BYTES = 64 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_EVENTS_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 4 * 1024 * 1024
# Leave room for JSON escaping and the enclosing JSONL event.
MAX_RESULT_TEXT_BYTES = 64 * 1024
SKILL_ROOT = Path(__file__).resolve().parents[1]
EXEC_SCRIPT = SKILL_ROOT / "scripts" / "exec.py"
if sys.platform in {"linux", "darwin"}:
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


def response_schema_document(result_path: str, *, inline: bool = True, decision_metadata: bool = True) -> dict[str, Any]:
    properties = {
        "status": {"type": "string", "enum": ["completed", "needs-human-decision", "failed"]},
        "resultPath": {"type": "string", "const": result_path},
    }
    if inline:
        properties["resultText"] = {"type": "string", "minLength": 1, "maxLength": MAX_RESULT_TEXT_BYTES}
    if inline and decision_metadata:
        properties["decisionKind"] = {"type": ["string", "null"], "enum": ["approval", "clarification", None]}
    # Codex requires every property, including nullable metadata, in required.
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
            "properties": properties, "required": list(properties), "additionalProperties": False}


def inline_result(state: dict[str, Any]) -> bool:
    """Persisted schemas choose the protocol; never reinterpret historical runs."""
    schema = safe_read_json(Path(state["responseSchemaPath"]))
    for inline in (True, False):
        if any(schema == response_schema_document(state["resultPath"], inline=inline, decision_metadata=metadata) for metadata in (True, False)):
            return inline
    # Recognize persisted runs from before nullable decision metadata was required.
    historical = response_schema_document(state["resultPath"])
    historical["required"].remove("decisionKind")
    if schema == historical:
        return True
    raise ContractError("result_schema_invalid", "Managed response schema is unsupported or mismatched")


def validate_terminal_result(terminal: Any, state: dict[str, Any]) -> bytes | None:
    inline = inline_result(state)
    expected = {"status", "resultPath", "resultText"} if inline else {"status", "resultPath"}
    allowed = expected | ({"decisionKind"} if inline else set())
    if (not isinstance(terminal, dict) or not expected <= set(terminal) or not set(terminal) <= allowed
            or not isinstance(terminal.get("status"), str)
            or terminal.get("status") not in {"completed", "needs-human-decision", "failed"}
            or terminal.get("resultPath") != state["resultPath"]):
        raise ContractError("result_invalid", "Codex returned an invalid terminal result")
    decision = terminal.get("decisionKind")
    if decision not in (None, "approval", "clarification") or (decision is not None and terminal["status"] != "needs-human-decision"):
        raise ContractError("result_invalid", "Decision kind is valid only for a Human decision result")
    if not inline:
        return None
    text = terminal["resultText"]
    if not isinstance(text, str) or not text.strip():
        raise ContractError("result_invalid", "Terminal resultText must be nonempty UTF-8 text")
    try:
        content = text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ContractError("result_invalid", "Terminal resultText must be valid UTF-8") from error
    if len(content) > MAX_RESULT_TEXT_BYTES:
        raise ContractError("result_invalid", "Terminal resultText exceeds the byte limit")
    return content


def publish_terminal_result(terminal: Any, state: dict[str, Any]) -> None:
    content = validate_terminal_result(terminal, state)
    if content is not None:
        path = Path(state["resultPath"])
        reject_symlink(path)
        if path.exists() and not stat.S_ISREG(path.lstat().st_mode):
            raise ContractError("result_file_invalid", "Managed result path is not a regular file")
        atomic_write(path, content)


def build_prompt_parts(
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
    inline_response: bool = True,
    task_mode: str = "work-verification",
    request: bytes | None = None,
) -> PromptParts:
    prompt_path = role_path(role)
    try:
        role_prompt = safe_read_bytes(prompt_path, MAX_REQUEST_BYTES).decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("role_invalid", "Agent role prompt must be UTF-8 text") from error
    if not role_prompt.strip():
        raise ContractError("role_invalid", "Agent role prompt must not be empty")
    communication_obligation = ""
    if role == "main":
        communication_path = prompt_path.parents[2] / "convention" / "references" / "communication.md"
        try:
            communication = safe_read_bytes(communication_path, MAX_REQUEST_BYTES).decode("utf-8")
        except UnicodeDecodeError as error:
            raise ContractError("communication_invalid", "Communication contract must be UTF-8 text") from error
        if not communication.strip():
            raise ContractError("communication_invalid", "Communication contract must not be empty")
        communication_obligation = f"""
The current communication contract is already loaded below. Apply it directly;
do not open a Skill or reference file merely to obtain these instructions.
<agent-factory-communication-contract>
{communication}
</agent-factory-communication-contract>
"""
    if human_approval_policy not in HUMAN_APPROVAL_POLICIES:
        raise ContractError("human_approval_policy_invalid", "Human approval policy is invalid")
    human_approval_obligation = ""
    if human_approval_policy == "bypass" and role == "main":
        human_approval_obligation = """
This Main run has Human approval policy `bypass`. Classify conversation versus work
under Main's rules; conversation stays direct, without Work/Verification.
For requested work, the Human has authorized execution without a separate proposal
or plan approval; the Delegation gate is satisfied. Follow the captured task route.
Do not return
`needs-human-decision` merely to approve a plan, scope, delegation, tools or in-scope
actions. Make bounded reasonable assumptions; ask only for blocking credentials or
Human-owned choices with materially different outcomes. Scope and authority stay unchanged.
"""
    elif human_approval_policy == "bypass":
        human_approval_obligation = f"""
This {role} run has Human approval policy `bypass`. Perform the authorized bounded
request without a separate plan or execution approval. Preserve this role's
boundaries, the captured task route, capability bindings and explicit authorization
requirements for destructive or externally visible actions. Request Human input
when required credentials or a Human-owned decision are missing. This policy does
not expand the request or grant Main's orchestration authority.
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
in the detailed response; if the project was untouched, use an empty `changedPaths` array.
Use the neutral `outcome: completed` for new Work receipts, including read-only work.
Read this run's receipt schema before writing the receipt. Copy any `const` values
exactly, including `tests.reason`; do not replace a schema literal with explanatory
prose. Where `tests.run` is a boolean and `tests.reason` is free text, report actual
own checks or why they were not run. Never claim checks that did not occur or use
newer receipt rules to rewrite an older run's captured contract.
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
    result_instruction = (
        f"Return the supplied final JSON schema: `status`, `resultPath` = `{result_path}`, "
        f"and the complete answer once in `resultText` (nonempty UTF-8, maximum {MAX_RESULT_TEXT_BYTES} bytes). "
        "The runtime saves it atomically. Do not write or reread your answer file. Intermediate messages are progress only. "
        "If decisionKind is supported: approval requires a concrete proposal awaiting explicit authorization; "
        "clarification means missing information, choices or credentials; otherwise null. "
        "needs-human-decision alone never implies approval; bypass needs no routine proposal approval."
        if inline_response else
        f"This historical run uses the legacy output contract. Write the detailed result to "
        f"`{result_path}`. Then return only the compact JSON required by the supplied output schema."
    )
    request_instruction = f"Read the delegated request from `{request_path}`. Keep its scope and authority unchanged."
    if role == "main" and request is not None and len(request) <= MAX_INLINE_REQUEST_BYTES:
        request_text = request.decode("utf-8")
        request_instruction = (
            "The complete Human request is included below. Respond to it directly; "
            "do not read the request file merely to obtain its contents. "
            "Keep its scope and authority unchanged. "
            f"The runtime retains an identical record at `{request_path}`.\n\n"
            f"<agent-factory-request>\n{request_text}\n</agent-factory-request>"
        )
    fixed = f"""These are the current Agent Factory fixed instructions. They supersede earlier
Agent Factory role and communication instructions. Apply the latest run's request,
authority, task route and output contracts; prior run contracts are historical.

The following validated content is the complete `{role}` system-prompt source:

<agent-factory-role-prompt>
{role_prompt}
</agent-factory-role-prompt>
{communication_obligation}"""
    dynamic = f"""Act as Agent `{agent_id}` for Agent Factory.
{request_instruction}

{result_instruction} Run ID: `{run_id}`.
{human_approval_obligation}{route_instruction(task_mode, role)}{binding_obligation}{receipt_obligation}{migration_obligation}"""
    development_root = os.environ.get("AGENT_FACTORY_DEV_PLUGIN_ROOT", "").strip()
    if development_root:
        root = Path(development_root).resolve()
        if root != Path(__file__).resolve().parents[3]:
            raise ContractError("development_plugin_invalid", "Development run must use the local plugin runtime")
        bindings = "\n".join(
            f"- agent-factory:{name}: {root / 'skills' / name / 'SKILL.md'}"
            for name in ("agent", "convention", "document")
        )
        fixed += (
            "\n\n<agent-factory-development-sources>\n"
            "This run uses the live local development plugin. For Agent Factory skills, "
            "the following source bindings supersede installed/cache catalog paths and "
            "previously loaded copies. Read these local SKILL.md files when the operation "
            "requires the skill; resolve their scripts and references relative to these files. "
            "Use this same local source for child Work/Verification execution. "
            "Do not install or refresh the marketplace plugin for this development run.\n"
            + bindings + "\n</agent-factory-development-sources>"
        )
    return PromptParts(fixed, dynamic)


def build_prompt(**kwargs: Any) -> str:
    """Keep full-text delivery for legacy callers and CLI exec/resume.

    CLI config overrides would replace the user's existing developer instructions.
    Until those can be safely composed, do not remove instructions from stdin.
    """
    return build_prompt_parts(**kwargs).full


def build_codex_command(
    session: dict[str, Any], state: dict[str, Any], session_id: str | None,
    *, prompt_parts: bool = False,
) -> list[str]:
    codex = str(session["codex"])
    common = []
    for image in state.get("imageInputs", []):
        common.extend(["--image", str(image["path"])])
    common.extend(["--json", "--output-schema", str(state["responseSchemaPath"])])
    if session.get("backend") == "app-server":
        return [sys.executable, str(SKILL_ROOT / "runtime" / "native_codex.py"), str(state["statePath"]),
                *(["--prompt-parts"] if prompt_parts else [])]
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


class EventLogWriter:
    """Reuse one descriptor per attempt while keeping per-event fsync durability."""
    def __init__(self, path):
        self.path, self.descriptor = path, None

    def append(self, line):
        reject_symlink(self.path)
        if self.descriptor is None:
            self.descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(self.descriptor)
        current = self.path.stat()
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise ContractError("runtime_path_unsafe", "runtime event log was replaced")
        content = line.encode()
        if info.st_size > MAX_EVENTS_BYTES or len(content) > MAX_EVENTS_BYTES - info.st_size:
            return False
        view = memoryview(content)
        while view:
            written = os.write(self.descriptor, view)
            if written <= 0:
                raise OSError("short runtime event write")
            view = view[written:]
        os.fsync(self.descriptor)
        return True

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None


def append_event(path: Path, line: str) -> bool:
    return append_bounded(path, line.encode(), MAX_EVENTS_BYTES)


def _queue_output(output, value, stopped=None):
    while stopped is None or not stopped.is_set():
        try:
            output.put(value, timeout=0.1)
            return True
        except queue.Full:
            continue
    return False


def read_process_lines(stream: IO[str], output: queue.Queue[tuple[str, str | None]], stopped=None) -> None:
    try:
        while stopped is None or not stopped.is_set():
            line = stream.readline(MAX_EVENT_BYTES + 1)
            if not line:
                break
            if len(line.encode()) > MAX_EVENT_BYTES:
                _queue_output(output, ("error", None), stopped)
                return
            if not _queue_output(output, ("line", line), stopped):
                return
    except (OSError, UnicodeError):
        _queue_output(output, ("error", None), stopped)
    finally:
        _queue_output(output, ("stdout_eof", None), stopped)


def stream_stderr(
    stream: IO[str], path: Path, output: queue.Queue[tuple[str, str | None]], stopped=None
) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            if not append_bounded(path, chunk.encode(), MAX_STDERR_BYTES):
                _queue_output(output, ("stderr_overflow", None), stopped)
                return
    except (ContractError, OSError, UnicodeError):
        _queue_output(output, ("stderr_error", None), stopped)
    finally:
        _queue_output(output, ("stderr_eof", None), stopped)
