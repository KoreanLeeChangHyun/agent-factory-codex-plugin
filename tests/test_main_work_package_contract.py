from __future__ import annotations

import unittest
from pathlib import Path


MAIN = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent"
    / "references"
    / "main.md"
)


class MainAgentContractTest(unittest.TestCase):
    def test_main_routes_bounded_work_through_independent_review(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        self.assertIn("Work Agent edits the current Git workspace", content)
        self.assertIn("independent Review Agent", content)
        self.assertIn("different managed Codex session", content)
        self.assertIn("blocking findings", content)

    def test_main_routes_inquiry_specification_and_gather_without_promotion(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        self.assertIn("`inquery` Skill", content)
        self.assertIn("`specification` Skill", content)
        self.assertIn("`gather` Skill", content)
        self.assertIn("without treating it as trusted project truth", content)


if __name__ == "__main__":
    unittest.main()
