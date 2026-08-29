from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "skills" / "agent" / "prompt"
SKILL = ROOT / "skills" / "agent" / "SKILL.md"
MAIN = PROMPTS / "main.md"
WORK = PROMPTS / "work.md"
VERIFICATION = PROMPTS / "verification.md"


def normalized(content: str) -> str:
    return " ".join(re.sub(r"[`*_]", "", content).lower().split())


class ThreeRoleGraphContractTests(unittest.TestCase):
    def test_exact_prompt_set_is_main_work_verification(self) -> None:
        self.assertEqual(
            {path.name for path in PROMPTS.glob("*.md")},
            {"main.md", "work.md", "verification.md"},
        )

    def test_main_owns_the_exact_graph_and_does_not_execute_child_roles(self) -> None:
        main = normalized(MAIN.read_text(encoding="utf-8"))
        self.assertIn("main -> work -> verification", main)
        self.assertIn("pass -> end", main)
        self.assertIn("human skip -> end", main)
        self.assertRegex(main, r"on fail.*same work agent.*same verification agent")
        self.assertRegex(main, r"on pass.*final result")
        self.assertRegex(main, r"record intent to skip at any time before the next verification starts")
        self.assertRegex(main, r"control-plane intent, not a graph transition")
        self.assertRegex(main, r"after the current initial or revision work turn completes.*prevent the next or an additional verification run")
        self.assertIn("do not perform work or verification directly", main)
        self.assertIn("do not add another agent role, node, or route", main)
        self.assertRegex(main, r"continue receiving human messages.*work and verification run")
        self.assertRegex(main, r"preserve the active agent session and run identities")
        self.assertRegex(main, r"do not omit, implicitly cancel, or abandon earlier work")
        self.assertRegex(main, r"explicitly redirects.*preserve existing execution and result state")

    def test_work_executes_and_never_verifies_or_coordinates(self) -> None:
        work = normalized(WORK.read_text(encoding="utf-8"))
        self.assertIn("perform the bounded task delegated by main", work)
        self.assertRegex(work, r"when verification returns fail.*address its findings")
        self.assertIn("do not verify your own work", work)
        self.assertIn("do not coordinate another agent", work)

    def test_verification_returns_pass_or_fail_without_repairing(self) -> None:
        verification = normalized(VERIFICATION.read_text(encoding="utf-8"))
        self.assertIn("return exactly one decision: pass or fail", verification)
        self.assertRegex(verification, r"return fail.*actionable correction findings")
        self.assertRegex(verification, r"return pass only when no finding remains")
        self.assertIn("do not edit or repair project files", verification)
        self.assertIn("do not coordinate another agent or add a new graph route", verification)

    def test_role_prompt_transport_and_main_hosts_do_not_add_nodes(self) -> None:
        skill = normalized(SKILL.read_text(encoding="utf-8"))
        self.assertIn("tagged role-instruction block", skill)
        self.assertIn("does not claim a separate platform system-channel message", skill)
        self.assertRegex(skill, r"codex cli.*exec-hosted session.*vs code extension")
        self.assertIn("hosts, not additional agent roles", skill)


if __name__ == "__main__":
    unittest.main()
