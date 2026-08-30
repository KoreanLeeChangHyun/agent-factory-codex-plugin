from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention", "document", "gather", "workspace"}


def fenced_tree_paths(content: str) -> set[str]:
    """Parse parent/child paths from the declared text tree."""
    block = re.search(r"```text\n(<project-root>/\.agent-factory/.*?)\n```", content, re.S)
    if block is None:
        return set()

    paths: set[str] = set()
    stack: dict[int, str] = {}
    for index, line in enumerate(block.group(1).splitlines()):
        match = re.match(r"(?P<prefix>(?:│   |    )*)(?:├── |└── )?(?P<name>.+)", line)
        if match is None:
            continue
        depth = 0 if index == 0 else len(match.group("prefix")) // 4 + 1
        name = match.group("name").rstrip("/")
        path = name if depth == 0 else f"{stack[depth - 1]}/{name}"
        stack[depth] = path
        paths.add(path)
    return paths


def normalized_paragraphs(content: str) -> list[str]:
    return [
        " ".join(re.sub(r"[`*_]", "", block).lower().split())
        for block in re.split(r"\n\s*\n", content)
        if block.strip()
    ]


class SkillMetadataTests(unittest.TestCase):
    def test_agent_factory_project_work_root_has_explicit_ownership(self) -> None:
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        paths = fenced_tree_paths(instructions)
        self.assertTrue(
            {
                "<project-root>/.agent-factory/db.sqlite",
                "<project-root>/.agent-factory/agent/<agent-id>/session.json",
                "<project-root>/.agent-factory/agent/<agent-id>/runs/<run-id>",
                "<project-root>/.agent-factory/document/original",
                "<project-root>/.agent-factory/document/processed",
                "<project-root>/.agent-factory/document/specification/human",
                "<project-root>/.agent-factory/document/sync.json",
                "<project-root>/.agent-factory/workspace/common",
                "<project-root>/.agent-factory/workspace/explorer",
                "<project-root>/.agent-factory/workspace/skills",
            }
            <= paths
        )
        paragraphs = normalized_paragraphs(instructions)
        self.assertTrue(
            any(
                re.search(
                    r"common/ owns the shared browser shell.*workspace/explorer/ owns an internal read-only file/project metadata projection.*skills/ owns internal read-only skill navigation",
                    paragraph,
                )
                for paragraph in paragraphs
            )
        )
        normalized_instructions = " ".join(
            instructions.casefold().replace("`", "").split()
        )
        self.assertIn(
            "temporary execution-only explorer material in the producing managed agent run",
            normalized_instructions,
        )
        self.assertIn(
            "durable explorer evidence as an original or processed document",
            normalized_instructions,
        )
        self.assertIn(
            "these stores define neither an activity nor nesting under one of the five activities",
            normalized_instructions,
        )
        self.assertNotIn(
            "workspace file/project explorer activity projection",
            normalized_instructions,
        )
        self.assertEqual(
            instructions,
            (SKILLS / "convention" / "assets" / "AGENTS.md").read_text(encoding="utf-8"),
        )
        for semantic_requirement in (
            "one semantic body",
            "ai-facing skill",
            "human-facing korean html, css, and javascript document",
            "must always remain semantically synchronized",
            "one-sided change is incomplete and unacceptable",
            "if both representations cannot be synchronized, do not report the change or run as completed",
        ):
            self.assertIn(semantic_requirement, normalized_instructions)
        self.assertTrue(
            any(
                re.search(r"gather.*destination outside this work root", paragraph)
                for paragraph in paragraphs
            )
        )

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
            "explorer",
            "interview",
            "specifications",
            "specification",
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

    def test_agent_exposes_only_three_prompt_roles(self) -> None:
        references = {
            path.name for path in (SKILLS / "agent" / "references").glob("*.md")
        }
        prompts = {path.name for path in (SKILLS / "agent" / "prompt").glob("*.md")}
        self.assertEqual(references, set())
        self.assertEqual(prompts, {"main.md", "work.md", "verification.md"})

    def test_public_skills_expose_only_their_owned_scripts(self) -> None:
        expected = {
            "agent": {"exec.py", "loop.py"},
            "convention": {"init_agents.py"},
            "document": set(),
            "gather": {
                "provider_support.py",
                "sync.py",
                "sync_discord.py",
                "sync_gmail.py",
                "sync_google_drive.py",
                "sync_notion.py",
                "sync_onedrive.py",
                "sync_slack.py",
            },
            "workspace": {"serve.py"},
        }
        for skill, scripts in expected.items():
            with self.subTest(skill=skill):
                self.assertEqual(
                    {path.name for path in (SKILLS / skill / "scripts").glob("*.py")},
                    scripts,
                )

    def test_gather_preserves_shared_sync_configuration_identity(self) -> None:
        management = (
            SKILLS / "gather" / "references" / "gather-management.md"
        ).read_text(encoding="utf-8")
        self.assertIn(".agent-factory/document/sync.json", management)
        self.assertTrue(
            (SKILLS / "gather" / "assets" / "schema" / "sync.schema.json").is_file()
        )
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync.py").is_file())
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync_gmail.py").is_file())


if __name__ == "__main__":
    unittest.main()
