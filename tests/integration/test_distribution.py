"""Independent checks of the final package's runtime-relative entry points."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DistributionTests(unittest.TestCase):
    def test_runtime_entrypoints_import_from_isolated_installed_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installed = base / "agent-factory"
            shutil.copytree(ROOT / "skills", installed / "skills",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            cwd = base / "consumer"; cwd.mkdir()
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "AGENT_FACTORY_HOME": str(base / "runtime-home")}
            env.pop("PYTHONPATH", None)
            for script in ("exec.py", "loop.py"):
                path = installed / "skills/agent/scripts" / script
                result = subprocess.run([sys.executable, str(path), "--help"], cwd=cwd,
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
            retired_invocations = [
                ("exec.py", ["reporting-deliver"]),
                ("exec.py", ["_report-send"]),
                ("exec.py", ["submit", "--agent", "main", "--role", "main", "--message", "request",
                             "--reporting-config", "missing.json"]),
                ("exec.py", ["send", "--agent", "main", "--message", "request",
                             "--reporting-loop-id", "old-loop"]),
                ("loop.py", ["start", "--work-agent", "work", "--verification-agent", "verify",
                             "--request-file", "missing.md", "--work-reporting-config", "missing.json"]),
                ("loop.py", ["start", "--work-agent", "work", "--verification-agent", "verify",
                             "--request-file", "missing.md", "--verification-reporting-config", "missing.json"]),
            ]
            for name, arguments in retired_invocations:
                with self.subTest(retired=arguments):
                    rejected = subprocess.run(
                        [sys.executable, str(installed / "skills/agent/scripts" / name), *arguments],
                        cwd=cwd, env=env, capture_output=True, text=True, timeout=20,
                    )
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn("invalid_arguments", rejected.stdout)
                    self.assertIn("report", rejected.stdout)
                    self.assertFalse((base / "runtime-home").exists())
            script = installed / "skills/agent/scripts/exec.py"
            location = subprocess.run([sys.executable, str(script), "location", "--project-root", str(cwd)],
                                      env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(location.returncode, 0, location.stdout)
            self.assertFalse((base / "runtime-home").exists())
            initialized = subprocess.run([sys.executable, str(script), "init", "--project-root", str(cwd)],
                                         env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(initialized.returncode, 0, initialized.stdout)
            self.assertTrue((base / "runtime-home/registry.json").is_file())
            self.assertFalse((cwd / ".agent-factory").exists())
            self.assertFalse((installed / "skills/agent/runtime/cloud_reporting.py").exists())
            self.assertFalse((installed / "mcp").exists())
            self.assertFalse((installed / "skills/mcp").exists())
            layout = (installed / "skills/document/SKILL.md").read_text()
            normalized_layout = " ".join(layout.split())
            for document_type in ("original", "processed", "skills"):
                self.assertIn(
                    f"<project-root>/docs/{document_type}/<category>[-<domain>]-<name>/",
                    normalized_layout,
                )
            self.assertIn("complete standalone behavior", normalized_layout)
            self.assertFalse((installed / "docs").exists())
