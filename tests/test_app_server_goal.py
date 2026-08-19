from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "work-units"
    / "scripts"
    / "app_server_goal.py"
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
turn_count = 0
active_objective = "wu-001"


def emit(value):
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def record(method):
    with open(log_path, "a", encoding="utf-8") as stream:
        stream.write(method + "\n")


def goal(*, status="active", thread_id="thread-1", objective=None):
    return {
        "threadId": thread_id,
        "objective": active_objective if objective is None else objective,
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
        active_objective = message["params"]["objective"]
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
        turn_count += 1
        turn_id = f"turn-{turn_count}"
        if scenario == "invalid_turn_response":
            emit({"id": request_id, "result": {"turn": None}})
            continue
        emit(
            {
                "id": request_id,
                "result": {
                    "turn": {
                        "id": turn_id,
                        "status": "inProgress",
                        "items": [],
                    }
                },
            }
        )
        if scenario == "interrupted_once" and turn_count == 1:
            emit(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turn": {
                            "id": turn_id,
                            "status": "interrupted",
                            "items": [],
                        },
                    },
                }
            )
            continue
        if (
            scenario == "blocked_forever"
            or (scenario == "blocked_once" and turn_count == 1)
        ):
            emit(
                {
                    "method": "thread/goal/updated",
                    "params": {
                        "threadId": "thread-1",
                        "goal": goal(status="blocked"),
                        "turnId": turn_id,
                    },
                }
            )
            emit(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turn": {
                            "id": turn_id,
                            "status": "completed",
                            "items": [],
                        },
                    },
                }
            )
            continue
        completed_goal = goal(status="complete")
        turn_status = "failed" if scenario == "turn_failed" else "completed"
        goal_message = {
            "method": "thread/goal/updated",
            "params": {
                "threadId": "thread-1",
                "goal": completed_goal,
                "turnId": turn_id,
            },
        }
        turn_message = {
            "method": "turn/completed",
            "params": {
                "threadId": "thread-1",
                "turn": {
                    "id": turn_id,
                    "status": turn_status,
                    "items": [
                        {
                            "id": "agent-result",
                            "type": "agentMessage",
                            "text": json.dumps(
                                {
                                    "result": "pass",
                                    "checklistResult": "pass",
                                    "findings": [],
                                    "blockingFindings": [],
                                    "remainingRisks": [],
                                    "inputs": [
                                        "implementation",
                                        "tests",
                                        "documentation",
                                    ],
                                }
                            ),
                        }
                    ],
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
            "mode": "execution",
            "executionRoute": "workspace-direct",
            "objective": work_unit_id,
            "package": str(
                repository / ".agent-factory" / "work-units" / work_unit_id
            ),
        }

    def execute(
        self,
        scenario: str = "success",
        timeout: float = 1.0,
        emit_ack=None,
        thread_id: str | None = None,
    ):
        os.environ["FAKE_APP_SERVER_SCENARIO"] = scenario
        module = load_module()
        return module.execute(
            repository=self.repository,
            work_unit_id="wu-001",
            codex_executable=str(self.server),
            timeout_seconds=timeout,
            validator=self.validator,
            emit_ack=emit_ack,
            thread_id=thread_id,
        )

    def methods(self) -> list[str]:
        if not self.log_path.exists():
            return []
        return self.log_path.read_text(encoding="utf-8").splitlines()

    def test_goal_is_verified_before_turn_starts(self) -> None:
        acknowledgements = []
        payload = self.execute(emit_ack=acknowledgements.append)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "complete")
        self.assertEqual(payload["context"]["workUnitId"], "wu-001")
        self.assertEqual(payload["context"]["executionRoute"], "workspace-direct")
        self.assertEqual(payload["context"]["threadId"], "thread-1")
        self.assertEqual(payload["context"]["goal"]["status"], "complete")
        self.assertEqual(payload["context"]["turnIds"], ["turn-1"])
        self.assertEqual(payload["process"]["returnCode"], 0)
        self.assertEqual(
            [
                {
                    key: value
                    for key, value in acknowledgement.items()
                    if key != "initializationTimingMs"
                }
                for acknowledgement in acknowledgements
            ],
            [
                {
                    "executionMode": "execution",
                    "executionRoute": "workspace-direct",
                    "package": str(
                        self.repository
                        / ".agent-factory"
                        / "work-units"
                        / "wu-001"
                    ),
                    "repository": str(self.repository),
                    "schemaVersion": "1.0.0",
                    "threadId": "thread-1",
                    "threadDisposition": "created",
                    "turnId": "turn-1",
                    "type": "ack",
                    "workUnitId": "wu-001",
                }
            ],
        )
        timing = acknowledgements[0]["initializationTimingMs"]
        self.assertEqual(
            list(timing),
            [
                "processStart",
                "appServerReady",
                "threadReady",
                "goalReady",
                "turnAccepted",
                "ackEmitted",
            ],
        )
        self.assertEqual(list(timing.values()), sorted(timing.values()))
        self.assertEqual(acknowledgements[0]["threadDisposition"], "created")
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

    def test_existing_thread_is_reused_without_thread_start(self) -> None:
        acknowledgements = []

        payload = self.execute(
            emit_ack=acknowledgements.append,
            thread_id="thread-1",
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["context"]["threadId"], "thread-1")
        self.assertEqual(payload["context"]["threadDisposition"], "reused")
        self.assertEqual(acknowledgements[0]["threadDisposition"], "reused")
        self.assertNotIn("thread/start", self.methods())
        self.assertEqual(
            self.methods(),
            ["initialize", "initialized", "thread/goal/get", "turn/start"],
        )

    def test_existing_thread_with_mismatched_goal_is_refused(self) -> None:
        acknowledgements = []

        payload = self.execute(
            "objective_mismatch",
            emit_ack=acknowledgements.append,
            thread_id="thread-1",
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "goal_objective_mismatch")
        self.assertEqual(acknowledgements, [])
        self.assertNotIn("thread/start", self.methods())
        self.assertNotIn("turn/start", self.methods())

    def test_execution_prompt_explicitly_invokes_workflow_agent_role(self) -> None:
        module = load_module()

        prompt = module.execution_prompt("wu-001", "execution", None)

        self.assertIn("$agent", prompt)
        self.assertIn("You are the Workflow Agent", prompt)
        self.assertIn("You must execute", prompt)
        self.assertIn("primary Git workspace", prompt)
        self.assertIn("preserve unrelated changes", prompt)
        self.assertIn("Do not reassess", prompt)
        self.assertIn("execute only its implementation Work", prompt)
        self.assertIn("implementation Work", prompt)
        self.assertIn("Do not run tests", prompt)
        self.assertNotIn("Plan -> Work -> AI Review -> Report", prompt)

    def test_role_prompts_preserve_test_documentation_and_review_boundaries(self) -> None:
        module = load_module()

        test_prompt = module.test_agent_prompt(
            "wu-001",
            ["python -m unittest x"],
            "workspace-direct",
            self.repository,
        )
        documentation_prompt = module.documentation_agent_prompt(
            "wu-001", "tests not run"
        )
        review_prompt = module.review_agent_prompt(
            "wu-001", {"tests": {"state": "tests-not-run"}}
        )

        self.assertIn("You are the Test Agent", test_prompt)
        self.assertIn("exact Human-authorized", test_prompt)
        self.assertIn("do not modify product code", test_prompt)
        self.assertIn("You are the Documentation Agent", documentation_prompt)
        self.assertIn("directly affected", documentation_prompt)
        self.assertIn("owning manager", documentation_prompt)
        self.assertIn("You are the Review Agent", review_prompt)
        self.assertIn("static review", review_prompt)
        self.assertIn("Do not modify any file", review_prompt)
        self.assertIn("Do not execute tests", review_prompt)
        self.assertIn("blockingFindings", review_prompt)

    def test_review_result_is_extracted_and_rejects_inconsistent_blockers(self) -> None:
        module = load_module()
        result = {
            "result": "pass",
            "checklistResult": "pass",
            "findings": [],
            "blockingFindings": [],
            "remainingRisks": ["Human review remains"],
            "inputs": ["implementation", "tests", "documentation"],
        }
        turn = {
            "items": [
                {"type": "agentMessage", "text": json.dumps(result)}
            ]
        }

        self.assertEqual(
            module.validate_review_result(module.agent_result(turn)), result
        )
        result["blockingFindings"] = ["role contract mismatch"]
        with self.assertRaises(module.ContractError):
            module.validate_review_result(result)
        result["blockingFindings"] = []
        result["checklistResult"] = "fail"
        with self.assertRaises(module.ContractError):
            module.validate_review_result(result)
        result["result"] = "fail"
        result["checklistResult"] = "pass"
        result["inputs"] = ["implementation", "tests"]
        with self.assertRaises(module.ContractError):
            module.validate_review_result(result)

    def test_failed_review_result_is_terminal_even_when_structurally_valid(self) -> None:
        module = load_module()
        result = {
            "result": "fail",
            "checklistResult": "fail",
            "findings": ["implementation mismatch"],
            "blockingFindings": ["implementation mismatch"],
            "remainingRisks": [],
            "inputs": ["implementation", "tests", "documentation"],
        }

        self.assertEqual(module.validate_review_result(result), result)
        with self.assertRaisesRegex(module.ContractError, "did not pass"):
            module.require_passing_review_result(result)

    def test_role_failure_payload_preserves_completed_stage_evidence(self) -> None:
        module = load_module()
        stages = {
            "implementation": {"ack": {"role": "Workflow Agent"}},
            "tests": {"state": "tests-not-run"},
            "documentation": {"ack": {"role": "Documentation Agent"}},
            "failure": {"role": "Review Agent"},
        }

        payload = module.error_payload(
            module.ContractError(
                "review_result_invalid",
                "invalid Review Agent result",
                {"role": "Review Agent"},
            ),
            [],
            {"review": {"returnCode": 0}},
            stages,
        )

        self.assertEqual(payload["context"]["stages"], stages)
        self.assertEqual(payload["error"]["details"]["role"], "Review Agent")

    def test_orchestration_runs_review_after_documentation_and_aggregates_report_material(
        self,
    ) -> None:
        os.environ["FAKE_APP_SERVER_SCENARIO"] = "success"
        module = load_module()

        def validator(repository: Path, work_unit_id: str):
            package = self.validator(repository, work_unit_id)
            package["orchestrateRoles"] = True
            package["authorizedTests"] = []
            return package

        payload = module.execute(
            repository=self.repository,
            work_unit_id="wu-001",
            codex_executable=str(self.server),
            timeout_seconds=1.0,
            validator=validator,
        )

        self.assertTrue(payload["ok"])
        stages = payload["context"]["stages"]
        self.assertEqual(
            list(stages),
            ["implementation", "tests", "documentation", "review", "reportMaterial"],
        )
        self.assertEqual(stages["tests"]["state"], "tests-not-run")
        self.assertEqual(stages["review"]["ack"]["role"], "Review Agent")
        self.assertEqual(stages["review"]["aiReviewResult"]["result"], "pass")
        self.assertEqual(
            stages["reportMaterial"]["review"]["aiReviewResult"],
            stages["review"]["aiReviewResult"],
        )

    def test_rework_prompt_explicitly_invokes_workflow_agent_role(self) -> None:
        module = load_module()

        prompt = module.execution_prompt(
            "wu-001",
            "rework",
            "Commit the implementation and rebind all evidence.",
        )

        self.assertIn("$agent", prompt)
        self.assertIn("perform rework", prompt)
        self.assertIn(
            "Commit the implementation and rebind all evidence.",
            prompt,
        )
        self.assertIn("execute only its implementation Work", prompt)

    def test_recovery_prompt_requires_unconditional_workflow_continuation(
        self,
    ) -> None:
        module = load_module()

        prompt = module.recovery_prompt("wu-001", "interrupted")

        self.assertIn("You are the Workflow Agent", prompt)
        self.assertIn("You must continue", prompt)
        self.assertIn("Do not reassess", prompt)
        self.assertIn("primary Git workspace", prompt)
        self.assertIn("preserve unrelated changes", prompt)

    def test_launch_mode_accepts_ready_execution_and_planned_rework(
        self,
    ) -> None:
        module = load_module()
        ready = {"valid": True, "id": "wu-001", "status": "ready"}
        rework = {"valid": True, "id": "wu-001", "status": "working"}
        planned_rework = {
            "content": [
                {
                    "id": "EXECUTION-STATE-001",
                    "kind": "execution-state",
                    "content": {
                        "state": "planned",
                        "currentRevision": 2,
                        "currentAttempt": None,
                        "history": [{"revision": 1, "attempt": 1}],
                        "reworkInstruction": "Commit and rebind evidence.",
                    },
                }
            ]
        }

        self.assertEqual(module.launch_mode(ready, {}, "wu-001"), "execution")
        self.assertEqual(
            module.launch_mode(rework, planned_rework, "wu-001"),
            "rework",
        )

    def test_launch_mode_accepts_active_working_state_for_resume(self) -> None:
        module = load_module()
        validation = {"valid": True, "id": "wu-001", "status": "working"}
        active = {
            "content": [
                {
                    "id": "EXECUTION-STATE-001",
                    "kind": "execution-state",
                    "content": {
                        "state": "running",
                        "currentRevision": 1,
                        "currentAttempt": 1,
                        "invocationId": "thread-prior",
                        "history": [],
                    },
                }
            ]
        }

        self.assertEqual(module.launch_mode(validation, active, "wu-001"), "resume")

        planned_without_instruction = {
            "content": [
                {
                    "id": "EXECUTION-STATE-001",
                    "kind": "execution-state",
                    "content": {
                        "state": "planned",
                        "currentRevision": 2,
                        "currentAttempt": None,
                        "history": [{"revision": 1, "attempt": 1}],
                    },
                }
            ]
        }
        with self.assertRaises(module.ContractError) as missing:
            module.launch_mode(
                validation,
                planned_without_instruction,
                "wu-001",
            )

        self.assertEqual(missing.exception.code, "rework_instruction_missing")

    def test_validate_workspace_direct_uses_primary_repository(self) -> None:
        module = load_module()
        subprocess.run(
            ["git", "init", "-b", "main", str(self.repository)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package = self.repository / ".agent-factory" / "work-units" / "wu-001"
        package.mkdir(parents=True)
        context = {
            "goalId": "wu-001",
            "repository": str(self.repository),
            "baseRef": "primary-workspace",
            "executionMode": "workspace-direct",
        }
        section = {
            "content": [
                {
                    "id": "EXEC-CONTEXT-001",
                    "kind": "execution-context",
                    "content": context,
                }
            ]
        }
        with (
            mock.patch.object(
                module,
                "manager_validation",
                return_value={"valid": True, "id": "wu-001", "status": "ready"},
            ),
            mock.patch.object(
                module,
                "execution_context_section",
                return_value=(section, context),
            ),
        ):
            selected = module.validate_work_unit(self.repository, "wu-001")

        self.assertEqual(selected["mode"], "execution")
        self.assertEqual(selected["executionRoute"], "workspace-direct")
        self.assertEqual(selected["package"], str(package))

    def test_validate_specification_direct_uses_primary_repository(self) -> None:
        module = load_module()
        subprocess.run(
            ["git", "init", "-b", "main", str(self.repository)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package = (
            self.repository / ".agent-factory" / "work-units" / "wu-001"
        )
        package.mkdir(parents=True)
        context = {
            "id": "EXEC-CONTEXT-001",
            "kind": "execution-context",
            "content": {
                "goalId": "wu-001",
                "repository": str(self.repository),
                "executionMode": "specification-direct",
            },
        }
        section = {"content": [context]}

        with (
            mock.patch.object(
                module,
                "manager_validation",
                return_value={"valid": True, "id": "wu-001", "status": "ready"},
            ),
            mock.patch.object(
                module,
                "execution_context_section",
                return_value=(section, context["content"]),
            ),
        ):
            selected = module.validate_work_unit(self.repository, "wu-001")

        self.assertEqual(selected["mode"], "execution")
        self.assertEqual(selected["executionRoute"], "specification-direct")
        self.assertEqual(selected["package"], str(package))

    def test_validate_work_unit_rejects_removed_execution_mode(self) -> None:
        module = load_module()
        subprocess.run(
            ["git", "init", "-b", "main", str(self.repository)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        package = self.repository / ".agent-factory" / "work-units" / "wu-001"
        package.mkdir(parents=True)
        context = {
            "goalId": "wu-001",
            "repository": str(self.repository),
            "baseRef": "primary-workspace",
            "executionMode": "linked-workspace",
        }
        section = {
            "content": [
                {
                    "id": "EXEC-CONTEXT-001",
                    "kind": "execution-context",
                    "content": context,
                }
            ]
        }
        with (
            mock.patch.object(
                module,
                "manager_validation",
                return_value={"valid": True, "id": "wu-001", "status": "ready"},
            ),
            mock.patch.object(
                module,
                "execution_context_section",
                return_value=(section, context),
            ),
            self.assertRaises(module.ContractError) as raised,
        ):
            module.validate_work_unit(self.repository, "wu-001")

        self.assertEqual(raised.exception.code, "invalid_execution_context")

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
                acknowledgements = []
                timeout = (
                    0.1
                    if scenario in {"timeout", "missing_notification"}
                    else 1.0
                )
                payload = self.execute(
                    scenario,
                    timeout=timeout,
                    emit_ack=acknowledgements.append,
                )
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["error"]["code"], code)
                self.assertEqual(acknowledgements, [])
                self.assertNotIn("turn/start", self.methods())

    def test_invalid_initial_turn_response_emits_no_ack(self) -> None:
        acknowledgements = []
        payload = self.execute(
            "invalid_turn_response",
            emit_ack=acknowledgements.append,
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid_turn_response")
        self.assertEqual(acknowledgements, [])
        self.assertEqual(self.methods()[-1], "turn/start")

    def test_failed_turn_is_not_reported_as_success(self) -> None:
        payload = self.execute("turn_failed")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "turn_failed")
        self.assertEqual(self.methods()[-1], "turn/start")

    def test_interrupted_turn_is_automatically_continued(self) -> None:
        acknowledgements = []
        payload = self.execute(
            "interrupted_once",
            emit_ack=acknowledgements.append,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["context"]["turnIds"], ["turn-1", "turn-2"])
        self.assertEqual(payload["context"]["recoveryCount"], 1)
        self.assertEqual(len(acknowledgements), 1)
        self.assertEqual(acknowledgements[0]["turnId"], "turn-1")
        self.assertEqual(self.methods().count("turn/start"), 2)

    def test_blocked_goal_is_reactivated_and_continued(self) -> None:
        payload = self.execute("blocked_once")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["context"]["goal"]["status"], "complete")
        self.assertEqual(payload["context"]["turnIds"], ["turn-1", "turn-2"])
        self.assertEqual(payload["context"]["recoveryCount"], 1)
        self.assertEqual(self.methods().count("thread/goal/set"), 2)
        self.assertEqual(self.methods().count("thread/goal/get"), 2)
        self.assertEqual(self.methods().count("turn/start"), 2)

    def test_blocked_goal_recovery_exhaustion_is_explicit(self) -> None:
        payload = self.execute("blocked_forever")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "goal_recovery_exhausted")
        self.assertEqual(payload["error"]["details"]["recoveries"], 20)
        self.assertEqual(self.methods().count("turn/start"), 21)

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

    def test_stdout_payload_is_stable_json(self) -> None:
        payload = self.execute()
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

        self.assertEqual(json.loads(encoded), payload)
        self.assertEqual(payload["schemaVersion"], "1.0.0")
        self.assertEqual(payload["command"], "execute")

    def test_cli_emits_ack_before_final_document(self) -> None:
        module = load_module()
        acknowledgement = {
            "schemaVersion": "1.0.0",
            "threadId": "thread-1",
            "turnId": "turn-1",
            "type": "ack",
            "workUnitId": "wu-001",
        }
        terminal = {
            "command": "execute",
            "ok": True,
            "schemaVersion": "1.0.0",
            "state": "complete",
        }

        def execute(**arguments):
            arguments["emit_ack"](acknowledgement)
            return terminal

        output = io.StringIO()
        with (
            mock.patch.object(module, "execute", side_effect=execute),
            contextlib.redirect_stdout(output),
        ):
            status = module.main(
                [
                    "--repository",
                    str(self.repository),
                    "--work-unit-id",
                    "wu-001",
                ]
            )

        self.assertEqual(status, 0)
        self.assertEqual(
            [json.loads(line) for line in output.getvalue().splitlines()],
            [acknowledgement, terminal],
        )

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
