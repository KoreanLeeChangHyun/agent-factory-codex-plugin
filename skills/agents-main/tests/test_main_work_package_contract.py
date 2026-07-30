from __future__ import annotations

import unittest
from pathlib import Path


class MainAgentWorkPackageContractTest(unittest.TestCase):
    def test_main_monitors_work_unit_ack_and_final_document(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("first JSONL document", content)
        self.assertIn("immediate ACK", content)
        self.assertIn("final success or failure document", content)

    def test_main_routes_package_execution_and_single_review(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("work_package.py preflight", content)
        self.assertIn("work_package_supervisor.py", content)
        self.assertIn("one Human result review", content)
        self.assertIn("work_package_integrate.py", content)


if __name__ == "__main__":
    unittest.main()
