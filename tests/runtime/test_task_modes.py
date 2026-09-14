"""Bounded route and native Plan transitions for independent Verification."""
import runtime_test_home
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from native_fixtures import native, runtime, native_fixture
from task_modes import route_instruction


class TaskModeTests(unittest.TestCase):
    def test_new_main_default_and_explicit_dispatch_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = {"role": "main", "maxAttempts": 1}
            default = runtime.create_run(project_root=root, agent_id="main-default", actor="human", request=b"task", session=session)
            self.assertEqual(default["taskMode"], "work")
            for mode in ("direct", "work", "work-verification", "plan-work-verification"):
                state = runtime.create_run(project_root=root, agent_id="main-selected", actor="human", request=b"task", session=session,
                                           execution_options={"taskMode": mode}, dispatch_id="dispatch-" + mode, dispatch_operation="send")
                self.assertEqual(state["taskMode"], mode)
                self.assertEqual(state["dispatchTuple"]["executionOptions"], {"taskMode": mode})
                self.assertIn(mode, route_instruction(mode, "main"))
            with self.assertRaises(runtime.ContractError):
                route_instruction("pretend-plan", "main")

    def fixture(self, root, *, plan_status="planned", cancel=False, failure=False, supported=True):
        original, rpc, state = native_fixture(root, goal=False)
        state["role"] = "work"
        state["executionOptions"] = {"taskMode": "plan-work-verification"}
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
