"""Exercise persisted lesson lifecycle with real document synchronization."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / 'skills/document/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('lesson_lifecycle', SCRIPTS / 'lessons.py')
lessons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lessons)


def seed(root, category='error'):
    value = dict(id='demo', category=category, title='사례', language='ko', occurrenceId='run-1',
                 source='run:1', scope='project-a', symptom='failure', cause='미확인', solution='미해결',
                 verification='미검증', humanJudgment='간단히', humanReason='미확인', aiJudgment='자세히',
                 aiReason='배경 설명 필요', difference='길이', reflection='선호 차이 추정', outcome='간단히 수정')
    lessons.operate(root, 'record', value)
    return value


def candidate(root):
    return lessons.operate(root, 'candidate', dict(id='demo', ruleName='rule-demo', ruleText='# 규칙\n\n## 1. 실행\n\n- 조건을 확인합니다.',
        trigger='관련 작업에 적용합니다.', exceptions='다른 프로젝트 제외', scope='project-a', authority='human-request:LL-001'))['candidateHash']


def test_full_lifecycle_and_actual_export(tmp_path):
    value = seed(tmp_path)
    lessons.operate(tmp_path, 'record', value)
    assert len(lessons.find(tmp_path, 'demo')['occurrences']) == 1
    value['occurrenceId'] = 'run-2'
    lessons.operate(tmp_path, 'record', value)
    assert len(lessons.find(tmp_path, 'demo')['occurrences']) == 2
    assert lessons.operate(tmp_path, 'audit', {'occurrenceIds': ['run-1', 'run-3']})['missing'] == ['run-3']
    hash_ = candidate(tmp_path)
    with pytest.raises(ValueError, match='missing'):
        lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    for kind in ('original', 'held-out'):
        lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=hash_, kind=kind, caseId=kind, passed=True, evidence='test:' + kind))
    lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    assert (tmp_path / '.codex/skills/rule-demo/SKILL.md').read_bytes() == (tmp_path / 'docs/skills/rule-demo/SKILL.md').read_bytes()
    lessons.operate(tmp_path, 'apply', dict(id='demo', runId='run-4', outcome='recurrence', evidence='test:failed'))
    found = lessons.operate(tmp_path, 'retrieve', {'query': '사례', 'scope': 'project-a'})
    assert found['records'][0]['applications'][0]['version'] == 1
    assert lessons.operate(tmp_path, 'retrieve', {'query': '사례', 'scope': 'project-b'})['count'] == 0
    lessons.operate(tmp_path, 'retire', {'id': 'demo', 'reason': '재발'})
    assert '적용하지 않습니다' in (tmp_path / '.codex/skills/rule-demo/SKILL.md').read_text()
    with pytest.raises(ValueError, match='active'):
        lessons.operate(tmp_path, 'apply', dict(id='demo', runId='r5', outcome='success', evidence='x'))


def test_judgment_and_stale_evaluation(tmp_path):
    seed(tmp_path, 'judgment')
    first = candidate(tmp_path)
    candidate(tmp_path)
    with pytest.raises(ValueError, match='Stale'):
        lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=first, kind='held-out', caseId='case', passed=True, evidence='x'))
    record = lessons.find(tmp_path, 'demo')
    assert record['occurrences'][0]['humanReason'] == '미확인'
    assert record['occurrences'][0]['aiJudgment'] == '자세히'


def test_unowned_rule_and_symlink_preserved(tmp_path):
    seed(tmp_path)
    hash_ = candidate(tmp_path)
    for kind in ('original', 'held-out'):
        lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=hash_, kind=kind, caseId=kind, passed=True, evidence='test'))
    path = tmp_path / 'docs/skills/rule-demo/SKILL.md'
    path.parent.mkdir(parents=True)
    path.write_text('human-owned')
    with pytest.raises(ValueError, match='unowned'):
        lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    assert path.read_text() == 'human-owned'
    with pytest.raises(ValueError):
        lessons.operate(tmp_path, 'record', {**seed(tmp_path), 'id': '../escape'})


def test_failed_evaluation_and_sync_recovery(tmp_path):
    seed(tmp_path)
    hash_ = candidate(tmp_path)
    lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=hash_, kind='original', caseId='same', passed=False, evidence='failure'))
    with pytest.raises(ValueError, match='failing'):
        lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    hash_ = candidate(tmp_path)
    for kind in ('original', 'held-out'):
        lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=hash_, kind=kind, caseId=kind, passed=True, evidence='test'))
    conflict = tmp_path / '.codex/skills/rule-demo'
    conflict.mkdir(parents=True)
    (conflict / 'SKILL.md').write_text('unowned')
    with pytest.raises(ValueError):
        lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    assert lessons.find(tmp_path, 'demo')['status'] == 'sync-pending'
    # Simulate the owner resolving the reported destination collision.
    conflict.rename(tmp_path / 'owner-backup')
    lessons.operate(tmp_path, 'sync', {'id': 'demo'})
    assert lessons.find(tmp_path, 'demo')['status'] == 'active'
    assert (tmp_path / 'owner-backup/SKILL.md').read_text() == 'unowned'


def test_applied_rule_must_match_published_version(tmp_path):
    seed(tmp_path)
    hash_ = candidate(tmp_path)
    for kind in ('original', 'held-out'):
        lessons.operate(tmp_path, 'evaluate', dict(id='demo', candidateHash=hash_, kind=kind, caseId=kind, passed=True, evidence='test'))
    lessons.operate(tmp_path, 'publish', {'id': 'demo'})
    (tmp_path / 'docs/skills/rule-demo/SKILL.md').write_text('independent edit')
    with pytest.raises(ValueError, match='version changed'):
        lessons.operate(tmp_path, 'apply', dict(id='demo', runId='r2', outcome='success', evidence='test'))
    assert lessons.find(tmp_path, 'demo')['applications'] == []


def test_json_only_storage_and_legacy_update_guard(tmp_path):
    seed(tmp_path)
    path = tmp_path / 'docs/lessons-learned/demo.json'
    assert path.is_file()
    assert not list((tmp_path / 'docs/lessons-learned').rglob('SKILL.md'))
    legacy = path.parent / 'error-demo/assets'
    legacy.mkdir(parents=True)
    (legacy / 'lesson.json').write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match='Duplicate'):
        lessons.records(tmp_path)
    path.unlink()
    assert lessons.find(tmp_path, 'demo')['id'] == 'demo'
    with pytest.raises(ValueError, match='migrated'):
        lessons.operate(tmp_path, 'resolve', dict(id='demo', cause='known', solution='fix', verification='pass', evidence='test'))
    assert not path.exists()
