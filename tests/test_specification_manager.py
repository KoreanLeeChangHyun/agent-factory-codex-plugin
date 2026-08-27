from __future__ import annotations

import re
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
        self.assertIn("must be authored in Korean", entry)
        self.assertIn("Human-readable", document)
        self.assertIn("AI-readable", project_skill)

    def test_singular_specification_collection_path_is_preserved(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                SKILL_ROOT / "references" / "specification-document.md",
                SKILL_ROOT / "references" / "project-skill.md",
            )
        )
        self.assertIn(".agent-factory/specification/", combined)
        self.assertNotIn(".agent-factory/specifications/", combined)

    def test_specification_keeps_explorer_and_session_state_separate(self) -> None:
        entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        normalized = " ".join(re.sub(r"[`*_]", "", entry).lower().split())
        self.assertRegex(
            normalized,
            r"(?=.*explorer working material)"
            r"(?=.*managed agent session state)"
            r"(?=.*separate logical roles)"
            r"(?=.*resolved stores)",
        )


if __name__ == "__main__":
    unittest.main()
