from __future__ import annotations

import importlib.util
import sys
import threading
import time
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "work_package_exec.py"


def load_module():
    spec = importlib.util.spec_from_file_location("work_package_exec", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Package executor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkPackageSchedulerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def definition(self, *, modes=None):
        selected = modes or {}
        return {
            "maxParallel": 2,
            "nodes": [
                {
                    "id": "a",
                    "workUnitId": "wu-a",
                    "prerequisites": [],
                    "executionMode": selected.get("a", "worktree"),
                },
                {
                    "id": "b",
                    "workUnitId": "wu-b",
                    "prerequisites": [],
                    "executionMode": selected.get("b", "worktree"),
                },
                {
                    "id": "c",
                    "workUnitId": "wu-c",
                    "prerequisites": ["a", "b"],
                    "executionMode": selected.get("c", "worktree"),
                },
            ],
        }

    def test_independent_nodes_run_in_parallel_and_dependent_runs_after_merges(self):
        lock = threading.Lock()
        running = 0
        peak = 0
        finished = set()
        merged = []

        def run_node(node, _base, _key):
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.03)
            with lock:
                running -= 1
                finished.add(node["id"])
            return {"result": "success"}

        def merge_node(node, _result):
            self.assertTrue(set(node["prerequisites"]) <= set(merged))
            merged.append(node["id"])
            return {"result": "merged"}

        events = []
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=self.definition(),
            durable_state={"nodes": {}},
            run_node=run_node,
            merge_node=merge_node,
            resolve_node=lambda *_: None,
            emit=events.append,
        )
        state = scheduler.run()
        self.assertEqual(peak, 2)
        self.assertEqual(merged, ["a", "b", "c"])
        self.assertEqual(tuple(state["completedOrder"]), ("a", "b", "c"))
        self.assertTrue(any(event["type"] == "heartbeat" for event in events))

    def test_resume_does_not_repeat_completed_nodes(self):
        launched = []
        state = {
            "nodes": {
                "a": {"state": "completed", "idempotencyKey": "pkg:1:a"},
                "b": {"state": "completed", "idempotencyKey": "pkg:1:b"},
            },
            "completedOrder": ["a", "b"],
            "mergedOrder": ["a", "b"],
        }
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=self.definition(),
            durable_state=state,
            run_node=lambda node, *_: launched.append(node["id"]) or {},
            merge_node=lambda *_: {},
            resolve_node=lambda *_: None,
            emit=lambda *_: None,
        )
        scheduler.run()
        self.assertEqual(launched, ["c"])

    def test_node_error_enters_recovering_and_retries_with_same_key(self):
        attempts = []
        resolutions = []

        def run_node(node, _base, key):
            attempts.append((node["id"], key))
            if len(attempts) == 1:
                raise RuntimeError("transient")
            return {}

        definition = {
            "maxParallel": 1,
            "nodes": [
                {
                    "id": "a",
                    "workUnitId": "wu-a",
                    "prerequisites": [],
                    "executionMode": "worktree",
                }
            ],
        }
        events = []
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=definition,
            durable_state={"nodes": {}},
            run_node=run_node,
            merge_node=lambda *_: {},
            resolve_node=lambda node, error, key: resolutions.append(
                (node["id"], str(error), key)
            ),
            emit=events.append,
            max_recovery_attempts=2,
        )
        scheduler.run()
        self.assertEqual(len(resolutions), 1)
        self.assertEqual(attempts[0][1], attempts[1][1])
        self.assertIn("recovering", [event.get("state") for event in events])

    def test_specification_direct_nodes_are_serialized(self):
        running = 0
        peak = 0
        lock = threading.Lock()

        def run_node(_node, _base, _key):
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.02)
            with lock:
                running -= 1
            return {}

        definition = {
            "maxParallel": 2,
            "nodes": [
                {
                    "id": "a",
                    "workUnitId": "wu-a",
                    "prerequisites": [],
                    "executionMode": "specification-direct",
                },
                {
                    "id": "b",
                    "workUnitId": "wu-b",
                    "prerequisites": [],
                    "executionMode": "specification-direct",
                },
            ],
        }
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=definition,
            durable_state={"nodes": {}},
            run_node=run_node,
            merge_node=lambda *_: {},
            resolve_node=lambda *_: None,
            emit=lambda *_: None,
        )
        scheduler.run()
        self.assertEqual(peak, 1)


if __name__ == "__main__":
    unittest.main()
