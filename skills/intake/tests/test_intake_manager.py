from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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


def value_file(root: Path, name: str, value: object) -> Path:
    path = root / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def item(item_id: str, kind: str, content: object, **attributes: object) -> dict[str, object]:
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
        source = value_file(root, f"{section_id}.json", items)
        run_cli("section-items-put", str(package), section_id, "--value-file", str(source))
    readiness = value_file(
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
    run_cli("metadata-set", str(package), "readiness", "--value-file", str(readiness))
    run_cli("transition", str(package), "validating")


class IntakeManagerTests(unittest.TestCase):
    def test_check_schemas_and_profile(self) -> None:
        payload = json.loads(run_cli("check-schemas").stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["schemaVersion"], "2.0.0")
        self.assertEqual(payload["profile"], "intake@2.0.0")
        self.assertEqual(
            [entry["id"] for entry in json.loads(PROFILE.read_text())["requiredSections"]],
            REQUIRED_SECTIONS,
        )
        self.assertEqual(
            set(payload["schemas"]),
            {"metadata.schema.json", "title.schema.json", "table-of-contents.schema.json", "section.schema.json", "blocks.schema.json"},
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
            self.assertEqual([entry["id"] for entry in toc["sections"]], REQUIRED_SECTIONS)
            self.assertEqual(len(list((package / "data" / "sections").glob("*.json"))), 7)
            payload = json.loads(run_cli("validate", str(package)).stdout)
            self.assertEqual(payload["status"], "draft")
            self.assertEqual(payload["sectionCount"], 7)

    def test_title_set_and_section_item_put_are_manager_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            run_cli("title-set", str(package), "갱신된 Intake")
            candidate = value_file(root, "item.json", item("REQ-001", "human-request", "요청"))
            run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                "--value-file",
                str(candidate),
            )
            replacement = value_file(root, "replacement.json", item("REQ-001", "human-request", "수정된 요청"))
            run_cli(
                "section-item-put",
                str(package),
                "request-and-goal",
                "--value-file",
                str(replacement),
            )
            shown = json.loads(run_cli("show", str(package), "--section", "request-and-goal").stdout)
            self.assertEqual(shown["content"], [item("REQ-001", "human-request", "수정된 요청")])
            self.assertEqual(json.loads((package / "data" / "title.json").read_text())["title"], "갱신된 Intake")
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.3")

    def test_concurrent_mutations_are_serialized_and_recovery_restores_preimage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            commands = [
                [sys.executable, str(SCRIPT), "title-set", str(package), title]
                for title in ("Concurrent A", "Concurrent B")
            ]
            processes = [subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for command in commands]
            results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
            self.assertTrue(all(returncode == 0 for _, _, returncode in results), results)
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertEqual(metadata["documentVersion"], "1.0.2")
            self.assertTrue((root / ".agent-factory" / "runtime" / "locks" / "intakes" / "sample-intake.lock").exists())

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
                    {"path": "data/title.json", "existed": True, "backup": "backup/0.old", "stage": "stage/0.new"}
                ],
            }
            journal_path = package / ".manager" / "transaction.json"
            journal_path.parent.mkdir(exist_ok=True)
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            self.assertTrue(json.loads(run_cli("validate", str(package)).stdout)["valid"])
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
            (package / "data" / "redirect").symlink_to(outside, target_is_directory=True)

            with self.assertRaises(manager.ManagerError):
                manager.commit_transaction(
                    package,
                    json_writes={package / "data" / "redirect" / "escaped.json": {"changed": True}},
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
            (manager_root / "transactions").symlink_to(outside, target_is_directory=True)
            title = package / "data" / "title.json"
            before = title.read_bytes()

            with self.assertRaises(manager.ManagerError):
                manager.commit_transaction(package, json_writes={title: {"title": "blocked"}})

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
                if candidate == target and label == "transaction target" and not swapped:
                    redirect.rename(package / "data" / "redirect-original")
                    redirect.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return relative

            manager.base.checked_package_target = racing_check
            try:
                with self.assertRaises(manager.ManagerError):
                    manager.commit_transaction(package, json_writes={target: {"changed": True}})
            finally:
                manager.base.checked_package_target = original_check

            self.assertTrue(swapped)
            self.assertEqual(escaped.read_text(encoding="utf-8"), "outside-preserve")

    def test_recovery_rejects_symlinked_parent_escape_and_preserves_outside_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            outside = root / "outside"
            outside.mkdir()
            escaped = outside / "escaped.json"
            escaped.write_text("preserve", encoding="utf-8")
            (package / "data" / "redirect").symlink_to(outside, target_is_directory=True)
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
            batch = [item(f"E-{index:04d}", "evidence", {"finding": index}) for index in range(1000)]
            source = value_file(root, "batch.json", batch)
            run_cli(
                "section-items-put",
                str(package),
                "evidence-and-findings",
                "--value-file",
                str(source),
            )
            shown = json.loads(run_cli("show", str(package), "--section", "evidence-and-findings").stdout)
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
                    "subsections": [{"id": "level-two", "title": "Level two", "content": []}],
                }
            ]
            source = value_file(root, "section.json", section)
            result = run_cli("section-put", str(package), "--value-file", str(source), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("schema validation failed", result.stderr)
            self.assertEqual(section_path.read_bytes(), before)

    def test_optional_section_add_move_and_remove_updates_toc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section = {"id": "migration-analysis", "title": "Migration Analysis", "content": [], "subsections": []}
            source = value_file(root, "section.json", section)
            run_cli("section-add", str(package), "--value-file", str(source), "--before", "work-unit-basis")
            run_cli("section-move", str(package), "migration-analysis", "--after", "work-unit-basis")
            toc = json.loads((package / "data" / "table-of-contents.json").read_text())
            self.assertEqual(toc["sections"][-1]["id"], "migration-analysis")
            run_cli("section-remove", str(package), "migration-analysis")
            self.assertFalse((package / "data" / "sections" / "migration-analysis.json").exists())
            required = run_cli("section-remove", str(package), "request-and-goal", check=False)
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
            ghost.write_text(json.dumps({"id": "ghost", "title": "Ghost", "content": [], "subsections": []}))
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section file set", result.stderr)

    def test_duplicate_subsection_and_item_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            section_path = package / "data" / "sections" / "request-and-goal.json"
            section = json.loads(section_path.read_text())
            section["content"] = [item("DUPLICATE", "human-request", "one"), item("DUPLICATE", "desired-outcome", "two")]
            source = value_file(root, "duplicates.json", section)
            result = run_cli("section-put", str(package), "--value-file", str(source), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("content item ids must be unique", result.stderr)

            section["content"] = []
            section["subsections"] = [
                {"id": "context-and-scope", "title": "Conflicting id", "content": []}
            ]
            source = value_file(root, "hierarchy-duplicates.json", section)
            result = run_cli("section-put", str(package), "--value-file", str(source), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section and subsection ids must be unique", result.stderr)

            section["subsections"] = [
                {
                    "id": "request-details",
                    "title": "Request details",
                    "content": [item("CROSS-CONTAINER", "desired-outcome", "subsection")],
                }
            ]
            section["content"] = [item("CROSS-CONTAINER", "human-request", "section")]
            source = value_file(root, "cross-container-duplicates.json", section)
            result = run_cli("section-put", str(package), "--value-file", str(source), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unique across top-level section", result.stderr)

    def test_metadata_semantic_failure_preserves_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relations = value_file(
                root,
                "relations.json",
                [{"type": "based-on", "target": {"artifactType": "document", "id": "missing", "path": "missing.json"}}],
            )
            result = run_cli("metadata-set", str(package), "relations", "--value-file", str(relations), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("typed reference does not exist", result.stderr)
            self.assertEqual(metadata_path.read_bytes(), before)

            id_only = value_file(
                root,
                "id-only-relations.json",
                [{"type": "based-on", "target": {"artifactType": "document", "id": "unresolved-without-path"}}],
            )
            result = run_cli("metadata-set", str(package), "relations", "--value-file", str(id_only), check=False)
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
            source = value_file(root, "basis.json", basis)
            run_cli("section-item-put", str(package), "work-unit-basis", "--value-file", str(source))
            metadata_path = package / "data" / "metadata.json"
            before = metadata_path.read_bytes()
            relations = [
                {
                    "type": "refines",
                    "target": {
                        "artifactType": "intake",
                        "id": package.name,
                        "path": f".agent-factory/intakes/{package.name}",
                        "anchor": {"sectionId": "work-unit-basis", "itemId": "BASIS-001"},
                    },
                }
            ]
            valid = value_file(root, "anchored-relations.json", relations)
            run_cli("metadata-set", str(package), "relations", "--value-file", str(valid))
            relations[0]["target"]["anchor"]["itemId"] = "MISSING"
            invalid = value_file(root, "missing-anchor.json", relations)
            current = metadata_path.read_bytes()
            result = run_cli("metadata-set", str(package), "relations", "--value-file", str(invalid), check=False)
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
                "content": [item(f"E-{index:04d}", "evidence", {"finding": f"finding-{index}"}) for index in range(1500)],
                "subsections": [],
            }
            source = value_file(root, "large-section.json", section)
            run_cli("section-put", str(package), "--value-file", str(source))
            self.assertGreater((package / "data" / "sections" / "evidence-and-findings.json").stat().st_size, 100_000)
            self.assertLess((package / "data" / "table-of-contents.json").stat().st_size, 10_000)
            self.assertTrue(json.loads(run_cli("validate", str(package)).stdout)["valid"])

    def test_focused_show_does_not_parse_unrelated_large_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            unrelated = package / "data" / "sections" / "evidence-and-findings.json"
            unrelated.write_text("{malformed", encoding="utf-8")
            shown = json.loads(run_cli("show", str(package), "--section", "request-and-goal").stdout)
            self.assertEqual(shown["id"], "request-and-goal")
            self.assertNotEqual(run_cli("validate", str(package), check=False).returncode, 0)

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
            block_item = value_file(
                root,
                "block-item.json",
                {"id": "BLOCK-001", "kind": "block", "content": "Large log", "blockRef": "blocks/logs/large.log"},
            )
            run_cli("section-item-put", str(package), "evidence-and-findings", "--value-file", str(block_item))
            remove = run_cli("block-remove", str(package), "blocks/logs/large.log", check=False)
            self.assertNotEqual(remove.returncode, 0)
            self.assertIn("referenced", remove.stderr)
            self.assertTrue(json.loads(run_cli("validate", str(package), "--full").stdout)["valid"])

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

            styled = value_file(
                root,
                "styled.json",
                item("STYLE-001", "evidence", {"style": {"color": "red"}, "finding": "styled"}),
            )
            result = run_cli(
                "section-item-put",
                str(package),
                "evidence-and-findings",
                "--value-file",
                str(styled),
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
                    item("OUTCOME-001", "desired-outcome", "실행 가능한 Work Unit basis"),
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
                "evidence-and-findings": [item("EVIDENCE-001", "evidence", "승인 기록")],
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
                    source = value_file(root, f"{section_id}-{index}.json", content_item)
                    run_cli("section-item-put", str(package), section_id, "--value-file", str(source))
            readiness = value_file(
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
            run_cli("metadata-set", str(package), "readiness", "--value-file", str(readiness))
            run_cli("transition", str(package), "validating")
            payload = json.loads(run_cli("transition", str(package), "ready").stdout)
            self.assertEqual(payload["status"], "ready")
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertTrue(metadata["readiness"]["contractValid"])

    def test_specialized_evidence_kinds_satisfy_ready_evidence_family(self) -> None:
        for evidence_kind in ("web-evidence", "internal-evidence", "user-evidence", "interview"):
            with self.subTest(evidence_kind=evidence_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                package = create_package(root)
                populate_ready_intake(root, package, evidence_kind=evidence_kind)
                payload = json.loads(run_cli("transition", str(package), "ready").stdout)
                self.assertEqual(payload["status"], "ready")

    def test_ready_requires_explicit_specification_resolution_status(self) -> None:
        accepted = ("aligned", "not-applicable", "gap-accepted-for-work-unit")
        for status in accepted:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                package = create_package(root)
                populate_ready_intake(root, package, specification_status=status)
                self.assertEqual(
                    json.loads(run_cli("transition", str(package), "ready").stdout)["status"],
                    "ready",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package, specification_status="pending")
            result = run_cli("transition", str(package), "ready", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("specification-impact status", result.stderr)

    def test_ready_mutation_reopens_draft_and_invalidates_semantic_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package)
            run_cli("transition", str(package), "ready")

            run_cli("title-set", str(package), "변경된 Intake")

            metadata = json.loads((package / "data" / "metadata.json").read_text(encoding="utf-8"))
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

    def test_explicit_ready_to_draft_transition_invalidates_semantic_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            populate_ready_intake(root, package)
            run_cli("transition", str(package), "ready")

            run_cli("transition", str(package), "draft")

            metadata = json.loads((package / "data" / "metadata.json").read_text(encoding="utf-8"))
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
            source = value_file(root, "closed-disposition.json", disposition)
            run_cli("section-item-put", str(package), "decisions-and-open-items", "--value-file", str(source))
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
            blocker = value_file(
                root,
                "blocker.json",
                item("OPEN-001", "open-item", "Human 결정 필요", blocking=True, resolved=False),
            )
            run_cli("section-item-put", str(package), "decisions-and-open-items", "--value-file", str(blocker))
            self.assertEqual(json.loads(run_cli("transition", str(package), "blocked").stdout)["status"], "blocked")

    def test_historical_disposition_states_are_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            closed = create_package(root, "closed-intake")
            missing = run_cli("transition", str(closed), "closed", check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("evidence-backed disposition", missing.stderr)
            evidence = root / "disposition.json"
            evidence.write_text('{"decision":"close historical Intake"}', encoding="utf-8")
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
            source = value_file(root, "closed-disposition.json", disposition)
            run_cli("section-item-put", str(closed), "decisions-and-open-items", "--value-file", str(source))
            payload = json.loads(run_cli("transition", str(closed), "closed").stdout)
            self.assertEqual(payload["status"], "closed")
            rejected = run_cli("transition", str(closed), "draft", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("invalid Intake transition", rejected.stderr)

            superseded = create_package(root, "superseded-intake")
            disposition["attributes"]["targetStatus"] = "superseded"
            disposition["content"] = "A later contract replaces this Intake"
            source = value_file(root, "superseded-disposition.json", disposition)
            run_cli("section-item-put", str(superseded), "decisions-and-open-items", "--value-file", str(source))
            payload = json.loads(run_cli("transition", str(superseded), "superseded").stdout)
            self.assertEqual(payload["status"], "superseded")
            rejected = run_cli("transition", str(superseded), "validating", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("invalid Intake transition", rejected.stderr)

    def test_related_skills_use_section_item_manager_contract(self) -> None:
        skills_root = SKILL_ROOT.parent
        intake = (SKILL_ROOT / "SKILL.md").read_text()
        structure = (SKILL_ROOT / "references" / "intake-structure.md").read_text()
        lifecycle = (skills_root / "lifecycle" / "SKILL.md").read_text()
        for name in ("analysis", "interview", "user-research", "web-search", "specification"):
            text = (skills_root / name / "SKILL.md").read_text()
            self.assertIn("section-item-put", text)
        self.assertIn("metadata.json", intake)
        self.assertIn("table-of-contents.json", intake)
        self.assertIn("request-and-goal", structure)
        self.assertIn("Use `intake` for every Intake package", lifecycle)
        self.assertIn("Use `user-research`", lifecycle)
        self.assertIn("kind `decision-status`", (skills_root / "interview" / "SKILL.md").read_text())
        self.assertIn("kind `open-items-status`", (skills_root / "interview" / "SKILL.md").read_text())
        execution_skill = (skills_root / "work-unit-execution" / "SKILL.md").read_text()
        normalized_execution_skill = " ".join(execution_skill.split())
        self.assertIn("codex --ask-for-approval <policy> exec", normalized_execution_skill)
        self.assertIn("reported changed-path set", normalized_execution_skill)

    def test_intake_capability_routing_is_bidirectional(self) -> None:
        skills_root = SKILL_ROOT.parent
        web_search = (skills_root / "web-search" / "SKILL.md").read_text()
        analysis = (skills_root / "analysis" / "SKILL.md").read_text()
        interview = (skills_root / "interview" / "SKILL.md").read_text()

        self.assertIn("direct observation", web_search)
        self.assertIn("`user-research`", web_search)
        self.assertIn("direct observation", analysis)
        self.assertIn("`user-research`", analysis)
        self.assertIn("not user-research interviews", interview)
        self.assertIn("`user-research`", interview)


if __name__ == "__main__":
    unittest.main()
