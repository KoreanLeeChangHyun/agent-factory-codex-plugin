from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "tool" / "scripts" / "tool.py"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_factory_tool", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Tool adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ToolAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_git_discovery_is_stateless_and_keeps_exact_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.module.shutil, "which", return_value=None
        ):
            args = self.module.parse_args([
                "discover", "--profile", "git.cli", "--target", directory,
                "--authority-reference", "os-package:git",
            ])
            document = self.module.profile_document(args)
        self.assertEqual(document["authority"], {"kind": "native-executable", "reference": "os-package:git"})
        self.assertEqual(document["state"], "unavailable")
        self.assertFalse(document["route"]["performed"])
        self.assertFalse(document["secretMaterialStored"])

    def test_playwright_plugin_authority_remains_unknown_without_provider_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.module.parse_args([
                "health", "--profile", "playwright.browser", "--target", directory,
                "--authority-kind", "plugin", "--authority-reference", "plugin:browser-provider",
            ])
            document = self.module.profile_document(args)
        self.assertEqual(document["state"], "unknown")
        self.assertEqual(document["facts"]["browsers"], "unknown")

    def test_lifecycle_mutation_only_returns_provider_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = self.module.parse_args([
                "install", "--profile", "playwright.browser", "--target", directory,
                "--authority-kind", "project-cli",
            ])
            document = self.module.profile_document(args)
        self.assertEqual(document["kind"], "tool-lifecycle-route")
        self.assertTrue(document["route"]["requiresHumanApproval"])
        self.assertFalse(document["route"]["performed"])

    def test_github_auth_reports_supported_structured_success(self) -> None:
        result = {
            "status": "available",
            "output": '{"hosts":{"github.com":[{"active":true,"host":"github.com","login":"octo","scopes":["repo"],"state":"success","tokenSource":"keyring"}]}}',
            "failureReason": None,
        }
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/gh"), mock.patch.object(
            self.module, "run", return_value=result
        ) as run:
            authentication = self.module.github_auth("github.com")
        run.assert_called_once_with((
            "/usr/bin/gh", "auth", "status", "--hostname", "github.com", "--json", "hosts",
        ))
        self.assertEqual(authentication["status"], "available")
        self.assertEqual(authentication["inspectionSupport"], "supported")

    def test_github_auth_keeps_unsupported_structured_inspection_unknown(self) -> None:
        process = subprocess.CompletedProcess(
            args=[], returncode=2, stdout="", stderr="unknown flag: --json",
        )
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/gh"), mock.patch.object(
            self.module.subprocess, "run", return_value=process
        ) as run:
            authentication = self.module.github_auth("github.com")
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/gh", "auth", "status", "--hostname", "github.com", "--json", "hosts",
        ])
        self.assertEqual(authentication["status"], "unknown")
        self.assertEqual(authentication["inspectionSupport"], "unsupported")

    def test_github_auth_reports_structured_unauthenticated_separately(self) -> None:
        result = {
            "status": "unavailable",
            "output": '{"hosts":{"github.com":[{"active":false,"host":"github.com","login":"octo","scopes":[],"state":"failure","tokenSource":"keyring"}]}}',
            "failureReason": None,
        }
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/gh"), mock.patch.object(
            self.module, "run", return_value=result
        ) as run:
            authentication = self.module.github_auth("github.com")
        run.assert_called_once_with((
            "/usr/bin/gh", "auth", "status", "--hostname", "github.com", "--json", "hosts",
        ))
        self.assertEqual(authentication["status"], "unavailable")
        self.assertEqual(authentication["inspectionSupport"], "supported")

    def test_github_auth_keeps_malformed_structured_response_unknown(self) -> None:
        result = {
            "status": "available", "output": "not-json", "failureReason": None,
        }
        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/gh"), mock.patch.object(
            self.module, "run", return_value=result
        ) as run:
            authentication = self.module.github_auth("github.com")
        run.assert_called_once_with((
            "/usr/bin/gh", "auth", "status", "--hostname", "github.com", "--json", "hosts",
        ))
        self.assertEqual(authentication["status"], "unknown")
        self.assertEqual(authentication["inspectionSupport"], "unknown")


if __name__ == "__main__":
    unittest.main()
