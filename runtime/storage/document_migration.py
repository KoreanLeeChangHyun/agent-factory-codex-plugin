"""Content-preserving lesson/refined layout migration with resumable backups."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

import yaml

from storage import lessons as bodies, paths

CATEGORIES = ('analysis', 'research', 'interview', 'comparison', 'history')
ALIASES = {'analyze': 'analysis', 'websearch': 'research'}
MANIFEST = 'document-layout.json'
LINK = re.compile(r'(?P<start>\]\()(?P<angle><)?(?P<target>[^\s)>]+)(?P<end>>?)(?P<suffix>\s+"[^"]*"\s*)?\)')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'Unsafe migration path: {relative}')
    target = root / rel
    paths.inspect(target, missing=True)
    return target


def remap_links(data, source, destination, mapping):
    """Change local Markdown link locators, keeping source text and attachments intact."""
    text = data.decode('utf-8')
    def replace(match):
        raw = match['target']
        locator, marker, fragment = raw.partition('#')
        if not locator or ':' in locator or locator.startswith('/'):
            return match[0]
        old = Path(os.path.abspath(source.parent / locator))
        new = mapping.get(old, old)
        if new == old and source.parent == destination.parent:
            return match[0]
        relative = Path(os.path.relpath(new, destination.parent)).as_posix()
        return match['start'] + (match['angle'] or '') + relative + marker + fragment + (match['end'] or '') + (match['suffix'] or '') + ')'
    # Preserve link-shaped examples inside fenced code, not just binary attachments.
    pieces = re.split(r'(?ms)(^```[^\n]*\n.*?^```[^\n]*$)', text)
    text = ''.join(piece if index % 2 else LINK.sub(replace, piece) for index, piece in enumerate(pieces))
    if text.startswith('---\n'):
        front, body = text[4:].split('---\n', 1)
        def lesson_locator(match):
            raw = yaml.safe_load(match[2])
            if not isinstance(raw, str) or raw.startswith('/') or ':' in raw:
                return match[0]
            old = Path(os.path.abspath(source.parent / raw))
            new = mapping.get(old)
            if new is None:
                return match[0]
            return match[1] + 'lesson: ' + json.dumps(Path(os.path.relpath(new, destination.parent)).as_posix())
        front = re.sub(r'(?m)^(\s*)lesson:\s*(.*?)$', lesson_locator, front)
        text = '---\n' + front + '---\n' + body
    return text.encode('utf-8')


def preview(root, documents_root, classify=None, excluded=(), language=None):
    # Import CLI-owned metadata validation lazily; storage does not own catalog policy.
    from catalog_documents import document_metadata, read_frontmatter, read_lesson, validate_metadata
    docs = bodies.document_root(root, documents_root)
    classify = classify or {}
    if language is not None and not language.strip():
        raise ValueError('Language must be a nonempty selected language tag')
    result = {'schemaVersion': 1, 'projectRoot': str(root), 'documentsRoot': str(docs),
              'moves': [], 'outputs': [], 'directories': [], 'sourceDirectories': [], 'conflicts': [],
              'unclassified': [], 'excluded': [], 'language': language, 'languages': {}, 'sourceLanguages': {}}
    sources, output = {}, {}
    lesson_values = []
    mapping = {}
    identities = set()
    def omit(relative):
        return any(relative == item or relative.startswith(item.rstrip('/') + '/') for item in excluded)
    def put(source, destination, content, kind='file'):
        key = str(destination)
        if key in output:
            result['conflicts'].append({'path': key, 'reason': 'duplicate destination'})
        else:
            output[key] = {'source': str(source) if source else None, 'destination': key,
                           'content': content.decode('utf-8') if kind == 'metadata' else content.hex(), 'kind': kind,
                           'sha256': digest(content)}
    directory = safe(docs, 'docs/lessons-learned')
    if directory.exists():
        for entry in sorted(directory.iterdir()):
            paths.inspect(entry)
            if entry.name in bodies.FOLDERS.values() and entry.is_dir():
                for body in sorted(entry.glob('*.md')):
                    paths.inspect(body)
                    try:
                        info, _ = bodies.frontmatter(body)
                    except ValueError:
                        # A colliding unowned destination is reported below; never adopt it.
                        continue
                    name = info.get('id')
                    if name in identities:
                        result['conflicts'].append({'path': str(body), 'reason': 'duplicate existing lesson id'})
                    identities.add(name)
            elif entry.is_dir() and (entry / 'assets/lesson.json').exists():
                legacy = read_lesson(safe(docs, (entry / 'assets/lesson.json').relative_to(docs)))
                if legacy['id'] in identities:
                    result['conflicts'].append({'path': str(entry), 'reason': 'duplicate legacy lesson id'})
                identities.add(legacy['id'])
        for source in sorted(directory.glob('*.json')):
            relative = source.relative_to(docs).as_posix()
            if omit(relative):
                result['excluded'].append(relative)
                continue
            paths.inspect(source)
            record = read_lesson(source)
            if record['id'] in identities:
                result['conflicts'].append({'path': relative, 'reason': 'duplicate lesson id'})
            identities.add(record['id'])
            source_language = record['language']
            if language is not None and language != source_language:
                record.setdefault('sourceLanguage', source_language)
                record['language'] = language
            destination = bodies.body_path(docs, record)
            meta = bodies.metadata_path(root, record['id'])
            if meta is None:
                result['conflicts'].append({'path': relative, 'reason': 'register runtime identity before apply'})
                continue
            # Refuse even identical destinations until a matching backup proves ownership.
            if destination.exists() or meta.exists():
                result['conflicts'].append({'path': str(destination), 'reason': 'existing lesson body or metadata'})
            sources[str(source)] = source.read_bytes()
            mapping[source] = destination
            result['moves'].append({'source': relative, 'destination': destination.relative_to(docs).as_posix(),
                                    'metadataPath': str(meta), 'kind': 'lesson', 'id': record['id']})
            lesson_values.append((source, destination, meta, record))
            actual_language = record['language']
            result['languages'][actual_language] = result['languages'].get(actual_language, 0) + 1
            result['sourceLanguages'][source_language] = result['sourceLanguages'].get(source_language, 0) + 1
    refined = safe(docs, 'docs/refined')
    packages = []
    if refined.exists():
        for source in sorted(refined.iterdir()):
            paths.inspect(source)
            if source.name in CATEGORIES and source.is_dir() and not (source / 'SKILL.md').exists():
                continue
            relative = source.relative_to(docs).as_posix()
            if omit(relative):
                result['excluded'].append(relative)
                continue
            if not source.is_dir() or not (source / 'SKILL.md').is_file():
                result['unclassified'].append({'path': relative, 'reason': 'not a flat refined package'})
                continue
            info = document_metadata(read_frontmatter(source / 'SKILL.md'), source / 'SKILL.md')
            validate_metadata(info, 'processed', source / 'SKILL.md')
            category = classify.get(relative) or ALIASES.get(info.get('category'), info.get('category'))
            if category not in CATEGORIES:
                result['unclassified'].append({'path': relative, 'category': info.get('category'),
                    'reason': 'inspect body and supply an explicit classification'})
                continue
            name = source.name
            prefixes = (*CATEGORIES, *ALIASES, 'other', 'classification')
            for prefix in prefixes:
                if name.startswith(prefix + '-'):
                    name = name[len(prefix) + 1:]
                    break
            if not name or name in CATEGORIES or '/' in name:
                result['conflicts'].append({'path': relative, 'reason': 'ambiguous topic name'})
                continue
            destination = safe(docs, f'docs/refined/{category}/{name}')
            if destination.exists():
                result['conflicts'].append({'path': str(destination), 'reason': 'existing refined destination'})
            files = sorted(source.rglob('*'))
            if any(omit(file.relative_to(docs).as_posix()) for file in files):
                result['excluded'].append(relative)
                continue
            for file in files:
                paths.inspect(file)
                target = destination / file.relative_to(source)
                if file.is_dir():
                    result['directories'].append(str(target))
                    result['sourceDirectories'].append(str(file))
                elif file.is_file():
                    mapping[file] = target
                    sources[str(file)] = file.read_bytes()
                else:
                    raise ValueError(f'Unsupported migration source: {file}')
            packages.append((source, destination, category, info))
            result['moves'].append({'source': relative, 'destination': destination.relative_to(docs).as_posix(), 'kind': 'refined'})
            actual_language = info.get('language') or 'unspecified'
            result['languages'][actual_language] = result['languages'].get(actual_language, 0) + 1
            result['sourceLanguages'][actual_language] = result['sourceLanguages'].get(actual_language, 0) + 1
    for source, _destination, category, info in packages:
        for file in sorted(source.rglob('*')):
            if not file.is_file():
                continue
            target = mapping[file]
            content = sources[str(file)]
            if file.suffix == '.md' and 'assets' not in file.relative_to(source).parts:
                content = remap_links(content, file, target, mapping)
                if file.name == 'SKILL.md' and info.get('category') != category:
                    text = content.decode('utf-8')
                    # Only classification metadata changes; historical body remains verbatim.
                    front, rest = text[4:].split('---\n', 1)
                    front = re.sub(r'(?m)^(\s*)category:.*$', lambda m, category=category: m[1] + 'category: ' + category, front)
                    front += 'migration-original-category: ' + json.dumps(info['category'], ensure_ascii=False) + '\n'
                    content = ('---\n' + front + '---\n' + rest).encode()
            put(file, target, content)
    # Repair incoming Markdown links in project Documents, including reachable references.
    for source in sorted((docs / 'docs').rglob('*.md')) if (docs / 'docs').exists() else ():
        if str(source) in sources or omit(source.relative_to(docs).as_posix()) or 'assets' in source.parts:
            continue
        paths.inspect(source)
        original = source.read_bytes()
        content = remap_links(original, source, source, mapping)
        if content != original:
            sources[str(source)] = original
            put(source, source, content)
    for source, destination, meta, record in lesson_values:
        # Link-only changes do not rewrite historical publication hashes or evaluation evidence.
        if record['publications']:
            publication = record['publications'][-1]
            rule = safe(docs, publication['path'])
            changed = output.get(str(rule))
            if changed is not None and str(rule) in sources:
                expected = publication.get('currentFileHash', publication.get('fileHash'))
                if expected != digest(sources[str(rule)]):
                    result['conflicts'].append({'path': str(rule), 'reason': 'published rule has independent edits'})
                else:
                    publication['currentFileHash'] = changed['sha256']
        text, metadata = bodies.prepare(docs, record, destination)
        put(source, destination, text.encode())
        put(None, meta, (json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode(), 'metadata')
    result['sources'] = {name: {'content': value.hex(), 'sha256': digest(value)} for name, value in sources.items()}
    result['outputs'] = list(output.values())
    return result


def summary(plan):
    return {key: plan[key] for key in ('moves', 'conflicts', 'unclassified', 'excluded', 'language', 'languages', 'sourceLanguages')}


def apply(root, documents_root, backup, classify=None, excluded=(), language=None):
    """Resume only manifest-owned outputs; never accept independently edited targets."""
    import lessons as cli
    docs = bodies.document_root(root, documents_root)
    backup = Path(backup).resolve()
    paths.inspect(backup, missing=True)
    binding = paths.resolve(root, create=True)
    runtime_root = Path(binding['runtimeRoot'])
    if backup.is_relative_to(docs):
        raise ValueError('Backup must be outside the document workspace')
    if backup.is_relative_to(runtime_root):
        relative = backup.relative_to(runtime_root).parts
        if len(relative) < 5 or relative[0] != 'agents' or relative[2] != 'runs' or not runtime_root.joinpath(*relative[:4]).is_dir():
            raise ValueError('Runtime backups must be inside an existing run storage directory')
    manifest = backup / MANIFEST
    with cli.locked(root):
        if manifest.exists():
            plan = json.loads(manifest.read_text(encoding='utf-8'))
            if plan.get('projectRoot') != str(root) or plan.get('documentsRoot') != str(docs):
                raise ValueError('Backup identity/workspace mismatch')
            if language is not None and plan.get('language') != language:
                raise ValueError('Backup language differs from the selected language')
        else:
            if backup.exists() and any(backup.iterdir()):
                raise ValueError('Backup directory must be empty or contain a matching migration manifest')
            plan = preview(root, docs, classify, excluded, language)
            if plan['conflicts'] or plan['unclassified']:
                raise ValueError('Resolve migration conflicts and unclassified packages before apply')
            backup.mkdir(parents=True, exist_ok=True)
            cli.atomic(manifest, json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
        for name in plan['sources']:
            if not Path(name).is_relative_to(docs / 'docs'):
                raise ValueError('Backup source escapes document workspace')
        expected_metadata = {str(bodies.metadata_path(root, move['id'])) for move in plan['moves'] if move['kind'] == 'lesson'}
        for item in plan['outputs']:
            target = Path(item['destination'])
            if item['kind'] == 'metadata':
                if str(target) not in expected_metadata:
                    raise ValueError('Backup metadata escapes runtime identity')
            elif not target.is_relative_to(docs / 'docs'):
                raise ValueError('Backup output escapes document workspace')
        for directory in plan['directories']:
            if not Path(directory).is_relative_to(docs / 'docs/refined'):
                raise ValueError('Backup directory escapes refined workspace')
        # The backup contains exact source bytes, target bytes and their hashes.
        for name, proof in plan['sources'].items():
            source = Path(name)
            if digest(bytes.fromhex(proof['content'])) != proof['sha256']:
                raise ValueError('Backup source checksum mismatch')
            paths.inspect(source, missing=True)
            if source.exists() and digest(source.read_bytes()) != proof['sha256']:
                own = next((item for item in plan['outputs'] if item['destination'] == name), None)
                if own is None or digest(source.read_bytes()) != own['sha256']:
                    raise ValueError(f'Source changed after backup: {source}')
        for item in plan['outputs']:
            target = Path(item['destination'])
            paths.inspect(target, missing=True)
            content = item['content'].encode() if item['kind'] == 'metadata' else bytes.fromhex(item['content'])
            if digest(content) != item['sha256']:
                raise ValueError('Backup output checksum mismatch')
            if target.exists() and digest(target.read_bytes()) != item['sha256']:
                original = plan['sources'].get(str(target))
                if original is None or digest(target.read_bytes()) != original['sha256']:
                    raise ValueError(f'Destination changed or collides: {target}')
        for directory in plan['directories']:
            paths.inspect(Path(directory), missing=True)
            Path(directory).mkdir(parents=True, exist_ok=True)
        for item in plan['outputs']:
            target = Path(item['destination'])
            if target.exists() and digest(target.read_bytes()) == item['sha256']:
                continue
            if item['kind'] == 'metadata':
                paths.mkdir(target.parent)
                paths.write(target, json.loads(item['content']))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                content = bytes.fromhex(item['content'])
                # atomic() is a text writer; binary attachments need the same replace discipline.
                import tempfile
                descriptor, name = tempfile.mkstemp(dir=target.parent)
                try:
                    with os.fdopen(descriptor, 'wb') as stream:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(name, target)
                finally:
                    if os.path.exists(name):
                        os.unlink(name)
        for item in plan['outputs']:
            if digest(Path(item['destination']).read_bytes()) != item['sha256']:
                raise ValueError('Output verification failed; source retained')
        for move in plan['moves']:
            if move['kind'] == 'lesson':
                record = bodies.read(root, safe(docs, move['destination']), docs)
                original = json.loads(bytes.fromhex(plan['sources'][str(safe(docs, move['source']))]['content']))
                historical = json.loads(json.dumps(record))
                if historical['publications'] and original['publications']:
                    if 'currentFileHash' not in original['publications'][-1]:
                        historical['publications'][-1].pop('currentFileHash', None)
                    else:
                        historical['publications'][-1]['currentFileHash'] = original['publications'][-1]['currentFileHash']
                if plan.get('language') is not None:
                    historical['language'] = original['language']
                    if 'sourceLanguage' not in original:
                        historical.pop('sourceLanguage', None)
                if historical != original:
                    raise ValueError('Lesson round-trip mismatch; source retained')
            elif move['kind'] == 'refined':
                from catalog_documents import catalog_entry
                catalog_entry(docs, safe(docs, move['destination']), 'processed')
                source = safe(docs, move['source'])
                expected = set(plan['sources']) | set(plan.get('sourceDirectories', []))
                if source.exists() and any(str(member) not in expected for member in source.rglob('*')):
                    raise ValueError('Source package gained unbacked content; source retained')
        # Recheck after all writes, before retiring any source. Editors do not take our lock.
        for name, proof in plan['sources'].items():
            source = Path(name)
            if source.exists() and name not in {item['destination'] for item in plan['outputs']}:
                if digest(source.read_bytes()) != proof['sha256']:
                    raise ValueError('Source changed during migration; source retained')
        outputs = {item['destination'] for item in plan['outputs']}
        for name in plan['sources']:
            if name not in outputs:
                Path(name).unlink(missing_ok=True)
        for move in plan['moves']:
            if move['kind'] == 'refined':
                source = safe(docs, move['source'])
                if source.exists():
                    for directory in sorted(source.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                        if directory.is_dir():
                            directory.rmdir()
                    source.rmdir()
        return {'mode': 'apply', 'backup': str(manifest), **summary(plan)}
