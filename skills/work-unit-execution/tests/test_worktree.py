from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree.py"


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=repo)


class WorktreeCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.assertEqual(run("git", "init", "-b", "main", str(self.repo)).returncode, 0)
        self.assertEqual(git(self.repo, "config", "user.name", "Agent Factory Test").returncode, 0)
        self.assertEqual(git(self.repo, "config", "user.email", "agent-factory@example.invalid").returncode, 0)
        (self.repo / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "tracked.txt").returncode, 0)
        self.assertEqual(git(self.repo, "commit", "-m", "baseline").returncode, 0)
        self.base_commit = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.worktree = self.root / "worktrees" / "wu-001"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, command: str, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = run(
            sys.executable,
            str(SCRIPT),
            command,
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "wu-001",
            "--branch",
            "work-unit/wu-001",
            "--path",
            str(self.worktree),
            *extra,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout must contain one JSON document: {exc}; stdout={result.stdout!r}; stderr={result.stderr!r}")
        self.assertEqual(payload["schemaVersion"], "1.0.0")
        self.assertEqual(payload["command"], command)
        return result, payload

    def prepare(self, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.cli("prepare", "--base", "main", *extra)

    def assert_error(self, result: subprocess.CompletedProcess[str], payload: dict, code: str) -> None:
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["state"], "refused")
        self.assertEqual(payload["error"]["code"], code)

    def test_invalid_repository_fails_before_mutation(self) -> None:
        missing = self.root / "missing"
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            str(missing),
            "--work-unit-id",
            "wu-001",
            "--base",
            "main",
            "--branch",
            "work-unit/wu-001",
            "--path",
            str(self.worktree),
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "invalid_repository")
        self.assertFalse(self.worktree.exists())

    def test_unresolved_base_fails_before_mutation(self) -> None:
        result, payload = self.cli("prepare", "--base", "missing-ref")
        self.assert_error(result, payload, "invalid_base_ref")
        self.assertFalse(self.worktree.exists())
        self.assertNotEqual(git(self.repo, "show-ref", "--verify", "--quiet", "refs/heads/work-unit/wu-001").returncode, 0)

    def test_invalid_branch_fails_before_mutation(self) -> None:
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "wu-001",
            "--base",
            "main",
            "--branch",
            "bad..branch",
            "--path",
            str(self.worktree),
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "invalid_branch")
        self.assertFalse(self.worktree.exists())

    def test_existing_branch_collision_fails_without_mutation(self) -> None:
        self.assertEqual(git(self.repo, "branch", "work-unit/wu-001").returncode, 0)
        result, payload = self.prepare()
        self.assert_error(result, payload, "branch_collision")
        self.assertFalse(self.worktree.exists())

    def test_existing_path_collision_fails_without_branch_creation(self) -> None:
        self.worktree.mkdir(parents=True)
        result, payload = self.prepare()
        self.assert_error(result, payload, "path_collision")
        self.assertNotEqual(git(self.repo, "show-ref", "--verify", "--quiet", "refs/heads/work-unit/wu-001").returncode, 0)

    def test_registered_worktree_collision_fails_without_target_branch_creation(self) -> None:
        self.assertEqual(
            git(
                self.repo,
                "worktree",
                "add",
                "-b",
                "work-unit/other",
                str(self.worktree),
                "main",
            ).returncode,
            0,
        )
        result, payload = self.prepare()
        self.assert_error(result, payload, "worktree_collision")
        self.assertNotEqual(git(self.repo, "show-ref", "--verify", "--quiet", "refs/heads/work-unit/wu-001").returncode, 0)

    def test_prepare_creates_and_locks_linked_worktree(self) -> None:
        result, payload = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "prepared")
        self.assertEqual(payload["context"]["repository"], str(self.repo.resolve()))
        self.assertEqual(payload["context"]["baseCommit"], self.base_commit)
        self.assertEqual(payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(payload["context"]["worktreePath"], str(self.worktree.resolve()))
        self.assertTrue(payload["context"]["locked"])
        listing = git(self.repo, "worktree", "list", "--porcelain").stdout
        self.assertIn(f"worktree {self.worktree.resolve()}", listing)
        self.assertIn("locked", listing)

    def test_worktree_add_failure_returns_canonical_json(self) -> None:
        blocked_parent = self.root / "blocked-parent"
        blocked_parent.write_text("not a directory\n", encoding="utf-8")
        self.worktree = blocked_parent / "wu-001"

        result, payload = self.prepare()

        self.assert_error(result, payload, "prepare_failed")
        self.assertEqual(payload["operations"][0]["args"][1:4], ["-C", str(self.repo), "worktree"])
        self.assertNotEqual(payload["operations"][0]["returnCode"], 0)

    def test_prepare_reuses_the_same_work_unit_branch_and_worktree_pair(self) -> None:
        first, first_payload = self.prepare()
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first_payload["state"], "prepared")
        before = git(self.repo, "worktree", "list", "--porcelain").stdout.count("worktree ")
        second, second_payload = self.prepare()
        self.assertEqual(second.returncode, 0)
        self.assertEqual(second_payload["state"], "reused")
        after = git(self.repo, "worktree", "list", "--porcelain").stdout.count("worktree ")
        self.assertEqual(before, after)
        self.assertEqual(second_payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(second_payload["context"]["worktreePath"], str(self.worktree.resolve()))

    def test_branch_must_match_deterministic_work_unit_pattern(self) -> None:
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "wu-001",
            "--base",
            "main",
            "--branch",
            "topic/wu-001",
            "--path",
            str(self.worktree),
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "branch_derivation_mismatch")
        self.assertFalse(self.worktree.exists())

    def test_prepare_derives_branch_when_branch_argument_is_omitted(self) -> None:
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "wu-001",
            "--base",
            "main",
            "--path",
            str(self.worktree),
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(payload["context"]["workUnitId"], "wu-001")

    def test_inspect_reports_clean_and_dirty_states(self) -> None:
        self.prepare()
        result, payload = self.cli("inspect")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["state"], "clean")
        self.assertFalse(payload["context"]["dirty"])
        (self.worktree / "untracked file.txt").write_text("dirty\n", encoding="utf-8")
        result, payload = self.cli("inspect")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["state"], "dirty")
        self.assertTrue(payload["context"]["dirty"])
        self.assertEqual(payload["context"]["changes"][0]["path"], "untracked file.txt")

    def test_inspect_rejects_repository_mismatch(self) -> None:
        self.prepare()
        other = self.root / "other"
        other.mkdir()
        self.assertEqual(run("git", "init", "-b", "main", str(other)).returncode, 0)
        result = run(
            sys.executable,
            str(SCRIPT),
            "inspect",
            "--repository",
            str(other),
            "--work-unit-id",
            "wu-001",
            "--branch",
            "work-unit/wu-001",
            "--path",
            str(self.worktree),
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "repository_mismatch")

    def test_cleanup_requires_explicit_human_decision(self) -> None:
        self.prepare()
        result, payload = self.cli("cleanup")
        self.assert_error(result, payload, "missing_human_decision")
        self.assertTrue(self.worktree.exists())

    def test_cleanup_refuses_dirty_worktree(self) -> None:
        self.prepare()
        (self.worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result, payload = self.cli("cleanup", "--human-decision", "approved")
        self.assert_error(result, payload, "dirty_worktree")
        self.assertTrue(self.worktree.exists())

    def test_cleanup_removes_clean_worktree_without_deleting_branch(self) -> None:
        self.prepare()
        result, payload = self.cli("cleanup", "--human-decision", "approved")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "cleaned")
        self.assertFalse(self.worktree.exists())
        self.assertEqual(git(self.repo, "show-ref", "--verify", "--quiet", "refs/heads/work-unit/wu-001").returncode, 0)
        self.assertTrue(payload["context"]["branchRetained"])

    def test_shell_metacharacters_are_not_executed(self) -> None:
        marker = self.root / "should-not-exist"
        malicious_ref = f"main;touch {marker}"
        result, payload = self.cli("prepare", "--base", malicious_ref)
        self.assert_error(result, payload, "invalid_base_ref")
        self.assertFalse(marker.exists())

    def test_failure_output_is_deterministic_json(self) -> None:
        first, first_payload = self.cli("prepare", "--base", "missing-ref")
        second, second_payload = self.cli("prepare", "--base", "missing-ref")
        self.assertEqual(first.returncode, second.returncode)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first_payload, second_payload)

    def test_source_has_no_unsafe_git_flags_or_shell_invocation(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ('"--force"', '"-B"', '"-D"', "shell=True", "os.system("):
            self.assertNotIn(forbidden, source)

    def test_relative_repository_and_worktree_paths_are_rejected(self) -> None:
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            "relative-repo",
            "--work-unit-id",
            "wu-001",
            "--base",
            "main",
            "--branch",
            "work-unit/wu-001",
            "--path",
            "relative-worktree",
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "path_not_absolute")


if __name__ == "__main__":
    unittest.main()
