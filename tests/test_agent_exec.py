from __future__ import annotations

import argparse
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent"
    / "scripts"
    / "exec.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("exec", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exec runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentExecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_build_prompt_embeds_each_validated_role_prompt(self) -> None:
        for role in ("main", "work", "verification"):
            with self.subTest(role=role):
                source = self.module.role_path(role).read_text(encoding="utf-8")
                prompt = self.module.build_prompt(
                    agent_id=f"{role}-agent", role=role,
                    request_path=Path("/managed/request.md"),
                    result_path=Path("/managed/result.md"), run_id="run-one",
                )
                self.assertIn(source, prompt)
                self.assertIn("<agent-factory-role-prompt>", prompt)

    def test_role_path_rejects_role_outside_graph(self) -> None:
        with self.assertRaises(self.module.ContractError) as raised:
            self.module.role_path("review")
        self.assertEqual(raised.exception.code, "role_not_found")

    def test_generated_result_path_schema_has_string_type_and_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            schema = json.loads(
                Path(state["responseSchemaPath"]).read_text(encoding="utf-8")
            )

        self.assertEqual(
            schema["properties"]["resultPath"],
            {"type": "string", "const": state["resultPath"]},
        )

    def dispatch_args(self, directory: str, dispatch_id: str, message: str = "bounded request") -> argparse.Namespace:
        return argparse.Namespace(
            project_root=Path(directory), agent="work-agent", actor="main", message=message,
            request_file=None, receipt_request_hash="a" * 64, verified_work_run_id=None,
            dispatch_id=dispatch_id, role="work", codex="/bin/true", sandbox=self.module.DEFAULT_SANDBOX,
            model=None, heartbeat_interval=5.0, heartbeat_timeout=20.0,
            start_timeout=60.0, turn_timeout=1800.0, max_attempts=2,
        )

    def test_dispatch_id_deduplicates_and_collisions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123) as spawn, mock.patch.object(self.module, "emit") as emit:
            self.module.submit(self.dispatch_args(directory, "dispatch-one"), True)
            first = emit.call_args.args[0]
            emit.reset_mock()
            self.module.submit(self.dispatch_args(directory, "dispatch-one"), True)
            duplicate = emit.call_args.args[0]
            self.assertEqual(first["runId"], duplicate["runId"])
            self.assertFalse(first["deduplicated"])
            self.assertTrue(duplicate["deduplicated"])
            self.assertEqual(spawn.call_count, 1)
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.submit(self.dispatch_args(directory, "dispatch-one", "different"), True)
            self.assertEqual(raised.exception.code, "dispatch_id_collision")

    def test_identical_requests_with_distinct_dispatches_create_distinct_runs_and_send_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123) as spawn, mock.patch.object(self.module, "emit") as emit:
            self.module.submit(self.dispatch_args(directory, "dispatch-submit"), True)
            send_one = self.dispatch_args(directory, "dispatch-send-one")
            send_two = self.dispatch_args(directory, "dispatch-send-two")
            outputs = []
            for values in (send_one, send_one, send_two):
                emit.reset_mock()
                self.module.submit(values, False)
                outputs.append(emit.call_args.args[0])
            self.assertEqual(outputs[0]["runId"], outputs[1]["runId"])
            self.assertNotEqual(outputs[0]["runId"], outputs[2]["runId"])
            self.assertTrue(outputs[1]["deduplicated"])
            self.assertEqual(spawn.call_count, 3)

    def test_crash_after_creation_before_ack_is_adopted_by_exact_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit", side_effect=RuntimeError("lost ack")):
            with self.assertRaises(RuntimeError):
                self.module.submit(self.dispatch_args(directory, "dispatch-crash"), True)
            states = list(self.module.iter_run_states(Path(directory), "work-agent"))
            self.assertEqual(len(states), 1)
            self.assertEqual(states[0]["dispatchId"], "dispatch-crash")

    def test_initial_dispatch_reservation_recovers_session_created_run_missing_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.dispatch_args(directory, "dispatch-initial-reserved")
            original_create_run = self.module.create_run
            calls = 0

            def crash_once(**values):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("crash after session creation")
                return original_create_run(**values)

            with mock.patch.object(self.module, "create_run", side_effect=crash_once), mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit") as emit:
                with self.assertRaises(RuntimeError):
                    self.module.submit(args, True)
                self.assertTrue(self.module.session_file(Path(directory), "work-agent").is_file())
                self.assertEqual(list(self.module.iter_run_states(Path(directory), "work-agent")), [])
                with self.assertRaises(self.module.ContractError) as collision:
                    self.module.submit(
                        self.dispatch_args(directory, "dispatch-initial-reserved", "different"),
                        True,
                    )
                self.assertEqual(collision.exception.code, "dispatch_id_collision")
                self.module.submit(args, True)
                recovered = emit.call_args.args[0]
                with self.assertRaises(self.module.ContractError) as established:
                    self.module.submit(
                        self.dispatch_args(directory, "dispatch-another-initial"), True
                    )

            self.assertEqual(recovered["dispatchId"], "dispatch-initial-reserved")
            self.assertFalse(recovered["deduplicated"])
            self.assertEqual(established.exception.code, "agent_exists")

    def test_worker_does_not_retry_failure_after_process_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.dispatch_args(directory, "dispatch-post-launch")
            with mock.patch.object(self.module, "spawn_worker", return_value=123), mock.patch.object(self.module, "emit"):
                self.module.submit(args, True)
            state = next(self.module.iter_run_states(root, "work-agent"))
            heartbeat = mock.Mock()
            worker_args = argparse.Namespace(
                project_root=root, agent="work-agent", run_id=state["runId"]
            )
            failure = self.module.AttemptFailure(
                "start_ack_missing", "process exited without a start event", False, True
            )
            original_update = self.module.update_json
            with mock.patch.object(self.module, "Heartbeat", return_value=heartbeat), mock.patch.object(self.module, "run_codex_attempt", side_effect=failure) as attempt, mock.patch.object(self.module, "update_json", wraps=original_update) as updates:
                outcome = self.module.worker(worker_args)
            final = self.module.safe_read_json(Path(state["statePath"]))

        self.assertEqual(outcome, 1)
        self.assertEqual(attempt.call_count, 1)
        self.assertEqual(final["attempt"], 1)
        self.assertEqual(final["startDisposition"], "launching")
        self.assertEqual(final["error"]["code"], "start_ack_missing")
        self.assertEqual(updates.call_count, 2)

    def test_reconcile_never_replays_ambiguous_or_started_stale_run(self) -> None:
        cases = (
            ("launching", {"startDisposition": "launching"}, None, "run_start_unknown"),
            ("thread-marker", {}, '{"type":"thread.started"}\n', "started_run_not_replayable"),
            ("started-at", {"startedAt": "2026-08-28T00:00:00Z"}, None, "started_run_not_replayable"),
            ("session", {"sessionId": "session-work"}, None, "started_run_not_replayable"),
        )
        for label, updates, events, expected_code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state = self.module.create_run(
                    project_root=root, agent_id="work-agent", actor="main",
                    request=b"bounded", session={"role": "work", "maxAttempts": 2},
                )
                self.module.atomic_write_json(
                    self.module.session_file(root, "work-agent"),
                    {"agentId": "work-agent", "role": "work", "sessionId": None,
                     "projectRoot": str(root), "heartbeatTimeout": 1},
                )
                persisted = self.module.safe_read_json(Path(state["statePath"]))
                persisted.update(updates)
                persisted.update(
                    {
                        "workerPid": 999999,
                        "workerIdentity": {"pid": 999999, "bootId": "old", "startTicks": 1},
                        "codexPid": 999998,
                        "codexIdentity": {"pid": 999998, "bootId": "old", "startTicks": 2},
                    }
                )
                self.module.atomic_write_json(Path(state["statePath"]), persisted)
                if events is not None:
                    self.module.atomic_write(Path(state["eventsPath"]), events.encode())
                heartbeat = self.module.safe_read_json(Path(state["heartbeatPath"]))
                heartbeat["observedAt"] = "2000-01-01T00:00:00Z"
                self.module.atomic_write_json(Path(state["heartbeatPath"]), heartbeat)
                args = argparse.Namespace(project_root=root, agent="work-agent")
                with mock.patch.object(self.module, "process_identity_status", return_value="dead"), mock.patch.object(self.module, "spawn_worker") as spawn, mock.patch.object(self.module, "emit") as emit:
                    self.module.command_reconcile(args)
                final = self.module.safe_read_json(Path(state["statePath"]))
                self.assertEqual(emit.call_args.args[0]["runs"][0]["action"], "failed-not-replayable")
                self.assertEqual(final["error"]["code"], expected_code)
                spawn.assert_not_called()

    def test_reconcile_resubmits_only_explicit_not_started_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root, agent_id="work-agent", actor="main",
                request=b"bounded", session={"role": "work", "maxAttempts": 2},
            )
            self.module.atomic_write_json(
                self.module.session_file(root, "work-agent"),
                {"agentId": "work-agent", "role": "work", "sessionId": None,
                 "projectRoot": str(root), "heartbeatTimeout": 1},
            )
            heartbeat = self.module.safe_read_json(Path(state["heartbeatPath"]))
            heartbeat["observedAt"] = "2000-01-01T00:00:00Z"
            self.module.atomic_write_json(Path(state["heartbeatPath"]), heartbeat)
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update(
                {
                    "workerPid": 77,
                    "workerIdentity": {"pid": 77, "bootId": "old", "startTicks": 3},
                }
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(project_root=root, agent="work-agent")
            with mock.patch.object(self.module, "process_identity_status", return_value="mismatch"), mock.patch.object(self.module, "spawn_worker", return_value=42) as spawn, mock.patch.object(self.module, "emit") as emit:
                self.module.command_reconcile(args)
        spawn.assert_called_once_with(root, "work-agent", state["runId"])
        self.assertEqual(emit.call_args.args[0]["runs"][0]["action"], "resubmitted")

    def test_linux_process_identity_matches_exact_start_and_detects_pid_reuse(self) -> None:
        expected = {"pid": 41, "bootId": "boot", "startTicks": 99}
        with mock.patch.object(self.module, "linux_process_identity", return_value=expected):
            self.assertEqual(self.module.process_identity_status(expected), "match")
            self.assertEqual(
                self.module.process_identity_status(
                    {"pid": 41, "bootId": "boot", "startTicks": 98}
                ),
                "mismatch",
            )

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_attempt_group_termination_reaches_nested_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "child.pid"
            script = (
                "import pathlib,subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(child_path)],
                start_new_session=True,
            )
            deadline = time.monotonic() + 5
            while not child_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            child_pid = int(child_path.read_text())
            identity = self.module.linux_process_identity(process.pid)
            self.module.terminate_attempt_group(process, identity)
            deadline = time.monotonic() + 2
            while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(Path(f"/proc/{child_pid}").exists())

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_attempt_group_termination_cleans_child_after_leader_exits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "child.pid"
            release_path = Path(directory) / "release"
            script = (
                "import os,pathlib,subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
                "release=pathlib.Path(sys.argv[2]); "
                "exec('while not release.exists(): time.sleep(0.01)'); os._exit(0)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(child_path), str(release_path)],
                start_new_session=True,
            )
            identity = self.module.linux_process_identity(process.pid)
            deadline = time.monotonic() + 5
            while not child_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            child_pid = int(child_path.read_text())
            release_path.touch()
            process.wait(timeout=5)
            self.assertTrue(Path(f"/proc/{child_pid}").exists())
            self.module.terminate_attempt_group(process, identity)
            deadline = time.monotonic() + 2
            while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(Path(f"/proc/{child_pid}").exists())

    def test_post_exit_failure_invokes_group_cleanup_before_returning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 101
            fake_process.stdin = io.StringIO()
            fake_process.stdout = io.StringIO("")
            fake_process.stderr = io.StringIO("")
            fake_process.wait.return_value = 1
            session = {
                "codex": "codex",
                "projectRoot": str(root),
                "sandbox": "workspace-write",
                "sessionId": None,
                "startTimeout": 5,
                "turnTimeout": 5,
            }
            identity = {"pid": 101, "bootId": "boot", "startTicks": 7}
            with mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, 55)), mock.patch.object(self.module, "release_contained_process"), mock.patch.object(self.module, "terminate_attempt_group") as terminate:
                with self.assertRaises(self.module.AttemptFailure) as raised:
                    self.module.run_codex_attempt(
                        project_root=root,
                        session=session,
                        state=state,
                        attempt=1,
                        heartbeat=mock.Mock(),
                        cancel_event=self.module.threading.Event(),
                        expected_agent_id="work-agent",
                        expected_run_id=state["runId"],
                    )
            self.assertEqual(raised.exception.code, "codex_failed")
            terminate.assert_called_once_with(fake_process, identity)

    def test_codex_pre_release_failure_aborts_barrier_without_pid_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 202
            fake_process.wait.return_value = 125
            release_read, release_write = os.pipe()
            failure = self.module.ContractError(
                "process_identity_unavailable", "identity unavailable"
            )
            identity = {"pid": 202, "bootId": "boot", "startTicks": 8}
            session = {
                "codex": "codex",
                "projectRoot": str(root),
                "sandbox": "workspace-write",
                "sessionId": None,
                "startTimeout": 5,
                "turnTimeout": 5,
            }
            heartbeat = mock.Mock()
            heartbeat.update.side_effect = failure
            with mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, release_write)):
                with self.assertRaises(self.module.AttemptFailure) as raised:
                    self.module.run_codex_attempt(
                        project_root=root,
                        session=session,
                        state=state,
                        attempt=1,
                        heartbeat=heartbeat,
                        cancel_event=self.module.threading.Event(),
                        expected_agent_id="work-agent",
                        expected_run_id=state["runId"],
                    )
            self.assertEqual(raised.exception.code, "process_identity_unavailable")
            self.assertEqual(os.read(release_read, 1), b"")
            os.close(release_read)
            fake_process.kill.assert_not_called()
            fake_process.terminate.assert_not_called()

    def test_worker_pre_release_failure_aborts_barrier_without_pid_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            fake_process = mock.Mock()
            fake_process.pid = 303
            fake_process.wait.return_value = 125
            release_read, release_write = os.pipe()
            failure = self.module.ContractError(
                "process_identity_unavailable", "identity unavailable"
            )
            identity = {"pid": 303, "bootId": "boot", "startTicks": 9}
            with mock.patch.object(self.module, "spawn_contained_process", return_value=(fake_process, identity, release_write)), mock.patch.object(self.module, "update_json", side_effect=failure):
                with self.assertRaises(self.module.ContractError) as raised:
                    self.module.spawn_worker(root, "work-agent", state["runId"])
            self.assertEqual(raised.exception.code, "process_identity_unavailable")
            self.assertEqual(os.read(release_read, 1), b"")
            os.close(release_read)
            fake_process.kill.assert_not_called()
            fake_process.terminate.assert_not_called()

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_readiness_timeout_terminates_only_verified_bootstrap_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "timeout-child.pid"
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )
            real_popen = subprocess.Popen
            real_killpg = os.killpg
            launched: dict[str, subprocess.Popen] = {}

            def nonready_bootstrap(_command, **options):
                script = (
                    "import pathlib,subprocess,sys,time; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
                )
                process = real_popen(
                    [sys.executable, "-c", script, str(child_path)],
                    cwd=options.get("cwd"),
                    pass_fds=options["pass_fds"],
                    start_new_session=True,
                    close_fds=True,
                )
                launched["process"] = process
                return process

            try:
                with mock.patch.object(self.module, "CONTAINMENT_START_TIMEOUT", 0.5), mock.patch.object(self.module, "PROCESS_TERM_TIMEOUT", 0.05), mock.patch.object(self.module.subprocess, "Popen", side_effect=nonready_bootstrap), mock.patch.object(self.module.os, "killpg", wraps=real_killpg) as killpg:
                    with self.assertRaises(self.module.ContractError) as raised:
                        self.module.spawn_contained_process(["ignored"])
                self.assertEqual(raised.exception.code, "containment_start_failed")
                leader_pid = launched["process"].pid
                signalled_groups = {call.args[0] for call in killpg.call_args_list}
                self.assertEqual(signalled_groups, {leader_pid})
                deadline = time.monotonic() + 2
                while Path(f"/proc/{leader_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{leader_pid}").exists())
                self.assertTrue(child_path.exists())
                child_pid = int(child_path.read_text())
                deadline = time.monotonic() + 2
                while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{child_pid}").exists())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    @unittest.skipUnless(sys.platform == "linux", "Linux process groups are required")
    def test_pre_release_abort_terminates_only_verified_bootstrap_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_path = Path(directory) / "abort-child.pid"
            unrelated = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                start_new_session=True,
            )
            real_popen = subprocess.Popen
            real_killpg = os.killpg
            launched: dict[str, subprocess.Popen] = {}

            def nonexiting_bootstrap(_command, **options):
                ready_fd = options["pass_fds"][0]
                script = (
                    "import os,pathlib,subprocess,sys,time; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
                    "os.write(int(sys.argv[2]),b'R'); time.sleep(60)"
                )
                process = real_popen(
                    [sys.executable, "-c", script, str(child_path), str(ready_fd)],
                    cwd=options.get("cwd"),
                    pass_fds=options["pass_fds"],
                    start_new_session=True,
                    close_fds=True,
                )
                launched["process"] = process
                return process

            try:
                with mock.patch.object(self.module, "PROCESS_TERM_TIMEOUT", 0.05), mock.patch.object(self.module.subprocess, "Popen", side_effect=nonexiting_bootstrap), mock.patch.object(self.module.os, "killpg", wraps=real_killpg) as killpg:
                    process, identity, release_fd = self.module.spawn_contained_process(
                        ["ignored"]
                    )
                    self.module.abort_contained_process(process, identity, release_fd)
                leader_pid = launched["process"].pid
                signalled_groups = {call.args[0] for call in killpg.call_args_list}
                self.assertEqual(signalled_groups, {leader_pid})
                deadline = time.monotonic() + 2
                while Path(f"/proc/{leader_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{leader_pid}").exists())
                self.assertTrue(child_path.exists())
                child_pid = int(child_path.read_text())
                deadline = time.monotonic() + 2
                while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertFalse(Path(f"/proc/{child_pid}").exists())
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_aggregate_event_and_stderr_caps_never_grow_past_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "events.jsonl"
            with mock.patch.object(self.module, "MAX_EVENTS_BYTES", 8):
                self.assertTrue(self.module.append_event(event_path, "1234"))
                self.assertFalse(self.module.append_event(event_path, "56789"))
            self.assertEqual(event_path.stat().st_size, 4)

            stderr_path = Path(directory) / "stderr.log"
            output = self.module.queue.Queue()
            with mock.patch.object(self.module, "MAX_STDERR_BYTES", 4):
                self.module.stream_stderr(io.StringIO("12345"), stderr_path, output)
            self.assertEqual(output.get_nowait()[0], "stderr_overflow")
            self.assertEqual(stderr_path.read_bytes(), b"")

    def test_terminal_transition_atomically_clears_active_codex_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            identity = {"pid": 17, "bootId": "boot", "startTicks": 5}
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update(
                {"codexPid": 17, "codexIdentity": identity, "lastCodexIdentity": identity}
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            self.module.mark_terminal(Path(state["statePath"]), "failed")
            final = self.module.safe_read_json(Path(state["statePath"]))
            self.assertIsNone(final["codexPid"])
            self.assertIsNone(final["codexIdentity"])
            self.assertEqual(final["lastCodexIdentity"], identity)

    def test_cancel_refuses_reused_pid_without_signalling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded",
                session={"role": "work", "maxAttempts": 1},
            )
            persisted = self.module.safe_read_json(Path(state["statePath"]))
            persisted.update(
                {"workerIdentity": {"pid": 22, "bootId": "old", "startTicks": 1}}
            )
            self.module.atomic_write_json(Path(state["statePath"]), persisted)
            args = argparse.Namespace(
                project_root=root, agent="work-agent", run_id=state["runId"]
            )
            with mock.patch.object(self.module, "process_identity_status", return_value="mismatch"), mock.patch.object(self.module.os, "kill") as kill:
                with self.assertRaises(self.module.ContractError) as raised:
                    self.module.command_cancel(args)
            self.assertEqual(raised.exception.code, "process_identity_mismatch")
            kill.assert_not_called()

    def test_new_command_keeps_configured_sandbox_without_bypass(self) -> None:
        command = self.module.build_codex_command(
            {
                "codex": "codex",
                "projectRoot": "/tmp/project",
                "sandbox": "danger-full-access",
            },
            {"responseSchemaPath": "/tmp/schema.json"},
            None,
        )

        self.assertIn("--sandbox", command)
        self.assertIn("danger-full-access", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_submit_defaults_new_session_sandbox_and_preserves_explicit_overrides(self) -> None:
        base = ["submit", "--agent", "work-agent", "--role", "work"]

        self.assertEqual(
            self.module.parse_args(base).sandbox,
            "danger-full-access",
        )
        for sandbox in self.module.SANDBOXES:
            with self.subTest(sandbox=sandbox):
                self.assertEqual(
                    self.module.parse_args([*base, "--sandbox", sandbox]).sandbox,
                    sandbox,
                )

    def test_resume_reasserts_project_root_and_stored_sandbox(self) -> None:
        for sandbox in ("danger-full-access", "workspace-write", "read-only"):
            with self.subTest(sandbox=sandbox):
                command = self.module.build_codex_command(
                    {
                        "codex": "codex",
                        "projectRoot": "/tmp/project",
                        "sandbox": sandbox,
                    },
                    {
                        "responseSchemaPath": "/tmp/schema.json",
                    },
                    "session-1",
                )

                self.assertEqual(
                    command[:7],
                    [
                        "codex",
                        "exec",
                        "--cd",
                        "/tmp/project",
                        "--sandbox",
                        sandbox,
                        "resume",
                    ],
                )
                self.assertEqual(
                    command[7:],
                    [
                        "--json",
                        "--output-schema",
                        "/tmp/schema.json",
                        "session-1",
                        "-",
                    ],
                )
                self.assertNotIn(
                    "--dangerously-bypass-approvals-and-sandbox", command
                )

    def test_sandbox_failure_classification_requires_observed_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stderr_path = Path(directory) / "stderr.log"
            stderr_path.write_text(
                "apply_patch verification failed: fs sandbox helper failed with status "
                "exit status: 1: bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )

            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "sandbox_unavailable")

            stderr_path.write_text(
                "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted\n",
                encoding="utf-8",
            )
            failure = self.module.missing_result_failure(stderr_path)
            self.assertEqual(failure.code, "result_file_missing")

    def test_work_receipt_requires_exact_binding_and_no_test_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "work-receipt",
                "runId": state["runId"],
                "requestHash": state["requestHash"],
                "outcome": "implemented",
                "changedPaths": ["skills/agent/SKILL.md"],
                "addressedFindingIds": [],
                "tests": {"run": False, "reason": "work-agent-prohibited"},
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")

            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                ),
                receipt,
            )
            receipt["tests"]["run"] = True
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_tests_invalid")

    def test_verification_receipt_enforces_unique_ids_and_decision_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = self.module.create_run(
                project_root=Path(directory),
                agent_id="verification-agent",
                actor="main",
                request=b"verification request",
                session={"role": "verification", "maxAttempts": 1},
                receipt_request_hash="a" * 64,
                verified_work_run_id="run-work-1",
            )
            finding = {
                "id": "REV-001",
                "path": "skills/agent/scripts/exec.py",
                "location": "validate_receipt",
                "problem": "binding is not checked",
                "evidence": "the expected value is available in state",
                "correction": "compare the exact values",
            }
            receipt = {
                "schemaVersion": "0.1.0",
                "kind": "verification-receipt",
                "runId": state["runId"],
                "verifiedWorkRunId": "run-work-1",
                "verifiedRequestHash": "a" * 64,
                "decision": "fail",
                "findings": [finding],
            }
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                ),
                receipt,
            )

            receipt["verifiedWorkRunId"] = "run-work-other"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as binding_error:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(binding_error.exception.code, "receipt_binding_invalid")
            receipt["verifiedWorkRunId"] = "run-work-1"

            receipt["decision"] = "pass"
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_decision_invalid")

            receipt["decision"] = "fail"
            receipt["findings"] = [finding, finding]
            Path(state["receiptPath"]).write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    Path(directory), state, agent_id="verification-agent", run_id=state["runId"]
                )
            self.assertEqual(raised.exception.code, "receipt_invalid")

    def test_receipt_rejects_adjacent_noncanonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            Path(state["resultPath"]).write_text("result\n", encoding="utf-8")
            adjacent = Path(state["resultPath"]).parent.parent / "adjacent-receipt.json"
            adjacent.write_text("{}\n", encoding="utf-8")
            state["receiptPath"] = str(adjacent)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")

    def test_receipt_rejects_symlinked_run_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.module.create_run(
                project_root=root,
                agent_id="work-agent",
                actor="main",
                request=b"bounded request",
                session={"role": "work", "maxAttempts": 1},
            )
            run_path = Path(state["statePath"]).parent
            relocated = run_path.parent / f"{run_path.name}-relocated"
            run_path.rename(relocated)
            run_path.symlink_to(relocated, target_is_directory=True)

            with self.assertRaises(self.module.ContractError) as raised:
                self.module.validate_receipt(
                    root, state, agent_id="work-agent", run_id=state["runId"]
                )

        self.assertEqual(raised.exception.code, "receipt_path_invalid")


if __name__ == "__main__":
    unittest.main()
