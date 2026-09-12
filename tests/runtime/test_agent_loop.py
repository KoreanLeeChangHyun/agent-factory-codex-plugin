from __future__ import annotations

import runtime_test_home  # Isolate all runtime subprocesses from the real home.

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
EXEC_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "exec.py"
LOOP_SCRIPT = ROOT / "skills" / "agent" / "scripts" / "loop.py"


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
        binding_hash = (
            hashlib.sha256(Path(values["capability_binding_file"]).read_bytes()).hexdigest()
            if values.get("capability_binding_file") else None
        )
        dispatch_tuple = {
            "agentId": values["agent_id"],
            "role": values["role"],
            "actor": "main",
            "requestHash": request_hash,
            "receiptRequestHash": values["request_hash"],
            "verifiedWorkRunId": values["verified_work_run_id"],
            "operation": values["operation"],
            "humanApprovalPolicy": values["human_approval_policy"],
        }
        if "executionPolicy" in values["execution"]:
            dispatch_tuple["executionPolicy"] = values["execution"]["executionPolicy"]
        if binding_hash is not None:
            dispatch_tuple["capabilityBindingHash"] = binding_hash
        directory = self.agent_exec.agent_root(self.root) / values["agent_id"] / "runs" / run_id
        directory.mkdir(parents=True, exist_ok=True)
        session_id = f"session-{values['agent_id']}"
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
            "sessionId": session_id,
        }
        self.agent_exec.atomic_write_json(directory / "state.json", run)
        self.agent_exec.atomic_write_json(directory / "receipt.schema.json", {})
        session = self.agent_exec.session_file(self.root, values["agent_id"])
        session.parent.mkdir(parents=True, exist_ok=True)
        if not session.exists():
            self.agent_exec.atomic_write_json(
                session, {"role": values["role"], "sessionId": session_id}
            )
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
            "requestHash": run["receiptRequestHash"], "outcome": "completed",
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

    def start(self, extra: list[str] | None = None):
        arguments = [
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true",
        ]
        arguments.extend(extra or [])
        args = self.agent_loop.build_parser().parse_args(arguments)
        return self.agent_loop.start_loop(args)

    def reconcile(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "reconcile", "--project-root", str(self.root), "--work-agent", "work-agent",
            "--loop-id", started["loopId"],
        ])
        return self.agent_loop.reconcile_loop(args)

    def recover_receipt(self, started):
        args = self.agent_loop.build_parser().parse_args([
            "recover-receipt", "--project-root", str(self.root),
            "--work-agent", "work-agent", "--loop-id", started["loopId"],
        ])
        return self.agent_loop.recover_receipt(args)

    def fail_work_receipt(self, started, code="receipt_path_contract_invalid", message=None):
        run = self.runtime.runs[("work-agent", started["latestWorkRunId"])]
        run.update({
            "status": "failed",
            "error": {
                "code": code,
                "message": message or "changedPaths must contain only project-root-relative paths",
            },
        })
        return self.reconcile(started)

    def test_legacy_execution_upgrade_binds_current_authority_without_rewriting_child(self) -> None:
        started = self.start()
        path = Path(started["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        child_before = dict(self.runtime.runs[(started["currentChild"]["agentId"], started["currentChild"]["runId"])])
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        self.agent_exec.atomic_write_json(path, stored)
        self.reconcile(started)
        execution = self.agent_exec.safe_read_json(path)["execution"]
        self.assertEqual(execution["executionPolicy"], runtime_test_home.policy("danger-full-access"))
        self.assertEqual(self.agent_exec.safe_read_json(Path(execution["executionPolicyPath"])), execution["executionPolicy"])
        self.assertEqual(self.runtime.runs[(started["currentChild"]["agentId"], started["currentChild"]["runId"])], child_before)

    def test_legacy_execution_upgrade_fails_without_mutating_state_on_invalid_authority(self) -> None:
        started = self.start()
        path = Path(started["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        self.agent_exec.atomic_write_json(path, stored)
        before = path.read_bytes()
        with mock.patch.dict(self.agent_exec.os.environ, {"AGENT_FACTORY_EXECUTION_POLICY": "invalid"}):
            with self.assertRaises(self.agent_exec.ContractError) as raised:
                self.reconcile(started)
        self.assertEqual(raised.exception.code, "execution_policy_invalid")
        self.assertEqual(path.read_bytes(), before)

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

    def test_loop_preserves_capability_binding_for_child_dispatch(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text(json.dumps({
            "schemaVersion": "0.1.0",
            "bindings": [{
                "capabilityId": "git.cli.inspect",
                "authority": {"kind": "native-executable", "reference": "executable:git"},
                "invocationRoute": "git",
                "exactTarget": str(self.root),
                "allowedEffects": [],
                "allowedScopes": ["repository:read"],
                "approvalReference": None,
            }],
        }), encoding="utf-8")
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true", "--work-capability-binding-file", str(binding),
        ])
        state = self.agent_loop.start_loop(args)
        dispatched = self.runtime.dispatches[-1]["capability_binding_file"]
        self.assertIsNotNone(dispatched)
        self.assertEqual(Path(dispatched).parent.name, state["loopId"])

    def test_loop_start_rejects_symlinked_capability_binding(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text("{}", encoding="utf-8")
        linked = self.root / "binding-link.json"
        linked.symlink_to(binding)
        args = self.agent_loop.build_parser().parse_args([
            "start", "--project-root", str(self.root), "--request-file", str(self.request),
            "--work-agent", "work-agent", "--verification-agent", "verification-agent",
            "--codex", "/bin/true", "--work-capability-binding-file", str(linked),
        ])
        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.agent_loop.start_loop(args)
        self.assertEqual(raised.exception.code, "capability_binding_invalid")

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
        loops = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        state = self.agent_exec.safe_read_json(loops / "state.json")
        dispatch_id = state["pendingDispatch"]["dispatchId"]
        state = self.reconcile({"loopId": state["loopId"]})
        self.reconcile(state)
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(self.runtime.runs[("work-agent", state["latestWorkRunId"])]["dispatchId"], dispatch_id)

    def test_dispatch_binds_required_human_approval_policy(self) -> None:
        state = self.start()
        dispatched = self.runtime.dispatches[-1]
        run = self.runtime.runs[("work-agent", state["latestWorkRunId"])]
        self.assertEqual(dispatched["human_approval_policy"], "required")
        self.assertEqual(run["dispatchTuple"]["humanApprovalPolicy"], "required")

    def test_legacy_pending_ack_without_human_approval_policy_is_adopted(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"].pop("humanApprovalPolicy")

        recovered = self.reconcile({"loopId": stored["loopId"]})

        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])

    def test_pending_ack_rejects_bypass_human_approval_policy(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        stored = self.agent_exec.safe_read_json(directory / "state.json")
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"]["humanApprovalPolicy"] = "bypass"

        with self.assertRaises(self.agent_exec.ContractError) as raised:
            self.reconcile({"loopId": stored["loopId"]})

        self.assertEqual(raised.exception.code, "dispatch_binding_invalid")
        persisted = self.agent_exec.safe_read_json(directory / "state.json")
        self.assertEqual(persisted["pendingDispatch"]["dispatchId"], child["dispatchId"])

    def test_legacy_pending_ack_recovers_original_tuple_without_redispatch(self) -> None:
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        directory = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
        path = directory / "state.json"
        stored = self.agent_exec.safe_read_json(path)
        stored["execution"] = {"codex": "/bin/true", "sandbox": "danger-full-access", "model": None}
        child = next(iter(self.runtime.runs.values()))
        child["dispatchTuple"].pop("executionPolicy")
        original_tuple = dict(child["dispatchTuple"])
        self.agent_exec.atomic_write_json(path, stored)
        recovered = self.reconcile({"loopId": stored["loopId"]})
        self.assertEqual(len(self.runtime.dispatches), 1)
        self.assertEqual(child["dispatchTuple"], original_tuple)
        self.assertEqual(recovered["currentChild"]["runId"], child["runId"])
        self.assertIsNone(recovered["pendingDispatch"])

    def test_crash_before_call_reuses_durable_dispatch_id(self) -> None:
        self.runtime.fail_before_call = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.start()
        loops = next((self.agent_exec.agent_root(self.root) / "work-agent" / "loops").iterdir())
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

    def test_receipt_recovery_preserves_failed_run_and_reaches_verification(self) -> None:
        state = self.start()
        failed_run_id = state["latestWorkRunId"]
        failed = dict(self.runtime.runs[("work-agent", failed_run_id)])
        state = self.fail_work_receipt(state)

        state = self.recover_receipt(state)
        recovery_run_id = state["latestWorkRunId"]
        self.assertNotEqual(recovery_run_id, failed_run_id)
        self.assertEqual(self.runtime.runs[("work-agent", failed_run_id)], {
            **failed,
            "status": "failed",
            "error": {
                "code": "receipt_path_contract_invalid",
                "message": "changedPaths must contain only project-root-relative paths",
            },
        })
        recovery = state["receiptRecovery"]
        self.assertEqual(recovery["failedWorkRunId"], failed_run_id)
        self.assertEqual(recovery["recoveryWorkRunId"], recovery_run_id)
        dispatched = self.runtime.dispatches[-1]
        self.assertEqual(dispatched["operation"], "send")
        stored = self.agent_exec.safe_read_json(Path(state["statePath"]))
        self.assertEqual(dispatched["request_hash"], stored["originalRequestHash"])
        self.assertEqual(dispatched["execution"]["executionPolicy"], stored["execution"]["executionPolicy"])
        recovery_request = Path(recovery["requestPath"]).read_text(encoding="utf-8")
        self.assertIn("Do not repeat any already performed tool effect", recovery_request)
        self.assertIn(f"Failed Work run: {failed_run_id}", recovery_request)

        self.runtime.complete_work("work-agent", recovery_run_id)
        state = self.reconcile(state)
        self.assertEqual(state["currentChild"]["role"], "verification")
        verification = self.runtime.runs[("verification-agent", state["latestVerificationRunId"])]
        self.assertEqual(verification["verifiedWorkRunId"], recovery_run_id)
        dispatch_count = len(self.runtime.dispatches)
        repeated = self.recover_receipt(state)
        self.assertEqual(repeated["latestVerificationRunId"], state["latestVerificationRunId"])
        self.assertEqual(len(self.runtime.dispatches), dispatch_count)

    def test_receipt_recovery_preserves_valid_capability_evidence(self) -> None:
        binding = self.root / "binding.json"
        binding.write_text(json.dumps({
            "schemaVersion": "0.1.0",
            "bindings": [{
                "capabilityId": "git.cli.inspect",
                "authority": {"kind": "native-executable", "reference": "executable:git"},
                "invocationRoute": "git", "exactTarget": str(self.root),
                "allowedEffects": [], "allowedScopes": ["repository:read"],
                "approvalReference": None,
            }],
        }), encoding="utf-8")
        state = self.fail_work_receipt(self.start([
            "--work-capability-binding-file", str(binding),
        ]))
        recovered = self.recover_receipt(state)
        stored = self.agent_exec.safe_read_json(Path(recovered["statePath"]))
        self.assertEqual(
            str(self.runtime.dispatches[-1]["capability_binding_file"]),
            stored["capabilityBindings"]["work"]["path"],
        )
        recovery_run = self.runtime.runs[("work-agent", recovered["latestWorkRunId"])]
        request = self.agent_loop.verification_request(
            stored, recovery_run, Path(recovered["statePath"]).parent
        ).read_text(encoding="utf-8")
        self.assertIn(stored["receiptRecovery"]["failedReceiptPath"], request)

    def test_receipt_recovery_preserves_revision_findings(self) -> None:
        state = self.start()
        self.runtime.complete_work("work-agent", state["latestWorkRunId"])
        state = self.reconcile(state)
        self.runtime.complete_verification(
            "verification-agent", state["latestVerificationRunId"], "fail"
        )
        state = self.reconcile(state)
        state = self.fail_work_receipt(state)

        recovered = self.recover_receipt(state)
        request = Path(recovered["receiptRecovery"]["requestPath"]).read_text(encoding="utf-8")
        self.assertIn('Required addressed finding IDs: ["finding-1"]', request)
        self.runtime.complete_work(
            "work-agent", recovered["latestWorkRunId"], ["finding-1"]
        )
        reconciled = self.reconcile(recovered)
        self.assertEqual(reconciled["currentChild"]["role"], "verification")

    def test_receipt_recovery_reuses_durable_dispatch_after_ack_loss(self) -> None:
        state = self.fail_work_receipt(self.start())
        self.runtime.lose_ack = True
        with self.assertRaises(self.agent_exec.ContractError):
            self.recover_receipt(state)
        dispatch_count = len(self.runtime.dispatches)
        stored = self.agent_exec.safe_read_json(Path(state["statePath"]))
        dispatch_id = stored["pendingDispatch"]["dispatchId"]

        recovered = self.recover_receipt(stored)
        self.assertEqual(len(self.runtime.dispatches), dispatch_count)
        self.assertEqual(
            self.runtime.runs[("work-agent", recovered["latestWorkRunId"])]["dispatchId"],
            dispatch_id,
        )

    def test_legacy_changed_path_error_remains_recoverable_without_capabilities(self) -> None:
        state = self.fail_work_receipt(
            self.start(), "receipt_invalid", "changedPaths must be bounded relative paths"
        )
        failed_run_id = state["latestWorkRunId"]
        recovered = self.recover_receipt(state)
        self.assertEqual(recovered["receiptRecovery"]["failedWorkRunId"], failed_run_id)

    def test_receipt_recovery_fails_closed_for_active_unsafe_or_wrong_session(self) -> None:
        active = self.start()
        with self.assertRaises(self.agent_exec.ContractError) as unavailable:
            self.recover_receipt(active)
        self.assertEqual(unavailable.exception.code, "receipt_recovery_unavailable")

        unsafe = self.fail_work_receipt(active, "sandbox_unavailable")
        with self.assertRaises(self.agent_exec.ContractError) as rejected:
            self.recover_receipt(unsafe)
        self.assertEqual(rejected.exception.code, "receipt_recovery_unsafe")

        receipt_error = {
            "code": "receipt_path_contract_invalid",
            "message": "changedPaths must contain only project-root-relative paths",
        }
        run = self.runtime.runs[("work-agent", unsafe["latestWorkRunId"])]
        run["error"] = receipt_error
        path = Path(unsafe["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["controlPlaneError"] = receipt_error
        self.agent_exec.atomic_write_json(path, stored)
        session_path = self.agent_exec.session_file(self.root, "work-agent")
        session = self.agent_exec.safe_read_json(session_path)
        session["sessionId"] = "different-session"
        self.agent_exec.atomic_write_json(session_path, session)
        with self.assertRaises(self.agent_exec.ContractError) as mismatch:
            self.recover_receipt(stored)
        self.assertEqual(mismatch.exception.code, "receipt_recovery_session_invalid")

    def test_receipt_recovery_rejects_test_and_capability_evidence_failures(self) -> None:
        state = self.fail_work_receipt(
            self.start(), "receipt_tests_invalid", "Work receipt must prove Work ran no tests"
        )
        with self.assertRaises(self.agent_exec.ContractError) as tests_error:
            self.recover_receipt(state)
        self.assertEqual(tests_error.exception.code, "receipt_recovery_unsafe")

        failed_run = self.runtime.runs[("work-agent", state["latestWorkRunId"])]
        capability_error = {
            "code": "receipt_capability_invalid",
            "message": "capability outcome binding is invalid",
        }
        failed_run["error"] = capability_error
        path = Path(state["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        stored["controlPlaneError"] = capability_error
        self.agent_exec.atomic_write_json(path, stored)
        before = dict(failed_run)
        with self.assertRaises(self.agent_exec.ContractError) as capability:
            self.recover_receipt(stored)
        self.assertEqual(capability.exception.code, "receipt_recovery_unsafe")
        self.assertEqual(failed_run, before)

    def test_rejected_legacy_recovery_does_not_publish_policy_or_change_bytes(self) -> None:
        state = self.start()
        path = Path(state["statePath"])
        stored = self.agent_exec.safe_read_json(path)
        self.assertTrue((path.parent / ".loop.lock").is_file())
        policy_path = Path(stored["execution"]["executionPolicyPath"])
        policy_path.unlink()
        stored["execution"] = {
            "codex": "/bin/true", "sandbox": "danger-full-access", "model": None,
        }
        self.agent_exec.atomic_write_json(path, stored)
        directory = path.parent
        before_files = {
            item.relative_to(directory): item.read_bytes()
            for item in directory.rglob("*") if item.is_file()
        }
        before_directories = {
            item.relative_to(directory) for item in directory.rglob("*") if item.is_dir()
        }

        with self.assertRaises(self.agent_exec.ContractError) as rejected:
            self.recover_receipt(stored)
        self.assertEqual(rejected.exception.code, "receipt_recovery_unavailable")
        self.assertEqual(before_files, {
            item.relative_to(directory): item.read_bytes()
            for item in directory.rglob("*") if item.is_file()
        })
        self.assertEqual(before_directories, {
            item.relative_to(directory) for item in directory.rglob("*") if item.is_dir()
        })


if __name__ == "__main__":
    unittest.main()
