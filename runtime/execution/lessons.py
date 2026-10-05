"""Capture observable execution failures without retaining tool payloads or secrets.

The project keeps one aggregate record per failure signature (provider, role, command kind and
exit code) and appends every occurrence to it; raw commands and outputs stay out of the project."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
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
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'fish', 'pwsh', 'powershell'}
SEARCH = {'rg', 'grep', 'egrep', 'fgrep', 'ag', 'ack'}
TEST = re.compile(r'\b(pytest|vitest|jest|mocha|unittest|playwright\s+test|node\s+--test|(npm|pnpm|yarn)\s+(run\s+)?test'
                  r'|cargo\s+test|go\s+test)\b|\b(node|python3?|uv\s+run\s+\S*)\s+\S*\btests?/')
BUILD = re.compile(r'\b(ruff|mypy|tsc|eslint|make|cmake|vsce|(npm|pnpm|yarn)\s+run\s+(build|lint|compile|package)'
                   r'|cargo\s+(build|check|clippy)|go\s+(build|vet))\b')
FIRST_WORD = {**{name: 'search' for name in SEARCH | {'find', 'fd'}}, 'git': 'git',
              **{name: 'script' for name in ('python', 'python3', 'node', 'uv', 'npx', 'deno', 'bun')},
              **{name: 'read' for name in ('cat', 'sed', 'head', 'tail', 'ls', 'wc', 'stat', 'jq', 'diff', 'test', '[', 'file', 'tree')}}
CLAUDE_EXIT = re.compile(r'\AExit code -?\d+\s*')


def unwrap(command):
    """The script a shell wrapper such as `/usr/bin/zsh -lc '…'` runs, else the command itself."""
    command = command if isinstance(command, str) else ' '.join(map(str, command)) if isinstance(command, list) else ''
    try:
        words = shlex.split(command)
    except ValueError:
        return command.strip()
    if len(words) == 3 and Path(words[0]).name in SHELLS and words[1] in ('-c', '-lc', '-Command'):
        return words[2].strip()
    return command.strip()


def last_command(script):
    """First word of the last simple command, skipping `VAR=value` assignments and `sudo`/`env`."""
    if '<<' in script:
        script = script.split('<<', 1)[0]
    segment = re.split(r'&&|\|\||[;|\n]', script.strip())[-1] if script.strip() else ''
    for word in segment.split():
        if '=' in word and not word.startswith('='):
            continue
        if word in ('sudo', 'env', 'time', 'command', 'exec'):
            continue
        return Path(word.strip('()')).name
    return ''


def command_kind(command):
    """A coarse, payload-free label for what a failed command did."""
    script = unwrap(command)
    if 'lessons.py' in script:
        return 'lessons-cli'
    if TEST.search(script):
        return 'test'
    if BUILD.search(script):
        return 'build'
    if '<<' in script and re.match(r'\s*(python3?|node|uv)\b', script):
        return 'script'
    return FIRST_WORD.get(last_command(script), 'other')


def output_text(item):
    """The command's visible output, with Claude's `Exit code N` preamble removed."""
    value = item.get('aggregated_output', item.get('aggregatedOutput'))
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except ValueError:
            decoded = value
        value = decoded if isinstance(decoded, (str, list)) else value
    if isinstance(value, list):
        value = ''.join(str(block.get('text', '')) if isinstance(block, dict) else str(block) for block in value)
    return CLAUDE_EXIT.sub('', value, count=1).strip() if isinstance(value, str) else ''


def no_match(item):
    """grep and rg report an empty search with exit code 1; that is a result, not an error."""
    return (item.get('exit_code') == 1 and last_command(unwrap(item.get('command'))) in SEARCH
            and not output_text(item))


def succeeded(item):
    """Codex reports exit code 0; Claude and Antigravity report a completed command without one."""
    exit_code = item.get('exit_code')
    return item.get('type') == 'command_execution' and (
        exit_code == 0 or exit_code is None and item.get('status') == 'completed' and not item.get('error'))


def command_hash(item):
    return hashlib.sha256(unwrap(item.get('command')).encode()).hexdigest()


def classify(event, state):
    """The failure signature of an event, or None when it is not a recordable failure."""
    item = event.get('item', {})
    if not isinstance(item, dict):
        item = {}
    if event.get('type') in ('error', 'goal.error', 'runtime.failure'):
        code, kind = str(event.get('code', event['type'])), 'runtime'
    elif event.get('type') != 'item.completed':
        return None
    elif item.get('type') == 'command_execution':
        exit_code = item.get('exit_code')
        if isinstance(exit_code, int) and exit_code != 0:
            if no_match(item):
                return None
            code = f'command-exit-{exit_code}'
        elif not isinstance(exit_code, int) and (item.get('status') == 'failed' or item.get('error')):
            code = 'command-failed'  # Claude and Antigravity report some failed commands without an exit code.
        else:
            return None
        kind = command_kind(item.get('command'))
    elif item.get('type') in ('mcp_tool_call', 'tool_call') and (
        item.get('status') == 'failed' or item.get('error') or
        (isinstance(item.get('result'), dict) and item['result'].get('isError') is True)
    ):
        code, kind = 'tool-error', 'tool'
    else:
        return None
    return {'provider': str(state.get('provider') or 'codex'), 'role': str(state.get('role') or 'unknown'),
            'kind': kind, 'code': code}


def signature_id(signature):
    """The project record of a signature: `runtime-<24 hex>`, stable across runs and Agents."""
    text = json.dumps({key: signature[key] for key in ('provider', 'role', 'kind', 'code')}, sort_keys=True)
    return 'runtime-' + hashlib.sha256(text.encode()).hexdigest()[:24]


def signature_title(signature):
    return f'{signature["code"]} ({signature["kind"]}, {signature["provider"]} {signature["role"]})'


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
    return (state.get('workProfile') == 'explore'
            or state.get('executionPolicy', {}).get('sandboxPolicy', {}).get('type') == 'read-only')


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
        if source == root / 'docs' and Path(unit['path']).name == 'docs':
            return Path(unit['path']).parent
    return root



def document_workspace_available(project_root, state):
    workspace = state.get('taskWorkspace')
    if not isinstance(workspace, dict) or workspace.get('mode') != 'code':
        return True
    return any(isinstance(unit, dict) and unit.get('repositoryRoot') and unit.get('path') and
               (Path(project_root).is_relative_to(Path(unit['repositoryRoot'])) or
                (Path(unit['repositoryRoot']) == Path(project_root) / 'docs' and Path(unit['path']).name == 'docs'))
               for unit in workspace.get('repositories') or [])

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


def record(project_root, state, pending):
    """Record one capture input and store its receipt; returns the observe() result."""
    if not document_workspace_available(project_root, state):
        return {'saved': False, 'pending': str(pending), 'reason': 'document-workspace-unavailable'}
    blocked = storage_block(project_root, state)
    if blocked:
        return {'saved': False, 'pending': str(pending), 'reason': 'lesson-storage-blocked', **blocked}
    result = subprocess.run([sys.executable, str(SCRIPT), '--project-root', str(project_root), '--documents-root', str(record_root(project_root, state)),
                             'record', '--input', str(pending)], capture_output=True, text=True, timeout=20)
    occurrence = json.loads(pending.read_text(encoding='utf-8'))['occurrenceId']
    receipt = pending.with_suffix('.receipt')
    if result.returncode:
        blocked = block_storage_failure(project_root, state, result)
        receipt.write_text(json.dumps({'saved': False, 'occurrenceId': occurrence, **blocked}), encoding='utf-8')
        return {'saved': False, 'pending': str(pending), **blocked}
    saved = json.loads(result.stdout)
    receipt.write_text(json.dumps({'saved': True, 'occurrenceId': occurrence, **saved}), encoding='utf-8')
    return {'saved': True, **saved}


def storage_block(project_root, state):
    """A permanent storage failure blocks only this run and physical document workspace."""
    path = Path(state['statePath']).parent / 'lesson-storage-block.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if (isinstance(value, dict) and value.get('projectRoot') == str(Path(project_root).resolve())
            and value.get('documentsRoot') == str(record_root(project_root, state).resolve())
            and isinstance(value.get('diagnostic'), dict)):
        return {'reason': 'lesson-storage-blocked', 'diagnostic': value['diagnostic']}
    return None


def block_storage_failure(project_root, state, result):
    try:
        diagnostic = json.loads(result.stdout)
    except (TypeError, ValueError):
        return {}
    if not isinstance(diagnostic, dict) or diagnostic.get('code') != 'lesson_storage_incompatible' or diagnostic.get('retryable') is not False:
        return {}
    path = Path(state['statePath']).parent / 'lesson-storage-block.json'
    path.write_text(json.dumps({'projectRoot': str(Path(project_root).resolve()),
                               'documentsRoot': str(record_root(project_root, state).resolve()),
                               'diagnostic': diagnostic}), encoding='utf-8')
    return {'reason': 'lesson-storage-blocked', 'diagnostic': diagnostic}


def recover(project_root, state, item, event_key):
    """Mark this run's earlier failures of the same command as recovered by its later success."""
    directory = Path(state['statePath']).parent / 'lesson-capture'
    if item.get('type') != 'command_execution' or not directory.is_dir():
        return None
    digest = command_hash(item)
    result = None
    for marker in sorted(directory.glob('*.command')):
        if marker.read_text(encoding='utf-8').strip() != digest:
            continue
        pending = marker.with_suffix('.json')
        marker.unlink()
        if not pending.is_file():
            continue
        payload = json.loads(pending.read_text(encoding='utf-8'))
        payload.update({'recovered': True, 'recoveredBy': event_key})
        pending.write_text(json.dumps(payload), encoding='utf-8')
        pending.with_suffix('.receipt').unlink(missing_ok=True)
        if not read_only(state):
            result = record(project_root, state, pending)
    return result


def observe(project_root, state, event, attempt=0):
    item = event.get('item', {})
    if not isinstance(item, dict):
        item = {}
    signature = classify(event, state)
    if signature is None:
        if event.get('type') == 'item.completed' and succeeded(item) and item.get('id'):
            return recover(project_root, state, item, str(item['id']))
        return None
    code = signature['code']
    run = str(state['runId'])
    agent = str(state['agentId'])
    run_dir = Path(state['statePath']).parent
    capture_dir = run_dir / 'lesson-capture'
    capture_dir.mkdir(exist_ok=True)
    event_key = str(item.get('id') or event.get('id') or (code if event.get('type') == 'runtime.failure' else uuid.uuid4().hex))
    occurrence = f'{agent}:{run}:{attempt}:{event_key}:{code}'
    key = hashlib.sha256(occurrence.encode()).hexdigest()[:24]
    title = signature_title(signature)
    # Never copy raw command, output or error messages to durable project documents.
    payload = {'id': signature_id(signature), 'category': 'error', 'title': title,
               'language': state.get('language', 'en'), 'occurrenceId': occurrence,
               'source': f'agent:{agent}/run:{run}/attempt:{attempt}/event:{event_key}',
               'scope': 'runtime', 'signature': signature, 'symptom': title, 'cause': 'unknown',
               'solution': 'unresolved', 'verification': 'not checked'}
    pending = capture_dir / f'{key}.json'
    if not pending.exists():
        pending.write_text(json.dumps(payload), encoding='utf-8')
        if signature['kind'] not in ('runtime', 'tool'):
            # Run-local only: lets a later success of the same command mark this occurrence recovered.
            pending.with_suffix('.command').write_text(command_hash(item), encoding='utf-8')
    if read_only(state):
        return {'saved': False, 'pending': str(pending), 'reason': 'project-read-only'}
    return record(project_root, state, pending)


def audit(state):
    return [str(pending) for pending in captures(state) if not is_saved(pending)]


def replay(project_root, state):
    """Retry only unsaved durable capture inputs, never rerun the failed tool.

    Recording is idempotent per occurrence, so a failed write (lock contention, a slow
    disk, a concurrent writer) is retried a bounded number of times before it is reported.
    """
    if read_only(state) or not document_workspace_available(project_root, state):
        return
    if storage_block(project_root, state):
        return
    for attempt in range(REPLAY_ATTEMPTS):
        remaining = [pending for pending in captures(state) if not is_saved(pending)]
        if not remaining:
            return
        if attempt:
            time.sleep(REPLAY_BACKOFF_SECONDS * attempt)
        for pending in remaining:
            try:
                result = record(project_root, state, pending)
            except subprocess.TimeoutExpired:
                continue
            if result.get('reason') == 'lesson-storage-blocked':
                return


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
    if read_only(state) or not document_workspace_available(project_root, state) or run_directory.parent.name != 'runs':
        return 0
    if storage_block(project_root, state):
        return 0
    deadline = clock() + APPLY_BUDGET_SECONDS
    applied = 0
    for directory in sorted(run_directory.parents[2].glob('*/runs/*/lesson-capture')):
        try:
            owner = json.loads((directory.parent / 'state.json').read_text())
        except (OSError, ValueError):
            owner = {}
        owned = record_root(project_root, owner) if isinstance(owner, dict) else Path(project_root)
        workspace = owner.get('taskWorkspace', {}) if isinstance(owner, dict) else {}
        if (owned != Path(project_root) and owned.exists()) or (workspace.get('mode') == 'code' and
                any(Path(unit['path']).exists() for unit in workspace.get('repositories', []) if unit.get('path'))):
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
                if result.returncode:
                    blocked = block_storage_failure(project_root, state, result)
                    if blocked:
                        receipt.write_text(json.dumps({**recorded, 'saved': False, **blocked}), encoding='utf-8')
                        return applied
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
