from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXEC_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "agent_exec.py"
LOOP_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "agent_loop.py"


def load_modules():
    exec_spec = importlib.util.spec_from_file_location("agent_exec", EXEC_SCRIPT)
    if exec_spec is None or exec_spec.loader is None:
        raise RuntimeError("cannot load agent_exec")
    agent_exec = importlib.util.module_from_spec(exec_spec)
    exec_spec.loader.exec_module(agent_exec)
    sys.modules["agent_exec"] = agent_exec
    loop_spec = importlib.util.spec_from_file_location("agent_loop", LOOP_SCRIPT)
    if loop_spec is None or loop_spec.loader is None:
        raise RuntimeError("cannot load agent_loop")
    agent_loop = importlib.util.module_from_spec(loop_spec)
    loop_spec.loader.exec_module(agent_loop)
    return agent_exec, agent_loop


class FakeRuntime:
    def __init__(self) -> None:
        self.next_work = 1
        self.next_review = 1
        self.runs: dict[tuple[str, str], dict] = {}
        self.cancelled: list[tuple[str, str]] = []
        self.reconciled: list[str] = []
        self.statused: list[tuple[str, str]] = []

    def submit(self, **values):
        role = values["role"]
        agent_id = values["agent_id"]
        if role == "work":
            run_id = f"run-work-{self.next_work}"
            self.next_work += 1
        else:
            run_id = f"run-review-{self.next_review}"
            self.next_review += 1
        self.runs[(agent_id, run_id)] = {
            "status": "accepted",
            "agentId": agent_id,
            "runId": run_id,
            "dispatchId": values["dispatch_id"],
            "dispatchTuple": self.dispatch_tuple(values, "submit"),
        }
        self.persist_run(values, self.runs[(agent_id, run_id)], role)
        return {"runId": run_id}

    def send(self, **values):
        agent_id = values["agent_id"]
        if "review" in agent_id:
            run_id = f"run-review-{self.next_review}"
            self.next_review += 1
        else:
            run_id = f"run-work-{self.next_work}"
            self.next_work += 1
        self.runs[(agent_id, run_id)] = {
            "status": "accepted",
            "agentId": agent_id,
            "runId": run_id,
            "dispatchId": values["dispatch_id"],
            "dispatchTuple": self.dispatch_tuple(values, "send"),
        }
        role = "review" if "review" in agent_id else "work"
        self.persist_run(values, self.runs[(agent_id, run_id)], role)
        return {"runId": run_id}

    @staticmethod
    def persist_run(values, run, role):
        request_path = Path(values["request_file"]).resolve()
        factory = next((parent for parent in request_path.parents if parent.name == ".agent-factory"), None)
        root = factory.parent if factory is not None else request_path.parent
        directory = root / ".agent-factory" / "agent" / values["agent_id"] / "runs" / run["runId"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "state.json").write_text(
            json.dumps({**run, "role": role}), encoding="utf-8"
        )

    def status(self, agent_id, run_id):
        self.statused.append((agent_id, run_id))
        return self.runs[(agent_id, run_id)]

    def status_dispatch(self, agent_id, dispatch_id):
        matches = [run for (managed_agent, _), run in self.runs.items() if managed_agent == agent_id and run.get("dispatchId") == dispatch_id]
        if not matches:
            raise sys.modules["agent_exec"].ContractError("dispatch_not_found", "missing")
        return matches[0]

    @staticmethod
    def dispatch_tuple(values, operation):
        content_hash = hashlib.sha256(Path(values["request_file"]).read_bytes()).hexdigest()
        return {
            "agentId": values["agent_id"], "role": values.get("role", "review" if "review" in values["agent_id"] else "work"),
            "actor": "main", "requestHash": content_hash,
            "receiptRequestHash": values["request_hash"],
            "reviewedWorkRunId": values.get("reviewed_work_run_id"), "operation": operation,
        }

    def cancel(self, agent_id, run_id):
        self.cancelled.append((agent_id, run_id))
        return {"status": "cancelling"}

    def reconcile(self, agent_id):
        self.reconciled.append(agent_id)
        return {"runs": []}


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent_exec, self.module = load_modules()

    def start_args(self, directory: str) -> argparse.Namespace:
        request = Path(directory) / "request.md"
        request.write_text("Implement one bounded change without running tests.\n", encoding="utf-8")
        return argparse.Namespace(
            project_root=Path(directory),
            request_file=request,
            work_agent="work-loop",
            review_agent="review-loop",
            max_work_turns=3,
            max_review_turns=3,
            max_revisions=2,
            max_elapsed_seconds=7200,
            max_unchanged_finding_rounds=1,
            test_evidence_policy="not-required",
            test_evidence_file=None,
            codex="codex",
            sandbox="workspace-write",
            model=None,
        )

    def command_args(self, directory: str, loop_id: str) -> argparse.Namespace:
        return argparse.Namespace(
            project_root=Path(directory), work_agent="work-loop", loop_id=loop_id
        )

    def init_git(self, directory: str) -> None:
        commands = (
            ["git", "init", "-q"],
            ["git", "config", "user.email", "agent-loop@example.invalid"],
            ["git", "config", "user.name", "Agent Loop Test"],
            ["git", "add", "."],
            ["git", "commit", "-qm", "initial"],
        )
        for command in commands:
            subprocess.run(command, cwd=directory, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def approve_required(self, directory: str, runtime: FakeRuntime):
        args = self.start_args(directory)
        args.test_evidence_policy = "required"
        self.init_git(directory)
        ack = self.module.start_loop(args, runtime)
        command = self.command_args(directory, ack["loopId"])
        request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
        runtime.runs[("work-loop", "run-work-1")] = self.make_run(
            directory, role="work", run_id="run-work-1", request_hash=request_hash
        )
        self.module.reconcile_loop(command, runtime)
        runtime.runs[("review-loop", "run-review-1")] = self.make_run(
            directory, role="review", run_id="run-review-1", request_hash=request_hash,
            reviewed_work_run_id="run-work-1",
        )
        stopped = self.module.reconcile_loop(command, runtime)
        state = self.agent_exec.safe_read_json(Path(ack["statePath"]))
        return ack, command, stopped, state

    def evidence_args(self, directory: str, state: dict, **updates) -> argparse.Namespace:
        loop_directory = Path(state["projectRoot"]) / ".agent-factory" / "evidence-inputs"
        loop_directory.mkdir(parents=True, exist_ok=True)
        output = loop_directory / "output.bin"
        output.write_bytes(b"all focused tests passed\n")
        evidence = {
            "schemaVersion": "0.1.0",
            "kind": "agent-loop-test-evidence",
            **state["acceptanceBinding"],
            "actor": "human",
            "timestamp": "2026-08-28T00:00:00Z",
            "authorizationReference": "human-request-42",
            "command": "python -m unittest tests.test_agent_loop",
            "exitStatus": 0,
            "outputHash": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
        evidence.update(updates)
        evidence_path = loop_directory / "evidence.json"
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
        return argparse.Namespace(
            project_root=Path(directory), work_agent="work-loop", loop_id=state["loopId"],
            evidence_file=evidence_path, test_output_file=output,
        )

    def test_test_evidence_accepts_verification_actor_and_rejects_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = {
                "loopId": "loop-example",
                "projectRoot": directory,
                "acceptanceBinding": {
                    "originalRequestHash": "a" * 64,
                    "latestWorkRunId": "run-work-1",
                    "approvingReviewRunId": "run-review-1",
                    "workspaceFingerprint": "b" * 64,
                },
            }
            args = self.evidence_args(directory, state, actor="verification")
            _content, evidence = self.module._read_test_evidence(args.evidence_file)
            self.assertEqual(evidence["actor"], "verification")
            args = self.evidence_args(directory, state, actor="main")
            with self.assertRaisesRegex(self.agent_exec.ContractError, "actor"):
                self.module._read_test_evidence(args.evidence_file)

    def make_run(
        self,
        directory: str,
        *,
        role: str,
        run_id: str,
        request_hash: str,
        reviewed_work_run_id: str | None = None,
        decision: str = "approved",
        findings: list[dict] | None = None,
        resolved_finding_ids: list[str] | None = None,
    ) -> dict:
        agent_id = "work-loop" if role == "work" else "review-loop"
        run_directory = (
            Path(directory)
            / ".agent-factory"
            / "agent"
            / agent_id
            / "runs"
            / run_id
        )
        run_directory.mkdir(parents=True, exist_ok=True)
        state_path = run_directory / "state.json"
        if not state_path.exists():
            state_path.write_text("{}\n", encoding="utf-8")
        receipt_schema_path = run_directory / "receipt.schema.json"
        receipt_schema_path.write_text("{}\n", encoding="utf-8")
        result_path = run_directory / "result.md"
        result_path.write_text("result\n", encoding="utf-8")
        receipt_path = run_directory / "receipt.json"
        if role == "work":
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "work-receipt",
                "runId": run_id,
                "requestHash": request_hash,
                "outcome": "implemented",
                "changedPaths": ["skills/agent/scripts/agent_exec.py"],
                "addressedFindingIds": ["REV-001"] if run_id != "run-work-1" else [],
                "tests": {"run": False, "reason": "work-agent-prohibited"},
            }
            session_id = "session-work"
        else:
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "review-receipt",
                "runId": run_id,
                "reviewedWorkRunId": reviewed_work_run_id,
                "reviewedRequestHash": request_hash,
                "decision": decision,
                "findings": findings or [],
                "resolvedFindingIds": resolved_finding_ids or [],
                "tests": {"run": False, "reason": "static-review-only"},
            }
            session_id = "session-review"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return {
            "status": "completed",
            "role": role,
            "agentId": agent_id,
            "runId": run_id,
            "sessionId": session_id,
            "resultPath": str(result_path),
            "statePath": str(state_path),
            "receiptPath": str(receipt_path),
            "receiptSchemaPath": str(receipt_schema_path),
            "receiptRequestHash": request_hash,
            "reviewedWorkRunId": reviewed_work_run_id,
        }

    def followup_review_with_ledger(
        self, directory: str, runtime: FakeRuntime, finding: dict
    ) -> tuple[dict, argparse.Namespace, str]:
        ack = self.module.start_loop(self.start_args(directory), runtime)
        command = self.command_args(directory, ack["loopId"])
        request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
        runtime.runs[("work-loop", "run-work-1")] = self.make_run(
            directory, role="work", run_id="run-work-1", request_hash=request_hash
        )
        self.module.reconcile_loop(command, runtime)
        runtime.runs[("review-loop", "run-review-1")] = self.make_run(
            directory, role="review", run_id="run-review-1", request_hash=request_hash,
            reviewed_work_run_id="run-work-1", decision="changes_requested",
            findings=[finding],
        )
        self.module.reconcile_loop(command, runtime)
        runtime.runs[("work-loop", "run-work-2")] = self.make_run(
            directory, role="work", run_id="run-work-2", request_hash=request_hash
        )
        self.module.reconcile_loop(command, runtime)
        return ack, command, request_hash

    def test_budget_validation_rejects_nonpositive_and_contradictory_values(self) -> None:
        with self.assertRaises(self.agent_exec.ContractError):
            self.module.validate_budgets(3, 3, 0, 7200, 1)
        with self.assertRaises(self.agent_exec.ContractError):
            self.module.validate_budgets(2, 3, 2, 7200, 1)

    def test_start_accepts_exact_initial_work_pending_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
            state = self.agent_exec.safe_read_json(Path(ack["statePath"]))

        self.assertEqual(state["phase"], "work-running")
        self.assertEqual(state["childRuns"][0]["dispatchId"], state["currentChild"]["dispatchId"])

    def test_strict_validator_rejects_illegal_initial_pending_phase(self) -> None:
        class CrashBeforeRuntime(FakeRuntime):
            def submit(self, **values):
                raise RuntimeError("preserve initial pending intent")

        with tempfile.TemporaryDirectory() as directory:
            runtime = CrashBeforeRuntime()
            with self.assertRaises(RuntimeError):
                self.module.start_loop(self.start_args(directory), runtime)
            state_path = next(
                (Path(directory) / ".agent-factory" / "agent" / "work-loop" / "loops").glob("*/state.json")
            )
            state = self.agent_exec.safe_read_json(state_path)
            state["phase"] = "review-pending"
            self.agent_exec.atomic_write_json(state_path, state)
            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.module.status_loop(self.command_args(directory, state["loopId"]), runtime)

        self.assertEqual(raised.exception.code, "loop_state_invalid")

    def test_non_git_not_required_loop_completes_after_review_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            args = self.start_args(directory)
            ack = self.module.start_loop(args, runtime)
            state = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            request_hash = state["originalRequestHash"]
            runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                directory, role="work", run_id="run-work-1", request_hash=request_hash
            )
            first = self.module.reconcile_loop(self.command_args(directory, ack["loopId"]), runtime)
            self.assertEqual(first["phase"], "review-running")
            self.assertEqual(first["currentChild"]["agentId"], "review-loop")
            self.assertEqual(first["currentChild"]["runId"], "run-review-1")
            persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            self.assertFalse((Path(directory) / ".git").exists())
            self.assertIsNone(persisted["reviewSourceBinding"])
            self.assertEqual(
                persisted["currentChild"],
                {
                    "role": "review",
                    "agentId": first["currentChild"]["agentId"],
                    "runId": first["currentChild"]["runId"],
                    "dispatchId": first["currentChild"]["dispatchId"],
                },
            )
            runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                directory,
                role="review",
                run_id="run-review-1",
                request_hash=request_hash,
                reviewed_work_run_id="run-work-1",
            )
            final = self.module.reconcile_loop(self.command_args(directory, ack["loopId"]), runtime)

        self.assertEqual(final["status"], "completed")
        self.assertEqual(final["terminalReason"]["code"], "approved")
        self.assertIsNone(final["currentChild"])

    def test_required_test_evidence_policy_stops_approval_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            args = self.start_args(directory)
            args.test_evidence_policy = "required"
            self.init_git(directory)
            ack = self.module.start_loop(args, runtime)
            command = self.command_args(directory, ack["loopId"])
            request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
            runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                directory, role="work", run_id="run-work-1", request_hash=request_hash
            )
            self.module.reconcile_loop(command, runtime)
            runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                directory, role="review", run_id="run-review-1", request_hash=request_hash,
                reviewed_work_run_id="run-work-1",
            )
            final = self.module.reconcile_loop(command, runtime)

        self.assertEqual(final["status"], "needs-human-decision")
        self.assertEqual(final["terminalReason"]["code"], "test_evidence_required")

    def test_empty_ledger_applied_review_terminal_marker_is_strict(self) -> None:
        cases = (
            ("approved", None),
            ("approved", "run-review-stale"),
            ("approved", "run-work-1"),
            ("approved", "run-review-2"),
            ("test-evidence-required", None),
            ("test-evidence-required", "run-review-stale"),
            ("test-evidence-required", "run-work-1"),
            ("test-evidence-required", "run-review-2"),
        )
        for terminal, marker in cases:
            with self.subTest(terminal=terminal, marker=marker), tempfile.TemporaryDirectory() as directory:
                runtime = FakeRuntime()
                if terminal == "test-evidence-required":
                    ack, command, _stopped, state = self.approve_required(directory, runtime)
                else:
                    ack = self.module.start_loop(self.start_args(directory), runtime)
                    command = self.command_args(directory, ack["loopId"])
                    request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
                    runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                        directory, role="work", run_id="run-work-1",
                        request_hash=request_hash,
                    )
                    self.module.reconcile_loop(command, runtime)
                    runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                        directory, role="review", run_id="run-review-1",
                        request_hash=request_hash, reviewed_work_run_id="run-work-1",
                    )
                    self.module.reconcile_loop(command, runtime)
                    state = self.agent_exec.safe_read_json(Path(ack["statePath"]))
                self.assertEqual(state["findingLedger"], {})
                state["latestAppliedReviewRunId"] = marker
                self.agent_exec.atomic_write_json(Path(ack["statePath"]), state)
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.module.status_loop(command, runtime)

                self.assertEqual(raised.exception.code, "loop_state_invalid")

    def test_start_rejects_pre_start_test_evidence_for_every_policy(self) -> None:
        for policy in ("required", "not-required"):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                args = self.start_args(directory)
                args.test_evidence_policy = policy
                args.test_evidence_file = Path(directory) / "evidence.json"
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.module.start_loop(args, FakeRuntime())
                self.assertEqual(raised.exception.code, "test_evidence_pre_start_forbidden")

    def test_valid_post_review_attachment_is_bound_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack, _command, stopped, state = self.approve_required(directory, runtime)
            args = self.evidence_args(directory, state)
            completed = self.module.attach_evidence(args)
            repeated = self.module.attach_evidence(args)
            persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            copied_evidence_exists = Path(persisted["testEvidence"]["evidencePath"]).is_file()
            copied_output_exists = Path(persisted["testEvidence"]["outputPath"]).is_file()

        self.assertEqual(stopped["terminalReason"]["code"], "test_evidence_required")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(repeated["status"], "completed")
        self.assertEqual(persisted["terminalReason"]["code"], "approved_with_test_evidence")
        self.assertEqual(
            {key: persisted["testEvidence"][key] for key in state["acceptanceBinding"]},
            state["acceptanceBinding"],
        )
        self.assertTrue(copied_evidence_exists)
        self.assertTrue(copied_output_exists)

    def test_attachment_rejects_binding_and_output_mismatches_and_nonzero_status(self) -> None:
        cases = (
            ("originalRequestHash", "0" * 64, "test_evidence_binding_invalid"),
            ("latestWorkRunId", "run-work-stale", "test_evidence_binding_invalid"),
            ("approvingReviewRunId", "run-review-stale", "test_evidence_binding_invalid"),
            ("workspaceFingerprint", "1" * 64, "test_evidence_binding_invalid"),
            ("outputHash", "2" * 64, "test_output_hash_mismatch"),
            ("exitStatus", 1, "test_evidence_unsuccessful"),
        )
        for field, value, code in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                runtime = FakeRuntime()
                _ack, _command, _stopped, state = self.approve_required(directory, runtime)
                args = self.evidence_args(directory, state, **{field: value})
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.module.attach_evidence(args)
                self.assertEqual(raised.exception.code, code)

    def test_attachment_rejects_source_mutation_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            _ack, _command, _stopped, state = self.approve_required(directory, runtime)
            args = self.evidence_args(directory, state)
            (Path(directory) / "source.py").write_text("changed = True\n", encoding="utf-8")
            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.module.attach_evidence(args)
        self.assertEqual(raised.exception.code, "workspace_fingerprint_changed")

    def test_reconcile_rejects_mutation_after_review_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            args = self.start_args(directory)
            args.test_evidence_policy = "required"
            self.init_git(directory)
            ack = self.module.start_loop(args, runtime)
            command = self.command_args(directory, ack["loopId"])
            request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
            runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                directory, role="work", run_id="run-work-1", request_hash=request_hash
            )
            self.module.reconcile_loop(command, runtime)
            dispatched = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                directory, role="review", run_id="run-review-1", request_hash=request_hash,
                reviewed_work_run_id="run-work-1",
            )
            (Path(directory) / "changed-after-review.py").write_text(
                "review_never_saw_this = True\n", encoding="utf-8"
            )
            failed = self.module.reconcile_loop(command, runtime)

        self.assertEqual(dispatched["reviewSourceBinding"]["reviewRunId"], "run-review-1")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["terminalReason"]["code"], "reviewed_workspace_changed")

    def test_attachment_rejects_wrong_lifecycle_state_and_conflicting_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack, _command, _stopped, state = self.approve_required(directory, runtime)
            args = self.evidence_args(directory, state)
            self.module.attach_evidence(args)
            conflicting = self.evidence_args(directory, state, authorizationReference="different")
            with self.assertRaises(self.agent_exec.ContractError) as conflict:
                self.module.attach_evidence(conflicting)
            persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            persisted["status"] = "failed"
            persisted["phase"] = "failed"
            persisted["testEvidence"] = None
            self.agent_exec.atomic_write_json(Path(ack["statePath"]), persisted)
            with self.assertRaises(self.agent_exec.ContractError) as lifecycle:
                self.module.attach_evidence(args)
        self.assertEqual(conflict.exception.code, "test_evidence_conflict")
        self.assertEqual(lifecycle.exception.code, "test_evidence_lifecycle_invalid")

    def test_start_parser_requires_explicit_test_evidence_policy(self) -> None:
        with self.assertRaises(self.agent_exec.ContractError):
            self.module.build_parser().parse_args(
                [
                    "start",
                    "--request-file",
                    "request.md",
                    "--work-agent",
                    "work-loop",
                    "--review-agent",
                    "review-loop",
                ]
            )

    def test_blocking_revision_and_unchanged_finding_circuit(self) -> None:
        finding = {
            "id": "REV-001",
            "severity": "blocking",
            "path": "skills/agent/scripts/agent_exec.py",
            "location": "validate_receipt",
            "problem": "binding is missing",
            "evidence": "state contains the expected binding",
            "correction": "compare the exact values",
        }
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            args = self.start_args(directory)
            ack = self.module.start_loop(args, runtime)
            command = self.command_args(directory, ack["loopId"])
            request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
            runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                directory, role="work", run_id="run-work-1", request_hash=request_hash
            )
            self.module.reconcile_loop(command, runtime)
            runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                directory, role="review", run_id="run-review-1", request_hash=request_hash,
                reviewed_work_run_id="run-work-1", decision="changes_requested", findings=[finding],
            )
            revision = self.module.reconcile_loop(command, runtime)
            self.assertEqual(revision["phase"], "work-running")
            runtime.runs[("work-loop", "run-work-2")] = self.make_run(
                directory, role="work", run_id="run-work-2", request_hash=request_hash
            )
            self.module.reconcile_loop(command, runtime)
            runtime.runs[("review-loop", "run-review-2")] = self.make_run(
                directory, role="review", run_id="run-review-2", request_hash=request_hash,
                reviewed_work_run_id="run-work-2", decision="changes_requested", findings=[finding],
            )
            stopped = self.module.reconcile_loop(command, runtime)

        self.assertEqual(stopped["status"], "needs-human-decision")
        self.assertEqual(stopped["terminalReason"]["code"], "unchanged_blocking_findings")

    def test_review_finding_lifecycle_partition_and_identity_rules(self) -> None:
        finding = {
            "id": "REV-001", "severity": "blocking", "path": "a.py", "location": "f",
            "problem": "broken", "evidence": "observed", "correction": "fix it",
        }
        def receipt(findings, resolved):
            return {"findings": findings, "resolvedFindingIds": resolved}
        state = {
            "counters": {"reviewTurns": 1}, "pendingFindingIds": [],
            "resolvedFindingIds": [], "findingLedger": {}, "findingFingerprints": {},
        }
        self.module._apply_review_finding_lifecycle(state, receipt([finding], []), "run-review-1")
        self.assertEqual(state["pendingFindingIds"], ["REV-001"])
        self.assertEqual(state["findingLedger"]["REV-001"]["firstReviewRunId"], "run-review-1")
        state["counters"]["reviewTurns"] = 2
        self.module._apply_review_finding_lifecycle(state, receipt([], ["REV-001"]), "run-review-2")
        self.assertEqual(state["resolvedFindingIds"], ["REV-001"])
        self.assertEqual(state["findingLedger"]["REV-001"]["lastReviewRunId"], "run-review-2")

        cases = []
        base = {
            "counters": {"reviewTurns": 2}, "pendingFindingIds": ["REV-001"],
            "resolvedFindingIds": [], "findingFingerprints": {"REV-001": self.module._finding_hash(finding)},
            "findingLedger": {"REV-001": {
                "fingerprint": self.module._finding_hash(finding), "firstReviewRunId": "run-review-1",
                "lastReviewRunId": "run-review-1", "status": "pending",
            }},
        }
        cases.append((json.loads(json.dumps(base)), receipt([], []), "finding_resolution_invalid"))
        cases.append((json.loads(json.dumps(base)), receipt([], ["REV-UNKNOWN"]), "finding_resolution_invalid"))
        cases.append((json.loads(json.dumps(base)), receipt([finding], ["REV-001"]), "finding_resolution_invalid"))
        changed = {**finding, "problem": "different material identity"}
        cases.append((json.loads(json.dumps(base)), receipt([changed], []), "finding_identity_changed"))
        resolved_state = json.loads(json.dumps(base))
        resolved_state["pendingFindingIds"] = []
        resolved_state["resolvedFindingIds"] = ["REV-001"]
        resolved_state["findingLedger"]["REV-001"]["status"] = "resolved"
        cases.append((resolved_state, receipt([finding], []), "finding_resolution_invalid"))
        for lifecycle_state, review_receipt, code in cases:
            with self.subTest(code=code, receipt=review_receipt), self.assertRaises(self.agent_exec.ContractError) as raised:
                self.module._apply_review_finding_lifecycle(lifecycle_state, review_receipt, "run-review-2")
            self.assertEqual(raised.exception.code, code)

    def test_unapplied_followup_review_terminal_reasons_remain_stable(self) -> None:
        finding = {
            "id": "REV-001", "severity": "blocking", "path": "a.py", "location": "f",
            "problem": "broken", "evidence": "observed", "correction": "fix it",
        }
        for case, expected_reason in (
            ("failed", "child_terminal_failure"),
            ("cancelled", "cancelled"),
            ("identity-rejected", "finding_identity_changed"),
        ):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                runtime = FakeRuntime()
                ack, command, request_hash = self.followup_review_with_ledger(
                    directory, runtime, finding
                )
                before = self.agent_exec.safe_read_json(Path(ack["statePath"]))
                self.assertEqual(before["latestReviewRunId"], "run-review-2")
                self.assertEqual(before["latestAppliedReviewRunId"], "run-review-1")
                if case == "failed":
                    runtime.runs[("review-loop", "run-review-2")] = {
                        "status": "failed", "agentId": "review-loop",
                        "runId": "run-review-2",
                    }
                    first = self.module.reconcile_loop(command, runtime)
                elif case == "cancelled":
                    self.module.cancel_loop(command, runtime)
                    runtime.runs[("review-loop", "run-review-2")] = {
                        "status": "cancelled", "agentId": "review-loop",
                        "runId": "run-review-2",
                    }
                    first = self.module.reconcile_loop(command, runtime)
                else:
                    changed = {**finding, "problem": "materially different"}
                    runtime.runs[("review-loop", "run-review-2")] = self.make_run(
                        directory, role="review", run_id="run-review-2",
                        request_hash=request_hash, reviewed_work_run_id="run-work-2",
                        decision="changes_requested", findings=[changed],
                    )
                    first = self.module.reconcile_loop(command, runtime)
                status = self.module.status_loop(command, runtime)
                repeated = self.module.reconcile_loop(command, runtime)
                persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))

                self.assertEqual(first["terminalReason"]["code"], expected_reason)
                self.assertEqual(status["terminalReason"]["code"], expected_reason)
                self.assertEqual(repeated["terminalReason"]["code"], expected_reason)
                self.assertEqual(persisted["latestAppliedReviewRunId"], "run-review-1")

    def test_strict_validator_rejects_corrupt_finding_ledger_history_and_indexes(self) -> None:
        finding = {
            "id": "REV-001", "severity": "blocking", "path": "a.py", "location": "f",
            "problem": "broken", "evidence": "observed", "correction": "fix it",
        }
        cases = (
            ("nonexistent-review", False),
            ("work-run-as-review", False),
            ("reversed-review-order", False),
            ("stale-pending-last-review", True),
            ("fingerprint-index-mismatch", False),
            ("applied-review-identity", False),
        )
        for case, leave_pending in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                runtime = FakeRuntime()
                ack = self.module.start_loop(self.start_args(directory), runtime)
                command = self.command_args(directory, ack["loopId"])
                request_hash = self.agent_exec.safe_read_json(Path(ack["statePath"]))["originalRequestHash"]
                runtime.runs[("work-loop", "run-work-1")] = self.make_run(
                    directory, role="work", run_id="run-work-1", request_hash=request_hash
                )
                self.module.reconcile_loop(command, runtime)
                runtime.runs[("review-loop", "run-review-1")] = self.make_run(
                    directory, role="review", run_id="run-review-1", request_hash=request_hash,
                    reviewed_work_run_id="run-work-1", decision="changes_requested", findings=[finding],
                )
                self.module.reconcile_loop(command, runtime)
                runtime.runs[("work-loop", "run-work-2")] = self.make_run(
                    directory, role="work", run_id="run-work-2", request_hash=request_hash
                )
                self.module.reconcile_loop(command, runtime)
                runtime.runs[("review-loop", "run-review-2")] = self.make_run(
                    directory, role="review", run_id="run-review-2", request_hash=request_hash,
                    reviewed_work_run_id="run-work-2",
                    decision="changes_requested" if leave_pending else "approved",
                    findings=[finding] if leave_pending else [],
                    resolved_finding_ids=[] if leave_pending else ["REV-001"],
                )
                self.module.reconcile_loop(command, runtime)
                state_path = Path(ack["statePath"])
                state = self.agent_exec.safe_read_json(state_path)
                entry = state["findingLedger"]["REV-001"]
                if case == "nonexistent-review":
                    entry["firstReviewRunId"] = "run-review-missing"
                elif case == "work-run-as-review":
                    entry["firstReviewRunId"] = "run-work-1"
                elif case == "reversed-review-order":
                    entry["firstReviewRunId"] = "run-review-2"
                    entry["lastReviewRunId"] = "run-review-1"
                elif case == "stale-pending-last-review":
                    entry["lastReviewRunId"] = "run-review-1"
                elif case == "fingerprint-index-mismatch":
                    state["findingFingerprints"]["REV-001"] = "0" * 64
                else:
                    state["latestAppliedReviewRunId"] = "run-work-2"
                self.agent_exec.atomic_write_json(state_path, state)
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.module.status_loop(command, runtime)

                self.assertEqual(raised.exception.code, "loop_state_invalid")

    def test_hybrid_legacy_pending_state_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
            state_path = Path(ack["statePath"])
            state = self.agent_exec.safe_read_json(state_path)
            state.pop("findingLedger")
            state.pop("resolvedFindingIds")
            state["phase"] = "review-dispatching"
            state["pendingDispatch"] = {
                "role": "review", "agentId": "review-loop", "requestHash": "a" * 64,
                "ordinal": 1, "revision": False,
            }
            self.agent_exec.atomic_write_json(state_path, state)
            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.module.status_loop(self.command_args(directory, ack["loopId"]), runtime)

        self.assertEqual(raised.exception.code, "loop_state_invalid")

    def test_reconcile_retries_same_dispatch_after_crash_before_runtime_call(self) -> None:
        class CrashBeforeRuntime(FakeRuntime):
            def submit(self, **values):
                if not hasattr(self, "crashed"):
                    self.crashed = True
                    raise RuntimeError("crash before runtime call")
                return super().submit(**values)
        with tempfile.TemporaryDirectory() as directory:
            runtime = CrashBeforeRuntime()
            with self.assertRaises(RuntimeError):
                self.module.start_loop(self.start_args(directory), runtime)
            state_path = next((Path(directory) / ".agent-factory" / "agent" / "work-loop" / "loops").glob("*/state.json"))
            before = self.agent_exec.safe_read_json(state_path)
            dispatch_id = before["pendingDispatch"]["dispatchId"]
            command = self.command_args(directory, before["loopId"])
            recovered = self.module.reconcile_loop(command, runtime)
            persisted = self.agent_exec.safe_read_json(state_path)
        self.assertEqual(recovered["phase"], "work-running")
        self.assertEqual(persisted["currentChild"]["dispatchId"], dispatch_id)

    def test_reconcile_adopts_exact_run_after_lost_ack_and_rejects_tuple_mismatch(self) -> None:
        class LostAck(FakeRuntime):
            def submit(self, **values):
                ack = super().submit(**values)
                if not hasattr(self, "crashed"):
                    self.crashed = True
                    raise RuntimeError("ack lost")
                return ack
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                runtime = LostAck()
                with self.assertRaises(RuntimeError):
                    self.module.start_loop(self.start_args(directory), runtime)
                state_path = next((Path(directory) / ".agent-factory" / "agent" / "work-loop" / "loops").glob("*/state.json"))
                state = self.agent_exec.safe_read_json(state_path)
                dispatch_id = state["pendingDispatch"]["dispatchId"]
                managed = runtime.status_dispatch("work-loop", dispatch_id)
                if mismatch:
                    managed["dispatchTuple"]["actor"] = "human"
                    with self.assertRaises(self.agent_exec.ContractError) as raised:
                        self.module.reconcile_loop(self.command_args(directory, state["loopId"]), runtime)
                    self.assertEqual(raised.exception.code, "dispatch_binding_invalid")
                else:
                    recovered = self.module.reconcile_loop(self.command_args(directory, state["loopId"]), runtime)
                    self.assertEqual(recovered["currentChild"]["runId"], managed["runId"])
                    self.assertEqual(recovered["currentChild"]["dispatchId"], dispatch_id)
                    self.assertEqual(runtime.next_work, 2)

    def test_strict_validator_rejects_corrupt_child_history_before_runtime_status(self) -> None:
        cases = ("role", "agent", "ordinal", "counter", "latest", "dispatch_tuple")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                runtime = FakeRuntime()
                ack = self.module.start_loop(self.start_args(directory), runtime)
                state_path = Path(ack["statePath"])
                state = self.agent_exec.safe_read_json(state_path)
                child = state["childRuns"][0]
                if case == "role":
                    child["role"] = "review"
                elif case == "agent":
                    child["agentId"] = "review-loop"
                elif case == "ordinal":
                    child["ordinal"] = 2
                elif case == "counter":
                    state["counters"]["workTurns"] = 2
                elif case == "latest":
                    state["latestWorkRunId"] = "run-work-other"
                else:
                    child["dispatchTuple"]["actor"] = "human"
                self.agent_exec.atomic_write_json(state_path, state)
                with self.assertRaises(self.agent_exec.ContractError) as raised:
                    self.module.status_loop(self.command_args(directory, ack["loopId"]), runtime)
                self.assertEqual(raised.exception.code, "loop_state_invalid")
                self.assertEqual(runtime.statused, [])

    def test_cancel_is_idempotent_and_reconcile_finishes_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
            command = self.command_args(directory, ack["loopId"])
            first = self.module.cancel_loop(command, runtime)
            second = self.module.cancel_loop(command, runtime)
            self.assertEqual(first["status"], "cancelling")
            self.assertEqual(second["status"], "cancelling")
            runtime.runs[("work-loop", "run-work-1")] = {"status": "cancelled"}
            final = self.module.reconcile_loop(command, runtime)
            persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))
            repeated = self.module.reconcile_loop(command, runtime)

        self.assertEqual(final["status"], "cancelled")
        self.assertIsNone(final["currentChild"])
        self.assertIsNone(persisted["currentChild"])
        self.assertEqual(repeated["status"], "cancelled")

    def test_child_failure_and_human_decision_terminal_responses_clear_child(self) -> None:
        cases = (
            ("failed", "failed"),
            ("needs-human-decision", "needs-human-decision"),
        )
        for child_status, expected_status in cases:
            with self.subTest(child_status=child_status):
                with tempfile.TemporaryDirectory() as directory:
                    runtime = FakeRuntime()
                    ack = self.module.start_loop(self.start_args(directory), runtime)
                    command = self.command_args(directory, ack["loopId"])
                    runtime.runs[("work-loop", "run-work-1")] = {
                        "status": child_status,
                        "agentId": "work-loop",
                        "runId": "run-work-1",
                    }
                    response = self.module.reconcile_loop(command, runtime)
                    persisted = self.agent_exec.safe_read_json(Path(ack["statePath"]))

                self.assertEqual(response["status"], expected_status)
                self.assertIsNone(response["currentChild"])
                self.assertIsNone(persisted["currentChild"])

    def test_pending_dispatch_cancellation_adopts_and_cancels_without_reactivation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
            command = self.command_args(directory, ack["loopId"])
            state_path = Path(ack["statePath"])
            state = self.agent_exec.safe_read_json(state_path)
            for child in state["childRuns"]:
                child.pop("dispatchId", None)
                child.pop("dispatchTuple", None)
            if isinstance(state.get("currentChild"), dict):
                state["currentChild"].pop("dispatchId", None)
            state.pop("findingLedger", None)
            state.pop("resolvedFindingIds", None)
            state.pop("latestAppliedReviewRunId", None)
            dispatch_hash = "b" * 64
            state["phase"] = "review-dispatching"
            state["pendingDispatch"] = {
                "role": "review",
                "agentId": "review-loop",
                "requestHash": dispatch_hash,
                "ordinal": 1,
                "revision": False,
            }
            self.agent_exec.atomic_write_json(state_path, state)
            managed = (
                Path(directory)
                / ".agent-factory"
                / "agent"
                / "review-loop"
                / "runs"
                / "run-review-crash"
            )
            managed.mkdir(parents=True)
            (managed / "state.json").write_text(
                json.dumps(
                    {
                        "runId": "run-review-crash",
                        "agentId": "review-loop",
                        "role": "review",
                        "status": "running",
                        "requestHash": dispatch_hash,
                    }
                ),
                encoding="utf-8",
            )
            runtime.runs[("review-loop", "run-review-crash")] = {
                "status": "running",
                "agentId": "review-loop",
                "runId": "run-review-crash",
            }
            self.module.cancel_loop(command, runtime)
            recovered = self.module.reconcile_loop(command, runtime)
            self.assertEqual(recovered["status"], "cancelling")
            self.assertIn(("review-loop", "run-review-crash"), runtime.cancelled)
            runtime.runs[("review-loop", "run-review-crash")] = {"status": "cancelled"}
            final = self.module.reconcile_loop(command, runtime)
            repeated = self.module.reconcile_loop(command, runtime)

        self.assertEqual(final["status"], "cancelled")
        self.assertEqual(repeated["status"], "cancelled")

    def test_pending_dispatch_cancellation_without_child_finishes_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
            command = self.command_args(directory, ack["loopId"])
            state_path = Path(ack["statePath"])
            state = self.agent_exec.safe_read_json(state_path)
            for child in state["childRuns"]:
                child.pop("dispatchId", None)
                child.pop("dispatchTuple", None)
            if isinstance(state.get("currentChild"), dict):
                state["currentChild"].pop("dispatchId", None)
            state.pop("findingLedger", None)
            state.pop("resolvedFindingIds", None)
            state.pop("latestAppliedReviewRunId", None)
            state["pendingDispatch"] = {
                "role": "review",
                "agentId": "review-loop",
                "requestHash": "c" * 64,
                "ordinal": 1,
                "revision": False,
            }
            state["phase"] = "review-dispatching"
            self.agent_exec.atomic_write_json(state_path, state)
            self.module.cancel_loop(command, runtime)
            final = self.module.reconcile_loop(command, runtime)
            repeated = self.module.reconcile_loop(command, runtime)

        self.assertEqual(final["status"], "cancelled")
        self.assertEqual(final["terminalReason"]["code"], "cancelled-before-dispatch")
        self.assertEqual(repeated["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
