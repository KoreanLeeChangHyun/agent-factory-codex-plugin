from __future__ import annotations

import unittest
from pathlib import Path


MAIN = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "agent"
    / "references"
    / "main.md"
)


class HumanOwnerBreakGlassContractTests(unittest.TestCase):
    def test_main_keeps_break_glass_explicit_bounded_and_expiring(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
