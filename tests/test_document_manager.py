from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "document"


class DocumentContractTests(unittest.TestCase):
    def test_specification_uses_paired_human_and_ai_representations(self) -> None:
        entry = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        document = (
            SKILL_ROOT / "references" / "specification.md"
        ).read_text(encoding="utf-8")

        self.assertIn("one semantic body", entry)
        self.assertIn("HTML", document)
        self.assertIn("CSS", document)
        self.assertIn("JavaScript", document)
        self.assertIn("Project Skill", document)
        self.assertIn("must be authored in Korean", entry)
        self.assertIn("Human-readable", document)
        self.assertIn("AI-readable", document)

    def test_workspace_projection_path_is_separate_from_document_store(self) -> None:
        combined = (SKILL_ROOT / "references" / "specification.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(".agent-factory/workspace/", combined)
        self.assertIn(".agent-factory/information/refined/human/", combined)

    def test_document_keeps_explorer_and_session_state_separate(self) -> None:
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
