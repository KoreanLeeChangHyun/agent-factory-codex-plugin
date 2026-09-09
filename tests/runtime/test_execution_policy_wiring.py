"""Policy persistence and launch boundaries, with isolated external processes."""
import runtime_test_home
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from native_fixtures import runtime, native_fixture


POLICY = runtime.execution_policy.normalize({"schemaVersion": 1, "sandboxPolicy": {"type": "danger-full-access"}, "approvalPolicy": "never"})


class ExecutionPolicyWiringTests(unittest.TestCase):
    def test_legacy_upgrade_requires_current_source_and_matching_sandbox(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(runtime.os.environ, {"AGENT_FACTORY_EXECUTION_POLICY": json.dumps(POLICY)}):
            root = Path(directory)
            args = runtime.parse_args(["send", "--agent", "legacy", "--message", "bounded"])
            self.assertEqual(runtime.resolve_execution_policy(args, root, {"sandbox": "danger-full-access"}), POLICY)
            with self.assertRaises(runtime.ContractError):
                runtime.resolve_execution_policy(args, root, {"sandbox": "read-only"})

    def test_legacy_queued_session_never_launches_without_policy_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = {"role": "work", "maxAttempts": 1, "codex": "/bin/true", "sandbox": "danger-full-access"}
            state = runtime.create_run(project_root=root, agent_id="legacy", actor="main", request=b"bounded", session=session)
            with mock.patch.object(runtime.execution_preflight, "check") as check, mock.patch.object(runtime, "spawn_contained_process") as spawn:
                with self.assertRaises(runtime.AttemptFailure) as raised:
                    runtime.run_codex_attempt(project_root=root, session=session, state=state, attempt=1,
                        heartbeat=mock.Mock(), cancel_event=threading.Event(), expected_agent_id="legacy", expected_run_id=state["runId"])
                self.assertEqual(raised.exception.code, "execution_policy_mismatch")
                check.assert_not_called()
                spawn.assert_not_called()

    def test_submit_binds_policy_to_session_run_and_dispatch_identity(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(runtime.os.environ, {"AGENT_FACTORY_EXECUTION_POLICY": json.dumps(POLICY)}):
            root = Path(directory)
            args = runtime.parse_args(["submit", "--project-root", str(root), "--agent", "policy-work", "--role", "work",
                                       "--codex", "/bin/true", "--message", "bounded", "--dispatch-id", "dispatch-policy"])
            with mock.patch.object(runtime, "spawn_worker", return_value=123), mock.patch.object(runtime, "emit") as emit:
                runtime.submit(args, True)
            state = runtime.safe_read_json(runtime.agent_directory(root, "policy-work") / "runs" / emit.call_args.args[0]["runId"] / "state.json")
            self.assertEqual(state["executionPolicy"], POLICY)
            self.assertEqual(state["dispatchTuple"]["executionPolicy"], POLICY)
            self.assertEqual(runtime.load_session(root, "policy-work")["executionPolicy"], POLICY)
            before = list(runtime.iter_run_states(root, "policy-work"))
            changed = {**POLICY, "sandboxPolicy": {"type": "read-only"}}
            send = runtime.parse_args(["send", "--project-root", str(root), "--agent", "policy-work", "--message", "next"])
            with mock.patch.dict(runtime.os.environ, {"AGENT_FACTORY_EXECUTION_POLICY": json.dumps(changed)}), mock.patch.object(runtime, "spawn_worker") as spawn:
                with self.assertRaises(runtime.ContractError):
                    runtime.submit(send, False)
                spawn.assert_not_called()
            self.assertEqual(len(list(runtime.iter_run_states(root, "policy-work"))), len(before))

    def test_failed_preflight_records_evidence_and_never_launches_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = {"role": "work", "maxAttempts": 1, "codex": "/bin/true", "projectRoot": str(root),
                       "sandbox": "danger-full-access", "executionPolicy": POLICY}
            state = runtime.create_run(project_root=root, agent_id="policy-work", actor="main", request=b"bounded", session=session)
            evidence = {"passed": False, "error": "exact run write denied"}
            with mock.patch.object(runtime.execution_preflight, "check", return_value=evidence) as check, mock.patch.object(runtime, "spawn_contained_process") as spawn:
                with self.assertRaises(runtime.AttemptFailure) as raised:
                    runtime.run_codex_attempt(project_root=root, session=session, state=state, attempt=1,
                        heartbeat=mock.Mock(), cancel_event=threading.Event(), expected_agent_id="policy-work", expected_run_id=state["runId"])
                self.assertEqual(raised.exception.code, "execution_preflight_failed")
                spawn.assert_not_called()
                check.assert_called_once_with("/bin/true", POLICY, root, Path(state["statePath"]).parent, Path(state["requestPath"]))
            self.assertEqual(runtime.safe_read_json(Path(state["statePath"]))["executionPreflight"], evidence)

    def test_child_environment_carries_current_policy_after_successful_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = {"role": "work", "maxAttempts": 1, "codex": "/bin/true", "projectRoot": str(root),
                       "sandbox": "danger-full-access", "executionPolicy": POLICY}
            state = runtime.create_run(project_root=root, agent_id="policy-work", actor="main", request=b"bounded", session=session)
            with mock.patch.object(runtime.execution_preflight, "check", return_value={"passed": True}), mock.patch.object(runtime, "spawn_contained_process", side_effect=OSError("fixture stop")) as spawn:
                with self.assertRaises(runtime.AttemptFailure):
                    runtime.run_codex_attempt(project_root=root, session=session, state=state, attempt=1,
                        heartbeat=mock.Mock(), cancel_event=threading.Event(), expected_agent_id="policy-work", expected_run_id=state["runId"])
                self.assertEqual(json.loads(spawn.call_args.kwargs["env"]["AGENT_FACTORY_EXECUTION_POLICY"]), POLICY)

    def test_native_backend_preserves_approval_policy(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = native_fixture(Path(directory), goal=False)
            bridge.session["executionPolicy"] = {**POLICY, "approvalPolicy": "on-request"}
            bridge.setup("bounded request")
            params = next(params for method, params in rpc.calls if method == "thread/resume")
            self.assertEqual(params["approvalPolicy"], "on-request")
