from __future__ import annotations

import importlib.util
import sys
import threading
import time
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "work-units"
    / "scripts"
    / "work_package_exec.py"
)


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
                    "executionMode": selected.get("a", "workspace-direct"),
                },
                {
                    "id": "b",
                    "workUnitId": "wu-b",
                    "prerequisites": [],
                    "executionMode": selected.get("b", "workspace-direct"),
                },
                {
                    "id": "c",
                    "workUnitId": "wu-c",
                    "prerequisites": ["a", "b"],
                    "executionMode": selected.get("c", "workspace-direct"),
                },
            ],
        }

    def test_json_command_uses_final_document_after_work_unit_ack(self):
        acknowledgement = {
            "type": "ack",
            "workUnitId": "wu-a",
        }
        terminal = {
            "command": "execute",
            "ok": True,
            "state": "complete",
        }
        script = (
            "import json;"
            f"print(json.dumps({acknowledgement!r}));"
            f"print(json.dumps({terminal!r}))"
        )

        result = self.module.run_json_command(
            [sys.executable, "-c", script],
            "launch Work Unit wu-a",
        )

        self.assertEqual(result, terminal)

    def test_member_review_failure_cannot_enter_package_review(self):
        failed = {
            "context": {
                "stages": {
                    "review": {
                        "aiReviewResult": {
                            "result": "fail",
                            "checklistResult": "fail",
                        }
                    }
                }
            }
        }

        with self.assertRaisesRegex(
            self.module.ExecutionError, "AI review did not pass"
        ):
            self.module.member_review_result(failed)

    def test_package_review_evidence_is_derived_from_member_reviews(self):
        review = {"result": "pass", "checklistResult": "pass"}
        state = {
            "nodes": {
                "a": {
                    "result": {
                        "context": {
                            "stages": {
                                "review": {"aiReviewResult": review}
                            }
                        }
                    }
                }
            }
        }

        evidence = self.module.package_review_evidence(state)

        self.assertEqual(evidence["result"], "pass")
        self.assertEqual(evidence["checklistResult"], "pass")
        self.assertEqual(evidence["memberReviews"], {"a": review})

    def test_workspace_nodes_are_serial_and_prerequisites_run_first(self):
        lock = threading.Lock()
        running = 0
        peak = 0
        finished = []
        bases = {}

        def run_node(node, base, _key):
            nonlocal running, peak
            bases[node["id"]] = base
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.03)
            with lock:
                running -= 1
                finished.append(node["id"])
            return {"result": "success"}

        events = []
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=self.definition(),
            durable_state={"nodes": {}},
            run_node=run_node,
            resolve_node=lambda *_: None,
            emit=events.append,
        )
        state = scheduler.run()
        self.assertEqual(peak, 1)
        self.assertEqual(finished, ["a", "b", "c"])
        self.assertEqual(tuple(state["completedOrder"]), ("a", "b", "c"))
        self.assertEqual(
            bases,
            {
                "a": None,
                "b": None,
                "c": None,
            },
        )
        self.assertTrue(any(event["type"] == "heartbeat" for event in events))

    def test_resume_does_not_repeat_completed_nodes(self):
        launched = []
        state = {
            "nodes": {
                "a": {"state": "completed", "idempotencyKey": "pkg:1:a"},
                "b": {"state": "completed", "idempotencyKey": "pkg:1:b"},
            },
            "completedOrder": ["a", "b"],
        }
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=self.definition(),
            durable_state=state,
            run_node=lambda node, *_: launched.append(node["id"]) or {},
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
                    "executionMode": "workspace-direct",
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

    def test_default_node_recovery_budget_is_finite(self):
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition={
                "maxParallel": 1,
                "nodes": [
                    {
                        "id": "a",
                        "workUnitId": "wu-a",
                        "prerequisites": [],
                        "executionMode": "workspace-direct",
                    }
                ],
            },
            durable_state={"nodes": {}},
            run_node=lambda *_: (_ for _ in ()).throw(RuntimeError("permanent")),
            resolve_node=lambda *_: None,
            emit=lambda *_: None,
        )

        with self.assertRaisesRegex(
            self.module.ExecutionError, "recovery budget exhausted"
        ):
            scheduler.run()

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
            resolve_node=lambda *_: None,
            emit=lambda *_: None,
        )
        scheduler.run()
        self.assertEqual(peak, 1)

if __name__ == "__main__":
    unittest.main()
