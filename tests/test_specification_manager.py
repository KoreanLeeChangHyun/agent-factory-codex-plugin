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


SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "specifications"
SCRIPT = SKILL_ROOT / "scripts" / "specification.py"
PROFILE_ROOT = SKILL_ROOT / "assets" / "profiles"
PROFILE_IDS = [
    "api-design",
    "class-architecture",
    "data-model",
    "project-core",
    "requirements-specification",
    "system-architecture",
]
COMMON_SECTIONS = [
    "purpose-and-scope",
    "basis-and-relations",
    "decisions-and-open-items",
    "verification-and-traceability",
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


def create_package(
    root: Path, profile_id: str = "project-core", specification_id: str = "sample-spec"
) -> Path:
    package = root / ".agent-factory" / "specifications" / specification_id
    run_cli(
        "create",
        str(package),
        "--id",
        specification_id,
        "--title",
        "Sample Specification",
        "--project-id",
        "sample-project",
        "--profile",
        profile_id,
        "--language",
        "ko",
        "--theme",
        "default",
    )
    return package


def load_manager() -> object:
    spec = importlib.util.spec_from_file_location(
        "specification_manager_under_test", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load Specification manager: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SpecificationManagerTests(unittest.TestCase):
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
                "different-specification",
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

            metadata["id"] = "different-specification"
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

    def test_delete_profile_unresolved_package_with_explicit_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            metadata_path = package / "data" / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["documentProfile"] = {
                "id": "missing-profile",
                "version": "1.0.0",
            }
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
            self.assertIn("profile-unresolved", deleted["validationError"])
            self.assertFalse(package.exists())

    def test_delete_rejects_symlink_package_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            collection = root / ".agent-factory" / "specifications"
            collection.mkdir(parents=True)
            target = root / "outside"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            package = collection / "linked-specification"
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
            moved = package.parent / "moved-specification"
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

    def test_check_schemas_validates_every_implemented_profile(self) -> None:
        payload = json.loads(run_cli("check-schemas").stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["schemaVersion"], "1.0.0")
        self.assertEqual(payload["profiles"], PROFILE_IDS)
        self.assertEqual(
            {path.name for path in PROFILE_ROOT.glob("*.profile.json")},
            {f"{profile_id}.profile.json" for profile_id in PROFILE_IDS},
        )
        for path in PROFILE_ROOT.glob("*.profile.json"):
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["implementationStatus"],
                "implemented",
            )

    def test_every_profile_creates_its_exact_sectioned_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile_id in PROFILE_IDS:
                with self.subTest(profile=profile_id):
                    package = create_package(root, profile_id, f"spec-{profile_id}")
                    profile = json.loads(
                        (PROFILE_ROOT / f"{profile_id}.profile.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    expected = COMMON_SECTIONS + [
                        entry["id"] for entry in profile["profileRequiredSections"]
                    ]
                    metadata = json.loads(
                        (package / "data" / "metadata.json").read_text(encoding="utf-8")
                    )
                    toc = json.loads(
                        (package / "data" / "table-of-contents.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(metadata["artifactType"], "specification")
                    self.assertEqual(
                        metadata["documentClass"], profile["documentClass"]
                    )
                    self.assertEqual(
                        metadata["documentProfile"],
                        {"id": profile_id, "version": "1.0.0"},
                    )
                    self.assertEqual(
                        metadata["lifecycle"],
                        {"phase": "specification", "status": "draft"},
                    )
                    self.assertNotIn("readiness", metadata)
                    self.assertEqual(
                        [entry["id"] for entry in toc["sections"]], expected
                    )
                    result = json.loads(
                        run_cli("validate", str(package), "--full").stdout
                    )
                    self.assertEqual(result["profile"], f"{profile_id}@1.0.0")
                    self.assertEqual(
                        result["profileValidation"], "base-valid-and-profile-valid"
                    )

    def test_system_architecture_profile_covers_runtime_contract_sections(self) -> None:
        profile = json.loads(
            (PROFILE_ROOT / "system-architecture.profile.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(profile["documentClass"], "architecture")
        self.assertEqual(
            [entry["id"] for entry in profile["profileRequiredSections"]],
            [
                "system-context-and-boundaries",
                "components-and-ownership",
                "startup-and-runtime",
                "state-storage-and-consistency",
                "admission-execution-and-recovery",
                "security-observability-and-verification",
            ],
        )

    def test_mutation_without_readiness_increments_one_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            run_cli("title-set", str(package), "Updated Specification")
            metadata = json.loads(
                (package / "data" / "metadata.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["documentVersion"], "1.0.1")
            self.assertNotIn("readiness", metadata)
            shown = json.loads(
                run_cli("show", str(package), "--section", "purpose-and-scope").stdout
            )
            self.assertEqual(shown["id"], "purpose-and-scope")

    def test_unknown_profile_is_profile_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run_cli(
                "create",
                str(root / ".agent-factory" / "specifications" / "unknown-spec"),
                "--id",
                "unknown-spec",
                "--title",
                "Unknown",
                "--project-id",
                "sample-project",
                "--profile",
                "missing-profile",
                "--theme",
                "default",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("profile-unresolved", result.stderr)

    def test_profile_version_and_document_class_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for field, value in (
                ("documentProfile", {"id": "project-core", "version": "9.0.0"}),
                ("documentClass", "requirements"),
            ):
                with self.subTest(field=field):
                    package = create_package(
                        root, specification_id=f"mismatch-{field.lower()}"
                    )
                    metadata_path = package / "data" / "metadata.json"
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    metadata[field] = value
                    metadata_path.write_text(
                        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    result = run_cli("validate", str(package), check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("profile", result.stderr.lower())

    def test_profile_fields_cannot_be_mutated_directly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_package(Path(temporary))
            for field in ("documentClass", "documentProfile"):
                result = run_cli(
                    "metadata-set",
                    str(package),
                    field,
                    "--value-string",
                    "ignored",
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("must not be updated directly", result.stderr)

    def test_legacy_custom_manifest_is_not_relabelled_as_conforming(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = (
                Path(temporary) / ".agent-factory" / "specifications" / "legacy-spec"
            )
            (package / "data").mkdir(parents=True)
            (package / "data" / "manifest.json").write_text(
                '{"status":"draft"}\n', encoding="utf-8"
            )
            result = run_cli("validate", str(package), check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("metadata.json", result.stderr)

    def test_profile_selection_does_not_leak_between_processes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            api = create_package(root, "api-design", "api-spec")
            core = create_package(root, "project-core", "project-core")
            self.assertEqual(
                json.loads(run_cli("validate", str(api)).stdout)["profile"],
                "api-design@1.0.0",
            )
            self.assertEqual(
                json.loads(run_cli("validate", str(core)).stdout)["profile"],
                "project-core@1.0.0",
            )

    def test_prune_missing_provenance_ref_recovers_full_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = create_package(root)
            metadata_path = package / "data" / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["provenance"]["sourceRefs"] = [
                {
                    "artifactType": "work-unit",
                    "id": "removed-unit",
                    "path": ".agent-factory/work-units/removed-unit",
                }
            ]
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertNotEqual(
                run_cli("validate", str(package), "--full", check=False).returncode,
                0,
            )
            recovered = json.loads(
                run_cli(
                    "source-ref-prune",
                    str(package),
                    "--artifact-type",
                    "work-unit",
                    "--id",
                    "removed-unit",
                    "--path",
                    ".agent-factory/work-units/removed-unit",
                ).stdout
            )
            self.assertTrue(recovered["valid"])
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8"))["provenance"][
                    "sourceRefs"
                ],
                [],
            )


if __name__ == "__main__":
    unittest.main()
