from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import jsonschema


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "intakes"
    / "scripts"
    / "intake_agent_exec.py"
)
INTAKE_MANAGER = SCRIPT.with_name("intake.py")


def create_intake(root: Path) -> None:
    package = root / ".agent-factory" / "intakes" / "intake-1"
    result = subprocess.run(
        [sys.executable, str(INTAKE_MANAGER), "create", str(package),
         "--id", "intake-1", "--topic", "test", "--project-id", "test",
         "--language", "ko"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr)


def load_module():
    spec = importlib.util.spec_from_file_location("intake_agent_exec", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load intake_agent_exec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeProcess:
    def __init__(self, lines: list[str], returncode: int = 0, stderr: str = "") -> None:
        self.stdout = iter(lines)
        self.stderr = io.StringIO(stderr)
        self.stdin = io.StringIO()
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class IntakeAgentExecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_new_command_uses_argv_stdin_schema_and_minimum_network(self) -> None:
        command = self.module.build_command(
            codex="codex",
            repository=Path("/tmp/project"),
            session_id=None,
            capability="analysis",
        )
        self.assertEqual(command[:3], ["codex", "exec", "-C"])
        self.assertIn("--output-schema", command)
        self.assertIn("--json", command)
        self.assertEqual(command[-1], "-")
        self.assertIn("sandbox_workspace_write.network_access=false", command)
        self.assertNotIn("shell=True", command)

    def test_terminal_result_schema_is_valid(self) -> None:
        schema = json.loads(self.module.RESULT_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)

    def test_web_command_enables_network_and_resume_uses_selected_session(self) -> None:
        command = self.module.build_command(
            codex="codex",
            repository=Path("/tmp/project"),
            session_id="019fd1e3-64ea-7bc0-a757-6165641ad9ba",
            capability="web-search",
        )
        self.assertEqual(command[:3], ["codex", "exec", "resume"])
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertEqual(command[-2:], ["019fd1e3-64ea-7bc0-a757-6165641ad9ba", "-"])

    def test_prompt_enforces_role_and_manager_only_writes(self) -> None:
        prompt = self.module.build_prompt(
            Path("/tmp/project"), "intake-1", "analysis", "inspect runtime"
        )
        self.assertIn("You are the Intake Agent", prompt)
        self.assertIn("intake.py", prompt)
        self.assertIn("Main Agent", prompt)
        self.assertIn("Main Agent owns topic-boundary", prompt)
        self.assertIn("internal code, documents, and runtime", prompt)

    def test_success_emits_only_ack_and_terminal_result(self) -> None:
        terminal = {
            "status": "completed",
            "summary": "evidence recorded",
            "question": None,
            "evidence": ["skills/intakes/SKILL.md"],
            "limitations": [],
        }
        lines = [
            json.dumps({"type": "thread.started", "thread_id": "session-1"}) + "\n",
            json.dumps({"type": "item.completed", "item": {"text": "secret raw log"}}) + "\n",
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 9}}) + "\n",
        ]
        process = FakeProcess(lines)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process", return_value=process):
                with mock.patch.object(
                    self.module, "read_terminal_result", return_value=terminal
                ):
                    code = self.module.run(
                        repository=root,
                        intake_id="intake-1",
                        capability="analysis",
                        request="inspect",
                        session_id=None,
                        codex="codex",
                        timeout=5,
                        output=output,
                    )
        self.assertEqual(code, 0)
        documents = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([item["kind"] for item in documents], ["ack", "result"])
        self.assertEqual(documents[0]["sessionId"], "session-1")
        self.assertEqual(documents[1]["summary"], "evidence recorded")
        self.assertNotIn("secret raw log", output.getvalue())

    def test_mismatched_resume_is_rejected_before_process_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            self.module.save_binding(root, "intake-1", "session-one")
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process") as popen:
                code = self.module.run(
                    repository=root,
                    intake_id="intake-1",
                    capability="analysis",
                    request="inspect",
                    session_id="session-two",
                    codex="codex",
                    timeout=5,
                    output=output,
                )
        self.assertEqual(code, 2)
        popen.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "session_mismatch")

    def test_duplicate_writer_is_rejected_before_process_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            with self.module.intake_lock(root, "intake-1"):
                output = io.StringIO()
                with mock.patch.object(self.module, "start_process") as popen:
                    code = self.module.run(
                        repository=root,
                        intake_id="intake-1",
                        capability="analysis",
                        request="inspect",
                        session_id=None,
                        codex="codex",
                        timeout=5,
                        output=output,
                    )
            self.assertEqual(code, 2)
            popen.assert_not_called()
            self.assertEqual(
                json.loads(output.getvalue())["error"]["code"], "intake_writer_busy"
            )

    def test_process_failure_is_sanitized(self) -> None:
        process = FakeProcess(
            [json.dumps({"type": "thread.started", "thread_id": "session-1"}) + "\n"],
            returncode=7,
            stderr="token=super-secret",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process", return_value=process):
                code = self.module.run(
                    repository=root,
                    intake_id="intake-1",
                    capability="analysis",
                    request="inspect",
                    session_id=None,
                    codex="codex",
                    timeout=5,
                    output=output,
                )
        self.assertEqual(code, 1)
        self.assertNotIn("super-secret", output.getvalue())
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1])["error"]["code"], "codex_exec_failed")

    def test_malformed_event_fails_closed_without_raw_output(self) -> None:
        process = FakeProcess(["not-json\n"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process", return_value=process):
                code = self.module.run(
                    repository=root,
                    intake_id="intake-1",
                    capability="analysis",
                    request="inspect",
                    session_id=None,
                    codex="codex",
                    timeout=5,
                    output=output,
                )
        self.assertEqual(code, 1)
        self.assertNotIn("not-json", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "malformed_codex_event")

    def test_oversized_event_fails_closed(self) -> None:
        process = FakeProcess(["{" + ("x" * 1_048_576) + "\n"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process", return_value=process):
                code = self.module.run(
                    repository=root,
                    intake_id="intake-1",
                    capability="analysis",
                    request="inspect",
                    session_id=None,
                    codex="codex",
                    timeout=5,
                    output=output,
                )
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "codex_event_too_large")

    def test_timeout_stops_a_silent_process(self) -> None:
        read_fd, write_fd = os.pipe()
        process = FakeProcess([])
        process.stdout = os.fdopen(read_fd, "r", encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            output = io.StringIO()
            with mock.patch.object(self.module, "start_process", return_value=process):
                started = time.monotonic()
                code = self.module.run(
                    repository=root,
                    intake_id="intake-1",
                    capability="analysis",
                    request="inspect",
                    session_id=None,
                    codex="codex",
                    timeout=0.02,
                    output=output,
                )
            os.close(write_fd)
            process.stdout.close()
        self.assertEqual(code, 1)
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "codex_exec_timeout")

    def test_cli_new_then_selected_resume_integration(self) -> None:
        fake_source = """#!/usr/bin/env python3
import json
import os
import sys
with open(os.environ["INTAKE_EXEC_ARGV_LOG"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\\n")
prompt = sys.stdin.read()
if "intake.py" not in prompt:
    raise SystemExit(9)
print(json.dumps({"type": "thread.started", "thread_id": "session-1"}), flush=True)
result = {"status": "completed", "summary": "recorded", "question": None, "evidence": ["source"], "limitations": []}
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(result)}}), flush=True)
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_intake(root)
            fake = root / "fake-codex"
            fake.write_text(fake_source, encoding="utf-8")
            fake.chmod(0o755)
            log = root / "argv.jsonl"
            environment = dict(os.environ, INTAKE_EXEC_ARGV_LOG=str(log))
            common = [
                sys.executable,
                str(SCRIPT),
                "--repository",
                str(root),
                "--intake-id",
                "intake-1",
                "--capability",
                "analysis",
                "--request",
                "inspect",
                "--codex",
                str(fake),
            ]
            created = subprocess.run(common, text=True, capture_output=True, env=environment, check=False)
            resumed = subprocess.run(common + ["--session-id", "session-1"], text=True, capture_output=True, env=environment, check=False)

            self.assertEqual(created.returncode, 0, created.stdout)
            self.assertEqual(resumed.returncode, 0, resumed.stdout)
            self.assertEqual(created.stderr, "")
            self.assertEqual(resumed.stderr, "")
            self.assertEqual([json.loads(line)["kind"] for line in created.stdout.splitlines()], ["ack", "result"])
            invocations = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(invocations[0][0], "exec")
            self.assertEqual(invocations[1][:2], ["exec", "resume"])
            self.assertEqual(invocations[1][-2:], ["session-1", "-"])


if __name__ == "__main__":
    unittest.main()
