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
        self.assertIn(".agent-factory/specifications/", content)

    def test_project_skill_is_the_paired_ai_facing_representation(self) -> None:
        content = (
            SPECIFICATION / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")
        self.assertIn("AI-facing representation of a Specification", content)
        self.assertIn("standard Skill structure", content)
        self.assertIn("Do not automatically promote an Inquiry document", content)


if __name__ == "__main__":
    unittest.main()
