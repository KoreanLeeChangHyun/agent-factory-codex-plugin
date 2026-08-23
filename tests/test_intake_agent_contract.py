from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InquiryAgentContractTests(unittest.TestCase):
    def test_inquery_role_uses_the_temporary_inquery_workspace_contract(self) -> None:
        role = (
            ROOT / "skills" / "agent" / "references" / "inquery.md"
        ).read_text(encoding="utf-8")
        workspace = (
            ROOT / "skills" / "inquery" / "references" / "workspace.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Apply the `inquery` Skill", role)
        self.assertIn(".agent-factory/inquery/", role + workspace)
        self.assertIn("unrefined Markdown", role + workspace)
        self.assertIn("not a canonical evidence ledger", workspace)
        self.assertIn(".agent-factory/agent/", workspace)


if __name__ == "__main__":
    unittest.main()
