"""Versioned home registry and immutable per-process project bindings.

No checkout marker, remote URL, credential, or Codex configuration is stored.
Read-only discovery never initializes storage. Rebinding is an explicit operation.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import stat
import uuid
from pathlib import Path

VERSION = 1
PROJECT_ID = re.compile(r"project-[a-f0-9]{32}\Z")
_BINDINGS: dict[str, dict] = {}


def absolute(value) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('runtime paths must be absolute without traversal')
    return path


def inspect(path: Path, *, missing=False):
    """Reject links at every component, including custom-home ancestors."""
    path = absolute(path)
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            if missing:
                return
            raise
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('runtime symlink is forbidden')
        if cursor != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError('runtime ancestor is not a directory')
    return info


def mkdir(path: Path):
    path = absolute(path)
    # Traverse by descriptors so ancestor replacement cannot redirect mkdir.
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('managed directory must be private and owned by this user')
    finally:
        os.close(fd)


def read(path: Path):
    inspect(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4 * 1024 * 1024:
            raise ValueError('invalid registry file')
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('registry file must be private')
        return json.loads(stream.read(4 * 1024 * 1024 + 1))


def write(path: Path, value):
    inspect(path, missing=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextlib.contextmanager
def lock(home: Path):
    mkdir(home)
    fd = os.open(home / '.registry.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('registry lock must be a private regular file')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def home_path(value=None):
    home = absolute(value or os.environ.get('AGENT_FACTORY_HOME') or Path.home() / '.agent-factory')
    inspect(home, missing=True)
    return home


def registry(home: Path):
    path = home / 'registry.json'
    if not path.exists():
        return {'schemaVersion': VERSION, 'projects': {}}
    value = read(path)
    if set(value) != {'schemaVersion', 'projects'} or value['schemaVersion'] != VERSION or not isinstance(value['projects'], dict):
        raise ValueError('unsupported home registry')
    roots = set()
    for key, root in value['projects'].items():
        if not PROJECT_ID.fullmatch(key) or str(absolute(root)) != root or root in roots:
            raise ValueError('ambiguous project registry')
        roots.add(root)
    return value


def document(home, root, project_id):
    runtime = home / 'projects' / project_id if project_id else None
    return {'schemaVersion': VERSION, 'kind': 'runtime-location', 'home': str(home),
            'projectRoot': str(root), 'projectId': project_id,
            'runtimeRoot': str(runtime) if runtime else None,
            'agentsRoot': str(runtime / 'agents') if runtime else None,
            'registered': project_id is not None}


def resolve(root, *, create=False, home=None, project_id=None):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('project root must be a directory')
    prior = _BINDINGS.get(str(root))
    if prior and not create:
        if home is not None and str(home_path(home)) != prior['home'] or project_id is not None and project_id != prior['projectId']:
            raise ValueError('immutable runtime binding changed')
        # Another process can rebind while this client retains its original root.
        projects = registry(home_path(prior['home']))['projects']
        identity = next((key for key, path in projects.items() if path == str(root)), None)
        if identity != prior['projectId']:
            raise ValueError('immutable runtime binding changed')
        return dict(prior)
    if prior:
        if home is not None and str(home_path(home)) != prior['home']:
            raise ValueError('immutable runtime home changed')
        if prior['registered']:
            project_id = project_id or prior['projectId']
    base = home_path(home or (prior and prior['home']))
    if base.is_relative_to(root):
        raise ValueError('runtime home must be outside the code project')
    def lookup():
        marker = base / 'layout.json'
        if marker.exists() and read(marker) != {'schemaVersion': VERSION, 'kind': 'agent-factory-home'}:
            raise ValueError('unsupported home layout')
        value = registry(base)
        found = [key for key, path in value['projects'].items() if path == str(root)]
        identity = found[0] if found else None
        if project_id is not None and identity != project_id:
            raise ValueError('pinned project binding mismatch')
        if create and identity is None:
            identity = 'project-' + uuid.uuid4().hex
            value['projects'][identity] = str(root)
            write(base / 'registry.json', value)
        if create:
            marker = base / 'layout.json'
            if marker.exists():
                if read(marker) != {'schemaVersion': VERSION, 'kind': 'agent-factory-home'}:
                    raise ValueError('unsupported home layout')
            else:
                write(marker, {'schemaVersion': VERSION, 'kind': 'agent-factory-home'})
            mkdir(base / 'projects')
            mkdir(base / 'projects' / identity)
            mkdir(base / 'projects' / identity / 'agents')
        return document(base, root, identity)
    if create:
        with lock(base):
            result = lookup()
    else:
        result = lookup()
    _BINDINGS[str(root)] = result
    return dict(result)


def bind(value):
    if not isinstance(value, dict) or value.get('kind') != 'runtime-location' or not value.get('registered'):
        raise ValueError('invalid pinned runtime binding')
    actual = resolve(value['projectRoot'], home=value['home'], project_id=value['projectId'])
    if actual != value:
        raise ValueError('runtime binding does not match registry')
    return actual


def arguments(root):
    value = resolve(root, create=True)
    return ['--runtime-home', value['home'], '--project-id', value['projectId']]


def anchor(path):
    path = absolute(path)
    for value in _BINDINGS.values():
        if value['runtimeRoot'] and path.is_relative_to(value['runtimeRoot']):
            inspect(path, missing=True)
            return Path(value['runtimeRoot'])
    raise ValueError('path is outside the pinned managed runtime')


def project_for(path):
    runtime = anchor(path)
    return Path(next(value['projectRoot'] for value in _BINDINGS.values() if value['runtimeRoot'] == str(runtime)))


def rebind(home, identity, old_root, new_root):
    base = home_path(home)
    old = str(absolute(old_root))
    new = str(Path(new_root).resolve(strict=True))
    with lock(base):
        value = registry(base)
        if value['projects'].get(identity) == new:
            return document(base, Path(new), identity)
        if value['projects'].get(identity) != old or new in value['projects'].values():
            raise ValueError('rebind source mismatch or destination already registered')
        runtime = base / 'projects' / identity
        # Never move a live session to a different working directory.
        import migration
        members = {str(path): {} for path in (runtime / 'agents').rglob('*') if path.is_file()}
        with migration.quiet({'files': members}):
            for state_path in (runtime / 'agents').glob('*/loops/*/state.json'):
                if read(state_path).get('status') == 'active':
                    raise ValueError('unfinished loop blocks project rebind')
            history = read(runtime / 'relocation.json')['fromRoots'] if (runtime / 'relocation.json').exists() else []
            write(runtime / 'relocation.json', {'schemaVersion': 1, 'fromRoots': list(dict.fromkeys([*history, old])), 'projectRoot': new})
            value['projects'][identity] = new
            write(base / 'registry.json', value)
    _BINDINGS.pop(old, None)
    _BINDINGS.pop(new, None)
    return resolve(Path(new), home=base, project_id=identity)


def project_json(path, value):
    """Resolve historical operational locators without rewriting archived evidence."""
    try:
        runtime = anchor(path)
    except ValueError:
        return value
    marker = runtime / 'migration.json'
    pending = runtime / 'migration-pending.json'
    if pending.exists() and not marker.exists():
        raise ValueError('migration publication is pending recovery')
    binding = next(b for b in _BINDINGS.values() if b['runtimeRoot'] == str(runtime))
    if path.name not in {'state.json', 'session.json', 'native-session.json', 'response.schema.json'}:
        return value
    mapping = {}
    if marker.exists():
        import migration
        record = read(marker)
        expected = Path(binding['home']) / 'migrations' / record['planId'] / 'plan.json'
        if record.get('schemaVersion') != 1 or record.get('planPath') != str(expected):
            raise ValueError('invalid migration overlay')
        plan = migration.validate(read(expected), historical=True)
        mapping = plan['mapping']
    import copy
    result = copy.deepcopy(value)
    def locator(item):
        if not isinstance(item, str) or not marker.exists():
            return item
        candidate = absolute(item)
        for project in sorted(plan['projects'], key=lambda p: len(p['projectRoot']), reverse=True):
            old = Path(project['projectRoot']) / '.agent-factory' / 'agent'
            if not candidate.is_relative_to(old):
                continue
            rel = candidate.relative_to(old)
            # Root-bound Agent locators, including not-yet-created outputs.
            if len(rel.parts) < 2 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', rel.parts[0]):
                raise ValueError('invalid legacy Agent locator')
            return str(Path(project['agentsRoot']) / rel)
        return item
    fields = {'statePath', 'requestPath', 'resultPath', 'eventsPath', 'heartbeatPath',
              'responseSchemaPath', 'receiptPath', 'receiptSchemaPath', 'capabilityBindingPath',
              'nativeSessionPath', 'originalRequestPath'}
    for key in fields.intersection(result):
        result[key] = locator(result[key])
    if path.name == 'response.schema.json':
        field = result.get('properties', {}).get('resultPath', {})
        if 'const' in field:
            field['const'] = locator(field['const'])
    if '/loops/' in str(path):
        pending_dispatch = result.get('pendingDispatch')
        if isinstance(pending_dispatch, dict):
            for key in ('requestPath', 'capabilityBindingPath'):
                if key in pending_dispatch:
                    pending_dispatch[key] = locator(pending_dispatch[key])
        for collection in (result.get('capabilityBindings', {}), result.get('execution', {}).get('reportingConfigs', {})):
            for entry in collection.values():
                if isinstance(entry, dict) and 'path' in entry:
                    entry['path'] = locator(entry['path'])
    if path.name in {'session.json', 'native-session.json'} or '/loops/' in str(path):
        relocation = runtime / 'relocation.json'
        if relocation.exists():
            move = read(relocation)
            if result.get('projectRoot') in move['fromRoots'] and move['projectRoot'] == binding['projectRoot']:
                result['projectRoot'] = binding['projectRoot']
    if path.name in {'session.json', 'native-session.json', 'state.json'}:
        previous_binding = result.get('runtimeBinding')
        if previous_binding is not None and previous_binding != binding:
            relocation = runtime / 'relocation.json'
            if not relocation.exists() or not isinstance(previous_binding, dict):
                raise ValueError('persisted runtime binding mismatch')
            move = read(relocation)
            old_root = previous_binding.get('projectRoot')
            if old_root not in move['fromRoots'] or previous_binding != {**binding, 'projectRoot': old_root}:
                raise ValueError('persisted runtime binding mismatch')
        result['runtimeBinding'] = dict(binding)
    return result


def require_ready(binding):
    if not binding['registered']:
        return
    runtime = Path(binding['runtimeRoot'])
    pending = runtime / 'migration-pending.json'
    if pending.exists():
        record = read(pending)
        identity = record.get('planId')
        if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{64}', identity):
            raise ValueError('invalid pending migration identity')
        journal = read(Path(binding['home']) / 'migrations' / identity / 'journal.json')
        if journal.get('planId') != identity or journal.get('phase') not in {'activated', 'retiring', 'retired'}:
            raise ValueError('migration publication is pending recovery')


def map_evidence(root, original):
    """Return only a manifest-bound historical file, with its immutable digest."""
    import migration
    binding = resolve(root)
    if not binding['registered']:
        raise ValueError('unregistered project has no migration map')
    marker = read(Path(binding['runtimeRoot']) / 'migration.json')
    identity = marker.get('planId')
    if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{64}', identity):
        raise ValueError('invalid migration identity')
    plan = migration.validate(read(Path(binding['home']) / 'migrations' / identity / 'plan.json'), historical=True)
    original = str(absolute(original))
    if original not in plan['files']:
        raise ValueError('historical path is absent from the full migration manifest')
    target = migration.area(plan) / 'archive' / migration.archive_member(plan, original)
    proof = plan['files'][original]
    data = migration.read_bytes(target)
    if len(data) != proof['size'] or migration.hashlib.sha256(data).hexdigest() != proof['sha256']:
        raise ValueError('historical archive bytes differ from the manifest')
    return {'schemaVersion': 1, 'kind': 'runtime-evidence-location', 'planId': identity,
            'originalPath': original, 'archivePath': str(target), 'operationalPath': plan['mapping'].get(original), **proof}
