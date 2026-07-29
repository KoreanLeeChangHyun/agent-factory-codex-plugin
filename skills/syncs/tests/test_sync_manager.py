from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
MANAGER = SKILL_ROOT / "scripts" / "sync.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("sync_manager_test", MANAGER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def run_manager(
    root: Path, *args: str, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(MANAGER), *args],
        cwd=cwd or root,
        check=check,
        capture_output=True,
        text=True,
    )


class SyncManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-q", "-b", "main")
        (self.root / "nested" / "child").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def resolve(
        self, source: str, *extra: str, cwd: Path | None = None
    ) -> dict[str, object]:
        result = run_manager(self.root, "resolve", "--source", source, *extra, cwd=cwd)
        return json.loads(result.stdout)

    def test_defaults_are_resolved_from_git_root_when_invoked_below_it(self) -> None:
        nested = self.root / "nested" / "child"

        drive = self.resolve("google-drive", cwd=nested)
        gmail = self.resolve("google-gmail", cwd=nested)

        self.assertEqual(drive["projectRoot"], str(self.root.resolve()))
        self.assertEqual(
            drive["destination"], str((self.root / "source/google/drive").resolve())
        )
        self.assertEqual(
            gmail["destination"], str((self.root / "source/google/mail").resolve())
        )
        self.assertEqual(drive["origin"], "default")
        self.assertEqual(gmail["origin"], "default")

    def test_source_overrides_are_independent(self) -> None:
        run_manager(
            self.root,
            "set",
            "--source",
            "google-drive",
            "--destination",
            "snapshots/drive",
        )

        drive = self.resolve("google-drive")
        gmail = self.resolve("google-gmail")

        self.assertEqual(
            drive["destination"], str((self.root / "snapshots/drive").resolve())
        )
        self.assertEqual(drive["origin"], "config")
        self.assertEqual(
            gmail["destination"], str((self.root / "source/google/mail").resolve())
        )
        self.assertEqual(gmail["origin"], "default")

    def test_explicit_destination_precedes_config_and_supports_absolute_paths(
        self,
    ) -> None:
        run_manager(
            self.root,
            "set",
            "--source",
            "google-gmail",
            "--destination",
            "configured/mail",
        )
        absolute = self.root.parent / "absolute-mail"

        resolved = self.resolve(
            "google-gmail", "--destination", str(absolute)
        )

        self.assertEqual(resolved["destination"], str(absolute.resolve()))
        self.assertEqual(resolved["origin"], "explicit")

    def test_invalid_relative_destination_fails_without_moving_existing_data(
        self,
    ) -> None:
        existing = self.root / "source/google/mail/existing.eml"
        existing.parent.mkdir(parents=True)
        existing.write_text("preserve", encoding="utf-8")

        result = run_manager(
            self.root,
            "resolve",
            "--source",
            "google-gmail",
            "--destination",
            "../outside",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not contain '..'", result.stderr)
        self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")
        self.assertFalse((self.root.parent / "outside").exists())

    def test_set_writes_schema_valid_config_without_creating_destination(
        self,
    ) -> None:
        result = run_manager(
            self.root,
            "set",
            "--source",
            "google-gmail",
            "--destination",
            "archive/mail",
        )
        payload = json.loads(result.stdout)
        config_path = self.root / ".agent-factory/sync.json"

        self.assertEqual(payload["configPath"], str(config_path))
        self.assertTrue(config_path.is_file())
        self.assertFalse((self.root / "archive/mail").exists())
        checked = run_manager(self.root, "show")
        self.assertEqual(
            json.loads(checked.stdout)["sources"]["google-gmail"]["destination"],
            "archive/mail",
        )

    def test_directory_swap_between_validation_and_open_fails_closed(self) -> None:
        manager = load_manager()
        agent_factory = self.root / ".agent-factory"
        original = self.root / ".agent-factory-original"
        outside = self.root / "outside"
        agent_factory.mkdir()
        real_open = manager.os.open
        swapped = False

        def swapping_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if (
                path == ".agent-factory"
                and kwargs.get("dir_fd") is not None
                and not swapped
            ):
                agent_factory.rename(original)
                outside.mkdir()
                agent_factory.symlink_to(outside, target_is_directory=True)
                swapped = True
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(manager.os, "open", side_effect=swapping_open):
            with self.assertRaises(manager.SyncConfigError):
                manager.write_config(
                    self.root,
                    {
                        "schemaVersion": "1.0.0",
                        "sources": {
                            "google-drive": {"destination": "source/google/drive"}
                        },
                    },
                )

        self.assertFalse((outside / "sync.json").exists())

    def test_explicit_project_root_must_be_the_git_top_level(self) -> None:
        result = run_manager(
            self.root,
            "resolve",
            "--source",
            "google-drive",
            "--project-root",
            str(self.root / "nested"),
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match Git top-level", result.stderr)

    def test_sync_skill_contracts_use_the_shared_resolver(self) -> None:
        documents = {
            "syncs": SKILL_ROOT / "SKILL.md",
            "google-drive": SKILL_ROOT.parent / "syncs-google-drive" / "SKILL.md",
            "google-gmail": SKILL_ROOT.parent / "syncs-google-gmail" / "SKILL.md",
        }
        for name, path in documents.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertIn(".agent-factory/sync.json", text)
                self.assertIn("scripts/sync.py", text)
                self.assertIn("resolved destination", text.lower())


if __name__ == "__main__":
    unittest.main()
