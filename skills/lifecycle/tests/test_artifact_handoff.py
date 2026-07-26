from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


LIFECYCLE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = LIFECYCLE_ROOT / "assets" / "scripts" / "artifact_handoff.py"
PLANNER_TEST = (
    LIFECYCLE_ROOT.parent
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


helpers = load_planner_test_helpers()


def load_handoff_module():
    spec = importlib.util.spec_from_file_location("artifact_handoff", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load artifact handoff module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


handoff = load_handoff_module()


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ArtifactHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name) / "repo"
        self.repository.mkdir()
        run("git", "init", "-b", "main", str(self.repository))
        run("git", "config", "user.name", "Agent Factory Test", cwd=self.repository)
        run(
            "git",
            "config",
            "user.email",
            "agent-factory@example.invalid",
            cwd=self.repository,
        )
        (self.repository / ".gitignore").write_text(
            "/.agent-factory/worktree/\n", encoding="utf-8"
        )
        run("git", "add", ".gitignore", cwd=self.repository)
        run("git", "commit", "-m", "baseline", cwd=self.repository)
        self.intake = helpers.create_ready_intake(self.repository)
        self.work_unit = helpers.create_package(self.repository, "wu-001")
        helpers.populate_ready_candidate(self.repository, self.work_unit, self.intake)
        helpers.run_cli("transition", str(self.work_unit), "ready")
        shutil.rmtree(self.repository / ".agent-factory" / "worktree")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(
        self,
        command: str,
        artifact_type: str,
        artifact_id: str,
        *extra: str,
        target_branch: str = "main",
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        package_collection = (
            "intakes" if artifact_type == "intake" else "work-units"
        )
        package = (
            self.repository
            / ".agent-factory"
            / package_collection
            / artifact_id
        )
        result = run(
            sys.executable,
            str(SCRIPT),
            command,
            "--repository",
            str(self.repository),
            "--artifact-type",
            artifact_type,
            "--artifact-id",
            artifact_id,
            "--package",
            str(package),
            "--target-branch",
            target_branch,
            *extra,
        )
        payload = json.loads(result.stdout)
        return result, payload

    def checkpoint(
        self,
        artifact_type: str,
        artifact_id: str,
        message: str,
        *,
        target_branch: str = "main",
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        return self.cli(
            "checkpoint",
            artifact_type,
            artifact_id,
            "--message",
            message,
            "--human-decision",
            "approved",
            target_branch=target_branch,
        )

    def test_checkpoint_uses_the_checked_out_approved_target_branch(self) -> None:
        target_branch = "intake/source-intake"
        switched = run("git", "switch", "-c", target_branch, cwd=self.repository)
        self.assertEqual(switched.returncode, 0, switched.stderr)
        before = run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip()

        refused, refusal = self.checkpoint(
            "intake",
            "source-intake",
            "checkpoint intake source-intake",
            target_branch="main",
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(refusal["error"]["code"], "target_branch_mismatch")
        self.assertEqual(
            run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip(),
            before,
        )

        result, receipt = self.checkpoint(
            "intake",
            "source-intake",
            "checkpoint intake source-intake",
            target_branch=target_branch,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(receipt["state"], "checkpointed")
        self.assertEqual(receipt["context"]["targetBranch"], target_branch)
        self.assertEqual(
            run(
                "git", "symbolic-ref", "--short", "HEAD", cwd=self.repository
            ).stdout.strip(),
            target_branch,
        )

    def test_checkpoint_refuses_detached_head_without_mutation(self) -> None:
        before = run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip()
        detached = run("git", "switch", "--detach", cwd=self.repository)
        self.assertEqual(detached.returncode, 0, detached.stderr)

        refused, refusal = self.checkpoint(
            "intake",
            "source-intake",
            "checkpoint intake source-intake",
            target_branch="intake/source-intake",
        )

        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(refusal["error"]["code"], "target_branch_mismatch")
        self.assertEqual(
            run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip(),
            before,
        )
        self.assertEqual(
            run(
                "git", "diff", "--cached", "--name-only", cwd=self.repository
            ).stdout.strip(),
            "",
        )

    def test_two_checkpoint_handoff_replay_and_inspection(self) -> None:
        intake_result, intake_receipt = self.checkpoint(
            "intake", "source-intake", "checkpoint intake source-intake"
        )
        self.assertEqual(intake_result.returncode, 0, intake_result.stderr)
        self.assertEqual(intake_receipt["state"], "checkpointed")

        work_result, work_receipt = self.checkpoint(
            "work-unit", "wu-001", "checkpoint work unit wu-001"
        )
        self.assertEqual(work_result.returncode, 0, work_result.stderr)
        self.assertEqual(work_receipt["state"], "checkpointed")
        self.assertEqual(
            work_receipt["context"]["beforeCommit"],
            intake_receipt["context"]["afterCommit"],
        )

        intake_replay_result, intake_replay = self.checkpoint(
            "intake", "source-intake", "checkpoint intake source-intake"
        )
        self.assertEqual(intake_replay_result.returncode, 0, intake_replay_result.stderr)
        self.assertEqual(intake_replay["state"], "already-checkpointed")
        self.assertEqual(
            intake_replay["context"]["afterCommit"],
            intake_receipt["context"]["afterCommit"],
        )

        replay_result, replay = self.checkpoint(
            "work-unit", "wu-001", "checkpoint work unit wu-001"
        )
        self.assertEqual(replay_result.returncode, 0, replay_result.stderr)
        self.assertEqual(replay["state"], "already-checkpointed")
        self.assertEqual(
            replay["context"]["afterCommit"], work_receipt["context"]["afterCommit"]
        )

        inspect_result, inspected = self.cli(
            "inspect", "work-unit", "wu-001"
        )
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
        self.assertEqual(inspected["state"], "inspected")
        self.assertEqual(
            inspected["context"]["checkpointCommit"],
            work_receipt["context"]["afterCommit"],
        )

    def test_existing_package_recheckpoint_commits_changed_canonical_subset(self) -> None:
        intake_result, intake_receipt = self.checkpoint(
            "intake", "source-intake", "checkpoint intake source-intake"
        )
        self.assertEqual(intake_result.returncode, 0, intake_result.stderr)

        helpers.run_intake(
            "title-set", str(self.intake), "Updated Source Intake"
        )
        helpers.run_intake(
            "metadata-set",
            str(self.intake),
            "readiness",
            *helpers.data_args(
                {
                    "contractValid": True,
                    "evidenceComplete": True,
                    "requirementsComplete": True,
                    "specificationConsistent": True,
                    "executionReady": True,
                    "reviewedAt": "2026-07-25T00:00:00+00:00",
                    "findings": [],
                }
            ),
        )
        helpers.run_intake("transition", str(self.intake), "validating")
        helpers.run_intake("transition", str(self.intake), "ready")

        recheckpoint_result, recheckpoint = self.checkpoint(
            "intake", "source-intake", "recheckpoint intake source-intake"
        )
        self.assertEqual(
            recheckpoint_result.returncode, 0, recheckpoint_result.stdout
        )
        self.assertEqual(recheckpoint["state"], "checkpointed")

        package_files = set(recheckpoint["context"]["validation"]["files"])
        package_root = ".agent-factory/intakes/source-intake"
        canonical_paths = {f"{package_root}/{path}" for path in package_files}
        changed_paths = set(
            run(
                "git",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                recheckpoint["context"]["afterCommit"],
                cwd=self.repository,
            ).stdout.splitlines()
        )
        self.assertTrue(changed_paths)
        self.assertLess(changed_paths, canonical_paths)

        replay_result, replay = self.checkpoint(
            "intake", "source-intake", "recheckpoint intake source-intake"
        )
        self.assertEqual(replay_result.returncode, 0, replay_result.stdout)
        self.assertEqual(replay["state"], "already-checkpointed")
        self.assertEqual(
            replay["context"]["afterCommit"],
            recheckpoint["context"]["afterCommit"],
        )

        inspect_result, inspected = self.cli(
            "inspect", "intake", "source-intake"
        )
        self.assertEqual(inspect_result.returncode, 0, inspect_result.stdout)
        self.assertEqual(
            inspected["context"]["checkpointCommit"],
            recheckpoint["context"]["afterCommit"],
        )

        work_result, work_receipt = self.checkpoint(
            "work-unit", "wu-001", "checkpoint work unit wu-001"
        )
        self.assertEqual(work_result.returncode, 0, work_result.stdout)
        self.assertEqual(
            work_receipt["context"]["beforeCommit"],
            recheckpoint["context"]["afterCommit"],
        )
        self.assertNotEqual(
            intake_receipt["context"]["afterCommit"],
            recheckpoint["context"]["afterCommit"],
        )

    def test_checkpoint_refuses_missing_approval_and_unrelated_staged_state(self) -> None:
        before = run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip()
        denied, payload = self.cli(
            "checkpoint",
            "intake",
            "source-intake",
            "--message",
            "checkpoint intake source-intake",
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(payload["error"]["code"], "missing_human_decision")
        self.assertEqual(
            run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip(),
            before,
        )

        unrelated = self.repository / "unrelated.txt"
        unrelated.write_text("staged\n", encoding="utf-8")
        run("git", "add", "unrelated.txt", cwd=self.repository)
        refused, payload = self.checkpoint(
            "intake", "source-intake", "checkpoint intake source-intake"
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(payload["error"]["code"], "unrelated_staged_changes")
        self.assertEqual(
            run("git", "diff", "--cached", "--name-only", cwd=self.repository)
            .stdout.strip(),
            "unrelated.txt",
        )

    def test_validation_to_stage_swap_is_detected_and_index_is_restored(self) -> None:
        before = run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip()
        title = self.intake / "data" / "title.json"

        class SwapExecution(handoff.Execution):
            swapped = False

            def git(self, repository, args, *, record=False):
                result = super().git(repository, args, record=record)
                if list(args[:2]) == ["add", "--"] and not self.swapped:
                    title.write_text('{"title":"swapped"}\n', encoding="utf-8")
                    self.swapped = True
                return result

        args = handoff.parser().parse_args(
            [
                "checkpoint",
                "--repository",
                str(self.repository),
                "--artifact-type",
                "intake",
                "--artifact-id",
                "source-intake",
                "--package",
                str(self.intake),
                "--target-branch",
                "main",
                "--message",
                "checkpoint intake source-intake",
                "--human-decision",
                "approved",
            ]
        )
        execution = SwapExecution("checkpoint")
        with self.assertRaises(handoff.ContractError) as raised:
            handoff.checkpoint(execution, args)
        self.assertEqual(raised.exception.code, "artifact_content_race")
        self.assertEqual(
            run("git", "rev-parse", "HEAD", cwd=self.repository).stdout.strip(),
            before,
        )
        self.assertEqual(
            run("git", "diff", "--cached", "--name-only", cwd=self.repository)
            .stdout.strip(),
            "",
        )


if __name__ == "__main__":
    unittest.main()
