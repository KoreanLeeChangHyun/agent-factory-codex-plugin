from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "work-units"
SCRIPT = SKILL_ROOT / "scripts" / "work_unit.py"
INTAKE_SCRIPT = SKILL_ROOT.parent / "intakes" / "scripts" / "intake.py"
SCHEMA_ROOT = SKILL_ROOT / "assets" / "schema"
PROFILE = SKILL_ROOT / "assets" / "profiles" / "work-unit.profile.json"
SCHEMA_NAMES = {
    "metadata.schema.json",
    "title.schema.json",
    "table-of-contents.schema.json",
    "section.schema.json",
    "blocks.schema.json",
}
REQUIRED_SECTIONS = [
    "basis",
    "work-definition",
    "plan",
    "execution-context",
    "acceptance-and-verification",
    "execution",
    "ai-review",
    "human-review",
    "report",
]


def run_cli(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def run_intake(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(INTAKE_SCRIPT), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result


def item(
    item_id: str, kind: str, content: object, **extra: object
) -> dict[str, object]:
    value: dict[str, object] = {"id": item_id, "kind": kind, "content": content}
    value.update(extra)
    return value


def data_args(value: object) -> list[str]:
    arguments: list[str] = []

    def add(path: str, current: object) -> None:
        if isinstance(current, dict):
            if not current:
                arguments.extend(("--empty-object", path))
            for key, child in current.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                add(f"{path}/{escaped}", child)
        elif isinstance(current, list):
            if not current:
                arguments.extend(("--empty-list", path))
            for index, child in enumerate(current):
                add(f"{path}/{index}", child)
        elif isinstance(current, bool):
            arguments.extend(("--boolean", path, str(current).lower()))
        elif isinstance(current, int):
            arguments.extend(("--integer", path, str(current)))
        elif isinstance(current, float):
            arguments.extend(("--number", path, str(current)))
        elif current is None:
            arguments.extend(("--null", path))
        else:
            arguments.extend(("--string", path, str(current)))

    if isinstance(value, (dict, list)):
        if not value:
            raise AssertionError("test data root must not be empty")
        for key, child in (
            value.items() if isinstance(value, dict) else enumerate(value)
        ):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            add(f"/{escaped}", child)
    else:
        raise AssertionError("test data root must be structured")
    return arguments


def data_value(_: Path, __: str, value: object) -> list[str]:
    return data_args(value)


def create_package(root: Path, work_unit_id: str = "sample-unit") -> Path:
    package = root / ".agent-factory" / "work-units" / work_unit_id
    run_cli(
        "create",
        str(package),
        "--id",
        work_unit_id,
        "--title",
        "Sample Work Unit",
        "--project-id",
        "sample-project",
        "--language",
        "ko",
        "--theme",
        "default",
    )
    return package


def create_ready_intake(root: Path, intake_id: str = "source-intake") -> Path:
    package = root / ".agent-factory" / "intakes" / intake_id
    run_intake(
        "create",
        str(package),
        "--id",
        intake_id,
        "--topic",
        "Source Intake",
        "--project-id",
        "sample-project",
        "--language",
        "ko",
    )
    run_intake(
        "entry-put",
        str(package),
        "--string", "/id", "BASIS-001",
        "--string", "/actor/type", "human",
        "--string", "/activity", "user-input",
        "--string", "/content/request", "Implement v4 package",
    )
    run_intake("validate", str(package), "--full")
    return package


def ready_items(
    root: Path, intake: Path, work_unit_id: str = "sample-unit"
) -> dict[str, list[dict[str, object]]]:
    intake_ref = {
        "artifactType": "intake",
        "id": intake.name,
        "path": f".agent-factory/intakes/{intake.name}",
    }
    return {
        "basis": [
            item(
                "BASIS-REF-001",
                "intake-basis-ref",
                {"summary": "Accepted basis", "entryIds": ["BASIS-001"]},
                sourceRefs=[intake_ref],
            )
        ],
        "work-definition": [
            item("GOAL-001", "goal", "Implement the scoped Work Unit"),
            item("SCOPE-001", "scope", ["manager", "schemas"]),
            item("OUT-001", "out-of-scope", ["existing data"]),
            item("OUTPUT-001", "expected-output", "Validated v4 package"),
        ],
        "plan": [item("PLAN-001", "plan-step", "Plan -> Work -> AI Review -> Report")],
        "execution-context": [
            item(
                "EXEC-CONTEXT-001",
                "execution-context",
                {
                    "goalId": work_unit_id,
                    "objective": "Implement the scoped Work Unit",
                    "execInvocation": (
                        "python3 "
                        "skills/work-units/scripts/app_server_goal.py "
                        f"--repository {root} --work-unit-id {work_unit_id}"
                    ),
                    "executionAgent": "Codex",
                    "repository": str(root),
                    "baseRef": "primary-workspace",
                    "executionMode": "workspace-direct",
                    "targetReviewRole": (
                        "review-only; must not modify files or execute "
                        "verification commands"
                    ),
                    "reviewExecution": (
                        "mandatory separate Goal after Documentation Agent completion"
                    ),
                },
            )
        ],
        "acceptance-and-verification": [
            item("AC-001", "acceptance-criterion", "Package validates"),
            item("DOD-001", "definition-of-done", "Evidence recorded"),
            item("TEST-001", "test-criterion", "Regression passes"),
            item(
                "QUALITY-001",
                "quality-check",
                "Not run",
                attributes={"status": "not-run", "evidence": []},
            ),
        ],
        "execution": [
            item(
                "EXECUTION-STATUS",
                "execution-result",
                "Not started",
                attributes={"status": "not-started", "verificationResult": "not-run"},
            )
        ],
        "ai-review": [
            item("AI-CHECKLIST-001", "ai-checklist", ["Scope", "Tests"]),
            item(
                "AI-REVIEW-STATUS",
                "ai-review-result",
                "Not run",
                attributes={"result": "not-run", "checklistResult": "not-run"},
            ),
        ],
        "human-review": [
            item("HUMAN-CHECKLIST-001", "human-checklist", ["Inspect package"]),
            item(
                "HUMAN-METHOD-001", "human-review-method", "Inspect evidence and decide"
            ),
            item(
                "HUMAN-REVIEW-STATUS",
                "human-review-result",
                "Pending",
                attributes={"status": "pending"},
            ),
        ],
        "report": [
            item(
                "REPORT-STATUS",
                "report-result",
                "Not run",
                attributes={"verificationResult": "not-run", "evidence": []},
            )
        ],
    }


def populate_ready_candidate(root: Path, package: Path, intake: Path) -> None:
    for section_id, content in ready_items(root, intake, package.name).items():
        source = data_value(root, f"{section_id}.json", content)
        run_cli("section-items-put", str(package), section_id, *source)
    readiness = data_value(
        root,
        "readiness.json",
        {
            "contractValid": False,
            "intakeTraceabilityValid": True,
            "definitionComplete": True,
            "executionContextComplete": True,
            "verificationPlanComplete": True,
            "reviewedAt": "2026-07-16T00:00:00+00:00",
            "findings": [],
        },
    )
    run_cli("metadata-set", str(package), "readiness", *readiness)


class WorkUnitV4ManagerTests(unittest.TestCase):
    def test_help_exposes_complete_crud_surface(self) -> None:
        help_text = run_cli("--help").stdout
        for command in ("create", "show", "delete", "title-set", "section-put"):
            self.assertIn(command, help_text)

    def test_status_all_reports_sorted_aggregate_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            running = create_package(root, "a-running-unit")
            populate_ready_candidate(root, running, intake)
            run_cli("transition", str(running), "ready")
            self.initialize_and_start_execution(running)
            create_package(root, "z-backlog-unit")

            result = json.loads(
                run_cli(
                    "status",
                    "--all",
                    "--root",
                    str(root / ".agent-factory" / "work-units"),
                ).stdout
            )

            self.assertEqual(result["count"], 2)
            self.assertEqual(result["validCount"], 2)
            self.assertEqual(result["invalidCount"], 0)
            self.assertEqual(
                [entry["id"] for entry in result["workUnits"]],
                ["a-running-unit", "z-backlog-unit"],
            )
            self.assertEqual(
                result["workUnits"][0],
                {
                    "id": "a-running-unit",
                    "lifecycleStatus": "working",
                    "executionState": "running",
                    "reviewStatus": "pending",
                    "validationStatus": "valid",
                },
            )
            self.assertEqual(
                result["workUnits"][1],
                {
                    "id": "z-backlog-unit",
                    "lifecycleStatus": "backlog",
                    "executionState": "not-initialized",
                    "reviewStatus": "not-recorded",
                    "validationStatus": "valid",
                },
            )

    def test_status_all_isolates_invalid_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            create_package(root, "valid-unit")
            broken = root / ".agent-factory" / "work-units" / "broken-unit"
            broken.mkdir()

            result = json.loads(
                run_cli(
                    "status",
                    "--all",
                    "--root",
                    str(root / ".agent-factory" / "work-units"),
                ).stdout
            )

            self.assertEqual(result["count"], 2)
            self.assertEqual(result["validCount"], 1)
            self.assertEqual(result["invalidCount"], 1)
            invalid = result["workUnits"][0]
            self.assertEqual(invalid["id"], "broken-unit")
            self.assertEqual(invalid["validationStatus"], "invalid")
            self.assertIsNone(invalid["lifecycleStatus"])
            self.assertIsNone(invalid["executionState"])
            self.assertIsNone(invalid["reviewStatus"])
            self.assertIn("validationError", invalid)

    def test_status_all_rejects_noncanonical_and_symlink_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / ".agent-factory" / "work-units"
            collection.mkdir(parents=True)
            unrelated = root / "unrelated"
            unrelated.mkdir()
            rejected = run_cli("status", "--all", "--root", str(unrelated), check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(
                "collection must be <project-root>/.agent-factory/work-units",
                rejected.stderr,
            )
            linked = root / "linked-work-units"
            linked.symlink_to(collection, target_is_directory=True)
            rejected = run_cli("status", "--all", "--root", str(linked), check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("must not be a symlink", rejected.stderr)

    def test_delete_valid_package_requires_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)

            denied = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                "different-unit",
                check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("confirmation id must equal", denied.stderr)
            self.assertTrue(package.is_dir())

            deleted = json.loads(
                run_cli(
                    "delete",
                    str(package),
                    "--confirm-id",
                    package.name,
                ).stdout
            )
            self.assertEqual(deleted["id"], package.name)
            self.assertEqual(deleted["path"], str(package))
            self.assertEqual(deleted["validation"], "valid")
            self.assertEqual(deleted["operationResult"], "deleted")
            self.assertFalse(package.exists())

    def test_delete_invalid_legacy_package_requires_explicit_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / ".agent-factory" / "work-units" / "legacy-unit"
            (package / "data").mkdir(parents=True)
            (package / "data" / "work-unit.json").write_text(
                json.dumps(
                    {
                        "id": package.name,
                        "version": "3.0.0",
                        "status": "review",
                    }
                ),
                encoding="utf-8",
            )

            denied = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                package.name,
                check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("requires --allow-invalid", denied.stderr)
            self.assertTrue(package.is_dir())

            deleted = json.loads(
                run_cli(
                    "delete",
                    str(package),
                    "--confirm-id",
                    package.name,
                    "--allow-invalid",
                ).stdout
            )
            self.assertEqual(deleted["validation"], "invalid")
            self.assertEqual(deleted["operationResult"], "deleted")
            self.assertFalse(package.exists())

    def test_delete_invalid_package_rejects_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / ".agent-factory" / "work-units" / "legacy-unit"
            (package / "data").mkdir(parents=True)
            (package / "data" / "work-unit.json").write_text(
                json.dumps(
                    {
                        "id": "different-unit",
                        "version": "3.0.0",
                        "status": "review",
                    }
                ),
                encoding="utf-8",
            )

            denied = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                package.name,
                "--allow-invalid",
                check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("identity does not match", denied.stderr)
            self.assertTrue(package.is_dir())

    def test_delete_rejects_symlink_package_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / ".agent-factory" / "work-units"
            collection.mkdir(parents=True)
            target = root / "outside"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            package = collection / "linked-unit"
            os.symlink(target, package)

            denied = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                package.name,
                "--allow-invalid",
                check=False,
            )
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("must not be a symlink", denied.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_delete_rejects_package_swap_before_rename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            moved = package.parent / "moved-unit"
            spec = importlib.util.spec_from_file_location(
                "work_unit_delete_race_test", SCRIPT
            )
            assert spec is not None and spec.loader is not None
            manager = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(manager)
            original_rename = os.rename
            swapped = False

            def swapping_rename(
                source: str,
                target: str,
                *,
                src_dir_fd: int | None = None,
                dst_dir_fd: int | None = None,
            ) -> None:
                nonlocal swapped
                if source == package.name and not swapped:
                    swapped = True
                    original_rename(
                        source,
                        moved.name,
                        src_dir_fd=src_dir_fd,
                        dst_dir_fd=dst_dir_fd,
                    )
                    os.mkdir(package.name, dir_fd=src_dir_fd)
                    (package / "marker.txt").write_text(
                        "preserve replacement", encoding="utf-8"
                    )
                original_rename(
                    source,
                    target,
                    src_dir_fd=src_dir_fd,
                    dst_dir_fd=dst_dir_fd,
                )

            with mock.patch.object(
                manager.base.os, "rename", side_effect=swapping_rename
            ):
                with self.assertRaisesRegex(
                    manager.ManagerError, "changed during deletion"
                ):
                    manager.base.command_delete(
                        SimpleNamespace(
                            package=str(package),
                            confirm_id=package.name,
                            allow_invalid=False,
                        )
                    )

            self.assertTrue(moved.is_dir())
            self.assertEqual(
                (package / "marker.txt").read_text(encoding="utf-8"),
                "preserve replacement",
            )

    def initialize_and_start_execution(
        self,
        package: Path,
        *,
        invocation_id: str = "session-1",
    ) -> dict[str, object]:
        run_cli("execution-init", str(package))
        return json.loads(
            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                invocation_id,
            ).stdout
        )

    def current_execution_target(self, package: Path) -> dict[str, object]:
        shown = json.loads(
            run_cli("show", str(package), "--section", "execution-context").stdout
        )
        state = next(
            entry for entry in shown["content"] if entry["kind"] == "execution-state"
        )["content"]
        return {
            "contractVersion": state["contractVersion"],
            "revision": state["currentRevision"],
            "attempt": state["currentAttempt"],
            "invocationId": state["invocationId"],
        }

    def test_schemas_and_profile_define_v4_sectioned_contract(self) -> None:
        payload = json.loads(run_cli("check-schemas").stdout)
        self.assertEqual(payload["schemaVersion"], "4.0.0")
        self.assertEqual(set(payload["schemas"]), SCHEMA_NAMES)
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["version"], "4.0.0")
        self.assertEqual(profile["implementationStatus"], "implemented")
        self.assertEqual(profile["storageContract"], "sectioned-document-package-v2")
        self.assertEqual(
            [entry["id"] for entry in profile["profileRequiredSections"]],
            REQUIRED_SECTIONS,
        )

    def test_create_builds_common_sectioned_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            self.assertFalse((package / "data" / "work-unit.json").exists())
            self.assertTrue((package / "data" / "metadata.json").is_file())
            self.assertTrue((package / "data" / "title.json").is_file())
            self.assertTrue((package / "data" / "table-of-contents.json").is_file())
            self.assertTrue((package / "blocks" / "index.json").is_file())
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(
                [entry["id"] for entry in toc["sections"]], REQUIRED_SECTIONS
            )
            result = json.loads(run_cli("validate", str(package), "--full").stdout)
            self.assertEqual(result["status"], "backlog")
            self.assertEqual(result["schemaVersion"], "4.0.0")

    def test_batch_update_increments_one_document_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            source = data_value(
                root,
                "batch.json",
                [
                    item(f"PLAN-{index:04d}", "plan-step", index)
                    for index in range(1000)
                ],
            )
            run_cli("section-items-put", str(package), "plan", *source)
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.1")
            shown = json.loads(
                run_cli("show", str(package), "--section", "plan").stdout
            )
            self.assertEqual(len(shown["content"]), 1000)

    def test_optional_section_lifecycle_preserves_required_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section = {
                "id": "rework-history",
                "title": "Rework History",
                "content": [],
                "subsections": [],
            }
            source = data_value(root, "optional.json", section)
            run_cli(
                "section-add",
                str(package),
                *source,
                "--after",
                "report",
            )
            run_cli("section-move", str(package), "rework-history", "--before", "basis")
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(toc["sections"][0]["id"], "rework-history")
            run_cli("section-remove", str(package), "rework-history")
            self.assertFalse(
                (package / "data" / "sections" / "rework-history.json").exists()
            )
            self.assertTrue(
                json.loads(run_cli("validate", str(package)).stdout)["valid"]
            )

    def test_ready_transition_resolves_package_root_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            result = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["validationMode"], "full")

    def test_ready_rejects_intake_path_swap_after_fd_bound_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)

            manager_spec = importlib.util.spec_from_file_location(
                "work_unit_intake_swap_test", SCRIPT
            )
            assert manager_spec is not None and manager_spec.loader is not None
            manager = importlib.util.module_from_spec(manager_spec)
            manager_spec.loader.exec_module(manager)

            intake_spec = importlib.util.spec_from_file_location(
                "intake_swap_validation_delegate", INTAKE_SCRIPT
            )
            assert intake_spec is not None and intake_spec.loader is not None
            intake_manager = importlib.util.module_from_spec(intake_spec)
            intake_spec.loader.exec_module(intake_manager)
            original_spec_from_file = importlib.util.spec_from_file_location
            moved = intake.with_name("held-source-intake")

            class SwapValidationLoader:
                def create_module(self, _spec: object) -> None:
                    return None

                def exec_module(self, module: object) -> None:
                    module.ManagerError = intake_manager.ManagerError

                    def validate_package(*args: object, **kwargs: object) -> object:
                        result = intake_manager.validate_package(*args, **kwargs)
                        intake.rename(moved)
                        shutil.copytree(moved, intake)
                        return result

                    module.validate_package = validate_package

            def swapping_spec(name: str, location: object, *args: object, **kwargs: object):
                if name == "agent_factory_intake_validation":
                    return importlib.util.spec_from_loader(
                        name, SwapValidationLoader()
                    )
                return original_spec_from_file(name, location, *args, **kwargs)

            with mock.patch.object(
                manager.importlib.util,
                "spec_from_file_location",
                side_effect=swapping_spec,
            ):
                with self.assertRaisesRegex(
                    manager.ManagerError, "changed during validation"
                ):
                    manager.validate_ready_semantics(package)

    def test_shared_intake_mutation_policy_does_not_reopen_working_work_unit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            before = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            update = data_value(
                root, "working-update.json", item("PLAN-002", "plan-step", "Execute")
            )

            run_cli("section-item-put", str(package), "plan", *update)

            after = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(after["lifecycle"]["status"], "working")
            self.assertEqual(after["readiness"], before["readiness"])

    def test_missing_anchor_item_rejected_without_mutating_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relation = data_value(
                root,
                "relations.json",
                [
                    {
                        "type": "based-on",
                        "target": {
                            "artifactType": "intake",
                            "id": intake.name,
                            "path": f".agent-factory/intakes/{intake.name}",
                            "anchor": {
                                "sectionId": "work-unit-basis",
                                "itemId": "MISSING",
                            },
                        },
                    }
                ],
            )
            result = run_cli(
                "metadata-set",
                str(package),
                "relations",
                *relation,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("data/table-of-contents.json", result.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

    def test_anchor_path_must_target_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            source = data_value(
                root,
                "bad-basis.json",
                item(
                    "BASIS-REF-001",
                    "intake-basis-ref",
                    "Bad path",
                    sourceRefs=[
                        {
                            "artifactType": "intake",
                            "id": intake.name,
                            "path": f".agent-factory/intakes/{intake.name}/data/sections/work-unit-basis.json",
                            "anchor": {
                                "sectionId": "work-unit-basis",
                                "itemId": "BASIS-001",
                            },
                        }
                    ],
                ),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "basis",
                *source,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("typed reference does not exist", result.stderr)

    def test_ready_rejects_missing_required_kind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            content = ready_items(root, intake, package.name)
            content["work-definition"] = [
                entry
                for entry in content["work-definition"]
                if entry["kind"] != "expected-output"
            ]
            for section_id, items in content.items():
                source = data_value(root, f"invalid-{section_id}.json", items)
                run_cli(
                    "section-items-put",
                    str(package),
                    section_id,
                    *source,
                )
            readiness = data_value(
                root,
                "readiness.json",
                {
                    "contractValid": True,
                    "intakeTraceabilityValid": True,
                    "definitionComplete": True,
                    "executionContextComplete": True,
                    "verificationPlanComplete": True,
                    "reviewedAt": "2026-07-16T00:00:00+00:00",
                    "findings": [],
                },
            )
            run_cli(
                "metadata-set",
                str(package),
                "readiness",
                *readiness,
            )
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required content kinds", result.stderr)

    def test_ready_rejects_direct_codex_exec_and_requires_goal_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"]["execInvocation"] = (
                f"codex exec -C {root} "
                "'Execute the Work Unit'"
            )
            source = data_value(root, "direct-codex-exec-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )

            rejected = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("must call app_server_goal.py", rejected.stderr)

            context["content"]["execInvocation"] = (
                "python3 skills/work-units/scripts/app_server_goal.py "
                f"--repository {root} --work-unit-id {package.name}"
            )
            source = data_value(root, "valid-exec-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )
            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")

    def test_ready_rejects_removed_git_isolation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"]["branch"] = "legacy/task"
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "removed-git-field.json", context),
            )

            rejected = run_cli("transition", str(package), "ready", check=False)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("must omit removed Git isolation fields", rejected.stderr)

    def test_review_role_context_requires_complete_field_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"].pop("reviewExecution")
            source = data_value(root, "partial-review-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )

            rejected = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(
                "review-separated execution context is missing fields",
                rejected.stderr,
            )

            context["content"]["reviewExecution"] = (
                "mandatory separate Goal after Documentation Agent completion"
            )
            source = data_value(root, "complete-review-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )
            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")

    def test_current_profile_allows_unselected_review_role_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"].pop("targetReviewRole")
            context["content"].pop("reviewExecution")
            source = data_value(root, "current-profile-review-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )

            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")

    def test_ready_rejects_omitted_execution_mode_and_review_role_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"].pop("executionMode")
            context["content"].pop("targetReviewRole")
            context["content"].pop("reviewExecution")
            source = data_value(root, "missing-required-execution-context.json", context)
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *source,
            )

            rejected = run_cli("transition", str(package), "ready", check=False)

            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(
                "execution context executionMode must be workspace-direct or "
                "specification-direct",
                rejected.stderr,
            )

    def test_workspace_direct_accepts_human_request_basis_without_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)

            basis = item(
                "BASIS-REF-001",
                "work-basis-ref",
                {
                    "basisType": "human-request",
                    "request": "Implement the bounded Work Unit",
                },
            )
            run_cli(
                "section-item-put",
                str(package),
                "basis",
                *data_value(root, "human-work-basis.json", basis),
            )
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"]["executionMode"] = "workspace-direct"
            context["content"].pop("targetReviewRole")
            context["content"].pop("reviewExecution")
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "workspace-direct-context.json", context),
            )

            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")

    def test_execution_attempt_retry_and_resume_preserve_identity_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")

            started = self.initialize_and_start_execution(package)
            self.assertEqual(started["status"], "working")
            shown = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["contractVersion"], "2.0.0")
            self.assertEqual(state["currentRevision"], 1)
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(state["invocationId"], "session-1")
            self.assertEqual(state["invocationChain"], ["session-1"])
            self.assertNotIn("subject", state)
            self.assertEqual(state["history"], [])

            run_cli(
                "attempt-resume",
                str(package),
                "--invocation-id",
                "session-1-resume",
            )
            resumed = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in resumed["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(state["invocationId"], "session-1")
            self.assertEqual(
                state["invocationChain"], ["session-1", "session-1-resume"]
            )

            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-2",
            )
            retried = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in retried["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentRevision"], 1)
            self.assertEqual(state["currentAttempt"], 2)
            self.assertEqual(state["invocationId"], "session-2")
            self.assertEqual(state["invocationChain"], ["session-2"])
            self.assertNotIn("subject", state)
            self.assertEqual(len(state["history"]), 1)
            self.assertEqual(state["history"][0]["revision"], 1)
            self.assertEqual(state["history"][0]["attempt"], 1)
            self.assertEqual(
                state["history"][0]["invocationChain"],
                ["session-1", "session-1-resume"],
            )
            before = (
                package / "data" / "sections" / "execution-context.json"
            ).read_bytes()
            duplicate = run_cli(
                "attempt-resume",
                str(package),
                "--invocation-id",
                "session-1-resume",
                check=False,
            )
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("must be unique in execution history", duplicate.stderr)
            self.assertEqual(
                (package / "data" / "sections" / "execution-context.json").read_bytes(),
                before,
            )

    def test_specification_direct_execution_uses_primary_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"]["executionMode"] = "specification-direct"
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "specification-direct.json", context),
            )
            ready = json.loads(run_cli("transition", str(package), "ready").stdout)
            started = self.initialize_and_start_execution(package)

            self.assertEqual(ready["status"], "ready")
            self.assertEqual(started["status"], "working")

    def test_active_execution_requires_init_and_state_is_manager_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            obsolete = run_cli(
                "execution-init",
                str(package),
                "--head-commit",
                "a" * 40,
                check=False,
            )
            self.assertNotEqual(obsolete.returncode, 0)
            self.assertIn("unrecognized arguments", obsolete.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

            rejected = run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-1",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("requires execution-init", rejected.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

            direct_state = item(
                "EXECUTION-STATE-001",
                "execution-state",
                {
                    "contractVersion": "2.0.0",
                    "state": "planned",
                    "currentRevision": 1,
                    "currentAttempt": None,
                    "invocationId": None,
                    "invocationChain": [],
                    "history": [],
                },
            )
            rejected = run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "direct-state.json", direct_state),
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("execution-state is manager-owned", rejected.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

    def test_rework_invalidates_results_and_review_rejects_stale_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, f"replace-{section_id}.json", replacement),
                )
            run_cli("transition", str(package), "review")
            missing = run_cli(
                "rework-start",
                str(package),
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("requires --instruction", missing.stderr)
            run_cli(
                "rework-start",
                str(package),
                "--instruction",
                "Commit the implementation and rebind all evidence to that commit.",
            )
            run_cli(
                "attempt-start",
                str(package),
                "--invocation-id",
                "session-2",
            )

            shown = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentRevision"], 2)
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(
                state["reworkInstruction"],
                "Commit the implementation and rebind all evidence to that commit.",
            )
            self.assertEqual(len(state["history"]), 1)
            self.assertEqual(
                state["history"][0]["outcomes"]["report-result"]["attributes"][
                    "verificationResult"
                ],
                "pass",
            )
            execution = json.loads(
                run_cli("show", str(package), "--section", "execution").stdout
            )["content"][0]
            self.assertEqual(execution["attributes"]["status"], "pending")

            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, f"stale-{section_id}.json", replacement),
                )
            rejected = run_cli("transition", str(package), "review", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("current execution target", rejected.stderr)

    def test_existing_done_v4_without_execution_state_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            for section_id, replacement in replacements.items():
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *data_value(root, section_id, replacement),
                )
            run_cli("transition", str(package), "review")
            run_cli(
                "transition",
                str(package),
                "done",
                "--review-decision",
                "complete",
            )

            report_path = package / "data" / "sections" / "report.json"
            report_before = report_path.read_bytes()
            immutable = run_cli(
                "section-item-put",
                str(package),
                "report",
                *data_value(
                    root,
                    "mutated-done-report.json",
                    item(
                        "REPORT-STATUS",
                        "report-result",
                        "Changed after approval",
                        attributes={
                            "verificationResult": "pass",
                            "evidence": ["blocks/logs/tests.log"],
                            "executionTarget": target,
                        },
                    ),
                ),
                check=False,
            )
            self.assertNotEqual(immutable.returncode, 0)
            self.assertIn(
                "done Work Unit outcome records are immutable", immutable.stderr
            )
            self.assertEqual(report_path.read_bytes(), report_before)

            human_review_path = package / "data" / "sections" / "human-review.json"
            human_review = json.loads(human_review_path.read_text(encoding="utf-8"))
            decision = next(
                entry
                for entry in human_review["content"]
                if entry["kind"] == "human-review-result"
            )
            decision["attributes"]["executionTarget"]["invocationId"] = "stale-session"
            human_review_path.write_text(
                json.dumps(human_review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            stale = run_cli("validate", str(package), "--full", check=False)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("human-review-result decision", stale.stderr)

            execution_context_path = (
                package / "data" / "sections" / "execution-context.json"
            )
            execution_context = json.loads(
                execution_context_path.read_text(encoding="utf-8")
            )
            execution_context["content"] = [
                entry
                for entry in execution_context["content"]
                if entry["kind"] != "execution-state"
            ]
            execution_context_path.write_text(
                json.dumps(execution_context, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(
                json.loads(run_cli("validate", str(package), "--full").stdout)["valid"]
            )

    def test_review_and_done_transitions_enforce_results_and_atomic_review_decision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            context = ready_items(root, intake, package.name)["execution-context"][0]
            context["content"].update(
                {
                    "targetReviewRole": (
                        "review-only; must not modify files or execute "
                        "verification commands"
                    ),
                    "reviewExecution": (
                        "mandatory separate Goal after Documentation Agent completion"
                    ),
                }
            )
            run_cli(
                "section-item-put",
                str(package),
                "execution-context",
                *data_value(root, "review-context.json", context),
            )
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            target = self.current_execution_target(package)
            premature = run_cli("transition", str(package), "review", check=False)
            self.assertNotEqual(premature.returncode, 0)
            self.assertIn(
                "review transition requires passing execution", premature.stderr
            )

            replacements = {
                "execution": item(
                    "EXECUTION-STATUS",
                    "execution-result",
                    "Complete",
                    attributes={
                        "status": "complete",
                        "verificationResult": "pass",
                        "executionTarget": target,
                    },
                ),
                "acceptance-and-verification": item(
                    "QUALITY-001",
                    "quality-check",
                    "Pass",
                    attributes={
                        "status": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "ai-review": item(
                    "AI-REVIEW-STATUS",
                    "ai-review-result",
                    "Pass",
                    attributes={
                        "result": "pass",
                        "checklistResult": "pass",
                        "sourceRole": "Review Agent",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
                "report": item(
                    "REPORT-STATUS",
                    "report-result",
                    "Pass",
                    attributes={
                        "verificationResult": "pass",
                        "evidence": ["blocks/logs/tests.log"],
                        "executionTarget": target,
                    },
                ),
            }
            block = root / "tests.log"
            block.write_text("tests passed\n", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(block),
                "--path",
                "blocks/logs/tests.log",
                "--media-type",
                "text/plain",
                "--description",
                "tests",
            )
            invalid_ai_review = dict(replacements["ai-review"])
            invalid_ai_review["sourceRole"] = invalid_ai_review["attributes"].pop(
                "sourceRole"
            )
            rejected_location = run_cli(
                "section-item-put",
                str(package),
                "ai-review",
                *data_value(
                    root,
                    "invalid-ai-review-source-role.json",
                    invalid_ai_review,
                ),
                check=False,
            )
            self.assertNotEqual(rejected_location.returncode, 0)
            self.assertIn(
                "Additional properties are not allowed",
                rejected_location.stderr,
            )
            replacements["ai-review"]["attributes"]["sourceRole"] = "Review Agent"
            for section_id, replacement in replacements.items():
                source = data_value(root, f"replace-{section_id}.json", replacement)
                run_cli(
                    "section-item-put",
                    str(package),
                    section_id,
                    *source,
                )
            self.assertEqual(
                json.loads(run_cli("transition", str(package), "review").stdout)[
                    "status"
                ],
                "review",
            )
            ai_review = json.loads(
                run_cli("show", str(package), "--section", "ai-review").stdout
            )["content"]
            result = next(
                entry for entry in ai_review if entry["kind"] == "ai-review-result"
            )
            self.assertEqual(result["attributes"]["sourceRole"], "Review Agent")
            denied = run_cli("transition", str(package), "done", check=False)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn(
                "requires --review-decision complete", denied.stderr
            )
            done = json.loads(
                run_cli(
                    "transition",
                    str(package),
                    "done",
                    "--review-decision",
                    "complete",
                ).stdout
            )
            self.assertEqual(done["status"], "done")
            shown = json.loads(
                run_cli("show", str(package), "--section", "human-review").stdout
            )
            status = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "human-review-result"
            )
            self.assertEqual(status["attributes"]["status"], "complete")
            self.assertIn("decidedAt", status["attributes"])

    def test_orphan_block_style_data_and_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            orphan = package / "blocks" / "orphan.log"
            orphan.write_text("orphan", encoding="utf-8")
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("block file set", result.stderr)
            orphan.unlink()
            styled = data_value(
                root,
                "styled.json",
                item("STYLE-001", "plan-step", {"style": {"color": "red"}}),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "plan",
                *styled,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("actual style", result.stderr)

            source = root / "evidence.log"
            source.write_text("evidence", encoding="utf-8")
            run_cli(
                "block-put",
                str(package),
                str(source),
                "--path",
                "blocks/evidence.log",
                "--media-type",
                "text/plain",
                "--description",
                "evidence",
            )
            (package / "blocks" / "evidence.log").write_text(
                "tampered", encoding="utf-8"
            )
            result = run_cli("validate", str(package), "--full", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("block integrity mismatch", result.stderr)

    def test_interrupted_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            title_path = package / "data" / "title.json"
            original = title_path.read_bytes()
            transaction_root = package / ".manager" / "transactions" / "interrupted"
            backup = transaction_root / "backup" / "0.old"
            backup.parent.mkdir(parents=True)
            backup.write_bytes(original)
            title_path.write_text("{invalid", encoding="utf-8")
            journal = {
                "version": 1,
                "id": "interrupted",
                "entries": [
                    {
                        "path": "data/title.json",
                        "existed": True,
                        "backup": "backup/0.old",
                        "stage": "stage/0.new",
                    }
                ],
            }
            journal_path = package / ".manager" / "transaction.json"
            journal_path.parent.mkdir(exist_ok=True)
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            self.assertTrue(
                json.loads(run_cli("validate", str(package)).stdout)["valid"]
            )
            self.assertEqual(title_path.read_bytes(), original)
            self.assertFalse(journal_path.exists())

    def test_toc_digest_owns_section_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            toc_path = package / "data" / "table-of-contents.json"
            toc = json.loads(toc_path.read_text())
            toc["sections"].reverse()
            toc_path.write_text(json.dumps(toc), encoding="utf-8")
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("table of contents integrity", result.stderr)

    def test_durable_progress_replay_and_blocked_attempt_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intake = create_ready_intake(root)
            package = create_package(root)
            populate_ready_candidate(root, package, intake)
            run_cli("transition", str(package), "ready")
            self.initialize_and_start_execution(package)
            pending = run_cli(
                "execution-progress",
                str(package),
                "--step-id",
                "work",
                "--state",
                "pending",
                "--idempotency-key",
                "revision-1-attempt-1-work",
            )
            self.assertEqual(json.loads(pending.stdout)["status"], "working")
            metadata_path = package / "data" / "metadata.json"
            version = json.loads(metadata_path.read_text())["documentVersion"]
            replay = run_cli(
                "execution-progress",
                str(package),
                "--step-id",
                "work",
                "--state",
                "pending",
                "--idempotency-key",
                "revision-1-attempt-1-work",
            )
            self.assertEqual(json.loads(replay.stdout)["status"], "working")
            self.assertEqual(
                json.loads(metadata_path.read_text())["documentVersion"], version
            )

            first_failure = json.loads(
                run_cli(
                    "execution-failure",
                    str(package),
                    "--step-id",
                    "work",
                    "--classification",
                    "transient",
                    "--max-retries",
                    "2",
                    "--evidence",
                    "temporary timeout",
                    "--idempotency-key",
                    "work-failure-1",
                ).stdout
            )
            self.assertEqual(first_failure["status"], "working")
            replayed_failure = json.loads(
                run_cli(
                    "execution-failure",
                    str(package),
                    "--step-id",
                    "work",
                    "--classification",
                    "transient",
                    "--max-retries",
                    "2",
                    "--evidence",
                    "temporary timeout",
                    "--idempotency-key",
                    "work-failure-1",
                ).stdout
            )
            self.assertEqual(replayed_failure["status"], "working")
            blocked = json.loads(
                run_cli(
                    "execution-failure",
                    str(package),
                    "--step-id",
                    "work",
                    "--classification",
                    "transient",
                    "--max-retries",
                    "2",
                    "--evidence",
                    "retry exhausted",
                    "--idempotency-key",
                    "work-failure-2",
                    "--blocker-id",
                    "BLOCKER-001",
                ).stdout
            )
            self.assertEqual(blocked["status"], "blocked")

            resumed = json.loads(
                run_cli(
                    "blocker-resolve",
                    str(package),
                    "--blocker-id",
                    "BLOCKER-001",
                    "--resolution-evidence",
                    "dependency recovered",
                    "--invocation-id",
                    "session-2",
                ).stdout
            )
            self.assertEqual(resumed["status"], "working")
            shown = json.loads(
                run_cli("show", str(package), "--section", "execution-context").stdout
            )
            state = next(
                entry
                for entry in shown["content"]
                if entry["kind"] == "execution-state"
            )["content"]
            self.assertEqual(state["currentRevision"], 1)
            self.assertEqual(state["currentAttempt"], 1)
            self.assertEqual(state["invocationChain"], ["session-1", "session-2"])
            self.assertEqual(state["progress"]["pendingStep"], "work")
            self.assertEqual(state["progress"]["retry"]["work"]["count"], 2)
            self.assertEqual(state["recovery"]["status"], "running")


if __name__ == "__main__":
    unittest.main()
