from __future__ import annotations

import unittest
from pathlib import Path


class WorkflowAgentWorkPackageContractTest(unittest.TestCase):
    def test_workflow_agent_defers_scheduling_and_integration(self) -> None:
        content = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "agents"
            / "references"
            / "workflow-agent.md"
        ).read_text(encoding="utf-8")
        self.assertIn("scheduler-prepared worktree", content)
        self.assertIn("do not ask for", content)
        self.assertIn("do not integrate its branch", content)
        self.assertIn("deterministic", content)


if __name__ == "__main__":
    unittest.main()
