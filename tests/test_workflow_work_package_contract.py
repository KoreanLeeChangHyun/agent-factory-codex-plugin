from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowAgentWorkPackageContractTest(unittest.TestCase):
    def test_workflow_agent_defers_sequential_package_scheduling(self) -> None:
        content = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "agents"
            / "references"
            / "workflow-agent.md"
        ).read_text(encoding="utf-8")
        self.assertIn("recorded primary workspace", content)
        self.assertIn("runs nodes sequentially", content)
        self.assertIn("do not merge", content)
        self.assertIn("deterministic", content)


if __name__ == "__main__":
    unittest.main()
