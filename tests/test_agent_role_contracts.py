from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills" / "agent" / "references"
MAIN = REFERENCES / "main.md"


class MainAgentContractTests(unittest.TestCase):
    def test_break_glass_is_explicit_bounded_and_expiring(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        for expected in (
            "`BREAK-GLASS`",
            "named project-internal recovery target",
            "bounded scope",
            "expires on success, failure, or inability to continue",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)

        self.assertIn("does not authorize tests", content)
        self.assertIn("external transmission", content)

    def test_routes_bounded_work_through_independent_review(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        self.assertIn("Work Agent edits the current Git workspace", content)
        self.assertIn("independent Review Agent", content)
        self.assertIn("different managed Codex session", content)
        self.assertIn("blocking findings", content)

    def test_routes_inquiry_specification_and_gather_without_promotion(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        self.assertIn("`inquery` Skill", content)
        self.assertIn("`specification` Skill", content)
        self.assertIn("`gather` Skill", content)
        self.assertIn("without treating it as trusted project truth", content)


class InquiryAgentContractTests(unittest.TestCase):
    def test_uses_the_temporary_inquery_workspace_contract(self) -> None:
        role = (REFERENCES / "inquery.md").read_text(encoding="utf-8")
        workspace = (
            ROOT / "skills" / "inquery" / "references" / "workspace.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Apply the `inquery` Skill", role)
        self.assertIn(".agent-factory/inquery/", role + workspace)
        self.assertIn("unrefined Markdown", role + workspace)
        self.assertIn("not a canonical evidence ledger", workspace)
        self.assertIn(".agent-factory/agent/", workspace)


class WorkReviewContractTests(unittest.TestCase):
    def test_work_and_review_are_separate_managed_roles(self) -> None:
        work = (REFERENCES / "work.md").read_text(encoding="utf-8")
        review = (REFERENCES / "review.md").read_text(encoding="utf-8")

        self.assertIn("Implement one bounded Human-requested change", work)
        self.assertIn("Independently perform a static review", review)
        self.assertIn("different managed Codex sessions", review)
        self.assertIn("Do not modify files", review)


if __name__ == "__main__":
    unittest.main()
