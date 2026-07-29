from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


SKILLS = Path(__file__).resolve().parents[2]


class SkillMetadataTests(unittest.TestCase):
    def test_skill_directories_match_the_approved_flat_naming_contract(self) -> None:
        expected = {
            "agent-factory",
            "agents",
            "agents-main",
            "agents-workflow",
            "conventions",
            "conventions-annotation",
            "conventions-icon-svg",
            "factories",
            "factories-lifecycle",
            "factories-rule",
            "intakes",
            "intakes-analysis",
            "intakes-interview",
            "intakes-research",
            "intakes-web-search",
            "specifications",
            "specifications-diagram",
            "syncs",
            "syncs-google-drive",
            "syncs-google-gmail",
            "work-units",
            "work-units-execution",
            "work-units-manager",
        }
        actual = {
            path.name
            for path in SKILLS.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            sorted(actual),
            [
                "agent-factory",
                "agents",
                "agents-main",
                "agents-workflow",
                "conventions",
                "conventions-annotation",
                "conventions-icon-svg",
                "factories",
                "factories-lifecycle",
                "factories-rule",
                "intakes",
                "intakes-analysis",
                "intakes-interview",
                "intakes-research",
                "intakes-web-search",
                "specifications",
                "specifications-diagram",
                "syncs",
                "syncs-google-drive",
                "syncs-google-gmail",
                "work-units",
                "work-units-execution",
                "work-units-manager",
            ],
        )
        removed_skill = "fact" + "-only"
        self.assertFalse((SKILLS / removed_skill).exists())

    def test_lifecycle_starts_with_intake_without_init_skill_or_mandatory_specification(
        self,
    ) -> None:
        self.assertFalse((SKILLS / "init" / "SKILL.md").exists())
        self.assertFalse((SKILLS / "init" / "agents" / "openai.yaml").exists())
        lifecycle = (SKILLS / "factories-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "factories-lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        specification = (SKILLS / "specifications" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_specification = " ".join(specification.split())

        self.assertNotIn("Use `init`", lifecycle)
        self.assertNotIn("route through `init`", lifecycle)
        self.assertIn("start with `intakes`", lifecycle)
        self.assertNotIn("Goal-Based Initialization", lifecycle_reference)
        self.assertIn(
            "Specification creation is not mandatory", normalized_specification
        )
        self.assertIn(
            "only when the recorded impact requires it", normalized_specification
        )

    def test_named_work_unit_execution_requires_an_active_goal(self) -> None:
        lifecycle = (SKILLS / "factories-lifecycle" / "SKILL.md").read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "factories-lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        execution = (SKILLS / "work-units-execution" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        app_server_goal = (
            SKILLS
            / "work-units-execution"
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

    def test_skill_frontmatter_names_match_their_directories(self) -> None:
        for path in sorted(SKILLS.glob("*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                _, frontmatter, _ = text.split("---", 2)
                metadata = yaml.safe_load(frontmatter)
                self.assertEqual(metadata["name"], path.parent.name)

    def test_routing_entrypoints_expose_only_the_approved_capabilities(self) -> None:
        routes = {
            "agent-factory": [
                "agents",
                "factories",
                "intakes",
                "specifications",
                "work-units",
                "conventions",
                "syncs",
            ],
            "agents": ["agents-main", "agents-workflow"],
            "factories": ["factories-lifecycle", "factories-rule"],
            "conventions": ["conventions-annotation", "conventions-icon-svg"],
            "syncs": ["syncs-google-drive", "syncs-google-gmail"],
            "work-units": ["work-units-manager", "work-units-execution"],
        }

        for router, capabilities in routes.items():
            with self.subTest(router=router):
                text = (SKILLS / router / "SKILL.md").read_text(encoding="utf-8")
                route_lines = [
                    line
                    for line in text.splitlines()
                    if line.startswith("- `")
                ]
                self.assertEqual(
                    [line.split("`", 2)[1] for line in route_lines],
                    capabilities,
                )
                for line in route_lines:
                    self.assertRegex(line, r"^- `[^`]+`: \S.+[.!]$")
                forbidden_logic = [
                    "Mandatory Manager Script Gate",
                    "Code Comment Convention",
                ]
                if router != "syncs":
                    forbidden_logic.extend(("python3 ", "scripts/"))
                for duplicated_logic in forbidden_logic:
                    self.assertNotIn(duplicated_logic, text)

    def test_annotation_convention_has_single_skill_owner(self) -> None:
        owners = [
            path
            for path in SKILLS.glob("*/SKILL.md")
            if "## Code Comment Convention"
            in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            owners,
            [SKILLS / "conventions-annotation" / "SKILL.md"],
        )
        factory_rule = (SKILLS / "factories-rule" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Use `conventions-annotation`", factory_rule)

    def test_main_agent_owns_human_result_review_without_a_standalone_skill(
        self,
    ) -> None:
        skill_path = SKILLS / "human-review" / "SKILL.md"
        metadata_path = SKILLS / "human-review" / "agents" / "openai.yaml"
        main_agent = (SKILLS / "agents-main" / "SKILL.md").read_text(
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
        agent_main = (SKILLS / "agents-main" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        agent_workflow = (SKILLS / "agents-workflow" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("primary lifecycle", agent_main)
        self.assertIn("app_server_goal.py", agent_main)
        self.assertIn("must not execute Work Unit implementation", agent_main)
        self.assertIn("Goal preflight", agent_workflow)
        self.assertIn("Plan -> Work -> AI Review -> Report", agent_workflow)
        self.assertIn(
            "before `execution-init` or `attempt-start`",
            agent_workflow,
        )
        for excluded in (
            "merge",
            "cleanup",
            "push",
            "PR promotion",
        ):
            with self.subTest(excluded=excluded):
                self.assertIn(excluded, agent_workflow)

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
            "syncs-google-gmail": {
                "google-api-python-client",
                "google-auth",
                "google-auth-oauthlib",
            },
            "intakes": {"jsonschema>=4.18,<5"},
            "specifications": {"jsonschema>=4.18,<5"},
            "work-units-manager": {"jsonschema>=4.18,<5"},
        }
        paths = {
            "syncs-google-gmail": SKILLS / "syncs-google-gmail" / "scripts" / "requirements.txt",
            "intakes": SKILLS / "intakes" / "scripts" / "requirements.txt",
            "specifications": SKILLS / "specifications" / "scripts" / "requirements.txt",
            "work-units-manager": SKILLS
            / "work-units-manager"
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
