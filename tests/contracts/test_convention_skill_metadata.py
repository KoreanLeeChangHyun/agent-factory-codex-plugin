from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention"}


class ConventionSkillMetadataTests(unittest.TestCase):
    def test_public_skill_directories_match_the_two_skill_contract(self) -> None:
        actual = {
            path.name
            for path in SKILLS.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertEqual(actual, PUBLIC_SKILLS)
        self.assertFalse((ROOT / "docs").exists())

    def test_skill_frontmatter_uses_exact_singular_names_and_fields(self) -> None:
        for name in sorted(PUBLIC_SKILLS):
            with self.subTest(skill=name):
                text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                _, frontmatter, _ = text.split("---", 2)
                metadata = yaml.safe_load(frontmatter)
                expected_fields = {"name", "description", "metadata"}
                self.assertEqual(
                    {
                        "specification-id": name,
                    },
                    metadata["metadata"],
                )
                self.assertEqual(set(metadata), expected_fields)
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

    def test_convention_reference_inventory_includes_nested_routes(self) -> None:
        convention = SKILLS / "convention"
        entry = (convention / "SKILL.md").read_text(encoding="utf-8")
        routes = set(re.findall(r"`references/([^`]+\.md)`", entry))
        declared = set(routes)
        for route in routes:
            content = (convention / "references" / route).read_text(encoding="utf-8")
            for nested in re.findall(r"^- Read `([^`]+\.md)`", content, re.M):
                declared.add((Path(route).parent / nested).as_posix())
        actual = {
            path.relative_to(convention / "references").as_posix()
            for path in (convention / "references").rglob("*.md")
        }
        self.assertEqual(declared, actual)

    def test_agent_prompt_roles(self) -> None:
        prompts = {path.name for path in (SKILLS / "agent" / "prompt").glob("*.md")}
        self.assertEqual(prompts, {"main.md", "work.md", "verification.md"})

    def test_public_skills_expose_only_their_owned_scripts(self) -> None:
        expected = {
            name: ({"exec.py", "loop.py"} if name == "agent" else set())
            for name in PUBLIC_SKILLS
        }
        for skill, scripts in expected.items():
            with self.subTest(skill=skill):
                self.assertEqual(
                    {path.name for path in (SKILLS / skill / "scripts").glob("*.py")},
                    scripts,
                )

    def test_legacy_artifacts_are_excluded_and_runtime_state_is_ignored(self):
        self.assertEqual(list(SKILLS.rglob("*.sql")), [])
        self.assertEqual(list(SKILLS.rglob("sync.schema.json")), [])
        self.assertEqual(list(SKILLS.rglob("requirements.txt")), [])
        ignored = (ROOT / ".gitignore").read_text()
        for item in ("/.agent-factory/db.sqlite", "/.agent-factory/db.sqlite-wal", "/.agent-factory/agent/"):
            self.assertIn(item, ignored)


if __name__ == "__main__":
    unittest.main()
