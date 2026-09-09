"""Independent Verification targets; no production recipient or execution required."""
import runtime_test_home  # Isolate all runtime subprocesses from the real home.

import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import uuid

SCRIPT = Path(__file__).resolve().parents[2] / 'skills/agent/scripts/exec.py'
spec = importlib.util.spec_from_file_location('cloud_test_exec', SCRIPT)
rt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rt
spec.loader.exec_module(rt)
cloud = rt.cloud_reporting


class Recipient(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        server = self.server
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        server.requests.append(body)
        params = body['params']
        valid = (self.headers['Mcp-Protocol-Version'] == cloud.VERSION
                 and self.headers['Mcp-Method'] == body['method']
                 and self.headers['Mcp-Name'] == params['name']
                 and params['_meta']['io.modelcontextprotocol/protocolVersion'] == cloud.VERSION)
        if not valid:
            self.send_error(400)
            return
        if server.redirect:
            self.send_response(307)
            self.send_header('Location', server.redirect)
            self.end_headers()
            return
        if server.delay:
            time.sleep(server.delay)
        config = server.config
        if params['name'] == 'reporting_read':
            value = {'agents': [{'id': config['cloud_agent_id'], 'owner_user_id': config['reporter_user_id'],
                                 'workspace_id': config['workspace_id']}]}
        else:
            command = params['arguments']['command']
            server.commands.append(command)
            if server.deny or self.headers['Authorization'] not in {'Bearer afm_first', 'Bearer afm_rotated'}:
                self.send_response(403)
                self.end_headers()
                return
            key = command['key']
            if key in server.receipts:
                previous, value = server.receipts[key]
                if previous != command:
                    self.send_error(409)
                    return
            else:
                op = command['operation']
                payload = command[op]
                record = {'id': payload['id'], 'agent_id': config['cloud_agent_id'],
                          'workspace_id': config['workspace_id'], 'runtime_binding': payload['runtime_binding'],
                          'revision': payload.get('revision', 0) + 1}
                if op == 'report':
                    record['status'] = payload['status']
                if op == 'heartbeat':
                    record['runtime_observation'] = {k: payload[k] for k in ('sequence', 'observed_at', 'fact')}
                value = {'record': record, 'report_id': str(uuid.uuid4()) if op == 'report' else None,
                         'audit_event_id': str(uuid.uuid4()), 'received_at': rt.now()}
                server.receipts[key] = (command, value)
                if server.lose_ack:
                    server.lose_ack = False
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
            if server.forge:
                value = json.loads(json.dumps(value))
                value['record']['runtime_binding']['run_id'] = 'forged'
        result = {'jsonrpc': '2.0', 'id': body['id'], 'result': {'structuredContent': value, 'content': []}}
        data = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Recipient)
        self.server.daemon_threads = True
        self.server.config = self.config = {
            'version': 1, 'endpoint': f'http://127.0.0.1:{self.server.server_port}/mcp',
            'recipient_id': 'test-recipient', 'project_ref': 'project-one',
            'organization_id': str(uuid.uuid4()), 'workspace_id': str(uuid.uuid4()),
            'reporter_user_id': str(uuid.uuid4()), 'cloud_agent_id': str(uuid.uuid4()),
            'credential_file': str(self.root / 'credential.json'), 'allow_loopback_http': True}
        self.server.requests = []
        self.server.commands = []
        self.server.receipts = {}
        self.server.lose_ack = self.server.deny = self.server.forge = False
        self.server.redirect = None
        self.server.delay = 0
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.credential('afm_first')
        self.config_path = self.root / 'config.json'
        self.config_path.write_text(json.dumps(self.config))
        self.config_path.chmod(0o600)
        directory = rt.run_directory(self.root, 'work-one', 'run-one', create=True)
        self.state = {'agentId': 'work-one', 'runId': 'run-one', 'sessionId': 'session-one',
                      'role': 'work', 'status': 'running', 'cloudReporting': self.config,
                      'reportingLoopId': 'loop-one', 'statePath': str(directory / 'state.json')}
        rt.atomic_write_json(directory / 'state.json', self.state)
        cloud.collect(rt, self.root, self.state)

    def credential(self, token, target=None):
        path = Path(self.config['credential_file'])
        path.write_text(json.dumps({'version': 1, 'target': target or {
            k: self.config[k] for k in cloud.TARGET_KEYS}, 'token': token}))
        path.chmod(0o600)

    def test_lost_ack_rotation_replays_identical_command_without_execution(self):
        self.server.lose_ack = True
        first = cloud.deliver(rt, self.root, self.state)
        self.assertEqual(first['pending'], 1)
        self.credential('afm_rotated')
        second = cloud.deliver(rt, self.root, self.state)
        self.assertEqual(second['pending'], 0)
        self.assertEqual(len(self.server.receipts), 1)
        self.assertEqual(self.server.commands[0], self.server.commands[1])
        self.assertTrue(all(r['params']['name'] in {'reporting_read', 'reporting_write'} for r in self.server.requests))
        for path in rt.agent_root(self.root).parent.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'afm_first', path.read_bytes())
                self.assertNotIn(b'afm_rotated', path.read_bytes())

    def test_rotation_cannot_change_owner_or_recipient(self):
        target = {k: self.config[k] for k in cloud.TARGET_KEYS}
        target['reporter_user_id'] = str(uuid.uuid4())
        self.credential('afm_rotated', target)
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)
        self.assertEqual(self.server.requests, [])

    def test_forged_ack_remains_pending(self):
        self.server.forge = True
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)

    def test_denial_leaves_authoritative_state_unchanged(self):
        self.server.deny = True
        before = Path(self.state['statePath']).read_bytes()
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)
        self.assertEqual(Path(self.state['statePath']).read_bytes(), before)

    def test_timeout_is_bounded(self):
        self.server.delay = 8
        start = time.monotonic()
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)
        self.assertLess(time.monotonic() - start, 7)

    def test_redirect_is_not_followed(self):
        self.server.redirect = self.config['endpoint'] + '/elsewhere'
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)
        self.assertEqual(len(self.server.requests), 1)

    def test_private_config_symlink_and_unknown_fields(self):
        link = self.root / 'link'
        link.symlink_to(self.config_path)
        with self.assertRaises(rt.ContractError):
            cloud.read_config(rt, link)
        self.config_path.chmod(0o644)
        with self.assertRaises(rt.ContractError):
            cloud.read_config(rt, self.config_path)
        with self.assertRaises(cloud.ReportingError):
            cloud.validate_config({**self.config, 'token': 'afm_secret'})
        with self.assertRaises(cloud.ReportingError):
            cloud.validate_config({**self.config, 'endpoint': 'http://example.com/mcp'})

    def test_binding_change_is_rejected(self):
        with self.assertRaises(cloud.ReportingError):
            cloud.collect(rt, self.root, {**self.state, 'sessionId': 'different'})

    def test_observations_do_not_infer_completion_and_keep_sequence(self):
        cloud.collect(rt, self.root, self.state, ('2026-01-01T00:00:00Z', 'process_alive'))
        cloud.collect(rt, self.root, self.state, ('2026-01-01T00:01:00Z', 'process_exited'))
        self.state['status'] = 'failed'
        cloud.collect(rt, self.root, self.state)
        _, box = cloud.load_box(rt, self.root, self.state)
        self.assertEqual(box['sequence'], 2)
        self.assertEqual([e['command']['operation'] for e in box['entries']], ['task', 'heartbeat', 'heartbeat'])
        cloud.collect(rt, self.root, self.state, ('2025-01-01T00:00:00Z', 'process_alive'))
        self.assertEqual(cloud.status(rt, self.root, self.state)['sequence'], 2)

    def test_validated_terminal_receipt_produces_explicit_results(self):
        result = Path(self.state['statePath']).parent / 'result.md'
        result.write_text('private result body is not transmitted')
        receipt = {'runId': 'run-one', 'outcome': 'implemented'}
        self.state.update(status='completed', resultPath=str(result), reportingSemanticResult={
            'status': 'completed', 'result_sha256': cloud.hashlib.sha256(result.read_bytes()).hexdigest(),
            'receipt_sha256': cloud.digest(receipt)})
        with patch.object(rt, 'validate_receipt', return_value=receipt):
            cloud.prepare_semantic(rt, self.root, self.state)
        _, box = cloud.load_box(rt, self.root, self.state)
        reports = [e['command']['report'] for e in box['entries'] if e['command']['operation'] == 'report']
        self.assertEqual([r['status'] for r in reports], ['in_progress', 'completed'])
        self.assertEqual([r['revision'] for r in reports], [1, 2])
        self.assertEqual(len(reports[-1]['results']), 1)
        self.assertNotIn('private result body', json.dumps(box))
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 0)

    def test_waits_for_actual_session_and_no_default_configuration(self):
        rt.run_directory(self.root, 'other', 'run-two', create=True)
        state = {**self.state, 'agentId': 'other', 'runId': 'run-two', 'sessionId': None}
        cloud.collect(rt, self.root, state)
        self.assertTrue(cloud.status(rt, self.root, state)['awaitingSession'])
        self.assertEqual(cloud.status(rt, self.root, state)['pending'], 0)
        self.assertIsNone(cloud.status(rt, self.root, {}))


    def test_busy_delivery_does_not_block_supervisor_and_can_resume(self):
        path = cloud.reporting_path(rt, self.root, self.state)
        started = time.monotonic()
        with rt.file_lock(path.parent / '.reporting.lock'):
            cloud.hook(rt, Path(self.state['statePath']), ('2026-01-01T00:00:00Z', 'process_alive'))
        self.assertLess(time.monotonic() - started, 1)
        current = rt.safe_read_json(Path(self.state['statePath']))
        self.assertEqual(current['reportingObservation'][1], 'process_alive')
        cloud.collect(rt, self.root, current)
        self.assertEqual(cloud.status(rt, self.root, current)['sequence'], 1)

    def test_unsafe_parent_and_fifo_do_not_read_credentials(self):
        parent = self.root / 'alias'
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(rt.ContractError):
            cloud.read_config(rt, parent / self.config_path.name)
        fifo = self.root / 'fifo'
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(rt.ContractError):
            cloud.read_config(rt, fifo)

    def test_changed_result_does_not_emit_semantic_completion(self):
        result = Path(self.state['statePath']).parent / 'result.md'
        result.write_text('changed')
        self.state.update(status='completed', resultPath=str(result), reportingSemanticResult={
            'status': 'completed', 'result_sha256': '0' * 64, 'receipt_sha256': '0' * 64})
        with self.assertRaises(cloud.ReportingError):
            cloud.prepare_semantic(rt, self.root, self.state)
        _, box = cloud.load_box(rt, self.root, self.state)
        self.assertFalse(any(e['command']['operation'] == 'report' for e in box['entries']))


    def accept_runtime_terminal(self, *, size=8388609, role='main', fail_intent_writes=False):
        """Use real runtime acceptance and receipts; replace only the Codex process."""
        import io
        from unittest.mock import Mock
        state = rt.create_run(project_root=self.root, agent_id='accepted-agent', actor='main',
            request=b'bounded reporting regression', session={'role': role, 'maxAttempts': 1},
            reporting_config=self.config)
        result = Path(state['resultPath'])
        # Sparse data avoids allocating a large fixture string while remaining a
        # nonempty regular file accepted by the runtime's original contract.
        with result.open('wb') as stream:
            stream.truncate(size)
        if role == 'work':
            rt.atomic_write_json(Path(state['receiptPath']), {
                'schemaVersion': '0.1.0', 'kind': 'work-receipt', 'runId': state['runId'],
                'requestHash': state['requestHash'], 'outcome': 'implemented',
                'changedPaths': ['example.py'], 'addressedFindingIds': [],
                'tests': {'run': False, 'reason': 'work-agent-prohibited'}})
        terminal = {'status': 'completed', 'resultPath': str(result)}
        events = [{'type': 'thread.started', 'thread_id': 'session-one'},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(terminal)}}]
        process = Mock(pid=101)
        process.stdin = io.StringIO()
        process.stdout = io.StringIO(''.join(json.dumps(e) + '\n' for e in events))
        process.stderr = io.StringIO()
        process.wait.return_value = 0
        session = {'codex': 'codex', 'projectRoot': str(self.root), 'sandbox': 'workspace-write',
                   'executionPolicy': runtime_test_home.policy('workspace-write', self.root),
                   'sessionId': 'session-one', 'startTimeout': 5, 'turnTimeout': 5}
        rt.atomic_write_json(rt.session_file(self.root, state['agentId']), session)
        identity = {'pid': 101, 'bootId': 'fixture', 'startTicks': 7}
        update = rt.update_json
        failures = []
        def transient_intent_write(path, lock, change):
            probe = rt.safe_read_json(path)
            change(probe)
            if fail_intent_writes and probe.get('reportingSemanticIntent') and probe['status'] == 'running' and len(failures) < 2:
                failures.append(True)
                raise OSError('afm_DO_NOT_STORE_DIAGNOSTIC')
            return update(path, lock, change)
        with patch.object(rt.execution_preflight, 'check', return_value={'passed': True}), \
             patch.object(rt, 'spawn_contained_process', return_value=(process, identity, 55)) as spawn, \
             patch.object(rt, 'release_contained_process'), patch.object(rt, 'terminate_attempt_group'), \
             patch.object(rt, 'update_json', side_effect=transient_intent_write):
            outcome, session_id = rt.run_codex_attempt(project_root=self.root, session=session, state=state,
                attempt=1, heartbeat=Mock(), cancel_event=threading.Event(),
                expected_agent_id=state['agentId'], expected_run_id=state['runId'])
            rt.mark_terminal(Path(state['statePath']), outcome,
                             semantic_intent=state.get('reportingSemanticIntent'))
            self.assertEqual(spawn.call_count, 1)
        self.assertEqual(outcome, 'completed')
        self.assertEqual(session_id, 'session-one')
        current = rt.safe_read_json(Path(state['statePath']))
        self.assertEqual(current['status'], 'completed')
        self.assertEqual(current['reportingSemanticIntent']['status'], 'completed')
        self.assertNotIn('reportingSemanticResult', current)
        return current

    def test_actual_heartbeat_between_capture_and_enqueue_never_reads_results(self):
        state = self.accept_runtime_terminal(role='work')
        # Reach the real interruption window: a durable validated proof exists,
        # but delivery has not prepared semantic outbox commands yet.
        state = cloud.capture_semantic_result(rt, self.root, state)
        self.assertIn('reportingSemanticResult', state)
        _, before = cloud.load_box(rt, self.root, state)
        self.assertFalse(before['semantic'])
        heartbeat = rt.Heartbeat(Path(state['heartbeatPath']), Path(state['statePath']), 5)
        opened = []
        real_open = os.open
        def observe_open(path, *args, **kwargs):
            opened.append(str(path))
            return real_open(path, *args, **kwargs)
        with patch.object(rt, 'safe_hash_caller_file', side_effect=AssertionError('hook hashed result')) as hashing, \
             patch.object(rt, 'validate_receipt', side_effect=AssertionError('hook validated receipt')) as receipt, \
             patch.object(cloud, 'prepare_semantic', side_effect=AssertionError('hook prepared semantics')) as preparing, \
             patch.object(rt.os, 'open', side_effect=observe_open) as opened_mock, \
             patch.object(rt.os, 'supports_dir_fd', rt.os.supports_dir_fd | {opened_mock}):
            heartbeat._write()
            heartbeat.update(status='completed', attempt=1, codex_pid=None)
            rt.mark_terminal(Path(state['statePath']), 'completed')
        hashing.assert_not_called()
        receipt.assert_not_called()
        preparing.assert_not_called()
        self.assertFalse(any(Path(name).name in {'result.md', 'receipt.json'} for name in opened))
        self.assertEqual(rt.safe_read_json(Path(state['heartbeatPath']))['sequence'], 2)
        state = rt.safe_read_json(Path(state['statePath']))
        self.assertIn('reportingObservation', state)
        _, box = cloud.load_box(rt, self.root, state)
        self.assertFalse(box['semantic'])
        self.assertFalse(any(e['command']['operation'] == 'report' for e in box['entries']))
        self.assertTrue(cloud.status(rt, self.root, state)['semanticPending'])
        self.assertEqual(cloud.deliver(rt, self.root, state)['pending'], 0)
        reports = [c['report'] for c in self.server.commands if c['operation'] == 'report']
        self.assertEqual([r['status'] for r in reports], ['in_progress', 'completed'])

    def test_delivery_revalidates_result_after_proof_persistence(self):
        state = self.accept_runtime_terminal(size=128)
        state = cloud.capture_semantic_result(rt, self.root, state)
        Path(state['resultPath']).write_bytes(b'changed result')
        delivered = cloud.deliver(rt, self.root, state)
        self.assertTrue(delivered['semanticPending'])
        self.assertGreater(delivered['pending'], 0)
        self.assertEqual(delivered['error'], 'reporting_semantic_pending')
        self.assertFalse(any(c['operation'] == 'report' for c in self.server.commands))

    def test_delivery_revalidates_receipt_after_proof_persistence(self):
        state = self.accept_runtime_terminal(size=128, role='work')
        state = cloud.capture_semantic_result(rt, self.root, state)
        receipt_path = Path(state['receiptPath'])
        receipt = rt.safe_read_json(receipt_path)
        receipt['changedPaths'] = ['substituted.py']
        rt.atomic_write_json(receipt_path, receipt)
        delivered = cloud.deliver(rt, self.root, state)
        self.assertTrue(delivered['semanticPending'])
        self.assertEqual(delivered['error'], 'reporting_semantic_pending')
        self.assertFalse(any(c['operation'] == 'report' for c in self.server.commands))

    def test_actual_runtime_large_result_captures_and_delivers_with_bounded_reads(self):
        state = self.accept_runtime_terminal()
        pending = cloud.status(rt, self.root, state)
        self.assertTrue(pending['semanticPending'])
        self.assertEqual(pending['error'], 'reporting_capture_pending')
        read = os.read
        requested = []
        def bounded_read(fd, count):
            requested.append(count)
            return read(fd, count)
        with patch.object(rt.os, 'read', side_effect=bounded_read), \
             patch.object(rt, 'spawn_contained_process', side_effect=AssertionError('execution replay')):
            delivered = cloud.deliver(rt, self.root, state)
        self.assertLessEqual(max(requested), 65536)
        self.assertEqual(delivered['pending'], 0)
        self.assertIsNone(delivered['error'])
        reports = [c['report'] for c in self.server.commands if c['operation'] == 'report']
        self.assertEqual([r['status'] for r in reports], ['in_progress', 'completed'])
        self.assertTrue(reports[-1]['results'])

    def test_actual_work_receipt_transient_capture_recovers_without_reexecution(self):
        state = self.accept_runtime_terminal(role='work')
        intent = state['reportingSemanticIntent']
        self.assertIsNotNone(intent['receipt_sha256'])
        with patch.object(rt, 'safe_hash_caller_file', side_effect=OSError('afm_DO_NOT_STORE_DIAGNOSTIC')):
            first = cloud.deliver(rt, self.root, state)
        self.assertGreater(first['pending'], 0)
        self.assertEqual(first['error'], 'reporting_capture_pending')
        self.assertFalse(any(c['operation'] == 'report' for c in self.server.commands))
        state = rt.safe_read_json(Path(state['statePath']))
        self.assertEqual(state['reportingSemanticIntent'], intent)
        self.assertEqual(state['status'], 'completed')
        with patch.object(rt, 'spawn_contained_process', side_effect=AssertionError('execution replay')):
            recovered = cloud.deliver(rt, self.root, state)
        self.assertEqual(recovered['pending'], 0)
        self.assertIsNone(recovered['error'])
        for path in Path(state['statePath']).parent.rglob('*'):
            if path.is_file() and path.name != 'result.md':
                self.assertNotIn(b'afm_DO_NOT_STORE_DIAGNOSTIC', path.read_bytes())

    def test_terminal_write_retains_intent_when_early_publication_fails(self):
        state = self.accept_runtime_terminal(size=128, fail_intent_writes=True)
        self.assertEqual(cloud.status(rt, self.root, state)['error'], 'reporting_capture_pending')
        self.assertEqual(cloud.deliver(rt, self.root, state)['pending'], 0)

    def test_capture_proof_publication_failure_remains_pending_and_recovers(self):
        state = self.accept_runtime_terminal(size=128)
        update = rt.update_json
        failures = []
        def interrupted_publish(path, lock, change):
            probe = rt.safe_read_json(path)
            change(probe)
            if probe.get('reportingSemanticResult') and not failures:
                failures.append(True)
                raise OSError('afm_DO_NOT_STORE_DIAGNOSTIC')
            return update(path, lock, change)
        with patch.object(rt, 'update_json', side_effect=interrupted_publish):
            first = cloud.deliver(rt, self.root, state)
        self.assertEqual(first['error'], 'reporting_capture_pending')
        self.assertGreater(first['pending'], 0)
        state = rt.safe_read_json(Path(state['statePath']))
        self.assertNotIn('reportingSemanticResult', state)
        self.assertEqual(state['reportingSemanticIntent']['status'], 'completed')
        self.assertEqual(cloud.deliver(rt, self.root, state)['pending'], 0)

    def test_deferred_capture_refuses_replaced_result(self):
        state = self.accept_runtime_terminal(size=128)
        replacement = Path(state['resultPath']).with_name('replacement.md')
        replacement.write_bytes(b'x' * 128)
        os.replace(replacement, state['resultPath'])
        delivered = cloud.deliver(rt, self.root, state)
        self.assertGreater(delivered['pending'], 0)
        self.assertEqual(delivered['error'], 'reporting_capture_pending')
        self.assertFalse(any(c['operation'] == 'report' for c in self.server.commands))


class InstalledSDKTests(unittest.TestCase):
    """Run an actual installed MCP 2 server with fake storage and lost acknowledgement."""

    setUp = ReportingTests.setUp
    credential = ReportingTests.credential

    def test_actual_sdk_and_recipient_schema(self):
        import subprocess
        python = SCRIPT.parents[3].parent / 'mcp/.venv/bin/python'
        mcp_root = SCRIPT.parents[3].parent / 'mcp'
        if not python.exists():
            self.skipTest('Sibling MCP environment required for SDK integration')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        self.config['endpoint'] = f'http://127.0.0.1:{port}/mcp'
        self.credential('afm_first')
        self.state['cloudReporting'] = self.config
        rt.atomic_write_json(Path(self.state['statePath']), self.state)
        path = cloud.reporting_path(rt, self.root, self.state)
        box = rt.safe_read_json(path)
        box['config'] = self.config
        cloud.publish(rt, path, box)
        code = r'''
import json, sys, uuid
from datetime import datetime, timezone
from mcp.server import MCPServer
from mcp_types import CallToolResult, TextContent
from app.modules.reporting.schemas import Command
import uvicorn
config = json.loads(sys.stdin.readline())
server = MCPServer('fake-reporting-recipient')
receipts = {}

def result(value):
    return CallToolResult(content=[TextContent(text=json.dumps(value))], structured_content=value)

@server.tool(name='reporting_read')
async def reporting_read(organization_id: str, workspace_id: str):
    return result({'agents': [{'id': config['cloud_agent_id'], 'owner_user_id': config['reporter_user_id'], 'workspace_id': config['workspace_id']}]})

@server.tool(name='reporting_write')
async def reporting_write(command: Command, organization_id: str, workspace_id: str):
    data = command.model_dump(mode='json')
    if command.key in receipts:
        original, value = receipts[command.key]
        assert original == data
        return result(value)
    payload = data['task']
    value = {'record': {**payload, 'workspace_id': workspace_id, 'revision': 1}, 'report_id': None,
             'audit_event_id': str(uuid.uuid4()), 'received_at': datetime.now(timezone.utc).isoformat()}
    receipts[command.key] = (data, value)
    # Simulate a durable commit followed by failure before an acknowledgement.
    raise RuntimeError('injected lost acknowledgement')

uvicorn.run(server.streamable_http_app(), host='127.0.0.1', port=int(sys.argv[1]), log_level='critical')
'''
        process = subprocess.Popen([str(python), '-c', code, str(port)], cwd=mcp_root,
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.stdin.write((json.dumps(self.config) + '\n').encode())
        process.stdin.close()
        def stop():
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        self.addCleanup(stop)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    break
            except OSError:
                if process.poll() is not None:
                    self.fail('SDK fixture exited before listening')
                time.sleep(.05)
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 1)
        self.credential('afm_rotated')
        self.assertEqual(cloud.deliver(rt, self.root, self.state)['pending'], 0)


if __name__ == '__main__':
    unittest.main()
