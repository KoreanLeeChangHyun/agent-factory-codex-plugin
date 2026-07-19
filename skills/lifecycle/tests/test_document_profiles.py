from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


SKILLS = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    SKILLS / "lifecycle" / "assets" / "schema" / "document-profile.schema.json"
)
PROFILE_PATHS = sorted(
    (SKILLS / "specification" / "assets" / "profiles").glob("*.profile.json")
) + [SKILLS / "work-unit-planner" / "assets" / "profiles" / "work-unit.profile.json"]


class DocumentProfileTests(unittest.TestCase):
    def test_registered_profiles_follow_common_contract(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertEqual(len(PROFILE_PATHS), 6)
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
        profile = json.loads(PROFILE_PATHS[-1].read_text(encoding="utf-8"))
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
        planner = (SKILLS / "work-unit-planner" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        common = (
            SKILLS / "lifecycle" / "references" / "common-document-contract.md"
        ).read_text(encoding="utf-8")
        for document in (planner, common):
            self.assertIn("anchor", document)
            self.assertIn("package root", document)

    def test_sectioned_document_manager_is_owned_by_lifecycle(self) -> None:
        common_manager = (
            SKILLS / "lifecycle" / "assets" / "scripts" / "sectioned_document.py"
        )
        common_schemas = (
            SKILLS / "lifecycle" / "assets" / "schema" / "sectioned-document"
        )
        intake_manager = SKILLS / "intake" / "scripts" / "intake.py"
        specification_manager = (
            SKILLS / "specification" / "scripts" / "specification.py"
        )
        work_unit_manager = (
            SKILLS / "work-unit-planner" / "assets" / "scripts" / "work_unit.py"
        )

        self.assertTrue(common_manager.is_file())
        common_source = common_manager.read_text(encoding="utf-8")
        self.assertEqual(common_source.count("def command_create("), 1)
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
            self.assertNotIn("--value-file", source)
            self.assertNotIn("INTAKE_MANAGER", source)
            if manager in (intake_manager, specification_manager):
                artifact_schema_root = manager.parents[1] / "assets" / "schema"
            else:
                artifact_schema_root = manager.parents[1] / "schema"
            self.assertEqual(
                {path.name for path in artifact_schema_root.glob("*.schema.json")},
                {"metadata.schema.json"},
            )

    def test_project_core_policy_is_single_source_and_profile_driven(self) -> None:
        specification = (SKILLS / "specification" / "SKILL.md").read_text(
            encoding="utf-8"
        )
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

    def test_specification_profiles_share_only_the_accepted_common_sections(
        self,
    ) -> None:
        expected = [
            "purpose-and-scope",
            "basis-and-relations",
            "decisions-and-open-items",
            "verification-and-traceability",
        ]
        for path in PROFILE_PATHS[:-1]:
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
        fact_only = (SKILLS / "fact-only" / "SKILL.md").read_text(encoding="utf-8")
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
            self.assertIn(artifact, fact_only)

    def test_specification_supporting_sources_use_registered_blocks(self) -> None:
        specification = (SKILLS / "specification" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        diagram = (SKILLS / "diagram" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`blocks/reference/**`", specification)
        self.assertIn("`blocks/diagram/**`", specification)
        self.assertIn("/blocks/diagram/", diagram)
        self.assertNotIn("/<specification-id>/diagram/", diagram)


if __name__ == "__main__":
    unittest.main()
