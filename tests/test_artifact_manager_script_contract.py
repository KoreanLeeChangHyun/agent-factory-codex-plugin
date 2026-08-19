from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


class PublicSkillResourceContractTests(unittest.TestCase):
    def test_only_agent_and_gather_ship_executable_managers(self) -> None:
        self.assertTrue((SKILLS / "agent" / "scripts" / "agent_exec.py").is_file())
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync.py").is_file())
        self.assertTrue((SKILLS / "gather" / "scripts" / "sync_gmail.py").is_file())

        for name in ("convention", "inquery", "specification"):
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
