from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
PUBLIC_SKILLS = {"agent", "convention", "document"}


class ConventionSkillMetadataTests(unittest.TestCase):
    def test_public_skill_directories_match_the_public_skill_contract(self) -> None:
        actual = {
            path.name
            for path in SKILLS.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertEqual(actual, PUBLIC_SKILLS)

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

    def test_agent_reference_inventory_is_routed_from_entrypoint(self) -> None:
        agent = SKILLS / "agent"
        entry = (agent / "SKILL.md").read_text(encoding="utf-8")
        declared = set(re.findall(r"`references/([^`]+\.md)`", entry))
        actual = {
            path.relative_to(agent / "references").as_posix()
            for path in (agent / "references").rglob("*.md")
        }
        self.assertEqual(declared, actual)

    def test_distributed_guidance_excludes_mcp_service_instructions(self) -> None:
        for path in sorted(SKILLS.rglob("*")):
            if path.suffix not in {".md", ".yaml"}:
                continue
            with self.subTest(path=path.relative_to(SKILLS).as_posix()):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"(?i)\bMCP\b|cloud reporting|reporting-deliver|--reporting-config")

    def test_local_workflow_and_service_independence_contracts_are_explicit(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agent = (SKILLS / "agent" / "SKILL.md").read_text(encoding="utf-8")
        convention = (SKILLS / "convention" / "SKILL.md").read_text(encoding="utf-8")
        layout = (
            SKILLS / "document" / "SKILL.md"
        ).read_text(encoding="utf-8")
        documents = (SKILLS / "document" / "SKILL.md").read_text(encoding="utf-8") + "\n" + "\n".join(
            (SKILLS / "document" / "references" / name).read_text(encoding="utf-8")
            for name in ("specification.md", "processed.md", "original.md")
        )
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        for mode in ("Extension + plugin", "MCP"):
            self.assertIn(mode, readme)
        plugin_only = re.search(
            r"(?ms)^- \*\*Extension \+ plugin:\*\*\s*(.+?)(?=^- \*\*MCP:\*\*)",
            readme,
        )
        self.assertIsNotNone(plugin_only)
        standalone = " ".join(plugin_only.group(1).split())
        self.assertRegex(
            standalone.lower(), r"\bcomplete\b.*\blocal\b.*\bworkflow\b"
        )
        self.assertRegex(standalone, r"(?:requires? no|without)\s+Agent Factory MCP")
        for dependency in (
            "package",
            "server",
            "account",
            "tenant",
            "connection",
            "authenticated resource",
        ):
            with self.subTest(standalone_dependency=dependency):
                self.assertIn(dependency, standalone)
        self.assertIn(
            "Main, Work, Verification and exec/loop provide the complete local workflow",
            " ".join(agent.split()),
        )
        manifest_description = manifest["interface"]["longDescription"]
        self.assertIn("complete local workflows", manifest_description)
        for mode in ("direct", "work", "work-verification", "plan-work-verification"):
            self.assertRegex(manifest_description, rf"(?<![\w-]){mode}(?![\w-])")
        self.assertRegex(manifest_description, r"\bNo MCP package\b")
        for dependency in (
            "server", "account", "tenant", "connection", "authenticated resource"
        ):
            with self.subTest(manifest_dependency=dependency):
                self.assertIn(dependency, manifest_description)
        self.assertIn("../agent/SKILL.md", convention)
        self.assertIn("../document/SKILL.md", convention)
        for document_type in ("original", "processed", "skills"):
            self.assertIn(
                f"<project-root>/docs/{document_type}/<category>[-<domain>]-<name>/", layout
            )
        self.assertIn("not an error fallback", " ".join(layout.split()))
        self.assertNotIn("docs/<category>[-<domain>]-<name>.html", documents)
        self.assertIn(
            "docs/skills/<category>[-<domain>]-<name>/SKILL.md", documents
        )
        for clause_id in (
            "specification.routing.canonical",
        ):
            self.assertIn(f"<!-- clause-id: {clause_id} -->", documents)
        distributed_python = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SKILLS / "agent").rglob("*.py")
        )
        self.assertNotRegex(
            distributed_python, r"(?m)^\s*(?:from|import)\s+mcp(?:\.|\s|$)"
        )
        self.assertNotIn("mcp", (ROOT / "requirements.txt").read_text().lower())

    def test_document_package_contract(self) -> None:
        documents = (SKILLS / "document" / "SKILL.md").read_text(encoding="utf-8") + "\n" + "\n".join(
            (SKILLS / "document" / "references" / name).read_text(encoding="utf-8")
            for name in ("specification.md", "processed.md", "original.md")
        )
        normalized_documents = " ".join(documents.split())
        asset = (SKILLS / "convention" / "assets" / "AGENTS.md").read_text(
            encoding="utf-8"
        )

        for document_type in ("original", "processed", "skills"):
            root = f"<project-root>/docs/{document_type}/<category>[-<domain>]-<name>/"
            self.assertIn(root, documents)
        for detail in (
            "provenance",
            "fidelity",
            "nonempty `links` list",
            "Store no copied source body",
            "Every AI-generated durable Document is Processed by default",
            "`interview`",
            "`research`",
            "`analyze`",
        ):
            with self.subTest(detail=detail):
                self.assertIn(detail, normalized_documents)
        self.assertIn(
            "limited to `info-*`, `rule-*`, and `design-*`",
            normalized_documents,
        )
        self.assertIn("`docs/skills/`", asset)
        self.assertIn("<category>[-<domain>]-<name>/SKILL.md", asset)

    def test_structured_design_json_is_a_linked_asset(self) -> None:
        document = (SKILLS / "document" / "SKILL.md").read_text(encoding="utf-8")
        diagrams = (SKILLS / "convention" / "references" / "diagrams.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join((document + "\n" + diagrams).split())
        for detail in (
            "system architecture",
            "database/ERD",
            "API design",
            "separate JSON file under `assets/`",
            "descriptive relative Markdown link",
            "does not embed the JSON object or a fenced JSON copy",
        ):
            with self.subTest(detail=detail):
                self.assertIn(detail, normalized)
        self.assertIn(
            "[System architecture](assets/system-architecture.json)", document
        )

    def test_original_and_processed_catalog_contract(self) -> None:
        document = (SKILLS / "document" / "SKILL.md").read_text(encoding="utf-8")
        original = (SKILLS / "document" / "references" / "original.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join((document + "\n" + original).split())
        for detail in (
            "one `metadata.yaml` with metadata and links only",
            "stores no copied source body or assets",
            "Original and Processed packages use the separate local Document catalog",
            "writes no generated index into the project",
            "do not activate a Processed Document as a Skill",
            "nonempty `links` list",
        ):
            with self.subTest(detail=detail):
                self.assertIn(detail, normalized)

    def test_agent_prompt_roles(self) -> None:
        prompts = {path.name for path in (SKILLS / "agent" / "prompt").glob("*.md")}
        self.assertEqual(prompts, {"main.md", "work.md", "verification.md"})

    def test_agent_prompt_markdown_links_resolve(self) -> None:
        for prompt in sorted((SKILLS / "agent" / "prompt").glob("*.md")):
            text = prompt.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)]+\.md(?:#[^)]+)?)\)", text):
                relative = target.split("#", 1)[0]
                with self.subTest(prompt=prompt.name, target=target):
                    self.assertTrue((prompt.parent / relative).resolve().is_file())

    def test_verification_routes_test_environment_resolution(self) -> None:
        prompt = (SKILLS / "agent" / "prompt" / "verification.md").read_text(
            encoding="utf-8"
        )
        testing = (SKILLS / "convention" / "references" / "testing.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("references/testing.md", prompt)
        self.assertIn("system-default", testing)
        self.assertIn("existing compatible project environment", testing)
        self.assertNotIn("python3 -m pytest", testing)
        self.assertRegex(
            testing,
            r"make no installation\s+change unless authorized",
        )

    def test_public_skills_expose_only_their_owned_scripts(self) -> None:
        expected = {
            name: ({"exec.py", "loop.py"} if name == "agent"
                   else {"catalog_documents.py", "export_documents.py",
                         "search_documents.py", "sync_documents.py"}
                   if name == "document" else set())
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
        for item in (
            "/docs/",
            "/.agent-factory/db.sqlite",
            "/.agent-factory/db.sqlite-wal",
            "/.agent-factory/agent/",
        ):
            self.assertIn(item, ignored)


if __name__ == "__main__":
    unittest.main()
