"""Subprocess transport coverage, plus separately opted-in live model evidence."""
import runtime_test_home  # Isolate all runtime subprocesses from the real home.

import io
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from contextlib import redirect_stdout
from native_fixtures import native, runtime, native_fixture


class RevisionContracts(unittest.TestCase):
    def test_legacy_off_overrides_config_on_initial_and_exact_resume(self):
        for thread in (None, 'exact-thread'):
            session = {'codex': 'codex', 'sandbox': 'read-only', 'executionPolicy': runtime_test_home.policy('read-only'), 'projectRoot': '/tmp', 'fast': False}
            command = runtime.build_codex_command(session, {'responseSchemaPath': '/tmp/schema', 'statePath':'/tmp/run/state.json'}, thread)
            self.assertIn('service_tier="default"', command)
            self.assertIn('features.goals=false', command)
            if thread:
                self.assertEqual(command[-2], thread)
            session.pop('fast')
            self.assertNotIn('service_tier="default"', runtime.build_codex_command(session, {'responseSchemaPath': '/tmp/schema', 'statePath':'/tmp/run/state.json'}, thread))

    def test_fast_without_goal_schema_never_calls_goal(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = native_fixture(Path(directory), fast=True, goal=False)
            bridge.session['nativeCapabilities'] = {'fast': True, 'goal': False}
            bridge = native.Bridge(runtime, bridge.session, bridge.state, rpc)
            bridge.setup('bounded Main')
            self.assertFalse(any(method.startswith('thread/goal/') for method, _ in rpc.calls))
            self.assertEqual(next(params for method, params in rpc.calls if method == 'turn/start')['serviceTier'], 'priority')

    def test_uncertainty_survives_full_log_and_session_restore(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, _, state = native_fixture(Path(directory))
            with mock.patch.object(runtime, 'append_event', return_value=False):
                runtime.record_goal_uncertainty(Path(state['statePath']), 'pause unconfirmed')
            saved = runtime.safe_read_json(runtime.session_file(Path(directory), state['agentId']))
            self.assertEqual(saved['goalError'], 'pause unconfirmed')
            self.assertEqual(runtime.public_state(runtime.safe_read_json(Path(state['statePath'])))['goalError'], 'pause unconfirmed')

    def test_stalled_pause_records_uncertainty(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            _, _, state = native_fixture(Path(directory))
            path = Path(state['statePath'])
            runtime.update_json(path, path.parent / '.state.lock', lambda value: value.update({'goal': {'status': 'active'}}))
            with mock.patch.object(runtime.time, 'monotonic', side_effect=[0, 0, 4]), mock.patch.object(runtime.time, 'sleep'):
                runtime.wait_native_pause(path)
            self.assertIn('unconfirmed', runtime.safe_read_json(runtime.session_file(Path(directory), state['agentId']))['goalError'])


class ActivationAndFramingRegressions(unittest.TestCase):
    def test_start_and_reopen_reload_paused_goal_before_native_activation(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
                bridge, rpc, state = native_fixture(Path(directory), existing=existing, action='reopen' if existing else None)
                if existing:
                    state.pop('goalObjective')
                    rpc.goal = {'threadId': 'thread-exact', 'objective': 'preserve objective', 'status': 'active', 'tokensUsed': 25, 'timeUsedSeconds': 4}
                bridge.setup('complete Main role and exact managed request')
                methods = [method for method, _ in rpc.calls]
                self.assertEqual(methods.count('turn/start'), 0)
                reload_index = methods.index('owned/restart')
                enabled = [(i, params) for i, (method, params) in enumerate(rpc.calls) if method == 'thread/resume' and params.get('config', {}).get('features.goals') is True]
                self.assertEqual(len(enabled), 1)
                self.assertGreater(enabled[0][0], reload_index)
                self.assertIn('complete Main role and exact managed request', enabled[0][1]['developerInstructions'])
                self.assertIn(state['resultPath'], enabled[0][1]['developerInstructions'])
                self.assertEqual(rpc.goal['status'], 'active')
                if existing:
                    self.assertEqual(rpc.goal['tokensUsed'], 25)
                    self.assertEqual(rpc.goal['objective'], 'preserve objective')

    def test_reload_failure_does_not_activate_goal(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            bridge, rpc, _ = native_fixture(Path(directory))
            rpc.restart_owned = mock.Mock(side_effect=native.NativeError('owner did not stop'))
            with self.assertRaisesRegex(native.NativeError, 'owner did not stop'):
                bridge.run('Main role')
            self.assertEqual(rpc.goal['status'], 'paused')
            self.assertFalse(any(method == 'turn/start' for method, _ in rpc.calls))

    def test_terminal_result_contract_remains_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge, _, _ = native_fixture(Path(directory))
            for text in ('not JSON', '{"status":"completed","resultPath":"wrong"}', '{"status":"completed"}'):
                bridge.last_message = text
                with self.assertRaises((native.NativeError, ValueError)):
                    bridge.finish_turn()

    def test_latest_failed_or_interrupted_native_turn_cannot_accept_earlier_answer(self):
        for status in ('failed', 'interrupted'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
                bridge, rpc, state = native_fixture(Path(directory))
                setup = bridge.setup
                terminal = json.dumps({'status': 'completed', 'resultPath': state['resultPath']})
                events = [
                    {'method': 'turn/started', 'params': {'threadId': 'thread-exact', 'turn': {'id': 'first'}}},
                    {'method': 'item/completed', 'params': {'threadId': 'thread-exact', 'turnId': 'first', 'item': {'type': 'agentMessage', 'text': terminal}}},
                    {'method': 'turn/completed', 'params': {'threadId': 'thread-exact', 'turn': {'id': 'first', 'status': 'completed'}}},
                    {'method': 'turn/started', 'params': {'threadId': 'thread-exact', 'turn': {'id': 'last'}}},
                    {'method': 'turn/completed', 'params': {'threadId': 'thread-exact', 'turn': {'id': 'last', 'status': status, 'error': {'message': 'native final failure'}}}},
                ]
                def delayed_setup(prompt):
                    ready = setup(prompt)
                    rpc.goal['status'] = 'complete'
                    rpc.history = [{'id': 'first', 'status': 'completed'}, {'id': 'last', 'status': status}]
                    return ready
                bridge.setup = delayed_setup
                rpc.event = lambda: events.pop(0)
                with self.assertRaisesRegex(native.NativeError, status):
                    bridge.run('Main role and exact request')
                emitted = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertFalse(any(event['type'] == 'item.completed' for event in emitted))
                self.assertIn('last', bridge.completed_turns)

    def test_repeated_pause_warnings_and_next_event_are_separate_jsonl_records(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            _, _, state = native_fixture(Path(directory))
            runtime.record_goal_uncertainty(Path(state['statePath']), 'warning one')
            runtime.record_goal_uncertainty(Path(state['statePath']), 'warning two')
            runtime.append_event(Path(state['eventsPath']), json.dumps({'type': 'turn.completed'}) + '\n')
            raw = Path(state['eventsPath']).read_text()
            self.assertTrue(raw.endswith('\n'))
            events = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([event['type'] for event in events], ['goal.error', 'goal.error', 'turn.completed'])
            self.assertEqual(runtime.safe_read_json(runtime.session_file(Path(directory), state['agentId']))['goalError'], 'warning two')


class SubprocessRpcTests(unittest.TestCase):
    def start_child(self, source):
        process = subprocess.Popen([sys.executable, '-u', '-c', source], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        self.addCleanup(self.stop_child, process)
        return process, native.Rpc(process)

    @staticmethod
    def stop_child(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None: stream.close()

    def test_real_pipe_framing_notifications_and_control_response(self):
        process, rpc = self.start_child('''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 print(json.dumps({'method':'thread/goal/updated','params':{'threadId':'exact','goal':{'status':'paused'}}}),flush=True)
 reply=json.dumps({'id':r['id'],'result':{'accepted':r['method']}})+'\\n'
 for part in [reply[:8],reply[8:]]:
  sys.stdout.write(part);sys.stdout.flush()
''')
        self.assertEqual(rpc.call('turn/interrupt', {'threadId': 'exact', 'turnId': 'one'})['accepted'], 'turn/interrupt')
        self.assertEqual(rpc.event()['method'], 'thread/goal/updated')

    def test_malformed_frame_and_stalled_rpc_fail_bounded(self):
        _, rpc = self.start_child("import sys,time;sys.stdin.readline();print('not-json',flush=True);time.sleep(10)")
        with self.assertRaises(ValueError):
            rpc.call('initialize', {}, timeout=1)
        _, stalled = self.start_child('import time;time.sleep(10)')
        with self.assertRaisesRegex(native.NativeError, 'timed out'):
            stalled.call('thread/goal/set', {}, timeout=.2)

    def test_pending_queue_overflow_is_bounded(self):
        _, rpc = self.start_child("import sys,json,time;sys.stdin.readline();[print(json.dumps({'method':'event','params':{}}),flush=True) for _ in range(130)];time.sleep(10)")
        with self.assertRaisesRegex(native.NativeError, 'pending'):
            rpc.call('initialize', {}, timeout=2)

    def test_managed_group_contains_adapter_and_native_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child.json'
            source = "import subprocess,sys,json,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);Path(sys.argv[1]).write_text(json.dumps({'pid':p.pid}));time.sleep(60)"
            process, identity, release = runtime.spawn_contained_process([sys.executable, '-c', source, str(marker)],
                cwd=Path(directory), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                runtime.release_contained_process(process, identity, release)
                deadline = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(marker.exists(), 'native child did not start')
                child = json.loads(marker.read_text())['pid']
                child_identity = runtime.linux_process_identity(child)
                runtime.terminate_attempt_group(process, identity)
                self.assertIsNotNone(process.poll())
                self.assertEqual(runtime.process_identity_status(child_identity), 'dead')
            finally:
                runtime.terminate_attempt_group(process, identity)


