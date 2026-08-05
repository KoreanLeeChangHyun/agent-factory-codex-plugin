from __future__ import annotations

import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parents[1] / "skills"


class IntakeAgentContractTests(unittest.TestCase):
    def test_agents_routes_three_non_overlapping_roles(self) -> None:
        router = (SKILLS / "agents" / "SKILL.md").read_text(encoding="utf-8")
        intake = (SKILLS / "agents" / "references" / "intake-agent.md").read_text(
            encoding="utf-8"
        )
        main = (SKILLS / "agents" / "references" / "main-agent.md").read_text(
            encoding="utf-8"
        )
        workflow = (
            SKILLS / "agents" / "references" / "workflow-agent.md"
        ).read_text(encoding="utf-8")

        self.assertIn("references/intake-agent.md", router)
        self.assertIn("codex exec", intake)
        self.assertIn("intake.py", intake)
        self.assertIn("single writer", intake)
        self.assertIn("Main Agent", intake)
        self.assertIn("must not decide readiness", intake)
        self.assertNotIn("Plan -> Work -> AI Review -> Report", intake)
        self.assertIn("app_server_goal.py", workflow)
        self.assertIn("rework", main)
        self.assertIn("complete", main)

    def test_lifecycle_routes_research_without_changing_workflow_goal_contract(self) -> None:
        entry = (SKILLS / "lifecycle" / "references" / "lifecycle-entry.md").read_text(
            encoding="utf-8"
        )
        lifecycle = (SKILLS / "lifecycle" / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )
        for text in (entry, lifecycle):
            self.assertIn("Intake Agent", text)
            self.assertIn("codex exec", text)
            self.assertIn("Main Agent", text)
            self.assertIn("app_server_goal.py", text)


if __name__ == "__main__":
    unittest.main()
