from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention", "inquery", "specification", "gather"}


class SkillMetadataTests(unittest.TestCase):
    def test_agent_factory_project_work_root_has_explicit_ownership(self) -> None:
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for required in (
            "<project-root>/.agent-factory/",
            "<agent-id>/",
            "<run-id>/",
            "inquery/",
            "<inquiry-id>/",
            "specification/",
            "common/",
            "explorer/",
            "planning/",
            "skills/",
            "candidate/",
            "<specification-id>/",
            "sync.json",
            "paired Project Skill below",
            "Gather uses its resolved destination outside this work root",
        ):
            self.assertIn(required, instructions)

    def test_public_skill_directories_match_the_five_skill_contract(self) -> None:
        actual = {
            path.name
            for path in SKILLS.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertEqual(actual, PUBLIC_SKILLS)

        for removed in (
            "agents",
            "conventions",
            "specifications",
            "synchronization",
            "intakes",
            "lifecycle",
            "projects",
            "rules",
            "work-units",
        ):
            with self.subTest(removed=removed):
                self.assertFalse((SKILLS / removed).exists())

    def test_skill_frontmatter_uses_exact_singular_names_and_fields(self) -> None:
        for name in sorted(PUBLIC_SKILLS):
            with self.subTest(skill=name):
                text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                _, frontmatter, _ = text.split("---", 2)
                metadata = yaml.safe_load(frontmatter)
                self.assertEqual(set(metadata), {"name", "description"})
                self.assertEqual(metadata["name"], name)

    def test_openai_yaml_interfaces_use_matching_invocation_names(self) -> None:
        for name in sorted(PUBLIC_SKILLS):
            with self.subTest(skill=name):
                path = SKILLS / name / "agents" / "openai.yaml"
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
                interface = value["interface"]
                short = interface["short_description"]
                self.assertGreaterEqual(len(short), 25)
                self.assertLessEqual(len(short), 64)
                self.assertIn(f"${name}", interface["default_prompt"])

    def test_entrypoint_routes_resolve_inside_each_skill(self) -> None:
        for name in sorted(PUBLIC_SKILLS):
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.startswith("- `references/"):
                    continue
                reference = line.split("`", 2)[1]
                with self.subTest(skill=name, reference=reference):
                    self.assertTrue((SKILLS / name / reference).is_file())

    def test_agent_exposes_only_managed_main_work_review_and_inquiry_roles(self) -> None:
        references = {
            path.name for path in (SKILLS / "agent" / "references").glob("*.md")
        }
        self.assertEqual(references, {"main.md", "work.md", "review.md", "inquery.md"})
        entry = (SKILLS / "agent" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("codex exec", entry)
        self.assertIn("Do not use platform Sub-agents", entry)

    def test_gather_preserves_sync_mechanisms_without_promoting_truth(self) -> None:
        gather = (SKILLS / "gather" / "SKILL.md").read_text(encoding="utf-8")
        management = (
            SKILLS / "gather" / "references" / "gather-management.md"
        ).read_text(encoding="utf-8")
        self.assertIn("gathered collections as evidence", gather)
        self.assertIn("do not reconcile", gather)
        self.assertIn(".agent-factory/sync.json", gather + management)
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync.py").is_file())
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync_gmail.py").is_file())


if __name__ == "__main__":
    unittest.main()
