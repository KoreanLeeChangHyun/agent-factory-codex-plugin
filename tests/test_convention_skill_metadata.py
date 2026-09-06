from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention", "document", "gather", "tool", "workspace"}


class ConventionSkillMetadataTests(unittest.TestCase):
    def test_readme_declares_cloud_and_local_authority(self):
        text = (ROOT / "README.md").read_text()
        for phrase in ("cloud", "exec.py", "loop.py", "document_template", "six Skills", "Code retirement never authorizes deletion"):
            self.assertIn(phrase, text)

    def test_agents_entrypoint_routes_to_authoritative_convention_references(self) -> None:
        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(
            instructions,
            (SKILLS / "convention" / "assets" / "AGENTS.md").read_text(encoding="utf-8"),
        )
        self.assertLessEqual(len(instructions.splitlines()), 24)
        self.assertIn(
            "skills/convention/references/agent-factory-core.md", instructions
        )
        self.assertIn(
            "skills/convention/references/directory-structure.md", instructions
        )
        self.assertIn("Use the relevant Agent Factory Skills", instructions)
        self.assertIn("<plugin-root>/skills/", instructions)
        self.assertIn("do not create or mirror them", instructions)
        for duplicated_detail in (
            "db.sqlite",
            "one semantic body",
            "Human-only skip",
            "Google Drive and OneDrive",
        ):
            self.assertNotIn(duplicated_detail, instructions)

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
        self.assertEqual(references, {"reporting.md"})
        self.assertEqual(prompts, {"main.md", "work.md", "verification.md"})

    def test_public_skills_expose_only_their_owned_scripts(self) -> None:
        expected = {name: ({"exec.py", "loop.py"} if name == "agent" else set()) for name in PUBLIC_SKILLS}
        for skill, scripts in expected.items():
            with self.subTest(skill=skill):
                self.assertEqual(
                    {path.name for path in (SKILLS / skill / "scripts").glob("*.py")},
                    scripts,
                )

    def test_no_distributed_domain_executable_schema_or_secret_dependency(self):
        python_files = {p.relative_to(SKILLS).as_posix() for p in SKILLS.rglob("*.py")}
        self.assertEqual(python_files, {"agent/scripts/exec.py", "agent/scripts/loop.py", "agent/runtime/cloud_reporting.py"})
        self.assertEqual(list(SKILLS.rglob("*.sql")), [])
        self.assertEqual(list(SKILLS.rglob("sync.schema.json")), [])
        self.assertEqual(list(SKILLS.rglob("requirements.txt")), [])
        self.assertFalse(any(p.is_file() for p in (SKILLS / "document/assets/document").rglob("*")))
        ignored = (ROOT / ".gitignore").read_text()
        for item in ("/.agent-factory/db.sqlite", "/.agent-factory/db.sqlite-wal", "/.agent-factory/agent/"):
            self.assertIn(item, ignored)

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
