"""Optional local reporting outbox; execution and graph authority stay local.

Transport is explicitly MCP 2026-07-28 (SDK 2 per-request envelopes).
No run text, environment, credential bytes, or remote error bodies are persisted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlsplit
import paths as runtime_paths

VERSION = '2026-07-28'
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}')
CONFIG_KEYS = {'version', 'endpoint', 'recipient_id', 'project_ref', 'organization_id',
               'workspace_id', 'reporter_user_id', 'cloud_agent_id', 'credential_file',
               'allow_loopback_http'}
TARGET_KEYS = {'endpoint', 'recipient_id', 'organization_id', 'workspace_id',
               'reporter_user_id', 'cloud_agent_id'}
MAX_ENTRIES = 512


class ReportingError(Exception):
    """Only fixed, credential-free codes may cross the transport boundary."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ReportingError('reporting_binding_invalid')
    return value


def validate_config(value):
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS or value['version'] != 1:
        raise ReportingError('reporting_config_invalid')
    for key in ('recipient_id', 'project_ref'):
        identifier(value[key])
    for key in ('organization_id', 'workspace_id', 'reporter_user_id', 'cloud_agent_id'):
        if str(uuid.UUID(value[key])) != value[key]:
            raise ReportingError('reporting_config_invalid')
    endpoint = value['endpoint']
    parsed = urlsplit(endpoint)
    if (not isinstance(value['allow_loopback_http'], bool) or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or any(ord(c) < 33 or ord(c) > 126 for c in endpoint)
            or (parsed.scheme != 'https' and not (
                parsed.scheme == 'http' and value['allow_loopback_http']
                and parsed.hostname in {'127.0.0.1', '::1'}))):
        raise ReportingError('reporting_endpoint_invalid')
    credential = Path(value['credential_file'])
    if not credential.is_absolute() or '..' in credential.parts or '.agent-factory' in credential.parts or credential.is_relative_to(runtime_paths.home_path()):
        raise ReportingError('reporting_credential_reference_invalid')
    return value


def read_config(rt, path):
    if path is None:
        return None
    try:
        return validate_config(json.loads(rt.safe_read_caller_file(Path(path), 16384, private=True)))
    except Exception:
        raise rt.ContractError('reporting_config_invalid', 'Reporting configuration is invalid or unsafe') from None


def publish(rt, path, document):
    rt.atomic_write_json(path, document)
    sync_directory(path.parent)


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def reporting_path(rt, root, state):
    directory = rt.run_directory(root, state['agentId'], state['runId'])
    rt.ensure_directory(directory, rt.find_project_anchor(directory))
    return directory / 'reporting.json'


def append(box, operation, payload):
    if len(box['entries']) >= MAX_ENTRIES:
        raise ReportingError('reporting_outbox_full')
    command = {'key': 'local-' + uuid.uuid4().hex, 'operation': operation, operation: payload}
    box['entries'].append({'command': command, 'digest': digest(command), 'ack': None})


def load_box(rt, root, state):
    path = reporting_path(rt, root, state)
    box = json.loads(rt.safe_read_caller_file(path, 1024 * 1024))
    if box['config'] != state['cloudReporting'] or box['run_id'] != state['runId']:
        raise ReportingError('reporting_binding_conflict')
    expected = binding(state)
    if box['binding'] is not None and box['binding'] != expected:
        raise ReportingError('reporting_binding_conflict')
    for entry in box['entries']:
        command = entry['command']
        op = command['operation']
        if entry['digest'] != digest(command) or op not in {'task', 'report', 'heartbeat'}:
            raise ReportingError('reporting_command_conflict')
        if op == 'task' and command[op]['agent_id'] != box['config']['cloud_agent_id']:
            raise ReportingError('reporting_binding_conflict')
        if (command[op]['id'] != box['task_id']
                or command[op]['runtime_binding'] != box['binding']):
            raise ReportingError('reporting_binding_conflict')
    return path, box


def binding(state):
    if not state.get('sessionId'):
        return None
    return {'project_ref': identifier(state['cloudReporting']['project_ref']),
            'agent_id': identifier(state['agentId']), 'session_id': identifier(state['sessionId']),
            'run_id': identifier(state['runId']),
            'loop_id': identifier(state['reportingLoopId']) if state.get('reportingLoopId') else None}


def capture_semantic_result(rt, root, state):
    """Recover evidence only from a durably validated terminal intent, never exit facts."""
    intent = state.get('reportingSemanticIntent')
    if not intent or state.get('reportingSemanticResult'):
        return state
    state_path = Path(state['statePath'])
    try:
        expected = {'run_id': state['runId'], 'agent_id': state['agentId'],
                    'session_id': state['sessionId'], 'request_sha256': state['requestHash'],
                    'role': state['role'], 'status': state['status']}
        if (set(intent) != set(expected) | {'result_identity', 'receipt_sha256'}
                or any(intent[k] != v for k, v in expected.items())
                or intent['status'] not in {'completed', 'failed', 'needs-human-decision'}):
            raise ReportingError('reporting_intent_conflict')
        result_path = rt.run_directory(root, state['agentId'], state['runId']) / 'result.md'
        if str(result_path) != state['resultPath']:
            raise ReportingError('reporting_result_conflict')
        if intent['status'] == 'completed' and state['role'] in {'work', 'verification'}:
            receipt = rt.validate_receipt(root, state, agent_id=state['agentId'], run_id=state['runId'])
            if digest(receipt) != intent['receipt_sha256']:
                raise ReportingError('reporting_receipt_conflict')
        proof = {k: intent[k] for k in ('status', 'run_id', 'request_sha256', 'role', 'receipt_sha256')}
        proof['result_sha256'] = rt.safe_hash_caller_file(result_path, intent['result_identity'])
        def captured(value):
            if value.get('reportingSemanticIntent') != intent or value['status'] != intent['status']:
                raise ReportingError('reporting_intent_conflict')
            value.update(reportingSemanticResult=proof, reportingCaptureError=None)
        captured_state = rt.update_json(state_path, state_path.parent / '.state.lock', captured)
        sync_directory(state_path.parent)
        return captured_state
    except Exception:
        # Even if this diagnostic write fails, the durable intent makes status
        # report capture pending; the validated semantic outcome cannot disappear.
        try:
            return rt.update_json(state_path, state_path.parent / '.state.lock',
                lambda value: value.update(reportingCaptureError='reporting_capture_pending'))
        except Exception:
            return state


def collect(rt, root, state, observation=None):
    """Persist bounded registration/observation metadata, without reading results."""
    if not state.get('cloudReporting'):
        return
    path = reporting_path(rt, root, state)
    with rt.file_lock(path.parent / '.reporting.lock', blocking=False):
        if path.exists():
            path, box = load_box(rt, root, state)
        else:
            box = {'version': 1, 'config': state['cloudReporting'], 'run_id': state['runId'],
                   'task_id': str(uuid.uuid4()), 'binding': None, 'entries': [],
                   'sequence': 0, 'observed_at': None, 'semantic': False, 'error': None}
        actual = binding(state)
        observation = observation or state.get('reportingObservation')
        if actual is not None and box['binding'] is None:
            box['binding'] = actual
            append(box, 'task', {'id': box['task_id'], 'agent_id': box['config']['cloud_agent_id'],
                                'name': state['runId'], 'description': 'Local managed run',
                                'runtime_binding': actual})
        if actual is not None and observation is not None:
            stamp, fact = observation
            elapsed = (rt.parse_time(stamp) or 0) - (rt.parse_time(box['observed_at']) or 0)
            if elapsed > 0 and (elapsed >= 30 or fact == 'process_exited'):
                box['sequence'] += 1
                box['observed_at'] = stamp
                append(box, 'heartbeat', {'id': box['task_id'], 'runtime_binding': actual,
                    'sequence': box['sequence'], 'observed_at': stamp, 'fact': fact})
        publish(rt, path, box)
        publish(rt, path.parent / 'reporting-error.json', {'error': None})


def prepare_semantic(rt, root, state):
    """Delivery-only result revalidation and semantic outbox preparation.

    Keep this separate from collect: supervisor hooks must never open result
    bodies or validate receipts, including after interrupted proof publication.
    """
    path = reporting_path(rt, root, state)
    with rt.file_lock(path.parent / '.reporting.lock', blocking=False):
        path, box = load_box(rt, root, state)
        actual = binding(state)
        proof = state.get('reportingSemanticResult')
        if actual is not None and proof and state['status'] in rt.TERMINAL_STATES and not box['semantic']:
            result_hash = rt.safe_hash_caller_file(Path(state['resultPath']))
            if result_hash != proof['result_sha256'] or proof['status'] != state['status']:
                raise ReportingError('reporting_result_conflict')
            if state['status'] == 'completed' and state['role'] in {'work', 'verification'}:
                receipt = rt.validate_receipt(root, state, agent_id=state['agentId'], run_id=state['runId'])
                if digest(receipt) != proof['receipt_sha256']:
                    raise ReportingError('reporting_receipt_conflict')
            # Registration begins pending; recipient requires an explicit start before finish.
            append(box, 'report', {'id': box['task_id'], 'runtime_binding': actual, 'revision': 1,
                'status': 'in_progress', 'message': 'Validated local result is available; recording its lifecycle.'})
            status = {'completed': 'completed', 'failed': 'failed', 'needs-human-decision': 'input_required'}[proof['status']]
            summary = json.dumps(proof, sort_keys=True)
            append(box, 'report', {'id': box['task_id'], 'runtime_binding': actual, 'revision': 2,
                'status': status, 'message': 'Explicit validated local runtime result. Loop outcome remains independent.',
                'results': [{'label': 'Local result evidence', 'summary': summary}]})
            box['semantic'] = True
        publish(rt, path, box)


def hook(rt, state_path, observation=None):
    """Reporting errors never become execution errors or signal process completion."""
    try:
        state = rt.safe_read_json(state_path)
        if state.get('cloudReporting'):
            if observation is not None:
                def remember(value):
                    previous = value.get('reportingObservation')
                    if previous is None or observation[0] > previous[0]:
                        value['reportingObservation'] = observation
                state = rt.update_json(state_path, state_path.parent / '.state.lock', remember)
            collect(rt, rt.runtime_paths.project_for(state_path), state, observation)
    except Exception:
        try:
            publish(rt, state_path.parent / 'reporting-error.json', {'error': 'reporting_local_pending'})
        except Exception:
            pass


def status(rt, root, state):
    if not state.get('cloudReporting'):
        return None
    try:
        path, box = load_box(rt, root, state)
        local_error = rt.safe_read_json(path.parent / 'reporting-error.json').get('error')
        semantic_pending = not box['semantic'] and bool(
            state.get('reportingSemanticIntent') or state.get('reportingSemanticResult')
            or state.get('status') in {'completed', 'needs-human-decision'})
        capture_pending = semantic_pending and not state.get('reportingSemanticResult')
        return {'taskId': box['task_id'], 'binding': box['binding'],
                'pending': sum(e['ack'] is None for e in box['entries']) + int(semantic_pending),
                'semanticPending': semantic_pending,
                'sequence': box['sequence'], 'error': (
                    'reporting_capture_pending' if capture_pending else
                    'reporting_semantic_pending' if semantic_pending else local_error or box['error']),
                'awaitingSession': box['binding'] is None}
    except Exception:
        return {'pending': True, 'error': 'reporting_local_pending'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReportingError('reporting_redirect_refused')


def call(config, token, name, arguments):
    """SDK 2 modern requests do not initialize or retain an MCP session."""
    request_id = uuid.uuid4().hex
    params = {'name': name, 'arguments': arguments, '_meta': {
        'io.modelcontextprotocol/protocolVersion': VERSION,
        'io.modelcontextprotocol/clientInfo': {'name': 'agent-factory-local-reporting', 'version': '1'},
        'io.modelcontextprotocol/clientCapabilities': {}}}
    body = {'jsonrpc': '2.0', 'id': request_id, 'method': 'tools/call', 'params': params}
    request = urllib.request.Request(config['endpoint'], data=json.dumps(body).encode(), headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream', 'Mcp-Protocol-Version': VERSION,
        'Mcp-Method': 'tools/call', 'Mcp-Name': name})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=2) as response:
        content_type = response.headers.get_content_type()
        if content_type == 'application/json':
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ReportingError('reporting_response_invalid')
            document = json.loads(raw)
        elif content_type == 'text/event-stream':
            document = None
            data = []
            size = 0
            while size <= 1024 * 1024:
                line = response.readline(65537)
                size += len(line)
                if not line:
                    break
                if line.strip() == b'' and data:
                    candidate = json.loads(b'\n'.join(data))
                    data = []
                    if candidate.get('id') == request_id:
                        document = candidate
                        break
                elif line.startswith(b'data:'):
                    data.append(line[5:].strip())
            if document is None:
                raise ReportingError('reporting_response_invalid')
        else:
            raise ReportingError('reporting_response_invalid')
    if document.get('id') != request_id or document.get('jsonrpc') != '2.0' or 'error' in document:
        raise ReportingError('reporting_protocol_denied')
    result = document['result']
    if result.get('isError'):
        raise ReportingError('reporting_server_denied')
    payload = result.get('structuredContent')
    if payload is None:
        payload = json.loads(result['content'][0]['text'])
    return payload


def send_one(rt, root, state, index):
    """Called only in a deadline-contained child; never emit raw exception text."""
    _, box = load_box(rt, root, state)
    config = validate_config(box['config'])
    credential = json.loads(rt.safe_read_caller_file(Path(config['credential_file']), 16384, private=True))
    if (set(credential) != {'version', 'target', 'token'} or credential['version'] != 1
            or credential['target'] != {k: config[k] for k in TARGET_KEYS}):
        raise ReportingError('reporting_credential_binding_conflict')
    token = credential['token']
    if not isinstance(token, str) or not re.fullmatch(r'afm_[A-Za-z0-9_-]{1,4096}', token):
        raise ReportingError('reporting_credential_invalid')
    scope = {k: config[k] for k in ('organization_id', 'workspace_id')}
    snapshot = call(config, token, 'reporting_read', scope)
    agent = next((a for a in snapshot['agents'] if a['id'] == config['cloud_agent_id']), None)
    if (agent is None or agent['owner_user_id'] != config['reporter_user_id']
            or agent['workspace_id'] != config['workspace_id']):
        raise ReportingError('reporting_owner_conflict')
    # The server rechecks token ownership for every write, including receipt replay.
    command = box['entries'][index]['command']
    payload = call(config, token, 'reporting_write', {**scope, 'command': command})
    record = payload['record']
    op = command['operation']
    if (record['id'] != box['task_id'] or record['runtime_binding'] != box['binding']
            or record['agent_id'] != config['cloud_agent_id']
            or record['workspace_id'] != config['workspace_id']):
        raise ReportingError('reporting_ack_binding_conflict')
    expected_revision = command[op]['revision'] + 1 if op == 'report' else None
    if op == 'task' and record['revision'] != 1:
        raise ReportingError('reporting_ack_revision_conflict')
    if op == 'report' and record['status'] != command[op]['status']:
        raise ReportingError('reporting_ack_binding_conflict')
    if op == 'heartbeat':
        observed = record['runtime_observation']
        expected = command[op]
        if (observed['sequence'] != expected['sequence'] or observed['fact'] != expected['fact']
                or rt.parse_time(observed['observed_at']) != rt.parse_time(expected['observed_at'])):
            raise ReportingError('reporting_ack_binding_conflict')
    if expected_revision is not None and record['revision'] != expected_revision:
        raise ReportingError('reporting_ack_revision_conflict')
    # Only validated metadata is stored; server content could reflect secrets.
    ack = {'audit_event_id': str(uuid.UUID(payload['audit_event_id'])),
           'report_id': str(uuid.UUID(payload['report_id'])) if payload['report_id'] else None,
           'revision': int(record['revision']), 'command_digest': digest(command)}
    from datetime import datetime
    ack['received_at'] = datetime.fromisoformat(
        payload['received_at'].replace('Z', '+00:00')
    ).isoformat()
    return ack


def deliver(rt, root, state):
    state = capture_semantic_result(rt, root, state)
    try:
        collect(rt, root, state)
        prepare_semantic(rt, root, state)
    except Exception:
        # A full outbox must still drain before deferred observations/results fit.
        pass
    path = reporting_path(rt, root, state)
    started = time.monotonic()
    with rt.file_lock(path.parent / '.reporting.lock', blocking=False):
        path, box = load_box(rt, root, state)
        for index, entry in enumerate(box['entries']):
            if entry['ack'] is not None:
                continue
            if time.monotonic() - started >= 10:
                break
            try:
                completed = subprocess.run([sys.executable, str(rt.SKILL_ROOT / 'scripts' / 'exec.py'),
                    '_report-send', *rt.runtime_paths.arguments(root), '--project-root', str(root), '--agent', state['agentId'],
                    '--run-id', state['runId'], '--entry', str(index)],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
                output = json.loads(completed.stdout)
                if completed.returncode or not output.get('ack'):
                    raise ReportingError('reporting_delivery_pending')
                entry['ack'] = output['ack']
                box['error'] = None
            except Exception:
                box['error'] = 'reporting_delivery_pending'
                publish(rt, path, box)
                break
            publish(rt, path, box)
        for entry in box['entries']:
            if entry['ack'] is not None:
                key = entry['command']['key']
                if not re.fullmatch(r'local-[a-f0-9]{32}', key):
                    raise ReportingError('reporting_command_conflict')
                publish(rt, path.parent / 'reporting-receipts' / (key + '.json'), entry)
        box['entries'] = [entry for entry in box['entries'] if entry['ack'] is None]
        publish(rt, path, box)
    hook(rt, Path(state['statePath']))
    try:
        # Capacity may have become available during this bounded delivery.
        # Any newly prepared commands remain durable for the next invocation.
        prepare_semantic(rt, root, state)
    except Exception:
        pass
    return status(rt, root, state)
