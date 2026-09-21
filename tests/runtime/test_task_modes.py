"""Bounded route and native Plan transitions for independent Verification."""
import runtime_test_home
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from native_fixtures import native, runtime, native_fixture
from task_modes import route_instruction
from prompt_delivery import PromptParts


class TaskModeTests(unittest.TestCase):
    def test_new_main_default_and_explicit_dispatch_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = {"role": "main", "maxAttempts": 1}
            default = runtime.create_run(project_root=root, agent_id="main-default", actor="human", request=b"task", session=session)
            self.assertEqual(default["taskMode"], "direct")
            for mode in ("direct", "work", "plan", "verification", "plan-work", "work-verification", "plan-work-verification"):
                state = runtime.create_run(project_root=root, agent_id="main-selected", actor="human", request=b"task", session=session,
                                           execution_options={"taskMode": mode}, dispatch_id="dispatch-" + mode, dispatch_operation="send")
                self.assertEqual(state["taskMode"], mode)
                self.assertEqual(state["dispatchTuple"]["executionOptions"], {"taskMode": mode})
                self.assertIn(mode, route_instruction(mode, "main"))
            with self.assertRaises(runtime.ContractError):
                route_instruction("pretend-plan", "main")

    def fixture(self, root, *, plan_status="planned", cancel=False, failure=False, supported=True, task_mode="plan-work-verification"):
        original, rpc, state = native_fixture(root, goal=False)
        state["role"] = "work"
        state["executionOptions"] = {"taskMode": task_mode}
        original.session["role"] = "work"
        original.session["nativeCapabilities"] = {"plan": supported}
        rpc.events = []
        call = rpc.call

        def dispatch(method, params, timeout=15):
            if method == "collaborationMode/list":
                rpc.calls.append((method, params))
                return {"data": [{"mode": "plan"}, {"mode": "default"}]}
            if method != "turn/start":
                return call(method, params, timeout)
            rpc.calls.append((method, params))
            phase = params["collaborationMode"]["mode"]
            turn_id = phase + "-turn"
            terminal = ({"status": plan_status, "plan": "Bounded implementation plan"} if phase == "plan" else
                        {"status": "completed", "resultPath": state["resultPath"], "resultText": "Implemented"})
            rpc.events.extend([
                {"method": "turn/started", "params": {"threadId": "thread-exact", "turn": {"id": turn_id}}},
                {"method": "item/completed", "params": {"threadId": "thread-exact", "turnId": turn_id,
                    "item": {"type": "agentMessage", "text": json.dumps(terminal)}}},
                {"method": "turn/completed", "params": {"threadId": "thread-exact",
                    "turn": {"id": turn_id, "status": "failed" if failure and phase == "plan" else "completed"}}},
            ])
            return {"turn": {"id": turn_id}}

        rpc.call = dispatch
        event = rpc.event

        def next_event():
            result = event()
            if cancel and result["method"] == "turn/completed":
                path = Path(state["statePath"])
                runtime.update_json(path, path.parent / ".state.lock", lambda value: value.update(cancelRequested=True))
            return result

        rpc.event = next_event
        return native.Bridge(runtime, original.session, state, rpc), rpc, state

    def test_plan_then_execution_use_one_thread_and_original_output_contract(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = self.fixture(Path(directory))
            bridge.run("original bounded request and receipt")
            turns = [params for method, params in rpc.calls if method == "turn/start"]
            self.assertEqual([turn["collaborationMode"]["mode"] for turn in turns], ["plan", "default"])
            self.assertEqual([turn["threadId"] for turn in turns], ["thread-exact", "thread-exact"])
            self.assertEqual(sum(method in ("thread/start", "thread/resume") for method, _ in rpc.calls), 1)
            self.assertEqual(turns[0]["collaborationMode"]["settings"], turns[1]["collaborationMode"]["settings"])
            self.assertEqual(turns[1]["outputSchema"], runtime.safe_read_json(Path(state["responseSchemaPath"])))
            self.assertEqual(json.loads((Path(state["statePath"]).parent / "plan.json").read_text())["status"], "planned")
            completed = [json.loads(line) for line in output.getvalue().splitlines() if json.loads(line).get("type") == "item.completed"]
            self.assertEqual(len(completed), 1)
            self.assertEqual(json.loads(completed[0]["item"]["text"])["resultText"], "Implemented")

    def test_fixed_instructions_stay_in_thread_config_across_plan_transition(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, state = self.fixture(Path(directory))
            parts = PromptParts("Fixed Work instructions", "Current request and receipt contract")
            bridge.run(parts)
            resume = next(params for method, params in rpc.calls if method == "thread/resume")
            self.assertIn(parts.fixed, resume["developerInstructions"])
            self.assertIn("Host phase contract", resume["developerInstructions"])
            turns = [params for method, params in rpc.calls if method == "turn/start"]
            self.assertEqual(len(turns), 2)
            for turn in turns:
                text = "\n".join(item.get("text", "") for item in turn["input"])
                self.assertIn(parts.dynamic, text)
                self.assertNotIn(parts.fixed, text)
                self.assertIsNone(turn["collaborationMode"]["settings"]["developer_instructions"])
            self.assertEqual(turns[-1]["outputSchema"], runtime.safe_read_json(Path(state["responseSchemaPath"])))

    def test_unresolved_human_choice_stops_without_implementation(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, _ = self.fixture(Path(directory), plan_status="needs-human-decision")
            bridge.run("bounded request")
            self.assertEqual(sum(method == "turn/start" for method, _ in rpc.calls), 1)
            terminal = json.loads(json.loads(output.getvalue().splitlines()[-1])["item"]["text"])
            self.assertEqual(terminal["status"], "needs-human-decision")

    def test_cancel_or_failed_plan_never_starts_execution(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
                bridge, rpc, _ = self.fixture(Path(directory), cancel=not failure, failure=failure)
                if failure:
                    with self.assertRaises(native.NativeError):
                        bridge.run("bounded request")
                else:
                    bridge.run("bounded request")
                self.assertEqual(sum(method == "turn/start" for method, _ in rpc.calls), 1)

    def test_missing_native_support_does_not_fake_a_plan_turn(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory), supported=False)
            with self.assertRaisesRegex(native.NativeError, "genuine Plan"):
                bridge.run("bounded request")
            self.assertFalse(any(method == "turn/start" for method, _ in rpc.calls))


class PlanWorkTests(TaskModeTests):
    """Exercise the same native transition and stop boundaries without Verification."""

    def fixture(self, root, **kwargs):
        return super().fixture(root, task_mode="plan-work", **kwargs)

    def test_capabilities_gate_both_plan_routes(self):
        for supported in (False, True):
            with self.subTest(supported=supported), tempfile.TemporaryDirectory() as directory:
                capabilities = {"submit": {"plan": supported}, "send": {"plan": supported}}
                with mock.patch.object(native, "inspect_capabilities", return_value=capabilities), mock.patch.object(runtime, "emit") as emit:
                    runtime.main(["capabilities", "--project-root", directory])
                for operation in ("submit", "send"):
                    modes = emit.call_args.args[0][operation]["taskModes"]
                    self.assertIn("work", modes)
                    self.assertIn("work-verification", modes)
                    for mode in ("plan", "plan-work", "plan-work-verification"):
                        self.assertEqual(mode in modes, supported)

    def test_main_guidance_reports_work_checks_without_reverification(self):
        instruction = route_instruction("plan-work", "main")
        self.assertIn("loop.py start --task-mode plan-work", instruction)
        self.assertIn("do not review implementation or rerun checks", instruction)
        self.assertIn("Do not start separate Verification", instruction)
        self.assertEqual(route_instruction("plan-work", "work"), "")


class MessageActionTests(unittest.TestCase):
    def test_plan_only_stops_after_real_plan_and_records_read_only_receipt(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, state = TaskModeTests().fixture(Path(directory), task_mode="plan")
            run_dir = Path(state["statePath"]).parent
            state["receiptPath"] = str(run_dir / "receipt.json")
            state["receiptSchemaPath"] = str(run_dir / "receipt.schema.json")
            runtime.atomic_write_json(Path(state["receiptSchemaPath"]), runtime.receipt_schema_document(
                role="work", run_id=state["runId"], request_hash=state["requestHash"], verified_work_run_id=None))
            bridge.run("Plan only")
            turns = [params for method, params in rpc.calls if method == "turn/start"]
            self.assertEqual([turn["collaborationMode"]["mode"] for turn in turns], ["plan"])
            self.assertEqual(runtime.safe_read_json(Path(state["receiptPath"]))["changedPaths"], [])
            self.assertEqual(runtime.safe_read_json(run_dir / "plan.json")["status"], "planned")

    def test_standalone_receipt_is_request_bound_and_cannot_be_a_loop_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = runtime.create_run(project_root=root, agent_id="verify-target", actor="main",
                request=b"Inspect explicit target src/example.py", session={"role": "verification", "maxAttempts": 1},
                execution_options={"taskMode": "verification"})
            schema = runtime.safe_read_json(Path(state["receiptSchemaPath"]))
            self.assertEqual(schema["properties"]["kind"]["const"], "standalone-verification-receipt")
            self.assertNotIn("verifiedWorkRunId", schema["properties"])
            runtime.atomic_write(Path(state["resultPath"]), b"No findings")
            receipt = {"schemaVersion": "0.1.0", "kind": "standalone-verification-receipt",
                "runId": state["runId"], "requestHash": state["requestHash"], "decision": "pass", "findings": []}
            runtime.atomic_write_json(Path(state["receiptPath"]), receipt)
            runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"])
            with self.assertRaises(runtime.ContractError):
                runtime.validate_receipt(root, {**state, "taskMode": "work-verification", "verifiedWorkRunId": "work-exact"},
                    agent_id=state["agentId"], run_id=state["runId"])
            receipt["requestHash"] = "0" * 64
            runtime.atomic_write_json(Path(state["receiptPath"]), receipt)
            with self.assertRaises(runtime.ContractError):
                runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"])

    def test_standalone_guidance_requires_target_and_managed_verification(self):
        instruction = route_instruction("verification", "main")
        self.assertIn("explicit input first", instruction)
        self.assertIn("prior completed work in this current chat", instruction)
        self.assertIn("ask the Human", instruction)
        self.assertIn("--role verification --task-mode verification", instruction)
