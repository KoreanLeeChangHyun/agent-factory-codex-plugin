"""Verify incremental projection and the bundled hook's wire contract."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_document_export import package

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/document/scripts/sync_documents.py"


def run(root, hook=False):
    args = ["--hook"] if hook else ["--project-root", str(root)]
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          input=json.dumps({"cwd": str(root)}), text=True, capture_output=True)


def test_source_mirror_removes_destination_only_files(tmp_path):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    target = tmp_path / ".codex/skills/info-example"
    (target / "local.txt").write_text("independent")
    (source / "SKILL.md").write_text("updated")
    (source / "assets/data.bin").unlink()
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (target / "SKILL.md").read_text() == "updated"
    assert not (target / "assets/data.bin").exists()
    assert not (target / "local.txt").exists()
    assert json.loads(run(tmp_path).stdout)["changes"] == []


def test_source_overwrites_independent_destination_edits(tmp_path):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    target = tmp_path / ".codex/skills/info-example"
    (target / "SKILL.md").write_text("human edit")
    (source / "assets/data.bin").write_bytes(b"new data")
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (target / "assets/data.bin").read_bytes() == b"new data"
    assert (target / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()


def test_hook_overwrites_destination(tmp_path):
    package(tmp_path, "skills")
    assert json.loads(run(tmp_path, hook=True).stdout) == {}
    target = tmp_path / ".codex/skills/info-example/SKILL.md"
    target.write_text("edited")
    (tmp_path / "docs/skills/info-example/SKILL.md").write_text("source update")
    result = run(tmp_path, hook=True)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}
    assert target.read_text() == "source update"


def test_removed_package_prunes_only_owned_files(tmp_path):
    import shutil
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    shutil.rmtree(source)
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".codex/skills/info-example").exists()


def test_unrelated_hook_is_noop_and_configuration_runs(tmp_path):
    import os
    config = json.loads((ROOT / "hooks/hooks.json").read_text())
    for event in ("PostToolUse", "Stop"):
        command = config["hooks"][event][0]["hooks"][0]["command"]
        result = subprocess.run(command, shell=True, input=json.dumps({"cwd": str(tmp_path)}),
                                text=True, capture_output=True, env={**os.environ, "PLUGIN_ROOT": str(ROOT)})
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {}
    assert not (tmp_path / ".codex").exists()


def test_bundled_hook_runs_from_relocated_document_skill(tmp_path):
    import os
    import shutil
    installed = tmp_path / "installed plugin"
    shutil.copytree(ROOT / "skills/document", installed / "skills/document",
                    ignore=shutil.ignore_patterns("__pycache__"))
    project = tmp_path / "consumer"
    project.mkdir()
    package(project, "skills")
    config = json.loads((ROOT / "hooks/hooks.json").read_text())
    command = config["hooks"]["Stop"][0]["hooks"][0]["command"]
    result = subprocess.run(command, shell=True, cwd=project,
                            input=json.dumps({"cwd": str(project)}), text=True,
                            capture_output=True, env={**os.environ, "PLUGIN_ROOT": str(installed)})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}
    source = project / "docs/skills/info-example/SKILL.md"
    assert (project / ".codex/skills/info-example/SKILL.md").read_bytes() == source.read_bytes()


@pytest.mark.parametrize("kind", ["source_link", "target_link", "locked"])
def test_unsafe_inputs_preserve_documents(tmp_path, kind):
    source = package(tmp_path, "skills")
    state = tmp_path / ".codex/.document-sync"
    state.mkdir(parents=True)
    if kind == "source_link":
        (source / "link").symlink_to(tmp_path / "missing")
    elif kind == "target_link":
        (tmp_path / ".codex/skills").symlink_to(tmp_path / "missing")
    else:
        (state / "lock").mkdir()
    result = run(tmp_path)
    assert result.returncode == 1
    assert not (tmp_path / ".codex/skills").exists()


def test_mirror_handles_shape_changes_and_preserves_other_codex_content(tmp_path):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    config = tmp_path / ".codex/config.toml"
    config.write_text("preserve")
    target = tmp_path / ".codex/skills/info-example"
    (source / "assets/data.bin").unlink()
    (source / "assets/data.bin").mkdir()
    (source / "assets/data.bin/nested").write_text("new")
    (source / "assets/empty").rmdir()
    (source / "assets/empty").write_text("now a file")
    assert run(tmp_path).returncode == 0
    assert (target / "assets/data.bin/nested").read_text() == "new"
    assert (target / "assets/empty").read_text() == "now a file"
    assert config.read_text() == "preserve"


@pytest.mark.parametrize("hook", [False, True])
def test_sync_projects_only_skills(tmp_path, hook):
    source = package(tmp_path, "skills")
    for kind in ("original", "processed"):
        ignored = package(tmp_path, kind)
        (ignored / "SKILL.md").unlink()
        (ignored / "assets/link").symlink_to(tmp_path / "missing")
    result = run(tmp_path, hook=hook)
    assert result.returncode == 0, result.stderr
    if hook:
        assert json.loads(result.stdout) == {}
    assert (tmp_path / ".codex/skills/info-example/SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
    for kind in ("original", "processed"):
        assert not (tmp_path / ".codex" / kind).exists()
        assert (tmp_path / "docs" / kind / "info-example/assets/data.bin").read_bytes() == bytes(range(256))


@pytest.mark.parametrize("hook", [False, True])
def test_original_and_processed_only_project_is_noop(tmp_path, hook):
    for kind in ("original", "processed"):
        package(tmp_path, kind)
    result = run(tmp_path, hook=hook)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ({} if hook else {"changes": []})
    assert not (tmp_path / ".codex").exists()


def test_sync_preserves_unmapped_codex_roots(tmp_path):
    source = package(tmp_path, "skills")
    for kind in ("original", "processed"):
        package(tmp_path, kind)
        target = tmp_path / ".codex" / kind
        target.mkdir(parents=True)
        (target / "existing.txt").write_text("independent")
    assert run(tmp_path).returncode == 0
    (source / "SKILL.md").write_text("updated")
    assert run(tmp_path).returncode == 0
    for kind in ("original", "processed"):
        target = tmp_path / ".codex" / kind
        assert (target / "existing.txt").read_text() == "independent"
        assert not (target / "info-example").exists()
