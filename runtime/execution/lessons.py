"""Capture observable execution failures without retaining tool payloads or secrets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/lessons.py'
# observe() names every runtime capture `<24 hex>.json`. Agents also keep their own lesson
# CLI inputs (resolve, audit, retrieve) in the run; those are never pending captures.
CAPTURE_NAME = re.compile(r'[0-9a-f]{24}\.json')
REPLAY_ATTEMPTS = 3
REPLAY_BACKOFF_SECONDS = 0.5
# One sweep of earlier runs' pending captures: how many it records, how long it may take, and how
# many failed sweeps a capture gets before it is left pending for an Agent to record by hand.
APPLY_LIMIT = 20
APPLY_BUDGET_SECONDS = 20.0
APPLY_ATTEMPTS = 3


def captures(state):
    """Runtime-owned capture inputs of this run, ignoring Agent-authored files beside them."""
    directory = Path(state['statePath']).parent / 'lesson-capture'
    return sorted(path for path in directory.glob('*.json') if CAPTURE_NAME.fullmatch(path.name))


def is_saved(pending):
    receipt = pending.with_suffix('.receipt')
    try:
        return receipt.exists() and json.loads(receipt.read_text()).get('saved') is True
    except ValueError:
        return False


def read_only(state):
    return state.get('executionPolicy', {}).get('sandboxPolicy', {}).get('type') == 'read-only'


def record_root(project_root, state):
    """Where a run's captures belong: the code Work Unit that holds the project's lessons, else the project.

    An isolated run's lessons are committed and merged with its task instead of dirtying the
    source checkout the task integrates into. Shared, read-only and unbound runs keep the project."""
    root = Path(project_root)
    workspace = state.get('taskWorkspace')
    if not isinstance(workspace, dict) or workspace.get('mode') != 'code':
        return root
    for unit in workspace.get('repositories') or []:
        if not isinstance(unit, dict) or not unit.get('repositoryRoot') or not unit.get('path'):
            continue
        source = Path(unit['repositoryRoot'])
        if root.is_relative_to(source):
            return Path(unit['path']) / root.relative_to(source)
    return root


def recorded_paths(states, workspace_id):
    """Project-relative lesson files the runtime recorded into one code Work Unit."""
    paths = set()
    for state in states:
        workspace = state.get('taskWorkspace')
        if not isinstance(workspace, dict) or workspace.get('id') != workspace_id:
            continue
        for pending in captures(state):
            try:
                receipt = json.loads(pending.with_suffix('.receipt').read_text())
            except (OSError, ValueError):
                continue
            if isinstance(receipt, dict) and receipt.get('saved') is True and isinstance(receipt.get('path'), str):
                paths.add(receipt['path'])
    return paths


def pending_count(state):
    """Captures of this run that the project does not hold yet; never raises."""
    try:
        return len(audit(state))
    except (OSError, KeyError, TypeError, AttributeError):
        return 0


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
    if read_only(state):
        return {'saved': False, 'pending': str(pending), 'reason': 'project-read-only'}
    result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(record_root(project_root, state)),
                             'record', '--input', str(pending)], capture_output=True, text=True, timeout=20)
    receipt = capture_dir / f'{key}.receipt'
    if result.returncode:
        receipt.write_text(json.dumps({'saved': False, 'occurrenceId': occurrence}), encoding='utf-8')
        return {'saved': False, 'pending': str(pending)}
    saved = json.loads(result.stdout)
    receipt.write_text(json.dumps({'saved': True, 'occurrenceId': occurrence, **saved}), encoding='utf-8')
    return {'saved': True, **saved}


def audit(state):
    return [str(pending) for pending in captures(state) if not is_saved(pending)]


def replay(project_root, state):
    """Retry only unsaved durable capture inputs, never rerun the failed tool.

    Recording is idempotent per occurrence, so a failed write (lock contention, a slow
    disk, a concurrent writer) is retried a bounded number of times before it is reported.
    """
    if read_only(state):
        return
    root = record_root(project_root, state)
    for attempt in range(REPLAY_ATTEMPTS):
        remaining = [pending for pending in captures(state) if not is_saved(pending)]
        if not remaining:
            return
        if attempt:
            time.sleep(REPLAY_BACKOFF_SECONDS * attempt)
        for pending in remaining:
            try:
                result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(root),
                                         'record', '--input', str(pending)], capture_output=True, text=True, timeout=20)
            except subprocess.TimeoutExpired:
                continue
            if result.returncode == 0:
                pending.with_suffix('.receipt').write_text(
                    json.dumps({'saved': True, **json.loads(result.stdout)}), encoding='utf-8')


def apply_pending(project_root, state, *, clock=time.monotonic):
    """Record captures that earlier runs of this project left pending; returns how many were saved.

    A read-only run cannot write the project and a failed write stays in its run, so the next run that
    may write the project records them, after its own outcome is stored. Recording is idempotent per
    occurrence, so concurrent sweeps and repeats never duplicate a record. The sweep is bounded by
    count, time and attempts per capture; whatever it cannot save stays pending in its run.

    Captures of a run bound to a code Work Unit belong to that Unit, and only their own run records
    them there. While the Unit exists the sweep leaves them pending: recording them into the project
    would dirty the checkout the task integrates into, and writing into the Unit could race its
    integration commit. Every capture the sweep records has a unique runtime name that no task
    branch contains, so it never overlaps a merge and cannot block integration."""
    run_directory = Path(state['statePath']).parent
    if read_only(state) or run_directory.parent.name != 'runs':
        return 0
    deadline = clock() + APPLY_BUDGET_SECONDS
    applied = 0
    for directory in sorted(run_directory.parents[2].glob('*/runs/*/lesson-capture')):
        try:
            owner = json.loads((directory.parent / 'state.json').read_text())
        except (OSError, ValueError):
            owner = {}
        owned = record_root(project_root, owner) if isinstance(owner, dict) else Path(project_root)
        if owned != Path(project_root) and owned.exists():
            continue
        for pending in sorted(path for path in directory.glob('*.json') if CAPTURE_NAME.fullmatch(path.name)):
            if applied >= APPLY_LIMIT or clock() >= deadline:
                return applied
            receipt = pending.with_suffix('.receipt')
            try:
                recorded = json.loads(receipt.read_text()) if receipt.exists() else {}
            except ValueError:
                recorded = {}
            if not isinstance(recorded, dict):
                recorded = {}
            attempts = recorded.get('applyAttempts', 0)
            if recorded.get('saved') is True or not isinstance(attempts, int) or attempts >= APPLY_ATTEMPTS:
                continue
            try:
                result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(project_root),
                                         'record', '--input', str(pending)], capture_output=True, text=True,
                                        timeout=max(1.0, min(20.0, deadline - clock())))
                saved = json.loads(result.stdout) if result.returncode == 0 else None
            except (subprocess.SubprocessError, ValueError):
                saved = None
            if isinstance(saved, dict):
                receipt.write_text(json.dumps({**recorded, 'saved': True, **saved, 'appliedBy': str(state.get('runId'))}),
                                   encoding='utf-8')
                applied += 1
            else:
                receipt.write_text(json.dumps({**recorded, 'saved': False, 'applyAttempts': attempts + 1}), encoding='utf-8')
    return applied
