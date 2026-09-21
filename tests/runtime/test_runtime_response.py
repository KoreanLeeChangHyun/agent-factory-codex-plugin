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


class CapturedInput(io.StringIO):
    def close(self):
        self.sent = self.getvalue()
        super().close()


class RuntimeResponseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def new_run(self, role='main', request=b'bounded response'):
        return rt.create_run(project_root=self.root, agent_id=role+'-response', actor='main',
                             request=request, session={'role': role, 'maxAttempts': 1})

    def envelope(self, state, **values):
        return {'status': 'completed', 'resultPath': state['resultPath'],
                'resultText': '안녕하세요!\n**Answer**\n', **values}

    def attempt(self, state, terminal, *, return_code=0, backend=None, usage_events=()):
        events = [{'type': 'thread.started', 'thread_id': 'session-response'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'Progress only'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(terminal)}}]
        events.extend(usage_events)
        self.process_input = CapturedInput()
        process = Mock(pid=101, stdin=self.process_input, stderr=io.StringIO(),
                       stdout=io.StringIO(''.join(json.dumps(e)+'\n' for e in events)))
        process.wait.return_value = return_code
        session = {'codex': 'codex', 'role': state['role'], 'projectRoot': str(self.root),
                   'executionPolicy': runtime_test_home.policy('workspace-write', self.root),
                   'sessionId': 'session-response', 'startTimeout': 5, 'turnTimeout': 5}
        if backend:
            session['backend'] = backend
        rt.atomic_write_json(rt.session_file(self.root, state['agentId']), session)
        identity = {'pid': 101, 'bootId': 'fixture', 'startTicks': 7}
        with patch.object(rt.execution_preflight, 'check', return_value={'passed': True}), \
             patch.object(rt.native_codex, 'inspect_capabilities', return_value={'send': {'goal': False, 'fast': False, 'plan': False}}), \
             patch.object(rt, 'spawn_contained_process', return_value=(process, identity, 55)), \
             patch.object(rt, 'release_contained_process'), patch.object(rt, 'terminate_attempt_group'):
            return rt.run_codex_attempt(project_root=self.root, session=session, state=state,
                attempt=1, heartbeat=Mock(), cancel_event=threading.Event(),
                expected_agent_id=state['agentId'], expected_run_id=state['runId'])

    def test_attempt_persists_reported_usage_even_when_process_fails(self):
        for return_code in (0, 1):
            with self.subTest(return_code=return_code):
                state = self.new_run()
                event = {"type": "turn.completed", "usage": {
                    "input_tokens": 900, "cached_input_tokens": 700, "output_tokens": 50}}
                if return_code:
                    with self.assertRaises(rt.AttemptFailure):
                        self.attempt(state, self.envelope(state), return_code=return_code, usage_events=[event])
                else:
                    self.attempt(state, self.envelope(state), usage_events=[event])
                saved = rt.public_state(rt.safe_read_json(Path(state["statePath"])))
                self.assertEqual(saved["tokenUsage"]["inputTokens"], 900)
                self.assertEqual(saved["tokenUsage"]["cachedInputTokens"], 700)
                self.assertEqual(saved["tokenUsage"]["outputTokens"], 50)
                self.assertIsNone(saved["tokenUsage"]["reasoningOutputTokens"])
                self.assertEqual(saved["usageAttempts"]["1"]["reports"], 1)

    def test_native_attempt_sends_structured_parts_with_current_inline_request(self):
        from prompt_delivery import PromptParts
        state = self.new_run(request=b'current native request')
        self.attempt(state, self.envelope(state), backend='app-server')
        parts = PromptParts.decode(self.process_input.sent)
        self.assertIn('agent-factory-role-prompt', parts.fixed)
        self.assertNotIn(state['runId'], parts.fixed)
        self.assertNotIn(state['requestPath'], parts.fixed)
        self.assertIn('current native request', parts.dynamic)
        self.assertIn(state['resultPath'], parts.dynamic)
        self.assertNotIn('agent-factory-role-prompt', parts.dynamic)

    def test_attempt_persists_answer_without_model_file_writes(self):
        for status in ('completed', 'needs-human-decision', 'failed'):
            with self.subTest(status=status):
                state = self.new_run()
                response = self.envelope(state, status=status)
                self.assertFalse(Path(state['resultPath']).exists())
                self.assertEqual(self.attempt(state, response), (status, 'session-response'))
                self.assertEqual(Path(state['resultPath']).read_text(), response['resultText'])
                self.assertEqual(stat.S_IMODE(Path(state['resultPath']).stat().st_mode), 0o600)

    def test_main_attempt_delivers_exact_request_and_retains_record(self):
        request = '  안녕하세요!\r\n`code` <tag> & 요청\n'.encode('utf-8')
        state = self.new_run(request=request)
        self.attempt(state, self.envelope(state))
        prompt = self.process_input.sent
        self.assertIn('<agent-factory-request>\n' + request.decode('utf-8') +
                      '\n</agent-factory-request>', prompt)
        self.assertNotIn('Read the delegated request from', prompt)
        self.assertEqual(Path(state['requestPath']).read_bytes(), request)

    def test_inline_request_byte_boundary_and_managed_role_compatibility(self):
        for role, request, inline in (
            ('main', b'a' * (64 * 1024), True),
            ('main', b'a' * (64 * 1024 + 1), False),
            ('main', ('가' * 22000).encode('utf-8'), False),
            ('work', b'bounded work', False),
            ('verification', b'bounded verification', False),
        ):
            with self.subTest(role=role, size=len(request)):
                prompt = rt.build_prompt(agent_id='test-agent', role=role,
                    request_path=Path('/managed/request.md'), result_path=Path('/managed/result.md'),
                    run_id='run-one', request=request)
                self.assertEqual('<agent-factory-request>' in prompt, inline)
                self.assertEqual('Read the delegated request from' in prompt, not inline)

    def test_changed_request_is_rejected_before_delivery(self):
        state = self.new_run()
        Path(state['requestPath']).write_bytes(b'changed request')
        with self.assertRaises(rt.AttemptFailure) as raised:
            self.attempt(state, self.envelope(state))
        self.assertEqual(raised.exception.code, 'request_changed')
        self.assertEqual(self.process_input.getvalue(), '')

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
                with patch.object(rt, 'build_prompt_parts', side_effect=prompt_error, wraps=rt.build_prompt_parts), \
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
