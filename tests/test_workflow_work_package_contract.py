from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkReviewContractTest(unittest.TestCase):
    def test_work_and_review_are_separate_managed_roles(self) -> None:
        references = ROOT / "skills" / "agent" / "references"
        work = (references / "work.md").read_text(encoding="utf-8")
        review = (references / "review.md").read_text(encoding="utf-8")

        self.assertIn("Implement one bounded Human-requested change", work)
        self.assertIn("Independently perform a static review", review)
        self.assertIn("different managed Codex sessions", review)
        self.assertIn("Do not modify files", review)


if __name__ == "__main__":
    unittest.main()
