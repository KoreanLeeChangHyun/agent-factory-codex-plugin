from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills" / "agent" / "references"
MAIN = REFERENCES / "main.md"


def normalized_paragraphs(content: str) -> list[str]:
    """Preserve clause relationships while ignoring Markdown and wrapping."""
    return [
        " ".join(re.sub(r"[`*_]", "", block).lower().split())
        for block in re.split(r"\n\s*\n", content)
        if block.strip()
    ]


def assert_clause(test: unittest.TestCase, content: str, pattern: str) -> None:
    test.assertTrue(
        any(re.search(pattern, paragraph) for paragraph in normalized_paragraphs(content)),
        msg=f"missing normalized contract clause: {pattern}",
    )


class MainAgentContractTests(unittest.TestCase):
    def test_main_orchestrates_without_executable_task_work(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        assert_clause(
            self,
            content,
            r"human interface and control plane.*does not perform implementation, research, tests, verification, recovery",
        )
        assert_clause(
            self,
            content,
            r"main never runs.*verification command.*separate managed verification agent",
        )

    def test_break_glass_routes_recovery_to_a_managed_role(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        assert_clause(
            self,
            content,
            r"break-glass.*managed exec role.*never permits main to repair directly",
        )

    def test_main_conducts_interview_and_sequences_explorer(self) -> None:
        content = MAIN.read_text(encoding="utf-8")
        assert_clause(
            self,
            content,
            r"main itself uses the interview skill.*pause or sequence.*managed explorer agent.*resume the human conversation",
        )
        assert_clause(
            self,
            content,
            r"explorer.*never impersonate or interview the human",
        )


class VerificationAgentContractTests(unittest.TestCase):
    def test_requires_human_authority_and_never_edits_or_accepts(self) -> None:
        content = (REFERENCES / "verification.md").read_text(encoding="utf-8")
        assert_clause(
            self,
            content,
            r"human explicitly authorized.*human supplied a command, run that command unchanged.*smallest bounded command",
        )
        assert_clause(
            self,
            content,
            r"make no source, product, configuration.*edits.*do not repair.*approve",
        )
        assert_clause(
            self,
            content,
            r"report.*exact command, exit status.*limitations.*never claim acceptance",
        )


class ExplorerAgentContractTests(unittest.TestCase):
    def test_uses_the_temporary_explorer_workspace_contract(self) -> None:
        role = (REFERENCES / "explorer.md").read_text(encoding="utf-8")
        workspace = (
            ROOT / "skills" / "explorer" / "references" / "workspace.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "<project-root>/.agent-factory/explorer/<exploration-id>/", workspace
        )
        assert_clause(
            self,
            role,
            r"\.agent-factory/explorer/.*temporary workspace",
        )
        assert_clause(
            self,
            workspace,
            r"workspace is temporary working state, not a canonical project record",
        )
        assert_clause(
            self,
            workspace,
            r"explorer may preserve source-faithful original information.*processed information",
        )
        assert_clause(
            self,
            workspace,
            r"explorer never runs project tests.*managed verification agent",
        )


class WorkReviewContractTests(unittest.TestCase):
    def test_work_and_review_are_separate_managed_roles(self) -> None:
        work = (REFERENCES / "work.md").read_text(encoding="utf-8")
        review = (REFERENCES / "review.md").read_text(encoding="utf-8")

        assert_clause(
            self,
            work,
            r"implement one bounded human-requested change.*independent review",
        )
        assert_clause(
            self,
            work,
            r"never run a test or verification command.*human owns testing.*never authorize work agent testing",
        )
        assert_clause(
            self,
            review,
            r"work and review must use different managed codex sessions.*must not operate.*concurrently",
        )
        assert_clause(
            self,
            review,
            r"do not modify files.*do not run tests.*other verification command",
        )


if __name__ == "__main__":
    unittest.main()
