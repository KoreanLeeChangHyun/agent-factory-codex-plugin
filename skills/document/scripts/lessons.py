#!/usr/bin/env python3
"""Record, evaluate, publish and retrieve evidence-backed lessons (JSON input)."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import yaml
from catalog_documents import read_lesson
from export_documents import check_path
from sync_documents import sync


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
        if not isinstance(data.get(field), str) or not data[field].strip():
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


def records(root):
    directory = safe(root, 'docs/lessons-learned')
    if not directory.exists():
        return []
    output = []
    for package in sorted(directory.iterdir()):
        path = safe(root, package.relative_to(root))
        if path.is_dir():
            path = safe(root, package.relative_to(root) / 'assets/lesson.json')
        elif path.suffix != '.json':
            raise ValueError(f'Unsupported lesson entry: {path}')
        output.append(read_lesson(path))
    if len({r['id'] for r in output}) != len(output):
        raise ValueError('Duplicate lesson identity; reconcile legacy and JSON records')
    return output


def save(root, record):
    name = identifier(record['id'])
    legacy = safe(root, f'docs/lessons-learned/{record["category"]}-{name}')
    if legacy.exists():
        raise ValueError('Legacy lesson must be backed up and migrated before updating')
    path = safe(root, f'docs/lessons-learned/{name}.json')
    if path.exists():
        existing = read_lesson(path)
        if existing['id'] != name or existing['category'] != record['category']:
            raise ValueError('Existing lesson identity conflict')
    atomic(path, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return {'id': name, 'path': str(path.relative_to(root)), 'status': record['status']}


def find(root, name):
    identifier(name)
    found = [r for r in records(root) if r['id'] == name]
    if len(found) != 1:
        raise ValueError('Lesson identity missing or ambiguous')
    return found[0]


def candidate_hash(candidate):
    return digest({k: v for k, v in candidate.items() if k != 'evaluations'})


def operate(root, action, data):
    root = Path(root).resolve(strict=True)
    with locked(root):
        if action == 'record':
            required(data, ['category', 'title', 'language', 'occurrenceId', 'source', 'scope'])
            if data['category'] not in ('error', 'judgment'):
                raise ValueError('Unknown lesson category')
            fields = (['symptom', 'cause', 'solution', 'verification'] if data['category'] == 'error'
                      else ['humanJudgment', 'humanReason', 'aiJudgment', 'aiReason', 'difference', 'reflection', 'outcome'])
            required(data, fields)
            name = identifier(data.get('id') or 'incident-' + digest([data['category'], data['source'], data['scope']])[:20])
            existing = [r for r in records(root) if r['id'] == name]
            record = existing[0] if existing else {
                'schemaVersion': 1, 'id': name, 'category': data['category'], 'title': data['title'],
                'language': data['language'], 'scope': data['scope'], 'status': 'unresolved',
                'occurrences': [], 'applications': [], 'candidates': [], 'publications': []}
            if record['category'] != data['category'] or record['scope'] != data['scope']:
                raise ValueError('Cannot merge different categories or scopes')
            if not any(e['occurrenceId'] == data['occurrenceId'] for e in record['occurrences']):
                record['occurrences'].append({**data, 'recordedAt': stamp()})
            return save(root, record)
        if action in ('retrieve', 'audit'):
            found = records(root)
            if action == 'audit':
                expected = data.get('occurrenceIds', [])
                actual = {o['occurrenceId'] for r in found for o in r['occurrences']}
                return {'missing': [x for x in expected if x not in actual]}
            required(data, ['query', 'scope'])
            terms = data['query'].casefold().split()
            matches = [r for r in found if r['scope'] == data['scope'] and
                       all(t in json.dumps(r, ensure_ascii=False).casefold() for t in terms)]
            return {'records': matches, 'count': len(matches),
                    'metrics': {kind: sum(a['outcome'] == kind for r in matches for a in r['applications'])
                                for kind in ('success', 'recurrence', 'correction', 'unused')}}
        required(data, ['id'])
        record = find(root, data['id'])
        if action == 'resolve':
            required(data, ['cause', 'solution', 'verification', 'evidence'])
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
                other = find(root, source_id)
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
            if not checks or not all(e['passed'] for e in checks):
                raise ValueError('Candidate has missing or failing evaluations')
            originals = {e['caseId'] for e in checks if e['kind'] == 'original'}
            held_out = {e['caseId'] for e in checks if e['kind'] == 'held-out'}
            if not originals or not held_out or originals & held_out:
                raise ValueError('Separate original and held-out cases required')
            name = candidate['ruleName']
            path = safe(root, f'docs/skills/{name}/SKILL.md')
            previous = record['publications'][-1] if record['publications'] else None
            if path.exists() and (not previous or previous['path'] != str(path.relative_to(root)) or
                                  previous['fileHash'] != hashlib.sha256(path.read_bytes()).hexdigest()):
                raise ValueError('Existing rule has unowned or concurrent edits; integrate manually')
            meta = {'name': name, 'description': candidate['trigger'], 'metadata': {
                'document-type': 'specification', 'category': 'rule', 'domain': None,
                'name': name[5:], 'language': record['language'], 'provenance': candidate['sources'],
                'lesson': f'../../lessons-learned/{record["id"]}.json'}}
            text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n'
            text += candidate['ruleText'].rstrip() + '\n'
            # Rule text is the complete Human-language Specification, not a generated translation.
            if not text.split('---\n', 2)[-1].lstrip().startswith('# '):
                raise ValueError('ruleText must be a complete Specification Markdown document')
            atomic(path, text)
            publication = {'path': str(path.relative_to(root)), 'fileHash': hashlib.sha256(text.encode()).hexdigest(),
                           'candidateHash': candidate_hash(candidate), 'version': candidate['version'], 'status': 'sync-pending'}
            record['publications'].append(publication)
            record['status'] = 'sync-pending'
            save(root, record)
            sync(root)
            publication['status'] = 'active'
            record['status'] = 'active'
        elif action == 'sync':
            sync(root)
            if record['status'] == 'retire-sync-pending':
                record['status'] = 'retired'
            elif record['status'] == 'sync-pending':
                record['status'] = 'active'
                record['publications'][-1]['status'] = 'active'
        elif action == 'apply':
            required(data, ['runId', 'outcome', 'evidence'])
            if record['status'] != 'active':
                raise ValueError('Only active rules may be applied')
            publication = record['publications'][-1]
            rule_path = safe(root, publication['path'])
            if hashlib.sha256(rule_path.read_bytes()).hexdigest() != publication['fileHash']:
                raise ValueError('Applied rule version changed; reconcile before recording outcomes')
            if data['outcome'] not in ('success', 'recurrence', 'correction', 'unused'):
                raise ValueError('Unknown application outcome')
            record['applications'].append({**data, 'version': record['publications'][-1]['version'], 'recordedAt': stamp()})
        elif action == 'retire':
            required(data, ['reason'])
            # Synchronization propagates the disabled instruction, preserving the source history.
            publication = record['publications'][-1]
            path = safe(root, publication['path'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != publication['fileHash']:
                raise ValueError('Rule changed concurrently')
            record.setdefault('retirements', []).append({**data, 'recordedAt': stamp()})
            original = path.read_text()
            record['retirements'][-1]['previousRule'] = original
            meta = yaml.safe_load(original.split('---', 2)[1])
            meta['description'] = 'Inactive rule; do not apply.'
            note = '# 비활성 규칙\n\n## 1. 상태\n\n- 이 규칙은 적용하지 않습니다.\n' if record['language'] == 'ko' else '# Inactive rule\n\n## 1. Status\n\n- Do not apply this rule.\n'
            text = '---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n\n' + note
            atomic(path, text)
            publication['fileHash'] = hashlib.sha256(text.encode()).hexdigest()
            record['status'] = 'retire-sync-pending'
            save(root, record)
            sync(root)
            record['status'] = 'retired'
        else:
            raise ValueError('Unknown action')
        result = save(root, record)
        if record['candidates']:
            result['candidateHash'] = candidate_hash(record['candidates'][-1])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('action', choices=['record', 'resolve', 'retrieve', 'audit', 'candidate', 'evaluate', 'publish', 'sync', 'apply', 'retire'])
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(operate(args.project_root, args.action, json.loads(args.input.read_text())), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
