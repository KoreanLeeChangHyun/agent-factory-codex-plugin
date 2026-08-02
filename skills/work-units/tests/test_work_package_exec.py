from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
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
            "integrationBranch": "work-package/pkg",
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

    def test_independent_nodes_run_in_parallel_and_dependent_runs_after_merges(self):
        lock = threading.Lock()
        running = 0
        peak = 0
        finished = set()
        merged = []
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
        self.assertEqual(
            bases,
            {
                "a": "work-package/pkg",
                "b": "work-package/pkg",
                "c": "work-package/pkg",
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

    def test_merge_conflict_enters_recovering_and_launches_resolution(self):
        merges = 0
        resolutions = []
        events = []

        def merge_node(_node, _result):
            nonlocal merges
            merges += 1
            if merges == 1:
                raise RuntimeError("merge conflict")
            return {"result": "merged"}

        definition = {
            "maxParallel": 1,
            "integrationBranch": "work-package/pkg",
            "nodes": [
                {
                    "id": "a",
                    "workUnitId": "wu-a",
                    "prerequisites": [],
                    "executionMode": "worktree",
                }
            ],
        }
        scheduler = self.module.DeterministicScheduler(
            package_id="pkg",
            revision=1,
            definition=definition,
            durable_state={"nodes": {}},
            run_node=lambda *_: {},
            merge_node=merge_node,
            resolve_node=lambda node, error, key: resolutions.append(
                (node["id"], str(error), key)
            ),
            emit=events.append,
        )
        state = scheduler.run()
        self.assertEqual(merges, 2)
        self.assertEqual(resolutions, [("a", "merge conflict", "pkg:1:a")])
        self.assertEqual(state["nodes"]["a"]["state"], "completed")
        self.assertTrue(
            any(event.get("state") == "recovering" for event in events)
        )

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

    def test_scheduler_prepares_member_from_package_integration_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(
                ["git", "init", "-q", "-b", "main", str(repository)], check=True
            )
            subprocess.run(
                ["git", "-C", str(repository), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "config",
                    "user.email",
                    "test@example.invalid",
                ],
                check=True,
            )
            (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
            (repository / ".agent-factory").mkdir()
            (repository / ".agent-factory" / "canonical.txt").write_text(
                "control\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "."], check=True
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-q", "-m", "base"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "branch", "factory"], check=True
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "branch",
                    "work-package/pkg",
                    "factory",
                ],
                check=True,
            )
            package_commit = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "commit-tree",
                    "factory^{tree}",
                    "-p",
                    "factory",
                    "-m",
                    "package aggregate",
                ],
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "branch",
                    "-f",
                    "work-package/pkg",
                    package_commit,
                ],
                check=True,
            )
            runtime = self.module.PackageRuntime(
                repository=repository,
                package_id="pkg",
                definition={
                    "targetBranch": "factory",
                    "integrationBranch": "work-package/pkg",
                },
            )

            context = runtime.prepare_member_worktree("wu-a")
            member = repository / ".agent-factory" / "worktree" / "wu-a"

            self.assertEqual(context["baseRef"], "work-package/pkg")
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(member), "rev-parse", "HEAD"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                package_commit,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(member), "branch", "--show-current"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                "work-unit/wu-a",
            )
            self.assertFalse((member / ".agent-factory").exists())


if __name__ == "__main__":
    unittest.main()
