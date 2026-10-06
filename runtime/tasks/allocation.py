"""Validate Main's optional allocation evidence; never schedule or grant authority."""
from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

from storage.errors import ContractError


def validate(tasks):
    """Keep decisions in taskBinding, using existing scope and workspace owners."""
    if not any('allocation' in task for task in tasks):
        return
    ids = {task['id']: index for index, task in enumerate(tasks)}
    owners = {}

    def fail(message):
        raise ContractError('task_allocation_invalid', message)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    def exact(value, keys):
        if not isinstance(value, dict) or set(value) != set(keys):
            fail('Allocation fields must match schemaVersion 1')

    def evidence(item, dependency=False):
        keys = {'source', 'revision', 'capturedAt', 'confirmed'}
        if dependency and isinstance(item, dict) and 'taskId' in item:
            keys.add('taskId')
        exact(item, keys)
        if not all(text(item.get(key)) for key in ('source', 'revision', 'capturedAt')) or type(item['confirmed']) is not bool:
            fail('Inputs require source, revision, capturedAt and boolean confirmed')
        try:
            captured = datetime.fromisoformat(item['capturedAt'].replace('Z', '+00:00'))
        except ValueError:
            fail('capturedAt must be an ISO timestamp with timezone')
        if captured.tzinfo is None:
            fail('capturedAt must include timezone')

    for task in tasks:
        value = task.get('allocation')
        if 'allocation' not in task:
            continue  # Legacy briefs and historical task lists remain compatible.
        exact(value, {'schemaVersion', 'unitReason', 'profile', 'session', 'inputs',
                      'dependencies', 'readScope', 'writeScopeReason', 'sharedResources', 'parallelCandidate'})
        if type(value['schemaVersion']) is not int or value['schemaVersion'] != 1:
            fail('Unsupported allocation schemaVersion')
        if not text(value['unitReason']) or not text(value['writeScopeReason']):
            fail('Explain the independent outcome and the existing write boundary')
        exact(value['profile'], {'id', 'reason'})
        if not isinstance(value['profile']['id'], str) or value['profile']['id'] not in {'explore', 'workLight', 'work', 'scribe', 'verification'} or not text(value['profile']['reason']):
            fail('Record a supported profile and selection reason; this selects no model')
        exact(value['session'], {'strategy', 'reason'})
        if not isinstance(value['session']['strategy'], str) or value['session']['strategy'] not in {'new', 'reuse'} or not text(value['session']['reason']):
            fail('Explain new/reuse session choice')
        if type(value['parallelCandidate']) is not bool:
            fail('parallelCandidate must be boolean')
        for key in ('inputs', 'dependencies', 'readScope', 'sharedResources'):
            if not isinstance(value[key], list):
                fail(f'{key} must be an array, including empty arrays when absent')
        if any(not text(path) for path in value['readScope']):
            fail('readScope entries must be nonempty paths or source references')
        for item in value['inputs']:
            evidence(item)
        seen_dependencies = set()
        for item in value['dependencies']:
            evidence(item, dependency=True)
            if 'taskId' in item:
                dependency = item['taskId']
                if not isinstance(dependency, str) or dependency not in ids or ids[dependency] >= ids[task['id']]:
                    fail('Local dependencies must identify preceding tasks in this ordered workflow')
                if dependency in seen_dependencies:
                    fail('Duplicate local dependency')
                seen_dependencies.add(dependency)
        for item in value['sharedResources']:
            exact(item, {'resource', 'ownerTaskId', 'confirmed', 'evidence'})
            if not text(item['resource']) or not text(item['evidence']) or type(item['confirmed']) is not bool:
                fail('Shared resources require identity, ownership evidence and boolean confirmed')
            owner = task['id'] if item['ownerTaskId'] == 'self' else item['ownerTaskId']
            if not isinstance(owner, str) or owner not in ids:
                fail('Resource owner must be self or an existing task ID')
            prior = owners.setdefault(item['resource'], owner)
            if prior != owner:
                fail('Conflicting shared resource owners')
        if value['parallelCandidate']:
            if any(not item['confirmed'] for item in value['inputs'] + value['dependencies'] + value['sharedResources']):
                fail('Unconfirmed inputs, dependencies or ownership cannot be parallel-ready')
            if any(item['ownerTaskId'] != 'self' and item['ownerTaskId'] != task['id'] for item in value['sharedResources']):
                fail('A parallel candidate must own the resources it declares')

    # Exact writes come from the existing file operations/document binding, never a second list.
    writes = []
    for task in tasks:
        paths = set(task.get('documentPaths', []))
        operations = task.get('requiredFileOperations', [])
        if not isinstance(operations, list):
            fail('requiredFileOperations must retain its existing array format')
        for operation in operations:
            if not isinstance(operation, dict) or not text(operation.get('path')):
                fail('Invalid existing write operation path')
            if operation.get('destination') is not None and not text(operation['destination']):
                fail('Invalid existing destination path')
            paths.add(operation['path'])
            if operation.get('destination'):
                paths.add(operation['destination'])
        for other, other_paths in writes:
            if (task.get('allocation', {}).get('parallelCandidate') is True
                    or other.get('allocation', {}).get('parallelCandidate') is True):
                if any(a and b and (PurePosixPath(a) == PurePosixPath(b)
                        or PurePosixPath(a) in PurePosixPath(b).parents
                        or PurePosixPath(b) in PurePosixPath(a).parents) for a in paths for b in other_paths):
                    fail('Parallel candidates have overlapping declared writes')
        writes.append((task, paths))


def preserve(previous, current):
    """A same-task continuation may change the request, not its accepted scope/decision."""
    if previous and (previous.get('workflowId'), previous.get('taskId')) == (current.get('workflowId'), current.get('taskId')):
        if {k: v for k, v in previous.items() if k != 'requestHash'} != {k: v for k, v in current.items() if k != 'requestHash'}:
            raise ContractError('task_binding_changed', 'Continue with the accepted task scope and allocation record')
