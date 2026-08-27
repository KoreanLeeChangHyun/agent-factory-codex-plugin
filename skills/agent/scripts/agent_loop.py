#!/usr/bin/env python3
"""Orchestrate a finite Work and Review loop through the managed Agent runtime."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

import agent_exec


SCHEMA_VERSION = "0.1.0"
TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled"}
ACTIVE_CHILD = {"accepted", "queued", "starting", "running", "cancelling"}
DEFAULT_MAX_WORK_TURNS = 3
DEFAULT_MAX_REVIEW_TURNS = 3
DEFAULT_MAX_REVISIONS = 2
DEFAULT_MAX_ELAPSED_SECONDS = 7200
DEFAULT_MAX_UNCHANGED_FINDING_ROUNDS = 1
MAX_TEST_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_GIT_STATE_BYTES = 16 * 1024 * 1024
TEST_EVIDENCE_SCHEMA_VERSION = "0.1.0"
TEST_EVIDENCE_KIND = "agent-loop-test-evidence"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise agent_exec.ContractError("loop_state_invalid", "loop timestamp is invalid")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise agent_exec.ContractError("loop_state_invalid", "loop timestamp is invalid") from error


class AgentRuntime:
    """Invoke only the public child lifecycle exposed by agent_exec.py."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.script = Path(agent_exec.__file__).resolve()

    def _call(self, arguments: list[str]) -> dict[str, Any]:
        process = subprocess.run(
            [sys.executable, str(self.script), *arguments, "--project-root", str(self.project_root)],
            cwd=self.project_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        if not lines:
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime returned no response")
        try:
            response = json.loads(lines[-1])
        except json.JSONDecodeError as error:
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime response is invalid") from error
        if not isinstance(response, dict):
            raise agent_exec.ContractError("child_runtime_failure", "Agent runtime response is invalid")
        if response.get("kind") == "error" or process.returncode != 0:
            detail = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise agent_exec.ContractError(
                str(detail.get("code", "child_runtime_failure")),
                str(detail.get("message", "Agent runtime command failed")),
            )
        return response

    def submit(
        self,
        *,
        agent_id: str,
        role: str,
        request_file: Path,
        request_hash: str,
        dispatch_id: str,
        reviewed_work_run_id: str | None = None,
        codex: str = "codex",
        sandbox: str = "workspace-write",
        model: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "submit", "--agent", agent_id, "--role", role,
            "--request-file", str(request_file), "--receipt-request-hash", request_hash,
            "--codex", codex, "--sandbox", sandbox,
            "--dispatch-id", dispatch_id,
        ]
        if reviewed_work_run_id is not None:
            arguments.extend(["--reviewed-work-run-id", reviewed_work_run_id])
        if model is not None:
            arguments.extend(["--model", model])
        return self._call(arguments)

    def send(
        self,
        *,
        agent_id: str,
        request_file: Path,
        request_hash: str,
        dispatch_id: str,
        reviewed_work_run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "send", "--agent", agent_id, "--request-file", str(request_file),
            "--receipt-request-hash", request_hash,
            "--dispatch-id", dispatch_id,
        ]
        if reviewed_work_run_id is not None:
            arguments.extend(["--reviewed-work-run-id", reviewed_work_run_id])
        return self._call(arguments)

    def status(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self._call(["status", "--agent", agent_id, "--run-id", run_id])["run"]

    def status_dispatch(self, agent_id: str, dispatch_id: str) -> dict[str, Any]:
        return self._call(["status", "--agent", agent_id, "--dispatch-id", dispatch_id])["run"]

    def cancel(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self._call(["cancel", "--agent", agent_id, "--run-id", run_id])

    def reconcile(self, agent_id: str) -> dict[str, Any]:
        return self._call(["reconcile", "--agent", agent_id])


def loop_directory(project_root: Path, work_agent_id: str, loop_id: str, create: bool = False) -> Path:
    agent_exec.validate_id(work_agent_id, agent_exec.AGENT_ID, "agent_id")
    agent_exec.validate_id(loop_id, agent_exec.AGENT_ID, "loop_id")
    directory = agent_exec.agent_directory(project_root, work_agent_id, create=create) / "loops" / loop_id
    if create:
        agent_exec.ensure_directory(directory, project_root)
    return directory


def state_path(project_root: Path, work_agent_id: str, loop_id: str) -> Path:
    return loop_directory(project_root, work_agent_id, loop_id) / "state.json"


def emit(value: dict[str, Any]) -> None:
    agent_exec.emit(value)


def validate_budgets(
    max_work_turns: int,
    max_review_turns: int,
    max_revisions: int,
    max_elapsed_seconds: int,
    max_unchanged_finding_rounds: int,
) -> None:
    values = {
        "max work turns": max_work_turns,
        "max review turns": max_review_turns,
        "max revisions": max_revisions,
        "max elapsed seconds": max_elapsed_seconds,
        "max unchanged finding rounds": max_unchanged_finding_rounds,
    }
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values.values()):
        raise agent_exec.ContractError("invalid_budget", "all loop budgets must be finite positive integers")
    if any(value > 1_000_000 for value in values.values()):
        raise agent_exec.ContractError("invalid_budget", "loop budget is unreasonably large")
    if max_revisions > max_work_turns - 1 or max_revisions > max_review_turns - 1:
        raise agent_exec.ContractError(
            "contradictory_budget",
            "revision budget requires one additional Work and Review turn per revision",
        )


def _safe_request(path: Path) -> tuple[Path, bytes, str]:
    resolved = path.resolve(strict=False)
    content = agent_exec.safe_read_bytes(resolved, agent_exec.MAX_REQUEST_BYTES)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise agent_exec.ContractError("request_invalid", "request must be UTF-8 text") from error
    if not text.strip():
        raise agent_exec.ContractError("request_invalid", "request must not be empty")
    return resolved, content, hashlib.sha256(content).hexdigest()


def _read_test_evidence(source: Path) -> tuple[bytes, dict[str, Any]]:
    content = agent_exec.safe_read_bytes(source.resolve(strict=False), agent_exec.MAX_RECEIPT_BYTES)
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence must be valid JSON") from error
    required = {
        "schemaVersion", "kind", "originalRequestHash", "latestWorkRunId",
        "approvingReviewRunId", "workspaceFingerprint", "authorizationReference",
        "command", "actor", "timestamp", "exitStatus", "outputHash",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence fields are invalid")
    if value.get("schemaVersion") != TEST_EVIDENCE_SCHEMA_VERSION or value.get("kind") != TEST_EVIDENCE_KIND:
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence schema identity is invalid")
    if (
        value.get("actor") not in {"human", "verification"}
        or not isinstance(value.get("exitStatus"), int)
        or isinstance(value.get("exitStatus"), bool)
    ):
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence actor or exit status is invalid")
    for field in required - {"exitStatus"}:
        if not isinstance(value.get(field), str) or not value[field]:
            raise agent_exec.ContractError("test_evidence_invalid", f"test evidence {field} is invalid")
    for field in ("originalRequestHash", "workspaceFingerprint", "outputHash"):
        if not re.fullmatch(r"[0-9a-f]{64}", value[field]):
            raise agent_exec.ContractError("test_evidence_invalid", f"test evidence {field} is invalid")
    for field in ("latestWorkRunId", "approvingReviewRunId"):
        agent_exec.validate_id(value[field], agent_exec.AGENT_ID, field)
    parse_timestamp(value["timestamp"])
    return content, value


def _git_output(root: Path, arguments: list[str]) -> bytes:
    try:
        process = subprocess.run(
            ["git", *arguments], cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise agent_exec.ContractError("workspace_fingerprint_unavailable", "Git source state could not be read") from error
    if process.returncode != 0:
        raise agent_exec.ContractError("workspace_fingerprint_unavailable", "project is not a readable Git workspace")
    if len(process.stdout) > MAX_GIT_STATE_BYTES:
        raise agent_exec.ContractError("workspace_fingerprint_oversized", "Git source state exceeds the fingerprint limit")
    return process.stdout


def _fingerprint_add(digest: Any, label: bytes, content: bytes) -> None:
    digest.update(len(label).to_bytes(8, "big"))
    digest.update(label)
    digest.update(len(content).to_bytes(8, "big"))
    digest.update(content)


def workspace_fingerprint(root: Path) -> str:
    top = _git_output(root, ["rev-parse", "--show-toplevel"]).decode("utf-8", "strict").strip()
    try:
        if Path(top).resolve(strict=True) != root:
            raise agent_exec.ContractError(
                "workspace_fingerprint_unavailable", "project root must be the Git workspace root"
            )
    except OSError as error:
        raise agent_exec.ContractError("workspace_fingerprint_unavailable", "Git workspace root is unreadable") from error
    head = _git_output(root, ["rev-parse", "--verify", "HEAD"]).strip()
    pathspec = ["--", ".", ":(exclude).agent-factory", ":(exclude).agent-factory/**"]
    diff_options = ["--binary", "--full-index", "--no-ext-diff", "--no-textconv"]
    staged = _git_output(root, ["diff", *diff_options, "--cached", *pathspec])
    unstaged = _git_output(root, ["diff", *diff_options, *pathspec])
    untracked_output = _git_output(
        root, ["ls-files", "--others", "--exclude-standard", "-z", *pathspec]
    )
    untracked = [item for item in untracked_output.split(b"\0") if item]
    digest = hashlib.sha256()
    total = len(head) + len(staged) + len(unstaged) + len(untracked_output)
    if total > MAX_GIT_STATE_BYTES:
        raise agent_exec.ContractError(
            "workspace_fingerprint_oversized", "Git source state exceeds the fingerprint limit"
        )
    _fingerprint_add(digest, b"HEAD", head)
    _fingerprint_add(digest, b"staged", staged)
    _fingerprint_add(digest, b"unstaged", unstaged)
    for encoded_path in sorted(untracked):
        try:
            relative = encoded_path.decode("utf-8", "surrogateescape")
            source = root / relative
            info = os.lstat(source)
            if stat.S_ISLNK(info.st_mode):
                content = os.fsencode(os.readlink(source))
                file_kind = b"symlink"
            elif stat.S_ISREG(info.st_mode):
                content = agent_exec.safe_read_bytes(source, MAX_GIT_STATE_BYTES)
                file_kind = b"file"
            else:
                raise agent_exec.ContractError(
                    "workspace_fingerprint_unavailable", "untracked Git source state has an unsupported file type"
                )
        except (OSError, UnicodeError) as error:
            raise agent_exec.ContractError("workspace_fingerprint_unavailable", "untracked Git source state is unreadable") from error
        total += len(encoded_path) + len(content)
        if total > MAX_GIT_STATE_BYTES:
            raise agent_exec.ContractError("workspace_fingerprint_oversized", "Git source state exceeds the fingerprint limit")
        _fingerprint_add(digest, b"untracked-path", encoded_path)
        _fingerprint_add(digest, file_kind, content)
    return digest.hexdigest()


def _write_state(path: Path, state: dict[str, Any], *, advance: bool = True) -> None:
    if advance:
        state["version"] = int(state.get("version", 0)) + 1
    state["updatedAt"] = timestamp()
    agent_exec.atomic_write_json(path, state)


def _terminal(state: dict[str, Any], status: str, code: str, message: str) -> None:
    state["status"] = status
    state["phase"] = status
    state["terminalReason"] = {"code": code, "message": message}
    state["finishedAt"] = timestamp()
    state["currentChild"] = None
    state["pendingDispatch"] = None


def _new_loop_id() -> str:
    stamp = utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    return f"loop-{stamp}-{uuid.uuid4().hex[:8]}"


def _new_dispatch_id() -> str:
    return f"dispatch-{uuid.uuid4().hex}"


def start_loop(args: argparse.Namespace, runtime: AgentRuntime | None = None) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    agent_exec.validate_id(args.work_agent, agent_exec.AGENT_ID, "agent_id")
    agent_exec.validate_id(args.review_agent, agent_exec.AGENT_ID, "agent_id")
    if args.work_agent == args.review_agent:
        raise agent_exec.ContractError("agent_identity_conflict", "Work and Review Agent IDs must differ")
    for agent_id in (args.work_agent, args.review_agent):
        if agent_exec.agent_directory(root, agent_id).exists():
            raise agent_exec.ContractError(
                "agent_exists", "loop start requires distinct new Work and Review Agent IDs"
            )
    validate_budgets(
        args.max_work_turns, args.max_review_turns, args.max_revisions,
        args.max_elapsed_seconds, args.max_unchanged_finding_rounds,
    )
    request_path, _request, request_hash = _safe_request(args.request_file)
    if args.test_evidence_policy not in {"required", "not-required"}:
        raise agent_exec.ContractError(
            "test_evidence_policy_invalid",
            "test evidence policy must be explicitly required or not-required",
        )
    if args.test_evidence_file is not None:
        raise agent_exec.ContractError(
            "test_evidence_pre_start_forbidden",
            "test evidence cannot be supplied at loop start; attach it after Review approval",
        )
    loop_id = _new_loop_id()
    directory = loop_directory(root, args.work_agent, loop_id, create=True)
    path = directory / "state.json"
    started = utc_now()
    state: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "agent-loop",
        "loopId": loop_id,
        "version": 1,
        "status": "accepted",
        "phase": "work-pending",
        "projectRoot": str(root),
        "originalRequestPath": str(request_path),
        "originalRequestHash": request_hash,
        "workAgentId": args.work_agent,
        "reviewAgentId": args.review_agent,
        "workSessionId": None,
        "reviewSessionId": None,
        "budgets": {
            "maxWorkTurns": args.max_work_turns,
            "maxReviewTurns": args.max_review_turns,
            "maxRevisions": args.max_revisions,
            "maxElapsedSeconds": args.max_elapsed_seconds,
            "maxUnchangedFindingRounds": args.max_unchanged_finding_rounds,
        },
        "counters": {"workTurns": 0, "reviewTurns": 0, "revisions": 0, "unchangedFindingRounds": 0},
        "startedAt": timestamp(started),
        "deadlineAt": timestamp(started + timedelta(seconds=args.max_elapsed_seconds)),
        "updatedAt": timestamp(started),
        "finishedAt": None,
        "terminalReason": None,
        "childRuns": [],
        "currentChild": None,
        "pendingDispatch": {
            "dispatchId": _new_dispatch_id(),
            "role": "work",
            "agentId": args.work_agent,
            "actor": "main",
            "operation": "submit",
            "requestPath": str(request_path),
            "requestHash": request_hash,
            "receiptRequestHash": request_hash,
            "reviewedWorkRunId": None,
            "ordinal": 1,
            "revision": False,
        },
        "latestWorkRunId": None,
        "latestReviewRunId": None,
        "latestAppliedReviewRunId": None,
        "findingFingerprints": {},
        "findingLedger": {},
        "blockingFindingFingerprint": None,
        "pendingFindingIds": [],
        "resolvedFindingIds": [],
        "testEvidencePolicy": args.test_evidence_policy,
        "reviewSourceBinding": None,
        "acceptanceBinding": None,
        "testEvidence": None,
        "execution": {"codex": args.codex, "sandbox": args.sandbox, "model": args.model},
    }
    _write_state(path, state, advance=False)
    _validate_new_loop_state(root, path, state)
    child_runtime = runtime or AgentRuntime(root)
    try:
        ack = _dispatch_pending(state, child_runtime)
    except agent_exec.ContractError as error:
        if error.code == "child_runtime_failure":
            # The manager may have created the run before its ACK was lost.
            # Keep the durable intent for exact dispatch-ID reconciliation.
            raise
        _terminal(state, "failed", error.code, error.message)
        _write_state(path, state)
        raise
    run_id = str(ack["runId"])
    _record_dispatched_child(state, run_id)
    _write_state(path, state)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "loop-ack",
        "status": "accepted",
        "loopId": loop_id,
        "workAgentId": args.work_agent,
        "workRunId": run_id,
        "statePath": str(path),
    }


def _read_state(root: Path, work_agent: str, loop_id: str) -> tuple[Path, dict[str, Any]]:
    path = state_path(root, work_agent, loop_id)
    state = agent_exec.safe_read_json(path)
    if (
        state.get("kind") != "agent-loop"
        or state.get("loopId") != loop_id
        or state.get("workAgentId") != work_agent
        or state.get("projectRoot") != str(root)
    ):
        raise agent_exec.ContractError("loop_state_invalid", "loop state binding is invalid")
    return path, state


def _validate_new_loop_state(root: Path, path: Path, state: dict[str, Any]) -> None:
    """Fail closed on corrupt dispatch and finding lifecycle state."""
    pending = state.get("pendingDispatch")
    child_runs = state.get("childRuns")
    current = state.get("currentChild")
    legacy_children = (
        isinstance(child_runs, list)
        and all(
            isinstance(child, dict)
            and set(child) == {"role", "agentId", "runId", "ordinal"}
            for child in child_runs
        )
    )
    legacy_current = current is None or (
        isinstance(current, dict) and set(current) == {"role", "agentId", "runId"}
    )
    legacy_pending = pending is None or (
        isinstance(pending, dict)
        and set(pending) == {"role", "agentId", "requestHash", "ordinal", "revision"}
    )
    wholly_legacy = (
        "findingLedger" not in state
        and "resolvedFindingIds" not in state
        and "latestAppliedReviewRunId" not in state
        and legacy_children
        and legacy_current
        and legacy_pending
    )
    if state.get("legacyDispatchCompatibility") is True:
        if not wholly_legacy or pending is not None:
            raise agent_exec.ContractError("loop_state_invalid", "legacy dispatch compatibility state is ambiguous")
        return
    if wholly_legacy and isinstance(pending, dict):
        # Narrow compatibility boundary for pre-dispatch-ID pending recovery.
        if (
            pending.get("role") not in {"work", "review"}
            or pending.get("agentId") != state.get(f"{pending.get('role')}AgentId")
            or not isinstance(pending.get("requestHash"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", pending["requestHash"])
            or not isinstance(pending.get("ordinal"), int)
            or isinstance(pending.get("ordinal"), bool)
            or not isinstance(pending.get("revision"), bool)
            or (
                state.get("phase") != f"{pending.get('role')}-dispatching"
                and not (
                    state.get("status") == "cancelling"
                    and state.get("phase") == "cancelling"
                )
            )
        ):
            raise agent_exec.ContractError("loop_state_invalid", "legacy pending dispatch is ambiguous")
        return
    if wholly_legacy and pending is None and (
        current is not None or state.get("status") in TERMINAL
    ):
        # Pre-P1 active/terminal state without any P1 finding or dispatch fields.
        return
    if isinstance(pending, dict) and "dispatchId" in pending:
        required = {
            "dispatchId", "role", "agentId", "actor", "operation", "requestPath",
            "requestHash", "receiptRequestHash", "reviewedWorkRunId", "ordinal", "revision",
        }
        if set(pending) != required:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch fields are invalid")
        if not isinstance(pending["dispatchId"], str):
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch identifier is invalid")
        agent_exec.validate_id(pending["dispatchId"], agent_exec.DISPATCH_ID, "dispatch_id")
        if pending["role"] not in {"work", "review"} or pending["actor"] != "main":
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch identity is invalid")
        initial_work_pending = (
            pending["role"] == "work"
            and pending["ordinal"] == 1
            and state.get("phase") == "work-pending"
            and state.get("status") == "accepted"
            and state.get("currentChild") is None
            and state.get("childRuns") == []
            and state.get("latestWorkRunId") is None
            and state.get("latestReviewRunId") is None
        )
        if (
            state.get("phase") not in {f"{pending['role']}-dispatching", "cancelling"}
            and not initial_work_pending
        ):
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch phase is invalid")
        expected_agent = state.get(f"{pending['role']}AgentId")
        if pending["agentId"] != expected_agent:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch Agent binding is invalid")
        if not isinstance(pending["ordinal"], int) or isinstance(pending["ordinal"], bool) or pending["ordinal"] <= 0:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch ordinal is invalid")
        expected_operation = "submit" if pending["ordinal"] == 1 else "send"
        if pending["operation"] != expected_operation:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch operation is invalid")
        if not isinstance(pending["revision"], bool):
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch revision marker is invalid")
        for field in ("requestHash", "receiptRequestHash"):
            if not isinstance(pending[field], str) or not re.fullmatch(r"[0-9a-f]{64}", pending[field]):
                raise agent_exec.ContractError("loop_state_invalid", "pending dispatch hash is invalid")
        if pending["receiptRequestHash"] != state.get("originalRequestHash"):
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch receipt binding is invalid")
        reviewed = pending["reviewedWorkRunId"]
        if pending["role"] == "review":
            if reviewed != state.get("latestWorkRunId"):
                raise agent_exec.ContractError("loop_state_invalid", "pending Review Work binding is invalid")
        elif reviewed is not None:
            raise agent_exec.ContractError("loop_state_invalid", "pending Work dispatch has a Review binding")
        if not isinstance(pending["requestPath"], str) or not pending["requestPath"]:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch request path is invalid")
        request_path = Path(pending["requestPath"])
        if pending["role"] == "work" and pending["ordinal"] == 1:
            if request_path != Path(state.get("originalRequestPath", "")):
                raise agent_exec.ContractError("loop_state_invalid", "initial dispatch request path is invalid")
        else:
            try:
                request_path.relative_to(path.parent / "requests")
            except (TypeError, ValueError) as error:
                raise agent_exec.ContractError("loop_state_invalid", "pending dispatch request path is invalid") from error
        content = agent_exec.safe_read_bytes(request_path, agent_exec.MAX_REQUEST_BYTES)
        if hashlib.sha256(content).hexdigest() != pending["requestHash"]:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch request content changed")
        counter = state.get("counters", {}).get(f"{pending['role']}Turns")
        if counter != pending["ordinal"] - 1:
            raise agent_exec.ContractError("loop_state_invalid", "pending dispatch counter is inconsistent")
    elif pending is not None and not isinstance(pending, dict):
        raise agent_exec.ContractError("loop_state_invalid", "pending dispatch is invalid")

    ledger = state.get("findingLedger")
    resolved = state.get("resolvedFindingIds")
    if (
        not isinstance(ledger, dict) or not isinstance(resolved, list)
        or any(not isinstance(item, str) or not item for item in resolved)
        or len(set(resolved)) != len(resolved)
    ):
        raise agent_exec.ContractError("loop_state_invalid", "finding ledger state is invalid")
    pending_ids = state.get("pendingFindingIds")
    if (
        not isinstance(pending_ids, list)
        or any(not isinstance(item, str) or not item for item in pending_ids)
        or len(set(pending_ids)) != len(pending_ids)
    ):
        raise agent_exec.ContractError("loop_state_invalid", "pending finding identifiers are invalid")
    if set(pending_ids) & set(resolved):
        raise agent_exec.ContractError("loop_state_invalid", "pending and resolved finding identifiers overlap")
    expected_fields = {"fingerprint", "firstReviewRunId", "lastReviewRunId", "status"}
    for finding_id, entry in ledger.items():
        if not isinstance(finding_id, str) or not finding_id or not isinstance(entry, dict) or set(entry) != expected_fields:
            raise agent_exec.ContractError("loop_state_invalid", "finding ledger entry is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("fingerprint", ""))):
            raise agent_exec.ContractError("loop_state_invalid", "finding ledger fingerprint is invalid")
        for field in ("firstReviewRunId", "lastReviewRunId"):
            if not isinstance(entry.get(field), str) or not agent_exec.AGENT_ID.fullmatch(entry[field]):
                raise agent_exec.ContractError("loop_state_invalid", "finding ledger Review identity is invalid")
        if entry.get("status") not in {"pending", "resolved"}:
            raise agent_exec.ContractError("loop_state_invalid", "finding ledger status is invalid")
    if set(pending_ids) != {key for key, value in ledger.items() if value["status"] == "pending"}:
        raise agent_exec.ContractError("loop_state_invalid", "pending finding ledger index is inconsistent")
    if set(resolved) != {key for key, value in ledger.items() if value["status"] == "resolved"}:
        raise agent_exec.ContractError("loop_state_invalid", "resolved finding ledger index is inconsistent")
    child_runs = state.get("childRuns")
    if not isinstance(child_runs, list) or any(not isinstance(child, dict) for child in child_runs):
        raise agent_exec.ContractError("loop_state_invalid", "child run ledger is invalid")
    seen_dispatches: set[str] = set()
    seen_runs: set[tuple[str, str]] = set()
    latest_by_role: dict[str, str | None] = {"work": None, "review": None}
    expected_ordinals = {"work": 0, "review": 0}
    prior_work_run: str | None = None
    child_fields = {"role", "agentId", "runId", "ordinal", "dispatchId", "dispatchTuple"}
    tuple_fields = {
        "agentId", "role", "actor", "requestHash", "receiptRequestHash",
        "reviewedWorkRunId", "operation",
    }
    for index, child in enumerate(child_runs):
        if set(child) != child_fields:
            raise agent_exec.ContractError("loop_state_invalid", "child run fields are invalid")
        role = child.get("role")
        expected_role = "work" if index % 2 == 0 else "review"
        if role != expected_role or child.get("agentId") != state.get(f"{role}AgentId"):
            raise agent_exec.ContractError("loop_state_invalid", "child role or Agent binding is invalid")
        expected_ordinals[role] += 1
        if child.get("ordinal") != expected_ordinals[role]:
            raise agent_exec.ContractError("loop_state_invalid", "child ordinal sequence is invalid")
        if not isinstance(child.get("runId"), str) or not agent_exec.AGENT_ID.fullmatch(child["runId"]):
            raise agent_exec.ContractError("loop_state_invalid", "child run identity is invalid")
        if not isinstance(child.get("dispatchId"), str):
            raise agent_exec.ContractError("loop_state_invalid", "child dispatch identity is invalid")
        agent_exec.validate_id(child["dispatchId"], agent_exec.DISPATCH_ID, "dispatch_id")
        if child["dispatchId"] in seen_dispatches:
            raise agent_exec.ContractError("loop_state_invalid", "child dispatch identifier is duplicated")
        seen_dispatches.add(child["dispatchId"])
        run_identity = (child["agentId"], child["runId"])
        if run_identity in seen_runs:
            raise agent_exec.ContractError("loop_state_invalid", "child run identity is duplicated")
        seen_runs.add(run_identity)
        dispatch_tuple = child.get("dispatchTuple")
        if not isinstance(dispatch_tuple, dict) or set(dispatch_tuple) != tuple_fields:
            raise agent_exec.ContractError("loop_state_invalid", "child dispatch provenance is invalid")
        expected_operation = "submit" if child["ordinal"] == 1 else "send"
        expected_reviewed = prior_work_run if role == "review" else None
        if (
            dispatch_tuple.get("agentId") != child["agentId"]
            or dispatch_tuple.get("role") != role
            or dispatch_tuple.get("actor") != "main"
            or dispatch_tuple.get("operation") != expected_operation
            or dispatch_tuple.get("receiptRequestHash") != state.get("originalRequestHash")
            or dispatch_tuple.get("reviewedWorkRunId") != expected_reviewed
            or not isinstance(dispatch_tuple.get("requestHash"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", dispatch_tuple["requestHash"])
        ):
            raise agent_exec.ContractError("loop_state_invalid", "child dispatch tuple binding is invalid")
        try:
            managed = agent_exec.safe_read_json(
                agent_exec.state_file(root, child["agentId"], child["runId"])
            )
        except agent_exec.ContractError as error:
            raise agent_exec.ContractError(
                "loop_state_invalid", "child dispatch has no exact managed-run provenance"
            ) from error
        if (
            managed.get("agentId") != child["agentId"]
            or managed.get("runId") != child["runId"]
            or managed.get("role") != role
            or managed.get("dispatchId") != child["dispatchId"]
            or managed.get("dispatchTuple") != dispatch_tuple
        ):
            raise agent_exec.ContractError("loop_state_invalid", "child dispatch provenance changed")
        latest_by_role[role] = child["runId"]
        if role == "work":
            prior_work_run = child["runId"]
    counters = state.get("counters")
    if not isinstance(counters, dict) or (
        counters.get("workTurns") != expected_ordinals["work"]
        or counters.get("reviewTurns") != expected_ordinals["review"]
        or counters.get("revisions") != max(0, expected_ordinals["work"] - 1)
    ):
        raise agent_exec.ContractError("loop_state_invalid", "child counters are inconsistent")
    if (
        state.get("latestWorkRunId") != latest_by_role["work"]
        or state.get("latestReviewRunId") != latest_by_role["review"]
    ):
        raise agent_exec.ContractError("loop_state_invalid", "latest child run indexes are inconsistent")
    review_order = {
        child["runId"]: child["ordinal"]
        for child in child_runs
        if child["role"] == "review"
    }
    if "latestAppliedReviewRunId" not in state:
        raise agent_exec.ContractError(
            "loop_state_invalid", "new-format loop has no applied Review identity"
        )
    ledger_latest_review = state["latestAppliedReviewRunId"]
    if ledger_latest_review is not None and ledger_latest_review not in review_order:
        raise agent_exec.ContractError(
            "loop_state_invalid", "applied Review identity is not in Review history"
        )
    if ledger and ledger_latest_review is None:
        raise agent_exec.ContractError(
            "loop_state_invalid", "finding ledger has no applied Review identity"
        )
    if (
        current is not None
        and current.get("role") == "review"
        and state.get("phase") in {"review-running", "cancelling"}
        and ledger_latest_review is not None
        and review_order[ledger_latest_review] >= review_order[current["runId"]]
    ):
        raise agent_exec.ContractError(
            "loop_state_invalid", "running Review is already marked as applied"
        )
    terminal_reason = state.get("terminalReason")
    terminal_code = (
        terminal_reason.get("code") if isinstance(terminal_reason, dict) else None
    )
    applied_review_terminal_codes = {
        "approved",
        "approved_with_test_evidence",
        "test_evidence_required",
        "unchanged_blocking_findings",
        "revision_budget_exhausted",
        "cancelled-before-dispatch",
        "dispatch_outcome_unknown",
        "dispatch_binding_ambiguous",
    }
    latest_child_role = child_runs[-1]["role"] if child_runs else None
    work_after_review = bool(review_order) and (
        (isinstance(pending, dict) and pending.get("role") == "work")
        or (isinstance(current, dict) and current.get("role") == "work")
        or (state.get("status") in TERMINAL and latest_child_role == "work")
    )
    requires_latest_applied_review = (
        terminal_code in applied_review_terminal_codes or work_after_review
    )
    if (
        requires_latest_applied_review
        and ledger_latest_review != latest_by_role["review"]
    ):
        raise agent_exec.ContractError(
            "loop_state_invalid", "phase or terminal state has the wrong applied Review"
        )
    if terminal_code in {"test_evidence_required", "approved_with_test_evidence"}:
        acceptance = state.get("acceptanceBinding")
        if (
            not isinstance(acceptance, dict)
            or acceptance.get("approvingReviewRunId") != ledger_latest_review
        ):
            raise agent_exec.ContractError(
                "loop_state_invalid", "test-evidence state has the wrong applied Review"
            )
    for entry in ledger.values():
        first = entry["firstReviewRunId"]
        last = entry["lastReviewRunId"]
        if first not in review_order or last not in review_order:
            raise agent_exec.ContractError(
                "loop_state_invalid", "finding ledger references unknown Review history"
            )
        if review_order[first] > review_order[last]:
            raise agent_exec.ContractError(
                "loop_state_invalid", "finding ledger Review order is reversed"
            )
        if (
            ledger_latest_review is None
            or review_order[last] > review_order[ledger_latest_review]
        ):
            raise agent_exec.ContractError(
                "loop_state_invalid", "finding ledger is newer than its applied Review"
            )
        if entry["status"] == "pending" and last != ledger_latest_review:
            raise agent_exec.ContractError(
                "loop_state_invalid", "pending finding does not reflect the latest Review"
            )
        if entry["status"] == "resolved" and review_order[first] >= review_order[last]:
            raise agent_exec.ContractError(
                "loop_state_invalid", "resolved finding lifecycle order is invalid"
            )
    fingerprints = state.get("findingFingerprints")
    expected_fingerprints = {
        finding_id: entry["fingerprint"] for finding_id, entry in ledger.items()
    }
    if fingerprints != expected_fingerprints:
        raise agent_exec.ContractError(
            "loop_state_invalid", "finding fingerprint index is inconsistent"
        )
    if isinstance(pending, dict) and pending.get("dispatchId") in seen_dispatches:
        raise agent_exec.ContractError("loop_state_invalid", "pending dispatch reuses child history identity")
    current = state.get("currentChild")
    if current is not None:
        if not isinstance(current, dict) or set(current) != {"role", "agentId", "runId", "dispatchId"}:
            raise agent_exec.ContractError("loop_state_invalid", "current child fields are invalid")
        matching = [child for child in child_runs if child.get("dispatchId") == current["dispatchId"]]
        if len(matching) != 1 or any(matching[0].get(key) != current.get(key) for key in ("role", "agentId", "runId")):
            raise agent_exec.ContractError("loop_state_invalid", "current child dispatch identity is inconsistent")
        if not child_runs or matching[0] is not child_runs[-1]:
            raise agent_exec.ContractError("loop_state_invalid", "current child is not the latest dispatch")
        if pending is None and state.get("status") == "active" and state.get("phase") != f"{current['role']}-running":
            raise agent_exec.ContractError("loop_state_invalid", "current child phase is inconsistent")
    elif state.get("status") not in TERMINAL and pending is None:
        raise agent_exec.ContractError("loop_state_invalid", "active loop has no child or pending dispatch")
    if state.get("status") in TERMINAL and (current is not None or pending is not None):
        raise agent_exec.ContractError("loop_state_invalid", "terminal loop retains active dispatch state")


def _request_file(directory: Path, name: str, content: str) -> Path:
    path = directory / "requests" / name
    agent_exec.atomic_write(path, content.encode("utf-8"))
    return path


def _set_pending_dispatch(
    path: Path,
    state: dict[str, Any],
    *,
    role: str,
    agent_id: str,
    request_file: Path,
    ordinal: int,
    revision: bool,
    operation: str,
    receipt_request_hash: str,
    reviewed_work_run_id: str | None = None,
) -> None:
    content = agent_exec.safe_read_bytes(request_file, agent_exec.MAX_REQUEST_BYTES)
    state["phase"] = f"{role}-dispatching"
    state["pendingDispatch"] = {
        "dispatchId": _new_dispatch_id(),
        "role": role,
        "agentId": agent_id,
        "actor": "main",
        "operation": operation,
        "requestPath": str(request_file),
        "requestHash": hashlib.sha256(content).hexdigest(),
        "receiptRequestHash": receipt_request_hash,
        "reviewedWorkRunId": reviewed_work_run_id,
        "ordinal": ordinal,
        "revision": revision,
    }
    _write_state(path, state)


def _record_dispatched_child(
    state: dict[str, Any], run_id: str, *, preserve_cancelling: bool = False
) -> None:
    pending = state.get("pendingDispatch")
    if not isinstance(pending, dict):
        raise agent_exec.ContractError("loop_state_invalid", "pending child dispatch is missing")
    role = pending["role"]
    ordinal = int(pending["ordinal"])
    agent_id = pending["agentId"]
    if role == "work":
        state["counters"]["workTurns"] = ordinal
        if pending.get("revision"):
            state["counters"]["revisions"] += 1
        state["latestWorkRunId"] = run_id
    elif role == "review":
        state["counters"]["reviewTurns"] = ordinal
        state["latestReviewRunId"] = run_id
        if state.get("testEvidencePolicy") == "required":
            binding = state.get("reviewSourceBinding")
            if not isinstance(binding, dict) or binding.get("reviewRunId") is not None:
                raise agent_exec.ContractError(
                    "loop_state_invalid", "pending Review source binding is invalid"
                )
            binding["reviewRunId"] = run_id
    else:
        raise agent_exec.ContractError("loop_state_invalid", "pending child role is invalid")
    if not preserve_cancelling:
        state["status"] = "active"
        state["phase"] = f"{role}-running"
    current = {"role": role, "agentId": agent_id, "runId": run_id}
    if "dispatchId" in pending:
        current["dispatchId"] = pending["dispatchId"]
    state["currentChild"] = current
    child = {"role": role, "agentId": agent_id, "runId": run_id, "ordinal": ordinal}
    if "dispatchId" in pending:
        child.update(
            {
                "dispatchId": pending["dispatchId"],
                "dispatchTuple": {
                    "agentId": pending["agentId"], "role": pending["role"],
                    "actor": pending["actor"], "requestHash": pending["requestHash"],
                    "receiptRequestHash": pending["receiptRequestHash"],
                    "reviewedWorkRunId": pending["reviewedWorkRunId"],
                    "operation": pending["operation"],
                },
            }
        )
    state["childRuns"].append(child)
    state["pendingDispatch"] = None


def _recover_pending_dispatch(
    root: Path,
    path: Path,
    state: dict[str, Any],
    runtime: AgentRuntime,
) -> bool:
    pending = state.get("pendingDispatch")
    if not isinstance(pending, dict):
        return False
    if "dispatchId" in pending:
        cancelling = state.get("status") == "cancelling"
        try:
            matched = runtime.status_dispatch(pending["agentId"], pending["dispatchId"])
        except agent_exec.ContractError as error:
            if error.code != "dispatch_not_found":
                raise
            if cancelling:
                _terminal(state, "cancelled", "cancelled-before-dispatch", "loop was cancelled before the pending child dispatch occurred")
                _write_state(path, state)
                return True
            ack = _dispatch_pending(state, runtime)
            matched = runtime.status(pending["agentId"], str(ack["runId"]))
        expected_tuple = {
            "agentId": pending["agentId"],
            "role": pending["role"],
            "actor": pending["actor"],
            "requestHash": pending["requestHash"],
            "receiptRequestHash": pending["receiptRequestHash"],
            "reviewedWorkRunId": pending["reviewedWorkRunId"],
            "operation": pending["operation"],
        }
        if matched.get("dispatchId") != pending["dispatchId"] or matched.get("dispatchTuple") != expected_tuple:
            raise agent_exec.ContractError("dispatch_binding_invalid", "managed run does not match the exact pending dispatch tuple")
        _record_dispatched_child(state, str(matched["runId"]), preserve_cancelling=cancelling)
        _write_state(path, state)
        if cancelling and matched.get("status") not in TERMINAL:
            runtime.cancel(pending["agentId"], str(matched["runId"]))
        return True
    # Compatibility only: old loop state did not persist dispatch identifiers.
    matches = [
        run
        for run in agent_exec.iter_run_states(root, str(pending["agentId"]))
        if run.get("requestHash") == pending.get("requestHash")
        and run.get("role") == pending.get("role")
    ]
    cancelling = state.get("status") == "cancelling"
    if not matches and cancelling:
        _terminal(
            state,
            "cancelled",
            "cancelled-before-dispatch",
            "loop was cancelled before the pending child dispatch occurred",
        )
        _write_state(path, state)
        return True
    if len(matches) != 1:
        code = "dispatch_outcome_unknown" if not matches else "dispatch_binding_ambiguous"
        _terminal(
            state,
            "failed",
            code,
            "pending child dispatch could not be bound to exactly one managed run",
        )
        _write_state(path, state)
        return True
    matched = matches[0]
    _record_dispatched_child(
        state,
        str(matched["runId"]),
        preserve_cancelling=cancelling,
    )
    state["legacyDispatchCompatibility"] = True
    _write_state(path, state)
    if cancelling:
        if matched.get("status") in TERMINAL:
            _terminal(state, "cancelled", "cancelled", "loop cancellation completed")
            _write_state(path, state)
        else:
            try:
                runtime.cancel(str(pending["agentId"]), str(matched["runId"]))
            except agent_exec.ContractError as error:
                if error.code != "run_terminal":
                    raise
    return True


def _dispatch_pending(state: dict[str, Any], runtime: AgentRuntime) -> dict[str, Any]:
    pending = state.get("pendingDispatch")
    if not isinstance(pending, dict) or "dispatchId" not in pending:
        raise agent_exec.ContractError("loop_state_invalid", "durable pending dispatch is missing")
    common = {
        "agent_id": pending["agentId"],
        "request_file": Path(pending["requestPath"]),
        "request_hash": pending["receiptRequestHash"],
        "reviewed_work_run_id": pending["reviewedWorkRunId"],
        "dispatch_id": pending["dispatchId"],
    }
    if pending["operation"] == "submit":
        execution = state["execution"]
        return runtime.submit(
            **common,
            role=pending["role"],
            codex=execution["codex"], sandbox=execution["sandbox"], model=execution["model"],
        )
    if pending["operation"] == "send":
        return runtime.send(**common)
    raise agent_exec.ContractError("loop_state_invalid", "pending dispatch operation is invalid")


def _review_request(state: dict[str, Any], work_run: dict[str, Any]) -> str:
    binding = state.get("reviewSourceBinding")
    if state.get("testEvidencePolicy") == "required" and not isinstance(binding, dict):
        raise agent_exec.ContractError("loop_state_invalid", "Review source binding is missing")
    fingerprint_line = (
        f"Reviewed Git workspace fingerprint: {binding['workspaceFingerprint']}"
        if isinstance(binding, dict)
        else ""
    )
    return f"""Review the latest completed Work turn within the original Human boundary.

Original request: {state['originalRequestPath']}
Original request SHA-256: {state['originalRequestHash']}
Work run: {work_run['runId']}
Work result: {work_run['resultPath']}
Work receipt: {work_run['receiptPath']}
{fingerprint_line}

Read the original request, Work result and receipt, current changed files, and only directly relevant repository evidence. Preserve stable finding IDs on follow-up. Initial Review must leave resolvedFindingIds empty. On follow-up, explicitly place every prior pending blocking ID either in current blocking findings or resolvedFindingIds; Work addressedFindingIds is not Review resolution. Do not edit files or run tests or verification. Advisory findings never request a revision.
"""


def _revision_request(state: dict[str, Any], review_run: dict[str, Any], receipt: dict[str, Any]) -> str:
    blocking = [finding for finding in receipt["findings"] if finding["severity"] == "blocking"]
    return f"""Revise the current implementation only for the blocking Review findings below.

Original request: {state['originalRequestPath']}
Original request SHA-256: {state['originalRequestHash']}
Latest Work run: {state['latestWorkRunId']}
Review run: {review_run['runId']}
Blocking findings:
{json.dumps(blocking, ensure_ascii=False, indent=2, sort_keys=True)}

Keep the original scope, constraints, exclusions, and authority unchanged. Address only these blocking findings and regressions directly caused by the revision. Do not run tests or verification and do not perform external or destructive actions.
"""


def _finding_hash(finding: dict[str, Any]) -> str:
    normalized = {
        field: " ".join(str(finding[field]).split())
        for field in ("id", "severity", "path", "location", "problem", "correction")
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _blocking_fingerprints(receipt: dict[str, Any]) -> tuple[dict[str, str], str]:
    values = {
        finding["id"]: _finding_hash(finding)
        for finding in receipt["findings"]
        if finding["severity"] == "blocking"
    }
    aggregate = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return values, aggregate


def _apply_review_finding_lifecycle(
    state: dict[str, Any], receipt: dict[str, Any], review_run_id: str
) -> tuple[dict[str, str], str]:
    current, aggregate = _blocking_fingerprints(receipt)
    current_ids = set(current)
    declared_resolved = set(receipt["resolvedFindingIds"])
    prior_pending = set(state["pendingFindingIds"])
    prior_resolved = set(state["resolvedFindingIds"])
    initial = state["counters"]["reviewTurns"] == 1
    if initial:
        if declared_resolved:
            raise agent_exec.ContractError("finding_resolution_invalid", "initial Review must not resolve findings")
        if prior_pending or prior_resolved or state["findingLedger"]:
            raise agent_exec.ContractError("loop_state_invalid", "initial Review finding ledger is not empty")
    else:
        if declared_resolved & prior_resolved:
            raise agent_exec.ContractError("finding_resolution_invalid", "Review resolved an already-resolved finding")
        if not declared_resolved.issubset(prior_pending):
            raise agent_exec.ContractError("finding_resolution_invalid", "Review resolved an unknown finding")
        if not prior_pending.issubset(current_ids | declared_resolved):
            raise agent_exec.ContractError("finding_resolution_invalid", "Review silently dropped a pending finding")
    if current_ids & prior_resolved:
        raise agent_exec.ContractError("finding_resolution_invalid", "a resolved finding reappeared")
    if current_ids & declared_resolved:
        raise agent_exec.ContractError("finding_resolution_invalid", "a finding is both current and resolved")
    ledger = state["findingLedger"]
    for finding_id, fingerprint in current.items():
        entry = ledger.get(finding_id)
        if entry is not None and entry["fingerprint"] != fingerprint:
            raise agent_exec.ContractError("finding_identity_changed", f"finding {finding_id} changed materially")
        if entry is None:
            ledger[finding_id] = {
                "fingerprint": fingerprint,
                "firstReviewRunId": review_run_id,
                "lastReviewRunId": review_run_id,
                "status": "pending",
            }
        else:
            entry.update({"lastReviewRunId": review_run_id, "status": "pending"})
    for finding_id in declared_resolved:
        ledger[finding_id].update({"lastReviewRunId": review_run_id, "status": "resolved"})
    state["pendingFindingIds"] = sorted(current_ids)
    state["resolvedFindingIds"] = sorted(prior_resolved | declared_resolved)
    state["findingFingerprints"] = {
        finding_id: entry["fingerprint"] for finding_id, entry in ledger.items()
    }
    return current, aggregate


def _verify_session_identity(state: dict[str, Any], role: str, child: dict[str, Any]) -> None:
    session_id = child.get("sessionId")
    if not isinstance(session_id, str) or not agent_exec.SESSION_ID.fullmatch(session_id):
        raise agent_exec.ContractError("session_binding_invalid", "child Codex session identity is missing")
    key = "workSessionId" if role == "work" else "reviewSessionId"
    existing = state.get(key)
    if existing is not None and existing != session_id:
        raise agent_exec.ContractError("session_binding_invalid", "child Codex session identity changed")
    state[key] = session_id
    other = state.get("reviewSessionId" if role == "work" else "workSessionId")
    if other == session_id:
        raise agent_exec.ContractError("session_identity_conflict", "Work and Review Codex sessions must differ")


def _advance_work(
    root: Path, path: Path, state: dict[str, Any], run: dict[str, Any], runtime: AgentRuntime
) -> None:
    _verify_session_identity(state, "work", run)
    receipt = agent_exec.validate_receipt(
        root,
        run,
        agent_id=state["workAgentId"],
        run_id=run["runId"],
    )
    if receipt["requestHash"] != state["originalRequestHash"]:
        raise agent_exec.ContractError("request_binding_invalid", "Work receipt changed the original request identity")
    pending = set(state.get("pendingFindingIds", []))
    if pending and not pending.issubset(set(receipt["addressedFindingIds"])):
        raise agent_exec.ContractError("finding_binding_invalid", "revised Work receipt omitted blocking finding identifiers")
    if state["counters"]["reviewTurns"] >= state["budgets"]["maxReviewTurns"]:
        _terminal(state, "needs-human-decision", "review_budget_exhausted", "Review turn budget is exhausted")
        _write_state(path, state)
        return
    directory = path.parent
    ordinal = state["counters"]["reviewTurns"] + 1
    if state["testEvidencePolicy"] == "required":
        state["reviewSourceBinding"] = {
            "originalRequestHash": state["originalRequestHash"],
            "latestWorkRunId": run["runId"],
            "reviewRunId": None,
            "workspaceFingerprint": workspace_fingerprint(root),
        }
    else:
        state["reviewSourceBinding"] = None
    request_file = _request_file(directory, f"review-{ordinal}.md", _review_request(state, run))
    _set_pending_dispatch(
        path,
        state,
        role="review",
        agent_id=state["reviewAgentId"],
        request_file=request_file,
        ordinal=ordinal,
        revision=False,
        operation="submit" if ordinal == 1 else "send",
        receipt_request_hash=state["originalRequestHash"],
        reviewed_work_run_id=run["runId"],
    )
    _validate_new_loop_state(root, path, state)
    ack = _dispatch_pending(state, runtime)
    review_run_id = str(ack["runId"])
    _record_dispatched_child(state, review_run_id)
    _write_state(path, state)


def _advance_review(
    root: Path, path: Path, state: dict[str, Any], run: dict[str, Any], runtime: AgentRuntime
) -> None:
    _verify_session_identity(state, "review", run)
    receipt = agent_exec.validate_receipt(
        root,
        run,
        agent_id=state["reviewAgentId"],
        run_id=run["runId"],
    )
    if (
        receipt["reviewedWorkRunId"] != state["latestWorkRunId"]
        or receipt["reviewedRequestHash"] != state["originalRequestHash"]
    ):
        raise agent_exec.ContractError("review_binding_invalid", "Review receipt is not bound to the latest Work turn")
    source_binding = state.get("reviewSourceBinding")
    if state["testEvidencePolicy"] == "required":
        expected_source_binding = {
            "originalRequestHash": state["originalRequestHash"],
            "latestWorkRunId": state["latestWorkRunId"],
            "reviewRunId": run["runId"],
        }
        if (
            not isinstance(source_binding, dict)
            or any(source_binding.get(field) != value for field, value in expected_source_binding.items())
            or not isinstance(source_binding.get("workspaceFingerprint"), str)
        ):
            raise agent_exec.ContractError(
                "review_source_binding_invalid", "Review is not bound to the dispatched Git source state"
            )
        if workspace_fingerprint(root) != source_binding["workspaceFingerprint"]:
            raise agent_exec.ContractError(
                "reviewed_workspace_changed", "Git source state changed while Review was in progress"
            )
    applied_state = copy.deepcopy(state)
    current_hashes, aggregate = _apply_review_finding_lifecycle(
        applied_state, receipt, str(run["runId"])
    )
    applied_state["latestAppliedReviewRunId"] = str(run["runId"])
    state.clear()
    state.update(applied_state)
    if receipt["decision"] == "approved":
        if current_hashes or state["pendingFindingIds"]:
            raise agent_exec.ContractError("receipt_decision_invalid", "approved Review left blocking findings pending")
        if state["testEvidencePolicy"] == "required":
            state["acceptanceBinding"] = {
                "originalRequestHash": state["originalRequestHash"],
                "latestWorkRunId": state["latestWorkRunId"],
                "approvingReviewRunId": run["runId"],
                "workspaceFingerprint": source_binding["workspaceFingerprint"],
            }
            _terminal(
                state, "needs-human-decision", "test_evidence_required",
                "Review approved; Human or Verification Agent test evidence must now be attached",
            )
        else:
            _terminal(state, "completed", "approved", "Review approved with no blocking findings")
        _write_state(path, state)
        return
    unchanged = state.get("blockingFindingFingerprint") == aggregate
    state["counters"]["unchangedFindingRounds"] = (
        state["counters"]["unchangedFindingRounds"] + 1 if unchanged else 0
    )
    state["blockingFindingFingerprint"] = aggregate
    if unchanged and state["counters"]["unchangedFindingRounds"] >= state["budgets"]["maxUnchangedFindingRounds"]:
        _terminal(state, "needs-human-decision", "unchanged_blocking_findings", "blocking findings remained unchanged")
        _write_state(path, state)
        return
    counters = state["counters"]
    budgets = state["budgets"]
    if counters["revisions"] >= budgets["maxRevisions"] or counters["workTurns"] >= budgets["maxWorkTurns"]:
        _terminal(state, "needs-human-decision", "revision_budget_exhausted", "bounded revision budget is exhausted")
        _write_state(path, state)
        return
    ordinal = counters["workTurns"] + 1
    request_file = _request_file(path.parent, f"work-{ordinal}.md", _revision_request(state, run, receipt))
    _set_pending_dispatch(
        path,
        state,
        role="work",
        agent_id=state["workAgentId"],
        request_file=request_file,
        ordinal=ordinal,
        revision=True,
        operation="send",
        receipt_request_hash=state["originalRequestHash"],
    )
    _validate_new_loop_state(root, path, state)
    ack = _dispatch_pending(state, runtime)
    work_run_id = str(ack["runId"])
    _record_dispatched_child(state, work_run_id)
    _write_state(path, state)


def reconcile_loop(args: argparse.Namespace, runtime: AgentRuntime | None = None) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    loop_id = args.loop_id
    if loop_id is None:
        loops = agent_exec.agent_directory(root, args.work_agent) / "loops"
        agent_exec.reject_symlink(loops)
        candidates: list[tuple[str, dict[str, Any]]] = []
        if loops.is_dir():
            for item in sorted(loops.iterdir(), key=lambda value: value.name):
                if item.is_dir() and not item.is_symlink() and agent_exec.AGENT_ID.fullmatch(item.name):
                    candidate = agent_exec.safe_read_json(item / "state.json")
                    if candidate.get("status") not in TERMINAL:
                        candidates.append((item.name, candidate))
        if not candidates:
            raise agent_exec.ContractError("loop_not_found", "no active loop was found for the Work Agent")
        loop_id = candidates[0][0]
    path, _ = _read_state(root, args.work_agent, loop_id)
    child_runtime = runtime or AgentRuntime(root)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        _validate_new_loop_state(root, path, state)
        if state["status"] in TERMINAL:
            return loop_status_document(state)
        request = agent_exec.safe_read_bytes(Path(state["originalRequestPath"]), agent_exec.MAX_REQUEST_BYTES)
        if hashlib.sha256(request).hexdigest() != state["originalRequestHash"]:
            _terminal(state, "failed", "request_changed", "original loop request content changed")
            _write_state(path, state)
            return loop_status_document(state)
        if utc_now() >= parse_timestamp(state["deadlineAt"]):
            _terminal(state, "needs-human-decision", "elapsed_budget_exhausted", "loop elapsed-time budget is exhausted")
            _write_state(path, state)
            return loop_status_document(state)
        if state.get("pendingDispatch") is not None:
            _recover_pending_dispatch(root, path, state, child_runtime)
            return loop_status_after_transition(
                agent_exec.safe_read_json(path), child_runtime
            )
        current = state.get("currentChild")
        if not isinstance(current, dict):
            _terminal(state, "failed", "loop_state_invalid", "active loop has no current child")
            _write_state(path, state)
            return loop_status_document(state)
        run = child_runtime.status(current["agentId"], current["runId"])
        if state["status"] == "cancelling":
            if run.get("status") not in TERMINAL:
                try:
                    child_runtime.cancel(current["agentId"], current["runId"])
                except agent_exec.ContractError as error:
                    if error.code != "run_terminal":
                        raise
                return loop_status_document(state, run)
            _terminal(state, "cancelled", "cancelled", "loop cancellation completed")
            _write_state(path, state)
            return loop_status_after_transition(
                agent_exec.safe_read_json(path), child_runtime
            )
        if run.get("status") in ACTIVE_CHILD:
            child_runtime.reconcile(current["agentId"])
            return loop_status_document(state, run)
        child_status = run.get("status")
        if child_status != "completed":
            mapped = "needs-human-decision" if child_status == "needs-human-decision" else "failed"
            code = "child_needs_human" if mapped == "needs-human-decision" else "child_terminal_failure"
            _terminal(state, mapped, code, f"{current['role']} child ended as {child_status}")
            _write_state(path, state)
            return loop_status_after_transition(
                agent_exec.safe_read_json(path), child_runtime
            )
        try:
            if current["role"] == "work":
                _advance_work(root, path, state, run, child_runtime)
            elif current["role"] == "review":
                _advance_review(root, path, state, run, child_runtime)
            else:
                raise agent_exec.ContractError("loop_state_invalid", "current child role is invalid")
        except agent_exec.ContractError as error:
            if (
                error.code == "child_runtime_failure"
                and isinstance(state.get("pendingDispatch"), dict)
                and "dispatchId" in state["pendingDispatch"]
            ):
                return loop_status_document(state)
            _terminal(state, "failed", error.code, error.message)
            _write_state(path, state)
        return loop_status_after_transition(agent_exec.safe_read_json(path), child_runtime)


def loop_status_after_transition(
    state: dict[str, Any], runtime: AgentRuntime
) -> dict[str, Any]:
    if state["status"] in TERMINAL:
        return loop_status_document(state)
    current = state.get("currentChild")
    if not isinstance(current, dict):
        return loop_status_document(state)
    try:
        child = runtime.status(current["agentId"], current["runId"])
    except agent_exec.ContractError:
        return loop_status_document(state)
    return loop_status_document(state, child)


def loop_status_document(state: dict[str, Any], child: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "loop-status",
        "loopId": state["loopId"],
        "workAgentId": state["workAgentId"],
        "status": state["status"],
        "phase": state["phase"],
        "version": state["version"],
        "counters": state["counters"],
        "currentChild": child if child is not None else state.get("currentChild"),
        "deadlineAt": state["deadlineAt"],
        "terminalReason": state.get("terminalReason"),
        "acceptanceBinding": state.get("acceptanceBinding"),
        "statePath": str(state_path(Path(state["projectRoot"]), state["workAgentId"], state["loopId"])),
    }


def status_loop(args: argparse.Namespace, runtime: AgentRuntime | None = None) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, state = _read_state(root, args.work_agent, args.loop_id)
    _validate_new_loop_state(root, path, state)
    child = None
    current = state.get("currentChild")
    if isinstance(current, dict) and state["status"] not in TERMINAL:
        child = (runtime or AgentRuntime(root)).status(current["agentId"], current["runId"])
    return loop_status_document(state, child)


def cancel_loop(args: argparse.Namespace, runtime: AgentRuntime | None = None) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = _read_state(root, args.work_agent, args.loop_id)
    child_runtime = runtime or AgentRuntime(root)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        _validate_new_loop_state(root, path, state)
        if state["status"] in TERMINAL:
            return loop_status_document(state)
        if state["status"] == "cancelling":
            return loop_status_document(state)
        current = state.get("currentChild")
        state["status"] = "cancelling"
        state["phase"] = "cancelling"
        state["terminalReason"] = {"code": "cancel_requested", "message": "loop cancellation was requested"}
        _write_state(path, state)
        if isinstance(current, dict):
            try:
                child_runtime.cancel(current["agentId"], current["runId"])
            except agent_exec.ContractError as error:
                if error.code != "run_terminal":
                    raise
        return loop_status_document(state)


def attach_evidence(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = _read_state(root, args.work_agent, args.loop_id)
    evidence_content, evidence = _read_test_evidence(args.evidence_file)
    output_content = agent_exec.safe_read_bytes(
        args.test_output_file.resolve(strict=False), MAX_TEST_OUTPUT_BYTES
    )
    evidence_hash = hashlib.sha256(evidence_content).hexdigest()
    output_hash = hashlib.sha256(output_content).hexdigest()
    if output_hash != evidence["outputHash"]:
        raise agent_exec.ContractError(
            "test_output_hash_mismatch", "test output bytes do not match evidence outputHash"
        )
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        existing = state.get("testEvidence")
        if state.get("status") == "completed" and isinstance(existing, dict):
            if existing.get("evidenceHash") == evidence_hash and existing.get("outputHash") == output_hash:
                return loop_status_document(state)
            raise agent_exec.ContractError(
                "test_evidence_conflict", "completed loop already has different test evidence"
            )
        reason = state.get("terminalReason")
        if (
            state.get("status") != "needs-human-decision"
            or not isinstance(reason, dict)
            or reason.get("code") != "test_evidence_required"
        ):
            raise agent_exec.ContractError(
                "test_evidence_lifecycle_invalid",
                "evidence may be attached only after Review approval requires test evidence",
            )
        binding = state.get("acceptanceBinding")
        if not isinstance(binding, dict):
            raise agent_exec.ContractError("loop_state_invalid", "test acceptance binding is missing")
        evidence_binding = {
            field: evidence[field]
            for field in (
                "originalRequestHash", "latestWorkRunId", "approvingReviewRunId",
                "workspaceFingerprint",
            )
        }
        if evidence_binding != binding:
            raise agent_exec.ContractError(
                "test_evidence_binding_invalid",
                "test evidence does not match the approved Work/Review binding",
            )
        if evidence["exitStatus"] != 0:
            raise agent_exec.ContractError(
                "test_evidence_unsuccessful", "test evidence exitStatus must be zero"
            )
        if workspace_fingerprint(root) != binding["workspaceFingerprint"]:
            raise agent_exec.ContractError(
                "workspace_fingerprint_changed", "Git source state changed after Review approval"
            )
        evidence_path = path.parent / "test-evidence.json"
        output_path = path.parent / "test-output.bin"
        agent_exec.atomic_write(output_path, output_content)
        agent_exec.atomic_write(evidence_path, evidence_content)
        state["testEvidence"] = {
            "schemaVersion": TEST_EVIDENCE_SCHEMA_VERSION,
            "evidencePath": str(evidence_path),
            "evidenceHash": evidence_hash,
            "outputPath": str(output_path),
            "outputHash": output_hash,
            "actor": evidence["actor"],
            "timestamp": evidence["timestamp"],
            "authorizationReference": evidence["authorizationReference"],
            "command": evidence["command"],
            "exitStatus": evidence["exitStatus"],
            **binding,
        }
        _terminal(
            state, "completed", "approved_with_test_evidence",
            "Review approval and bound successful test evidence satisfy acceptance",
        )
        _write_state(path, state)
        return loop_status_document(state)


def build_parser() -> agent_exec.JsonArgumentParser:
    parser = agent_exec.JsonArgumentParser(prog="agent_loop.py")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--project-root", type=Path, default=Path.cwd())
    start.add_argument("--request-file", type=Path, required=True)
    start.add_argument("--work-agent", required=True)
    start.add_argument("--review-agent", required=True)
    start.add_argument("--max-work-turns", type=int, default=DEFAULT_MAX_WORK_TURNS)
    start.add_argument("--max-review-turns", type=int, default=DEFAULT_MAX_REVIEW_TURNS)
    start.add_argument("--max-revisions", type=int, default=DEFAULT_MAX_REVISIONS)
    start.add_argument("--max-elapsed-seconds", type=int, default=DEFAULT_MAX_ELAPSED_SECONDS)
    start.add_argument("--max-unchanged-finding-rounds", type=int, default=DEFAULT_MAX_UNCHANGED_FINDING_ROUNDS)
    start.add_argument("--test-evidence-file", type=Path)
    start.add_argument(
        "--test-evidence-policy",
        choices=("required", "not-required"),
        required=True,
    )
    start.add_argument("--codex", default="codex")
    start.add_argument("--sandbox", choices=agent_exec.SANDBOXES, default="workspace-write")
    start.add_argument("--model")
    for name in ("status", "cancel", "reconcile"):
        command = commands.add_parser(name)
        command.add_argument("--project-root", type=Path, default=Path.cwd())
        command.add_argument("--work-agent", required=True)
        command.add_argument("--loop-id", required=name != "reconcile")
    attach = commands.add_parser("attach-evidence")
    attach.add_argument("--project-root", type=Path, default=Path.cwd())
    attach.add_argument("--work-agent", required=True)
    attach.add_argument("--loop-id", required=True)
    attach.add_argument("--evidence-file", type=Path, required=True)
    attach.add_argument("--test-output-file", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "start":
            emit(start_loop(args))
        elif args.command == "status":
            emit(status_loop(args))
        elif args.command == "cancel":
            emit(cancel_loop(args))
        elif args.command == "reconcile":
            emit(reconcile_loop(args))
        elif args.command == "attach-evidence":
            emit(attach_evidence(args))
        else:
            raise agent_exec.ContractError("invalid_command", "command is invalid")
        return 0
    except agent_exec.ContractError as error:
        emit(agent_exec.error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        emit(agent_exec.error_document("runtime_failure", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
