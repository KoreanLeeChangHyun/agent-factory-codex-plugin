#!/usr/bin/env python3
"""Manage profile-driven Agent Factory Specification packages."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
PROFILE_ROOT = SKILL_ROOT / "assets" / "profiles"
PROFILE_SCHEMA = (
    SKILL_ROOT.parent
    / "lifecycle"
    / "assets"
    / "schema"
    / "document-profile.schema.json"
)
COMMON_MANAGER = (
    SKILL_ROOT.parent / "lifecycle" / "assets" / "scripts" / "sectioned_document.py"
)
COMMON_SCHEMA_ROOT = (
    SKILL_ROOT.parent / "lifecycle" / "assets" / "schema" / "sectioned-document"
)
PROFILE_SUFFIX = ".profile.json"


def load_base_manager() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_sectioned_document", COMMON_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sectioned document manager: {COMMON_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_specification_metadata(
    _: argparse.Namespace, metadata: dict[str, Any], current: dict[str, Any]
) -> None:
    metadata["documentClass"] = current["documentClass"]
    metadata["documentProfile"] = {
        "id": current["id"],
        "version": current["version"],
    }


base = load_base_manager()
ManagerError = base.ManagerError
base.configure_contract(
    skill_root=SKILL_ROOT,
    profile_path=PROFILE_ROOT / "project-core.profile.json",
    metadata_schema_path=SKILL_ROOT / "assets" / "schema" / "metadata.schema.json",
    structural_schema_root=COMMON_SCHEMA_ROOT,
    artifact_type="specification",
    artifact_label="Specification",
    package_collection="specifications",
    lifecycle_phase="specification",
    initial_status="draft",
    initial_readiness=None,
    generated_by="Agent Factory specification manager",
    create_metadata_hook=add_specification_metadata,
)
base.PROTECTED_METADATA_FIELDS |= {"documentClass", "documentProfile"}


def registered_profile_ids() -> list[str]:
    return sorted(
        path.name.removesuffix(PROFILE_SUFFIX)
        for path in PROFILE_ROOT.glob(f"*{PROFILE_SUFFIX}")
    )


def select_profile(
    profile_id: str, expected_version: str | None = None
) -> dict[str, Any]:
    if profile_id not in registered_profile_ids():
        raise ManagerError(
            f"profile-unresolved: Specification profile is not registered: {profile_id}"
        )
    path = PROFILE_ROOT / f"{profile_id}{PROFILE_SUFFIX}"
    raw = base.load_object(path, "Specification profile")
    if expected_version is not None and raw.get("version") != expected_version:
        raise ManagerError(
            f"profile-unresolved: Specification profile version mismatch: "
            f"requested={profile_id}@{expected_version}, registered={profile_id}@{raw.get('version')}"
        )
    base.PROFILE_PATH = path
    return raw


def profile() -> dict[str, Any]:
    raw = base.load_object(base.PROFILE_PATH, "Specification profile")
    normalized = dict(raw)
    normalized["requiredSections"] = [
        {**entry, "title": entry.get("title", entry["id"])}
        for entry in (
            *raw.get("commonRequiredSections", []),
            *raw.get("profileRequiredSections", []),
        )
    ]
    normalized["optionalSections"] = [
        {**entry, "title": entry.get("title", entry["id"])}
        for entry in raw.get("optionalSections", [])
    ]
    return normalized


def validate_schemas() -> dict[str, dict[str, Any]]:
    contracts = base.schemas()
    for contract in contracts.values():
        base.Draft202012Validator.check_schema(contract)
    registry_schema = base.load_object(PROFILE_SCHEMA, "document profile schema")
    base.Draft202012Validator.check_schema(registry_schema)
    current = profile()
    errors = list(
        base.Draft202012Validator(registry_schema).iter_errors(
            {key: value for key, value in current.items() if key != "requiredSections"}
        )
    )
    if errors:
        rendered = "; ".join(error.message for error in errors)
        raise ManagerError(
            f"Specification profile schema validation failed: {rendered}"
        )
    if current.get("artifactType") != "specification":
        raise ManagerError("Specification profile artifactType must be specification")
    if current.get("maximumSectionDepth") != 2:
        raise ManagerError("Specification profile maximumSectionDepth must be 2")
    version = contracts["metadata"]["properties"]["schemaVersion"]["const"]
    if current.get("version") != version:
        raise ManagerError(
            "Specification profile version must match metadata schemaVersion"
        )
    if current.get("implementationStatus") != "implemented":
        raise ManagerError(f"Specification profile is not implemented: {current['id']}")
    required = [entry["id"] for entry in current["requiredSections"]]
    optional = [entry["id"] for entry in current["optionalSections"]]
    if not required or len(required) != len(set(required)):
        raise ManagerError(
            "Specification required section ids must be non-empty and unique"
        )
    if set(required) & set(optional) or len(optional) != len(set(optional)):
        raise ManagerError(
            "Specification optional section ids must be unique and disjoint"
        )
    return contracts


def select_package_profile(package: Path) -> dict[str, Any]:
    metadata = base.load_object(package / base.METADATA_PATH, "Specification metadata")
    document_profile = metadata.get("documentProfile")
    if not isinstance(document_profile, dict):
        raise ManagerError(
            "profile-unresolved: Specification metadata.documentProfile is missing"
        )
    profile_id = document_profile.get("id")
    version = document_profile.get("version")
    if not isinstance(profile_id, str) or not isinstance(version, str):
        raise ManagerError(
            "profile-unresolved: Specification metadata.documentProfile is invalid"
        )
    return select_profile(profile_id, version)


base_validate_profile = base.validate_profile


def validate_profile(metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> None:
    base_validate_profile(metadata, summaries)
    current = profile()
    expected_profile = {"id": current["id"], "version": current["version"]}
    if metadata.get("documentProfile") != expected_profile:
        raise ManagerError(
            "Specification metadata documentProfile does not match the resolved profile"
        )
    if metadata.get("documentClass") != current["documentClass"]:
        raise ManagerError(
            "Specification metadata documentClass does not match the resolved profile"
        )


base_validate_package = base.validate_package


def validate_package(
    package_value: str | Path, *, full: bool = False
) -> dict[str, Any]:
    package = base.resolve_package(package_value)
    select_package_profile(package)
    result = base_validate_package(package, full=full)
    metadata = base.load_metadata(package)
    result["documentClass"] = metadata["documentClass"]
    result["profileValidation"] = "base-valid-and-profile-valid"
    return result


def command_check_schemas(_: argparse.Namespace) -> None:
    validated: list[str] = []
    for profile_id in registered_profile_ids():
        select_profile(profile_id)
        validate_schemas()
        validated.append(profile_id)
    print(
        json.dumps(
            {
                "valid": True,
                "schemaVersion": base.schemas()["metadata"]["properties"][
                    "schemaVersion"
                ]["const"],
                "profiles": validated,
                "schemas": sorted(path.name for path in base.SCHEMA_PATHS.values()),
            }
        )
    )


base.profile = profile
base.validate_schemas = validate_schemas
base.validate_profile = validate_profile
base.validate_package = validate_package


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Manage profile-driven Agent Factory Specification packages"
    )
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-schemas")
    check.set_defaults(handler=command_check_schemas)

    create = commands.add_parser("create")
    create.add_argument("package")
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--project-id", required=True)
    create.add_argument("--profile", required=True)
    create.add_argument("--language", default="ko")
    create.add_argument("--theme", required=True)
    create.set_defaults(handler=base.command_create)

    show = commands.add_parser("show")
    show.add_argument("package")
    show.add_argument("--section")
    show.set_defaults(handler=base.command_show)

    title = commands.add_parser("title-set")
    title.add_argument("package")
    title.add_argument("title")
    title.set_defaults(handler=base.command_title_set)

    metadata = commands.add_parser("metadata-set")
    metadata.add_argument("package")
    metadata.add_argument("field")
    base.add_data_arguments(metadata)
    metadata.set_defaults(handler=base.command_metadata_set)

    section_put = commands.add_parser("section-put")
    section_put.add_argument("package")
    base.add_data_arguments(section_put)
    section_put.set_defaults(handler=base.command_section_put)

    item_put = commands.add_parser("section-item-put")
    item_put.add_argument("package")
    item_put.add_argument("section_id")
    base.add_data_arguments(item_put)
    item_put.add_argument("--subsection")
    item_put.set_defaults(handler=base.command_section_item_put)

    items_put = commands.add_parser("section-items-put")
    items_put.add_argument("package")
    items_put.add_argument("section_id")
    base.add_data_arguments(items_put)
    items_put.add_argument("--subsection")
    items_put.set_defaults(handler=base.command_section_items_put)

    section_add = commands.add_parser("section-add")
    section_add.add_argument("package")
    base.add_data_arguments(section_add)
    position = section_add.add_mutually_exclusive_group()
    position.add_argument("--before")
    position.add_argument("--after")
    section_add.set_defaults(handler=base.command_section_add)

    section_move = commands.add_parser("section-move")
    section_move.add_argument("package")
    section_move.add_argument("section_id")
    move = section_move.add_mutually_exclusive_group(required=True)
    move.add_argument("--before")
    move.add_argument("--after")
    section_move.set_defaults(handler=base.command_section_move)

    section_remove = commands.add_parser("section-remove")
    section_remove.add_argument("package")
    section_remove.add_argument("section_id")
    section_remove.set_defaults(handler=base.command_section_remove)

    validate = commands.add_parser("validate")
    validate.add_argument("package")
    validate.add_argument("--full", action="store_true")
    validate.set_defaults(handler=base.command_validate)

    block_put = commands.add_parser("block-put")
    block_put.add_argument("package")
    block_put.add_argument("source")
    block_put.add_argument("--path", required=True)
    block_put.add_argument("--media-type", required=True)
    block_put.add_argument("--description", required=True)
    block_put.set_defaults(handler=base.command_block_put)

    block_remove = commands.add_parser("block-remove")
    block_remove.add_argument("package")
    block_remove.add_argument("path")
    block_remove.set_defaults(handler=base.command_block_remove)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if not hasattr(args, "package"):
            args.handler(args)
            return 0
        package = base.resolve_package(
            args.package, must_exist=args.command != "create"
        )
        if package.exists():
            base.recover_transaction(package)
            select_package_profile(package)
        elif args.command == "create":
            select_profile(args.profile)
        args.handler(args)
        return 0
    except ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
