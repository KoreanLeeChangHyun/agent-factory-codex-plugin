from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


SKILLS = Path(__file__).resolve().parents[2]


class SkillMetadataTests(unittest.TestCase):
    def test_lifecycle_starts_with_intake_without_init_skill_or_mandatory_specification(
        self,
    ) -> None:
        self.assertFalse((SKILLS / "init" / "SKILL.md").exists())
        self.assertFalse((SKILLS / "init" / "agents" / "openai.yaml").exists())
        lifecycle = (SKILLS / "lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        specification = (SKILLS / "specification" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_specification = " ".join(specification.split())

        self.assertNotIn("Use `init`", lifecycle)
        self.assertNotIn("route through `init`", lifecycle)
        self.assertIn("start with `intake`", lifecycle)
        self.assertNotIn("Goal-Based Initialization", lifecycle_reference)
        self.assertIn(
            "Specification creation is not mandatory", normalized_specification
        )
        self.assertIn(
            "only when the recorded impact requires it", normalized_specification
        )

    def test_named_work_unit_execution_requires_an_active_goal(self) -> None:
        lifecycle = (SKILLS / "lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        execution = (SKILLS / "work-unit-execution" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        app_server_goal = (
            SKILLS
            / "work-unit-execution"
            / "scripts"
            / "app_server_goal.py"
        )

        for text in (lifecycle, lifecycle_reference, execution):
            with self.subTest(document=text[:80]):
                self.assertNotIn(
                    "The `codex exec` route does not require persistent Goal mode.",
                    text,
                )
                self.assertNotIn(
                    "Persistent Goal mode is not required for the `codex exec` route.",
                    text,
                )

        self.assertIn("Goal preflight", lifecycle)
        self.assertIn("Goal preflight", lifecycle_reference)
        self.assertIn("Goal preflight", execution)
        self.assertIn("before worktree preparation", execution)
        self.assertIn("fail closed", execution)
        self.assertTrue(app_server_goal.is_file())
        for text in (lifecycle, lifecycle_reference, execution):
            with self.subTest(programmatic_document=text[:80]):
                self.assertIn("app_server_goal.py", text)
                self.assertIn("thread/goal/set", text)
                self.assertIn("thread/goal/get", text)
                self.assertIn("turn/start", text)

    def test_openai_yaml_interfaces_follow_skill_creator_contract(self) -> None:
        paths = sorted(SKILLS.glob("*/agents/openai.yaml"))
        skill_directories = sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))
        self.assertEqual(
            [path.parents[1] for path in paths],
            skill_directories,
            "every skill must provide agents/openai.yaml UI metadata",
        )
        for path in paths:
            with self.subTest(skill=path.parents[1].name):
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(value, dict)
                self.assertTrue(
                    set(value).issubset({"interface", "dependencies", "policy"})
                )
                interface = value["interface"]
                self.assertIsInstance(interface["display_name"], str)
                short = interface["short_description"]
                self.assertGreaterEqual(len(short), 25)
                self.assertLessEqual(len(short), 64)
                prompt = interface["default_prompt"]
                self.assertIn(f"${path.parents[1].name}", prompt)

    def test_main_agent_owns_human_result_review_without_a_standalone_skill(
        self,
    ) -> None:
        skill_path = SKILLS / "human-review" / "SKILL.md"
        metadata_path = SKILLS / "human-review" / "agents" / "openai.yaml"
        main_agent = (SKILLS / "main-agent" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_main_agent = " ".join(main_agent.split())

        self.assertFalse(skill_path.exists())
        self.assertFalse(metadata_path.exists())
        self.assertIn("Korean", main_agent)
        for expected in (
            "delivered scope and exclusions",
            "changed paths or updated canonical Specification",
            "exact verification commands and results",
            "AI review findings",
            "remaining risks or failed checks",
            "whether the execution mode requires Git integration",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, normalized_main_agent)
        self.assertIn("`rework`", main_agent)
        self.assertIn("`complete`", main_agent)
        self.assertIn("not an approval gate", normalized_main_agent)
        self.assertIn("later batch cleanup", normalized_main_agent)

    def test_main_and_workflow_agent_roles_are_separated(self) -> None:
        main_agent = (SKILLS / "main-agent" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        workflow_agent = (SKILLS / "workflow-agent" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("primary lifecycle", main_agent)
        self.assertIn("app_server_goal.py", main_agent)
        self.assertIn("must not execute Work Unit implementation", main_agent)
        self.assertIn("Goal preflight", workflow_agent)
        self.assertIn("Plan -> Work -> AI Review -> Report", workflow_agent)
        self.assertIn(
            "before `execution-init` or `attempt-start`",
            workflow_agent,
        )
        for excluded in (
            "merge",
            "cleanup",
            "push",
            "PR promotion",
        ):
            with self.subTest(excluded=excluded):
                self.assertIn(excluded, workflow_agent)

    def test_plugin_manifest_routes_to_all_skills_with_valid_starter_prompts(
        self,
    ) -> None:
        plugin_root = SKILLS.parent
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "agent-factory")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual((plugin_root / manifest["skills"]).resolve(), SKILLS.resolve())
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertGreaterEqual(len(prompts), 1)
        self.assertLessEqual(len(prompts), 3)
        self.assertTrue(
            all(
                isinstance(prompt, str) and 0 < len(prompt) <= 128 for prompt in prompts
            )
        )

    def test_bundled_python_tools_declare_requirements_when_they_import_third_party_packages(
        self,
    ) -> None:
        expected = {
            "google-mail": {
                "google-api-python-client",
                "google-auth",
                "google-auth-oauthlib",
            },
            "intake": {"jsonschema>=4.18,<5"},
            "specification": {"jsonschema>=4.18,<5"},
            "work-unit-planner": {"jsonschema>=4.18,<5"},
        }
        paths = {
            "google-mail": SKILLS / "google-mail" / "scripts" / "requirements.txt",
            "intake": SKILLS / "intake" / "scripts" / "requirements.txt",
            "specification": SKILLS / "specification" / "scripts" / "requirements.txt",
            "work-unit-planner": SKILLS
            / "work-unit-planner"
            / "assets"
            / "scripts"
            / "requirements.txt",
        }
        for skill, path in paths.items():
            with self.subTest(skill=skill):
                self.assertTrue(path.is_file())
                requirements = {
                    line.strip()
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                }
                self.assertEqual(requirements, expected[skill])


if __name__ == "__main__":
    unittest.main()
