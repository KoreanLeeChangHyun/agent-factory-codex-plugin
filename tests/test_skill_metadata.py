from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


SKILLS = Path(__file__).resolve().parents[1] / "skills"


class SkillMetadataTests(unittest.TestCase):
    def test_skill_directories_match_the_approved_flat_naming_contract(self) -> None:
        expected = {
            "agents",
            "conventions",
            "intakes",
            "lifecycle",
            "projects",
            "rules",
            "specifications",
            "synchronization",
            "work-units",
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
                "agents",
                "conventions",
                "intakes",
                "lifecycle",
                "projects",
                "rules",
                "specifications",
                "synchronization",
                "work-units",
            ],
        )
        removed_skill = "fact" + "-only"
        self.assertFalse((SKILLS / removed_skill).exists())

    def test_lifecycle_defaults_to_feedback_first_without_mandatory_artifacts(
        self,
    ) -> None:
        self.assertFalse((SKILLS / "init" / "SKILL.md").exists())
        self.assertFalse((SKILLS / "init" / "agents" / "openai.yaml").exists())
        lifecycle = (
            SKILLS / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        specification = (
            SKILLS
            / "specifications"
            / "references"
            / "specification-management.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Use `init`", lifecycle)
        self.assertNotIn("route through `init`", lifecycle)
        self.assertIn("Work Agent edits the current Git workspace", lifecycle)
        self.assertIn("Recording Agent records the prior result", lifecycle)
        for optional in ("Intake", "Specification", "Work Unit", "worktree"):
            with self.subTest(optional=optional):
                self.assertIn(optional, lifecycle)
        self.assertNotIn("Goal-Based Initialization", lifecycle_reference)
        self.assertIn("Feedback-first loop", lifecycle_reference)
        self.assertIn("only when the Human explicitly requests it", specification)

    def test_named_work_unit_execution_requires_an_active_goal(self) -> None:
        lifecycle = (
            SKILLS / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text(encoding="utf-8")
        lifecycle_reference = (
            SKILLS / "lifecycle" / "references" / "lifecycle.md"
        ).read_text(encoding="utf-8")
        execution = (
            SKILLS
            / "work-units"
            / "references"
            / "work-unit-execution.md"
        ).read_text(encoding="utf-8")
        app_server_goal = (
            SKILLS
            / "work-units"
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

        self.assertIn("Explicit advanced routes", lifecycle)
        self.assertIn("Goal preflight", lifecycle_reference)
        self.assertIn("Goal preflight", execution)
        self.assertIn("before worktree preparation", execution)
        self.assertIn("fail closed", execution)
        self.assertTrue(app_server_goal.is_file())
        for text in (lifecycle_reference, execution):
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
            "agents": [
                "references/main-agent.md",
                "references/intake-agent.md",
                "references/workflow-agent.md",
            ],
            "conventions": [
                "references/annotation.md",
                "references/svg-icon.md",
            ],
            "intakes": [
                "references/intake-management.md",
                "references/intake-structure.md",
                "references/analysis.md",
                "references/web-search.md",
                "references/user-research.md",
                "references/interview.md",
            ],
            "lifecycle": [
                "references/lifecycle-entry.md",
                "references/lifecycle.md",
                "references/common-document-contract.md",
            ],
            "projects": [
                "references/project-skill.md",
                "references/local-viewer.md",
            ],
            "rules": [
                "references/fact-and-evidence-control.md",
                "references/engineering-principles.md",
                "references/change-safety.md",
                "references/runtime-safety.md",
                "references/session-state-model.md",
                "references/interview-decision-gate.md",
            ],
            "specifications": [
                "references/specification-management.md",
                "references/diagram.md",
            ],
            "synchronization": [
                "references/synchronization-management.md",
                "references/google-drive.md",
                "references/google-mail.md",
            ],
            "work-units": [
                "references/work-unit-management.md",
                "references/work-unit-structure.md",
                "references/work-unit-execution.md",
                "references/worktree-contract.md",
            ],
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
                self.assertNotIn("Mandatory Manager Script Gate", text)
                self.assertNotIn("Code Comment Convention", text)
                for reference in capabilities:
                    path = SKILLS / router / reference
                    self.assertTrue(path.is_file())
                    self.assertFalse(path.read_text(encoding="utf-8").startswith("---"))

    def test_annotation_convention_has_single_skill_owner(self) -> None:
        owners = [
            path
            for path in SKILLS.glob("*/references/*.md")
            if "## Code Comment Convention"
            in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(
            owners,
            [SKILLS / "conventions" / "references" / "annotation.md"],
        )
        factory_rule = (
            SKILLS / "rules" / "references" / "engineering-principles.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Use `conventions`", factory_rule)

    def test_rules_references_are_split_by_responsibility(self) -> None:
        rules = SKILLS / "rules"
        references = rules / "references"
        expected_references = {
            "fact-and-evidence-control.md",
            "engineering-principles.md",
            "change-safety.md",
            "runtime-safety.md",
            "session-state-model.md",
            "interview-decision-gate.md",
        }
        self.assertEqual(
            {path.name for path in references.glob("*.md")},
            expected_references,
        )

        entrypoint = (rules / "SKILL.md").read_text(encoding="utf-8")
        normalized_entrypoint = " ".join(entrypoint.split())
        self.assertNotIn("engineering-rules.md", entrypoint)
        self.assertIn("Always read `references/fact-and-evidence-control.md`", entrypoint)
        for condition in (
            "engineering, design, code, refactoring, or review work",
            "changes, mutations, or intent confirmation",
            "runtime restart or frontend cache work",
            "Agent Factory session UI state work",
            "before asking the Human a question",
        ):
            with self.subTest(condition=condition):
                self.assertIn(condition, normalized_entrypoint)
        self.assertIn("`lifecycle` owns the lifecycle sequence", normalized_entrypoint)

        owners = {
            "fact-and-evidence-control.md": {
                "# Factory Rule",
                "## Core Rule",
                "## Fact Control",
                "## Critical Thinking Rule",
                "## Evidence-First Workflow",
                "## Reporting",
            },
            "engineering-principles.md": {
                "## Agent Factory Engineering Principles",
            },
            "change-safety.md": {
                "## Intent Confirmation",
                "## Change Safety",
                "## Hard Stops",
            },
            "runtime-safety.md": {
                "## Runtime Restart Safety",
                "## Frontend Cache And Verification",
            },
            "session-state-model.md": {
                "## Agent Factory State Model Rule",
            },
        }
        reference_texts = {
            path.name: path.read_text(encoding="utf-8")
            for path in references.glob("*.md")
        }
        for owner, headings in owners.items():
            for heading in headings:
                with self.subTest(owner=owner, heading=heading):
                    containing = [
                        name for name, text in reference_texts.items() if heading in text
                    ]
                    self.assertEqual(containing, [owner])
        self.assertFalse(
            any("## Lifecycle Rule" in text for text in reference_texts.values())
        )
        self.assertIn(
            "Session -> DOM -> State",
            reference_texts["session-state-model.md"],
        )
        self.assertIn(
            "ask for one more explicit confirmation",
            reference_texts["runtime-safety.md"],
        )

    def test_main_agent_owns_human_result_review_without_a_standalone_skill(
        self,
    ) -> None:
        skill_path = SKILLS / "human-review" / "SKILL.md"
        metadata_path = SKILLS / "human-review" / "agents" / "openai.yaml"
        main_agent = (
            SKILLS / "agents" / "references" / "main-agent.md"
        ).read_text(encoding="utf-8")
        normalized_main_agent = " ".join(main_agent.split())

        self.assertFalse(skill_path.exists())
        self.assertFalse(metadata_path.exists())
        self.assertIn("Default feedback-first route", main_agent)
        for expected in (
            "delivered boundary",
            "changed paths",
            "tests run or `tests not run`",
            "known limitations",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, normalized_main_agent)
        self.assertIn("Recording Agent", main_agent)
        self.assertIn("Do not wait for project recording", main_agent)

    def test_review_agent_has_independent_static_review_ownership(self) -> None:
        router = (SKILLS / "agents" / "SKILL.md").read_text(encoding="utf-8")
        review_agent = (
            SKILLS / "agents" / "references" / "review-agent.md"
        ).read_text(encoding="utf-8")
        manager = (
            SKILLS / "work-units" / "scripts" / "work_unit.py"
        ).read_text(encoding="utf-8")

        self.assertIn("references/review-agent.md", router)
        self.assertIn("static review only", review_agent)
        self.assertIn("Do not modify", review_agent)
        self.assertIn("Do not execute tests", review_agent)
        self.assertIn('"Review Agent"', manager)
        self.assertIn('"Main Agent"', manager)
        self.assertIn('package.name == "add-independent-review-agent"', manager)
        self.assertIn("require_evidence(package, ai_review", manager)

    def test_main_and_workflow_agent_roles_are_separated(self) -> None:
        agent_main = (
            SKILLS / "agents" / "references" / "main-agent.md"
        ).read_text(encoding="utf-8")
        agent_workflow = (
            SKILLS / "agents" / "references" / "workflow-agent.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Human interaction", agent_main)
        self.assertIn("delegate immediately to a Work Agent", agent_main)
        self.assertIn("Work Unit", agent_main)
        self.assertIn("Goal preflight", agent_workflow)
        self.assertIn("implementation Work", agent_workflow)
        self.assertIn("never runs verification commands", agent_workflow)
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

    def test_worktree_lifecycle_uses_local_factory_control_branch(self) -> None:
        documents = [
            SKILLS / "agents" / "references" / "main-agent.md",
            SKILLS / "agents" / "references" / "workflow-agent.md",
            SKILLS / "lifecycle" / "references" / "lifecycle-entry.md",
            SKILLS / "lifecycle" / "references" / "lifecycle.md",
            SKILLS / "work-units" / "references" / "work-unit-management.md",
            SKILLS / "work-units" / "references" / "work-unit-execution.md",
            SKILLS / "work-units" / "references" / "worktree-contract.md",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in documents)

        self.assertIn("local `factory`", combined)
        self.assertIn("`baseRef`", combined)
        self.assertIn("`targetBranch`", combined)
        self.assertIn("never pushes `factory`", combined)
        for promotion_target in ("`dev`", "`main`", "`master`", "PR"):
            with self.subTest(promotion_target=promotion_target):
                self.assertIn(promotion_target, combined)

    def test_consolidated_skill_documents_preserve_reference_level_routing(self) -> None:
        references = SKILLS / "intakes" / "references"
        intake_management = (references / "intake-management.md").read_text(
            encoding="utf-8"
        )
        analysis = (references / "analysis.md").read_text(encoding="utf-8")
        web_search = (references / "web-search.md").read_text(encoding="utf-8")
        user_research = (references / "user-research.md").read_text(
            encoding="utf-8"
        )
        interview = (references / "interview.md").read_text(encoding="utf-8")
        lifecycle = (
            SKILLS / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text(encoding="utf-8")
        synchronization = (
            SKILLS
            / "synchronization"
            / "references"
            / "synchronization-management.md"
        ).read_text(encoding="utf-8")

        intake_routes = {
            "references/intake-management.md": intake_management,
            "references/analysis.md": analysis,
            "references/web-search.md": web_search,
            "references/user-research.md": user_research,
            "references/interview.md": interview,
        }
        for route in intake_routes:
            with self.subTest(intake_route=route):
                self.assertIn(f"`{route}`", intake_management)

        for route in (
            "intakes/references/analysis.md",
            "intakes/references/web-search.md",
            "intakes/references/user-research.md",
            "intakes/references/interview.md",
        ):
            with self.subTest(lifecycle_route=route):
                self.assertIn(f"`{route}`", lifecycle)

        cross_routes = {
            "analysis": (
                analysis,
                "references/web-search.md",
                "references/user-research.md",
            ),
            "web-search": (
                web_search,
                "references/analysis.md",
                "references/user-research.md",
            ),
            "user-research": (
                user_research,
                "references/analysis.md",
                "references/web-search.md",
                "references/interview.md",
            ),
            "interview": (interview, "references/user-research.md"),
        }
        for capability, (document, *routes) in cross_routes.items():
            for route in routes:
                with self.subTest(capability=capability, route=route):
                    self.assertIn(f"`{route}`", document)

        self.assertIn("`references/google-drive.md`", synchronization)
        self.assertIn("`references/google-mail.md`", synchronization)

    def test_interview_preserves_execution_and_result_review_boundaries(self) -> None:
        interview = (
            SKILLS / "intakes" / "references" / "interview.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(interview.split())

        self.assertNotIn("Work Unit approval", interview)
        self.assertNotIn("merge approval", interview)
        self.assertIn("explicit Work Unit execution requests", normalized)
        self.assertNotIn("result review (`rework` or `complete`)", normalized)
        self.assertIn("Result review is outside the Interview capability", normalized)
        self.assertIn("Main Agent directly presents only `rework` and `complete`", normalized)
        self.assertIn("`complete` automatically integrates", normalized)

    def test_feedback_first_optional_contracts_are_consistent(self) -> None:
        lifecycle = (
            SKILLS / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text(encoding="utf-8")
        main_agent = (
            SKILLS / "agents" / "references" / "main-agent.md"
        ).read_text(encoding="utf-8")
        work_management = (
            SKILLS / "work-units" / "references" / "work-unit-management.md"
        ).read_text(encoding="utf-8")
        work_manager = (
            SKILLS / "work-units" / "scripts" / "work_unit.py"
        ).read_text(encoding="utf-8")

        self.assertIn("workspace-direct", work_management)
        self.assertIn('"workspace-direct"', work_manager)
        self.assertIn("Human request", work_management)
        self.assertIn("Project Skill", work_management)
        self.assertIn("separate explicit route", work_management)
        self.assertIn("select the smallest bounded command", main_agent)
        self.assertIn("exact supplied command unchanged", lifecycle)

    def test_plugin_manifest_routes_to_all_skills_with_valid_starter_prompts(
        self,
    ) -> None:
        plugin_root = SKILLS.parent
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "agent-factory")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["version"].count("+"), 1)
        self.assertEqual(manifest["version"].count("+codex."), 1)
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
            "synchronization": {
                "jsonschema>=4.0",
                "google-api-python-client",
                "google-auth",
                "google-auth-oauthlib",
            },
            "intakes": {"jsonschema>=4.18,<5"},
            "specifications": {"jsonschema>=4.18,<5"},
            "work-units": {"jsonschema>=4.18,<5"},
        }
        paths = {
            "synchronization": SKILLS / "synchronization" / "scripts" / "requirements.txt",
            "intakes": SKILLS / "intakes" / "scripts" / "requirements.txt",
            "specifications": SKILLS / "specifications" / "scripts" / "requirements.txt",
            "work-units": SKILLS
            / "work-units"
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

    def test_assets_contain_only_non_executable_resources(self) -> None:
        forbidden = sorted(
            path.relative_to(SKILLS)
            for assets in SKILLS.glob("*/assets")
            for path in assets.rglob("*")
            if path.is_file()
            and (path.suffix in {".py", ".pyc"} or path.name == "requirements.txt")
        )
        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
