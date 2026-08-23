from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = ROOT / "skills" / "specification"


class SpecificationDocumentContractTests(unittest.TestCase):
    def test_specification_documents_use_local_html_css_and_javascript(self) -> None:
        content = (
            SPECIFICATION / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        self.assertIn("refined HTML, CSS, and", content)
        self.assertIn("JavaScript", content)
        self.assertIn(".agent-factory/specification/", content)

    def test_project_skill_is_the_paired_ai_facing_representation(self) -> None:
        content = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        self.assertIn("AI-readable working", content)
        self.assertIn("standard Skill structure", content)
        self.assertIn("Do not automatically promote an Inquiry document", content)

    def test_project_skill_directory_roles_are_explicit(self) -> None:
        content = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        self.assertIn("one self-contained directory", content)
        self.assertIn("`agents/` contains Agent configuration as YAML files", content)
        self.assertIn("`assets/` contains reference material", content)
        self.assertIn("`references/` contains", content)
        self.assertIn("Use the `.md` extension for every reference document", content)
        self.assertIn("`scripts/` contains scripts the Agent may execute", content)

    def test_plugin_and_consumer_skill_locations_are_distinct(self) -> None:
        content = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Agent Factory plugin repository itself", content)
        self.assertIn("`<plugin-root>/skills/`", content)
        self.assertIn("every separate project that uses", content)
        self.assertIn("`<project-root>/.codex/skills/<project-skill>/`", content)
        self.assertIn("Do not create or mirror", content)

    def test_packaged_document_has_exactly_three_assets(self) -> None:
        document = SPECIFICATION / "assets" / "document"
        self.assertEqual(
            {path.name for path in document.iterdir()},
            {"index.html", "styles.css", "app.js"},
        )

    def test_packaged_document_is_local_semantic_and_grounded(self) -> None:
        html = (SPECIFICATION / "assets" / "document" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="./styles.css"', html)
        self.assertIn('src="./app.js"', html)
        self.assertIn("data-template-placeholder", html)
        self.assertIn('<html lang="ko">', html)
        self.assertIn("[[명세 제목]]", html)
        self.assertNotIn("Human", html)
        for element in ("<header", "<nav", "<main", "<section", "<table"):
            self.assertIn(element, html)
        for area in (
            "범위에 포함",
            "범위에서 제외",
            "수락된 결정",
            "요구사항",
            "근거와 출처",
            "미해결 질문",
        ):
            self.assertIn(area, html)

        self.assertNotIn('href="http://', html)
        self.assertNotIn('href="https://', html)
        self.assertNotIn('src="http://', html)
        self.assertNotIn('src="https://', html)
        self.assertNotIn('href="//', html)
        self.assertNotIn('src="//', html)

    def test_packaged_icons_are_inline_svg(self) -> None:
        html = (SPECIFICATION / "assets" / "document" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("<svg", html)
        self.assertIn('aria-hidden="true"', html)
        self.assertNotIn("<img", html)
        self.assertNotIn("icon-font", html.lower())

    def test_authoring_guidance_covers_document_contract(self) -> None:
        content = (
            SPECIFICATION / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        for required in (
            "lowercase hyphen-case",
            "copy-once",
            "never use the template to overwrite",
            "every marked template placeholder",
            "provenance",
            "Unresolved questions",
            "semantic alignment",
            "common/",
            "document-specific",
            "flexible starting point, not a rigid schema",
        ):
            self.assertIn(required, content)

    def test_primary_sidebar_is_activity_context_not_a_table_of_contents(self) -> None:
        content = (
            SPECIFICATION / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        self.assertIn("contextual companion", content)
        self.assertIn("not as a document table of contents", content)
        self.assertIn("Explorer Activity renders an Explorer tree", content)
        self.assertIn("Do not define", content)

    def test_korean_document_and_project_skill_identity_rules_are_explicit(self) -> None:
        document = (
            SPECIFICATION / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        project_skill = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Author every Human-facing Specification document in Korean", document)
        self.assertIn("Human-readable Specification", document)
        self.assertIn("AI-readable", project_skill)
        self.assertIn("`<project-root>/.codex/skills/<project-skill>/`", project_skill)
        self.assertIn("`<category>-<skill-title>`", project_skill)
        self.assertIn("Do not invent either component", project_skill)


if __name__ == "__main__":
    unittest.main()
