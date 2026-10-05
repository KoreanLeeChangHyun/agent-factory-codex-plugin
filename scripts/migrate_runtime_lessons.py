#!/usr/bin/env python3
"""Preview, and only with --apply perform, merging unresolved per-occurrence runtime lessons into signature records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / 'runtime'))
from execution import lessons as capture  # noqa: E402
from storage import paths  # noqa: E402
import lessons  # noqa: E402

SOURCE = re.compile(r'agent:([^/]+)/run:([^/]+)/attempt:(\d+)/event:(.+)')
COMMAND_CODE = re.compile(r'command-exit--?\d+|command-failed')


def runtime_shaped(record):
    """A capture the runtime wrote and nobody diagnosed: unknown cause on every occurrence."""
    return bool(record['occurrences']) and all(
        occurrence.get('cause') == 'unknown' and occurrence.get('solution') == 'unresolved'
        and occurrence.get('symptom') == record['title'] and SOURCE.fullmatch(str(occurrence.get('source', '')))
        for occurrence in record['occurrences'])


class Runs:
    """Read-only view of run states and command events, loaded once per run."""

    def __init__(self, agents_root):
        self.agents_root = Path(agents_root) if agents_root else None
        self.cache = {}

    def load(self, agent, run):
        key = (agent, run)
        if key not in self.cache:
            self.cache[key] = self.read(agent, run)
        return self.cache[key]

    def read(self, agent, run):
        if self.agents_root is None:
            return None
        directory = self.agents_root / agent / 'runs' / run
        try:
            state = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        commands = []
        try:
            with open(state.get('eventsPath') or directory / 'events.jsonl', encoding='utf-8') as stream:
                for line in stream:
                    if '"item.completed"' not in line or '"command_execution"' not in line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(event, dict) and isinstance(event.get('item'), dict):
                        commands.append(event['item'])
        except OSError:
            pass
        return {'state': state, 'commands': commands}


def signature(record, occurrence, runs):
    """The occurrence's signature and recovery marker, or the reason it cannot be determined."""
    agent, run, _attempt, event_key = SOURCE.fullmatch(occurrence['source']).groups()
    loaded = runs.load(agent, run)
    if loaded is None:
        return None, 'run-missing'
    state = loaded['state']
    code = record['title']
    kind, recovered = ('tool' if code == 'tool-error' else 'runtime'), None
    if COMMAND_CODE.fullmatch(code):
        position = next((index for index, item in enumerate(loaded['commands']) if str(item.get('id')) == event_key), None)
        if position is None:
            return None, 'event-missing'
        item = loaded['commands'][position]
        if capture.no_match(item):
            return None, 'no-match'
        kind = capture.command_kind(item.get('command'))
        digest = capture.command_hash(item)
        recovered = next((str(later.get('id')) for later in loaded['commands'][position + 1:]
                          if capture.succeeded(later) and capture.command_hash(later) == digest), None)
    # Sessions without a provider field predate it and ran on Codex, the runtime's default.
    value = {'provider': str(state.get('provider') or 'codex'), 'role': str(state.get('role') or 'unknown'),
             'kind': kind, 'code': code}
    return (value, recovered), None


def plan(root, agents_root):
    directory = lessons.safe(root, 'docs/lessons-learned')
    runs = Runs(agents_root)
    keep = {'resolved': [], 'agent-written': [], 'aggregate': [], 'reviewed': []}
    undetermined, excluded, groups = {}, {}, {}
    for path in sorted(directory.glob('runtime-*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if any('signature' in occurrence for occurrence in record['occurrences']):
            keep['aggregate'].append(record['id'])
        elif record.get('status') != 'unresolved':
            keep['resolved'].append(record['id'])
        elif record['applications'] or record['candidates'] or record.get('resolutions'):
            keep['reviewed'].append(record['id'])
        elif not runtime_shaped(record):
            keep['agent-written'].append(record['id'])
        else:
            merged, reason = [], None
            for occurrence in record['occurrences']:
                found, reason = signature(record, occurrence, runs)
                if found is None:
                    break
                merged.append((occurrence, *found))
            if reason:
                # A grep/rg no-match is not an error under the current capture; the next step decides its removal.
                (excluded if reason == 'no-match' else undetermined).setdefault(reason, []).append(record['id'])
                continue
            for occurrence, value, recovered in merged:
                group = groups.setdefault(capture.signature_id(value), {'signature': value, 'records': [], 'occurrences': []})
                if record['id'] not in group['records']:
                    group['records'].append(record['id'])
                group['occurrences'].append({**occurrence, 'legacyId': record['id'], 'recovered': recovered})
    for record in lessons.records(root):
        if any('signature' in occurrence for occurrence in record['occurrences']) and record['id'] not in keep['aggregate']:
            keep['aggregate'].append(record['id'])
    return {'groups': groups, 'keep': keep, 'excluded': excluded, 'undetermined': undetermined}


def summary(root, result, details):
    """Counts of the plan; call it before apply() so existing signature records are counted as found."""
    groups = result['groups']
    existing = {r['id'] for r in lessons.records(root)} & set(groups)
    output = {
        'mode': 'apply' if details.get('apply') else 'dry-run',
        'merge': {'signatures': len(groups), 'newSignatureRecords': len(set(groups) - existing),
                  'existingSignatureRecords': len(existing),
                  'records': sum(len(g['records']) for g in groups.values()),
                  'occurrences': sum(len(g['occurrences']) for g in groups.values()),
                  'recoveredOccurrences': sum(bool(o['recovered']) for g in groups.values() for o in g['occurrences'])},
        'keep': {reason: len(ids) for reason, ids in result['keep'].items()},
        'excluded': {reason: len(ids) for reason, ids in result['excluded'].items()},
        'undetermined': {reason: len(ids) for reason, ids in result['undetermined'].items()},
    }
    if details.get('list'):
        output['signatures'] = sorted(
            ({'id': name, 'title': capture.signature_title(g['signature']), 'records': len(g['records']),
              'occurrences': len(g['occurrences'])} for name, g in groups.items()),
            key=lambda item: (-item['occurrences'], item['id']))
        output['undeterminedIds'] = result['undetermined']
        output['excludedIds'] = result['excluded']
    return output


def apply(root, result, backup):
    """Write every signature record, back up the merged sources, then remove them, under the lessons lock."""
    directory = lessons.safe(root, 'docs/lessons-learned')
    with lessons.locked(root):
        for name, group in result['groups'].items():
            title = capture.signature_title(group['signature'])
            record = lessons.find(root, name) if name in {r['id'] for r in lessons.records(root)} else {
                'schemaVersion': 1, 'id': name, 'category': 'error', 'title': title, 'language': 'en',
                'scope': 'runtime', 'status': 'unresolved', 'occurrences': [], 'applications': [],
                'candidates': [], 'publications': []}
            known = {occurrence['occurrenceId'] for occurrence in record['occurrences']}
            for occurrence in group['occurrences']:
                if occurrence['occurrenceId'] in known:
                    continue
                moved = {**occurrence, 'id': name, 'title': title, 'symptom': title, 'signature': group['signature']}
                if not moved['recovered']:
                    moved.pop('recovered')
                else:
                    moved.update(recovered=True, recoveredBy=occurrence['recovered'])
                record['occurrences'].append(moved)
            record['occurrences'].sort(key=lambda occurrence: occurrence.get('recordedAt', ''))
            lessons.save(root, record)
        sources = [directory / f'{legacy}.json' for group in result['groups'].values() for legacy in group['records']]
        for source in sources:
            shutil.copy2(source, backup / source.name)
        for source in sources:
            source.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--agents-root', type=Path,
                        help="Run storage to read signatures from; defaults to the project's runtime storage")
    parser.add_argument('--list', action='store_true', help='Also list each signature and the undetermined record IDs')
    parser.add_argument('--apply', action='store_true', help='Write the merge; without it nothing is changed')
    parser.add_argument('--backup', type=Path, help='Existing empty directory that receives merged sources (required with --apply)')
    args = parser.parse_args()
    try:
        root = args.project_root.resolve(strict=True)
        lessons.check_root(root)
        agents_root = args.agents_root
        if agents_root is None:
            agents_root = paths.resolve(root).get('agentsRoot')
        if args.apply:
            if args.backup is None or not args.backup.is_dir() or any(args.backup.iterdir()):
                raise ValueError('--apply requires --backup pointing to an existing empty directory')
            if args.backup.resolve().is_relative_to(root / 'docs/lessons-learned'):
                raise ValueError('--backup must be outside docs/lessons-learned')
        result = plan(root, agents_root)
        output = summary(root, result, {'list': args.list, 'apply': args.apply})
        if args.apply:
            apply(root, result, args.backup.resolve())
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
