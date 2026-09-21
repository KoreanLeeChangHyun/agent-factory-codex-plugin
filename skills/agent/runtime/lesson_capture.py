"""Capture observable execution failures without retaining tool payloads or secrets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

SCRIPT = Path(__file__).resolve().parents[2] / 'document/scripts/lessons.py'


def observe(project_root, state, event, attempt=0):
    item = event.get('item', {})
    code = None
    if event.get('type') in ('error', 'goal.error', 'runtime.failure'):
        code = str(event.get('code', event['type']))
    elif event.get('type') == 'item.completed' and isinstance(item, dict):
        if item.get('type') == 'command_execution' and isinstance(item.get('exit_code'), int) and item['exit_code'] != 0:
            code = f'command-exit-{item["exit_code"]}'
        elif item.get('type') in ('mcp_tool_call', 'tool_call') and (
            item.get('status') == 'failed' or item.get('error') or
            (isinstance(item.get('result'), dict) and item['result'].get('isError') is True)
        ):
            code = 'tool-error'
    if code is None:
        return None
    run = str(state['runId'])
    agent = str(state['agentId'])
    run_dir = Path(state['statePath']).parent
    capture_dir = run_dir / 'lesson-capture'
    capture_dir.mkdir(exist_ok=True)
    event_key = str(item.get('id') or event.get('id') or (code if event.get('type') == 'runtime.failure' else uuid.uuid4().hex))
    occurrence = f'{agent}:{run}:{attempt}:{event_key}:{code}'
    key = hashlib.sha256(occurrence.encode()).hexdigest()[:24]
    # Never copy raw command, output or error messages to durable project documents.
    payload = {'id': 'runtime-' + key, 'category': 'error', 'title': code,
               'language': state.get('language', 'en'), 'occurrenceId': occurrence,
               'source': f'agent:{agent}/run:{run}/attempt:{attempt}/event:{event_key}',
               'scope': 'runtime', 'symptom': code, 'cause': 'unknown',
               'solution': 'unresolved', 'verification': 'not checked'}
    pending = capture_dir / f'{key}.json'
    if not pending.exists():
        pending.write_text(json.dumps(payload), encoding='utf-8')
    if state.get('executionPolicy', {}).get('sandboxPolicy', {}).get('type') == 'read-only':
        return {'saved': False, 'pending': str(pending), 'reason': 'project-read-only'}
    result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(project_root),
                             'record', '--input', str(pending)], capture_output=True, text=True, timeout=20)
    receipt = capture_dir / f'{key}.receipt'
    if result.returncode:
        receipt.write_text(json.dumps({'saved': False, 'occurrenceId': occurrence}), encoding='utf-8')
        return {'saved': False, 'pending': str(pending)}
    saved = json.loads(result.stdout)
    receipt.write_text(json.dumps({'saved': True, 'occurrenceId': occurrence, **saved}), encoding='utf-8')
    return {'saved': True, **saved}


def audit(state):
    directory = Path(state['statePath']).parent / 'lesson-capture'
    missing = []
    for pending in directory.glob('*.json'):
        receipt = pending.with_suffix('.receipt')
        if not receipt.exists() or json.loads(receipt.read_text()).get('saved') is not True:
            missing.append(str(pending))
    return missing


def replay(project_root, state):
    """Retry only unsaved durable capture inputs, never rerun the failed tool."""
    directory = Path(state['statePath']).parent / 'lesson-capture'
    if state.get('executionPolicy', {}).get('sandboxPolicy', {}).get('type') == 'read-only':
        return
    for pending in directory.glob('*.json'):
        receipt = pending.with_suffix('.receipt')
        if receipt.exists() and json.loads(receipt.read_text()).get('saved') is True:
            continue
        result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(project_root),
                                 'record', '--input', str(pending)], capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            receipt.write_text(json.dumps({'saved': True, **json.loads(result.stdout)}), encoding='utf-8')
