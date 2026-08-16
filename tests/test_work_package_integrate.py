from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "work-units"
    / "scripts"
    / "work_package_integrate.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("work_package_integrate", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Work Package integrator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repository: Path, *arguments: str):
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class WorkPackageIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_integrates_package_branch_once_and_returns_traceable_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q", "-b", "main")
            git(repository, "config", "user.name", "Agent Factory Test")
            git(repository, "config", "user.email", "agent-factory@example.invalid")
            (repository / "base.txt").write_text("base\n", encoding="utf-8")
            git(repository, "add", "base.txt")
            git(repository, "commit", "-q", "-m", "base")
            git(repository, "checkout", "-q", "-b", "work-package/pkg")
            (repository / "result.txt").write_text("done\n", encoding="utf-8")
            git(repository, "add", "result.txt")
            git(repository, "commit", "-q", "-m", "package result")
            git(repository, "checkout", "-q", "main")
            receipt = self.module.integrate(
                repository=repository,
                package_id="pkg",
                source_branch="work-package/pkg",
                target_branch="main",
            )
            self.assertEqual(receipt["operationResult"], "integrated")
            self.assertTrue((repository / "result.txt").is_file())
            second = self.module.integrate(
                repository=repository,
                package_id="pkg",
                source_branch="work-package/pkg",
                target_branch="main",
            )
            self.assertEqual(second["relationship"], "already-integrated")

    def test_failed_package_review_is_rejected_before_integration(self):
        section = {
            "content": [
                {
                    "kind": "ai-review-result",
                    "attributes": {
                        "result": "fail",
                        "checklistResult": "fail",
                    },
                }
            ],
            "subsections": [],
        }
        with mock.patch.object(self.module, "manager_json", return_value=section):
            with self.assertRaisesRegex(
                self.module.IntegrationError, "AI review did not pass"
            ):
                self.module.require_passing_review(Path("/package"))

    def test_integrates_without_forcing_target_branch_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            git(repository, "init", "-q", "-b", "main")
            git(repository, "config", "user.name", "Agent Factory Test")
            git(repository, "config", "user.email", "agent-factory@example.invalid")
            (repository / "base.txt").write_text("base\n", encoding="utf-8")
            git(repository, "add", "base.txt")
            git(repository, "commit", "-q", "-m", "base")
            git(repository, "branch", "factory")
            git(repository, "checkout", "-q", "-b", "work-package/pkg")
            (repository / "result.txt").write_text("done\n", encoding="utf-8")
            git(repository, "add", "result.txt")
            git(repository, "commit", "-q", "-m", "package result")
            source = git(repository, "rev-parse", "HEAD").stdout.strip()

            receipt = self.module.integrate(
                repository=repository,
                package_id="pkg",
                source_branch="work-package/pkg",
                target_branch="factory",
            )

            self.assertEqual(receipt["targetCommitAfter"], source)
            self.assertEqual(
                git(repository, "branch", "--show-current").stdout.strip(),
                "work-package/pkg",
            )


if __name__ == "__main__":
    unittest.main()
