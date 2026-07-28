from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SECTIONED_DOCUMENT = (
    PLUGIN_ROOT / "skills" / "lifecycle" / "assets" / "scripts"
    / "sectioned_document.py"
)


class ArtifactManagerScriptContractTests(unittest.TestCase):
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
            "intake": "scripts/intake.py",
            "specification": "scripts/specification.py",
            "work-unit-planner": "assets/scripts/work_unit.py",
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
            PLUGIN_ROOT / "skills" / "lifecycle" / "SKILL.md",
            (
                PLUGIN_ROOT
                / "skills"
                / "lifecycle"
                / "references"
                / "common-document-contract.md"
            ),
        ]

        for path in paths:
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                self.assertIn("intake/scripts/intake.py", text)
                self.assertIn("specification/scripts/specification.py", text)
                self.assertIn(
                    "work-unit-planner/assets/scripts/work_unit.py",
                    text,
                )
                self.assertIn("stop before mutation", text)
                self.assertIn("exception path", text)

    def test_plugin_has_no_artifact_authoring_hooks_or_hook_contract(self) -> None:
        hooks_root = PLUGIN_ROOT / "hooks"
        self.assertFalse(hooks_root.exists() and any(hooks_root.iterdir()))
        contract_paths = [
            PLUGIN_ROOT / "skills" / "intake" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "specification" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "work-unit-planner" / "SKILL.md",
            PLUGIN_ROOT / "skills" / "lifecycle" / "SKILL.md",
            (
                PLUGIN_ROOT
                / "skills"
                / "lifecycle"
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
