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


def refined(root, name="refined-example", body="Refined routing note"):
    package = root / "docs/refined" / f"analyze-{name}"
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "metadata:\n"
        "  document-type: processed\n"
        "  category: analyze\n"
        "  domain: null\n"
        f"  name: {name}\n"
        "  language: en\n"
        "---\n\n"
        f"# Analysis\n\n- {body}\n",
        encoding="utf-8",
    )
    return package


def contract(root, contract_id="WC-001", versions=(1,), attachment=True, base="docs/progress"):
    folder = root / base / contract_id
    folder.mkdir(parents=True)
    for version in versions:
        (folder / f"contract-v{version}.md").write_text(
            "---\nname: sample-contract\nmetadata:\n  document-type: processed\n"
            "  category: other\n  domain: null\n  name: sample-contract\n  language: en\n"
            f"  contract-id: {contract_id}\n  contract-version: {version}\n  status: draft\n---\n\n"
            "# Contract\n\n## 1. Tasks\n\n| Task ID | Task | Completion criteria |\n|---|---|---|\n"
            f"| T1 | Select tasks | Selection works |\n| `T{version + 1}` | Submit tasks | Submission works |\n\n"
            + ("- [File list](files-v1.csv)\n" if attachment else ""),
            encoding="utf-8",
        )
    if attachment:
        (folder / "files-v1.csv").write_text("taskIds,path\nT1,src/select.ts\n", encoding="utf-8")
    (folder / "progress.md").write_text(
        "---\nname: sample-progress\nmetadata:\n  document-type: progress\n  category: status\n"
        "  domain: null\n  name: sample-progress\n  language: ko\n---\n\n# 진행 기록\n\n"
        f"## 1. 기준\n\n- 계약: [v{versions[-1]}](contract-v{versions[-1]}.md#tasks).\n"
        "- T1 검증 대기 중입니다.\n",
        encoding="utf-8",
    )
    return folder


def test_catalog_reads_refined_and_legacy_processed_as_processed(tmp_path):
    refined(tmp_path)
    processed(tmp_path)
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    entries = json.loads(result.stdout)["documents"]
    assert [(e["documentType"], e["location"], e["packagePath"]) for e in entries] == [
        ("processed", "canonical", "docs/refined/analyze-refined-example"),
        ("processed", "legacy", "docs/processed/analyze-analysis-example"),
    ]
    assert entries[0]["metadata"]["category"] == "analyze"
    for document_type in ("refined", "processed"):
        result = run(SEARCH, tmp_path, "--query", "routing", "--type", document_type)
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["count"] == 1
        assert payload["results"][0]["contentPath"] == "docs/refined/analyze-refined-example/SKILL.md"


def test_catalog_rejects_refined_duplicate_of_legacy_processed(tmp_path):
    refined(tmp_path, name="analysis-example")
    processed(tmp_path)
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Duplicate Document identity" in result.stderr
    assert "docs/refined/analyze-analysis-example" in result.stderr
    assert "docs/processed/analyze-analysis-example" in result.stderr


def test_root_progress_catalogs_contract_versions_tasks_and_attachments(tmp_path):
    contract(tmp_path, versions=(1, 2))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    (entry,) = json.loads(result.stdout)["documents"]
    assert entry["documentType"] == "progress"
    assert entry["location"] == "canonical"
    assert entry["contentPath"] == "docs/progress/WC-001/progress.md"
    assert entry["contract"] == {
        "id": "WC-001",
        "latestVersion": 2,
        "taskIds": ["T1", "T3"],
        "versions": [
            {"version": 1, "path": "docs/progress/WC-001/contract-v1.md", "status": "draft", "taskIds": ["T1", "T2"]},
            {"version": 2, "path": "docs/progress/WC-001/contract-v2.md", "status": "draft", "taskIds": ["T1", "T3"]},
        ],
        "attachments": ["docs/progress/WC-001/files-v1.csv"],
    }
    for query in ("검증 대기", "Submission works", "src/select.ts"):
        result = run(SEARCH, tmp_path, "--query", query, "--type", "progress")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["count"] == 1, query


def test_legacy_root_contract_remains_searchable_and_duplicate_is_rejected(tmp_path):
    import shutil
    canonical = contract(tmp_path)
    legacy = tmp_path / "progress" / canonical.name
    legacy.parent.mkdir()
    shutil.move(str(canonical), str(legacy))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    (entry,) = json.loads(result.stdout)["documents"]
    assert entry["location"] == "legacy"
    assert entry["contentPath"] == "progress/WC-001/progress.md"
    result = run(SEARCH, tmp_path, "--query", "Submission works", "--type", "progress")
    assert json.loads(result.stdout)["count"] == 1
    shutil.copytree(legacy, canonical)
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Duplicate Document identity" in result.stderr


def test_root_progress_coexists_with_legacy_progress_and_rejects_duplicates(tmp_path):
    contract(tmp_path)
    legacy = tmp_path / "docs/progress/status-sample"
    legacy.mkdir(parents=True)
    content = legacy / "SKILL.md"
    content.write_text(
        "---\ndocument-type: progress\ncategory: status\ndomain: null\nname: legacy\n---\n\n# Legacy\n",
        encoding="utf-8",
    )
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    assert [(e["packagePath"], e["location"]) for e in json.loads(result.stdout)["documents"]] == [
        ("docs/progress/WC-001", "canonical"), ("docs/progress/status-sample", "legacy")
    ]
    content.write_text(content.read_text().replace("name: legacy", "name: sample-progress"))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Duplicate Document identity" in result.stderr


def test_root_progress_rejects_inconsistent_contract_directories(tmp_path):
    folder = contract(tmp_path)
    (folder / "notes.txt").write_text("unlinked", encoding="utf-8")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "not linked" in result.stderr
    (folder / "notes.txt").unlink()

    (folder / "files-v1.csv").unlink()
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "does not exist" in result.stderr
    (folder / "files-v1.csv").write_text("taskIds,path\n", encoding="utf-8")

    path = folder / "contract-v1.md"
    text = path.read_text()
    path.write_text(text.replace("contract-version: 1", "contract-version: 2"))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "contract-version does not match" in result.stderr
    path.write_text(text.replace("contract-id: WC-001", "contract-id: WC-999"))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "contract-id does not match" in result.stderr
    path.unlink()
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "needs contract-v<N>.md" in result.stderr
    path.write_text(text)

    other = contract(tmp_path, contract_id="WC-002", attachment=False)
    (other / "progress.md").unlink()
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "needs progress.md" in result.stderr


def test_legacy_root_progress_is_listed_and_same_contract_id_conflicts(tmp_path):
    legacy = contract(tmp_path, base="progress")
    result = run(CATALOG, tmp_path)
    assert result.returncode == 0, result.stderr
    (entry,) = json.loads(result.stdout)["documents"]
    assert (entry["packagePath"], entry["location"], entry["contract"]["id"]) == ("progress/WC-001", "legacy", "WC-001")

    contract(tmp_path)
    progress = legacy / "progress.md"
    progress.write_text(progress.read_text().replace("name: sample-progress", "name: renamed-progress"))
    result = run(CATALOG, tmp_path)
    assert result.returncode == 1
    assert "Duplicate contract ID: WC-001" in result.stderr
    assert "docs/progress/WC-001" in result.stderr
    assert "progress/WC-001" in result.stderr


def test_reference_documents_are_searchable_as_one_package(tmp_path):
    package = processed(tmp_path, body='[Detail](references/detail.md)')
    (package / 'references/nested').mkdir(parents=True)
    (package / 'references/detail.md').write_text('# Detail\n\n- [Nested](nested/topic.md)\n')
    (package / 'references/nested/topic.md').write_text('# Topic\n\n- unique-reference-evidence\n')
    result = run(SEARCH, tmp_path, '--query', 'unique-reference-evidence')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['count'] == 1
    entry = data['results'][0]
    assert entry['packagePath'] == str(package.relative_to(tmp_path))
    assert len(entry['contentPaths']) == 3
    assert entry['contentPaths'][0] == entry['contentPath']


def test_reference_symlink_cannot_escape_package(tmp_path):
    package = processed(tmp_path, body='[Detail](references/detail.md)')
    (package / 'references').mkdir()
    outside = tmp_path / 'private.md'
    outside.write_text('private')
    (package / 'references/detail.md').symlink_to(outside)
    result = run(SEARCH, tmp_path, '--query', 'private')
    assert result.returncode != 0
