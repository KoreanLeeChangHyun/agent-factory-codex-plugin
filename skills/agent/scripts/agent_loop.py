#!/usr/bin/env python3
"""Orchestrate a finite Work and Review loop through the managed Agent runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
        reviewed_work_run_id: str | None = None,
        codex: str = "codex",
        sandbox: str = "workspace-write",
        model: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "submit", "--agent", agent_id, "--role", role,
            "--request-file", str(request_file), "--receipt-request-hash", request_hash,
            "--codex", codex, "--sandbox", sandbox,
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
        reviewed_work_run_id: str | None = None,
    ) -> dict[str, Any]:
        arguments = [
            "send", "--agent", agent_id, "--request-file", str(request_file),
            "--receipt-request-hash", request_hash,
        ]
        if reviewed_work_run_id is not None:
            arguments.extend(["--reviewed-work-run-id", reviewed_work_run_id])
        return self._call(arguments)

    def status(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self._call(["status", "--agent", agent_id, "--run-id", run_id])["run"]

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


def _copy_test_evidence(source: Path, destination: Path) -> dict[str, Any]:
    content = agent_exec.safe_read_bytes(source.resolve(strict=False), agent_exec.MAX_RECEIPT_BYTES)
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence must be valid JSON") from error
    required = {"authorizationReference", "command", "actor", "timestamp", "exitStatus", "outputHash"}
    if not isinstance(value, dict) or set(value) != required:
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence fields are invalid")
    if value.get("actor") not in {"human", "main"} or not isinstance(value.get("exitStatus"), int):
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence actor or exit status is invalid")
    for field in required - {"exitStatus"}:
        if not isinstance(value.get(field), str) or not value[field]:
            raise agent_exec.ContractError("test_evidence_invalid", f"test evidence {field} is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", value["outputHash"]):
        raise agent_exec.ContractError("test_evidence_invalid", "test evidence output hash is invalid")
    parse_timestamp(value["timestamp"])
    agent_exec.atomic_write(destination, content)
    return {"path": str(destination), "hash": hashlib.sha256(content).hexdigest(), "exitStatus": value["exitStatus"]}


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
    if args.test_evidence_policy == "not-required" and args.test_evidence_file is not None:
        raise agent_exec.ContractError(
            "test_evidence_policy_conflict",
            "test evidence cannot be supplied when its policy is not-required",
        )
    loop_id = _new_loop_id()
    directory = loop_directory(root, args.work_agent, loop_id, create=True)
    path = directory / "state.json"
    started = utc_now()
    evidence = None
    if args.test_evidence_file is not None:
        evidence = _copy_test_evidence(args.test_evidence_file, directory / "test-evidence.json")
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
            "role": "work",
            "agentId": args.work_agent,
            "requestHash": request_hash,
            "ordinal": 1,
            "revision": False,
        },
        "latestWorkRunId": None,
        "latestReviewRunId": None,
        "findingFingerprints": {},
        "blockingFindingFingerprint": None,
        "pendingFindingIds": [],
        "testEvidencePolicy": args.test_evidence_policy,
        "testEvidence": evidence,
        "execution": {"codex": args.codex, "sandbox": args.sandbox, "model": args.model},
    }
    _write_state(path, state, advance=False)
    child_runtime = runtime or AgentRuntime(root)
    try:
        ack = child_runtime.submit(
            agent_id=args.work_agent,
            role="work",
            request_file=request_path,
            request_hash=request_hash,
            codex=args.codex,
            sandbox=args.sandbox,
            model=args.model,
        )
    except agent_exec.ContractError as error:
        _terminal(state, "failed", error.code, error.message)
        _write_state(path, state)
        raise
    run_id = str(ack["runId"])
    state["status"] = "active"
    state["phase"] = "work-running"
    state["counters"]["workTurns"] = 1
    state["latestWorkRunId"] = run_id
    state["currentChild"] = {"role": "work", "agentId": args.work_agent, "runId": run_id}
    state["pendingDispatch"] = None
    state["childRuns"].append({"role": "work", "agentId": args.work_agent, "runId": run_id, "ordinal": 1})
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
) -> None:
    content = agent_exec.safe_read_bytes(request_file, agent_exec.MAX_REQUEST_BYTES)
    state["phase"] = f"{role}-dispatching"
    state["pendingDispatch"] = {
        "role": role,
        "agentId": agent_id,
        "requestHash": hashlib.sha256(content).hexdigest(),
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
    else:
        raise agent_exec.ContractError("loop_state_invalid", "pending child role is invalid")
    if not preserve_cancelling:
        state["status"] = "active"
        state["phase"] = f"{role}-running"
    state["currentChild"] = {"role": role, "agentId": agent_id, "runId": run_id}
    state["childRuns"].append(
        {"role": role, "agentId": agent_id, "runId": run_id, "ordinal": ordinal}
    )
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


def _review_request(state: dict[str, Any], work_run: dict[str, Any]) -> str:
    return f"""Review the latest completed Work turn within the original Human boundary.

Original request: {state['originalRequestPath']}
Original request SHA-256: {state['originalRequestHash']}
Work run: {work_run['runId']}
Work result: {work_run['resultPath']}
Work receipt: {work_run['receiptPath']}

Read the original request, Work result and receipt, current changed files, and only directly relevant repository evidence. Preserve stable finding IDs on follow-up. Do not edit files or run tests or verification. Advisory findings never request a revision.
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
    request_file = _request_file(directory, f"review-{ordinal}.md", _review_request(state, run))
    _set_pending_dispatch(
        path,
        state,
        role="review",
        agent_id=state["reviewAgentId"],
        request_file=request_file,
        ordinal=ordinal,
        revision=False,
    )
    if ordinal == 1:
        execution = state["execution"]
        ack = runtime.submit(
            agent_id=state["reviewAgentId"], role="review", request_file=request_file,
            request_hash=state["originalRequestHash"], reviewed_work_run_id=run["runId"],
            codex=execution["codex"], sandbox=execution["sandbox"], model=execution["model"],
        )
    else:
        ack = runtime.send(
            agent_id=state["reviewAgentId"], request_file=request_file,
            request_hash=state["originalRequestHash"], reviewed_work_run_id=run["runId"],
        )
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
    if receipt["decision"] == "approved":
        if state["testEvidencePolicy"] == "required" and state.get("testEvidence") is None:
            _terminal(state, "needs-human-decision", "test_evidence_required", "Human-authorized test evidence is required for acceptance")
        elif state.get("testEvidence") is not None and state["testEvidence"].get("exitStatus") != 0:
            _terminal(state, "needs-human-decision", "test_evidence_inconclusive", "supplied test evidence does not show success")
        else:
            _terminal(state, "completed", "approved", "Review approved with no blocking findings")
        _write_state(path, state)
        return
    current_hashes, aggregate = _blocking_fingerprints(receipt)
    prior_hashes = state.get("findingFingerprints", {})
    for finding_id in set(current_hashes) & set(prior_hashes):
        if current_hashes[finding_id] != prior_hashes[finding_id]:
            raise agent_exec.ContractError("finding_identity_changed", f"finding {finding_id} changed materially")
    unchanged = state.get("blockingFindingFingerprint") == aggregate
    state["counters"]["unchangedFindingRounds"] = (
        state["counters"]["unchangedFindingRounds"] + 1 if unchanged else 0
    )
    state["findingFingerprints"] = {**prior_hashes, **current_hashes}
    state["blockingFindingFingerprint"] = aggregate
    state["pendingFindingIds"] = sorted(current_hashes)
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
    )
    ack = runtime.send(
        agent_id=state["workAgentId"], request_file=request_file,
        request_hash=state["originalRequestHash"],
    )
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
        "statePath": str(state_path(Path(state["projectRoot"]), state["workAgentId"], state["loopId"])),
    }


def status_loop(args: argparse.Namespace, runtime: AgentRuntime | None = None) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    _path, state = _read_state(root, args.work_agent, args.loop_id)
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
