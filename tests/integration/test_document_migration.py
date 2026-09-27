"""Exercise contract-listed document moves: backup gating, preservation, conflicts and reruns."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
MIGRATE = ROOT / "skills/document/scripts/migrate_document_paths.py"


def run(project, operations, *args):
    return subprocess.run(
        [sys.executable, str(MIGRATE), "--project-root", str(project), "--operations", str(operations), *args],
        capture_output=True,
        text=True,
    )


def setup(tmp_path):
    project = tmp_path / "project"
    old = project / "docs/processed"
    (old / "analyze-alpha/assets").mkdir(parents=True)
    (old / "analyze-alpha/SKILL.md").write_text(
        "# Alpha\n\n- [Beta](../analyze-beta/SKILL.md#top)\n- [Asset](assets/data.csv)\n", encoding="utf-8"
    )
    (old / "analyze-alpha/assets/data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (old / "analyze-beta").mkdir()
    (old / "analyze-beta/SKILL.md").write_text("# 베타\n\n- 원문 보존\n", encoding="utf-8")
    os.chmod(old / "analyze-beta/SKILL.md", 0o640)
    (project / "docs/unrelated-empty").mkdir()
    operations = tmp_path / "operations.csv"
    with operations.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["taskIds", "operation", "path", "destination"])
        for relative in ("analyze-alpha/SKILL.md", "analyze-alpha/assets/data.csv", "analyze-beta/SKILL.md"):
            writer.writerow(["T3", "move", f"docs/processed/{relative}", f"docs/refined/{relative}"])
    return project, operations, tmp_path / "backup"


def test_apply_requires_backup_then_moves_preserving_content(tmp_path):
    project, operations, backup = setup(tmp_path)
    beta_before = (project / "docs/processed/analyze-beta/SKILL.md").read_bytes()

    preview = run(project, operations)
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["summary"]["pending"] == 3

    refused = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert refused.returncode == 1
    assert "completed backup manifest" in refused.stderr
    assert not (project / "docs/refined").exists()

    backed_up = run(project, operations, "--backup", "--backup-dir", str(backup))
    assert backed_up.returncode == 0, backed_up.stderr
    assert (backup / "files/docs/processed/analyze-beta/SKILL.md").read_bytes() == beta_before

    applied = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["applied"]["moved"] == 3
    refined = project / "docs/refined"
    assert (refined / "analyze-beta/SKILL.md").read_bytes() == beta_before
    assert (refined / "analyze-beta/SKILL.md").stat().st_mode & 0o777 == 0o640
    assert (refined / "analyze-alpha/assets/data.csv").read_text() == "a,b\n1,2\n"
    # Relative links between moved packages still resolve after the move.
    assert "(../analyze-beta/SKILL.md#top)" in (refined / "analyze-alpha/SKILL.md").read_text()
    assert not (project / "docs/processed").exists()
    assert (project / "docs/unrelated-empty").is_dir()
    assert not list(refined.rglob(".migrate-*"))

    rerun = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert rerun.returncode == 0, rerun.stderr
    assert json.loads(rerun.stdout)["applied"] == {"moved": 0, "completedInterrupted": 0, "unchanged": 3}


def test_collision_and_partial_destination_never_overwrite(tmp_path):
    project, operations, backup = setup(tmp_path)
    assert run(project, operations, "--backup", "--backup-dir", str(backup)).returncode == 0
    partial = project / "docs/refined/analyze-beta/SKILL.md"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"# half-writ")
    result = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert result.returncode == 1
    assert "Destination collision" in result.stderr
    assert partial.read_bytes() == b"# half-writ"
    assert (project / "docs/processed/analyze-beta/SKILL.md").is_file()
    assert not (project / "docs/refined/analyze-alpha").exists()


def test_interrupted_move_completes_only_when_both_copies_verify(tmp_path):
    project, operations, backup = setup(tmp_path)
    assert run(project, operations, "--backup", "--backup-dir", str(backup)).returncode == 0
    source = project / "docs/processed/analyze-beta/SKILL.md"
    destination = project / "docs/refined/analyze-beta/SKILL.md"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    result = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["applied"]["completedInterrupted"] == 1
    assert not source.exists()


def test_changed_source_after_backup_is_rejected(tmp_path):
    project, operations, backup = setup(tmp_path)
    assert run(project, operations, "--backup", "--backup-dir", str(backup)).returncode == 0
    (project / "docs/processed/analyze-beta/SKILL.md").write_text("# edited\n", encoding="utf-8")
    result = run(project, operations, "--apply", "--backup-dir", str(backup))
    assert result.returncode == 1
    assert "does not match" in result.stderr or "changed" in result.stderr
    assert not (project / "docs/refined").exists()


def test_symlinks_and_escaping_paths_are_rejected(tmp_path):
    project, operations, backup = setup(tmp_path)
    (project / "docs/refined").symlink_to(tmp_path)
    result = run(project, operations, "--backup", "--backup-dir", str(backup))
    assert result.returncode == 1
    assert "Symlinks are not supported" in result.stderr

    escaping = tmp_path / "escape.csv"
    escaping.write_text("taskIds,operation,path,destination\nT3,move,../outside.md,docs/x.md\n", encoding="utf-8")
    result = run(project, escaping)
    assert result.returncode == 1
    assert "Unsafe source path" in result.stderr
