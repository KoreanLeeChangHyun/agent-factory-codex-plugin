"""Exercise the local Document catalog and search CLIs."""

import json
from pathlib import Path
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "skills/document/scripts/catalog_documents.py"
SEARCH = ROOT / "skills/document/scripts/search_documents.py"


def run(script, root, *args):
    return subprocess.run(
        [sys.executable, str(script), "--project-root", str(root), *args],
        capture_output=True,
        text=True,
    )


def original(root, name="source-example", **metadata):
    package = root / "docs/original" / f"info-{name}"
    package.mkdir(parents=True)
    value = {
        "document-type": "original",
        "category": "info",
        "domain": None,
        "name": name,
        "provenance": "Human supplied source",
        "fidelity": "linked",
        "links": ["https://example.com/source"],
        **metadata,
    }
    (package / "metadata.yaml").write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return package


def processed(root, name="analysis-example", body="Searchable architecture note"):
    package = root / "docs/processed" / f"analyze-{name}"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\n"
        "document-type: processed\n"
        "category: analyze\n"
        "domain: null\n"
        f"name: {name}\n"
        "language: en\n"
        "---\n\n"
        f"# Analysis\n\n- {body}\n",
        encoding="utf-8",
    )
    return package


def test_catalog_lists_original_and_processed_but_not_skills(tmp_path):
    original(tmp_path)
    processed(tmp_path)
    skill = tmp_path / "docs/skills/info-active"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("not cataloged", encoding="utf-8")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    catalog = json.loads(result.stdout)
    assert catalog["kind"] == "document-catalog"
    assert [entry["documentType"] for entry in catalog["documents"]] == [
        "original", "processed"
    ]
    source, analysis = catalog["documents"]
    assert source["contentPath"] is None
    assert source["links"] == ["https://example.com/source"]
    assert analysis["contentPath"].endswith("/SKILL.md")


def test_search_reads_original_metadata_and_processed_markdown(tmp_path):
    original(tmp_path, title="Payment source")
    processed(tmp_path, body="Payment gateway retry analysis")
    source = run(SEARCH, tmp_path, "--query", "example.com", "--type", "original")
    assert source.returncode == 0, source.stderr
    assert json.loads(source.stdout)["results"][0]["documentType"] == "original"
    analysis = run(SEARCH, tmp_path, "--query", "gateway retry", "--type", "processed")
    assert analysis.returncode == 0, analysis.stderr
    payload = json.loads(analysis.stdout)
    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "analysis-example"


def test_original_rejects_embedded_content_and_invalid_links(tmp_path):
    package = original(tmp_path)
    (package / "source.txt").write_text("copied source", encoding="utf-8")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "only metadata.yaml" in result.stderr
    (package / "source.txt").unlink()
    original_metadata = yaml.safe_load((package / "metadata.yaml").read_text())
    original_metadata["links"] = []
    (package / "metadata.yaml").write_text(yaml.safe_dump(original_metadata))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "links must be nonempty" in result.stderr


def test_catalog_rejects_duplicate_identity_and_symlinks(tmp_path):
    original(tmp_path)
    other = original(tmp_path, "other")
    metadata = yaml.safe_load((other / "metadata.yaml").read_text())
    metadata["name"] = "source-example"
    (other / "metadata.yaml").write_text(yaml.safe_dump(metadata))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Duplicate Document identity" in result.stderr

    (other / "metadata.yaml").unlink()
    (other / "metadata.yaml").symlink_to(tmp_path / "missing")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Symlinks are not supported" in result.stderr


def test_search_filters_and_validates_bounds(tmp_path):
    original(tmp_path)
    processed(tmp_path)
    filtered = run(SEARCH, tmp_path, "--query", "example", "--category", "missing")
    assert filtered.returncode == 0, filtered.stderr
    assert json.loads(filtered.stdout)["results"] == []
    invalid = run(SEARCH, tmp_path, "--query", "example", "--limit", "0")
    assert invalid.returncode == 1
    assert "between 1 and 100" in invalid.stderr


def test_progress_catalog_and_search_preserve_legacy_records(tmp_path):
    legacy = processed(tmp_path, body="Migration pending")
    legacy_file = legacy / "SKILL.md"
    legacy_file.write_text(legacy_file.read_text().replace("category: analyze", "category: process"))
    before = legacy_file.read_bytes()
    package = tmp_path / "docs/progress/status-migration"
    package.mkdir(parents=True)
    content = package / "SKILL.md"
    content.write_text(
        "---\ndocument-type: progress\ncategory: status\ndomain: null\n"
        "name: migration\nlanguage: ko\n---\n\n# 진행 상황\n\n"
        "## 1. 현재 상태\n\n- Migration 검증 대기 중입니다.\n",
        encoding="utf-8",
    )
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout)["documents"]
    assert [(e["documentType"], e["category"]) for e in entries] == [
        ("processed", "process"), ("progress", "status")
    ]
    result = run(SEARCH, tmp_path, "--query", "검증 대기", "--type", "progress", "--category", "status")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["results"][0]["contentPath"] == "docs/progress/status-migration/SKILL.md"
    result = run(SEARCH, tmp_path, "--query", "Migration")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["count"] == 2
    assert legacy_file.read_bytes() == before

    content.write_text(content.read_text().replace("document-type: progress", "document-type: processed"))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Expected document-type progress" in result.stderr


def test_lessons_learned_search_reflects_resolution_update(tmp_path):
    processed(tmp_path, body="dependency failure analysis")
    package = tmp_path / "docs/lessons-learned"
    package.mkdir(parents=True)
    record = package / "dependency.json"
    record.write_text(json.dumps({
        "schemaVersion": 1, "id": "dependency", "category": "error", "title": "의존성 오류",
        "language": "ko", "scope": "test", "status": "unresolved",
        "occurrences": [{"cause": "미확인", "solution": "미해결"}],
        "applications": [], "candidates": [], "publications": []
    }, ensure_ascii=False), encoding="utf-8")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    entry = json.loads(result.stdout)["documents"][-1]
    assert entry["documentType"] == "lessons-learned"
    assert entry["contentPath"] == "docs/lessons-learned/dependency.json"
    result = run(SEARCH, tmp_path, "--query", "미해결", "--type", "lessons-learned", "--category", "error")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["count"] == 1
    record.write_text(record.read_text().replace("미해결", "환경 수정 후 검증 통과"))
    result = run(SEARCH, tmp_path, "--query", "검증 통과", "--type", "lessons-learned")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["count"] == 1
    result = run(SEARCH, tmp_path, "--query", "미해결", "--type", "lessons-learned")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["count"] == 0


def test_json_lessons_reject_mismatch_corruption_and_symlinks(tmp_path):
    folder = tmp_path / 'docs/lessons-learned'
    folder.mkdir(parents=True)
    path = folder / 'wrong.json'
    record = dict(schemaVersion=1, id='actual', category='error', title='Failure', language='en',
                  scope='test', status='unresolved', occurrences=[], applications=[], candidates=[], publications=[])
    path.write_text(json.dumps(record))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert 'filename/id mismatch' in result.stderr
    path.write_text('{broken')
    assert run(CATALOG, tmp_path).returncode == 1
    path.unlink()
    external = tmp_path / 'external.json'
    external.write_text(json.dumps(record))
    path.symlink_to(external)
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert 'Symlinks' in result.stderr
