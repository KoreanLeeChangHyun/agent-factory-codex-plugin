from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXEC_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "exec.py"
LOOP_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "loop.py"
PROMPT_ROOT = ROOT / "skills" / "agent" / "prompt"
AGENT_SKILL = ROOT / "skills" / "agent" / "SKILL.md"


def normalized_contract(content: str) -> str:
    return " ".join(re.sub(r"[`*_]", "", content).lower().split())


def load_modules():
    exec_spec = importlib.util.spec_from_file_location("exec", EXEC_SCRIPT)
    if exec_spec is None or exec_spec.loader is None:
        raise RuntimeError("cannot load exec runtime")
    agent_exec = importlib.util.module_from_spec(exec_spec)
    exec_spec.loader.exec_module(agent_exec)
    sys.modules["exec"] = agent_exec
    loop_spec = importlib.util.spec_from_file_location("loop", LOOP_SCRIPT)
    if loop_spec is None or loop_spec.loader is None:
        raise RuntimeError("cannot load loop runtime")
    agent_loop = importlib.util.module_from_spec(loop_spec)
    loop_spec.loader.exec_module(agent_loop)
    return agent_exec, agent_loop


class FakeRuntime:
    def __init__(self, root: Path, agent_exec) -> None:
        self.root = root
        self.agent_exec = agent_exec
        self.runs: dict[tuple[str, str], dict] = {}
        self.dispatches: list[dict] = []
        self.next_run = 1
        self.fail_before_call = False
        self.lose_ack = False

    def dispatch(self, **values):
        if self.fail_before_call:
            raise self.agent_exec.ContractError("child_runtime_failure", "crash before call")
        run_id = f"run-{self.next_run}"
        self.next_run += 1
        request_hash = hashlib.sha256(Path(values["request_file"]).read_bytes()).hexdigest()
        dispatch_tuple = {
            "agentId": values["agent_id"],
            "role": values["role"],
            "actor": "main",
            "requestHash": request_hash,
            "receiptRequestHash": values["request_hash"],
            "verifiedWorkRunId": values["verified_work_run_id"],
            "operation": values["operation"],
        }
        directory = self.root / ".agent-factory" / "agent" / values["agent_id"] / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=True)
        run = {
            "runId": run_id,
            "agentId": values["agent_id"],
            "role": values["role"],
            "status": "accepted",
            "requestHash": request_hash,
            "receiptRequestHash": values["request_hash"],
            "verifiedWorkRunId": values["verified_work_run_id"],
            "dispatchId": values["dispatch_id"],
            "dispatchTuple": dispatch_tuple,
            "statePath": str(directory / "state.json"),
            "resultPath": str(directory / "result.md"),
            "receiptPath": str(directory / "receipt.json"),
            "receiptSchemaPath": str(directory / "receipt.schema.json"),
        }
        self.agent_exec.atomic_write_json(directory / "state.json", run)
        self.agent_exec.atomic_write_json(directory / "receipt.schema.json", {})
        session = self.agent_exec.session_file(self.root, values["agent_id"])
        session.parent.mkdir(parents=True, exist_ok=True)
        if not session.exists():
            self.agent_exec.atomic_write_json(session, {"role": values["role"]})
        self.runs[(values["agent_id"], run_id)] = run
        self.dispatches.append(values)
        if self.lose_ack:
            self.lose_ack = False
            raise self.agent_exec.ContractError("child_runtime_failure", "ack lost")
        return {"runId": run_id}

    def status(self, agent_id, run_id):
        return self.runs[(agent_id, run_id)]

    def status_dispatch(self, agent_id, dispatch_id):
        matches = [
            run for (managed, _run_id), run in self.runs.items()
            if managed == agent_id and run["dispatchId"] == dispatch_id
        ]
        if not matches:
            raise self.agent_exec.ContractError("dispatch_not_found", "not dispatched")
        return matches[0]

    def complete_work(self, agent_id: str, run_id: str, addressed: list[str] | None = None):
        run = self.runs[(agent_id, run_id)]
        receipt = {
            "schemaVersion": "0.1.0", "kind": "work-receipt", "runId": run_id,
            "requestHash": run["receiptRequestHash"], "outcome": "implemented",
            "changedPaths": ["changed.txt"], "addressedFindingIds": addressed or [],
            "tests": {"run": False, "reason": "work-agent-prohibited"},
        }
        Path(run["resultPath"]).write_text("work result\n", encoding="utf-8")
        Path(run["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
        run["status"] = "completed"
        return run

    def complete_verification(self, agent_id: str, run_id: str, decision: str):
        run = self.runs[(agent_id, run_id)]
        findings = [] if decision == "pass" else [{
            "id": "finding-1", "path": "changed.txt", "location": "1",
            "problem": "incorrect", "evidence": "observed mismatch", "correction": "fix it",
        }]
        receipt = {
            "schemaVersion": "0.1.0", "kind": "verification-receipt", "runId": run_id,
            "verifiedWorkRunId": run["verifiedWorkRunId"],
            "verifiedRequestHash": run["receiptRequestHash"],
            "decision": decision, "findings": findings,
        }
        Path(run["resultPath"]).write_text("verification result\n", encoding="utf-8")
        Path(run["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
        run["status"] = "completed"
        return run


class AgentLoopContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent_exec, self.agent_loop = load_modules()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.request = self.root / "request.md"
        self.request.write_text("bounded work\n", encoding="utf-8")
        self.runtime = FakeRuntime(self.root, self.agent_exec)
        self.runtime_patch = mock.patch.object(self.agent_loop, "AgentRuntime", return_value=self.runtime)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    def start(self):
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true",
        ])
        return self.agent_loop.start_loop(args)

    def reconcile(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "reconcile", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", started["loopId"],
        ])
        return self.agent_loop.reconcile_loop(args)

    def test_complete_graph_reuses_work_and_verification_sessions(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        first_verification = state["latestVerificationRunId"]
        self.runtime.complete_verification("verification-agent", first_verification, "fail")
        state = self.reconcile(state)
        revised_work = state["latestWorkRunId"]
        self.assertEqual(self.runtime.dispatches[-1]["agent_id"], "work-agent")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.runtime.complete_work("work-agent", revised_work, ["finding-1"])
        state = self.reconcile(state)
        second_verification = state["latestVerificationRunId"]
        self.assertNotEqual(first_verification, second_verification)
        self.assertEqual(self.runtime.dispatches[-1]["agent_id"], "verification-agent")
        self.assertEqual(self.runtime.dispatches[-1]["operation"], "send")
        self.runtime.complete_verification("verification-agent", second_verification, "pass")
        state = self.reconcile(state)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["terminalReason"]["code"], "pass")

    def test_human_skip_records_evidence_and_never_dispatches_verification(self) -> None:
        state = self.start()
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "human",
            "--authorization-reference", "human-message-7", "--decision-evidence", "skip verification",
        ])
        state = self.agent_loop.skip_loop(args)
        self.assertEqual(state["status"], "active")
        self.assertIsNone(state["terminalReason"])
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.assertEqual(state["terminalReason"]["code"], "human-skip")
        self.assertEqual(state["humanSkip"]["authorizationReference"], "human-message-7")
        self.assertEqual([call["role"] for call in self.runtime.dispatches], ["work"])

    def test_human_skip_after_revision_starts_no_additional_verification(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification(
            "verification-agent", state["latestVerificationRunId"], "fail"
        )
        state = self.reconcile(state)
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "human",
            "--authorization-reference", "human-message-8",
            "--decision-evidence", "skip additional verification",
        ])
        state = self.agent_loop.skip_loop(args)
        self.assertEqual(state["status"], "active")
        self.assertIsNone(state["terminalReason"])
        self.runtime.complete_work(
            "work-agent", state["latestWorkRunId"], ["finding-1"]
        )
        state = self.reconcile(state)
        self.assertEqual(state["terminalReason"]["code"], "human-skip")
        self.assertEqual(
            [call["role"] for call in self.runtime.dispatches],
            ["work", "verification", "work"],
        )

    def test_non_human_skip_is_rejected(self) -> None:
        state = self.start()
        args = self.agent_loop.build_parser().parse_args([
            "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", state["loopId"], "--actor", "main",
            "--authorization-reference", "main-claim", "--decision-evidence", "skip",
        ])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.skip_loop(args)
        self.assertEqual(raised.exception.code, "human_skip_unauthorized")

    def test_skip_missing_decision_evidence_is_rejected(self) -> None:
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.build_parser().parse_args([
                "skip", "--project-root", str(self.root), "--work-agent", "work-agent",
                "--loop-id", "loop-one", "--actor", "human",
                "--authorization-reference", "human-message-7",
            ])
        self.assertEqual(raised.exception.code, "invalid_arguments")

    def test_ack_loss_recovers_same_dispatch_without_duplicate(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        loops = next((self.root / ".agent-factory" / "agent" / "work-agent" / "loops").iterdir())
        state = self.agent_exec.safe_read_json(loops / "state.json")
        dispatch_id = state["pendingDispatch"]["dispatchId"]
        state = self.reconcile({"loopId": state["loopId"]})
        self.reconcile(state)
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(self.runtime.runs[("work-agent", state["latestWorkRunId"])]["dispatchId"], dispatch_id)

    def test_crash_before_call_reuses_durable_dispatch_id(self) -> None:
        self.runtime.fail_before_call = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        loops = next((self.root / ".agent-factory" / "agent" / "work-agent" / "loops").iterdir())
        persisted = self.agent_exec.safe_read_json(loops / "state.json")
        dispatch_id = persisted["pendingDispatch"]["dispatchId"]
        self.runtime.fail_before_call = False
        state = self.reconcile({"loopId": persisted["loopId"]})
        self.assertEqual(self.runtime.dispatches[0]["dispatch_id"], dispatch_id)
        self.assertIsNone(state["pendingDispatch"])

    def test_outside_graph_role_is_rejected(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.prepare_dispatch(state, path, role="review", request_file=self.request)
        self.assertEqual(raised.exception.code, "graph_role_invalid")

    def test_outside_graph_transition_is_rejected(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.prepare_dispatch(
                state, path, role="verification", request_file=self.request,
                verified_work_run_id="run-not-latest",
            )
        self.assertEqual(raised.exception.code, "graph_transition_invalid")

    def test_child_failure_is_control_plane_error_not_graph_end(self) -> None:
        state = self.start()
        self.runtime.runs[("work-agent", state["latestWorkRunId"])]["status"] = "failed"
        state = self.reconcile(state)
        self.assertEqual(state["status"], "runtime-error")
        self.assertEqual(state["phase"], "control-plane-error")
        self.assertIsNone(state["terminalReason"])

    def test_capability_prompts_route_to_convention_contracts(self) -> None:
        main = normalized_contract((PROMPT_ROOT / "main.md").read_text(encoding="utf-8"))
        work = normalized_contract((PROMPT_ROOT / "work.md").read_text(encoding="utf-8"))
        self.assertRegex(
            main,
            r"when conducting adaptive interview.*convention skill.*references/interview\.md",
        )
        self.assertRegex(
            work,
            r"when the bounded task includes evidence exploration.*convention skill.*references/explorer\.md",
        )

    def test_child_role_prompts_preserve_execution_boundaries(self) -> None:
        work = normalized_contract((PROMPT_ROOT / "work.md").read_text(encoding="utf-8"))
        verification = normalized_contract(
            (PROMPT_ROOT / "verification.md").read_text(encoding="utf-8")
        )
        self.assertIn("perform the bounded task delegated by main", work)
        self.assertIn("do not verify your own work", work)
        self.assertIn("do not coordinate another agent", work)
        self.assertIn("return exactly one decision: pass or fail", verification)
        self.assertIn("do not edit or repair project files", verification)

    def test_role_prompt_transport_and_hosts_do_not_add_graph_nodes(self) -> None:
        skill = normalized_contract(AGENT_SKILL.read_text(encoding="utf-8"))
        self.assertIn("tagged role-instruction block", skill)
        self.assertIn("does not claim a separate platform system-channel message", skill)
        self.assertRegex(skill, r"codex cli.*exec-hosted session.*vs code extension")
        self.assertIn("hosts, not additional agent roles", skill)


if __name__ == "__main__":
    unittest.main()
