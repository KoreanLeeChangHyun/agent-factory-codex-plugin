"""Real subprocess capture, redaction, pending failures and duplicate delivery."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('lesson_capture_test_module', ROOT / 'skills/agent/runtime/lesson_capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def test_capture_nonzero_and_ignore_success(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    state = {'statePath': str(run / 'state.json'), 'runId': 'r1', 'agentId': 'a1'}
    event = {'type': 'item.completed', 'item': {'type': 'command_execution', 'id': 'item1', 'exit_code': 1, 'command': 'secret=DO_NOT_SAVE'}}
    assert capture.observe(tmp_path, state, event, 1)['saved']
    assert capture.observe(tmp_path, state, event, 1)['saved']
    records = list((tmp_path / 'docs/lessons-learned').glob('*.json'))
    assert len(records) == 1
    text = records[0].read_text()
    assert 'DO_NOT_SAVE' not in text
    assert len(json.loads(text)['occurrences']) == 1
    assert capture.audit(state) == []
    event['item']['exit_code'] = 0
    assert capture.observe(tmp_path, state, event, 1) is None


def test_pending_on_storage_failure(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    state = {'statePath': str(run / 'state.json'), 'runId': 'r2', 'agentId': 'a1'}
    with patch.object(capture.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failure')):
        result = capture.observe(tmp_path, state, {'type': 'runtime.failure', 'code': 'launch_failed'})
    assert result['saved'] is False
    assert len(capture.audit(state)) == 1
    assert capture.observe(tmp_path, state, {'type': 'runtime.failure', 'code': 'launch_failed'})['saved']
    assert capture.audit(state) == []


def test_replay_and_unidentified_errors(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    state = {'statePath': str(run / 'state.json'), 'runId': 'r3', 'agentId': 'a1'}
    event = {'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'status': 'failed'}}
    with patch.object(capture.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'failure')):
        capture.observe(tmp_path, state, event)
        capture.observe(tmp_path, state, event)
    assert len(capture.audit(state)) == 2
    capture.replay(tmp_path, state)
    assert capture.audit(state) == []
    assert len(list((tmp_path / 'docs/lessons-learned').glob('*.json'))) == 2


def test_read_only_never_writes_project(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    state = {'statePath': str(run / 'state.json'), 'runId': 'r4', 'agentId': 'a1',
             'executionPolicy': {'sandboxPolicy': {'type': 'read-only'}}}
    result = capture.observe(tmp_path, state, {'type': 'runtime.failure', 'code': 'failed'})
    assert result['reason'] == 'project-read-only'
    capture.replay(tmp_path, state)
    assert not (tmp_path / 'docs').exists()
    assert len(capture.audit(state)) == 1
