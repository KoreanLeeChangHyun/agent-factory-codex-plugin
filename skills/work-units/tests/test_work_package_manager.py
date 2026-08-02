from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "work_package.py"
WORK_UNIT_TEST = Path(__file__).with_name("test_work_unit_manager.py")


def load_module():
    spec = importlib.util.spec_from_file_location("work_package_manager", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Package manager")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_work_unit_helpers():
    spec = importlib.util.spec_from_file_location("work_unit_test_helpers", WORK_UNIT_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Unit test helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_cli(*arguments: str, check: bool = True):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def data_args(value):
    arguments = []

    def add(path, current):
        if isinstance(current, dict):
            if not current:
                arguments.extend(("--empty-object", path))
            for key, child in current.items():
                add(f"{path}/{str(key).replace('~', '~0').replace('/', '~1')}", child)
        elif isinstance(current, list):
            if not current:
                arguments.extend(("--empty-list", path))
            for index, child in enumerate(current):
                add(f"{path}/{index}", child)
        elif isinstance(current, bool):
            arguments.extend(("--boolean", path, str(current).lower()))
        elif isinstance(current, int):
            arguments.extend(("--integer", path, str(current)))
        elif current is None:
            arguments.extend(("--null", path))
        else:
            arguments.extend(("--string", path, str(current)))

    for key, child in value.items():
        add(f"/{key}", child)
    return arguments


class WorkPackageGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def nodes(self):
        return [
            {
                "id": "b",
                "workUnitId": "wu-b",
                "prerequisites": [],
                "executionMode": "worktree",
            },
            {
                "id": "a",
                "workUnitId": "wu-a",
                "prerequisites": [],
                "executionMode": "worktree",
            },
            {
                "id": "c",
                "workUnitId": "wu-c",
                "prerequisites": ["a", "b"],
                "executionMode": "worktree",
            },
        ]

    def test_topological_order_and_ready_nodes_are_stable(self) -> None:
        graph = self.module.validate_graph(self.nodes())
        self.assertEqual(graph.order, ("a", "b", "c"))
        self.assertEqual(graph.initial_ready, ("a", "b"))

    def test_cycle_self_dependency_and_missing_reference_are_rejected(self) -> None:
        cases = [
            [
                {"id": "a", "workUnitId": "wu-a", "prerequisites": ["b"]},
                {"id": "b", "workUnitId": "wu-b", "prerequisites": ["a"]},
            ],
            [{"id": "a", "workUnitId": "wu-a", "prerequisites": ["a"]}],
            [{"id": "a", "workUnitId": "wu-a", "prerequisites": ["missing"]}],
        ]
        for nodes in cases:
            with self.subTest(nodes=nodes), self.assertRaises(
                self.module.ManagerError
            ):
                self.module.validate_graph(nodes)

    def test_positive_parallelism_and_distinct_branches_are_required(self) -> None:
        definition = {
            "nodes": self.nodes(),
            "maxParallel": 0,
            "repository": "/repo",
            "targetBranch": "main",
            "integrationBranch": "main",
            "executionPolicy": {"retryBackoffSeconds": [0], "leaseSeconds": 30},
        }
        with self.assertRaises(self.module.ManagerError):
            self.module.validate_definition(definition)
        definition["maxParallel"] = 2
        with self.assertRaises(self.module.ManagerError):
            self.module.validate_definition(definition)

    def test_rework_selects_affected_nodes_and_descendants_only(self) -> None:
        affected = self.module.affected_descendants(self.nodes(), {"a"})
        self.assertEqual(affected, ("a", "c"))


class WorkPackageManagerCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.helpers = load_work_unit_helpers()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Agent Factory Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "config",
                "user.email",
                "agent-factory@example.invalid",
            ],
            check=True,
        )
        (self.root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.root), "add", "tracked.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-q", "-m", "baseline"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "branch", "factory"], check=True
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def create_package(self, work_unit_id="missing-unit"):
        package = self.root / ".agent-factory" / "work-packages" / "pkg"
        run_cli(
            "create",
            str(package),
            "--id",
            "pkg",
            "--title",
            "Package",
            "--project-id",
            "sample",
            "--theme",
            "default",
        )
        definition = {
            "id": "PACKAGE-DEFINITION-001",
            "kind": "package-definition",
            "content": {
                "nodes": [
                    {
                        "id": "a",
                        "workUnitId": work_unit_id,
                        "prerequisites": [],
                        "executionMode": "worktree",
                    }
                ],
                "maxParallel": 1,
                "repository": str(self.root),
                "targetBranch": "main",
                "integrationBranch": "work-package/pkg",
                "executionPolicy": {
                    "leaseSeconds": 30,
                    "retryBackoffSeconds": [0],
                },
            },
        }
        placeholders = {
            "definition": definition,
            "ai-review": {
                "id": "AI-REVIEW-STATUS",
                "kind": "ai-review-result",
                "content": "pending",
            },
            "human-review": {
                "id": "HUMAN-REVIEW-STATUS",
                "kind": "human-review-result",
                "content": "pending",
            },
            "report": {
                "id": "REPORT-STATUS",
                "kind": "report-result",
                "content": "pending",
            },
        }
        for section, item in placeholders.items():
            run_cli(
                "section-item-put",
                str(package),
                section,
                *data_args(item),
            )
        run_cli("transition", str(package), "ready")
        return package

    def test_preflight_refusal_is_before_ack_and_non_mutating(self) -> None:
        package = self.create_package()
        before = json.loads(run_cli("show", str(package)).stdout)
        result = run_cli(
            "preflight",
            str(package),
            "--repository",
            str(self.root),
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('"type":"ack"', result.stdout)
        after = json.loads(run_cli("show", str(package)).stdout)
        self.assertEqual(
            before["metadata"]["lifecycle"]["status"],
            after["metadata"]["lifecycle"]["status"],
        )
        self.assertFalse(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "show-ref",
                    "--verify",
                    "--quiet",
                    "refs/heads/work-package/pkg",
                ],
                check=False,
            ).returncode
            == 0
        )

    def test_execution_start_returns_ack_contract(self) -> None:
        intake = self.helpers.create_ready_intake(self.root)
        work_unit = self.helpers.create_package(self.root, "wu-a")
        self.helpers.populate_ready_candidate(self.root, work_unit, intake)
        self.helpers.run_cli("transition", str(work_unit), "ready")
        package = self.create_package("wu-a")
        mismatch = run_cli(
            "preflight",
            str(package),
            "--repository",
            str(self.root.parent),
            check=False,
        )
        self.assertNotEqual(mismatch.returncode, 0)

        self.helpers.run_cli("transition", str(work_unit), "backlog")
        unready = run_cli(
            "preflight",
            str(package),
            "--repository",
            str(self.root),
            check=False,
        )
        self.assertNotEqual(unready.returncode, 0)
        self.assertIn("not ready", unready.stderr)
        self.helpers.run_cli("transition", str(work_unit), "ready")

        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "branch",
                "work-unit/wu-a",
            ],
            check=True,
        )
        collision = run_cli(
            "preflight",
            str(package),
            "--repository",
            str(self.root),
            check=False,
        )
        self.assertNotEqual(collision.returncode, 0)
        self.assertIn("collision", collision.stderr)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "branch",
                "-D",
                "work-unit/wu-a",
            ],
            check=True,
            stdout=subprocess.PIPE,
        )
        shown = json.loads(run_cli("show", str(package)).stdout)
        self.assertEqual(shown["metadata"]["lifecycle"]["status"], "ready")
        self.assertNotEqual(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.root),
                    "show-ref",
                    "--verify",
                    "--quiet",
                    "refs/heads/work-package/pkg",
                ],
                check=False,
            ).returncode,
            0,
        )
        payload = json.loads(
            run_cli(
                "execution-start",
                str(package),
                "--repository",
                str(self.root),
                "--invocation-id",
                "invocation-1",
            ).stdout
        )
        self.assertEqual(payload["packageId"], "pkg")
        self.assertEqual(payload["invocationId"], "invocation-1")
        self.assertEqual(payload["initialReadyNodes"], ["a"])
        self.assertEqual(payload["schedulerState"], "working")
        refused = run_cli(
            "execution-start",
            str(package),
            "--repository",
            str(self.root),
            "--invocation-id",
            "invocation-2",
            check=False,
        )
        self.assertNotEqual(refused.returncode, 0)
        resumed = json.loads(
            run_cli(
                "execution-start",
                str(package),
                "--repository",
                str(self.root),
                "--invocation-id",
                "invocation-2",
                "--resume-owner",
                "invocation-1",
            ).stdout
        )
        self.assertTrue(resumed["resume"])
        execution = json.loads(
            run_cli("show", str(package), "--section", "execution").stdout
        )
        state = next(
            item["content"]
            for item in execution["content"]
            if item["kind"] == "execution-state"
        )
        state["nodes"]["a"].update(
            {
                "state": "completed",
                "idempotencyKey": "pkg:1:a",
                "result": {"ok": True},
                "mergeResult": {"result": "merged"},
            }
        )
        state["completedOrder"] = ["a"]
        state["mergedOrder"] = ["a"]
        state["state"] = "review"
        state_file = self.root / "state.json"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        run_cli(
            "state-put",
            str(package),
            "--file",
            str(state_file),
            "--invocation-id",
            "invocation-2",
        )
        evidence_file = self.root / "evidence.json"
        evidence_file.write_text(
            json.dumps({"aiChecks": ["dag-complete"]}), encoding="utf-8"
        )
        run_cli(
            "review-put",
            str(package),
            "--evidence-file",
            str(evidence_file),
        )
        receipt_file = self.root / "receipt.json"
        receipt_file.write_text(
            json.dumps(
                {
                    "packageId": "pkg",
                    "sourceBranch": "work-package/pkg",
                    "targetBranch": "main",
                    "operationResult": "integrated",
                }
            ),
            encoding="utf-8",
        )
        completed = json.loads(
            run_cli(
                "complete",
                str(package),
                "--receipt",
                str(receipt_file),
            ).stdout
        )
        self.assertEqual(completed["status"], "done")


if __name__ == "__main__":
    unittest.main()
