"""Exercise the standalone Document export CLI against isolated projects."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "skills/document/scripts/export_documents.py"


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root), *args],
                          capture_output=True, text=True)


def package(root, kind, name="info-example"):
    path = root / "docs" / kind / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("# 문서\n", encoding="utf-8")
    (path / "assets").mkdir()
    (path / "assets/data.bin").write_bytes(bytes(range(256)))
    (path / "assets/empty").mkdir()
    return path


def test_preview_apply_and_repeat_project_only_skills(tmp_path):
    for kind in ("original", "processed", "skills"):
        package(tmp_path, kind)
    preview = run(tmp_path)
    assert preview.returncode == 0, preview.stderr
    assert len(json.loads(preview.stdout)["packages"]) == 1
    assert not (tmp_path / ".codex").exists()
    applied = run(tmp_path, "--apply")
    assert applied.returncode == 0, applied.stderr
    old = tmp_path / "docs/skills/info-example"
    new = tmp_path / ".codex/skills/info-example"
    assert (new / "SKILL.md").read_bytes() == (old / "SKILL.md").read_bytes()
    assert (new / "assets/data.bin").read_bytes() == bytes(range(256))
    assert (new / "assets/empty").is_dir()
    for kind in ("original", "processed"):
        assert not (tmp_path / ".codex" / kind).exists()
        assert (tmp_path / "docs" / kind / "info-example/assets/data.bin").read_bytes() == bytes(range(256))
    repeat = run(tmp_path, "--apply")
    assert repeat.returncode == 0, repeat.stderr
    assert {p["action"] for p in json.loads(repeat.stdout)["packages"]} == {"unchanged"}


def test_conflict_prevents_all_copies(tmp_path):
    package(tmp_path, "skills", "info-another")
    package(tmp_path, "skills")
    target = tmp_path / ".codex/skills/info-example"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("existing")
    result = run(tmp_path, "--apply")
    assert result.returncode == 1
    assert "conflict" in result.stderr
    assert not (tmp_path / ".codex/skills/info-another").exists()
    assert (target / "SKILL.md").read_text() == "existing"


@pytest.mark.parametrize("location", ["source", "target", "asset"])
def test_symlinks_are_rejected(tmp_path, location):
    source = package(tmp_path, "skills")
    outside = tmp_path / "outside"
    outside.mkdir()
    if location == "source":
        (tmp_path / "docs/skills/linked-package").symlink_to(outside, target_is_directory=True)
    elif location == "target":
        (tmp_path / ".codex").symlink_to(outside, target_is_directory=True)
    else:
        (source / "assets/link").symlink_to(outside / "missing")
    result = run(tmp_path, "--apply")
    assert result.returncode == 1
    assert "Symlinks" in result.stderr
    assert not list(outside.iterdir())


def test_missing_roots_and_invalid_package(tmp_path):
    assert json.loads(run(tmp_path).stdout)["packages"] == []
    source = package(tmp_path, "skills")
    (source / "SKILL.md").unlink()
    result = run(tmp_path, "--apply")
    assert result.returncode == 1
    assert "needs SKILL.md" in result.stderr
    assert not (tmp_path / ".codex").exists()


@pytest.mark.parametrize("apply", [False, True])
def test_ignored_document_roots_need_no_export(tmp_path, apply):
    original = tmp_path / "docs/original"
    original.mkdir(parents=True)
    (original / "unpackaged.txt").write_text("source evidence")
    (tmp_path / "docs/processed").symlink_to(tmp_path / "missing")
    result = run(tmp_path, *(["--apply"] if apply else []))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["packages"] == []
    assert not (tmp_path / ".codex").exists()


def test_export_preserves_unmapped_codex_content(tmp_path):
    package(tmp_path, "skills")
    for kind in ("original", "processed"):
        source = package(tmp_path, kind)
        (source / "SKILL.md").unlink()
        target = tmp_path / ".codex" / kind
        target.mkdir(parents=True)
        (target / "existing.txt").write_text("independent")
    result = run(tmp_path, "--apply")
    assert result.returncode == 0, result.stderr
    for kind in ("original", "processed"):
        assert (tmp_path / ".codex" / kind / "existing.txt").read_text() == "independent"
