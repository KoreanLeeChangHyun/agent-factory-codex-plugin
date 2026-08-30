#!/usr/bin/env python3
"""Orchestrate the Agent Factory Work/Verification loop."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import exec as agent_exec


SCHEMA_VERSION = "0.1.0"
CHILD_TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AgentRuntime:
    """Call only the public managed-session interface."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.script = Path(agent_exec.__file__).resolve()

    def call(self, arguments: list[str]) -> dict[str, Any]:
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
        if process.returncode != 0 or response.get("kind") == "error":
            detail = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise agent_exec.ContractError(
                str(detail.get("code", "child_runtime_failure")),
                str(detail.get("message", "Agent runtime command failed")),
            )
        return response

    def dispatch(
        self,
        *,
        operation: str,
        agent_id: str,
        role: str,
        request_file: Path,
        request_hash: str,
        dispatch_id: str,
        verified_work_run_id: str | None,
        execution: dict[str, Any],
        capability_binding_file: Path | None,
    ) -> dict[str, Any]:
        arguments = [
            operation,
            "--agent", agent_id,
            "--request-file", str(request_file),
            "--receipt-request-hash", request_hash,
            "--dispatch-id", dispatch_id,
        ]
        if operation == "submit":
            arguments.extend([
                "--role", role,
                "--codex", str(execution["codex"]),
                "--sandbox", str(execution["sandbox"]),
            ])
            if execution.get("model"):
                arguments.extend(["--model", str(execution["model"])])
        if verified_work_run_id is not None:
            arguments.extend(["--verified-work-run-id", verified_work_run_id])
        if capability_binding_file is not None:
            arguments.extend(["--capability-binding-file", str(capability_binding_file)])
        return self.call(arguments)

    def status(self, agent_id: str, run_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--run-id", run_id])["run"]

    def status_dispatch(self, agent_id: str, dispatch_id: str) -> dict[str, Any]:
        return self.call(["status", "--agent", agent_id, "--dispatch-id", dispatch_id])["run"]


def loop_directory(root: Path, work_agent: str, loop_id: str, *, create: bool = False) -> Path:
    agent_exec.validate_id(work_agent, agent_exec.AGENT_ID, "agent_id")
    agent_exec.validate_id(loop_id, agent_exec.AGENT_ID, "loop_id")
    directory = agent_exec.agent_directory(root, work_agent, create=create) / "loops" / loop_id
    if create:
        agent_exec.ensure_directory(directory, root)
    return directory


def state_path(root: Path, work_agent: str, loop_id: str) -> Path:
    return loop_directory(root, work_agent, loop_id) / "state.json"


def read_state(root: Path, work_agent: str, loop_id: str) -> tuple[Path, dict[str, Any]]:
    path = state_path(root, work_agent, loop_id)
    return path, agent_exec.safe_read_json(path)


def public_state(state: dict[str, Any], child: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "work-verification-loop",
        "loopId": state["loopId"],
        "status": state["status"],
        "phase": state["phase"],
        "workAgentId": state["workAgentId"],
        "verificationAgentId": state["verificationAgentId"],
        "latestWorkRunId": state.get("latestWorkRunId"),
        "latestVerificationRunId": state.get("latestVerificationRunId"),
        "humanSkip": state.get("humanSkip"),
        "pendingDispatch": state.get("pendingDispatch"),
        "controlPlaneError": state.get("controlPlaneError"),
        "currentChild": child,
        "terminalReason": state.get("terminalReason"),
        "statePath": state["statePath"],
    }


def write_request(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    agent_exec.atomic_write(path, content.encode("utf-8"))
    return path


def prepare_dispatch(
    state: dict[str, Any], path: Path, *, role: str, request_file: Path,
    verified_work_run_id: str | None = None,
) -> None:
    if role not in {"work", "verification"}:
        raise agent_exec.ContractError("graph_role_invalid", "dispatch role is outside the graph")
    if isinstance(state.get("pendingDispatch"), dict):
        raise agent_exec.ContractError("dispatch_intent_exists", "a durable dispatch intent already exists")
    if role == "verification" and (
        not isinstance(state.get("latestWorkRunId"), str)
        or verified_work_run_id != state.get("latestWorkRunId")
    ):
        raise agent_exec.ContractError("graph_transition_invalid", "Verification must bind the latest Work run")
    if role == "work" and state.get("latestWorkRunId") is not None and state.get("lastVerificationDecision") != "fail":
        raise agent_exec.ContractError("graph_transition_invalid", "a Work revision requires failed Verification")
    agent_id = state["workAgentId"] if role == "work" else state["verificationAgentId"]
    root = Path(state["projectRoot"])
    operation = "send" if agent_exec.session_file(root, agent_id).exists() else "submit"
    content = agent_exec.safe_read_bytes(request_file, agent_exec.MAX_REQUEST_BYTES)
    role_binding = state.get("capabilityBindings", {}).get(role, {})
    state["pendingDispatch"] = {
        "dispatchId": f"dispatch-{uuid.uuid4().hex}",
        "operation": operation,
        "agentId": agent_id,
        "role": role,
        "requestPath": str(request_file),
        "requestHash": hashlib.sha256(content).hexdigest(),
        "receiptRequestHash": state["originalRequestHash"],
        "verifiedWorkRunId": verified_work_run_id,
        "capabilityBindingPath": role_binding.get("path"),
        "capabilityBindingHash": role_binding.get("hash"),
    }
    state["phase"] = f"{role}-dispatching"
    state["updatedAt"] = now()
    agent_exec.atomic_write_json(path, state)


def complete_pending_dispatch(
    state: dict[str, Any], path: Path, runtime: AgentRuntime,
) -> dict[str, Any]:
    pending = state.get("pendingDispatch")
    if not isinstance(pending, dict):
        raise agent_exec.ContractError("dispatch_intent_missing", "durable dispatch intent is missing")
    try:
        run = runtime.status_dispatch(pending["agentId"], pending["dispatchId"])
    except agent_exec.ContractError as error:
        if error.code != "dispatch_not_found":
            raise
        acknowledgement = runtime.dispatch(
            operation=pending["operation"],
            agent_id=pending["agentId"],
            role=pending["role"],
            request_file=Path(pending["requestPath"]),
            request_hash=pending["receiptRequestHash"],
            dispatch_id=pending["dispatchId"],
            verified_work_run_id=pending["verifiedWorkRunId"],
            execution=state["execution"],
            capability_binding_file=(
                Path(pending["capabilityBindingPath"])
                if pending.get("capabilityBindingPath") else None
            ),
        )
        run = runtime.status(pending["agentId"], str(acknowledgement["runId"]))
    expected_tuple = {
        "agentId": pending["agentId"],
        "role": pending["role"],
        "actor": "main",
        "requestHash": pending["requestHash"],
        "receiptRequestHash": pending["receiptRequestHash"],
        "verifiedWorkRunId": pending["verifiedWorkRunId"],
        "operation": pending["operation"],
    }
    if pending.get("capabilityBindingHash") is not None:
        expected_tuple["capabilityBindingHash"] = pending["capabilityBindingHash"]
    if run.get("dispatchId") != pending["dispatchId"] or run.get("dispatchTuple") != expected_tuple:
        raise agent_exec.ContractError("dispatch_binding_invalid", "managed run does not match durable dispatch intent")
    role = pending["role"]
    run_id = str(run["runId"])
    state["currentChild"] = {"role": role, "agentId": pending["agentId"], "runId": run_id}
    state["phase"] = f"{role}-running"
    if role == "work":
        state["latestWorkRunId"] = run_id
    else:
        state["latestVerificationRunId"] = run_id
    state["pendingDispatch"] = None
    state["controlPlaneError"] = None
    state["status"] = "active"
    state["updatedAt"] = now()
    agent_exec.atomic_write_json(path, state)
    return run


def dispatch(
    state: dict[str, Any], path: Path, runtime: AgentRuntime, *, role: str,
    request_file: Path, verified_work_run_id: str | None = None,
) -> dict[str, Any]:
    prepare_dispatch(
        state, path, role=role, request_file=request_file,
        verified_work_run_id=verified_work_run_id,
    )
    return complete_pending_dispatch(state, path, runtime)


def start_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    agent_exec.validate_id(args.work_agent, agent_exec.AGENT_ID, "work_agent")
    agent_exec.validate_id(args.verification_agent, agent_exec.AGENT_ID, "verification_agent")
    if args.work_agent == args.verification_agent:
        raise agent_exec.ContractError("agent_identity_conflict", "Work and Verification require different Agent sessions")
    request = agent_exec.safe_read_bytes(args.request_file.resolve(strict=False), agent_exec.MAX_REQUEST_BYTES)
    if not request.decode("utf-8").strip():
        raise agent_exec.ContractError("request_invalid", "request must not be empty")
    loop_id = f"loop-{uuid.uuid4().hex[:16]}"
    directory = loop_directory(root, args.work_agent, loop_id, create=True)
    original = directory / "original-request.md"
    agent_exec.atomic_write(original, request)
    capability_bindings: dict[str, dict[str, str | None]] = {}
    for role in ("work", "verification"):
        _binding_document, binding_bytes = agent_exec.read_capability_bindings(
            getattr(args, f"{role}_capability_binding_file", None)
        )
        binding_path = None
        binding_hash = None
        if binding_bytes is not None:
            binding_path = directory / f"{role}-capability-bindings.json"
            agent_exec.atomic_write(binding_path, binding_bytes)
            binding_hash = hashlib.sha256(binding_bytes).hexdigest()
        capability_bindings[role] = {
            "path": str(binding_path) if binding_path else None,
            "hash": binding_hash,
        }
    created = now()
    path = directory / "state.json"
    state = {
        "schemaVersion": SCHEMA_VERSION,
        "loopId": loop_id,
        "status": "active",
        "phase": "starting",
        "projectRoot": str(root),
        "statePath": str(path),
        "originalRequestPath": str(original),
        "originalRequestHash": hashlib.sha256(request).hexdigest(),
        "capabilityBindings": capability_bindings,
        "workAgentId": args.work_agent,
        "verificationAgentId": args.verification_agent,
        "latestWorkRunId": None,
        "latestVerificationRunId": None,
        "lastVerificationDecision": None,
        "pendingFindingIds": [],
        "currentChild": None,
        "humanSkip": None,
        "pendingDispatch": None,
        "controlPlaneError": None,
        "terminalReason": None,
        "execution": {"codex": args.codex, "sandbox": args.sandbox, "model": args.model},
        "createdAt": created,
        "updatedAt": created,
    }
    agent_exec.atomic_write_json(path, state)
    dispatch(state, path, AgentRuntime(root), role="work", request_file=original)
    return public_state(state, state["currentChild"])


def verification_request(state: dict[str, Any], work: dict[str, Any], directory: Path) -> Path:
    return write_request(directory, f"verification-{work['runId']}.md", f"""Verify this Work result.

Original request: {state['originalRequestPath']}
Work run: {work['runId']}
Work result: {work['resultPath']}
Work receipt: {work['receiptPath']}
""")


def revision_request(state: dict[str, Any], verification: dict[str, Any], receipt: dict[str, Any], directory: Path) -> Path:
    findings = json.dumps(receipt["findings"], ensure_ascii=False, indent=2)
    return write_request(directory, f"revision-{verification['runId']}.md", f"""Address these failed Verification findings.

Original request: {state['originalRequestPath']}
Previous Work run: {state['latestWorkRunId']}
Verification result: {verification['resultPath']}
Findings:
{findings}
""")


def reconcile_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    path, state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] == "completed":
            return public_state(state)
        runtime = AgentRuntime(root)
        if isinstance(state.get("pendingDispatch"), dict):
            child = complete_pending_dispatch(state, path, runtime)
            return public_state(state, child)
        current = state.get("currentChild")
        if not isinstance(current, dict):
            raise agent_exec.ContractError("loop_state_invalid", "active loop has no child")
        child = runtime.status(current["agentId"], current["runId"])
        if child["status"] not in CHILD_TERMINAL:
            return public_state(state, child)
        if child["status"] != "completed":
            state.update({
                "status": "runtime-error",
                "phase": "control-plane-error",
                "controlPlaneError": child.get("error") or {
                    "code": child["status"],
                    "message": "managed child did not complete",
                },
                "updatedAt": now(),
            })
            agent_exec.atomic_write_json(path, state)
            return public_state(state, child)
        directory = path.parent
        if current["role"] == "work":
            receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
            pending_findings = set(state.get("pendingFindingIds", []))
            if not pending_findings.issubset(set(receipt["addressedFindingIds"])):
                raise agent_exec.ContractError("finding_binding_invalid", "Work receipt omitted failed Verification findings")
            if isinstance(state.get("humanSkip"), dict):
                state.update({"status": "completed", "phase": "ended", "currentChild": None, "terminalReason": {"code": "human-skip", "message": "Human skipped Verification"}, "updatedAt": now()})
                agent_exec.atomic_write_json(path, state)
                return public_state(state)
            request = verification_request(state, child, directory)
            state["pendingFindingIds"] = []
            dispatch(state, path, runtime, role="verification", request_file=request, verified_work_run_id=child["runId"])
            return public_state(state, state["currentChild"])
        if current["role"] != "verification":
            raise agent_exec.ContractError("loop_state_invalid", "child role is outside the graph")
        receipt = agent_exec.validate_receipt(root, child, agent_id=current["agentId"], run_id=current["runId"])
        if receipt["decision"] == "pass":
            state["lastVerificationDecision"] = "pass"
            state.update({"status": "completed", "phase": "ended", "currentChild": None, "terminalReason": {"code": "pass", "message": "Verification passed"}, "updatedAt": now()})
            agent_exec.atomic_write_json(path, state)
            return public_state(state)
        state["lastVerificationDecision"] = "fail"
        state["pendingFindingIds"] = [finding["id"] for finding in receipt["findings"]]
        request = revision_request(state, child, receipt, directory)
        dispatch(state, path, runtime, role="work", request_file=request)
        return public_state(state, state["currentChild"])


def status_loop(args: argparse.Namespace) -> dict[str, Any]:
    root = agent_exec.resolve_project_root(args.project_root)
    _path, state = read_state(root, args.work_agent, args.loop_id)
    child = None
    if isinstance(state.get("currentChild"), dict) and state["status"] != "completed":
        current = state["currentChild"]
        child = AgentRuntime(root).status(current["agentId"], current["runId"])
    return public_state(state, child)


def skip_loop(args: argparse.Namespace) -> dict[str, Any]:
    if args.actor != "human":
        raise agent_exec.ContractError("human_skip_unauthorized", "Verification skip requires actor human")
    if not args.authorization_reference.strip() or not args.decision_evidence.strip():
        raise agent_exec.ContractError("human_skip_evidence_missing", "Verification skip requires authorization reference and decision evidence")
    root = agent_exec.resolve_project_root(args.project_root)
    path, _state = read_state(root, args.work_agent, args.loop_id)
    with agent_exec.file_lock(path.parent / ".loop.lock"):
        state = agent_exec.safe_read_json(path)
        if state["status"] == "completed":
            return public_state(state)
        current = state.get("currentChild")
        if not isinstance(current, dict) or current.get("role") != "work":
            raise agent_exec.ContractError("verification_already_started", "Human skip is available only before Verification starts")
        state.update({
            "status": "active",
            "humanSkip": {
                "actor": "human",
                "authorizationReference": args.authorization_reference.strip(),
                "decisionEvidence": args.decision_evidence.strip(),
                "recordedAt": now(),
            },
            "updatedAt": now(),
        })
        agent_exec.atomic_write_json(path, state)
        return public_state(state, current)


def build_parser() -> agent_exec.JsonArgumentParser:
    parser = agent_exec.JsonArgumentParser(prog="loop.py")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--project-root", type=Path, default=Path.cwd())
    start.add_argument("--request-file", type=Path, required=True)
    start.add_argument("--work-agent", required=True)
    start.add_argument("--verification-agent", required=True)
    start.add_argument("--codex", default="codex")
    start.add_argument("--sandbox", choices=agent_exec.SANDBOXES, default=agent_exec.DEFAULT_SANDBOX)
    start.add_argument("--model")
    start.add_argument("--work-capability-binding-file", type=Path)
    start.add_argument("--verification-capability-binding-file", type=Path)
    for name in ("status", "reconcile", "skip"):
        command = commands.add_parser(name)
        command.add_argument("--project-root", type=Path, default=Path.cwd())
        command.add_argument("--work-agent", required=True)
        command.add_argument("--loop-id", required=True)
        if name == "skip":
            command.add_argument("--actor", choices=agent_exec.ACTORS, required=True)
            command.add_argument("--authorization-reference", required=True)
            command.add_argument("--decision-evidence", required=True)
    return parser


def emit(value: dict[str, Any]) -> None:
    agent_exec.emit(value)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        handlers = {"start": start_loop, "status": status_loop, "reconcile": reconcile_loop, "skip": skip_loop}
        emit(handlers[args.command](args))
        return 0
    except agent_exec.ContractError as error:
        emit(agent_exec.error_document(error.code, error.message))
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        emit(agent_exec.error_document("runtime_failure", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
