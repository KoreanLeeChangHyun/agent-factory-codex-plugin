from __future__ import annotations

import argparse
import importlib.util
import json
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
        }
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
        }
        return {"runId": run_id}

    def status(self, agent_id, run_id):
        return self.runs[(agent_id, run_id)]

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
                "resolvedFindingIds": [],
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

    def test_budget_validation_rejects_nonpositive_and_contradictory_values(self) -> None:
        with self.assertRaises(self.agent_exec.ContractError):
            self.module.validate_budgets(3, 3, 0, 7200, 1)
        with self.assertRaises(self.agent_exec.ContractError):
            self.module.validate_budgets(2, 3, 2, 7200, 1)

    def test_reconcile_response_tracks_new_review_and_terminal_clears_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = FakeRuntime()
            ack = self.module.start_loop(self.start_args(directory), runtime)
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
            self.assertEqual(
                persisted["currentChild"],
                {
                    "role": "review",
                    "agentId": first["currentChild"]["agentId"],
                    "runId": first["currentChild"]["runId"],
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

    def test_not_required_policy_rejects_supplied_test_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.start_args(directory)
            args.test_evidence_file = Path(directory) / "evidence.json"

            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.module.start_loop(args, FakeRuntime())

        self.assertEqual(raised.exception.code, "test_evidence_policy_conflict")

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
