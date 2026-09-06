"""Independent checks of the final package's runtime-relative entry points."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_runtime_entrypoints_import_from_isolated_installed_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            installed = base / "agent-factory"
            shutil.copytree(ROOT / "skills", installed / "skills",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            shutil.copytree(ROOT / ".agent-factory/document/specification",
                            installed / ".agent-factory/document/specification")
            cwd = base / "consumer"; cwd.mkdir()
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("PYTHONPATH", None)
            for script in ("exec.py", "loop.py"):
                path = installed / "skills/agent/scripts" / script
                result = subprocess.run([sys.executable, str(path), "--help"], cwd=cwd,
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((cwd / ".agent-factory").exists())
            self.assertTrue((installed / "skills/agent/runtime/cloud_reporting.py").is_file())
            for name in ("agent", "convention", "document", "gather", "tool", "workspace"):
                self.assertTrue((installed / ".agent-factory/document/specification" / name / "app.js").is_file())
