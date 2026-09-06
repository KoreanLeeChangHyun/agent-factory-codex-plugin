"""Focused native transport regressions; intended for independent Verification."""
from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("native_test_exec", Path(__file__).parents[1] / "skills/agent/scripts/exec.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)
native = runtime.native_codex


class FakeRpc:
    def __init__(self, result_path, goal_statuses=("complete",), mismatch=False):
        self.calls = []
        self.goal = None
        self.result_path = result_path
        self.mismatch = mismatch
        self.history = []
        self.events = []
        for index, status in enumerate(goal_statuses):
            turn = f"turn-{index}"
            self.events.extend([
                {"method": "turn/started", "params": {"threadId": "thread-exact", "turn": {"id": turn}}},
                {"method": "item/completed", "params": {"threadId": "thread-exact", "item": {
                    "type": "agentMessage", "text": json.dumps({"status": "completed", "resultPath": result_path})}}},
                {"method": "turn/completed", "params": {"threadId": "thread-exact", "turn": {"id": turn, "status": "completed"}}, "testGoalStatus": status},
            ])

    def restart_owned(self):
        self.calls.append(("owned/restart", {}))

    def write(self, value):
        self.calls.append((value["method"], value.get("params")))

    def call(self, method, params, timeout=15):
        self.calls.append((method, params))
        if method == "initialize":
            return {}
        if method in ("thread/start", "thread/resume"):
            return {"thread": {"id": "thread-wrong" if self.mismatch else "thread-exact"}, "model": "model-one"}
        if method == "model/list":
            return {"data": [{"model": "model-one", "serviceTiers": [{"id": "priority", "name": "Fast"}]}]}
        if method == "thread/goal/get":
            return {"goal": self.goal}
        if method == "thread/goal/set":
            self.goal = {"threadId": "thread-exact", "objective": "finish", "tokensUsed": 19,
                         "timeUsedSeconds": 3, **(self.goal or {}), **params}
            return {"goal": self.goal}
        if method == "thread/goal/clear":
            self.goal = None
            return {}
        if method == "turn/start":
            return {"turn": {"id": "turn-0"}}
        if method == "thread/read":
            return {"thread": {"id": "thread-exact", "turns": self.history or [{"id": "native-turn", "status": "inProgress"}]}}
        if method == "turn/interrupt":
            return {}
        raise AssertionError(method)

    def event(self):
        event = self.events.pop(0)
        if event.get("method") == "turn/completed":
            self.history.append(dict(event["params"]["turn"]))
        if self.goal and "testGoalStatus" in event:
            self.goal = {**self.goal, "status": event["testGoalStatus"]}
        if event.get("method") == "thread/goal/updated":
            self.goal = event["params"]["goal"]
        return event


class NativeCodexTests(unittest.TestCase):
    def fixture(self, root, *, fast=None, goal=True, existing=True, action=None, statuses=("complete",), mismatch=False):
        session = {"role": "main", "maxAttempts": 1, "codex": "codex", "projectRoot": str(root),
                   "sandbox": "read-only", "startTimeout": 20, "goalMode": goal, "fast": fast,
                   "model": "model-one", "reasoningEffort": "high", "sessionId": "thread-exact" if existing else None}
        state = runtime.create_run(project_root=root, agent_id="main-test", actor="human", request=b"finish", session=session)
        runtime.atomic_write_json(runtime.session_file(root, "main-test"), session)
        state["goalObjective"] = "finish" if goal else None
        state["goalAction"] = action
        rpc = FakeRpc(state["resultPath"], statuses, mismatch)
        return native.Bridge(runtime, session, state, rpc), rpc, state

    def test_explicit_false_and_inherit_are_distinct_on_submit_and_send(self):
        for command in ("submit", "send"):
            prefix = [command, "--agent", "main-test", "--message", "hi"]
            if command == "submit":
                prefix += ["--role", "main"]
            self.assertEqual(runtime.requested_execution(runtime.parse_args(prefix)), {})
            self.assertEqual(runtime.requested_execution(runtime.parse_args(prefix + ["--no-fast", "--no-goal-mode"])), {"fast": False, "goalMode": False})
            self.assertEqual(runtime.requested_execution(runtime.parse_args(prefix + ["--fast", "--goal-mode"])), {"fast": True, "goalMode": True})

    def test_fast_uses_advertised_tier_and_off_clears_inherited_tier(self):
        models = [{"model": "m", "serviceTiers": [{"id": "accelerated", "name": "Fast"}]}]
        self.assertEqual(native.service_tier(models, "m", True), "accelerated")
        self.assertEqual(native.service_tier(models, "m", False), "default")
        self.assertIsNone(native.service_tier(models, "m", None))
        with self.assertRaisesRegex(native.NativeError, "does not advertise"):
            native.service_tier([{"model": "m", "serviceTiers": []}], "m", True)

    def test_resume_preserves_exact_identity_and_applies_model_reasoning_and_false(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory), fast=False, goal=False)
            bridge.setup("role and request")
            resume = next(params for method, params in rpc.calls if method == "thread/resume")
            turn = next(params for method, params in rpc.calls if method == "turn/start")
            self.assertEqual(resume["threadId"], "thread-exact")
            self.assertEqual(resume["sandbox"], "read-only")
            self.assertEqual(turn["serviceTier"], "default")
            self.assertEqual(turn["model"], "model-one")
            self.assertEqual(turn["effort"], "high")
            self.assertEqual(resume["developerInstructions"], "role and request")
            self.assertIn("outputSchema", turn)

    def test_wrong_resumed_thread_fails_before_starting_a_turn(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory), mismatch=True)
            with self.assertRaisesRegex(native.NativeError, "different session"):
                bridge.setup("role")
            self.assertFalse(any(method == "turn/start" for method, _ in rpc.calls))

    def test_native_continuation_does_not_complete_goal_on_ordinary_turn_end(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = self.fixture(Path(directory), statuses=("active", "complete"))
            bridge.run("Main role")
            events = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(sum(method == "turn/start" for method, _ in rpc.calls), 0)
            self.assertEqual(sum(e["type"] == "turn.completed" for e in events), 2)
            self.assertEqual(sum(e["type"] == "item.completed" for e in events), 1)
            self.assertIn("goal.continuing", [e["type"] for e in events])
            self.assertEqual(runtime.safe_read_json(Path(state["statePath"]))["goal"]["status"], "complete")

    def test_paused_blocked_and_limited_goals_are_not_run_completion(self):
        for status in ("paused", "blocked", "usageLimited", "budgetLimited"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
                bridge, _, _ = self.fixture(Path(directory), statuses=(status,))
                bridge.run("Main role")
                final = json.loads(json.loads(output.getvalue().splitlines()[-1])["item"]["text"])
                self.assertEqual(final["status"], "needs-human-decision")

    def test_pause_and_clear_are_native_controls_with_no_model_turn(self):
        for action in ("pause", "cancel", "disable"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
                bridge, rpc, _ = self.fixture(Path(directory), action=action)
                rpc.goal = {"threadId": "thread-exact", "objective": "existing", "status": "active", "tokensUsed": 123, "timeUsedSeconds": 2}
                bridge.run("Main role")
                self.assertFalse(any(method == "turn/start" for method, _ in rpc.calls))
                if action == "pause":
                    self.assertEqual(rpc.goal["status"], "paused")
                    self.assertEqual(rpc.goal["tokensUsed"], 123)
                else:
                    self.assertIsNone(rpc.goal)

    def test_explicit_reopen_preserves_objective_and_usage(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, state = self.fixture(Path(directory), action="reopen")
            state.pop("goalObjective")
            rpc.goal = {"threadId": "thread-exact", "objective": "existing", "status": "paused", "tokensUsed": 123, "timeUsedSeconds": 2}
            bridge.setup("Main role")
            self.assertEqual(rpc.goal["status"], "active")
            self.assertEqual(rpc.goal["objective"], "existing")
            self.assertEqual(rpc.goal["tokensUsed"], 123)
            mutation = next(params for method, params in rpc.calls if method == "thread/goal/set")
            self.assertNotIn("objective", mutation)

    def test_native_error_pauses_goal_and_remains_an_error(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory))
            rpc.events = [{"method": "error", "params": {"error": {"message": "quota"}, "willRetry": False}}]
            with self.assertRaisesRegex(native.NativeError, "quota"):
                bridge.run("Main role")
            self.assertEqual(rpc.goal["status"], "paused")

    def test_cancel_request_pauses_before_return(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, state = self.fixture(Path(directory))
            runtime.update_json(Path(state["statePath"]), Path(state["statePath"]).parent / ".state.lock", lambda value: value.update({"cancelRequested": True}))
            bridge.run("Main role")
            self.assertEqual(rpc.goal["status"], "paused")
            self.assertTrue(any(method == "turn/interrupt" for method, _ in rpc.calls))

    def test_off_clears_existing_native_goal_before_the_next_turn(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = self.fixture(Path(directory), goal=False)
            rpc.goal = {"threadId": "thread-exact", "objective": "existing", "status": "active", "tokensUsed": 10, "timeUsedSeconds": 1}
            bridge.setup("ordinary request")
            self.assertIsNone(rpc.goal)
            methods = [method for method, _ in rpc.calls]
            self.assertLess(methods.index("thread/goal/clear"), methods.index("turn/start"))

    def test_inheriting_paused_goal_does_not_reopen_it(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, state = self.fixture(Path(directory))
            state.pop("goalObjective")
            rpc.goal = {"threadId": "thread-exact", "objective": "existing", "status": "paused", "tokensUsed": 10, "timeUsedSeconds": 1}
            bridge.setup("ordinary follow-up")
            self.assertEqual(rpc.goal["status"], "paused")
            self.assertFalse(any(method == "thread/goal/set" for method, _ in rpc.calls))

    def test_live_pause_uses_rpc_owner_and_acknowledges_control(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, state = self.fixture(Path(directory))
            path = Path(state["statePath"])
            runtime.update_json(path, path.parent / ".state.lock", lambda value: value.update({"goalControl": {"id": "human-one", "action": "pause"}}))
            bridge.run("Main role")
            self.assertEqual(rpc.goal["status"], "paused")
            self.assertIn('"controlId": "human-one"', output.getvalue())
            self.assertTrue(any(method == "turn/interrupt" for method, _ in rpc.calls))

    def test_terminal_goal_notification_after_turn_end_finishes_without_an_extra_turn(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            bridge, rpc, _ = self.fixture(Path(directory), statuses=("active",))
            rpc.events.append({"method": "thread/goal/updated", "params": {"threadId": "thread-exact", "goal": {
                "threadId": "thread-exact", "objective": "finish", "status": "complete", "tokensUsed": 23, "timeUsedSeconds": 3}}})
            bridge.run("Main role")
            self.assertEqual(sum(method == "turn/start" for method, _ in rpc.calls), 0)
            self.assertEqual(json.loads(output.getvalue().splitlines()[-1])["type"], "item.completed")

    def test_goal_rejected_for_work_before_process_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            args = runtime.parse_args(["submit", "--project-root", directory, "--agent", "work-test", "--role", "work", "--message", "hi", "--goal-mode"])
            with mock.patch.object(runtime, "resolve_project_root", return_value=Path(directory)), mock.patch.object(runtime, "spawn_worker") as spawn:
                with self.assertRaisesRegex(runtime.ContractError, "Main-only"):
                    runtime.submit(args, True)
                spawn.assert_not_called()

    def test_failed_capability_inspection_is_actionable_not_wrapper_flag_detection(self):
        with mock.patch.object(native.subprocess, "run", side_effect=FileNotFoundError("codex missing")):
            capabilities = native.inspect_capabilities("missing")
        self.assertFalse(capabilities["submit"]["fast"])
        self.assertFalse(capabilities["send"]["goal"])
        self.assertIn("Update/select Codex", capabilities["diagnostic"])

    def test_dispatch_receipt_identity_includes_explicit_execution_options(self):
        with tempfile.TemporaryDirectory() as directory:
            state = runtime.create_run(project_root=Path(directory), agent_id="work-one", actor="main", request=b"hi",
                session={"role": "work", "maxAttempts": 1}, dispatch_id="dispatch-options", dispatch_operation="submit",
                execution_options={"fast": False, "model": "m", "reasoningEffort": "high"})
            self.assertEqual(state["dispatchTuple"]["executionOptions"], {"fast": False, "model": "m", "reasoningEffort": "high"})
            self.assertEqual(state["executionOptions"], state["dispatchTuple"]["executionOptions"])


if __name__ == "__main__":
    unittest.main()
