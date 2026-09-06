"""REAL installed Codex scheduler/adapter/transport with FAKE local model.

Never uses the account provider. Paid/live-model testing has been retired.
"""
import io
import json
import os
import queue
import shutil
import subprocess
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from test_native_codex import native, runtime
from mock_responses_provider import MockResponsesProvider


@unittest.skipUnless(os.environ.get('AF_VERIFY_LOCAL_CODEX') == '1', 'opt in to installed Codex with owned loopback fake model')
class InstalledSchedulerWithFakeModel(unittest.TestCase):
    def test_native_initial_reopen_accounting_controls_and_validation(self):
        evidence = {'label': 'REAL Codex scheduler/adapter/transport with FAKE model', 'rpc': [], 'runs': []}
        with tempfile.TemporaryDirectory(prefix='af-native-local-') as directory:
            root = Path(directory)
            home = root / 'codex-home'
            home.mkdir()
            request_root = root / 'project'
            request_root.mkdir()
            session = {'role': 'main', 'maxAttempts': 1, 'codex': os.environ.get('AF_VERIFY_CODEX', shutil.which('codex') or 'codex'),
                'projectRoot': str(request_root), 'sandbox': 'read-only', 'startTimeout': 15, 'goalMode': True,
                'nativeCapabilities': {'goal': True, 'fast': False}, 'sessionId': None}
            state = runtime.create_run(project_root=request_root, agent_id='main-local', actor='human', request=b'Owned deterministic scheduler exercise', session=session)
            state['goalObjective'] = 'Owned deterministic scheduler exercise'
            runtime.atomic_write_json(runtime.session_file(request_root, 'main-local'), session)
            with MockResponsesProvider(state['resultPath']) as provider:
                (home / 'config.toml').write_text('model = "fixture-model"\nmodel_provider = "fixture"\nmodel_reasoning_effort = "low"\n[features]\ngoals = true\nenable_request_compression = false\n[model_providers.fixture]\nname = "Owned local fixture"\nbase_url = ' + json.dumps(provider.base_url) + '\nwire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\nenv_key = "AF_LOCAL_DUMMY_TOKEN"\n')
                env = {key: value for key, value in os.environ.items() if key not in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_API_KEY', 'CODEX_HOME')}
                env.update({'CODEX_HOME': str(home), 'AF_LOCAL_DUMMY_TOKEN': 'dummy-local-only', 'NO_PROXY': '127.0.0.1,localhost'})
                def factory():
                    return subprocess.Popen([session['codex'], 'app-server', '--listen', 'stdio://'], cwd=request_root,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
                def observe(direction, value):
                    if len(evidence['rpc']) < 1000:
                        encoded = json.dumps(value)
                        evidence['rpc'].append({'direction': direction, 'value': value if len(encoded) < 16000 else {'truncated': encoded[:16000]}})
                rpc = native.Rpc(factory(), observer=observe, process_factory=factory)
                def guard_provider(connection):
                    original_call = connection.call
                    def call(method, params, timeout=15):
                        if method == 'thread/goal/set' and params.get('status') == 'active':
                            observed = original_call('thread/read', {'threadId': params['threadId'], 'includeTurns': False})
                            self.assertEqual(observed['thread']['modelProvider'], 'fixture', 'refusing nonlocal model activation')
                        return original_call(method, params, timeout)
                    connection.call = call
                guard_provider(rpc)
                bridge = native.Bridge(runtime, session, state, rpc)
                deadline = time.monotonic() + 90
                try:
                    with redirect_stdout(io.StringIO()):
                        bridge.setup('You are Main in an owned deterministic transport exercise. Do not run tools except native Goal tracking. Return the mandatory exact JSON on every turn. Leave the objective active on the first turn and complete it on the next native continuation.')
                    thread_id = bridge.thread_id
                    self.assertIsNotNone(thread_id)
                    first = self.collect(rpc, thread_id, deadline)
                    evidence['runs'].append(first)
                    self.assertGreaterEqual(len(first['turns']), 2, 'installed scheduler did not continue automatically')
                    self.assertEqual(first['goal']['status'], 'complete')
                    self.assertGreaterEqual(first['goal']['tokensUsed'], 110, 'native accounting excluded model usage')
                    self.assertFalse(provider.errors, provider.errors)
                    self.assertGreaterEqual(len(first['finals']), 2)
                    for text in first['finals']:
                        bridge.last_message = text
                        bridge.goal = first['goal']
                        with redirect_stdout(io.StringIO()): bridge.finish_turn()
                    usage = first['goal']['tokensUsed']
                    # Same objective, same exact thread, through a newly owned
                    # app-server process using the production adapter again.
                    provider.reset()
                    session.update({'sessionId': thread_id, 'goal': first['goal']})
                    reopen_state = {**state, 'goalAction': 'reopen'}
                    reopen_state.pop('goalObjective', None)
                    bridge = native.Bridge(runtime, session, reopen_state, rpc)
                    # setup initializes a fresh connection, as the worker does.
                    self.stop(rpc)
                    rpc = native.Rpc(factory(), observer=observe, process_factory=factory)
                    guard_provider(rpc)
                    bridge.rpc = rpc
                    with redirect_stdout(io.StringIO()): bridge.setup('Complete Main instructions for the same owned objective; use only native Goal tracking and return the mandatory JSON.')
                    self.assertEqual(bridge.thread_id, thread_id)
                    second = self.collect(rpc, thread_id, deadline)
                    evidence['runs'].append(second)
                    self.assertGreaterEqual(len(second['turns']), 2)
                    self.assertGreaterEqual(second['goal']['tokensUsed'], usage)
                    # Hold a response on the next automatic turn, so controls
                    # exercise real in-flight native work, still entirely local.
                    provider.reset('hold')
                    with redirect_stdout(io.StringIO()):
                        bridge.set_goal(status='active')
                    observed_turns = set()
                    while time.monotonic() < deadline and len(observed_turns) < 2:
                        try: event = rpc.event()
                        except queue.Empty: continue
                        if event.get('method') == 'turn/started':
                            bridge.turn_id = event['params']['turn']['id']
                            observed_turns.add(bridge.turn_id)
                    self.assertGreaterEqual(len(observed_turns), 2, 'no active native turn to interrupt')
                    with redirect_stdout(io.StringIO()):
                        bridge.control('pause')
                        paused = bridge.get_goal()
                        self.assertEqual(paused['status'], 'paused')
                        provider.release_response.set()
                        interrupted = False
                        while time.monotonic() < deadline:
                            try: event = rpc.event()
                            except queue.Empty: continue
                            if event.get('method') == 'turn/completed':
                                self.assertEqual(event['params']['turn']['status'], 'interrupted')
                                interrupted = True
                                break
                        self.assertTrue(interrupted, 'native pause did not interrupt the active turn')
                        bridge.turn_id = None
                        bridge.control('cancel')
                        self.assertIsNone(bridge.get_goal())
                    evidence['pause'] = paused
                    bridge.last_message = '{"status":"completed","resultPath":"wrong"}'
                    with self.assertRaises(native.NativeError): bridge.finish_turn()
                    self.assertLessEqual(provider.total_tokens, 1760)
                    # Activation, never turn/start, owns every model turn.
                    self.assertFalse(any(row['direction'] == 'send' and row['value'].get('method') == 'turn/start' for row in evidence['rpc']))
                except Exception as error:
                    evidence['failure'] = {'type': type(error).__name__, 'message': str(error)}
                    raise
                finally:
                    if bridge.thread_id:
                        try: evidence['clear'] = rpc.call('thread/goal/clear', {'threadId': bridge.thread_id}, timeout=2)
                        except Exception as error: evidence['clearError'] = str(error)
                    self.stop(rpc)
                    evidence['mockModel'] = {'requests': len(provider.requests), 'tokensReported': provider.total_tokens, 'errors': provider.errors}
                    if os.environ.get('AF_VERIFY_EVIDENCE'):
                        Path(os.environ['AF_VERIFY_EVIDENCE']).write_text(json.dumps(evidence, indent=2))

    def collect(self, rpc, thread_id, deadline):
        turns, finals, usage = set(), [], []
        while time.monotonic() < deadline:
            try: event = rpc.event()
            except queue.Empty: continue
            method, params = event.get('method'), event.get('params', {})
            if params.get('threadId') not in (None, thread_id): continue
            if method == 'turn/started': turns.add(params['turn']['id'])
            if method == 'thread/tokenUsage/updated': usage.append(params)
            if method == 'item/completed' and params.get('item', {}).get('type') == 'agentMessage' and params['item'].get('phase') != 'commentary':
                finals.append(params['item']['text'])
            if method == 'turn/completed':
                self.assertEqual(params['turn']['status'], 'completed', params['turn'].get('error'))
                goal = rpc.call('thread/goal/get', {'threadId': thread_id}).get('goal')
                if goal and goal['status'] == 'complete':
                    return {'threadId': thread_id, 'turns': sorted(turns), 'finals': finals, 'goal': goal, 'usage': usage}
            if method == 'error' and not params.get('willRetry'):
                self.fail(json.dumps(params))
        self.fail('real installed scheduler with fake model exceeded the shared 90-second bound')

    @staticmethod
    def stop(rpc):
        process = rpc.process
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None: stream.close()

    def test_bridge_run_delayed_consumption_validates_actual_final_turn(self):
        """REAL host, FAKE model; native history advances ahead of Bridge.run."""
        evidence = {'label': 'REAL Codex Bridge.run with FAKE local model and delayed event consumption', 'cases': []}
        shared_deadline = time.monotonic() + 90
        try:
            for outcome in ('invalid', 'failed', 'valid'):
                with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(prefix='af-delayed-native-') as directory:
                    root = Path(directory)
                    home, project = root / 'home', root / 'project'
                    home.mkdir()
                    project.mkdir()
                    session = {'role': 'main', 'maxAttempts': 1, 'codex': os.environ.get('AF_VERIFY_CODEX', shutil.which('codex') or 'codex'),
                        'projectRoot': str(project), 'sandbox': 'read-only', 'startTimeout': 15, 'goalMode': True,
                        'nativeCapabilities': {'goal': True, 'fast': False}, 'sessionId': None}
                    state = runtime.create_run(project_root=project, agent_id='main-delayed', actor='human',
                                               request=b'Owned deterministic scheduler exercise', session=session)
                    state['goalObjective'] = 'Owned deterministic scheduler exercise'
                    runtime.atomic_write_json(runtime.session_file(project, 'main-delayed'), session)
                    case = {'outcome': outcome, 'rpc': []}
                    evidence['cases'].append(case)
                    with MockResponsesProvider(state['resultPath']) as provider:
                        original_output = provider.output
                        def output(request, n):
                            item = original_output(request, n)
                            if n >= 3 and item['type'] == 'message':
                                item['content'][0]['text'] = json.dumps({
                                    'status': 'failed' if outcome == 'failed' else 'completed',
                                    'resultPath': 'wrong' if outcome == 'invalid' else state['resultPath']})
                            return item
                        provider.output = output
                        (home / 'config.toml').write_text('model = "fixture-model"\nmodel_provider = "fixture"\n[features]\ngoals = true\nenable_request_compression = false\n[model_providers.fixture]\nname = "Owned local fixture"\nbase_url = ' + json.dumps(provider.base_url) + '\nwire_api = "responses"\nrequires_openai_auth = false\nsupports_websockets = false\nenv_key = "AF_LOCAL_DUMMY_TOKEN"\n')
                        env = {key: value for key, value in os.environ.items() if key not in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_API_KEY', 'CODEX_HOME')}
                        env.update({'CODEX_HOME': str(home), 'AF_LOCAL_DUMMY_TOKEN': 'dummy-local-only', 'NO_PROXY': '127.0.0.1,localhost'})
                        def factory():
                            return subprocess.Popen([session['codex'], 'app-server', '--listen', 'stdio://'], cwd=project,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
                        def observe(direction, value):
                            if len(case['rpc']) < 1000:
                                encoded = json.dumps(value)
                                case['rpc'].append({'direction': direction, 'value': value if len(encoded) < 16000 else {'truncated': encoded[:16000]}})
                        rpc = native.Rpc(factory(), observer=observe, process_factory=factory)
                        original_call = rpc.call
                        def guarded_call(method, params, timeout=15):
                            if time.monotonic() >= shared_deadline:
                                raise native.NativeError('shared delayed-consumer test deadline exceeded')
                            if method == 'thread/goal/set' and params.get('status') == 'active':
                                thread = original_call('thread/read', {'threadId': params['threadId'], 'includeTurns': False})['thread']
                                self.assertEqual(thread['modelProvider'], 'fixture', 'refusing nonlocal activation')
                            return original_call(method, params, timeout)
                        rpc.call = guarded_call
                        bridge = native.Bridge(runtime, session, state, rpc)
                        original_setup = bridge.setup
                        def delayed_setup(prompt):
                            ready = original_setup(prompt)
                            # Do not fabricate notifications or drain pending
                            # events: wait for native history to prove both turns
                            # finished while the production consumer is held.
                            while time.monotonic() < shared_deadline:
                                history = rpc.call('thread/read', {'threadId': bridge.thread_id, 'includeTurns': True})['thread']
                                goal = rpc.call('thread/goal/get', {'threadId': bridge.thread_id}).get('goal')
                                turns = history.get('turns', [])
                                if len(turns) >= 2 and turns[-1]['status'] != 'inProgress' and goal and goal['status'] == 'complete':
                                    case['nativeHistoryBeforeConsumption'] = turns
                                    return ready
                                time.sleep(.02)
                            raise native.NativeError('native turns did not settle before delayed consumption deadline')
                        bridge.setup = delayed_setup
                        emitted = io.StringIO()
                        try:
                            with redirect_stdout(emitted):
                                if outcome == 'invalid':
                                    with self.assertRaisesRegex(native.NativeError, 'invalid mandatory terminal'):
                                        bridge.run('Complete Main instructions for this owned Goal. Use only native Goal tracking; return the exact required JSON on each turn.')
                                else:
                                    bridge.run('Complete Main instructions for this owned Goal. Use only native Goal tracking; return the exact required JSON on each turn.')
                            events = [json.loads(line) for line in emitted.getvalue().splitlines()]
                            case['adapterEvents'] = events
                            history = case['nativeHistoryBeforeConsumption']
                            finals = [event for event in events if event['type'] == 'item.completed' and event.get('item', {}).get('type') == 'agent_message']
                            consumed = [event['turn_id'] for event in events if event['type'] == 'turn.completed']
                            self.assertIn(history[-1]['id'], consumed, 'returned before consuming actual last turn completion')
                            self.assertGreaterEqual(len(consumed), 2)
                            if outcome == 'invalid':
                                self.assertEqual(finals, [], 'earlier valid answer escaped as a terminal result')
                            else:
                                self.assertEqual(len(finals), 1)
                                self.assertEqual(json.loads(finals[0]['item']['text']), {
                                    'status': 'failed' if outcome == 'failed' else 'completed', 'resultPath': state['resultPath']})
                            self.assertFalse(provider.errors, provider.errors)
                            self.assertFalse(any(row['direction'] == 'send' and row['value'].get('method') == 'turn/start' for row in case['rpc']))
                        except Exception as error:
                            case['failure'] = str(error)
                            case['adapterOutput'] = emitted.getvalue()
                            raise
                        finally:
                            if bridge.thread_id:
                                try: case['clear'] = original_call('thread/goal/clear', {'threadId': bridge.thread_id}, timeout=2)
                                except Exception as error: case['clearError'] = str(error)
                            self.stop(rpc)
                            case['mockModel'] = {'requests': len(provider.requests), 'tokensReported': provider.total_tokens, 'errors': provider.errors}
        finally:
            if os.environ.get('AF_VERIFY_EVIDENCE'):
                # Preserve the existing lifecycle test's separate evidence file.
                path = Path(os.environ['AF_VERIFY_EVIDENCE'])
                path.with_name(path.stem + '-delayed' + path.suffix).write_text(json.dumps(evidence, indent=2))
