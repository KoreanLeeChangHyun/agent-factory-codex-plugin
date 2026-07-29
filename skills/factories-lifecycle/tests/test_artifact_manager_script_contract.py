from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SECTIONED_DOCUMENT = (
    PLUGIN_ROOT
    / "skills"
    / "factories-lifecycle"
    / "scripts"
    / "sectioned_document.py"
)
MANAGERS = {
    "intakes": (
        PLUGIN_ROOT / "skills" / "intakes" / "scripts" / "intake.py",
        [],
    ),
    "specifications": (
        PLUGIN_ROOT / "skills" / "specifications" / "scripts" / "specification.py",
        ["--profile", "project-core"],
    ),
    "work-units": (
        PLUGIN_ROOT
        / "skills"
        / "work-units-manager"
        / "scripts"
        / "work_unit.py",
        [],
    ),
}


class ArtifactManagerScriptContractTests(unittest.TestCase):
    def test_canonical_crud_and_validation_ignore_git_tracking_state(self) -> None:
        for collection, (manager, create_extra) in MANAGERS.items():
            for tracking_state in ("tracked", "untracked", "ignored"):
                with self.subTest(
                    collection=collection, tracking_state=tracking_state
                ), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    subprocess.run(
                        ["git", "init", "-q", "-b", "main"],
                        cwd=root,
                        check=True,
                    )
                    if tracking_state == "ignored":
                        (root / ".gitignore").write_text(
                            "/.agent-factory/\n", encoding="utf-8"
                        )
                    package = root / ".agent-factory" / collection / "sample"
                    create = subprocess.run(
                        [
                            "python3",
                            str(manager),
                            "create",
                            str(package),
                            "--id",
                            "sample",
                            "--title",
                            "Sample",
                            "--project-id",
                            "sample-project",
                            "--theme",
                            "default",
                            *create_extra,
                        ],
                        cwd=root,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    self.assertTrue(json.loads(create.stdout)["valid"])
                    if tracking_state == "tracked":
                        subprocess.run(
                            ["git", "add", ".agent-factory"],
                            cwd=root,
                            check=True,
                        )
                    status = subprocess.run(
                        ["git", "status", "--short", "--ignored", ".agent-factory"],
                        cwd=root,
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout
                    expected_prefix = {
                        "tracked": "A ",
                        "untracked": "??",
                        "ignored": "!!",
                    }[tracking_state]
                    self.assertIn(expected_prefix, status)

                    subprocess.run(
                        [
                            "python3",
                            str(manager),
                            "title-set",
                            str(package),
                            "Updated",
                        ],
                        cwd=root,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    validated = subprocess.run(
                        ["python3", str(manager), "validate", str(package), "--full"],
                        cwd=root,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    self.assertTrue(json.loads(validated.stdout)["valid"])

    def test_linked_worktree_canonical_paths_route_to_primary_repository(
        self,
    ) -> None:
        spec = importlib.util.spec_from_file_location(
            "sectioned_document_primary_route_test",
            SECTIONED_DOCUMENT,
        )
        assert spec is not None and spec.loader is not None
        manager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manager)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary = root / "primary"
            linked = root / "linked"
            primary.mkdir()
            subprocess.run(
                ["git", "init", "-q", "-b", "main"],
                cwd=primary,
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Agent Factory Test",
                    "-c",
                    "user.email=agent-factory@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-q",
                    "-m",
                    "baseline",
                ],
                cwd=primary,
                check=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "work-unit/test", linked],
                cwd=primary,
                check=True,
            )
            requested = linked / ".agent-factory" / "intakes" / "sample"
            prior = Path.cwd()
            try:
                os.chdir(linked)
                selected = manager.canonical_primary_package(requested)
            finally:
                os.chdir(prior)

            self.assertEqual(
                selected,
                primary / ".agent-factory" / "intakes" / "sample",
            )

    def test_canonical_artifact_skills_require_their_owning_scripts(self) -> None:
        contracts = {
            "intakes": "scripts/intake.py",
            "specifications": "scripts/specification.py",
            "work-units-manager": "scripts/work_unit.py",
        }

        for skill_name, manager_path in contracts.items():
            skill_root = PLUGIN_ROOT / "skills" / skill_name
            text = " ".join(
                (skill_root / "SKILL.md").read_text(encoding="utf-8").split()
            )
            with self.subTest(skill=skill_name):
                self.assertTrue((skill_root / manager_path).is_file())
                self.assertIn("Mandatory Manager Script Gate", text)
                self.assertIn(manager_path, text)
                self.assertIn("hard precondition", text)
                self.assertIn("stop before mutation", text)
                self.assertIn("Do not fall back to direct JSON editing", text)
                self.assertIn("do not create an exception path", text)

    def test_shared_contract_requires_script_only_fail_closed_management(
        self,
    ) -> None:
        paths = [
            PLUGIN_ROOT / "skills" / "factories-lifecycle" / "SKILL.md",
            (
                PLUGIN_ROOT
                / "skills"
                / "factories-lifecycle"
                / "references"
                / "common-document-contract.md"
            ),
        ]

        for path in paths:
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                self.assertIn("intakes/scripts/intake.py", text)
                self.assertIn("specifications/scripts/specification.py", text)
                self.assertIn(
                    "work-units-manager/scripts/work_unit.py",
                    text,
                )
                self.assertIn("stop before mutation", text)
                self.assertIn("exception path", text)

    def test_plugin_has_no_artifact_authoring_hooks_or_hook_contract(self) -> None:
        hooks_root = PLUGIN_ROOT / "hooks"
        self.assertFalse(hooks_root.exists() and any(hooks_root.iterdir()))
        contract_paths = [
            PLUGIN_ROOT / "skills" / "intakes" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "specifications" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "work-units-manager" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "factories-lifecycle" / "SKILL.md",
            (
                PLUGIN_ROOT
                / "skills"
                / "factories-lifecycle"
                / "references"
                / "common-document-contract.md"
            ),
        ]
        forbidden = (
            "hooks/hooks.json",
            "artifact_json_guard.py",
            "PreToolUse",
            "one-shot grant",
            "audited one-shot",
        )

        for path in contract_paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                for phrase in forbidden:
                    self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
