"""Exercise the local Original and Processed Document catalog and search CLIs."""

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
