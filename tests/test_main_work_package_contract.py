from __future__ import annotations

import unittest
from pathlib import Path


class MainAgentWorkPackageContractTest(unittest.TestCase):
    def test_main_uses_primary_workspace_for_bounded_work(self) -> None:
        content = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "agents"
            / "references"
            / "main.md"
        ).read_text(encoding="utf-8")
        self.assertIn("current Git workspace", content)
        self.assertIn("Do not create an Intake, Specification, Work Unit, branch", content)

    def test_main_routes_package_execution_and_single_review(self) -> None:
        content = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "agents"
            / "references"
            / "main.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Work Unit or Work Package", content)
        self.assertIn("Human explicitly requests", content)
        self.assertIn("opened primary Git", content)
        self.assertNotIn("work_package_integrate.py", content)


if __name__ == "__main__":
    unittest.main()
