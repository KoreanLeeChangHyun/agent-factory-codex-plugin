"""Response delivery exercises the real attempt boundary without model file I/O."""
import runtime_test_home
import io
import json
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from contextlib import redirect_stdout
from native_fixtures import runtime as rt, native_fixture


class RuntimeResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def new_run(self, role='main'):
        return rt.create_run(project_root=self.root, agent_id=role+'-response', actor='main',
                             request=b'bounded response', session={'role': role, 'maxAttempts': 1})

    def envelope(self, state, **values):
        return {'status': 'completed', 'resultPath': state['resultPath'],
                'resultText': '안녕하세요!\n**Answer**\n', **values}

    def attempt(self, state, terminal, *, return_code=0):
        events = [{'type': 'thread.started', 'thread_id': 'session-response'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Progress only'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(terminal)}}]
        process = Mock(pid=101, stdin=io.StringIO(), stderr=io.StringIO(),
                       stdout=io.StringIO(''.join(json.dumps(e)+'\n' for e in events)))
        process.wait.return_value = return_code
        session = {'codex': 'codex', 'role': state['role'], 'projectRoot': str(self.root),
                   'executionPolicy': runtime_test_home.policy('workspace-write', self.root),
                   'sessionId': 'session-response', 'startTimeout': 5, 'turnTimeout': 5}
        rt.atomic_write_json(rt.session_file(self.root, state['agentId']), session)
        identity = {'pid': 101, 'bootId': 'fixture', 'startTicks': 7}
        with patch.object(rt.execution_preflight, 'check', return_value={'passed': True}), \
             patch.object(rt, 'spawn_contained_process', return_value=(process, identity, 55)), \
             patch.object(rt, 'release_contained_process'), patch.object(rt, 'terminate_attempt_group'):
            return rt.run_codex_attempt(project_root=self.root, session=session, state=state,
                attempt=1, heartbeat=Mock(), cancel_event=threading.Event(),
                expected_agent_id=state['agentId'], expected_run_id=state['runId'])

    def test_attempt_persists_answer_without_model_file_writes(self):
        for status in ('completed', 'needs-human-decision', 'failed'):
            with self.subTest(status=status):
                state = self.new_run()
                response = self.envelope(state, status=status)
                self.assertFalse(Path(state['resultPath']).exists())
                self.assertEqual(self.attempt(state, response), (status, 'session-response'))
                self.assertEqual(Path(state['resultPath']).read_text(), response['resultText'])
                self.assertEqual(stat.S_IMODE(Path(state['resultPath']).stat().st_mode), 0o600)

    def test_failed_process_does_not_publish_even_valid_answer(self):
        state = self.new_run()
        with self.assertRaises(rt.AttemptFailure) as raised:
            self.attempt(state, self.envelope(state), return_code=1)
        self.assertEqual(raised.exception.code, 'codex_failed')
        self.assertFalse(Path(state['resultPath']).exists())

    def test_invalid_envelopes_do_not_publish_or_fall_back_to_file(self):
        state = self.new_run()
        invalid = [self.envelope(state, resultText=value) for value in
                   ('', ' \n', None, 42, '\ud800', '가' * 22000)]
        invalid += [self.envelope(state, status=[]), self.envelope(state, resultPath='/tmp/wrong'),
                    self.envelope(state, extra=True), {'status':'completed', 'resultPath':state['resultPath']}]
        for response in invalid:
            with self.subTest(response_keys=list(response)):
                with self.assertRaises(rt.ContractError):
                    rt.publish_terminal_result(response, state)
                self.assertFalse(Path(state['resultPath']).exists())

    def test_publish_refuses_symlink_and_nonregular_destination(self):
        state = self.new_run()
        path = Path(state['resultPath'])
        target = self.root / 'unrelated.txt'
        target.write_text('keep')
        path.symlink_to(target)
        with self.assertRaises(rt.ContractError):
            rt.publish_terminal_result(self.envelope(state), state)
        self.assertEqual(target.read_text(), 'keep')
        path.unlink()
        path.mkdir()
        with self.assertRaises(rt.ContractError):
            rt.publish_terminal_result(self.envelope(state), state)

    def test_legacy_schema_preserves_file_and_rejects_new_envelope(self):
        state = self.new_run()
        rt.atomic_write_json(Path(state['responseSchemaPath']),
                             rt.response_schema_document(state['resultPath'], inline=False))
        Path(state['resultPath']).write_text('legacy answer')
        terminal = {'status': 'completed', 'resultPath': state['resultPath']}
        self.assertEqual(self.attempt(state, terminal)[0], 'completed')
        self.assertEqual(Path(state['resultPath']).read_text(), 'legacy answer')
        with self.assertRaises(rt.ContractError):
            rt.publish_terminal_result(self.envelope(state), state)
        schema = rt.safe_read_json(Path(state['responseSchemaPath']))
        schema['additionalProperties'] = True
        rt.atomic_write_json(Path(state['responseSchemaPath']), schema)
        with self.assertRaises(rt.ContractError):
            rt.validate_terminal_result(terminal, state)

    def test_completed_work_still_requires_bound_receipt(self):
        state = self.new_run('work')
        with self.assertRaises(rt.AttemptFailure) as raised:
            self.attempt(state, self.envelope(state))
        self.assertIn('receipt', raised.exception.code)
        rt.atomic_write_json(Path(state['receiptPath']), {
            'schemaVersion': '0.1.0', 'kind': 'work-receipt', 'runId': state['runId'],
            'requestHash': state['requestHash'], 'outcome': 'completed', 'changedPaths': [],
            'addressedFindingIds': [], 'tests': {'run': False, 'reason': 'work-agent-prohibited'}})
        self.assertEqual(self.attempt(state, self.envelope(state))[0], 'completed')

    def test_new_prompt_returns_text_and_legacy_prompt_retains_old_contract(self):
        for inline in (True, False):
            prompt = rt.build_prompt(agent_id='main-response', role='main',
                request_path=Path('/managed/request.md'), result_path=Path('/managed/result.md'),
                run_id='run-one', inline_response=inline)
            if inline:
                self.assertIn('Do not write or reread your answer file', prompt)
                self.assertIn('`resultText`', prompt)
                self.assertNotIn('Write the detailed result to', prompt)
            else:
                self.assertIn('Write the detailed result to', prompt)

    def test_native_final_and_goal_control_use_runtime_persistence(self):
        for action in (None, 'clear'):
            with self.subTest(action=action), redirect_stdout(io.StringIO()) as output:
                bridge, _, state = native_fixture(self.root, goal=action is not None, action=action)
                bridge.run('bounded request')
                self.assertFalse(Path(state['resultPath']).exists())
                messages = [event['item']['text'] for line in output.getvalue().splitlines()
                            if (event := json.loads(line)).get('type') == 'item.completed'
                            and event.get('item', {}).get('type') == 'agent_message']
                terminal = json.loads(messages[-1])
                rt.publish_terminal_result(terminal, state)
                self.assertEqual(Path(state['resultPath']).read_text(), terminal['resultText'])
                self.assertEqual(terminal['status'], 'needs-human-decision' if action else 'completed')

    def test_invalid_schema_or_prompt_fails_before_child_launch(self):
        for failure in ('schema', 'prompt'):
            with self.subTest(failure=failure):
                state = self.new_run()
                if failure == 'schema':
                    schema = rt.safe_read_json(Path(state['responseSchemaPath']))
                    schema['additionalProperties'] = True
                    rt.atomic_write_json(Path(state['responseSchemaPath']), schema)
                session = {'codex': 'codex', 'role': 'main', 'projectRoot': str(self.root),
                           'executionPolicy': runtime_test_home.policy('workspace-write', self.root)}
                prompt_error = rt.ContractError('role_invalid', 'missing prompt') if failure == 'prompt' else None
                with patch.object(rt, 'build_prompt', side_effect=prompt_error, wraps=rt.build_prompt), \
                     patch.object(rt.execution_preflight, 'check') as preflight, \
                     patch.object(rt, 'spawn_contained_process') as spawn, \
                     patch.object(rt, 'release_contained_process') as release:
                    with self.assertRaises(rt.AttemptFailure) as raised:
                        rt.run_codex_attempt(project_root=self.root, session=session, state=state,
                            attempt=1, heartbeat=Mock(), cancel_event=threading.Event(),
                            expected_agent_id=state['agentId'], expected_run_id=state['runId'])
                    self.assertEqual(raised.exception.code, 'result_schema_invalid' if failure == 'schema' else 'role_invalid')
                    self.assertFalse(raised.exception.launched)
                    self.assertFalse(raised.exception.started)
                    preflight.assert_not_called()
                    spawn.assert_not_called()
                    release.assert_not_called()
