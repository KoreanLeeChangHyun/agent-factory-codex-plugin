"""Model-free policy canaries; intended for independent Verification."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import home_fixtures
import execution_policy
import preflight


def policy(mode):
    return execution_policy.normalize({"schemaVersion": 1, "sandboxPolicy": {"type": mode}, "approvalPolicy": "never"})


def evidence(mode="read-only"):
    return {"schemaVersion": 1, "passed": True, "checks": {
        "requestRead": True, "projectDirectoryRead": True, "runWrite": True,
        "projectWrite": "denied" if mode == "read-only" else "allowed"}}


class ExecutionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project"
        self.run = self.root / "run"
        self.project.mkdir()
        self.run.mkdir()
        self.request = self.run / "request.md"
        self.request.write_text("bounded task")

    def test_full_access_uses_selected_codex_profile_without_a_model_turn(self):
        from native_codex import Rpc
        fake = mock.Mock()
        fake.poll.return_value = 0
        with mock.patch.object(preflight.subprocess, "Popen", return_value=fake) as popen, \
                mock.patch.object(Rpc, "__init__", return_value=None), mock.patch.object(Rpc, "write"), \
                mock.patch.object(Rpc, "reader", create=True), \
                mock.patch.object(Rpc, "call", side_effect=[{}, {"exitCode": 0, "stdout": json.dumps(evidence("danger-full-access")), "stderr": ""}]) as call:
            result = preflight.check("selected-codex", policy("danger-full-access"), self.project, self.run, self.request)
        self.assertEqual(result["backend"], "codex-command-exec")
        self.assertEqual([entry.args[0] for entry in call.call_args_list], ["initialize", "command/exec"])
        self.assertEqual(call.call_args.args[1]["permissionProfile"], ":danger-full-access")
        self.assertLessEqual(call.call_args.args[1]["timeoutMs"], 8000)
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], ["selected-codex", "app-server", "--listen", "stdio://"])
        self.assertEqual(command[4:], execution_policy.arguments(policy("danger-full-access"), self.run))

    def test_canary_preserves_request_and_cleans_only_its_own_files(self):
        before = {str(path.relative_to(self.root)) for path in self.root.rglob("*")}
        subprocess.run([preflight.sys.executable, "-I", "-c", preflight.CANARY, str(self.request),
                        str(self.project), str(self.run), ".test-canary", "danger-full-access"],
                       check=True, timeout=5, capture_output=True)
        self.assertEqual({str(path.relative_to(self.root)) for path in self.root.rglob("*")}, before)
        self.assertEqual(self.request.read_text(), "bounded task")

    def test_restricted_uses_exact_same_config_and_command_policy(self):
        from native_codex import Rpc
        for mode in ("read-only", "workspace-write"):
            value = policy(mode)
            fake = mock.Mock()
            fake.poll.return_value = 0
            with self.subTest(mode=mode), mock.patch.object(preflight.subprocess, "Popen", return_value=fake) as popen, \
                    mock.patch.object(Rpc, "__init__", return_value=None), mock.patch.object(Rpc, "write"), \
                    mock.patch.object(Rpc, "reader", create=True), \
                    mock.patch.object(Rpc, "call", side_effect=[{}, {"exitCode": 0, "stdout": json.dumps(evidence(mode)), "stderr": ""}]) as call:
                result = preflight.check("codex-selected", value, self.project, self.run, self.request)
            self.assertEqual(popen.call_args.args[0][4:], execution_policy.arguments(value, self.run))
            params = call.call_args.args[1]
            for key, setting in execution_policy.command_params(value, self.run).items():
                self.assertEqual(params[key], setting)
            self.assertEqual(result["backend"], "codex-command-exec")

    def test_helper_failure_is_terminal_without_alternate_policy(self):
        with mock.patch.object(preflight, "_native_command", return_value=(1, "", "bwrap: namespace denied")) as command:
            with self.assertRaisesRegex(preflight.PreflightError, "namespace denied"):
                preflight.check("codex", policy("read-only"), self.project, self.run, self.request)
        self.assertEqual(command.call_count, 1)

    def test_rpc_timeout_terminates_the_owned_process_group(self):
        from native_codex import Rpc, NativeError
        fake = mock.Mock()
        fake.poll.return_value = None
        with mock.patch.object(preflight.subprocess, "Popen", return_value=fake), \
                mock.patch.object(Rpc, "__init__", return_value=None), mock.patch.object(Rpc, "reader", create=True), \
                mock.patch.object(Rpc, "call", side_effect=NativeError("initialize timed out")), \
                mock.patch.object(preflight.os, "killpg") as kill:
            with self.assertRaisesRegex(preflight.PreflightError, "timed out"):
                preflight.check("codex", policy("read-only"), self.project, self.run, self.request)
        kill.assert_called_once_with(fake.pid, preflight.signal.SIGTERM)
        fake.wait.assert_called_once_with(timeout=0.5)

    def test_missing_or_wrong_evidence_cannot_pass(self):
        for output in ("", "{}", json.dumps(evidence("danger-full-access"))):
            with self.subTest(output=output), mock.patch.object(preflight, "_native_command", return_value=(0, output, "")):
                with self.assertRaises(preflight.PreflightError):
                    preflight.check("codex", policy("read-only"), self.project, self.run, self.request)

    def test_external_request_is_rejected_before_process_start(self):
        with mock.patch.object(preflight.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(preflight.PreflightError, "exact run directory"):
                preflight.check("codex", policy("read-only"), self.project, self.run, self.project / "request.md")
        popen.assert_not_called()
