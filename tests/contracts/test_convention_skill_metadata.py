from __future__ import annotations

import json
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

    def test_plugin_guidance_excludes_mcp_implementation_inventory(self) -> None:
        paths = [
            ROOT / "README.md",
            SKILLS / "convention" / "references" / "agent-factory-core.md",
            SKILLS / "convention" / "references" / "directory-structure.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        forbidden = {
            "agent-factory://",
            "document_import",
            "document_prepare_upload",
            "reporting_write",
            "PostgreSQL stores tenant metadata",
            "object storage stores immutable Document bytes",
            "static/workspace/",
            "FastAPI host",
            "작업 표시줄 → 기본 사이드바",
        }
        for detail in sorted(forbidden):
            with self.subTest(detail=detail):
                self.assertNotIn(detail, text)
        self.assertIn("advertised authenticated", text)
        self.assertIn("Document, Gather, Tool and Workspace", text)

    def test_standalone_and_optional_integration_contracts_are_explicit(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agent = (SKILLS / "agent" / "SKILL.md").read_text(encoding="utf-8")
        convention = (SKILLS / "convention" / "SKILL.md").read_text(encoding="utf-8")
        layout = (
            SKILLS / "convention" / "references" / "directory-structure.md"
        ).read_text(encoding="utf-8")
        documents = (
            SKILLS / "convention" / "references" / "documents.md"
        ).read_text(encoding="utf-8")
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

        for mode in ("Plugin only", "MCP only", "Plugin plus MCP"):
            self.assertIn(mode, readme)
        plugin_only = re.search(
            r"(?ms)^- \*\*Plugin only:\*\*\s*(.+?)(?=^- \*\*MCP only:\*\*)",
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
            "without an MCP package, server, account, tenant, connection",
            " ".join(agent.split()),
        )
        manifest_description = manifest["interface"]["longDescription"]
        self.assertRegex(
            manifest_description,
            r"\bcomplete local\b.*Main -> Work -> Verification",
        )
        self.assertRegex(manifest_description, r"\bNo MCP package\b")
        for dependency in (
            "server", "account", "tenant", "connection", "authenticated resource"
        ):
            with self.subTest(manifest_dependency=dependency):
                self.assertIn(dependency, manifest_description)
        self.assertIn("absence of MCP is a normal supported mode", convention)
        for document_type in ("original", "processed", "specification"):
            self.assertIn(
                f"<project-root>/docs/{document_type}/<category>-<name>/", layout
            )
        self.assertIn("not an error fallback", layout)
        self.assertNotIn("docs/<category>-<name>.html", documents)
        self.assertIn(
            "docs/specification/<category>-<name>/index.html", documents
        )
        for clause_id in (
            "specification.routing.canonical",
            "specification.sync.local-transaction",
            "document.future-mcp.cutover",
            "document.future-mcp.dual-storage",
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

    def test_document_package_and_future_cutover_contract(self) -> None:
        documents = (
            SKILLS / "convention" / "references" / "documents.md"
        ).read_text(encoding="utf-8")
        normalized_documents = " ".join(documents.split())
        dual_storage = documents.split("#### Dual-storage mode", 1)[1].split(
            "\n## Formats", 1
        )[0]
        normalized_dual_storage = " ".join(dual_storage.split())
        asset = (SKILLS / "convention" / "assets" / "AGENTS.md").read_text(
            encoding="utf-8"
        )

        for document_type in ("original", "processed", "specification"):
            root = f"<project-root>/docs/{document_type}/<category>-<name>/"
            self.assertIn(root, documents)
        for detail in (
            "source identity",
            "provenance",
            "fidelity",
            "locators",
            "whether source content is stored",
            "only when the Human explicitly requests it",
            "Every AI-generated durable Document is Processed by default",
            "open-ended",
            "`interview`",
            "`research`",
            "`analysis`",
            "does not yet exist",
            "stable idempotency identifiers",
            "receiver acknowledgements",
            "complete bounded inventory",
            "no automatic deletion",
            "fails closed",
            "explicitly requests both canonical local storage and the future cloud",
            "first mutate the authoritative MCP Document",
            "expected revision/CAS and idempotency contract",
            "fetch the committed MCP revision",
            "never independently from proposed input",
            "Never write local first",
            "concurrent bidirectional writes",
            "silently merge divergent local and MCP state",
            "outcome is ambiguous, do not mutate the local projection",
            "local is explicitly stale and pending retry",
            "without replaying the MCP mutation",
            "existing atomic pair transaction and shared semantic metadata",
            "re-projects that confirmed MCP state to local",
            "Conflicting pre-existing MCP and local revisions require Human resolution",
            "never choose authority by timestamps",
            "dual-storage execution path are not currently implemented",
        ):
            with self.subTest(detail=detail):
                self.assertIn(detail, normalized_documents)
        self.assertIn(
            "Only after its acknowledgement succeeds, fetch the committed MCP revision",
            normalized_dual_storage,
        )
        self.assertIn(
            "limited to `info-*`, `rule-*`, and `design-*`",
            normalized_documents,
        )
        self.assertIn("<plugin-root>/skills/", normalized_documents)
        self.assertIn("Do not create parallel Provider", normalized_documents)
        self.assertIn("docs/specification/<category>-<name>/index.html", asset)

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
        for item in (
            "/docs/",
            "/.agent-factory/db.sqlite",
            "/.agent-factory/db.sqlite-wal",
            "/.agent-factory/agent/",
        ):
            self.assertIn(item, ignored)


if __name__ == "__main__":
    unittest.main()
