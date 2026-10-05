#!/usr/bin/env python3
"""Record, evaluate, publish and retrieve evidence-backed lessons (JSON input)."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from storage import lessons as body_store  # noqa: E402
from storage import paths as runtime_paths  # noqa: E402

import yaml
from catalog_documents import read_lesson  # noqa: E402
from export_documents import check_path  # noqa: E402
from sync_documents import sync  # noqa: E402


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', value):
        raise ValueError('Expected a lowercase hyphenated identifier')
    return value


def required(data, fields):
    for field in fields:
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f'Field {field} must be a nonempty string, not {type(value).__name__}; '
                             f'for example "{field}": "extension"')
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Missing nonempty field: {field}')


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextlib.contextmanager
def locked(root):
    # Outside the document tree; coordinates concurrent managed writers.
    key = hashlib.sha256(str(root).encode()).hexdigest()
    if os.name == 'nt':
        # Per-user %TEMP% is already private through the profile ACL.
        import getpass
        import msvcrt
        owner = ''.join(c if c.isalnum() else '_' for c in getpass.getuser())
        directory = Path(tempfile.gettempdir()) / f'agent-factory-lessons-{owner}'
        directory.mkdir(exist_ok=True)
        if directory.is_symlink():
            raise ValueError('Unsafe lesson lock directory')
        fd = os.open(directory / key, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'w') as stream:
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    directory = Path(tempfile.gettempdir()) / f'agent-factory-lessons-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise ValueError('Unsafe lesson lock directory')
    fd = os.open(directory / key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def safe(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Path escapes project root")
    path = root / relative
    check_path(path, root)
    return path


def superproject(root):
    """Return the workspace whose .gitmodules registers root as a submodule path."""
    for parent in root.parents:
        modules = parent / '.gitmodules'
        if modules.is_file():
            relative = re.escape(root.relative_to(parent).as_posix())
            if re.search(rf'^\s*path\s*=\s*{relative}\s*$', modules.read_text(encoding='utf-8'), re.M):
                return parent
    return None


def check_root(root):
    # A submodule root would split lessons away from the workspace record.
    parent = superproject(root)
    if parent and (parent / 'docs/lessons-learned').is_dir():
        raise ValueError(f'Project root {root} is a submodule of {parent}; '
                         f'use --project-root {parent} so lessons stay in {parent / "docs/lessons-learned"}')


SUPPORTED_FORMATS = ['categorized-markdown-with-runtime-metadata-v2', 'legacy-json-v1', 'legacy-package-v1']


class LessonStorageError(ValueError):
    """A storage contract failure needs repair, not retries with another action."""

    def __init__(self, root, cause):
        super().__init__(f'Lesson storage is incompatible or incomplete at {root}: {cause}. '
                         'Use a matching lessons CLI and document/runtime metadata layout; '
                         'preserve pending inputs and stop subsequent lifecycle calls until repaired.')
        self.root = str(root)

    def diagnostic(self):
        return {'error': str(self), 'code': 'lesson_storage_incompatible', 'retryable': False,
                'documentRoot': self.root, 'toolPath': str(Path(__file__).resolve()),
                'supportedFormats': SUPPORTED_FORMATS,
                'recovery': 'Repair the tool/storage mismatch, run check once, then retry pending inputs.'}


def records(root, documents_root=None):
    docroot = body_store.document_root(root, documents_root)
    try:
        return read_records(root, docroot)
    except (ValueError, FileNotFoundError) as error:
        raise LessonStorageError(docroot, error) from error


def read_records(root, documents_root=None):
    docroot = body_store.document_root(root, documents_root)
    directory = safe(docroot, 'docs/lessons-learned')
    if not directory.exists():
        return []
    output = []
    for package in sorted(directory.iterdir()):
        path = safe(docroot, package.relative_to(docroot))
        if package.name in body_store.FOLDERS.values() and path.is_dir():
            for body in sorted(path.iterdir()):
                safe(docroot, body.relative_to(docroot))
                if not body.is_file() or body.suffix != '.md':
                    raise ValueError(f'Unsupported lesson body: {body}')
                output.append(body_store.read(root, body, docroot))
            continue
        if path.is_dir():
            path = safe(docroot, package.relative_to(docroot) / 'assets/lesson.json')
            if not path.is_file():
                raise ValueError(f'Unrecognized lesson directory {package}; expected categorized '
                                 'Markdown in errors/ or judgment-differences/, or a legacy package '
                                 'containing assets/lesson.json')
        elif path.suffix != '.json':
            raise ValueError(f'Unsupported lesson entry: {path}')
        output.append(read_lesson(path))
    if len({r['id'] for r in output}) != len(output):
        raise ValueError('Duplicate lesson identity; reconcile legacy and Markdown records')
    return output


def save(root, record, documents_root=None):
    docroot = body_store.document_root(root, documents_root)
    name = identifier(record['id'])
    for relative in (f'docs/lessons-learned/{record["category"]}-{name}',
                     f'docs/lessons-learned/{name}.json'):
        if safe(docroot, relative).exists():
            raise ValueError('Legacy lesson must be backed up and migrated before updating')
    meta = body_store.metadata_path(root, name, create=True)
    existing_text = None
    if meta.exists():
        stored = runtime_paths.read(meta)
        path = safe(docroot, stored['documentPath'])
        # A record from another physical worktree must not overwrite its metadata.
        if not path.is_file():
            raise ValueError('Lesson metadata belongs to a missing body; reconcile the document workspace')
        existing = body_store.read(root, path, docroot)
        if existing['category'] != record['category'] or existing['scope'] != record['scope']:
            raise ValueError('Existing lesson identity conflict')
        existing_text = path.read_text(encoding='utf-8')
    else:
        path = body_store.body_path(docroot, record)
        safe(docroot, path.relative_to(docroot))
        if path.exists():
            raise ValueError('Lesson body filename conflict')
    text, stored = body_store.prepare(docroot, record, path, existing_text)
    # Retain a recovery transaction until both canonical files are published.
    journal = meta.with_suffix('.pending.json')
    if journal.exists():
        raise ValueError(f'Interrupted lesson write requires recovery: {journal}')
    runtime_paths.write(journal, {'documentPath': stored['documentPath'],
                                 'previousMetadata': runtime_paths.read(meta) if meta.exists() else None,
                                 'previousBody': existing_text, 'nextBody': text, 'nextMetadata': stored})
    atomic(path, text)
    runtime_paths.write(meta, stored)
    journal.unlink()
    return {'id': name, 'path': path.relative_to(docroot).as_posix(),
            'metadataPath': str(meta), 'status': record['status']}


def find(root, name, documents_root=None):
    identifier(name)
    found = [r for r in records(root, documents_root) if r['id'] == name]
    if len(found) != 1:
        raise ValueError('Lesson identity missing or ambiguous')
    return found[0]


def candidate_hash(candidate):
    return digest({k: v for k, v in candidate.items() if k != 'evaluations'})


def operate(root, action, data, documents_root=None):
    root = Path(root).resolve(strict=True)
    docroot = body_store.document_root(root, documents_root)
    check_root(docroot)
    # Queries must also work for Explorer without creating lock files.
    with (contextlib.nullcontext() if action in ('check', 'retrieve', 'audit') else locked(root)):
        if action == 'check':
            return {'compatible': True, 'count': len(records(root, docroot)),
                    'supportedFormats': SUPPORTED_FORMATS, 'toolPath': str(Path(__file__).resolve())}
        if action not in ('retrieve', 'audit') and data.get('id'):
            body_store.recover(root, identifier(data['id']), docroot, atomic)
        if action == 'recover':
            required(data, ['id'])
            record = find(root, data['id'], docroot)
            return {'id': record['id'], 'status': record['status']}
        if action == 'record':
            required(data, ['category', 'title', 'language', 'occurrenceId', 'source', 'scope'])
            if 'relatedIds' in data:
                if not isinstance(data['relatedIds'], list):
                    raise ValueError('relatedIds must be a list of lesson identifiers')
                for related in data['relatedIds']:
                    identifier(related)
            if data['category'] not in ('error', 'judgment'):
                raise ValueError('Unknown lesson category')
            fields = (['symptom', 'cause', 'solution', 'verification'] if data['category'] == 'error'
                      else ['humanJudgment', 'humanReason', 'aiJudgment', 'aiReason', 'difference', 'reflection', 'outcome'])
            required(data, fields)
            name = identifier(data.get('id') or 'incident-' + digest([data['category'], data['source'], data['scope']])[:20])
            existing = [r for r in records(root, docroot) if r['id'] == name]
            record = existing[0] if existing else {
                'schemaVersion': 1, 'id': name, 'category': data['category'], 'title': data['title'],
                'language': data['language'], 'scope': data['scope'], 'status': 'unresolved',
                'occurrences': [], 'applications': [], 'candidates': [], 'publications': []}
            if record['category'] != data['category'] or record['scope'] != data['scope']:
                raise ValueError('Cannot merge different categories or scopes')
            known = next((e for e in record['occurrences'] if e['occurrenceId'] == data['occurrenceId']), None)
            if known is None:
                record['occurrences'].append({**data, 'recordedAt': stamp()})
            elif data.get('recovered') is True and known.get('recovered') is not True:
                # A later success in the same run marks the stored occurrence; nothing else changes.
                known.update(recovered=True, recoveredBy=data.get('recoveredBy'), recoveredAt=stamp())
            return save(root, record, docroot)
        if action in ('retrieve', 'audit'):
            found = records(root, docroot)
            if action == 'audit':
                expected = data.get('occurrenceIds', [])
                actual = {o['occurrenceId'] for r in found for o in r['occurrences']}
                return {'missing': [x for x in expected if x not in actual]}
            required(data, ['query', 'scope'])
            terms = data['query'].casefold().split()
            def searchable(record):
                text = json.dumps(record, ensure_ascii=False)
                meta = body_store.metadata_path(root, record['id'])
                if meta is not None and meta.exists():
                    path = safe(docroot, runtime_paths.read(meta)['documentPath'])
                    if path.exists():
                        text += '\n' + path.read_text(encoding='utf-8')
                return text.casefold()
            matches = [r for r in found if r['scope'] == data['scope'] and
                       all(t in searchable(r) for t in terms)]
            return {'records': matches, 'count': len(matches),
                    'metrics': {kind: sum(a['outcome'] == kind for r in matches for a in r['applications'])
                                for kind in ('success', 'recurrence', 'correction', 'unused')}}
        required(data, ['id'])
        record = find(root, data['id'], docroot)
        if action == 'resolve':
            fields = (['cause', 'solution', 'verification', 'evidence'] if record['category'] == 'error'
                      else ['outcome', 'reflection', 'evidence'])
            required(data, fields)
            record.setdefault('resolutions', []).append({**data, 'recordedAt': stamp()})
            record['status'] = 'resolved'
        elif action == 'candidate':
            required(data, ['ruleName', 'ruleText', 'trigger', 'exceptions', 'scope', 'authority'])
            identifier(data['ruleName'])
            if not data['ruleName'].startswith('rule-') or data['scope'] != record['scope']:
                raise ValueError('Rule name or scope mismatch')
            candidate = {k: data[k] for k in ['ruleName', 'ruleText', 'trigger', 'exceptions', 'scope', 'authority']}
            candidate['version'] = len(record['candidates']) + 1
            source_records = [record]
            for source_id in data.get('lessonIds', []):
                other = find(root, source_id, docroot)
                if other['scope'] != record['scope']:
                    raise ValueError('Cannot consolidate across scopes')
                if other['id'] != record['id']:
                    source_records.append(other)
            candidate['lessonIds'] = [r['id'] for r in source_records]
            candidate['sources'] = list(dict.fromkeys(o['source'] for r in source_records for o in r['occurrences']))
            candidate['evaluations'] = []
            record['candidates'].append(candidate)
            record['status'] = 'candidate'
        elif action == 'evaluate':
            required(data, ['candidateHash', 'caseId', 'evidence', 'kind'])
            candidate = record['candidates'][-1]
            if data['candidateHash'] != candidate_hash(candidate):
                raise ValueError('Stale candidate evaluation')
            if data['kind'] not in ('original', 'held-out') or type(data.get('passed')) is not bool:
                raise ValueError('Expected original/held-out and boolean passed')
            candidate['evaluations'].append({**data, 'recordedAt': stamp()})
        elif action == 'publish':
            candidate = record['candidates'][-1]
            checks = candidate['evaluations']
            if any(e.get('candidateHash') != candidate_hash(candidate) for e in checks):
                raise ValueError('Stale candidate evaluation after body edit')
            if not checks or not all(e['passed'] for e in checks):
                raise ValueError('Candidate has missing or failing evaluations')
            originals = {e['caseId'] for e in checks if e['kind'] == 'original'}
            held_out = {e['caseId'] for e in checks if e['kind'] == 'held-out'}
            if not originals or not held_out or originals & held_out:
                raise ValueError('Separate original and held-out cases required')
            name = candidate['ruleName']
            path = safe(docroot, f'docs/skills/{name}/SKILL.md')
            previous = record['publications'][-1] if record['publications'] else None
            if path.exists() and (not previous or previous['path'] != str(path.relative_to(docroot)) or
                                  previous.get('currentFileHash', previous['fileHash']) != hashlib.sha256(path.read_bytes()).hexdigest()):
                raise ValueError('Existing rule has unowned or concurrent edits; integrate manually')
            meta = {'name': name, 'description': candidate['trigger'], 'metadata': {
                'document-type': 'specification', 'category': 'rule', 'domain': None,
                'name': name[5:], 'language': record['language'], 'provenance': candidate['sources'],
                'lesson': "../../" + body_store.body_path(docroot, record).relative_to(docroot / "docs").as_posix()}}
            text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n'
            text += candidate['ruleText'].rstrip() + '\n'
            # Rule text is the complete Human-language Specification, not a generated translation.
            if not text.split('---\n', 2)[-1].lstrip().startswith('# '):
                raise ValueError('ruleText must be a complete Specification Markdown document')
            atomic(path, text)
            publication = {'path': str(path.relative_to(docroot)), 'fileHash': hashlib.sha256(text.encode()).hexdigest(),
                           'candidateHash': candidate_hash(candidate), 'version': candidate['version'], 'status': 'sync-pending'}
            record['publications'].append(publication)
            record['status'] = 'sync-pending'
            save(root, record, docroot)
            sync(docroot)
            publication['status'] = 'active'
            record['status'] = 'active'
        elif action == 'sync':
            sync(docroot)
            if record['status'] == 'retire-sync-pending':
                record['status'] = 'retired'
            elif record['status'] == 'sync-pending':
                record['status'] = 'active'
                record['publications'][-1]['status'] = 'active'
        elif action == 'apply':
            required(data, ['runId', 'outcome', 'evidence'])
            if record['status'] != 'active':
                raise ValueError('Only active rules may be applied; record a recurrence with record '
                                 '(new occurrenceId) or a confirmed fix with resolve')
            publication = record['publications'][-1]
            rule_path = safe(docroot, publication['path'])
            if hashlib.sha256(rule_path.read_bytes()).hexdigest() != publication.get('currentFileHash', publication['fileHash']):
                raise ValueError('Applied rule version changed; reconcile before recording outcomes')
            if data['outcome'] not in ('success', 'recurrence', 'correction', 'unused'):
                raise ValueError('Unknown application outcome')
            record['applications'].append({**data, 'version': record['publications'][-1]['version'], 'recordedAt': stamp()})
        elif action == 'retire':
            required(data, ['reason'])
            # Synchronization propagates the disabled instruction, preserving the source history.
            publication = record['publications'][-1]
            path = safe(docroot, publication['path'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != publication.get('currentFileHash', publication['fileHash']):
                raise ValueError('Rule changed concurrently')
            record.setdefault('retirements', []).append({**data, 'recordedAt': stamp()})
            original = path.read_text(encoding='utf-8')
            record['retirements'][-1]['previousRule'] = original
            meta = yaml.safe_load(original.split('---', 2)[1])
            language = record['language'].split('-')[0]
            owner_metadata = meta.get('metadata') if isinstance(meta.get('metadata'), dict) else meta
            owner_metadata['language'] = record['language']
            meta['description'] = data.get('inactiveRuleDescription') or ('비활성 규칙; 적용하지 않습니다.'
                if language == 'ko' else 'Inactive rule; do not apply.' if language == 'en' else 'inactive')
            if language not in ('ko', 'en'):
                required(data, ['inactiveRuleText'])
            note = data.get('inactiveRuleText') or ('# 비활성 규칙\n\n## 1. 상태\n\n- 이 규칙은 적용하지 않습니다.\n'
                if language == 'ko' else '# Inactive rule\n\n## 1. Status\n\n- Do not apply this rule.\n')
            if not note.lstrip().startswith('# '):
                raise ValueError('inactiveRuleText must be a complete Markdown document in the selected language')
            text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n' + note
            atomic(path, text)
            publication['currentFileHash'] = hashlib.sha256(text.encode()).hexdigest()
            record['status'] = 'retire-sync-pending'
            save(root, record, docroot)
            sync(docroot)
            record['status'] = 'retired'
        else:
            raise ValueError('Unknown action')
        result = save(root, record, docroot)
        if record['candidates']:
            result['candidateHash'] = candidate_hash(record['candidates'][-1])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--documents-root', type=Path, help='Physical workspace containing docs; runtime identity stays --project-root')
    parser.add_argument('action', choices=['check', 'record', 'resolve', 'retrieve', 'audit', 'candidate', 'evaluate', 'publish', 'sync', 'apply', 'retire', 'recover'])
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--input', type=Path)
    inputs.add_argument('--input-json', help='Inline JSON payload; avoids temporary input files for read-only queries')
    args = parser.parse_args()
    try:
        data = json.loads(args.input_json if args.input_json is not None else args.input.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Input must be a JSON object')
        print(json.dumps(operate(args.project_root, args.action, data, args.documents_root), ensure_ascii=False))
        return 0
    except LessonStorageError as error:
        print(json.dumps(error.diagnostic(), ensure_ascii=False))
        return 1
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
