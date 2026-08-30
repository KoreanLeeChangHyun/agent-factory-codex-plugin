from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class PublicSkillResourceContractTests(unittest.TestCase):
    def test_current_skills_expose_their_public_scripts(self) -> None:
        agent_scripts = SKILLS / "agent" / "scripts"
        self.assertEqual(
            {path.name for path in agent_scripts.glob("*.py")},
            {"exec.py", "loop.py"},
        )

        gather_scripts = SKILLS / "gather" / "scripts"
        self.assertEqual(
            {path.name for path in gather_scripts.glob("*.py")},
            {
                "provider_support.py",
                "sync.py",
                "sync_discord.py",
                "sync_gmail.py",
                "sync_google_drive.py",
                "sync_notion.py",
                "sync_onedrive.py",
                "sync_slack.py",
            },
        )

        document_scripts = SKILLS / "document" / "scripts"
        self.assertEqual(
            {path.name for path in document_scripts.glob("*.py")},
            set(),
        )

        workspace_scripts = SKILLS / "workspace" / "scripts"
        self.assertEqual(
            {path.name for path in workspace_scripts.glob("*.py")},
            {"serve.py"},
        )

        convention_scripts = SKILLS / "convention" / "scripts"
        self.assertEqual(
            {path.name for path in convention_scripts.glob("*.py")},
            {"init_agents.py"},
        )

        for name in ("explorer", "interview"):
            with self.subTest(skill=name):
                self.assertFalse((SKILLS / name / "scripts").exists())

    def test_gather_keeps_existing_sync_schema_and_configuration_identity(self) -> None:
        schema = SKILLS / "gather" / "assets" / "schema" / "sync.schema.json"
        management = (
            SKILLS / "gather" / "references" / "gather-management.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(schema.is_file())
        self.assertIn(".agent-factory/sync.json", management)
        self.assertIn("google-drive", management)
        self.assertIn("google-mail", management)


if __name__ == "__main__":
    unittest.main()
