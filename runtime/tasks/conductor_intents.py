"""Validated intent plans and conservative resource admission for the queue ledger.

The model supplies semantic decomposition; this module checks the DAG and write
ownership rather than guessing goals from punctuation. Everything runs in Store.tx.
"""
from collections import deque
from pathlib import PurePosixPath, PureWindowsPath

from storage.errors import ContractError


def require(ok, message):
    if not ok:
        raise ContractError('intent_plan_invalid', message)


def scope_paths(value):
    require(isinstance(value, list) and all(isinstance(p, str) and p for p in value), 'Explicit writeScope list required')
    paths = []
    for item in value:
        path = PurePosixPath(item.replace('\\', '/'))
        require(not path.is_absolute() and not PureWindowsPath(item).drive and '..' not in path.parts, 'Write scope must stay inside the project')
        # Globs reserve their static parent. Unknown/full-tree scopes reserve the project.
        parts = []
        for part in path.parts:
            if any(c in part for c in '*?['):
                break
            parts.append(part)
        paths.append('/'.join(parts) or '.')
    return paths


def overlap(left, right):
    return any(a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/')
               for a in left for b in right)


def validate(items):
    require(isinstance(items, list) and len(items) >= 2, 'Split needs at least two bounded intents')
    keys, result = set(), []
    for item in items:
        require(isinstance(item, dict), 'Intent must be an object')
        key = item.get('key')
        require(isinstance(key, str) and key and key not in keys, 'Intent keys must be unique')
        keys.add(key)
        require(all(isinstance(item.get(k), str) and item[k].strip() for k in ('title', 'reason')), 'Title and separation reason required')
        spec = item.get('spec')
        require(isinstance(spec, dict) and all(isinstance(spec.get(k), str) and spec[k].strip()
                                              for k in ('goal', 'completionCriteria')), 'Goal and completion criteria required')
        scope_paths(spec.get('writeScope'))
        workspace = spec.get('workspace')
        require(isinstance(workspace, dict) and workspace.get('mode') in ('shared', 'code', 'read-only'), 'Explicit workspace mode required')
        require(workspace['mode'] != 'read-only' or not spec['writeScope'], 'Read-only intent cannot have a write scope')
        if workspace['mode'] == 'code':
            require(isinstance(workspace.get('repositories'), list) and workspace['repositories'], 'Code isolation needs exact repositories and checks')
        deps = item.get('dependsOn', [])
        resources = spec.get('sharedResources', [])
        require(isinstance(deps, list) and all(isinstance(d, str) for d in deps), 'Dependency keys required')
        require(isinstance(resources, list) and all(isinstance(r, str) and r for r in resources), 'Shared resource names required')
        result.append({**item, 'dependsOn': list(dict.fromkeys(deps)), 'spec': {**spec, 'sharedResources': resources}})
    for item in result:
        require(set(item['dependsOn']) <= keys and item['key'] not in item['dependsOn'], 'Unknown or self dependency')
    # Iterative topological ordering also handles large plans without recursion limits.
    by_key = {item['key']: item for item in result}
    degree = {item['key']: len(item['dependsOn']) for item in result}
    successors = {key: [] for key in by_key}
    for item in result:
        for dep in item['dependsOn']:
            successors[dep].append(item['key'])
    ready = deque(key for key, count in degree.items() if not count)
    ordered = []
    while ready:
        key = ready.popleft()
        ordered.append(by_key[key])
        for successor in successors[key]:
            degree[successor] -= 1
            if not degree[successor]:
                ready.append(successor)
    require(len(ordered) == len(result), 'Dependency cycle')
    for n, item in enumerate(ordered):
        conflicts = [old for old in ordered[:n] if conflict(item['spec'], old['spec'])]
        for old in conflicts:
            if old['key'] not in item['dependsOn']:
                item['dependsOn'].append(old['key'])
        item['parallelCandidate'] = not item['dependsOn'] and not any(conflict(item['spec'], other['spec'])
                                                                    for other in ordered if other is not item)
        item['admissionReason'] = 'shared-write-or-resource' if conflicts else 'dependency' if item['dependsOn'] else 'independent-scopes'
    return ordered


def conflict(a, b):
    wa, wb = a.get('workspace', {}), b.get('workspace', {})
    if set(a.get('sharedResources', [])) & set(b.get('sharedResources', [])):
        return True
    if overlap(scope_paths(a.get('writeScope', ['.'])), scope_paths(b.get('writeScope', ['.']))):
        return True
    # Even disjoint shared writes can both stage/commit to the same index. Reserve
    # the whole shared checkout; isolated code tasks own their private index.
    return wa.get('mode', 'shared') == wb.get('mode', 'shared') == 'shared'
