"""Deterministic, gated legacy runtime relocation. No model or network calls.

Archive bytes remain unchanged. The runtime reads a separate operational copy
through an explicit locator overlay. Invalid inactive records remain archive-only.
"""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path
sys.dont_write_bytecode = True
import paths

ACTIVE = {'accepted', 'queued', 'starting', 'running', 'cancelling'}
KEYS = {'schemaVersion', 'kind', 'home', 'projects', 'files', 'directories', 'mapping', 'archiveOnly', 'planId'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_bytes(path):
    paths.inspect(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('migration accepts regular files only')
        data = stream.read()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('source changed during inventory')
        return data


def inventory(roots):
    files, directories = {}, []
    for root in sorted(roots):
        source = paths.absolute(root) / '.agent-factory'
        paths.inspect(source)
        for directory, names, members in os.walk(source, followlinks=False):
            names.sort(); members.sort()
            paths.inspect(Path(directory))
            directories.append(str(Path(directory)))
            for name in names:
                paths.inspect(Path(directory) / name)
            for name in members:
                path = Path(directory) / name
                data = read_bytes(path)
                files[str(path)] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return files, directories


def runtime_owner():
    import importlib.util
    module = globals().get('_runtime_owner')
    if module is None:
        spec = importlib.util.spec_from_file_location('migration_runtime_owner', Path(__file__).parents[1] / 'scripts/exec.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        globals()['_runtime_owner'] = module
    return module


def writer_free(state):
    """Stale status is not liveness; unknown identity is never writer exclusion."""
    rt = runtime_owner()
    observed = False
    for key, pid_key in (('workerIdentity', 'workerPid'), ('codexIdentity', 'codexPid')):
        identity = state.get(key)
        if identity is not None:
            observed = True
            status = rt.process_identity_status(identity)
            if status in {'match', 'unknown'}:
                raise ValueError('live or unverifiable managed process blocks migration')
        elif state.get(pid_key):
            raise ValueError('unbound legacy PID requires authoritative reconciliation')
    containment = state.get('containment')
    if containment is not None:
        observed = True
        try:
            if not rt.containment_is_empty(containment):
                raise ValueError('populated containment blocks migration')
        except rt.ContractError as error:
            raise ValueError('unverifiable containment blocks migration') from error
    if state.get('status') in ACTIVE and not observed:
        raise ValueError('active record lacks authoritative writer exclusion')


def tree(root):
    """Complete relative inventory, including empty directories and object identity."""
    root = paths.absolute(root)
    paths.inspect(root)
    files, directories, identities = {}, set(), {}
    for directory, names, members in os.walk(root, followlinks=False):
        names.sort(); members.sort()
        here = Path(directory)
        info = paths.inspect(here)
        relative = here.relative_to(root).as_posix()
        directories.add(relative)
        identities[relative] = [info.st_dev, info.st_ino]
        for name in names:
            if not stat.S_ISDIR(paths.inspect(here / name).st_mode):
                raise ValueError('unsafe directory inventory')
        for name in members:
            target = here / name
            data = read_bytes(target)
            key = target.relative_to(root).as_posix()
            files[key] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            info = target.lstat()
            identities[key] = [info.st_dev, info.st_ino]
    return files, directories, identities


def expected_tree(files):
    directories = {'.'}
    for name in files:
        directories.update(parent.as_posix() for parent in Path(name).parents)
    return directories


def bounded_tree(root, files, directories=None, *, partial=False, identities=None):
    expected_dirs = expected_tree(files) if directories is None else set(directories)
    actual, dirs, ids = tree(root)
    if not set(actual).issubset(files) or not dirs.issubset(expected_dirs):
        raise ValueError('foreign file or directory in migration tree')
    if not partial and (set(actual) != set(files) or dirs != expected_dirs):
        raise ValueError('migration tree inventory is incomplete')
    if any(proof != files[name] for name, proof in actual.items()):
        raise ValueError('migration tree bytes changed')
    if identities is not None and any(ids[name] != identities.get(name) for name in ids):
        raise ValueError('migration tree object was replaced')
    return actual, dirs, ids


def source_expected(plan, binding):
    source = Path(binding['projectRoot']) / '.agent-factory'
    files = {Path(name).relative_to(source).as_posix(): proof for name, proof in plan['files'].items() if Path(name).is_relative_to(source)}
    dirs = {Path(name).relative_to(source).as_posix() for name in plan['directories'] if Path(name).is_relative_to(source)}
    return files, dirs


def copied_inventory(plan):
    journal = paths.read(area(plan) / 'journal.json')
    archive_files, archive_dirs = {}, {'.'}
    backup_files, backup_dirs = {}, {'.'}
    projection_files, projection_dirs = {}, {'.'}
    for binding in plan['projects']:
        files, dirs = source_expected(plan, binding)
        member = binding['projectId']
        archive_dirs.update({member, *(member + '/' + name for name in dirs if name != '.')})
        backup_dirs.update({member, *(member + '/' + name for name in dirs if name != '.')})
        archive_files.update({member + '/' + name: proof for name, proof in files.items()})
        backup_files.update({member + '/' + name: proof for name, proof in files.items()})
        source = Path(binding['projectRoot']) / '.agent-factory'
        projection = {member + '/' + Path(name).relative_to(source).as_posix(): proof
                      for name, proof in plan['files'].items()
                      if name in plan['mapping'] and Path(name).is_relative_to(source)}
        projection_files.update(projection)
        projection_dirs.update(expected_tree(projection))
    bounded_tree(area(plan) / 'archive', archive_files, archive_dirs)
    bounded_tree(Path(journal['backup']) / plan['planId'], backup_files, backup_dirs)
    bounded_tree(area(plan) / 'projection', projection_files, projection_dirs)
    return journal


def publication_inventory(plan, binding, *, complete):
    """Allow only manifest files and a bounded interrupted-copy prefix."""
    root = Path(binding['agentsRoot'])
    expected = {Path(target).relative_to(root).as_posix(): plan['files'][source]
                for source, target in plan['mapping'].items() if Path(target).is_relative_to(root)}
    actual, directories, _ = tree(root)
    for name in list(actual):
        path = Path(name)
        if not path.name.startswith('.') or not path.name.endswith('.staging'):
            continue
        final = path.with_name(path.name[1:-len('.staging')]).as_posix()
        if complete or final not in expected or final in actual:
            raise ValueError('unowned activation staging file')
        source = next(Path(item) for item, target in plan['mapping'].items()
                      if Path(target) == root / final)
        if not read_bytes(source).startswith(read_bytes(root / name)):
            raise ValueError('activation staging prefix changed')
        del actual[name]
    if not set(actual).issubset(expected) or not directories.issubset(expected_tree(expected)):
        raise ValueError('foreign file or directory in activation tree')
    if any(proof != expected[name] for name, proof in actual.items()):
        raise ValueError('activation bytes changed')
    if complete and (set(actual) != set(expected) or directories != expected_tree(expected)):
        raise ValueError('activation inventory is incomplete')


def quiet(plan):
    """Fail closed on active records, held locks, and legacy process identities."""
    handles = []
    try:
        for filename in plan['files']:
            path = Path(filename)
            if path.name.endswith('.lock'):
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                handles.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if path.name == 'state.json' and any(part in {'agent', 'agents'} for part in path.parts):
                try:
                    state = json.loads(read_bytes(path))
                except (ValueError, UnicodeError):
                    continue  # Recorded archive-only, never semantically promoted.
                if not isinstance(state, dict):
                    continue
                writer_free(state)
        yield
    finally:
        for fd in handles:
            os.close(fd)
quiet = contextlib.contextmanager(quiet)


def make_plan(roots, home):
    bindings = [paths.resolve(Path(root), create=True, home=home) for root in sorted(set(roots))]
    files, directories = inventory([b['projectRoot'] for b in bindings])
    mapping, archive_only = {}, []
    for binding in bindings:
        source = Path(binding['projectRoot']) / '.agent-factory'
        for filename in files:
            path = Path(filename)
            if not path.is_relative_to(source):
                continue
            relative = path.relative_to(source)
            if relative.parts[0] == 'agent':
                mapping[filename] = str(Path(binding['runtimeRoot']) / 'agents' / Path(*relative.parts[1:]))
    # An inactive malformed session/run stays readable in the immutable archive.
    for filename in list(mapping):
        path = Path(filename)
        if path.name not in {'state.json', 'session.json'}:
            continue
        try:
            value = json.loads(read_bytes(path))
            if not isinstance(value, dict) or value.get('schemaVersion') != '0.1.0':
                raise ValueError('unsupported legacy schema')
            if path.name == 'session.json' and not all(key in value for key in ('agentId', 'role', 'projectRoot')):
                raise ValueError('unbound legacy session')
            if '/runs/' in filename and not all(key in value for key in ('agentId', 'runId', 'requestHash', 'statePath', 'status')):
                raise ValueError('unbound legacy run')
        except (ValueError, UnicodeError):
            prefix = str(path.parent) + '/'
            archive_only.append({'path': str(path.parent), 'reason': 'malformed-or-unsupported-inactive-record'})
            for member in list(mapping):
                if member.startswith(prefix):
                    del mapping[member]
    result = {'schemaVersion': 1, 'kind': 'runtime-migration-plan', 'home': str(paths.home_path(home)),
              'projects': bindings, 'files': files, 'directories': directories,
              'mapping': mapping, 'archiveOnly': archive_only}
    result['planId'] = digest(result)
    return result


def validate(plan, *, historical=False):
    if not isinstance(plan, dict) or set(plan) != KEYS or plan['schemaVersion'] != 1 or plan['kind'] != 'runtime-migration-plan':
        raise ValueError('unsupported migration plan')
    if plan['planId'] != digest({k: v for k, v in plan.items() if k != 'planId'}):
        raise ValueError('migration plan identity mismatch')
    if not plan['projects'] or len(plan['projects']) > 64 or len(plan['files']) > 200000:
        raise ValueError('migration inventory bounds exceeded')
    for binding in plan['projects']:
        if historical:
            expected = paths.document(Path(plan['home']), Path(binding['projectRoot']), binding['projectId'])
            if binding != expected or binding['projectId'] not in paths.registry(Path(plan['home']))['projects']:
                raise ValueError('historical project binding is invalid')
        else:
            paths.bind(binding)
        if binding['home'] != plan['home']:
            raise ValueError('mixed migration homes')
    sources = [Path(b['projectRoot']) / '.agent-factory' for b in plan['projects']]
    for filename, proof in plan['files'].items():
        path = paths.absolute(filename)
        matches = [root for root in sources if path.is_relative_to(root)]
        if len(matches) != 1 or set(proof) != {'size', 'sha256'}:
            raise ValueError('ambiguous or invalid source inventory')
        if filename in plan['mapping']:
            binding = next(b for b in plan['projects'] if Path(b['projectRoot']) / '.agent-factory' == matches[0])
            rel = path.relative_to(matches[0])
            expected = Path(binding['runtimeRoot']) / 'agents' / Path(*rel.parts[1:])
            if rel.parts[0] != 'agent' or str(expected) != plan['mapping'][filename]:
                raise ValueError('operational mapping escapes project')
    if not set(plan['mapping']).issubset(plan['files']):
        raise ValueError('mapping has unknown source')
    for directory in plan['directories']:
        if not any(paths.absolute(directory).is_relative_to(root) for root in sources):
            raise ValueError('directory escapes source')
    return plan


def archive_member(plan, filename):
    binding = next(b for b in plan['projects'] if Path(filename).is_relative_to(Path(b['projectRoot']) / '.agent-factory'))
    return Path(binding['projectId']) / Path(filename).relative_to(Path(binding['projectRoot']) / '.agent-factory')


def area(plan):
    return Path(plan['home']) / 'migrations' / plan['planId']


def unchanged(plan):
    observed, directories = inventory([b['projectRoot'] for b in plan['projects']])
    if observed != plan['files'] or directories != plan['directories']:
        raise ValueError('source inventory changed; create a new plan')


def copy_member(source, target, proof):
    paths.inspect(target, missing=True)
    if target.exists():
        content = read_bytes(target)
    else:
        content = read_bytes(source)
        paths.mkdir(target.parent)
        temporary = target.with_name('.' + target.name + '.staging')
        offset = 0
        if temporary.exists():
            prefix = read_bytes(temporary)
            if not content.startswith(prefix):
                raise ValueError('interrupted staging conflicts')
            offset = len(prefix)
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_APPEND
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, 'ab') as stream:
            stream.write(content[offset:]); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    if len(content) != proof['size'] or hashlib.sha256(content).hexdigest() != proof['sha256']:
        raise ValueError('copy bytes conflict with immutable manifest')


def reject_credentials(plan):
    """Credential authorities are not migration backup inputs."""
    names = {'auth.json', 'credentials.json', 'token.json', 'tokens.json', '.env'}
    fields = {'access_token', 'refresh_token', 'client_secret', 'api_key', 'apiKey', 'private_key'}
    def contains_secret(value):
        if isinstance(value, dict):
            return any((key in fields and bool(item)) or contains_secret(item) for key, item in value.items())
        if isinstance(value, list):
            return any(contains_secret(item) for item in value)
        return False
    for filename in plan['files']:
        path = Path(filename)
        if path.name.lower() in names:
            raise ValueError('credential store must remain with its authority; exclude it through an explicit source decision')
        if path.suffix == '.json':
            try:
                value = json.loads(read_bytes(path))
            except (ValueError, UnicodeError):
                continue
            if contains_secret(value):
                raise ValueError('raw credential fields block archive duplication')


def validate_backup(plan, backup):
    backup = paths.absolute(backup)
    home = Path(plan['home'])
    if backup.is_relative_to(home) or home.is_relative_to(backup) or any(backup.is_relative_to(b['projectRoot']) or Path(b['projectRoot']).is_relative_to(backup) for b in plan['projects']):
        raise ValueError('backup must be independent of home and source projects')
    return backup


def copy(plan, backup):
    backup = validate_backup(plan, backup)
    with quiet(plan):
        unchanged(plan)
        reject_credentials(plan)
        work = area(plan)
        paths.mkdir(work)
        journal = work / 'journal.json'
        if journal.exists() and paths.read(journal).get('backup') != str(backup):
            raise ValueError('retry backup binding changed')
        paths.write(journal, {'planId': plan['planId'], 'phase': 'copying', 'backup': str(backup)})
        paths.write(work / 'plan.json', plan)
        for directory in plan['directories']:
            member = archive_member(plan, directory)
            paths.mkdir(work / 'archive' / member)
            paths.mkdir(backup / plan['planId'] / member)
        for filename, proof in plan['files'].items():
            member = archive_member(plan, filename)
            copy_member(Path(filename), work / 'archive' / member, proof)
            copy_member(Path(filename), backup / plan['planId'] / member, proof)
            if filename in plan['mapping']:
                copy_member(Path(filename), work / 'projection' / member, proof)
        unchanged(plan)
        paths.write(journal, {'planId': plan['planId'], 'phase': 'copied', 'backup': str(backup)})
    return {'kind': 'migration-copy', 'planId': plan['planId'], 'phase': 'copied', 'independentlyVerified': False}


def eligible(plan):
    """Deterministic byte evidence; this is not independent semantic acceptance."""
    unchanged(plan)
    copied_inventory(plan)
    return {'kind': 'migration-eligibility', 'planId': plan['planId'], 'eligible': True, 'independentlyVerified': False}


def copy_binding(plan, backup=None):
    if backup is None:
        backup = copied_inventory(plan)['backup']
    else:
        backup = str(validate_backup(plan, backup))
    return {'planId': plan['planId'], 'home': plan['home'], 'backup': backup,
            'sourceInventoryHash': digest({'files': plan['files'], 'directories': plan['directories']}),
            'projectionHash': digest({destination: plan['files'][source] for source, destination in plan['mapping'].items()})}


def managed_completion(state_path, role):
    rt = runtime_owner()
    state_path = paths.absolute(state_path)
    raw = rt.safe_read_json(state_path)
    bound = paths.bind(raw['runtimeBinding'])
    root = Path(bound['projectRoot'])
    state = rt.find_run(root, raw['agentId'], raw['runId'])
    if state['statePath'] != str(state_path) or state['role'] != role or state['status'] != 'completed' or not state.get('finishedAt') or not state.get('sessionId') or state.get('startDisposition') != 'started':
        raise ValueError('migration gate requires an actually completed managed role run')
    session = rt.load_session(root, state['agentId'])
    if session['sessionId'] != state['sessionId'] or session['role'] != role:
        raise ValueError('completion session/role binding mismatch')
    request = read_bytes(Path(state['requestPath']))
    if hashlib.sha256(request).hexdigest() != state['requestHash']:
        raise ValueError('completion request bytes mismatch')
    capability = None
    if state.get('capabilityBindingPath'):
        capability = rt.safe_read_json(Path(state['capabilityBindingPath']))
    expected = rt.receipt_schema_document(role=role, run_id=state['runId'],
        request_hash=state.get('receiptRequestHash') or state['requestHash'],
        verified_work_run_id=state.get('verifiedWorkRunId'), capability_bindings=capability)
    if rt.safe_read_json(Path(state['receiptSchemaPath'])) != expected:
        raise ValueError('managed role receipt schema mismatch')
    receipt = rt.validate_receipt(root, state, agent_id=state['agentId'], run_id=state['runId'])
    response = rt.safe_read_json(Path(state['responseSchemaPath']))
    if response.get('properties', {}).get('resultPath') != {'type': 'string', 'const': state['resultPath']}:
        raise ValueError('completion response schema mismatch')
    result = read_bytes(Path(state['resultPath']))
    events = read_bytes(Path(state['eventsPath']))
    if len(events) > rt.MAX_EVENTS_BYTES:
        raise ValueError('completion events exceed bound')
    terminal = False
    for line in events.splitlines():
        event = json.loads(line)
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
            try:
                terminal = json.loads(item['text']) == {'status': 'completed', 'resultPath': state['resultPath']}
            except (ValueError, KeyError):
                terminal = False
    if not terminal:
        raise ValueError('managed terminal output is absent or mismatched')
    return state, receipt, json.loads(request), json.loads(result)


def gate(plan, evidence):
    record = paths.read(paths.absolute(evidence))
    if set(record) != {'schemaVersion', 'kind', 'workStatePath', 'verificationStatePath'} or record['schemaVersion'] != 2 or record['kind'] != 'migration-verification':
        raise ValueError('unsupported independent migration gate')
    binding = copy_binding(plan)
    work, work_receipt, work_request, work_result = managed_completion(record['workStatePath'], 'work')
    check, receipt, request, result = managed_completion(record['verificationStatePath'], 'verification')
    if work['agentId'] == check['agentId'] or work['sessionId'] == check['sessionId']:
        raise ValueError('copy and independent Verification must have distinct role sessions')
    if work_request != {'schemaVersion': 1, 'kind': 'migration-copy-request', 'binding': binding} or work_result != {'schemaVersion': 1, 'kind': 'migration-copy-result', 'binding': binding}:
        raise ValueError('copy Work does not bind exact source/projection/backup evidence')
    verification = {'schemaVersion': 1, 'binding': binding, 'workRunId': work['runId'],
                    'workRequestHash': work['requestHash'],
                    'workResultHash': hashlib.sha256(read_bytes(Path(work['resultPath']))).hexdigest()}
    if request != {**verification, 'kind': 'migration-verification-request'} or result != {**verification, 'kind': 'migration-verification-result', 'decision': 'pass'}:
        raise ValueError('independent request/result does not bind copied inventory')
    if receipt['decision'] != 'pass' or receipt['verifiedWorkRunId'] != work['runId'] or receipt['verifiedRequestHash'] != work['requestHash'] or check.get('verifiedWorkRunId') != work['runId'] or work_receipt['requestHash'] != work['requestHash']:
        raise ValueError('independent pass does not bind exact copy Work')
    return record


def activate(plan, evidence):
    gate(plan, evidence)
    with quiet(plan):
        eligible(plan)
        work = area(plan)
        # Preflight every destination before any publication. Never merge existing work.
        for binding in plan['projects']:
            destination = Path(binding['agentsRoot'])
            marker = Path(binding['runtimeRoot']) / 'migration.json'
            expected_marker = {'schemaVersion': 1, 'planId': plan['planId'],
                               'planPath': str(work / 'plan.json')}
            if marker.exists():
                if paths.read(marker) != expected_marker:
                    raise ValueError('migration marker is invalid or belongs to another plan')
                publication_inventory(plan, binding, complete=True)
            elif any(destination.iterdir()):
                pending = Path(binding['runtimeRoot']) / 'migration-pending.json'
                if not pending.exists() or paths.read(pending) != {'planId': plan['planId']}:
                    raise ValueError('destination contains runtime work')
        journal = paths.read(work / 'journal.json')
        for binding in plan['projects']:
            publication_inventory(plan, binding, complete=journal['phase'] == 'activated')
        if journal['phase'] == 'activated':
            return {'kind': 'migration-activation', 'planId': plan['planId'], 'phase': 'activated'}
        paths.write(work / 'journal.json', {**journal, 'phase': 'activating'})
        for binding in plan['projects']:
            destination = Path(binding['agentsRoot'])
            marker = Path(binding['runtimeRoot']) / 'migration.json'
            if marker.exists():
                continue
            projection = work / 'projection' / binding['projectId'] / 'agent'
            paths.write(Path(binding['runtimeRoot']) / 'migration-pending.json', {'planId': plan['planId']})
            paths.mkdir(projection)
            for child in sorted(projection.iterdir()):
                target = destination / child.name
                paths.mkdir(target)
                members = {filename: proof for filename, proof in plan['files'].items()
                           if filename in plan['mapping'] and Path(plan['mapping'][filename]).is_relative_to(target)}
                for filename, proof in members.items():
                    member = archive_member(plan, filename)
                    copy_member(work / 'projection' / member, Path(plan['mapping'][filename]), proof)
            paths.write(marker, {'schemaVersion': 1, 'planId': plan['planId'], 'planPath': str(work / 'plan.json')})
        # Publication may have changed after preflight. Do not publish the
        # activated journal until every project is complete and still closed.
        for binding in plan['projects']:
            marker = Path(binding['runtimeRoot']) / 'migration.json'
            expected_marker = {'schemaVersion': 1, 'planId': plan['planId'],
                               'planPath': str(work / 'plan.json')}
            if paths.read(marker) != expected_marker:
                raise ValueError('migration marker changed during activation')
            publication_inventory(plan, binding, complete=True)
        paths.write(work / 'journal.json', {**journal, 'phase': 'activated'})
    return {'kind': 'migration-activation', 'planId': plan['planId'], 'phase': 'activated'}


def retire(plan, evidence, authority):
    if not authority.strip():
        raise ValueError('exact source-retirement authority reference is required')
    gate(plan, evidence)
    journal_path = area(plan) / 'journal.json'
    journal = copied_inventory(plan)
    if journal['phase'] not in {'activated', 'retiring', 'retired'}:
        raise ValueError('activation must precede retirement')
    if journal['phase'] == 'activated':
        unchanged(plan)
        journal['retirement'] = {}
        for binding in plan['projects']:
            source = Path(binding['projectRoot']) / '.agent-factory'
            files, dirs = source_expected(plan, binding)
            _, _, identities = bounded_tree(source, files, dirs)
            tomb = source.with_name('.agent-factory-retired-' + plan['planId'])
            if tomb.exists() or tomb.is_symlink():
                raise ValueError('unowned retirement tombstone exists')
            journal['retirement'][binding['projectId']] = {'identities': identities, 'renamed': False,
                'deleted': [], 'pending': None, 'complete': False}
        journal.update(phase='retiring', authority=authority)
        paths.write(journal_path, journal)
    if journal.get('authority') != authority or set(journal.get('retirement', {})) != {b['projectId'] for b in plan['projects']}:
        raise ValueError('retirement journal/authority is missing or mismatched')
    # Never recursively remove a source or tombstone. Every unlink/rmdir has a
    # durable intent, exact bytes and inode binding; retries permit only that gap.
    for binding in plan['projects']:
        record = journal['retirement'][binding['projectId']]
        source = Path(binding['projectRoot']) / '.agent-factory'
        tomb = source.with_name('.agent-factory-retired-' + plan['planId'])
        files, dirs = source_expected(plan, binding)
        if record['complete']:
            if source.exists() or tomb.exists() or source.is_symlink() or tomb.is_symlink():
                raise ValueError('retired source reappeared')
            continue
        if source.exists() and (record['renamed'] or tomb.exists()):
            raise ValueError('retirement source reappeared or conflicts')
        current = tomb if tomb.exists() else source
        remaining_files = {k: v for k, v in files.items() if k not in record['deleted']}
        remaining_dirs = dirs - set(record['deleted'])
        pending = record['pending']
        if pending and (current / pending).is_symlink():
            raise ValueError('retirement target was replaced by a link')
        if pending and not (current / pending).exists():
            remaining_files.pop(pending, None); remaining_dirs.discard(pending)
            record['deleted'].append(pending); record['pending'] = None
            paths.write(journal_path, journal)
        if not remaining_dirs:
            if source.exists() or tomb.exists():
                raise ValueError('foreign tree at retired path')
            record['complete'] = True; paths.write(journal_path, journal)
            continue
        bounded_tree(current, remaining_files, remaining_dirs, identities=record['identities'])
        # Acquire surviving legacy locks; use original archived process records
        # as well when the operational state file has already been deleted.
        mapped = dict(plan)
        mapped['files'] = {str(current / name): proof for name, proof in remaining_files.items()}
        with quiet(mapped):
            for name in files:
                if name.endswith('/state.json') and '/runs/' in name:
                    archived = area(plan) / 'archive' / binding['projectId'] / name
                    try:
                        writer_free(json.loads(read_bytes(archived)))
                    except (ValueError, UnicodeError):
                        source_root = Path(binding['projectRoot']) / '.agent-factory'
                        if not any(name.startswith(Path(item['path']).relative_to(source_root).as_posix() + '/')
                                   for item in plan['archiveOnly']
                                   if Path(item['path']).is_relative_to(source_root)):
                            raise
            if current == source:
                os.rename(source, tomb)
                current = tomb
            record['renamed'] = True; paths.write(journal_path, journal)
            order = sorted(remaining_files) + sorted(remaining_dirs, key=lambda n: (len(Path(n).parts), n), reverse=True)
            for name in order:
                bounded_tree(current, remaining_files, remaining_dirs, identities=record['identities'])
                record['pending'] = name; paths.write(journal_path, journal)
                target = current / name
                info = target.lstat()
                if [info.st_dev, info.st_ino] != record['identities'].get(name):
                    raise ValueError('retirement target object was replaced')
                if name in remaining_files:
                    target.unlink(); remaining_files.pop(name)
                else:
                    target.rmdir(); remaining_dirs.remove(name)
                record['deleted'].append(name); record['pending'] = None
                paths.write(journal_path, journal)
            record['complete'] = True; paths.write(journal_path, journal)
    journal['phase'] = 'retired'; paths.write(journal_path, journal)
    return {'kind': 'migration-retirement', 'planId': plan['planId'], 'phase': 'retired'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'plan', 'copy-request', 'copy', 'verify-eligible', 'activate', 'retire'])
    parser.add_argument('--project-root', action='append', default=[])
    parser.add_argument('--runtime-home')
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--backup')
    parser.add_argument('--evidence')
    parser.add_argument('--authority-reference')
    args = parser.parse_args(argv)
    try:
        if args.command == 'inventory':
            files, directories = inventory(args.project_root)
            result = {'files': files, 'directories': directories}
        elif args.command == 'plan':
            if not args.project_root or not args.plan:
                raise ValueError('plan needs explicit roots and output path')
            result = make_plan(args.project_root, args.runtime_home)
            paths.mkdir(args.plan.parent)
            if args.plan.exists() and paths.read(args.plan) != result:
                raise ValueError('existing plan differs')
            paths.write(args.plan, result)
        else:
            plan = validate(paths.read(args.plan))
            with paths.lock(Path(plan['home']) / 'migrations'):
                if args.command == 'copy-request':
                    result = {'schemaVersion': 1, 'kind': 'migration-copy-request',
                              'binding': copy_binding(plan, args.backup)}
                elif args.command == 'copy': result = copy(plan, args.backup)
                elif args.command == 'verify-eligible': result = eligible(plan)
                elif args.command == 'activate': result = activate(plan, args.evidence)
                else: result = retire(plan, args.evidence, args.authority_reference or '')
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'kind': 'error', 'error': {'code': 'migration_refused', 'message': str(error)}}))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
