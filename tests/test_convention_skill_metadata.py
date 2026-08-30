from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention", "document", "gather", "tool", "workspace"}


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


class ConventionSkillMetadataTests(unittest.TestCase):
    def test_readme_declares_adopted_shared_catalog_and_authority_boundary(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        normalized = " ".join(readme.casefold().replace("`", "").split())

        self.assertRegex(
            readme,
            r"(?ms)^\.agent-factory/\n├── db\.sqlite\n├── agent/",
        )
        for contract in (
            "the shared project-wide catalog/read model across agent execution structure and documents",
            "it is rebuildable and non-authoritative",
            "agent owns the maintained ddl at skills/agent/assets/schema/catalog.sql",
            "does not replace authoritative agent runtime files, document bodies or representations, provenance evidence, gather configuration, project skills, or faithful specification pairs",
            "the standard-library manager at skills/agent/scripts/catalog.py provides explicit init, rebuild, status, search-agents, and search-documents operations",
            "workspace initialization has no catalog side effect",
            "rebuild uses bounded local agent and document metadata scans plus capped allowlisted textual document indexing, builds and checks a separate database, and atomically publishes it without replacing the last good catalog on failure",
            "the implementation has no runtime dual write, http/general query api, catalog search screen/navigation integration, live watcher, semantic/vector search, or external-backend ingestion",
            "the database and its sqlite journal, shm, and wal sidecars are ignored generated artifacts and must not be committed",
            "agent execution does not depend on catalog creation, freshness, corruption, or availability",
            "workspace may later present agent-provided read-only results, but it does not own, initialize, rebuild, inspect, or execute searches against the catalog",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, normalized)

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
                "<project-root>/.agent-factory/document/specification",
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
            "human-facing korean html, css, and javascript representation",
            "must remain semantically synchronized",
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

    def test_public_skill_directories_match_the_six_skill_contract(self) -> None:
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
                expected_fields = {"name", "description", "metadata"}
                self.assertEqual(
                    {
                        "specification-id": name,
                        "human-entry": f".agent-factory/document/specification/{name}/index.html",
                        "ai-root": f"skills/{name}/",
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

    def test_agent_exposes_only_three_prompt_roles(self) -> None:
        references = {
            path.name for path in (SKILLS / "agent" / "references").glob("*.md")
        }
        prompts = {path.name for path in (SKILLS / "agent" / "prompt").glob("*.md")}
        self.assertEqual(references, set())
        self.assertEqual(prompts, {"main.md", "work.md", "verification.md"})

    def test_public_skills_expose_only_their_owned_scripts(self) -> None:
        expected = {
            "agent": {"catalog.py", "exec.py", "loop.py"},
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
            "tool": {"tool.py"},
            "workspace": {"serve.py"},
        }
        for skill, scripts in expected.items():
            with self.subTest(skill=skill):
                self.assertEqual(
                    {path.name for path in (SKILLS / skill / "scripts").glob("*.py")},
                    scripts,
                )

    def test_catalog_assets_and_manager_are_agent_owned_only(self) -> None:
        self.assertTrue((SKILLS / "agent" / "scripts" / "catalog.py").is_file())
        self.assertTrue(
            (SKILLS / "agent" / "assets" / "schema" / "catalog.sql").is_file()
        )
        self.assertFalse((SKILLS / "workspace" / "scripts" / "catalog.py").exists())
        self.assertFalse(
            (SKILLS / "workspace" / "assets" / "schema" / "catalog.sql").exists()
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

    def test_tool_is_a_logical_control_contract_without_a_local_backend(self) -> None:
        entry = (SKILLS / "tool" / "SKILL.md").read_text(encoding="utf-8")
        lifecycle = (
            SKILLS / "tool" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        combined = " ".join((entry + lifecycle).casefold().split())
        for authority_marker in (
            "host",
            "plugin",
            "mcp server",
            "project manifest",
        ):
            with self.subTest(authority_marker=authority_marker):
                self.assertIn(authority_marker, combined)
        for phrase in (
            "credential reference",
            "requested and actually granted permission scopes",
            "tool readiness does not authorize execution",
            "tool must not widen scope on its own",
            "no such runtime interface, registry, or state backend is implemented",
        ):
            self.assertIn(phrase, combined)
        self.assertFalse((ROOT / ".agent-factory" / "tool").exists())

    def test_tool_routes_distinct_git_profiles_without_owning_state(self) -> None:
        entry = (SKILLS / "tool" / "SKILL.md").read_text(encoding="utf-8")
        git_profiles = (
            SKILLS / "tool" / "references" / "git.md"
        ).read_text(encoding="utf-8")
        normalized_profiles = " ".join(git_profiles.casefold().split())
        self.assertIn("`references/git.md`", entry)
        for profile_id in ("git.cli", "github.cli", "git-lfs.cli"):
            with self.subTest(profile_id=profile_id):
                self.assertIn(f"`{profile_id}`", git_profiles)
                self.assertIn(f"`{profile_id}.inspect`", git_profiles)
                self.assertIn(f"`{profile_id}.execute`", git_profiles)
        for boundary in (
            "tool readiness never authorizes agent execution",
            "do not use a token-printing operation as a health check",
            "repository activation/configuration",
        ):
            self.assertIn(boundary, normalized_profiles)

    def test_tool_routes_playwright_profile_without_conflating_readiness(self) -> None:
        entry = (SKILLS / "tool" / "SKILL.md").read_text(encoding="utf-8")
        playwright = (
            SKILLS / "tool" / "references" / "playwright.md"
        ).read_text(encoding="utf-8")
        self.assertIn("`references/playwright.md`", entry)
        for identifier in (
            "playwright.browser",
            "playwright.browser.inspect",
            "playwright.browser.execute",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(f"`{identifier}`", playwright)


if __name__ == "__main__":
    unittest.main()
