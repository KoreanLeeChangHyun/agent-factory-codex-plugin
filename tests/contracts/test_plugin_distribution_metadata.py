from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
VERIFICATION_WORKFLOW = ROOT / ".github" / "workflows" / "manual-verification.yml"
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
CACHEBUSTER_VERSION = re.compile(r"^0\.1\.0\+codex\.\d{14}$")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


class PluginDistributionMetadataTests(unittest.TestCase):
    def test_manifest_has_release_metadata_and_resolvable_skill_path(self) -> None:
        manifest = read_json(MANIFEST)
        self.assertEqual(manifest["name"], "agent-factory")
        self.assertRegex(manifest["version"], SEMVER)
        self.assertRegex(manifest["version"], CACHEBUSTER_VERSION)
        for field in ("description", "homepage", "repository", "license"):
            self.assertIsInstance(manifest[field], str)
            self.assertTrue(manifest[field])
        self.assertEqual(manifest["author"]["name"], "Agent Factory")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)
        self.assertTrue((ROOT / manifest["skills"]).is_dir())
        self.assertEqual(
            {path.name for path in (ROOT / manifest["skills"]).iterdir() if path.is_dir()},
            {"agent", "convention"},
        )
        for field in ("homepage", "repository"):
            self.assertEqual(urlsplit(manifest[field]).scheme, "https")

    def test_manifest_interface_is_bounded_and_usable(self) -> None:
        interface = read_json(MANIFEST)["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            self.assertIsInstance(interface[field], str)
            self.assertTrue(interface[field])
        prompts = interface["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertGreaterEqual(len(prompts), 1)
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(all(isinstance(prompt, str) and 0 < len(prompt) <= 128 for prompt in prompts))
        self.assertEqual(urlsplit(interface["websiteURL"]).scheme, "https")

    def test_marketplace_matches_manifest_and_published_release_branch(self) -> None:
        manifest = read_json(MANIFEST)
        marketplace = read_json(MARKETPLACE)
        self.assertEqual(marketplace["name"], "agent-factory")
        self.assertTrue(marketplace["interface"]["displayName"])
        entries = marketplace["plugins"]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["name"], manifest["name"])
        self.assertEqual(entry["category"], manifest["interface"]["category"])
        self.assertEqual(entry["source"], {
            "source": "url",
            "url": manifest["repository"] + ".git",
            "ref": "main",
        })
        self.assertIn(entry["policy"]["installation"], {
            "NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT",
        })
        self.assertIn(entry["policy"]["authentication"], {"ON_INSTALL", "ON_USE"})

    def test_verification_workflow_requires_manual_human_dispatch(self) -> None:
        workflow = yaml.load(
            VERIFICATION_WORKFLOW.read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        dispatch = workflow["on"]["workflow_dispatch"]
        scope = dispatch["inputs"]["scope"]
        self.assertEqual(scope["type"], "choice")
        self.assertEqual(scope["required"], "true")
        self.assertEqual(scope["default"], "contracts")
        self.assertEqual(scope["options"], ["contracts", "full"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"contracts", "full"})
        contracts = workflow["jobs"]["contracts"]
        full = workflow["jobs"]["full"]
        self.assertNotIn("permissions", contracts)
        self.assertNotIn("permissions", full)
        self.assertNotIn("if", contracts)
        self.assertEqual(full["if"], "inputs.scope == 'full'")
        contract_commands = [step["run"] for step in contracts["steps"] if "run" in step]
        self.assertIn(
            "python -m pytest "
            "tests/contracts/test_convention_skill_metadata.py "
            "tests/contracts/test_plugin_distribution_metadata.py "
            "tests/integration/test_distribution.py",
            contract_commands,
        )
        full_commands = [step["run"] for step in full["steps"] if "run" in step]
        self.assertIn(
            "python -m pytest tests -n auto --maxprocesses=4 --dist=worksteal",
            full_commands,
        )


if __name__ == "__main__":
    unittest.main()
