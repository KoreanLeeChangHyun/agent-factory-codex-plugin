from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "intakes" / "scripts" / "intake.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("intake_manager_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load Intake manager")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result


def create(root: Path, intake_id: str = "topic-intake") -> Path:
    package = root / ".agent-factory" / "intakes" / intake_id
    run(
        "create",
        str(package),
        "--id",
        intake_id,
        "--topic",
        "One goal or topic",
        "--project-id",
        "project",
        "--language",
        "ko",
    )
    return package


def append(package: Path, entry_id: str, activity: str = "user-input") -> None:
    run(
        "entry-put",
        str(package),
        "--string",
        "/id",
        entry_id,
        "--string",
        "/actor/type",
        "human",
        "--string",
        "/activity",
        activity,
        "--string",
        "/content/message",
        "recorded",
    )


class IntakeManagerTests(unittest.TestCase):
    def test_schema_contract_is_v3_ledger(self) -> None:
        result = json.loads(run("check-schemas").stdout)
        self.assertEqual(result["schemaVersion"], "3.0.0")
        self.assertEqual(
            result["schemas"],
            ["blocks.schema.json", "entry.schema.json", "metadata.schema.json"],
        )

    def test_create_has_metadata_entries_and_blocks_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            self.assertTrue((package / "data" / "metadata.json").is_file())
            self.assertTrue((package / "data" / "entries").is_dir())
            self.assertTrue((package / "blocks" / "index.json").is_file())
            self.assertFalse((package / "data" / "title.json").exists())
            self.assertFalse((package / "data" / "table-of-contents.json").exists())
            metadata = json.loads((package / "data" / "metadata.json").read_text())
            self.assertNotIn("lifecycle", metadata)
            self.assertNotIn("readiness", metadata)
            self.assertNotIn("theme", metadata)

    def test_entries_are_append_only_and_manager_orders_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            append(package, "HUMAN-001")
            append(package, "SEARCH-001", "web-search")
            shown = json.loads(run("show", str(package)).stdout)
            self.assertEqual(
                [(item["id"], item["sequence"]) for item in shown["entries"]],
                [("HUMAN-001", 1), ("SEARCH-001", 2)],
            )
            rejected = run(
                "entry-put",
                str(package),
                "--string",
                "/id",
                "HUMAN-001",
                "--string",
                "/actor/type",
                "human",
                "--string",
                "/activity",
                "correction",
                "--string",
                "/content/message",
                "replacement",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("append-only", rejected.stderr)

    def test_correction_is_a_new_related_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            append(package, "HUMAN-001")
            run(
                "entry-put",
                str(package),
                "--string", "/id", "CORRECTION-001",
                "--string", "/actor/type", "human",
                "--string", "/activity", "correction",
                "--string", "/content/message", "corrected",
                "--string", "/relations/0/type", "corrects",
                "--string", "/relations/0/entryId", "HUMAN-001",
            )
            self.assertTrue(json.loads(run("validate", str(package), "--full").stdout)["valid"])

    def test_session_binding_does_not_change_semantic_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            path = package / "data" / "metadata.json"
            before = json.loads(path.read_text())
            run("session-bind", str(package), "session-1")
            bound = json.loads(path.read_text())
            self.assertEqual(bound["documentVersion"], before["documentVersion"])
            self.assertEqual(bound["updatedAt"], before["updatedAt"])
            run("session-clear", str(package))
            cleared = json.loads(path.read_text())
            self.assertEqual(cleared["documentVersion"], before["documentVersion"])

    def test_unresolved_entry_relation_is_rejected_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            result = run(
                "entry-put", str(package),
                "--string", "/id", "DECISION-001",
                "--string", "/actor/type", "human",
                "--string", "/activity", "decision",
                "--string", "/content/value", "yes",
                "--string", "/relations/0/type", "derived-from",
                "--string", "/relations/0/entryId", "MISSING",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((package / "data" / "entries" / "DECISION-001.json").exists())
            self.assertEqual(json.loads(run("validate", str(package)).stdout)["entryCount"], 0)

    def test_delete_requires_exact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            denied = run("delete", str(package), "--confirm-id", "other", check=False)
            self.assertNotEqual(denied.returncode, 0)
            self.assertTrue(package.exists())
            result = json.loads(run("delete", str(package), "--confirm-id", package.name).stdout)
            self.assertEqual(result["operationResult"], "deleted")
            self.assertFalse(package.exists())

    def test_block_put_keeps_package_valid_before_entry_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create(root)
            source = root / "evidence.txt"
            source.write_text("evidence", encoding="utf-8")
            run(
                "block-put", str(package), str(source),
                "--path", "blocks/evidence/source.txt",
                "--media-type", "text/plain",
                "--description", "source",
            )
            self.assertTrue(json.loads(run("validate", str(package), "--full").stdout)["valid"])

    def test_block_put_rejects_symlinked_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create(root)
            outside = root / "outside"
            outside.mkdir()
            (package / "blocks" / "escape").symlink_to(outside, target_is_directory=True)
            source = root / "evidence.txt"
            source.write_text("evidence", encoding="utf-8")
            result = run(
                "block-put", str(package), str(source),
                "--path", "blocks/escape/source.txt",
                "--media-type", "text/plain",
                "--description", "source",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((outside / "source.txt").exists())

    def test_malformed_entry_fails_closed_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create(Path(temporary))
            malformed = package / "data" / "entries" / "BAD.json"
            malformed.write_text("[]\n", encoding="utf-8")
            result = run("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be a JSON object", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_create_publish_never_replaces_existing_target(self) -> None:
        manager = load_manager()
        with tempfile.TemporaryDirectory() as temporary:
            collection = Path(temporary)
            staging = collection / "staging"
            target = collection / "target"
            staging.mkdir()
            target.mkdir()
            marker = target / "preserved"
            marker.write_text("existing", encoding="utf-8")
            descriptor = os.open(collection, manager.security.DIRECTORY_OPEN_FLAGS)
            try:
                with self.assertRaises(manager.ManagerError):
                    manager.rename_noreplace(
                        descriptor, staging.name, descriptor, target.name
                    )
            finally:
                os.close(descriptor)
            self.assertEqual(marker.read_text(encoding="utf-8"), "existing")
            self.assertTrue(staging.is_dir())

    def test_mutation_rejects_package_replaced_after_semantic_read(self) -> None:
        manager = load_manager()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create(root)
            original = package.with_name("held-original")
            identity_details = package.stat()
            identity = (identity_details.st_dev, identity_details.st_ino)
            metadata = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            package.rename(original)
            create(root)
            replacement_before = (
                package / "data" / "metadata.json"
            ).read_bytes()
            with self.assertRaises(manager.ManagerError):
                manager.commit(
                    package,
                    {package / "data" / "metadata.json": metadata},
                    expected_identity=identity,
                )
            self.assertEqual(
                (package / "data" / "metadata.json").read_bytes(),
                replacement_before,
            )


if __name__ == "__main__":
    unittest.main()
