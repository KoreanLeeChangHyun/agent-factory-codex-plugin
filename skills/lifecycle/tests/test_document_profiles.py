from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


SKILLS = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    SKILLS / "lifecycle" / "assets" / "schema" / "document-profile.schema.json"
)
SPECIFICATION_PROFILE_PATHS = sorted(
    (SKILLS / "specifications" / "assets" / "profiles").glob("*.profile.json")
)
WORK_UNIT_PROFILE_PATH = (
    SKILLS / "work-units" / "assets" / "profiles" / "work-unit.profile.json"
)
WORK_PACKAGE_PROFILE_PATH = (
    SKILLS / "work-units" / "assets" / "profiles" / "work-package.profile.json"
)
PROFILE_PATHS = [
    *SPECIFICATION_PROFILE_PATHS,
    WORK_UNIT_PROFILE_PATH,
    WORK_PACKAGE_PROFILE_PATH,
]


class DocumentProfileTests(unittest.TestCase):
    def test_registered_profiles_follow_common_contract(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for path in PROFILE_PATHS:
            with self.subTest(profile=path.name):
                profile = json.loads(path.read_text(encoding="utf-8"))
                errors = list(validator.iter_errors(profile))
                self.assertEqual(errors, [])
                self.assertEqual(profile["id"], path.name.removesuffix(".profile.json"))
                ids = [
                    section["id"]
                    for field in (
                        "commonRequiredSections",
                        "profileRequiredSections",
                        "optionalSections",
                    )
                    for section in profile[field]
                ]
                self.assertEqual(len(ids), len(set(ids)))

    def test_work_unit_v4_is_implemented_and_anchored(self) -> None:
        profile = json.loads(WORK_UNIT_PROFILE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(profile["implementationStatus"], "implemented")
        self.assertEqual(profile["storageContract"], "sectioned-document-package-v2")
        self.assertEqual(
            [section["id"] for section in profile["profileRequiredSections"]],
            [
                "basis",
                "work-definition",
                "plan",
                "execution-context",
                "acceptance-and-verification",
                "execution",
                "ai-review",
                "human-review",
                "report",
            ],
        )
        planner = (
            SKILLS
            / "work-units"
            / "references"
            / "work-unit-management.md"
        ).read_text(encoding="utf-8")
        common = (
            SKILLS / "lifecycle" / "references" / "common-document-contract.md"
        ).read_text(encoding="utf-8")
        for document in (planner, common):
            self.assertIn("anchor", document)
            self.assertIn("package root", document)

    def test_sectioned_document_manager_is_owned_by_lifecycle(self) -> None:
        common_manager = (
            SKILLS / "lifecycle" / "scripts" / "sectioned_document.py"
        )
        common_schemas = (
            SKILLS / "lifecycle" / "assets" / "schema" / "sectioned-document"
        )
        intake_manager = SKILLS / "intakes" / "scripts" / "intake.py"
        specification_manager = (
            SKILLS / "specifications" / "scripts" / "specification.py"
        )
        work_unit_manager = (
            SKILLS / "work-units" / "scripts" / "work_unit.py"
        )

        self.assertTrue(common_manager.is_file())
        common_source = common_manager.read_text(encoding="utf-8")
        self.assertEqual(common_source.count("def command_create("), 1)
        self.assertEqual(common_source.count("def command_delete("), 1)
        self.assertIn("def add_data_arguments(", common_source)
        self.assertNotIn("--value-file", common_source)
        self.assertEqual(
            {path.name for path in common_schemas.glob("*.schema.json")},
            {
                "title.schema.json",
                "table-of-contents.schema.json",
                "section.schema.json",
                "blocks.schema.json",
            },
        )
        for manager in (intake_manager, specification_manager, work_unit_manager):
            source = manager.read_text(encoding="utf-8")
            self.assertIn("sectioned_document.py", source)
            self.assertIn("configure_contract", source)
            self.assertNotIn("def command_create(", source)
            self.assertNotIn("def command_delete(", source)
            self.assertNotIn("--value-file", source)
            self.assertNotIn("INTAKE_MANAGER", source)
            artifact_schema_root = manager.parents[1] / "assets" / "schema"
            self.assertEqual(
                {path.name for path in artifact_schema_root.glob("*.schema.json")},
                {"metadata.schema.json"},
            )

    def test_artifact_skills_document_complete_crud_contract(self) -> None:
        contract = (
            SKILLS
            / "lifecycle"
            / "references"
            / "common-document-contract.md"
        ).read_text(encoding="utf-8")
        manager_references = {
            "intakes": "intake-management.md",
            "specifications": "specification-management.md",
            "work-units": "work-unit-management.md",
        }
        for skill_name, reference in manager_references.items():
            skill = (
                SKILLS / skill_name / "references" / reference
            ).read_text(encoding="utf-8")
            self.assertIn(
                "delete <package> --confirm-id <id> [--allow-invalid]", skill
            )
        self.assertIn(
            "delete <package> --confirm-id <id> [--allow-invalid]", contract
        )
        self.assertIn("descriptor-anchored", contract)

    def test_project_core_policy_is_single_source_and_profile_driven(self) -> None:
        specification = (
            SKILLS
            / "specifications"
            / "references"
            / "specification-management.md"
        ).read_text(encoding="utf-8")
        lifecycle = (SKILLS / "lifecycle" / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )
        combined = specification + lifecycle
        for obsolete in (
            "Project Core is represented as the fixed top section",
            "Project Core is the short fixed top section",
            "Produce or update Project Core inside",
            "The Design Document and Design Report must define at minimum",
        ):
            self.assertNotIn(obsolete, combined)
        self.assertIn("single canonical", specification)
        self.assertIn("governed-by", specification)
        self.assertIn("without copying", combined)
        self.assertIn("owns the exact common and", specification)

    def test_design_report_is_an_external_view_not_stored_files(self) -> None:
        specification = (
            SKILLS
            / "specifications"
            / "references"
            / "specification-management.md"
        ).read_text(encoding="utf-8")
        lifecycle = (SKILLS / "lifecycle" / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )
        combined = specification + lifecycle
        for obsolete in (
            "Use optional derived `report/`",
            "Design Report is the Human-facing HTML/CSS/JavaScript design artifact",
            "Produce or update the Human-facing Design Report rendering",
        ):
            self.assertNotIn(obsolete, combined)
        self.assertIn("separate Chrome extension", specification)
        self.assertIn(
            "Design Report is not a stored HTML, CSS, or JavaScript artifact", lifecycle
        )
        for forbidden_path in (
            "`report/`",
            "`report/index.html`",
            "`report/styles.css`",
            "`report/script.js`",
        ):
            self.assertIn(forbidden_path, combined)

    def test_specification_profiles_share_only_the_accepted_common_sections(
        self,
    ) -> None:
        expected = [
            "purpose-and-scope",
            "basis-and-relations",
            "decisions-and-open-items",
            "verification-and-traceability",
        ]
        for path in SPECIFICATION_PROFILE_PATHS:
            with self.subTest(profile=path.name):
                profile = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(profile["artifactType"], "specification")
                self.assertEqual(profile["implementationStatus"], "implemented")
                self.assertEqual(
                    profile["storageContract"], "sectioned-document-package-v2"
                )
                self.assertEqual(
                    [section["id"] for section in profile["commonRequiredSections"]],
                    expected,
                )

    def test_traceability_starts_at_ready_intake_and_specification_is_conditional(
        self,
    ) -> None:
        lifecycle = (SKILLS / "lifecycle" / "references" / "lifecycle.md").read_text(
            encoding="utf-8"
        )
        factory_rule = (
            SKILLS / "rules" / "references" / "engineering-rules.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "traceable from Project Core to Design Report to Work Unit",
            lifecycle,
        )
        self.assertIn("traceable from the ready Intake", lifecycle)
        self.assertIn("not applicable", lifecycle)
        for artifact in (
            "canonical Intake",
            "Project Core",
            "Specification",
            "Work Unit",
        ):
            self.assertIn(artifact, factory_rule)

    def test_specification_supporting_sources_use_registered_blocks(self) -> None:
        specification = (
            SKILLS
            / "specifications"
            / "references"
            / "specification-management.md"
        ).read_text(encoding="utf-8")
        diagram = (
            SKILLS / "specifications" / "references" / "diagram.md"
        ).read_text(encoding="utf-8")
        self.assertIn("`blocks/reference/**`", specification)
        self.assertIn("`blocks/diagram/**`", specification)
        self.assertIn("/blocks/diagram/", diagram)
        self.assertNotIn("/<specification-id>/diagram/", diagram)


if __name__ == "__main__":
    unittest.main()
