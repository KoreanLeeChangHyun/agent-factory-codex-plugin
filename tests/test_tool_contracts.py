"""Stateless local inspection stays with host tools; cloud owns connection state."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ToolContractTests(unittest.TestCase):
    def test_local_profiles_keep_authority_unknown_state_and_secret_boundaries(self):
        for profile, markers in {
            "git": ("git.cli", "github.cli", "git-lfs.cli", "Git directory", "common directory", "detached", "unknown", "structured", "token"),
            "playwright": ("playwright.browser", "unknown", "manifest", "Do not launch a browser", "authority"),
        }.items():
            text = (ROOT / "skills/tool/references" / f"{profile}.md").read_text()
            for marker in markers:
                with self.subTest(profile=profile, marker=marker):
                    self.assertIn(marker.casefold(), text.casefold())
        lifecycle = (ROOT / "skills/tool/references/lifecycle.md").read_text()
        for marker in ("Unknown, unsupported, stale, and unavailable", "Tool readiness does not authorize execution", "performed: false", "token-bearing tool arguments", "integration_inspect", "Unsupported permission enumeration", "never escalates scope automatically"):
            self.assertIn(marker, lifecycle)
