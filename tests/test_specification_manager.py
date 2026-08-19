from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "specification"


class SpecificationContractTests(unittest.TestCase):
    def test_specification_uses_paired_human_and_ai_representations(self) -> None:
        entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        document = (
            SKILL_ROOT / "references" / "specification-document.md"
        ).read_text(encoding="utf-8")
        project_skill = (
            SKILL_ROOT / "references" / "project-skill.md"
        ).read_text(encoding="utf-8")

        self.assertIn("one refined body of project knowledge", entry)
        self.assertIn("HTML", document)
        self.assertIn("CSS", document)
        self.assertIn("JavaScript", document)
        self.assertIn("Project Skill", project_skill)

    def test_plural_specification_collection_path_is_preserved(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                SKILL_ROOT / "references" / "specification-document.md",
                SKILL_ROOT / "references" / "project-skill.md",
            )
        )
        self.assertIn(".agent-factory/specifications/", combined)

    def test_specification_keeps_inquiry_and_session_state_separate(self) -> None:
        entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Inquiry working material", entry)
        self.assertIn("managed Agent session state", entry)
        self.assertIn("separate locations", entry)


if __name__ == "__main__":
    unittest.main()
