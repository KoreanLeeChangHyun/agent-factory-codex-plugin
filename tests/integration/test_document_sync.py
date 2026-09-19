"""Ownership, conflict, interruption and explicit CLI contracts for document sync."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from test_document_export import package

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/document/scripts/sync_documents.py"


def run(root):
    return subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(root)],
                          text=True, capture_output=True)


def manifest(root):
    return root / ".codex/.document-sync/manifest.json"


def test_managed_updates_and_source_file_deletion(tmp_path):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    target = tmp_path / ".codex/skills/info-example"
    (source / "SKILL.md").write_text("updated")
    (source / "assets/data.bin").unlink()
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (target / "SKILL.md").read_text() == "updated"
    assert not (target / "assets/data.bin").exists()
    assert json.loads(run(tmp_path).stdout)["changes"] == []


@pytest.mark.parametrize("change", ["edit", "addition", "deletion", "shape", "empty_directory"])
@pytest.mark.parametrize("remove_source", [False, True])
def test_independent_changes_block_all_mutations(tmp_path, change, remove_source):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    target = tmp_path / ".codex/skills/info-example"
    state_before = manifest(tmp_path).read_bytes()
    file = target / "SKILL.md"
    if change == "edit":
        file.write_text("human edit")
    elif change == "addition":
        (target / "local.txt").write_text("human file")
    elif change == "empty_directory":
        (target / "local-dir").mkdir()
    elif change == "deletion":
        file.unlink()
    else:
        file.unlink()
        file.mkdir()
    if remove_source:
        shutil.rmtree(source)
    else:
        (source / "assets/data.bin").write_bytes(b"source update")
    other = tmp_path / "docs/skills/info-other"
    other.mkdir()
    (other / "SKILL.md").write_text("new package")
    result = run(tmp_path)
    assert result.returncode == 1
    assert "Independent destination change" in result.stderr
    assert manifest(tmp_path).read_bytes() == state_before
    assert not (tmp_path / ".codex/skills/info-other").exists()
    assert (target / "assets/data.bin").read_bytes() == bytes(range(256))
    if change == "edit":
        assert file.read_text() == "human edit"
    elif change == "addition":
        assert (target / "local.txt").read_text() == "human file"
    elif change == "empty_directory":
        assert (target / "local-dir").is_dir()
    elif change == "deletion":
        assert not file.exists()
    else:
        assert file.is_dir()


@pytest.mark.parametrize("identical", [False, True])
def test_legacy_collision_is_never_adopted(tmp_path, identical):
    source = package(tmp_path, "skills")
    target = tmp_path / ".codex/skills/info-example"
    shutil.copytree(source, target)
    if not identical:
        (target / "SKILL.md").write_text("legacy")
    before = (target / "SKILL.md").read_bytes()
    assert run(tmp_path).returncode == 1
    assert (target / "SKILL.md").read_bytes() == before
    assert not manifest(tmp_path).exists()


def test_unowned_files_survive_owned_package_removal_and_empty_source(tmp_path):
    source = package(tmp_path, "skills")
    unowned = tmp_path / ".codex/skills/personal"
    unowned.mkdir(parents=True)
    (unowned / "SKILL.md").write_text("personal")
    loose = unowned.parent / "notes.txt"
    loose.write_text("loose")
    assert run(tmp_path).returncode == 0
    shutil.rmtree(source)
    assert run(tmp_path).returncode == 0
    assert not (unowned.parent / "info-example").exists()
    assert (unowned / "SKILL.md").read_text() == "personal"
    assert loose.read_text() == "loose"
    assert json.loads(manifest(tmp_path).read_text())["entries"] == {}


@pytest.mark.parametrize("missing_manifest", [False, True])
def test_missing_source_is_noop_even_with_managed_destination(tmp_path, missing_manifest):
    package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    if missing_manifest:
        manifest(tmp_path).unlink()
    shutil.rmtree(tmp_path / "docs/skills")
    assert json.loads(run(tmp_path).stdout) == {"changes": []}
    assert (tmp_path / ".codex/skills/info-example/SKILL.md").is_file()


@pytest.mark.parametrize("empty_source", [False, True])
def test_lost_manifest_never_claims_or_deletes_old_output(tmp_path, empty_source):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    manifest(tmp_path).unlink()
    if empty_source:
        shutil.rmtree(source)
    result = run(tmp_path)
    assert result.returncode == (0 if empty_source else 1)
    assert (tmp_path / ".codex/skills/info-example/SKILL.md").is_file()


@pytest.mark.parametrize("bad", [
    "{", "[]", '{"version":1,"entries":{},"extra":true}',
    '{"version":true,"entries":{}}', '{"version":1,"entries":{},"entries":{}}',
    *[json.dumps({"version": 1, "entries": {name: "dir"}})
      for name in ("../escape", "/absolute", "a/../../escape", "a//b", "a/./b", "C:/escape", "a\\b")],
    json.dumps({"version": 1, "entries": {"info-example": "dir", "info-example/SKILL.md": "bad-hash"}}),
])
def test_corrupt_manifest_fails_closed(tmp_path, bad):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    before = (source / "SKILL.md").read_bytes()
    manifest(tmp_path).write_text(bad)
    shutil.rmtree(source)
    result = run(tmp_path)
    assert result.returncode == 1
    assert (tmp_path / ".codex/skills/info-example/SKILL.md").read_bytes() == before
    assert manifest(tmp_path).read_text() == bad


@pytest.mark.parametrize("location", ["manifest", "state", "owned_file", "owned_directory"])
def test_symlink_boundaries_preserve_external_content(tmp_path, location):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep").write_text("safe")
    if location == "manifest":
        path = manifest(tmp_path)
    elif location == "state":
        path = manifest(tmp_path).parent
    elif location == "owned_file":
        path = tmp_path / ".codex/skills/info-example/SKILL.md"
    else:
        path = tmp_path / ".codex/skills/info-example/assets"
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    path.symlink_to(external, target_is_directory=True)
    shutil.rmtree(source)
    assert run(tmp_path).returncode == 1
    assert path.is_symlink()
    assert (external / "keep").read_text() == "safe"


@pytest.mark.parametrize("phase", ["journal", "output", "manifest"])
def test_interrupted_mutation_blocks_retry_without_adoption(tmp_path, phase):
    package(tmp_path, "skills")
    code = r"""
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import sync_documents as sync
original = sync.atomic_write
phase = sys.argv[3]
def interrupted(path, content):
    original(path, content)
    if ((phase == "journal" and path.name == "pending.json")
        or (phase == "output" and path.name == "SKILL.md")
        or (phase == "manifest" and path.name == "manifest.json")):
        os._exit(73)
sync.atomic_write = interrupted
sync.sync(Path(sys.argv[2]))
"""
    stopped = subprocess.run([sys.executable, "-c", code, str(SCRIPT.parent), str(tmp_path), phase])
    assert stopped.returncode == 73
    pending = manifest(tmp_path).with_name("pending.json")
    journal = pending.read_bytes()
    output = tmp_path / ".codex/skills/info-example/SKILL.md"
    if output.exists():
        output.write_text("human recovery edit")
    result = run(tmp_path)
    assert result.returncode == 1
    assert "Interrupted document sync" in result.stderr
    assert pending.read_bytes() == journal
    if output.exists():
        assert output.read_text() == "human recovery edit"


def test_no_bundled_auto_hooks():
    assert json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"] == {}
    result = subprocess.run([sys.executable, str(SCRIPT), "--hook"], text=True, capture_output=True)
    assert result.returncode != 0


def test_cli_runs_from_relocated_document_skill(tmp_path):
    installed = tmp_path / "installed plugin"
    shutil.copytree(ROOT / "skills/document", installed / "skills/document",
                    ignore=shutil.ignore_patterns("__pycache__"))
    project = tmp_path / "consumer"
    project.mkdir()
    source = package(project, "skills")
    result = subprocess.run([sys.executable, str(installed / "skills/document/scripts/sync_documents.py"),
                             "--project-root", str(project)], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (project / ".codex/skills/info-example/SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()


@pytest.mark.parametrize("kind", ["source_link", "target_link", "locked", "lock_link"])
def test_unsafe_inputs_preserve_documents(tmp_path, kind):
    source = package(tmp_path, "skills")
    state = tmp_path / ".codex/.document-sync"
    state.mkdir(parents=True)
    if kind == "source_link":
        (source / "link").symlink_to(tmp_path / "missing")
    elif kind == "target_link":
        (tmp_path / ".codex/skills").symlink_to(tmp_path / "missing")
    elif kind == "lock_link":
        (state / "lock").symlink_to(tmp_path / "missing")
    else:
        (state / "lock").mkdir()
    result = run(tmp_path)
    assert result.returncode == 1
    assert not (tmp_path / ".codex/skills").exists()


@pytest.mark.parametrize("stop_method", ["terminate", "kill"])
def test_sync_excludes_live_owner_and_recovers_after_forced_exit(tmp_path, stop_method):
    import time

    source = package(tmp_path, "skills")
    state = tmp_path / ".codex/.document-sync"
    state.mkdir(parents=True)
    ready = tmp_path / "owner-ready"
    code = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sync_documents import locked
with locked(Path(sys.argv[2])):
    Path(sys.argv[3]).touch()
    time.sleep(60)
"""
    owner = subprocess.Popen([sys.executable, "-c", code, str(SCRIPT.parent),
                              str(state), str(ready)])
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "Lock owner did not start"
        result = run(tmp_path)
        assert result.returncode == 1
        assert "already running" in result.stderr
        assert not (tmp_path / ".codex/skills").exists()
        getattr(owner, stop_method)()
        owner.wait(timeout=5)
        assert (state / "lock").is_file()
        result = run(tmp_path)
        assert result.returncode == 0, result.stderr
        assert (tmp_path / ".codex/skills/info-example/SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
        # Normal completion must release the lock as well, without unlinking it.
        assert json.loads(run(tmp_path).stdout) == {"changes": []}
        assert (state / "lock").is_file()
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=5)


def test_managed_shape_changes_and_preserves_other_codex_content(tmp_path):
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


def test_sync_projects_only_skills(tmp_path):
    source = package(tmp_path, "skills")
    for kind in ("original", "processed"):
        ignored = package(tmp_path, kind)
        (ignored / "SKILL.md").unlink()
        (ignored / "assets/link").symlink_to(tmp_path / "missing")
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".codex/skills/info-example/SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
    for kind in ("original", "processed"):
        assert not (tmp_path / ".codex" / kind).exists()
        assert (tmp_path / "docs" / kind / "info-example/assets/data.bin").read_bytes() == bytes(range(256))


def test_original_and_processed_only_project_is_noop(tmp_path):
    for kind in ("original", "processed"):
        package(tmp_path, kind)
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"changes": []}
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


@pytest.mark.parametrize("kind", ["manifest", "lock"])
def test_non_regular_state_is_rejected_without_blocking(tmp_path, kind):
    import os
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO fixture requires POSIX")
    package(tmp_path, "skills")
    state = tmp_path / ".codex/.document-sync"
    state.mkdir(parents=True)
    os.mkfifo(state / ("manifest.json" if kind == "manifest" else "lock"))
    result = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(tmp_path)],
                            text=True, capture_output=True, timeout=5)
    assert result.returncode == 1
    assert not (tmp_path / ".codex/skills").exists()


def test_preflight_collision_does_not_update_other_owned_package(tmp_path):
    source = package(tmp_path, "skills")
    assert run(tmp_path).returncode == 0
    target = tmp_path / ".codex/skills/info-example/SKILL.md"
    before = target.read_bytes()
    (source / "SKILL.md").write_text("pending update")
    second = tmp_path / "docs/skills/other"
    second.mkdir()
    (second / "SKILL.md").write_text("new")
    unowned = tmp_path / ".codex/skills/other"
    shutil.copytree(second, unowned)
    result = run(tmp_path)
    assert result.returncode == 1
    assert "Unowned destination" in result.stderr
    assert target.read_bytes() == before
    assert (unowned / "SKILL.md").read_text() == "new"
