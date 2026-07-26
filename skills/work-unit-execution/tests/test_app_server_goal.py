from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "app_server_goal.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("app_server_goal", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load app_server_goal")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAKE_SERVER = r"""
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time


scenario = os.environ.get("FAKE_APP_SERVER_SCENARIO", "success")
log_path = os.environ["FAKE_APP_SERVER_LOG"]


def emit(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def record(method):
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(method + "\n")


def goal(*, status="active", thread_id="thread-1", objective="wu-001"):
    return {
        "threadId": thread_id,
        "objective": objective,
        "status": status,
        "tokensUsed": 0,
        "timeUsedSeconds": 0,
        "createdAt": 1,
        "updatedAt": 1,
    }


for line in sys.stdin:
    message = json.loads(line)
    method = message["method"]
    record(method)
    request_id = message.get("id")

    if method == "initialize":
        emit(
            {
                "id": request_id,
                "result": {
                    "userAgent": "fake",
                    "codexHome": "/tmp/fake-codex",
                    "platformFamily": "unix",
                    "platformOs": "linux",
                },
            }
        )
    elif method == "initialized":
        continue
    elif method == "thread/start":
        emit({"id": request_id, "result": {"thread": {"id": "thread-1"}}})
    elif method == "thread/goal/set":
        if scenario == "rpc_error":
            emit(
                {
                    "id": request_id,
                    "error": {"code": -32603, "message": "goal set failed"},
                }
            )
            continue
        selected = goal()
        if scenario == "thread_mismatch":
            selected = goal(thread_id="thread-other")
        elif scenario == "objective_mismatch":
            selected = goal(objective="wu-other")
        elif scenario == "inactive_goal":
            selected = goal(status="paused")
        if scenario != "missing_notification":
            emit(
                {
                    "method": "thread/goal/updated",
                    "params": {
                        "threadId": selected["threadId"],
                        "goal": selected,
                        "turnId": None,
                    },
                }
            )
        emit({"id": request_id, "result": {"goal": selected}})
    elif method == "thread/goal/get":
        if scenario == "invalid_json":
            sys.stdout.write("{not-json\n")
            sys.stdout.flush()
            continue
        if scenario == "eof":
            raise SystemExit(0)
        if scenario == "timeout":
            time.sleep(5)
            continue
        selected = goal()
        if scenario == "null_goal":
            selected = None
        elif scenario == "thread_mismatch":
            selected = goal(thread_id="thread-other")
        elif scenario == "objective_mismatch":
            selected = goal(objective="wu-other")
        elif scenario == "inactive_goal":
            selected = goal(status="paused")
        emit({"id": request_id, "result": {"goal": selected}})
    elif method == "turn/start":
        emit(
            {
                "id": request_id,
                "result": {
                    "turn": {
                        "id": "turn-1",
                        "status": "inProgress",
                        "items": [],
                    }
                },
            }
        )
        completed_goal = goal(status="complete")
        turn_status = "failed" if scenario == "turn_failed" else "completed"
        goal_message = {
            "method": "thread/goal/updated",
            "params": {
                "threadId": "thread-1",
                "goal": completed_goal,
                "turnId": "turn-1",
            },
        }
        turn_message = {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turn": {
                    "id": "turn-1",
                    "status": turn_status,
                    "items": [],
                },
            },
        }
        if scenario == "goal_after_turn":
            emit(turn_message)
            emit(goal_message)
        else:
            emit(goal_message)
            emit(turn_message)
"""


class AppServerGoalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repository = self.root / "repo"
        self.repository.mkdir()
        self.log_path = self.root / "methods.log"
        self.server = self.root / "fake-codex"
        self.server.write_text(textwrap.dedent(FAKE_SERVER).lstrip(), encoding="utf-8")
        self.server.chmod(0o755)
        self.previous_scenario = os.environ.get("FAKE_APP_SERVER_SCENARIO")
        self.previous_log = os.environ.get("FAKE_APP_SERVER_LOG")
        os.environ["FAKE_APP_SERVER_LOG"] = str(self.log_path)

    def tearDown(self) -> None:
        if self.previous_scenario is None:
            os.environ.pop("FAKE_APP_SERVER_SCENARIO", None)
        else:
            os.environ["FAKE_APP_SERVER_SCENARIO"] = self.previous_scenario
        if self.previous_log is None:
            os.environ.pop("FAKE_APP_SERVER_LOG", None)
        else:
            os.environ["FAKE_APP_SERVER_LOG"] = self.previous_log
        self.temp.cleanup()

    @staticmethod
    def validator(repository: Path, work_unit_id: str) -> dict[str, str]:
        return {
            "objective": work_unit_id,
            "package": str(
                repository / ".agent-factory" / "work-units" / work_unit_id
            ),
        }

    def execute(self, scenario: str = "success", timeout: float = 1.0):
        os.environ["FAKE_APP_SERVER_SCENARIO"] = scenario
        module = load_module()
        return module.execute(
            repository=self.repository,
            work_unit_id="wu-001",
            codex_executable=str(self.server),
            timeout_seconds=timeout,
            validator=self.validator,
        )

    def methods(self) -> list[str]:
        if not self.log_path.exists():
            return []
        return self.log_path.read_text(encoding="utf-8").splitlines()

    def test_goal_is_verified_before_turn_starts(self) -> None:
        payload = self.execute()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "complete")
        self.assertEqual(payload["context"]["workUnitId"], "wu-001")
        self.assertEqual(payload["context"]["threadId"], "thread-1")
        self.assertEqual(payload["context"]["goal"]["status"], "complete")
        self.assertEqual(payload["context"]["turnIds"], ["turn-1"])
        self.assertEqual(payload["process"]["returnCode"], 0)
        self.assertEqual(
            self.methods(),
            [
                "initialize",
                "initialized",
                "thread/start",
                "thread/goal/set",
                "thread/goal/get",
                "turn/start",
            ],
        )

    def test_goal_preflight_failures_never_start_a_turn(self) -> None:
        expected_codes = {
            "rpc_error": "app_server_rpc_error",
            "null_goal": "goal_missing",
            "thread_mismatch": "goal_thread_mismatch",
            "objective_mismatch": "goal_objective_mismatch",
            "inactive_goal": "goal_not_active",
            "invalid_json": "invalid_app_server_json",
            "eof": "app_server_eof",
            "timeout": "app_server_timeout",
            "missing_notification": "app_server_timeout",
        }
        for scenario, code in expected_codes.items():
            with self.subTest(scenario=scenario):
                self.log_path.unlink(missing_ok=True)
                payload = self.execute(scenario, timeout=0.1)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], code)
                self.assertNotIn("turn/start", self.methods())

    def test_failed_turn_is_not_reported_as_success(self) -> None:
        payload = self.execute("turn_failed")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "turn_failed")
        self.assertEqual(self.methods()[-1], "turn/start")

    def test_goal_completion_after_turn_completion_is_accepted(self) -> None:
        payload = self.execute("goal_after_turn")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["context"]["goal"]["status"], "complete")

    def test_repository_must_be_absolute(self) -> None:
        module = load_module()
        payload = module.execute(
            repository=Path("relative"),
            work_unit_id="wu-001",
            codex_executable=str(self.server),
            timeout_seconds=1.0,
            validator=self.validator,
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "path_not_absolute")
        self.assertEqual(self.methods(), [])

    def test_explicit_authoring_package_is_passed_to_validator(self) -> None:
        module = load_module()
        package = self.root / "authoring" / ".agent-factory" / "work-units" / "wu-001"
        calls: list[tuple[Path, str, Path]] = []

        def validator(
            repository: Path,
            work_unit_id: str,
            package_path: Path,
        ) -> dict[str, str]:
            calls.append((repository, work_unit_id, package_path))
            return {"objective": work_unit_id, "package": str(package_path)}

        payload = module.execute(
            repository=self.repository,
            work_unit_id="wu-001",
            codex_executable=str(self.server),
            timeout_seconds=1.0,
            package_path=package,
            validator=validator,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(
            calls,
            [(self.repository.resolve(), "wu-001", package)],
        )
        self.assertEqual(payload["context"]["package"], str(package))

    def test_validator_accepts_package_from_same_repository_worktree(self) -> None:
        module = load_module()
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repository), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "config",
                "user.email",
                "test@example.com",
            ],
            check=True,
        )
        (self.repository / "README").write_text("test\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.repository), "add", "README"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repository), "commit", "-qm", "initial"],
            check=True,
        )
        authoring = self.root / "authoring"
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repository),
                "worktree",
                "add",
                "--detach",
                str(authoring),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package = authoring / ".agent-factory" / "work-units" / "wu-001"
        section = package / "data" / "sections"
        section.mkdir(parents=True)
        (section / "execution-context.json").write_text(
            json.dumps(
                {
                    "content": [
                        {
                            "kind": "execution-context",
                            "content": {
                                "goalId": "wu-001",
                                "repository": str(self.repository.resolve()),
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        fake_manager = self.root / "fake-work-unit.py"
        fake_manager.write_text(
            "import json\n"
            'print(json.dumps({"valid": True, "id": "wu-001", '
            '"status": "ready"}))\n',
            encoding="utf-8",
        )
        module.WORK_UNIT_MANAGER = fake_manager

        result = module.validate_work_unit(
            self.repository.resolve(),
            "wu-001",
            package,
        )

        self.assertEqual(result["package"], str(package.resolve()))

    def test_validator_refuses_package_from_different_repository(self) -> None:
        module = load_module()
        other = self.root / "other"
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        package = other / ".agent-factory" / "work-units" / "wu-001"
        package.mkdir(parents=True)

        with self.assertRaises(module.ContractError) as raised:
            module.validate_work_unit(
                self.repository.resolve(),
                "wu-001",
                package,
            )

        self.assertEqual(raised.exception.code, "work_unit_repository_mismatch")

    def test_stdout_payload_is_stable_json(self) -> None:
        payload = self.execute()
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

        self.assertEqual(json.loads(encoded), payload)
        self.assertEqual(payload["schemaVersion"], "1.0.0")
        self.assertEqual(payload["command"], "execute")

    def test_cli_emits_one_json_error_document_and_nonzero_status(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository",
                "relative",
                "--work-unit-id",
                "wu-001",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "path_not_absolute")


if __name__ == "__main__":
    unittest.main()
