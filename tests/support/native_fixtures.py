"""Shared fake RPC and native bridge setup."""
import runtime_test_home
import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("native_test_exec", Path(__file__).parents[2] / "skills/agent/scripts/exec.py")
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


def native_fixture(root, *, fast=None, goal=True, existing=True, action=None, statuses=("complete",), mismatch=False):
    session = {"role": "main", "maxAttempts": 1, "codex": "codex", "projectRoot": str(root),
               "sandbox": "read-only", "executionPolicy": runtime_test_home.policy("read-only"), "startTimeout": 20, "goalMode": goal, "fast": fast,
               "model": "model-one", "reasoningEffort": "high", "sessionId": "thread-exact" if existing else None}
    state = runtime.create_run(project_root=root, agent_id="main-test", actor="human", request=b"finish", session=session)
    runtime.atomic_write_json(runtime.session_file(root, "main-test"), session)
    state["goalObjective"] = "finish" if goal else None
    state["goalAction"] = action
    rpc = FakeRpc(state["resultPath"], statuses, mismatch)
    return native.Bridge(runtime, session, state, rpc), rpc, state
