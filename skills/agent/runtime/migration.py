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
            if path.name == 'state.json' and '/agent/' in str(path):
                try:
                    state = json.loads(read_bytes(path))
                except (ValueError, UnicodeError):
                    continue  # Recorded archive-only, never semantically promoted.
                if not isinstance(state, dict):
                    continue
                if state.get('status') in ACTIVE:
                    raise ValueError('active legacy run blocks migration')
                for field in ('workerPid', 'codexPid'):
                    pid = state.get(field)
                    if isinstance(pid, int) and pid > 0 and Path(f'/proc/{pid}').exists():
                        raise ValueError('legacy process identity must be reconciled before migration')
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


def copy(plan, backup):
    backup = paths.absolute(backup)
    home = Path(plan['home'])
    if backup.is_relative_to(home) or home.is_relative_to(backup) or any(backup.is_relative_to(b['projectRoot']) or Path(b['projectRoot']).is_relative_to(backup) for b in plan['projects']):
        raise ValueError('backup must be independent of home and source projects')
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
    journal = paths.read(area(plan) / 'journal.json')
    for directory in plan['directories']:
        member = archive_member(plan, directory)
        for target in (area(plan) / 'archive' / member, Path(journal['backup']) / plan['planId'] / member):
            if not stat.S_ISDIR(paths.inspect(target).st_mode):
                raise ValueError('archive directory inventory mismatch')
    for filename, proof in plan['files'].items():
        member = archive_member(plan, filename)
        targets = [area(plan) / 'archive' / member, Path(journal['backup']) / plan['planId'] / member]
        if filename in plan['mapping']:
            targets.append(area(plan) / 'projection' / member)
        for target in targets:
            data = read_bytes(target)
            if len(data) != proof['size'] or hashlib.sha256(data).hexdigest() != proof['sha256']:
                raise ValueError('archive or independent backup mismatch')
    return {'kind': 'migration-eligibility', 'planId': plan['planId'], 'eligible': True, 'independentlyVerified': False}


def gate(plan, evidence):
    record = paths.read(paths.absolute(evidence))
    expected = {'schemaVersion', 'kind', 'planId', 'decision', 'verifierRunId', 'verificationReceiptPath', 'verificationReceiptHash', 'copyWorkRequestPath', 'copyWorkReceiptPath', 'copyWorkReceiptHash'}
    if set(record) != expected or record['schemaVersion'] != 1 or record['kind'] != 'migration-verification' or record['planId'] != plan['planId'] or record['decision'] != 'pass':
        raise ValueError('independent migration verification evidence is missing or mismatched')
    receipt_bytes = read_bytes(paths.absolute(record['verificationReceiptPath']))
    receipt = json.loads(receipt_bytes)
    if hashlib.sha256(receipt_bytes).hexdigest() != record['verificationReceiptHash'] or receipt.get('kind') != 'verification-receipt' or receipt.get('decision') != 'pass' or receipt.get('runId') != record['verifierRunId'] or receipt.get('findings') != []:
        raise ValueError('independent Verification pass receipt mismatch')
    request = read_bytes(paths.absolute(record['copyWorkRequestPath']))
    work_bytes = read_bytes(paths.absolute(record['copyWorkReceiptPath']))
    work = json.loads(work_bytes)
    request_hash = hashlib.sha256(request).hexdigest()
    if (plan['planId'].encode() not in request or hashlib.sha256(work_bytes).hexdigest() != record['copyWorkReceiptHash']
            or work.get('kind') != 'work-receipt' or work.get('outcome') != 'implemented'
            or work.get('requestHash') != request_hash or receipt.get('verifiedRequestHash') != request_hash
            or receipt.get('verifiedWorkRunId') != work.get('runId')
            or work.get('tests') != {'run': False, 'reason': 'work-agent-prohibited'}):
        raise ValueError('Verification does not bind the exact plan-specific copy Work result')
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
            if marker.exists():
                if paths.read(marker).get('planId') != plan['planId']:
                    raise ValueError('another migration is active')
            elif any(destination.iterdir()):
                pending = Path(binding['runtimeRoot']) / 'migration-pending.json'
                if not pending.exists() or paths.read(pending) != {'planId': plan['planId']}:
                    raise ValueError('destination contains runtime work')
        journal = paths.read(work / 'journal.json')
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
        paths.write(work / 'journal.json', {**journal, 'phase': 'activated'})
    return {'kind': 'migration-activation', 'planId': plan['planId'], 'phase': 'activated'}


def retire(plan, evidence, authority):
    if not authority.strip():
        raise ValueError('exact source-retirement authority reference is required')
    gate(plan, evidence)
    journal = paths.read(area(plan) / 'journal.json')
    if journal['phase'] not in {'activated', 'retiring', 'retired'}:
        raise ValueError('activation must precede retirement')
    if journal['phase'] == 'retired':
        return journal
    # Rename each unchanged source atomically before deletion. A retry never guesses
    # whether a changed/new .agent-factory tree is the retired source.
    with quiet(plan) if journal['phase'] == 'activated' else contextlib.nullcontext():
        if journal['phase'] == 'activated':
            eligible(plan)
            paths.write(area(plan) / 'journal.json', {**journal, 'phase': 'retiring', 'authority': authority})
        for binding in plan['projects']:
            source = Path(binding['projectRoot']) / '.agent-factory'
            tomb = source.with_name('.agent-factory-retired-' + plan['planId'])
            if source.exists():
                if tomb.exists():
                    raise ValueError('retirement source reappeared or conflicts')
                os.rename(source, tomb)
            if tomb.exists():
                # All source bytes remain in independent backup and home archive.
                paths.inspect(tomb)
                shutil.rmtree(tomb)
        paths.write(area(plan) / 'journal.json', {**journal, 'phase': 'retired', 'authority': authority})
    return {'kind': 'migration-retirement', 'planId': plan['planId'], 'phase': 'retired'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'plan', 'copy', 'verify-eligible', 'activate', 'retire'])
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
                if args.command == 'copy': result = copy(plan, args.backup)
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
