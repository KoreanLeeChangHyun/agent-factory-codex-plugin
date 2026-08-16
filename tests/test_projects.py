from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest import mock


PROJECTS = Path(__file__).resolve().parents[1] / "skills" / "projects"


def load_script(name: str) -> ModuleType:
    path = PROJECTS / "scripts" / f"{name}.py"
    specification = importlib.util.spec_from_file_location(
        f"agent_factory_{name}", path
    )
    if specification is None or specification.loader is None:
        raise AssertionError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


project = load_script("project")
viewer = load_script("viewer")


class ProjectRecordingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        with mock.patch("builtins.print"):
            project.initialize(
                SimpleNamespace(project_root=str(self.root), name="Example")
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def progress(self) -> Path:
        return (
            self.root
            / ".agent-factory"
            / "skills"
            / "project"
            / "references"
            / "progress.md"
        )

    def progress_args(self, **overrides: object) -> SimpleNamespace:
        values: dict[str, object] = {
            "project_root": str(self.root),
            "title": "Completed work",
            "summary": "Changed one file",
            "status": "completed",
            "changed_path": ["src/app.py"],
            "feedback": "accepted",
            "tests": "tests not run",
            "receipt": "work-001",
            "disposition": "accepted",
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_record_is_complete_and_flattens_markdown_input(self) -> None:
        original_inode = self.progress.stat().st_ino
        with mock.patch("builtins.print"):
            project.record_progress(
                self.progress_args(
                    title="safe\n## forged",
                    summary="summary\n- injected",
                )
            )
        content = self.progress.read_text(encoding="utf-8")
        self.assertNotEqual(self.progress.stat().st_ino, original_inode)
        self.assertIn("Receipt: `work-001`", content)
        self.assertIn("Disposition: accepted", content)
        self.assertNotIn("\n## forged", content)
        self.assertNotIn("\n- injected", content)

    def test_record_rejects_a_symlink_target_without_touching_its_destination(
        self,
    ) -> None:
        destination = self.root / "outside.md"
        destination.write_text("outside\n", encoding="utf-8")
        self.progress.unlink()
        self.progress.symlink_to(destination)
        with self.assertRaises(SystemExit):
            project.record_progress(self.progress_args())
        self.assertEqual(destination.read_text(encoding="utf-8"), "outside\n")

    def test_record_rejects_a_hard_link_target(self) -> None:
        destination = self.root / "outside.md"
        destination.write_text("outside\n", encoding="utf-8")
        self.progress.unlink()
        os.link(destination, self.progress)
        with self.assertRaises(SystemExit):
            project.record_progress(self.progress_args())
        self.assertEqual(destination.read_text(encoding="utf-8"), "outside\n")


class ProjectViewerTests(unittest.TestCase):
    def test_reader_skips_symlinks_binary_files_and_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            references = root / ".agent-factory/skills/project/references"
            references.mkdir(parents=True)
            (references.parent / "SKILL.md").write_text(
                "# Project\n", encoding="utf-8"
            )
            (references / "valid.md").write_text("valid\n", encoding="utf-8")
            (references / "binary.bin").write_bytes(b"\xff\xfe")
            (references / "large.md").write_bytes(
                b"x" * (viewer.MAX_FILE_BYTES + 1)
            )
            (references / "linked.md").symlink_to(root / "outside.md")
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            os.link(outside, references / "hard-linked.md")

            skill = viewer.open_skill(root)
            self.assertIsNotNone(skill)
            assert skill is not None
            directory = viewer.open_directory(skill, "references")
            os.close(skill)
            files = viewer.files_under(directory, [viewer.MAX_TOTAL_BYTES])

        self.assertEqual(files, [{"path": "valid.md", "content": "valid\n"}])

    def test_loopback_resolution_rejects_unspecified_addresses(self) -> None:
        self.assertTrue(viewer.loopback_host("127.0.0.1"))
        self.assertTrue(viewer.loopback_host("::1"))
        self.assertFalse(viewer.loopback_host("0.0.0.0"))


if __name__ == "__main__":
    unittest.main()
