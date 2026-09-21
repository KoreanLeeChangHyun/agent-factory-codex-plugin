"""Work Goal lifecycle and receipts, isolated from real providers and runtime data."""
import runtime_test_home
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from native_fixtures import FakeRpc, native, native_fixture, runtime
from task_modes import work_goal_options


class WorkGoalTests(unittest.TestCase):
    def fixture(self, root, *, statuses=("active", "complete"), mode="work"):
        original, rpc, state = native_fixture(root, statuses=statuses)
        original.session["role"] = state["role"] = "work"
        state["executionOptions"] = {"taskMode": mode, "goalMode": True}
        original.session["nativeCapabilities"] = {"goal": True, "plan": True}
        return native.Bridge(runtime, original.session, state, rpc), rpc, state

    def test_delegated_main_goal_is_rejected_before_it_can_duplicate_work_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = runtime.parse_args(["submit", "--project-root", directory, "--agent", "main-delegating",
                                       "--role", "main", "--task-mode", "work", "--goal-mode", "--message", "bounded work"])
            with mock.patch.object(runtime, "spawn_worker") as spawn:
                with self.assertRaisesRegex(runtime.ContractError, "Main Goal is direct-only"):
                    runtime.submit(args, True)
                spawn.assert_not_called()

    def test_goal_owns_multiple_turns_without_wrapper_reexecution(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, _ = self.fixture(Path(directory))
            bridge.run("bounded work and receipt contract")
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(sum(event["type"] == "turn.completed" for event in events), 2)
            self.assertEqual(sum(event["type"] == "item.completed" for event in events), 1)
            self.assertFalse(any(method == "turn/start" for method, _ in rpc.calls))
            self.assertEqual(json.loads(events[-1]["item"]["text"])["status"], "completed")
            self.assertEqual(bridge.thread_id, "thread-exact")

    def test_goal_limits_input_and_failure_remain_distinct(self):
        for status, expected in [("blocked", "needs-human-decision"), ("paused", "needs-human-decision"),
                                 ("budgetLimited", "failed"), ("usageLimited", "failed")]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
                bridge, _, _ = self.fixture(Path(directory), statuses=(status,))
                bridge.run("bounded work")
                terminal = json.loads(json.loads(output.getvalue().splitlines()[-1])["item"]["text"])
                self.assertEqual(terminal["status"], expected)
                self.assertIn(status, terminal["resultText"])
                self.assertEqual(terminal["decisionKind"], "clarification" if expected == "needs-human-decision" else None)

    def test_reported_failure_is_not_reclassified_as_human_input(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, _ = self.fixture(Path(directory), statuses=("blocked",))
            item = rpc.events[1]["params"]["item"]
            terminal = json.loads(item["text"])
            terminal["status"] = "failed"
            item["text"] = json.dumps(terminal)
            bridge.run("bounded work")
            self.assertEqual(json.loads(json.loads(output.getvalue().splitlines()[-1])["item"]["text"])["status"], "failed")

    def test_unsupported_goal_fails_without_a_model_turn_or_fallback(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory))
            bridge.goal_supported = False
            with self.assertRaisesRegex(native.NativeError, "lacks Goal APIs"):
                bridge.run("bounded work")
            self.assertFalse(any(method in {"turn/start", "thread/goal/set"} for method, _ in rpc.calls))

    def test_cancel_pauses_work_goal_without_completion(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = self.fixture(Path(directory))
            path = Path(state["statePath"])
            runtime.update_json(path, path.parent / ".state.lock", lambda value: value.update(cancelRequested=True))
            bridge.run("bounded work")
            self.assertEqual(rpc.goal["status"], "paused")
            self.assertNotIn('"type": "item.completed"', output.getvalue())

    def test_work_request_and_revision_get_their_own_objective_without_invented_budget(self):
        for text in ("Initial bounded work", "Fix finding F1", "long request " * 1000):
            options = work_goal_options({"taskMode": "work", "model": "chosen"}, text)
            self.assertTrue(options["goalMode"])
            self.assertEqual(options["model"], "chosen")
            self.assertLessEqual(len(options["goalObjective"]), 4000)
            self.assertNotIn("tokenBudget", options)
        self.assertEqual(work_goal_options({"taskMode": "plan"}, "Plan"), {"taskMode": "plan", "goalMode": False})
        with self.assertRaises(runtime.ContractError):
            work_goal_options({"taskMode": "work", "goalMode": False}, "Work")

    def plan_fixture(self, root, *, cancel_default=False, fail_default=False):
        bridge, rpc, state = self.fixture(root, statuses=(), mode="plan-work")
        call = rpc.call

        def dispatch(method, params, timeout=15):
            if method == "collaborationMode/list":
                rpc.calls.append((method, params))
                return {"data": [{"mode": "plan"}, {"mode": "default"}]}
            if method == "turn/start":
                rpc.calls.append((method, params))
                phase = params["collaborationMode"]["mode"]
                turn_id = phase + "-turn"
                result = {"status": "planned", "plan": "Bounded plan"} if phase == "plan" else {"status": "ready"}
                rpc.events.extend([
                    {"method": "turn/started", "params": {"threadId": "thread-exact", "turn": {"id": turn_id}}},
                    {"method": "item/completed", "params": {"threadId": "thread-exact", "turnId": turn_id,
                        "item": {"type": "agentMessage", "text": json.dumps(result)}}},
                    {"method": "turn/completed", "params": {"threadId": "thread-exact", "turn": {
                        "id": turn_id, "status": "failed" if fail_default and phase == "default" else "completed"}}},
                ])
                return {"turn": {"id": turn_id}}
            result = call(method, params, timeout)
            if method == "thread/goal/set" and params.get("status") == "active":
                rpc.events.extend(FakeRpc(state["resultPath"]).events)
            return result

        rpc.call = dispatch
        event = rpc.event

        def next_event():
            value = event()
            if cancel_default and value.get("method") == "turn/completed" and value["params"]["turn"]["id"] == "default-turn":
                path = Path(state["statePath"])
                runtime.update_json(path, path.parent / ".state.lock", lambda data: data.update(cancelRequested=True))
            return value

        rpc.event = next_event
        return bridge, rpc, state

    def test_plan_default_transition_precedes_goal_in_same_thread(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = self.plan_fixture(Path(directory))
            bridge.run("full bounded request and receipt")
            turns = [params for method, params in rpc.calls if method == "turn/start"]
            self.assertEqual([turn["collaborationMode"]["mode"] for turn in turns], ["plan", "default"])
            self.assertTrue(all(turn["threadId"] == "thread-exact" for turn in turns))
            self.assertEqual(turns[-1]["outputSchema"]["properties"]["status"], {"const": "ready"})
            active_index = next(i for i, (method, params) in enumerate(rpc.calls)
                                if method == "thread/goal/set" and params.get("status") == "active")
            self.assertTrue(all(i < active_index for i, (method, _) in enumerate(rpc.calls) if method == "turn/start"))
            resumes = [params for method, params in rpc.calls if method == "thread/resume"]
            self.assertIn("full bounded request and receipt", resumes[-1]["developerInstructions"])
            self.assertIn(state["resultPath"], resumes[-1]["developerInstructions"])
            terminal = json.loads(json.loads(output.getvalue().splitlines()[-1])["item"]["text"])
            self.assertEqual(terminal["resultText"], "Native answer")

    def test_cancel_or_failed_default_transition_never_activates_goal(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
                bridge, rpc, _ = self.plan_fixture(Path(directory), cancel_default=not failure, fail_default=failure)
                if failure:
                    with self.assertRaises(native.NativeError):
                        bridge.run("bounded work")
                else:
                    bridge.run("bounded work")
                self.assertFalse(any(method == "thread/goal/set" and params.get("status") == "active" for method, params in rpc.calls))

    def test_new_receipts_record_own_checks_but_historical_authority_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = runtime.create_run(project_root=root, agent_id="work-receipt", actor="main", request=b"work",
                                       session={"role": "work", "maxAttempts": 1})
            runtime.atomic_write(Path(state["resultPath"]), b"Own checks recorded; independent verification not requested")
            receipt = {"schemaVersion": "0.1.0", "kind": "work-receipt", "runId": state["runId"],
                       "requestHash": state["requestHash"], "outcome": "completed", "changedPaths": [],
                       "addressedFindingIds": [], "tests": {"run": True, "reason": "Focused local check: 2 passed"}}
            runtime.atomic_write_json(Path(state["receiptPath"]), receipt)
            self.assertEqual(runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"]), receipt)
            schema = runtime.safe_read_json(Path(state["receiptSchemaPath"]))
            schema["properties"]["tests"]["properties"] = {"run": {"const": False}, "reason": {"const": "work-agent-prohibited"}}
            runtime.atomic_write_json(Path(state["receiptSchemaPath"]), schema)
            with self.assertRaisesRegex(runtime.ContractError, "Historical Work"):
                runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"])

    def test_historical_receipt_reason_literal_is_diagnosed_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = runtime.create_run(project_root=root, agent_id="work-literal", actor="main", request=b"work",
                                       session={"role": "work", "maxAttempts": 1})
            runtime.atomic_write(Path(state["resultPath"]), b"Work result")
            schema_path = Path(state["receiptSchemaPath"])
            schema = runtime.safe_read_json(schema_path)
            schema["properties"]["tests"]["properties"] = {
                "run": {"const": False}, "reason": {"const": "work-agent-prohibited"}}
            runtime.atomic_write_json(schema_path, schema)
            receipt = {"schemaVersion": "0.1.0", "kind": "work-receipt", "runId": state["runId"],
                       "requestHash": state["requestHash"], "outcome": "completed", "changedPaths": [],
                       "addressedFindingIds": [], "tests": {"run": False, "reason": "Checks reserved for Verification."}}
            path = Path(state["receiptPath"])
            runtime.atomic_write_json(path, receipt)
            before = path.read_bytes()
            with self.assertRaisesRegex(runtime.ContractError, 'tests.reason.*work-agent-prohibited') as raised:
                runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"])
            self.assertEqual(raised.exception.code, "receipt_tests_invalid")
            self.assertEqual(path.read_bytes(), before)
            receipt["tests"]["reason"] = "work-agent-prohibited"
            runtime.atomic_write_json(path, receipt)
            self.assertEqual(runtime.validate_receipt(root, state, agent_id=state["agentId"], run_id=state["runId"]), receipt)
