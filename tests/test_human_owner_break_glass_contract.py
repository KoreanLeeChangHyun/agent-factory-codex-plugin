from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HumanOwnerBreakGlassContractTests(unittest.TestCase):
    def test_main_agent_owns_bounded_break_glass_recovery(self) -> None:
        content = (
            ROOT / "skills" / "agents" / "references" / "main-agent.md"
        ).read_text(encoding="utf-8")

        for expected in (
            "`BREAK-GLASS`",
            "named project-internal recovery target",
            "bounded scope",
            "Main Agent",
            "manager-only",
            "expires automatically",
            "owning manager",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, content)

        self.assertIn("must not transfer the exception", content)
        self.assertIn("must not delay or precondition", content)

    def test_lifecycle_separates_break_glass_from_normal_flow(self) -> None:
        entry = (
            ROOT / "skills" / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text(encoding="utf-8")
        lifecycle = (
            ROOT / "skills" / "lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")

        for content in (entry, lifecycle):
            with self.subTest(document=content[:80]):
                self.assertIn("`BREAK-GLASS`", content)
                self.assertIn("normal lifecycle", content)
                self.assertIn("Main Agent", content)
                self.assertIn("Tests and verification", content)
                self.assertIn("external", content)
                self.assertIn("owning manager", content)
                self.assertIn("canonical JSON", content)

    def test_rules_do_not_infer_or_expand_break_glass_authority(self) -> None:
        facts = (
            ROOT
            / "skills"
            / "rules"
            / "references"
            / "fact-and-evidence-control.md"
        ).read_text(encoding="utf-8")
        safety = (
            ROOT / "skills" / "rules" / "references" / "change-safety.md"
        ).read_text(encoding="utf-8")

        self.assertIn("must not be promoted into break-glass authority", facts)
        self.assertIn("belongs only to the Main Agent", facts)
        for action in (
            "Deletion",
            "overwriting or replacing uncommitted work",
            "deployment",
            "restart",
            "external transmission",
        ):
            with self.subTest(action=action):
                self.assertIn(action, safety)
        self.assertIn("exact Human-requested commands", safety)


if __name__ == "__main__":
    unittest.main()
