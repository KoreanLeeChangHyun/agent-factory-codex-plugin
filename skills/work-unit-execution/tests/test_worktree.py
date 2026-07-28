from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "worktree.py"
PLANNER_TEST = (
    Path(__file__).resolve().parents[2]
    / "work-unit-planner"
    / "tests"
    / "test_work_unit_manager.py"
)


def load_planner_test_helpers():
    spec = importlib.util.spec_from_file_location("planner_test_helpers", PLANNER_TEST)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Unit test helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_worktree_module():
    module_name = "worktree_script"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load worktree script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


helpers = load_planner_test_helpers()


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
    @classmethod
    def setUpClass(cls) -> None:
        cls.template_temp = tempfile.TemporaryDirectory()
        cls.template_repo = Path(cls.template_temp.name) / "template"
        cls.template_repo.mkdir()
        run("git", "init", "-b", "main", str(cls.template_repo))
        run("git", "config", "user.name", "Agent Factory Test", cwd=cls.template_repo)
        run(
            "git",
            "config",
            "user.email",
            "agent-factory@example.invalid",
            cwd=cls.template_repo,
        )
        (cls.template_repo / "tracked.txt").write_text(
            "baseline\n", encoding="utf-8"
        )
        (cls.template_repo / ".gitignore").write_text(
            "/.agent-factory/worktree/\n", encoding="utf-8"
        )
        run("git", "add", "tracked.txt", ".gitignore", cwd=cls.template_repo)
        run("git", "commit", "-m", "baseline", cwd=cls.template_repo)
        intake = helpers.create_ready_intake(cls.template_repo)
        package = helpers.create_package(cls.template_repo, "wu-001")
        helpers.populate_ready_candidate(cls.template_repo, package, intake)
        helpers.run_cli("transition", str(package), "ready")
        shutil.rmtree(cls.template_repo / ".agent-factory" / "worktree")
        run("git", "add", ".agent-factory", cwd=cls.template_repo)
        run("git", "commit", "-m", "ready work unit fixture", cwd=cls.template_repo)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.template_temp.cleanup()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.assertEqual(
            run("git", "clone", "-q", str(self.template_repo), str(self.repo)).returncode,
            0,
        )
        self.assertEqual(
            git(self.repo, "config", "user.name", "Agent Factory Test").returncode, 0
        )
        self.assertEqual(
            git(
                self.repo, "config", "user.email", "agent-factory@example.invalid"
            ).returncode,
            0,
        )
        context_path = (
            self.repo
            / ".agent-factory"
            / "work-units"
            / "wu-001"
            / "data"
            / "sections"
            / "execution-context.json"
        )
        context_section = json.loads(context_path.read_text(encoding="utf-8"))
        context = next(
            item
            for item in context_section["content"]
            if item["kind"] == "execution-context"
        )["content"]
        context["repository"] = str(self.repo)
        context["execInvocation"] = (
            "python3 skills/work-unit-execution/scripts/app_server_goal.py "
            f"--repository {self.repo} --work-unit-id wu-001"
        )
        context["worktreePath"] = str(
            self.repo / ".agent-factory" / "worktree" / "wu-001"
        )
        context_path.write_text(
            json.dumps(context_section, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(git(self.repo, "add", str(context_path)).returncode, 0)
        self.assertEqual(
            git(self.repo, "commit", "-m", "bind test execution context").returncode,
            0,
        )
        self.base_commit = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.worktree = self.repo / ".agent-factory" / "worktree" / "wu-001"
        self.legacy_worktree = self.root / "worktrees" / "wu-001"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(
        self, command: str, *extra: str, path: Path | str | None = None
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        arguments = [
            sys.executable,
            str(SCRIPT),
            command,
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "wu-001",
            "--branch",
            "work-unit/wu-001",
        ]
        if path is not None:
            arguments.extend(["--path", str(path)])
        arguments.extend(extra)
        result = run(
            *arguments,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"stdout must contain one JSON document: {exc}; stdout={result.stdout!r}; stderr={result.stderr!r}"
            )
        self.assertEqual(payload["schemaVersion"], "1.0.0")
        self.assertEqual(payload["command"], command)
        return result, payload

    def prepare(self, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.cli("prepare", "--base", "main", *extra)

    def commit_source(self, content: str = "source\n") -> str:
        (self.worktree / "source.txt").write_text(content, encoding="utf-8")
        self.assertEqual(git(self.worktree, "add", "source.txt").returncode, 0)
        self.assertEqual(
            git(self.worktree, "commit", "-m", "source change").returncode, 0
        )
        return git(self.worktree, "rev-parse", "HEAD").stdout.strip()

    def integrate(self, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.cli("integrate", "--target-branch", "main", *extra)

    def assert_error(
        self, result: subprocess.CompletedProcess[str], payload: dict, code: str
    ) -> None:
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
        self.assertNotEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/wu-001",
            ).returncode,
            0,
        )

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
        self.assertNotEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/wu-001",
            ).returncode,
            0,
        )

    def test_registered_worktree_collision_fails_without_target_branch_creation(
        self,
    ) -> None:
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
        self.assertNotEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/wu-001",
            ).returncode,
            0,
        )

    def test_prepare_creates_and_locks_linked_worktree(self) -> None:
        result, payload = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "prepared")
        self.assertEqual(payload["context"]["repository"], str(self.repo.resolve()))
        self.assertEqual(payload["context"]["baseCommit"], self.base_commit)
        self.assertEqual(payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(
            payload["context"]["worktreePath"], str(self.worktree.resolve())
        )
        self.assertTrue(payload["context"]["locked"])
        listing = git(self.repo, "worktree", "list", "--porcelain").stdout
        self.assertIn(f"worktree {self.worktree.resolve()}", listing)
        self.assertIn("locked", listing)
        self.assertFalse((self.worktree / ".agent-factory").exists())
        self.assertEqual(git(self.repo, "status", "--short").stdout, "")

    def test_prepare_accepts_explicit_source_commit_after_main_advances(self) -> None:
        source_commit = self.base_commit
        (self.repo / "unrelated.txt").write_text("later\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "unrelated.txt").returncode, 0)
        self.assertEqual(
            git(self.repo, "commit", "-m", "advance main without package").returncode,
            0,
        )

        result, payload = self.cli("prepare", "--base", source_commit)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["baseCommit"], source_commit)
        self.assertEqual(payload["context"]["admission"]["baseRef"], "main")
        self.assertEqual(
            payload["context"]["admission"]["executionCommit"], source_commit
        )

    def test_prepare_accepts_current_symbolic_base_without_artifact_checkpoint(self) -> None:
        (self.repo / "unrelated.txt").write_text("later\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "unrelated.txt").returncode, 0)
        self.assertEqual(
            git(self.repo, "commit", "-m", "advance main without package").returncode,
            0,
        )

        result, payload = self.prepare()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["context"]["admission"]["executionCommit"],
            git(self.repo, "rev-parse", "main").stdout.strip(),
        )

    def test_prepare_refuses_missing_work_unit_before_git_mutation(self) -> None:
        result = run(
            sys.executable,
            str(SCRIPT),
            "prepare",
            "--repository",
            str(self.repo),
            "--work-unit-id",
            "missing-unit",
            "--base",
            "main",
        )
        payload = json.loads(result.stdout)
        self.assert_error(result, payload, "work_unit_admission_refused")
        self.assertFalse(
            (self.repo / ".agent-factory" / "worktree" / "missing-unit").exists()
        )
        self.assertNotEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/missing-unit",
            ).returncode,
            0,
        )

    def test_prepare_refuses_non_ready_package_before_git_mutation(self) -> None:
        metadata_path = (
            self.repo
            / ".agent-factory"
            / "work-units"
            / "wu-001"
            / "data"
            / "metadata.json"
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["lifecycle"]["status"] = "backlog"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        git(self.repo, "add", str(metadata_path))
        git(self.repo, "commit", "-m", "make work unit non-ready")
        result, payload = self.prepare()
        self.assert_error(result, payload, "work_unit_admission_refused")
        self.assertFalse(self.worktree.exists())
        self.assertNotEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/wu-001",
            ).returncode,
            0,
        )

    def test_prepare_accepts_explicit_canonical_path_assertion(self) -> None:
        result, payload = self.cli("prepare", "--base", "main", path=self.worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            payload["context"]["worktreePath"], str(self.worktree.resolve())
        )

    def test_prepare_rejects_new_noncanonical_path(self) -> None:
        result, payload = self.cli(
            "prepare", "--base", "main", path=self.legacy_worktree
        )
        self.assert_error(result, payload, "noncanonical_worktree_path")
        self.assertFalse(self.legacy_worktree.exists())

    def test_prepare_reuses_registered_legacy_path(self) -> None:
        context_path = (
            self.repo
            / ".agent-factory"
            / "work-units"
            / "wu-001"
            / "data"
            / "sections"
            / "execution-context.json"
        )
        section = json.loads(context_path.read_text(encoding="utf-8"))
        context = next(
            item
            for item in section["content"]
            if item["kind"] == "execution-context"
        )["content"]
        context["worktreePath"] = str(self.legacy_worktree)
        context_path.write_text(
            json.dumps(section, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        git(self.repo, "add", str(context_path))
        git(self.repo, "commit", "-m", "record legacy worktree")
        self.assertEqual(
            git(
                self.repo,
                "worktree",
                "add",
                "-b",
                "work-unit/wu-001",
                str(self.legacy_worktree),
                "main",
            ).returncode,
            0,
        )

        result, payload = self.cli(
            "prepare", "--base", "main", path=self.legacy_worktree
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["state"], "reused")
        self.assertEqual(
            payload["context"]["worktreePath"], str(self.legacy_worktree.resolve())
        )
        self.assertTrue(payload["context"]["locked"])

    def test_worktree_add_failure_returns_canonical_json(self) -> None:
        (self.repo / ".agent-factory" / "worktree").write_text(
            "not a directory\n", encoding="utf-8"
        )

        result, payload = self.prepare()

        self.assert_error(result, payload, "prepare_failed")
        self.assertEqual(
            payload["operations"][0]["args"][1:4], ["-C", str(self.repo), "worktree"]
        )
        self.assertNotEqual(payload["operations"][0]["returnCode"], 0)

    def test_prepare_reuses_the_same_work_unit_branch_and_worktree_pair(self) -> None:
        first, first_payload = self.prepare()
        self.assertEqual(first.returncode, 0)
        self.assertEqual(first_payload["state"], "prepared")
        before = git(self.repo, "worktree", "list", "--porcelain").stdout.count(
            "worktree "
        )
        second, second_payload = self.prepare()
        self.assertEqual(second.returncode, 0)
        self.assertEqual(second_payload["state"], "reused")
        after = git(self.repo, "worktree", "list", "--porcelain").stdout.count(
            "worktree "
        )
        self.assertEqual(before, after)
        self.assertEqual(second_payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(
            second_payload["context"]["worktreePath"], str(self.worktree.resolve())
        )

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
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["branch"], "work-unit/wu-001")
        self.assertEqual(payload["context"]["workUnitId"], "wu-001")
        self.assertEqual(
            payload["context"]["worktreePath"], str(self.worktree.resolve())
        )

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

    def test_cleanup_requires_no_approval_argument(self) -> None:
        self.prepare()
        result, payload = self.cli("cleanup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["state"], "cleaned")
        self.assertFalse(self.worktree.exists())

    def test_cleanup_refuses_dirty_worktree(self) -> None:
        self.prepare()
        (self.worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result, payload = self.cli("cleanup")
        self.assert_error(result, payload, "dirty_worktree")
        self.assertTrue(self.worktree.exists())

    def test_cleanup_removes_clean_worktree_without_deleting_branch(self) -> None:
        self.prepare()
        result, payload = self.cli("cleanup")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "cleaned")
        self.assertFalse(self.worktree.exists())
        self.assertEqual(
            git(
                self.repo,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/work-unit/wu-001",
            ).returncode,
            0,
        )
        self.assertTrue(payload["context"]["branchRetained"])

    def test_batch_cleanup_preflights_done_units_and_removes_clean_worktrees(
        self,
    ) -> None:
        self.prepare()
        module = load_worktree_module()
        manager = self.root / "fake-completed-manager"
        manager.write_text(
            textwrap.dedent(
                f"""\
                #!/usr/bin/env python3
                import json
                import sys

                if sys.argv[1] == "validate":
                    print(json.dumps({{"valid": True, "status": "done"}}))
                else:
                    print(json.dumps({{
                        "content": [{{
                            "kind": "execution-context",
                            "content": {{
                                "executionMode": "worktree",
                                "repository": {str(self.repo)!r},
                                "branch": "work-unit/wu-001",
                                "worktreePath": {str(self.worktree)!r}
                            }}
                        }}]
                    }}))
                """
            ),
            encoding="utf-8",
        )
        manager.chmod(0o755)
        module.WORK_UNIT_MANAGER = manager
        execution = module.Execution("cleanup-completed")

        payload = module.cleanup_completed(
            execution,
            argparse.Namespace(
                repository=str(self.repo),
                work_unit_id=["wu-001"],
            ),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state"], "cleaned")
        self.assertFalse(self.worktree.exists())
        self.assertEqual(
            payload["context"]["results"][0]["workUnitId"], "wu-001"
        )

    def test_integrate_requires_no_approval_argument(self) -> None:
        self.prepare()
        self.commit_source()
        target_before = git(self.repo, "rev-parse", "main").stdout.strip()

        result, payload = self.integrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["targetBeforeCommit"], target_before)

    def test_integrate_fast_forwards_and_returns_complete_receipt(self) -> None:
        self.prepare()
        source_commit = self.commit_source()
        target_before = git(self.repo, "rev-parse", "main").stdout.strip()

        result, payload = self.integrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["state"], "integrated")
        context = payload["context"]
        self.assertEqual(context["workUnitId"], "wu-001")
        self.assertEqual(context["repository"], str(self.repo.resolve()))
        self.assertEqual(context["sourceBranch"], "work-unit/wu-001")
        self.assertEqual(context["targetBranch"], "main")
        self.assertEqual(context["worktreePath"], str(self.worktree.resolve()))
        self.assertEqual(context["sourceCommit"], source_commit)
        self.assertEqual(context["targetBeforeCommit"], target_before)
        self.assertEqual(context["targetAfterCommit"], source_commit)
        self.assertEqual(context["relationship"], "fast-forwardable")
        self.assertEqual(context["strategy"], "ff-only")
        self.assertEqual(context["operationResult"], "fast-forwarded")
        self.assertEqual(
            git(self.repo, "rev-parse", "main").stdout.strip(), source_commit
        )
        self.assertTrue(self.worktree.exists())
        self.assertIn(
            "locked", git(self.repo, "worktree", "list", "--porcelain").stdout
        )

    def test_integrate_diverged_requires_explicit_no_ff_strategy(self) -> None:
        self.prepare()
        source_commit = self.commit_source()
        (self.repo / "target.txt").write_text("target\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "target.txt").returncode, 0)
        self.assertEqual(git(self.repo, "commit", "-m", "target change").returncode, 0)
        target_before = git(self.repo, "rev-parse", "main").stdout.strip()

        refused, refused_payload = self.integrate()
        self.assert_error(refused, refused_payload, "diverged_strategy_required")
        self.assertEqual(
            git(self.repo, "rev-parse", "main").stdout.strip(), target_before
        )

        result, payload = self.integrate("--strategy", "no-ff")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["relationship"], "diverged")
        self.assertEqual(payload["context"]["strategy"], "no-ff")
        self.assertEqual(payload["context"]["operationResult"], "merge-commit-created")
        target_after = payload["context"]["targetAfterCommit"]
        parents = git(
            self.repo, "show", "-s", "--format=%P", target_after
        ).stdout.split()
        self.assertEqual(parents, [target_before, source_commit])

    def test_integrate_conflict_returns_json_and_restores_clean_target(self) -> None:
        self.prepare()
        (self.worktree / "tracked.txt").write_text("source\n", encoding="utf-8")
        self.assertEqual(git(self.worktree, "add", "tracked.txt").returncode, 0)
        self.assertEqual(
            git(self.worktree, "commit", "-m", "source conflict").returncode, 0
        )
        (self.repo / "tracked.txt").write_text("target\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "tracked.txt").returncode, 0)
        self.assertEqual(
            git(self.repo, "commit", "-m", "target conflict").returncode, 0
        )
        target_before = git(self.repo, "rev-parse", "main").stdout.strip()

        result, payload = self.integrate("--strategy", "no-ff")

        self.assert_error(result, payload, "integration_failed")
        self.assertEqual(
            git(self.repo, "rev-parse", "main").stdout.strip(), target_before
        )
        self.assertEqual(git(self.repo, "status", "--short").stdout, "")
        self.assertEqual(len(payload["operations"]), 2)
        self.assertEqual(payload["operations"][1]["args"][-2:], ["merge", "--abort"])
        self.assertEqual(payload["operations"][1]["returnCode"], 0)

    def test_integrate_recovers_already_merged_without_duplicate_mutation(self) -> None:
        self.prepare()
        source_commit = self.commit_source()
        first, _ = self.integrate()
        self.assertEqual(first.returncode, 0)

        second, payload = self.integrate()

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(payload["state"], "already-merged")
        self.assertEqual(payload["context"]["relationship"], "already-merged")
        self.assertEqual(payload["context"]["operationResult"], "already-merged")
        self.assertEqual(payload["context"]["sourceCommit"], source_commit)
        self.assertEqual(payload["context"]["targetBeforeCommit"], source_commit)
        self.assertEqual(payload["context"]["targetAfterCommit"], source_commit)
        self.assertEqual(payload["operations"], [])

    def test_integrate_recovers_diverged_no_ff_with_the_same_command(self) -> None:
        self.prepare()
        source_commit = self.commit_source()
        (self.repo / "target.txt").write_text("target\n", encoding="utf-8")
        self.assertEqual(git(self.repo, "add", "target.txt").returncode, 0)
        self.assertEqual(git(self.repo, "commit", "-m", "target change").returncode, 0)
        first, first_payload = self.integrate("--strategy", "no-ff")
        self.assertEqual(first.returncode, 0, first.stderr)
        target_after = first_payload["context"]["targetAfterCommit"]

        second, payload = self.integrate("--strategy", "no-ff")

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(payload["state"], "already-merged")
        self.assertEqual(payload["context"]["relationship"], "already-merged")
        self.assertEqual(payload["context"]["strategy"], "no-ff")
        self.assertEqual(payload["context"]["sourceCommit"], source_commit)
        self.assertEqual(payload["context"]["targetBeforeCommit"], target_after)
        self.assertEqual(payload["context"]["targetAfterCommit"], target_after)
        self.assertEqual(payload["operations"], [])

    def test_integrate_refuses_dirty_source_and_unresolved_target(self) -> None:
        self.prepare()
        (self.worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        dirty, dirty_payload = self.integrate()
        self.assert_error(dirty, dirty_payload, "dirty_worktree")
        (self.worktree / "dirty.txt").unlink()
        self.assertEqual(git(self.repo, "branch", "release").returncode, 0)

        unresolved, unresolved_payload = self.cli(
            "integrate",
            "--target-branch",
            "release",
        )
        self.assert_error(unresolved, unresolved_payload, "target_worktree_unresolved")

    def test_integrate_refuses_dirty_target_before_mutation(self) -> None:
        self.prepare()
        self.commit_source()
        (self.repo / "dirty-target.txt").write_text("dirty\n", encoding="utf-8")
        target_before = git(self.repo, "rev-parse", "main").stdout.strip()

        result, payload = self.integrate()

        self.assert_error(result, payload, "dirty_target_worktree")
        self.assertEqual(
            git(self.repo, "rev-parse", "main").stdout.strip(), target_before
        )
        self.assertEqual(payload["operations"], [])

    def test_integrate_ignores_primary_agent_factory_changes(self) -> None:
        self.prepare()
        source_commit = self.commit_source()
        runtime_file = self.repo / ".agent-factory" / "runtime-local.txt"
        runtime_file.write_text("local control-plane state\n", encoding="utf-8")

        result, payload = self.integrate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["context"]["sourceCommit"], source_commit)
        self.assertTrue(runtime_file.exists())

    def test_integrate_does_not_execute_target_branch_metacharacters(self) -> None:
        self.prepare()
        marker = self.root / "should-not-exist"
        result, payload = self.cli(
            "integrate",
            "--target-branch",
            f"main;touch {marker}",
        )
        self.assert_error(result, payload, "invalid_target_branch")
        self.assertFalse(marker.exists())

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
