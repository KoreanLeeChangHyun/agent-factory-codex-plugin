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
        self.assertIn("AI-facing representation of a Specification", content)
        self.assertIn("standard Skill structure", content)
        self.assertIn("Do not automatically promote an Inquiry document", content)

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
        self.assertIn("[[SPECIFICATION TITLE]]", html)
        for element in ("<header", "<nav", "<main", "<section", "<table"):
            self.assertIn(element, html)
        for area in (
            "In scope",
            "Out of scope",
            "Accepted decisions",
            "Requirements",
            "Evidence and provenance",
            "Unresolved questions",
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


if __name__ == "__main__":
    unittest.main()
