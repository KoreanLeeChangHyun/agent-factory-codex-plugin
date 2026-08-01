from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "intake.py"
SCHEMA_ROOT = SKILL_ROOT / "assets" / "schema"
PROFILE = SKILL_ROOT / "assets" / "profiles" / "intake.profile.json"
REQUIRED_SECTIONS = [
    "request-and-goal",
    "context-and-scope",
    "stakeholders-and-approval",
    "evidence-and-findings",
    "requirements-and-constraints",
    "decisions-and-open-items",
    "work-unit-basis",
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


def create_package(root: Path, intake_id: str = "sample-intake") -> Path:
    package = root / ".agent-factory" / "intakes" / intake_id
    run_cli(
        "create",
        str(package),
        "--id",
        intake_id,
        "--title",
        "Sample Intake",
        "--project-id",
        "sample-project",
        "--language",
        "ko",
        "--theme",
        "default",
    )
    return package


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


def item(
    item_id: str, kind: str, content: object, **attributes: object
) -> dict[str, object]:
    value: dict[str, object] = {"id": item_id, "kind": kind, "content": content}
    if attributes:
        value["attributes"] = attributes
    return value


def load_manager() -> object:
    spec = importlib.util.spec_from_file_location("intake_manager_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load Intake manager: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def populate_ready_intake(
    root: Path,
    package: Path,
    *,
    evidence_kind: str = "evidence",
    specification_status: str = "aligned",
) -> None:
    required_items = {
        "request-and-goal": [
            item("REQUEST-001", "human-request", "Intake 고도화"),
            item("OUTCOME-001", "desired-outcome", "실행 가능한 Work Unit basis"),
            item("SUCCESS-001", "success-criterion", "검증 통과"),
        ],
        "context-and-scope": [
            item("CONTEXT-001", "context", "현재 Intake v2"),
            item("SCOPE-001", "scope", "Intake manager"),
            item("OUT-001", "out-of-scope", "기존 데이터 migration"),
        ],
        "stakeholders-and-approval": [
            item("STAKEHOLDER-001", "stakeholder", "Human"),
            item("OWNER-001", "decision-owner", "Human"),
            item("APPROVAL-001", "approval-boundary", "Human Review"),
        ],
        "evidence-and-findings": [item("EVIDENCE-001", evidence_kind, "검증 근거")],
        "requirements-and-constraints": [
            item("REQUIREMENT-001", "requirement", "필수 섹션 검증"),
            item("AC-001", "acceptance-criterion", "누락 시 거부"),
        ],
        "decisions-and-open-items": [
            item("DECISION-001", "decision-status", "결정 완료"),
            item("OPEN-STATUS-001", "open-items-status", "차단 항목 없음"),
        ],
        "work-unit-basis": [
            item(
                "SPEC-001",
                "specification-impact",
                {"status": specification_status},
                status=specification_status,
            ),
            item("BASIS-001", "work-unit-basis", "manager 구현"),
        ],
    }
    for section_id, items in required_items.items():
        source = data_value(root, f"{section_id}.json", items)
        run_cli("section-items-put", str(package), section_id, *source)
    readiness = data_value(
        root,
        "readiness.json",
        {
            "contractValid": False,
            "evidenceComplete": True,
            "requirementsComplete": True,
            "specificationConsistent": True,
            "executionReady": True,
            "reviewedAt": "2026-07-16T00:00:00+00:00",
            "findings": [],
        },
    )
    run_cli("metadata-set", str(package), "readiness", *readiness)
    run_cli("transition", str(package), "validating")


class IntakeManagerTests(unittest.TestCase):
    def test_help_exposes_complete_crud_surface(self) -> None:
        help_text = run_cli("--help").stdout
        for command in ("create", "show", "delete", "title-set", "section-put"):
            self.assertIn(command, help_text)

    def test_delete_valid_package_requires_exact_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))

            denied = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                "different-intake",
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

    def test_delete_invalid_package_requires_opt_in_and_matching_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["theme"] = 7
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
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

            metadata["id"] = "different-intake"
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            mismatch = run_cli(
                "delete",
                str(package),
                "--confirm-id",
                package.name,
                "--allow-invalid",
                check=False,
            )
            self.assertNotEqual(mismatch.returncode, 0)
            self.assertIn("identity does not match", mismatch.stderr)
            self.assertTrue(package.is_dir())

            metadata["id"] = package.name
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
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
            self.assertFalse(package.exists())

    def test_delete_rejects_symlink_package_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / ".agent-factory" / "intakes"
            collection.mkdir(parents=True)
            target = root / "outside"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            package = collection / "linked-intake"
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
            moved = package.parent / "moved-intake"
            manager = load_manager()
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
                    manager.base.ManagerError, "changed during deletion"
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

    def test_manager_constructs_json_from_typed_data_and_rejects_json_input(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                "--string",
                "/id",
                "REQUEST-001",
                "--string",
                "/kind",
                "human-request",
                "--string",
                "/content/request",
                "스크립트가 JSON을 생성한다.",
            )
            section = json.loads(
                (package / "data" / "sections" / "request-and-goal.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                section["content"][0]["content"]["request"],
                "스크립트가 JSON을 생성한다.",
            )
            rejected = run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                '{"id":"REQUEST-002"}',
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("unrecognized arguments", rejected.stderr)

    def test_check_schemas_and_profile(self) -> None:
        payload = json.loads(run_cli("check-schemas").stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["schemaVersion"], "2.0.0")
        self.assertEqual(payload["profile"], "intake@2.0.0")
        self.assertEqual(
            [
                entry["id"]
                for entry in json.loads(PROFILE.read_text())["requiredSections"]
            ],
            REQUIRED_SECTIONS,
        )
        self.assertEqual(
            set(payload["schemas"]),
            {
                "metadata.schema.json",
                "title.schema.json",
                "table-of-contents.schema.json",
                "section.schema.json",
                "blocks.schema.json",
            },
        )

    def test_create_builds_split_package_and_generated_toc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            self.assertFalse((package / "data" / "intake.json").exists())
            self.assertTrue((package / "data" / "metadata.json").is_file())
            self.assertTrue((package / "data" / "title.json").is_file())
            self.assertTrue((package / "data" / "table-of-contents.json").is_file())
            self.assertTrue((package / "blocks" / "index.json").is_file())
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(
                [entry["id"] for entry in toc["sections"]], REQUIRED_SECTIONS
            )
            self.assertEqual(
                len(list((package / "data" / "sections").glob("*.json"))), 7
            )
            payload = json.loads(run_cli("validate", str(package)).stdout)
            self.assertEqual(payload["status"], "draft")
            self.assertEqual(payload["sectionCount"], 7)

    def test_title_set_and_section_item_put_are_manager_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            run_cli("title-set", str(package), "갱신된 Intake")
            candidate = data_value(
                root, "item.json", item("REQ-001", "human-request", "요청")
            )
            run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                *candidate,
            )
            replacement = data_value(
                root,
                "replacement.json",
                item("REQ-001", "human-request", "수정된 요청"),
            )
            run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                *replacement,
            )
            shown = json.loads(
                run_cli("show", str(package), "--section", "request-and-goal").stdout
            )
            self.assertEqual(
                shown["content"], [item("REQ-001", "human-request", "수정된 요청")]
            )
            self.assertEqual(
                json.loads((package / "data" / "title.json").read_text())["title"],
                "갱신된 Intake",
            )
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.3")

    def test_interrupted_transaction_recovery_restores_preimage(self) -> None:
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
            self.assertFalse(transaction_root.exists())

    def test_commit_rejects_symlinked_parent_escape(self) -> None:
        manager = load_manager()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            outside = root / "outside"
            outside.mkdir()
            escaped = outside / "escaped.json"
            escaped.write_text("preserve", encoding="utf-8")
            (package / "data" / "redirect").symlink_to(
                outside, target_is_directory=True
            )

            with self.assertRaises(manager.ManagerError):
                manager.commit_transaction(
                    package,
                    json_writes={
                        package / "data" / "redirect" / "escaped.json": {
                            "changed": True
                        }
                    },
                )

            self.assertEqual(escaped.read_text(encoding="utf-8"), "preserve")

    def test_commit_rejects_symlinked_transaction_state_root(self) -> None:
        manager = load_manager()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            outside = root / "outside-transactions"
            outside.mkdir()
            manager_root = package / ".manager"
            manager_root.mkdir()
            (manager_root / "transactions").symlink_to(
                outside, target_is_directory=True
            )
            title = package / "data" / "title.json"
            before = title.read_bytes()

            with self.assertRaises(manager.ManagerError):
                manager.commit_transaction(
                    package, json_writes={title: {"title": "blocked"}}
                )

            self.assertEqual(title.read_bytes(), before)
            self.assertEqual(list(outside.iterdir()), [])

    def test_commit_resists_parent_symlink_swap_between_check_and_use(self) -> None:
        manager = load_manager()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            redirect = package / "data" / "redirect"
            redirect.mkdir()
            target = redirect / "escaped.json"
            target.write_text("inside", encoding="utf-8")
            outside = root / "outside-race"
            outside.mkdir()
            escaped = outside / "escaped.json"
            escaped.write_text("outside-preserve", encoding="utf-8")
            original_check = manager.base.checked_package_target
            swapped = False

            def racing_check(package_path: Path, candidate: Path, label: str) -> Path:
                nonlocal swapped
                relative = original_check(package_path, candidate, label)
                if (
                    candidate == target
                    and label == "transaction target"
                    and not swapped
                ):
                    redirect.rename(package / "data" / "redirect-original")
                    redirect.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return relative

            manager.base.checked_package_target = racing_check
            try:
                with self.assertRaises(manager.ManagerError):
                    manager.commit_transaction(
                        package, json_writes={target: {"changed": True}}
                    )
            finally:
                manager.base.checked_package_target = original_check

            self.assertTrue(swapped)
            self.assertEqual(escaped.read_text(encoding="utf-8"), "outside-preserve")

    def test_recovery_rejects_symlinked_parent_escape_and_preserves_outside_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            outside = root / "outside"
            outside.mkdir()
            escaped = outside / "escaped.json"
            escaped.write_text("preserve", encoding="utf-8")
            (package / "data" / "redirect").symlink_to(
                outside, target_is_directory=True
            )
            transaction_root = package / ".manager" / "transactions" / "interrupted"
            backup = transaction_root / "backup" / "0.old"
            backup.parent.mkdir(parents=True)
            backup.write_text("overwritten", encoding="utf-8")
            journal = {
                "version": 1,
                "id": "interrupted",
                "entries": [
                    {
                        "path": "data/redirect/escaped.json",
                        "existed": True,
                        "backup": "backup/0.old",
                        "stage": "stage/0.new",
                    }
                ],
            }
            journal_path = package / ".manager" / "transaction.json"
            journal_path.parent.mkdir(exist_ok=True)
            journal_path.write_text(json.dumps(journal), encoding="utf-8")

            result = run_cli("validate", str(package), check=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("transaction target", result.stderr)
            self.assertEqual(escaped.read_text(encoding="utf-8"), "preserve")

    def test_section_items_put_batches_large_updates_in_one_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            batch = [
                item(f"E-{index:04d}", "evidence", {"finding": index})
                for index in range(1000)
            ]
            source = data_value(root, "batch.json", batch)
            run_cli(
                "section-items-put",
                str(package),
                "evidence-and-findings",
                *source,
            )
            shown = json.loads(
                run_cli(
                    "show", str(package), "--section", "evidence-and-findings"
                ).stdout
            )
            self.assertEqual(len(shown["content"]), 1000)
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.1")

    def test_section_put_rejects_nested_subsections_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section_path = package / "data" / "sections" / "request-and-goal.json"
            before = section_path.read_bytes()
            section = json.loads(section_path.read_text())
            section["subsections"] = [
                {
                    "id": "level-one",
                    "title": "Level one",
                    "content": [],
                    "subsections": [
                        {"id": "level-two", "title": "Level two", "content": []}
                    ],
                }
            ]
            source = data_value(root, "section.json", section)
            result = run_cli("section-put", str(package), *source, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("schema validation failed", result.stderr)
            self.assertEqual(section_path.read_bytes(), before)

    def test_optional_section_add_move_and_remove_updates_toc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section = {
                "id": "migration-analysis",
                "title": "Migration Analysis",
                "content": [],
                "subsections": [],
            }
            source = data_value(root, "section.json", section)
            run_cli(
                "section-add",
                str(package),
                *source,
                "--before",
                "work-unit-basis",
            )
            run_cli(
                "section-move",
                str(package),
                "migration-analysis",
                "--after",
                "work-unit-basis",
            )
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(toc["sections"][-1]["id"], "migration-analysis")
            run_cli("section-remove", str(package), "migration-analysis")
            self.assertFalse(
                (package / "data" / "sections" / "migration-analysis.json").exists()
            )
            required = run_cli(
                "section-remove", str(package), "request-and-goal", check=False
            )
            self.assertNotEqual(required.returncode, 0)
            self.assertIn("required section", required.stderr)

    def test_validate_rejects_toc_tampering_and_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            toc_path = package / "data" / "table-of-contents.json"
            toc = json.loads(toc_path.read_text())
            toc["sections"].reverse()
            toc_path.write_text(json.dumps(toc))
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manager-owned table of contents", result.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            (package / "data" / "sections" / "context-and-scope.json").unlink()
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section file", result.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            ghost = package / "data" / "sections" / "ghost.json"
            ghost.write_text(
                json.dumps(
                    {"id": "ghost", "title": "Ghost", "content": [], "subsections": []}
                )
            )
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section file set", result.stderr)

    def test_duplicate_subsection_and_item_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section_path = package / "data" / "sections" / "request-and-goal.json"
            section = json.loads(section_path.read_text())
            section["content"] = [
                item("DUPLICATE", "human-request", "one"),
                item("DUPLICATE", "desired-outcome", "two"),
            ]
            source = data_value(root, "duplicates.json", section)
            result = run_cli("section-put", str(package), *source, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("content item ids must be unique", result.stderr)

            section["content"] = []
            section["subsections"] = [
                {"id": "context-and-scope", "title": "Conflicting id", "content": []}
            ]
            source = data_value(root, "hierarchy-duplicates.json", section)
            result = run_cli("section-put", str(package), *source, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section and subsection ids must be unique", result.stderr)

            section["subsections"] = [
                {
                    "id": "request-details",
                    "title": "Request details",
                    "content": [
                        item("CROSS-CONTAINER", "desired-outcome", "subsection")
                    ],
                }
            ]
            section["content"] = [item("CROSS-CONTAINER", "human-request", "section")]
            source = data_value(root, "cross-container-duplicates.json", section)
            result = run_cli("section-put", str(package), *source, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unique across top-level section", result.stderr)

    def test_metadata_semantic_failure_preserves_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relations = data_value(
                root,
                "relations.json",
                [
                    {
                        "type": "based-on",
                        "target": {
                            "artifactType": "document",
                            "id": "missing",
                            "path": "missing.json",
                        },
                    }
                ],
            )
            result = run_cli(
                "metadata-set",
                str(package),
                "relations",
                *relations,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("typed reference does not exist", result.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

            id_only = data_value(
                root,
                "id-only-relations.json",
                [
                    {
                        "type": "based-on",
                        "target": {
                            "artifactType": "document",
                            "id": "unresolved-without-path",
                        },
                    }
                ],
            )
            result = run_cli(
                "metadata-set",
                str(package),
                "relations",
                *id_only,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path", result.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

    def test_typed_reference_anchor_resolves_from_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            basis = {
                "id": "BASIS-001",
                "kind": "work-unit-basis",
                "content": "Canonical basis",
            }
            source = data_value(root, "basis.json", basis)
            run_cli(
                "section-item-put",
                str(package),
                "work-unit-basis",
                *source,
            )
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relations = [
                {
                    "type": "refines",
                    "target": {
                        "artifactType": "intake",
                        "id": package.name,
                        "path": f".agent-factory/intakes/{package.name}",
                        "anchor": {
                            "sectionId": "work-unit-basis",
                            "itemId": "BASIS-001",
                        },
                    },
                }
            ]
            valid = data_value(root, "anchored-relations.json", relations)
            run_cli("metadata-set", str(package), "relations", *valid)
            relations[0]["target"]["anchor"]["itemId"] = "MISSING"
            invalid = data_value(root, "missing-anchor.json", relations)
            current = metadata_path.read_bytes()
            result = run_cli(
                "metadata-set",
                str(package),
                "relations",
                *invalid,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("typed reference anchor item does not exist", result.stderr)
            self.assertNotEqual(current, before)
            self.assertEqual(metadata_path.read_bytes(), current)

    def test_large_section_is_stored_independently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section = {
                "id": "evidence-and-findings",
                "title": "Evidence and Findings",
                "content": [
                    item(f"E-{index:04d}", "evidence", {"finding": f"finding-{index}"})
                    for index in range(1500)
                ],
                "subsections": [],
            }
            source = data_value(root, "large-section.json", section)
            run_cli("section-put", str(package), *source)
            self.assertGreater(
                (package / "data" / "sections" / "evidence-and-findings.json")
                .stat()
                .st_size,
                100_000,
            )
            self.assertLess(
                (package / "data" / "table-of-contents.json").stat().st_size, 10_000
            )
            self.assertTrue(
                json.loads(run_cli("validate", str(package)).stdout)["valid"]
            )

    def test_focused_show_does_not_parse_unrelated_large_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            unrelated = package / "data" / "sections" / "evidence-and-findings.json"
            unrelated.write_text("{malformed", encoding="utf-8")
            shown = json.loads(
                run_cli("show", str(package), "--section", "request-and-goal").stdout
            )
            self.assertEqual(shown["id"], "request-and-goal")
            self.assertNotEqual(
                run_cli("validate", str(package), check=False).returncode, 0
            )

    def test_block_put_remove_and_reference_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            source = root / "large.log"
            source.write_bytes(b"x" * 2_000_000)
            put = json.loads(
                run_cli(
                    "block-put",
                    str(package),
                    str(source),
                    "--path",
                    "blocks/logs/large.log",
                    "--media-type",
                    "text/plain",
                    "--description",
                    "large log",
                ).stdout
            )
            self.assertIn("blocks/logs/large.log", put["files"])
            block_item = data_value(
                root,
                "block-item.json",
                {
                    "id": "BLOCK-001",
                    "kind": "block",
                    "content": "Large log",
                    "blockRef": "blocks/logs/large.log",
                },
            )
            run_cli(
                "section-item-put",
                str(package),
                "evidence-and-findings",
                *block_item,
            )
            remove = run_cli(
                "block-remove", str(package), "blocks/logs/large.log", check=False
            )
            self.assertNotEqual(remove.returncode, 0)
            self.assertIn("referenced", remove.stderr)
            self.assertTrue(
                json.loads(run_cli("validate", str(package), "--full").stdout)["valid"]
            )

    def test_orphan_block_and_actual_style_data_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            orphan = package / "blocks" / "orphan.log"
            orphan.write_text("orphan")
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("block file set", result.stderr)
            orphan.unlink()

            styled = data_value(
                root,
                "styled.json",
                item(
                    "STYLE-001",
                    "evidence",
                    {"style": {"color": "red"}, "finding": "styled"},
                ),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "evidence-and-findings",
                *styled,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("actual style", result.stderr)

    def test_validate_rejects_symlinked_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            link = root / ".agent-factory" / "intakes" / "linked-intake"
            link.symlink_to(package, target_is_directory=True)
            result = run_cli("validate", str(link), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not be a symlink", result.stderr)

    def test_ready_transition_requires_profile_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            run_cli("transition", str(package), "validating")
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("failed readiness flags", result.stderr)

    def test_complete_profile_can_transition_to_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            required_items = {
                "request-and-goal": [
                    item("REQUEST-001", "human-request", "Intake 고도화"),
                    item(
                        "OUTCOME-001", "desired-outcome", "실행 가능한 Work Unit basis"
                    ),
                    item("SUCCESS-001", "success-criterion", "검증 통과"),
                ],
                "context-and-scope": [
                    item("CONTEXT-001", "context", "현재 Intake v1"),
                    item("SCOPE-001", "scope", "Intake manager"),
                    item("OUT-001", "out-of-scope", "기존 데이터 migration"),
                ],
                "stakeholders-and-approval": [
                    item("STAKEHOLDER-001", "stakeholder", "Human"),
                    item("OWNER-001", "decision-owner", "Human"),
                    item("APPROVAL-001", "approval-boundary", "Human Review"),
                ],
                "evidence-and-findings": [
                    item("EVIDENCE-001", "evidence", "승인 기록")
                ],
                "requirements-and-constraints": [
                    item("REQUIREMENT-001", "requirement", "필수 섹션 검증"),
                    item("AC-001", "acceptance-criterion", "누락 시 거부"),
                ],
                "decisions-and-open-items": [
                    item("DECISION-001", "decision-status", "결정 완료"),
                    item("OPEN-STATUS-001", "open-items-status", "차단 항목 없음"),
                ],
                "work-unit-basis": [
                    item(
                        "SPEC-001",
                        "specification-impact",
                        {"status": "aligned"},
                        status="aligned",
                    ),
                    item("BASIS-001", "work-unit-basis", "manager 구현"),
                ],
            }
            for section_id, items in required_items.items():
                for index, content_item in enumerate(items):
                    source = data_value(
                        root, f"{section_id}-{index}.json", content_item
                    )
                    run_cli(
                        "section-item-put",
                        str(package),
                        section_id,
                        *source,
                    )
            readiness = data_value(
                root,
                "readiness.json",
                {
                    "contractValid": False,
                    "evidenceComplete": True,
                    "requirementsComplete": True,
                    "specificationConsistent": True,
                    "executionReady": True,
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
            run_cli("transition", str(package), "validating")
            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertTrue(metadata["readiness"]["contractValid"])

    def test_specialized_evidence_kinds_satisfy_ready_evidence_family(self) -> None:
        for evidence_kind in (
            "web-evidence",
            "internal-evidence",
            "user-evidence",
            "interview",
        ):
            with (
                self.subTest(evidence_kind=evidence_kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                package = create_package(root)
                populate_ready_intake(root, package, evidence_kind=evidence_kind)
                payload = json.loads(
                    run_cli("transition", str(package), "ready").stdout
                )
                self.assertEqual(payload["status"], "ready")

    def test_ready_requires_explicit_specification_resolution_status(self) -> None:
        accepted = ("aligned", "not-applicable", "gap-accepted-for-work-unit")
        for status in accepted:
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                package = create_package(root)
                populate_ready_intake(root, package, specification_status=status)
                self.assertEqual(
                    json.loads(run_cli("transition", str(package), "ready").stdout)[
                        "status"
                    ],
                    "ready",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package, specification_status="pending")
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("specification-impact status", result.stderr)

    def test_ready_mutation_reopens_draft_and_invalidates_semantic_readiness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package)
            run_cli("transition", str(package), "ready")

            run_cli("title-set", str(package), "변경된 Intake")

            metadata = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["lifecycle"]["status"], "draft")
            self.assertTrue(metadata["readiness"]["contractValid"])
            for field in (
                "evidenceComplete",
                "requirementsComplete",
                "specificationConsistent",
                "executionReady",
            ):
                self.assertFalse(metadata["readiness"][field])
            self.assertIsNone(metadata["readiness"]["reviewedAt"])

    def test_explicit_ready_to_draft_transition_invalidates_semantic_readiness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package)
            run_cli("transition", str(package), "ready")

            run_cli("transition", str(package), "draft")

            metadata = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["lifecycle"]["status"], "draft")
            self.assertTrue(metadata["readiness"]["contractValid"])
            self.assertFalse(metadata["readiness"]["evidenceComplete"])
            self.assertFalse(metadata["readiness"]["requirementsComplete"])
            self.assertFalse(metadata["readiness"]["specificationConsistent"])
            self.assertFalse(metadata["readiness"]["executionReady"])
            self.assertIsNone(metadata["readiness"]["reviewedAt"])

    def test_terminal_mutation_is_rejected_without_canonical_byte_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            evidence = root / "disposition.json"
            evidence.write_text('{"decision":"close"}', encoding="utf-8")
            disposition = {
                "id": "DISPOSITION-001",
                "kind": "disposition",
                "content": "Historical work is complete",
                "attributes": {"targetStatus": "closed"},
                "sourceRefs": [
                    {
                        "artifactType": "decision-record",
                        "id": "close-decision",
                        "path": "disposition.json",
                    }
                ],
            }
            source = data_value(root, "closed-disposition.json", disposition)
            run_cli(
                "section-item-put",
                str(package),
                "decisions-and-open-items",
                *source,
            )
            run_cli("transition", str(package), "closed")
            canonical = {
                path.relative_to(package): path.read_bytes()
                for path in package.rglob("*")
                if path.is_file() and ".manager" not in path.parts
            }

            result = run_cli("title-set", str(package), "변경 금지", check=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("terminal Intake", result.stderr)
            self.assertEqual(
                canonical,
                {
                    path.relative_to(package): path.read_bytes()
                    for path in package.rglob("*")
                    if path.is_file() and ".manager" not in path.parts
                },
            )

    def test_blocked_transition_requires_unresolved_blocking_item(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            result = run_cli("transition", str(package), "blocked", check=False)
            self.assertNotEqual(result.returncode, 0)
            blocker = data_value(
                root,
                "blocker.json",
                item(
                    "OPEN-001",
                    "open-item",
                    "Human 결정 필요",
                    blocking=True,
                    resolved=False,
                ),
            )
            run_cli(
                "section-item-put",
                str(package),
                "decisions-and-open-items",
                *blocker,
            )
            self.assertEqual(
                json.loads(run_cli("transition", str(package), "blocked").stdout)[
                    "status"
                ],
                "blocked",
            )

    def test_historical_disposition_states_are_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            closed = create_package(root, "closed-intake")
            missing = run_cli("transition", str(closed), "closed", check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("evidence-backed disposition", missing.stderr)
            evidence = root / "disposition.json"
            evidence.write_text(
                '{"decision":"close historical Intake"}', encoding="utf-8"
            )
            disposition = {
                "id": "DISPOSITION-001",
                "kind": "disposition",
                "content": "Historical work is complete",
                "attributes": {"targetStatus": "closed"},
                "sourceRefs": [
                    {
                        "artifactType": "decision-record",
                        "id": "close-decision",
                        "path": "disposition.json",
                    }
                ],
            }
            source = data_value(root, "closed-disposition.json", disposition)
            run_cli(
                "section-item-put",
                str(closed),
                "decisions-and-open-items",
                *source,
            )
            payload = json.loads(run_cli("transition", str(closed), "closed").stdout)
            self.assertEqual(payload["status"], "closed")
            rejected = run_cli("transition", str(closed), "draft", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("invalid Intake transition", rejected.stderr)

            superseded = create_package(root, "superseded-intake")
            disposition["attributes"]["targetStatus"] = "superseded"
            disposition["content"] = "A later contract replaces this Intake"
            source = data_value(root, "superseded-disposition.json", disposition)
            run_cli(
                "section-item-put",
                str(superseded),
                "decisions-and-open-items",
                *source,
            )
            payload = json.loads(
                run_cli("transition", str(superseded), "superseded").stdout
            )
            self.assertEqual(payload["status"], "superseded")
            rejected = run_cli("transition", str(superseded), "validating", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("invalid Intake transition", rejected.stderr)

    def test_related_skills_use_section_item_manager_contract(self) -> None:
        skills_root = SKILL_ROOT.parent
        intake = (
            SKILL_ROOT / "references" / "intake-management.md"
        ).read_text()
        structure = (SKILL_ROOT / "references" / "intake-structure.md").read_text()
        lifecycle = (
            skills_root / "lifecycle" / "references" / "lifecycle-entry.md"
        ).read_text()
        for path in (
            SKILL_ROOT / "references" / "analysis.md",
            SKILL_ROOT / "references" / "interview.md",
            SKILL_ROOT / "references" / "user-research.md",
            SKILL_ROOT / "references" / "web-search.md",
            skills_root
            / "specifications"
            / "references"
            / "specification-management.md",
        ):
            text = path.read_text()
            self.assertIn("section-item-put", text)
        self.assertIn("metadata.json", intake)
        self.assertIn("table-of-contents.json", intake)
        self.assertIn("request-and-goal", structure)
        self.assertIn("Use `intakes` for every Intake package", lifecycle)
        self.assertIn("Use `intakes`", lifecycle)
        self.assertIn(
            "kind `decision-status`",
            (SKILL_ROOT / "references" / "interview.md").read_text(),
        )
        self.assertIn(
            "kind `open-items-status`",
            (SKILL_ROOT / "references" / "interview.md").read_text(),
        )
        execution_skill = (
            skills_root
            / "work-units"
            / "references"
            / "work-unit-execution.md"
        ).read_text()
        normalized_execution_skill = " ".join(execution_skill.split())
        self.assertIn(
            "sparse checkout to exclude the entire `.agent-factory`",
            normalized_execution_skill,
        )
        self.assertIn(
            "ignores primary `.agent-factory/**` changes",
            normalized_execution_skill,
        )

    def test_intake_capability_routing_is_bidirectional(self) -> None:
        skills_root = SKILL_ROOT.parent
        web_search = (SKILL_ROOT / "references" / "web-search.md").read_text()
        analysis = (SKILL_ROOT / "references" / "analysis.md").read_text()
        interview = (SKILL_ROOT / "references" / "interview.md").read_text()

        self.assertIn("direct observation", web_search)
        self.assertIn("`intakes`", web_search)
        self.assertIn("direct observation", analysis)
        self.assertIn("`intakes`", analysis)
        self.assertIn("participant-session interpretation", interview)
        self.assertIn("`intakes`", interview)


if __name__ == "__main__":
    unittest.main()
