"""Markdown lesson bodies and runtime-only machine metadata.

Text references are structural locators, never a second editable prose source.
The lifecycle receives a joined record so its historical hashes remain stable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unicodedata

import yaml

from storage import paths

FOLDERS = {'error': 'errors', 'judgment': 'judgment-differences'}
MACHINE = frozenset(('id', 'category', 'title', 'language', 'sourceLanguage', 'scope', 'status',
    'occurrenceId', 'source', 'sources', 'lessonIds', 'relatedIds', 'legacyId', 'currentFileHash', 'runId', 'agentId',
    'recordedAt', 'recoveredAt', 'recoveredBy', 'ruleName', 'authority', 'caseId',
    'candidateHash', 'fileHash', 'path', 'provider', 'role', 'kind', 'code', 'documentPath'))
BLOCK = re.compile(r'<!-- af-text:([a-f0-9]{24}) -->\n(.*?)\n<!-- /af-text:\1 -->', re.S)
LABELS_KO = {'symptom': '현상·근거', 'cause': '원인', 'solution': '해결',
    'verification': '점검', 'humanJudgment': '사용자님의 판단', 'humanReason': '사용자님의 근거',
    'aiJudgment': 'AI의 판단', 'aiReason': 'AI의 근거', 'difference': '전제·판단 차이',
    'reflection': '성찰', 'outcome': '결정·결과', 'evidence': '근거',
    'ruleText': '규칙 본문', 'trigger': '적용 범위·조건', 'exceptions': '예외',
    'reason': '이유·후속 조치', 'previousRule': '이전 규칙',
    'futureApplication': '앞으로의 적용 범위', 'followUp': '후속 조치', 'context': '상황'}
STATE = re.compile(r'<!-- af-state -->.*?<!-- /af-state -->', re.S)


def state_projection(record):
    """Readable, validated machine-state projection; it is never an editable peer."""
    ko = record['language'].split('-')[0] == 'ko'
    rows = []
    def walk(value, pointer=''):
        if isinstance(value, dict):
            fields = []
            for key, item in sorted(value.items()):
                if key in MACHINE or key in ('version', 'passed', 'recovered', 'outcome'):
                    if isinstance(item, (str, bool, int)) and (key != 'outcome' or item in ('success', 'recurrence', 'correction', 'unused')):
                        fields.append(f'{key}: {item}')
                    elif isinstance(item, list) and all(isinstance(member, str) for member in item):
                        fields.append(f'{key}: ' + ', '.join(item))
            if pointer and fields:
                escaped = '; '.join(fields).replace('|', '\\|').replace('\n', '<br>')
                rows.append(f'| `{pointer}` | {escaped} |')
            for key, item in sorted(value.items()):
                walk(item, pointer + '/' + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, pointer + '/' + str(index))
    walk(record)
    language = record['language'].split('-')[0]
    heading = ('실행 연결·이력 상태' if ko else 'Execution links and history state'
               if language == 'en' else '`state`')
    return '<!-- af-state -->\n### 1.1. ' + heading + '\n\n| Path | State |\n|---|---|\n' + '\n'.join(rows) + '\n<!-- /af-state -->'


def document_root(root, documents_root=None):
    """Physical workspace root containing docs; never used as runtime identity."""
    return Path(documents_root or root).resolve(strict=True)


def metadata_path(root, name, *, create=False):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', name):
        raise ValueError('Invalid lesson id')
    binding = paths.resolve(root, create=create)
    if not binding['registered']:
        return None
    directory = Path(binding['runtimeRoot']) / 'lessons-learned'
    paths.inspect(directory, missing=True)
    if create:
        paths.mkdir(directory)
    return directory / (name + '.json')


def body_path(root, record):
    folder = FOLDERS[record['category']]
    title = unicodedata.normalize('NFKC', record['title']).casefold()
    slug = re.sub(r'[^\w-]+', '-', title, flags=re.UNICODE).strip('-_')[:70] or record['id']
    while len(slug.encode('utf-8')) > 120:
        slug = slug[:-1]
    return Path(root) / 'docs/lessons-learned' / folder / (slug + '--' + record['id'] + '.md')


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    parts = text.split('---\n', 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError(f'Lesson needs front matter: {path}')
    value = yaml.safe_load(parts[1])
    if not isinstance(value, dict) or value.get('document-type') != 'lessons-learned':
        raise ValueError(f'Invalid lesson front matter: {path}')
    return value, parts[2]


def read(root, path, documents_root=None):
    docroot = document_root(root, documents_root)
    paths.inspect(path)
    info, body = frontmatter(path)
    meta = metadata_path(root, info.get('id'))
    if meta is None or not meta.is_file():
        raise ValueError(f'Missing runtime lesson metadata: {path}')
    stored = paths.read(meta)
    if not isinstance(stored, dict) or stored.get('schemaVersion') != 2:
        raise ValueError(f'Unsupported runtime lesson metadata: {path}')
    for field in ('id', 'category', 'title', 'language', 'scope', 'status'):
        if not isinstance(stored.get(field), str) or not stored[field].strip():
            raise ValueError(f'Missing lesson field {field}: {path}')
    if stored['category'] not in FOLDERS or path.parent != docroot / 'docs/lessons-learned' / FOLDERS[stored['category']]:
        raise ValueError(f'Lesson category/path mismatch: {path}')
    if stored.get('bodyFormat') not in (None, 'quoted-markdown') or stored.get('stateProjectionVersion') not in (None, 1):
        raise ValueError(f'Unsupported lesson body format: {path}')
    if meta.with_suffix('.pending.json').exists():
        raise ValueError(f'Interrupted lesson write requires recovery: {meta}')
    if stored.get('schemaVersion') != 2 or stored.get('documentPath') != path.relative_to(docroot).as_posix():
        raise ValueError(f'Lesson document/metadata path mismatch: {path}')
    for key in ('id', 'category', 'language', 'scope', 'status', 'title'):
        if info.get(key) != stored.get(key):
            raise ValueError(f'Lesson identity/state mismatch ({key}): {path}')
    if info.get('source-language') != stored.get('sourceLanguage'):
        raise ValueError(f'Lesson source-language mismatch: {path}')
    texts = {}
    for match in BLOCK.finditer(body):
        if match[1] in texts:
            raise ValueError(f'Duplicate lesson text anchor: {path}')
        lines = match[2].split('\n')
        if stored.get('bodyFormat') == 'quoted-markdown' and any(not line.startswith('> ') for line in lines):
            raise ValueError(f'Lesson text must stay in its quoted field block: {path}')
        texts[match[1]] = ('\n'.join(line[2:] for line in lines)
                           if stored.get('bodyFormat') == 'quoted-markdown' else match[2])
    def join(value):
        if isinstance(value, dict):
            if set(value) == {'textRef'} and isinstance(value['textRef'], str):
                if value['textRef'] not in texts:
                    raise ValueError(f'Missing lesson text anchor: {path}')
                return texts[value['textRef']]
            return {key: join(item) for key, item in value.items()}
        if isinstance(value, list):
            return [join(item) for item in value]
        return value
    record = join(stored)
    record.pop('documentPath')
    record.pop('bodyFormat', None)
    projection = record.pop('stateProjectionVersion', None)
    record['schemaVersion'] = 1
    if projection == 1:
        displayed = STATE.search(body)
        if displayed is None or displayed[0] != state_projection(record):
            raise ValueError(f'Lesson state projection edited; use the lifecycle to change state: {path}')
    for field in ('occurrences', 'applications', 'candidates', 'publications'):
        if not isinstance(record.get(field), list) or any(not isinstance(value, dict) for value in record[field]):
            raise ValueError(f'Invalid lesson history field {field}: {path}')
    return record


def recover(root, name, documents_root, atomic):
    """Finish a recorded write only while both files still match its old/new states."""
    meta = metadata_path(root, name)
    if meta is None:
        return
    journal = meta.with_suffix('.pending.json')
    if not journal.exists():
        return
    transaction = paths.read(journal)
    rel = Path(transaction['documentPath'])
    if rel.is_absolute() or '..' in rel.parts or rel.parts[:2] != ('docs', 'lessons-learned'):
        raise ValueError('Unsafe lesson recovery path')
    body = document_root(root, documents_root) / rel
    paths.inspect(body, missing=True)
    next_meta = transaction['nextMetadata']
    if next_meta['id'] != name or next_meta['documentPath'] != rel.as_posix():
        raise ValueError('Lesson recovery identity mismatch')
    actual_body = body.read_text(encoding='utf-8') if body.exists() else None
    actual_meta = paths.read(meta) if meta.exists() else None
    if actual_body not in (transaction['previousBody'], transaction['nextBody']):
        raise ValueError('Lesson body edited during interrupted write; reconcile manually')
    if actual_meta not in (transaction['previousMetadata'], next_meta):
        raise ValueError('Lesson metadata edited during interrupted write; reconcile manually')
    atomic(body, transaction['nextBody'])
    paths.write(meta, next_meta)
    journal.unlink()


def prepare(root, record, path, existing_text=None):
    """Return exact body and metadata bytes, retaining independent Markdown edits."""
    texts = {}
    def quoted(value):
        return '\n'.join('> ' + line for line in value.split('\n'))
    def split(value, pointer='', field=''):
        if isinstance(value, dict):
            return {key: split(item, pointer + '/' + key.replace('~', '~0').replace('/', '~1'), key) for key, item in value.items()}
        if isinstance(value, list):
            return [split(item, pointer + '/' + str(index), field) for index, item in enumerate(value)]
        application_outcome = pointer.startswith('/applications/') and field == 'outcome'
        if isinstance(value, str) and field not in MACHINE and not application_outcome:
            anchor = hashlib.sha256(pointer.encode()).hexdigest()[:24]
            if '<!-- af-text:' in value or '<!-- /af-text:' in value:
                raise ValueError('Reserved lesson anchor in text')
            texts[anchor] = (pointer, field, value)
            return {'textRef': anchor}
        return value
    stored = split(record)
    stored.update(schemaVersion=2, documentPath=path.relative_to(root).as_posix(),
                  bodyFormat='quoted-markdown', stateProjectionVersion=1)
    info = {'document-type': 'lessons-learned', **{key: record[key] for key in
            ('id', 'category', 'title', 'language', 'scope', 'status')}}
    if 'sourceLanguage' in record:
        info['source-language'] = record['sourceLanguage']
    header = '---\n' + yaml.safe_dump(info, allow_unicode=True, sort_keys=False) + '---\n'
    language = record['language'].split('-')[0]
    ko = language == 'ko'
    if existing_text is None:
        body = '\n# ' + record['title'] + '\n\n## 1. ' + ('기록·현재 상태' if ko else 'Record and current state' if language == 'en' else '`record`') + '\n\n'
        body += f'- ID: `{record["id"]}`\n- ' + ('상태' if ko else 'Status' if language == 'en' else 'status') + f': `{record["status"]}`\n'
        body += f'- Scope: `{record["scope"]}`\n'
    else:
        body = existing_text.split('---\n', 2)[2]
        body = re.sub(r'(?m)^- (상태|Status|status): `[^`]+`$',
                      lambda m: f'- {m[1]}: `{record["status"]}`', body)
    state = state_projection(record)
    if STATE.search(body):
        body = STATE.sub(lambda _: state, body)
    else:
        body += '\n' + state + '\n'
    seen = set()
    def replace(match):
        key = match[1]
        if key not in texts or key in seen:
            raise ValueError('Unexpected or duplicate lesson text anchor')
        seen.add(key)
        return f'<!-- af-text:{key} -->\n{quoted(texts[key][2])}\n<!-- /af-text:{key} -->'
    body = BLOCK.sub(replace, body)
    for anchor, (pointer, field, value) in texts.items():
        if anchor in seen:
            continue
        label = LABELS_KO.get(field, field) if ko else field if language == 'en' else f'`{field}`'
        body += f'\n### 1.{len(seen) + 2}. {label} ({pointer})\n\n'
        # Display actual event context with its body; these are machine-derived locators.
        parts = pointer.strip('/').split('/')
        if len(parts) >= 3 and parts[0] in ('occurrences', 'resolutions', 'applications', 'candidates', 'retirements'):
            event = record[parts[0]][int(parts[1])]
            context = [f'{key}: `{event[key]}`' for key in ('occurrenceId', 'recordedAt', 'source', 'runId', 'authority') if key in event]
            if context:
                body += '- ' + '; '.join(context) + '\n\n'
        body += f'<!-- af-text:{anchor} -->\n{quoted(value)}\n<!-- /af-text:{anchor} -->\n'
        seen.add(anchor)
    return header + body, stored
