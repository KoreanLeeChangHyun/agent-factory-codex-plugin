#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    sys.stderr.write(
        "error: required package 'jsonschema' is not installed; "
        "install scripts/requirements.txt\n"
    )
    raise SystemExit(2)


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
SCHEMA_ROOT = SKILL_ROOT / "assets" / "schema"
PROFILE_PATH = SKILL_ROOT / "assets" / "profiles" / "intake.profile.json"
SCHEMA_PATHS = {
    "metadata": SCHEMA_ROOT / "metadata.schema.json",
    "title": SCHEMA_ROOT / "title.schema.json",
    "toc": SCHEMA_ROOT / "table-of-contents.schema.json",
    "section": SCHEMA_ROOT / "section.schema.json",
    "blocks": SCHEMA_ROOT / "blocks.schema.json",
}
METADATA_PATH = Path("data/metadata.json")
TITLE_PATH = Path("data/title.json")
TOC_PATH = Path("data/table-of-contents.json")
SECTIONS_PATH = Path("data/sections")
BLOCK_INDEX_PATH = Path("blocks/index.json")
MANAGER_PATH = Path(".manager")
JOURNAL_PATH = MANAGER_PATH / "transaction.json"
PROTECTED_METADATA_FIELDS = {
    "schemaVersion",
    "documentVersion",
    "id",
    "artifactType",
    "lifecycle",
    "createdAt",
    "updatedAt",
}
STYLE_KEYS = {"style", "styles", "css", "stylevars", "stylevariables"}


class ManagerError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot read strict JSON from {path}: {error}") from error


def parse_json(value: str, source: str) -> Any:
    try:
        return json.loads(value, parse_constant=reject_constant)
    except (ValueError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot parse strict JSON from {source}: {error}") from error


def load_object(path: Path, label: str) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ManagerError(f"{label} must be a JSON object: {path}")
    return value


@lru_cache(maxsize=1)
def profile() -> dict[str, Any]:
    return load_object(PROFILE_PATH, "Intake profile")


@lru_cache(maxsize=1)
def schemas() -> dict[str, dict[str, Any]]:
    return {name: load_object(path, f"{name} schema") for name, path in SCHEMA_PATHS.items()}


@lru_cache(maxsize=1)
def validate_schemas() -> dict[str, dict[str, Any]]:
    contracts = schemas()
    for contract in contracts.values():
        Draft202012Validator.check_schema(contract)
    current_profile = profile()
    if current_profile.get("artifactType") != "intake":
        raise ManagerError("Intake profile artifactType must be intake")
    if current_profile.get("maximumSectionDepth") != 2:
        raise ManagerError("Intake profile maximumSectionDepth must be 2")
    if current_profile.get("version") != contracts["metadata"]["properties"]["schemaVersion"]["const"]:
        raise ManagerError("Intake profile version must match metadata schemaVersion")
    required_ids = [entry["id"] for entry in current_profile.get("requiredSections", [])]
    if not required_ids or len(required_ids) != len(set(required_ids)):
        raise ManagerError("Intake profile required section ids must be non-empty and unique")
    optional_ids = [entry["id"] for entry in current_profile.get("optionalSections", [])]
    if set(required_ids) & set(optional_ids) or len(optional_ids) != len(set(optional_ids)):
        raise ManagerError("Intake profile optional section ids must be unique and disjoint")
    return contracts


def validate_instance(kind: str, value: Any) -> None:
    contract = validate_schemas()[kind]
    validator = Draft202012Validator(contract, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors
        )
        raise ManagerError(f"{kind} schema validation failed: {details}")


def assert_plain_path(path: Path, kind: str) -> None:
    if path.is_symlink():
        raise ManagerError(f"canonical {kind} must not be a symlink: {path}")
    if kind == "file" and not path.is_file():
        raise ManagerError(f"canonical file does not exist: {path}")
    if kind == "directory" and not path.is_dir():
        raise ManagerError(f"canonical directory does not exist: {path}")


def package_project_root(package: Path) -> Path:
    if package.parent.name != "intakes" or package.parent.parent.name != ".agent-factory":
        raise ManagerError("package must be <project-root>/.agent-factory/intakes/<intake-id>")
    return package.parent.parent.parent.resolve()


def resolve_package(value: str | Path, *, must_exist: bool = True) -> Path:
    requested = Path(value)
    if requested.is_symlink():
        raise ManagerError(f"canonical package must not be a symlink: {requested}")
    package = Path(os.path.abspath(requested))
    package_project_root(package)
    if must_exist:
        assert_plain_path(package, "directory")
    return package


def safe_relative_path(value: str, label: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ManagerError(f"{label} must be a safe relative path: {value}")
    return candidate


def section_path(package: Path, section_id: str) -> Path:
    if not section_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in section_id):
        raise ManagerError(f"section id must use lowercase kebab-case: {section_id}")
    return package / SECTIONS_PATH / f"{section_id}.json"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def toc_digest(sections: list[dict[str, Any]]) -> str:
    return hashlib.sha256(canonical_json_bytes(sections)).hexdigest()


def toc_entry(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": section["id"],
        "path": f"data/sections/{section['id']}.json",
        "subsections": [{"id": child["id"]} for child in section["subsections"]],
    }


def new_toc(sections: list[dict[str, Any]]) -> dict[str, Any]:
    entries = [toc_entry(section) for section in sections]
    return {"managerOwned": True, "sections": entries, "sha256": toc_digest(entries)}


def write_json_atomically(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def copy_file_atomically(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    temporary_path = Path(temporary_name)
    try:
        with source.open("rb") as input_handle, os.fdopen(descriptor, "wb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def package_lock(package: Path, timeout: float = 10.0) -> Iterable[None]:
    project_root = package_project_root(package)
    lock_root = project_root / ".agent-factory" / "runtime" / "locks" / "intakes"
    lock_root.mkdir(parents=True, exist_ok=True)
    lock_path = lock_root / f"{package.name}.lock"
    with lock_path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ManagerError(f"timed out waiting for Intake package lock: {package.name}")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recover_transaction(package: Path) -> None:
    journal_path = package / JOURNAL_PATH
    manager_root = package / MANAGER_PATH
    if manager_root.is_symlink():
        raise ManagerError(f"manager state directory must not be a symlink: {manager_root}")
    if not journal_path.exists():
        shutil.rmtree(manager_root / "transactions", ignore_errors=True)
        return
    journal = load_object(journal_path, "transaction journal")
    if set(journal) != {"version", "id", "entries"} or journal["version"] != 1:
        raise ManagerError("transaction journal has an unsupported shape or version")
    if not isinstance(journal["id"], str) or not journal["id"].isalnum():
        raise ManagerError("transaction journal id is invalid")
    if not isinstance(journal["entries"], list):
        raise ManagerError("transaction journal entries must be an array")
    transaction_root = package / MANAGER_PATH / "transactions" / journal["id"]
    for entry in journal["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "existed", "backup", "stage"}:
            raise ManagerError("transaction journal entry has an unsupported shape")
        if not isinstance(entry["existed"], bool):
            raise ManagerError("transaction journal existed flag must be boolean")
        relative = safe_relative_path(entry["path"], "transaction target")
        target = package / relative
        if entry["existed"]:
            backup_relative = safe_relative_path(entry["backup"], "transaction backup")
            if backup_relative.parts[0] != "backup":
                raise ManagerError("transaction backup must remain under backup/")
            backup = transaction_root / backup_relative
            assert_plain_path(backup, "file")
            copy_file_atomically(backup, target)
        else:
            target.unlink(missing_ok=True)
    journal_path.unlink(missing_ok=True)
    shutil.rmtree(transaction_root, ignore_errors=True)


def commit_transaction(
    package: Path,
    *,
    json_writes: dict[Path, Any] | None = None,
    file_writes: dict[Path, Path] | None = None,
    deletes: Iterable[Path] = (),
    full_validation: bool = False,
) -> None:
    json_writes = json_writes or {}
    file_writes = file_writes or {}
    deletes = list(deletes)
    manager_root = package / MANAGER_PATH
    if manager_root.is_symlink():
        raise ManagerError(f"manager state directory must not be a symlink: {manager_root}")
    transaction_id = uuid.uuid4().hex
    transaction_root = package / MANAGER_PATH / "transactions" / transaction_id
    stage_root = transaction_root / "stage"
    backup_root = transaction_root / "backup"
    entries: list[dict[str, Any]] = []
    targets = list(json_writes) + list(file_writes) + list(deletes)
    if len(targets) != len(set(targets)):
        raise ManagerError("transaction target paths must be unique")
    try:
        for index, target in enumerate(targets):
            try:
                relative = target.relative_to(package)
            except ValueError as error:
                raise ManagerError(f"transaction target escapes Intake package: {target}") from error
            stage_name = f"{index}.new"
            backup_name = f"{index}.old"
            existed = target.exists()
            if target.is_symlink():
                raise ManagerError(f"transaction target must not be a symlink: {relative}")
            if existed:
                copy_file_atomically(target, backup_root / backup_name)
            if target in json_writes:
                stage = stage_root / stage_name
                write_json_atomically(stage, json_writes[target])
            elif target in file_writes:
                copy_file_atomically(file_writes[target], stage_root / stage_name)
            entries.append(
                {
                    "path": relative.as_posix(),
                    "existed": existed,
                    "backup": f"backup/{backup_name}",
                    "stage": None if target in deletes else f"stage/{stage_name}",
                }
            )
        journal = {"version": 1, "id": transaction_id, "entries": entries}
        write_json_atomically(package / JOURNAL_PATH, journal)
        for entry in entries:
            target = package / entry["path"]
            if entry["stage"] is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(transaction_root / entry["stage"], target)
        validate_package(package, full=full_validation)
    except Exception:
        if (package / JOURNAL_PATH).exists():
            recover_transaction(package)
        else:
            shutil.rmtree(transaction_root, ignore_errors=True)
        raise
    (package / JOURNAL_PATH).unlink(missing_ok=True)
    shutil.rmtree(transaction_root, ignore_errors=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def next_document_version(value: str) -> str:
    major, minor, patch = (int(part) for part in value.split("."))
    return f"{major}.{minor}.{patch + 1}"


def updated_metadata(package: Path) -> dict[str, Any]:
    metadata = load_metadata(package)
    metadata["documentVersion"] = next_document_version(metadata["documentVersion"])
    metadata["updatedAt"] = now()
    metadata["readiness"]["contractValid"] = True
    validate_instance("metadata", metadata)
    return metadata


def reject_actual_style(value: Any, location: str = "content") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "").replace("_", "") in STYLE_KEYS:
                raise ManagerError(f"actual style data is not allowed in canonical Intake {location}: {key}")
            reject_actual_style(child, location)
    elif isinstance(value, list):
        for child in value:
            reject_actual_style(child, location)


def replacement_value(args: argparse.Namespace) -> Any:
    value_file = getattr(args, "value_file", None)
    value = getattr(args, "value", None)
    if value_file is not None:
        if value is not None:
            raise ManagerError("provide either a JSON value or --value-file, not both")
        return load_json(Path(value_file))
    if value is None:
        raise ManagerError("command requires a JSON value or --value-file")
    return parse_json(value, "command argument")


def load_metadata(package: Path) -> dict[str, Any]:
    return load_object(package / METADATA_PATH, "metadata")


def load_toc(package: Path) -> dict[str, Any]:
    return load_object(package / TOC_PATH, "table of contents")


def load_sections(package: Path, toc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return list(iter_sections(package, toc))


def iter_sections(package: Path, toc: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
    current_toc = toc if toc is not None else load_toc(package)
    for entry in current_toc["sections"]:
        expected = section_path(package, entry["id"])
        if entry["path"] != expected.relative_to(package).as_posix():
            raise ManagerError(f"section path does not match section id: {entry['id']}")
        if expected.is_symlink() or not expected.is_file():
            raise ManagerError(f"canonical section file does not exist or is a symlink: {expected}")
        section = load_object(expected, "section")
        validate_instance("section", section)
        if section["id"] != entry["id"]:
            raise ManagerError(f"section file id does not match table of contents: {entry['id']}")
        if toc_entry(section) != entry:
            raise ManagerError(f"section hierarchy does not match table of contents: {entry['id']}")
        yield section


def all_content_items(sections: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for section in sections:
        yield from section["content"]
        for subsection in section["subsections"]:
            yield from subsection["content"]


def summarize_sections(package: Path, toc: dict[str, Any]) -> list[dict[str, Any]]:
    return [summarize_section(section) for section in iter_sections(package, toc)]


def summarize_section(section: dict[str, Any]) -> dict[str, Any]:
    hierarchy_ids = [section["id"], *(entry["id"] for entry in section["subsections"])]
    kinds: set[str] = set()
    blockers: list[str] = []
    pending_interviews: list[str] = []
    typed_refs: list[dict[str, Any]] = []
    block_refs: list[str] = []
    dispositions: list[dict[str, Any]] = []
    for container in [section, *section["subsections"]]:
        item_ids = [entry["id"] for entry in container["content"]]
        if len(item_ids) != len(set(item_ids)):
            raise ManagerError(f"content item ids must be unique within {container['id']}")
        for content_item in container["content"]:
            reject_actual_style(content_item["content"])
            reject_actual_style(content_item.get("attributes", {}), "attributes")
            kinds.add(content_item["kind"])
            typed_refs.extend(content_item.get("sourceRefs", []))
            if "blockRef" in content_item:
                block_refs.append(content_item["blockRef"])
            attributes = content_item.get("attributes", {})
            if content_item["kind"] == "disposition":
                dispositions.append(
                    {
                        "id": content_item["id"],
                        "targetStatus": attributes.get("targetStatus"),
                        "evidenceCount": len(content_item.get("sourceRefs", [])),
                    }
                )
            if content_item["kind"] == "open-item" and attributes.get("blocking") is True and attributes.get("resolved") is not True:
                blockers.append(content_item["id"])
            if content_item["kind"] == "interview" and attributes.get("status") == "pending":
                pending_interviews.append(content_item["id"])
    return {
        "id": section["id"],
        "hierarchyIds": hierarchy_ids,
        "kinds": kinds,
        "blockers": blockers,
        "pendingInterviews": pending_interviews,
        "typedRefs": typed_refs,
        "blockRefs": block_refs,
        "dispositions": dispositions,
    }


def validate_typed_paths(package: Path, metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> None:
    project_root = package_project_root(package)
    references: list[dict[str, Any]] = list(metadata["provenance"]["sourceRefs"])
    references.extend(relation["target"] for relation in metadata["relations"])
    for summary in summaries:
        references.extend(summary["typedRefs"])
    for reference in references:
        relative = safe_relative_path(reference["path"], "typed reference path")
        target = project_root / relative
        try:
            target.resolve(strict=False).relative_to(project_root)
        except ValueError as error:
            raise ManagerError(f"typed reference escapes project root: {relative}") from error
        if not target.exists():
            raise ManagerError(f"typed reference does not exist: {relative}")
        if "anchor" not in reference:
            continue
        if not target.is_dir() or not (target / METADATA_PATH).is_file():
            raise ManagerError("typed reference anchor path must target a sectioned package root")
        target_metadata = load_object(target / METADATA_PATH, "referenced metadata")
        if target_metadata.get("artifactType") != reference["artifactType"] or target_metadata.get("id") != reference["id"]:
            raise ManagerError("typed reference identity does not match referenced package metadata")
        target_toc = load_object(target / TOC_PATH, "referenced table of contents")
        if target_toc.get("sha256") != toc_digest(target_toc.get("sections", [])):
            raise ManagerError("typed reference target table of contents integrity check failed")
        anchor = reference["anchor"]
        entry = next((item for item in target_toc["sections"] if item.get("id") == anchor["sectionId"]), None)
        if entry is None:
            raise ManagerError("typed reference anchor section does not exist")
        expected = f"data/sections/{anchor['sectionId']}.json"
        if entry.get("path") != expected:
            raise ManagerError("typed reference anchor section path is not canonical")
        target_section_path = target / expected
        assert_plain_path(target_section_path, "file")
        target_section = load_object(target_section_path, "referenced section")
        if target_section.get("id") != anchor["sectionId"] or toc_entry(target_section) != entry:
            raise ManagerError("typed reference anchor section does not match table of contents")
        if not any(item.get("id") == anchor["itemId"] for item in all_content_items([target_section])):
            raise ManagerError("typed reference anchor item does not exist")


def validate_blocks(package: Path, block_refs: Iterable[str], *, full: bool) -> tuple[dict[str, Any], list[str]]:
    index = load_object(package / BLOCK_INDEX_PATH, "block index")
    validate_instance("blocks", index)
    indexed = {entry["path"]: entry for entry in index["blocks"]}
    if len(indexed) != len(index["blocks"]):
        raise ManagerError("block index paths must be unique")
    for relative_value, entry in indexed.items():
        relative = safe_relative_path(relative_value, "block path")
        if relative.parts[0] != "blocks" or relative == BLOCK_INDEX_PATH:
            raise ManagerError(f"block path must remain under blocks/ and not replace index: {relative}")
        target = package / relative
        assert_plain_path(target, "file")
        try:
            target.resolve().relative_to(package / "blocks")
        except ValueError as error:
            raise ManagerError(f"block path escapes blocks directory: {relative}") from error
        if target.stat().st_size != entry["sizeBytes"]:
            raise ManagerError(f"block integrity mismatch: {relative}")
        if full and file_sha256(target) != entry["sha256"]:
            raise ManagerError(f"block integrity mismatch: {relative}")
    actual = {
        path.relative_to(package).as_posix()
        for path in (package / "blocks").rglob("*")
        if (path.is_file() or path.is_symlink()) and path != package / BLOCK_INDEX_PATH
    }
    if actual != set(indexed):
        extra = sorted(actual - set(indexed))
        missing = sorted(set(indexed) - actual)
        raise ManagerError(f"block file set does not match block index; extra={extra}, missing={missing}")
    for block_ref in block_refs:
        if block_ref not in indexed:
            raise ManagerError(f"content references an unregistered block: {block_ref}")
    return index, list(indexed)


def required_section_ids() -> list[str]:
    return [entry["id"] for entry in profile()["requiredSections"]]


def optional_section_ids() -> set[str]:
    return {entry["id"] for entry in profile()["optionalSections"]}


def unresolved_blockers(summaries: list[dict[str, Any]]) -> list[str]:
    return [item_id for summary in summaries for item_id in summary["blockers"]]


def validate_profile(metadata: dict[str, Any], summaries: list[dict[str, Any]]) -> None:
    ids = [summary["id"] for summary in summaries]
    if len(ids) != len(set(ids)):
        raise ManagerError("section ids must be unique")
    required = required_section_ids()
    positions = [ids.index(section_id) for section_id in required if section_id in ids]
    if len(positions) != len(required) or positions != sorted(positions):
        raise ManagerError("required sections must exist exactly once in profile order")
    allowed = set(required) | optional_section_ids()
    unknown = [section_id for section_id in ids if section_id not in allowed]
    if unknown:
        raise ManagerError(f"sections are not declared by the Intake profile: {', '.join(unknown)}")
    hierarchy_ids = [item_id for summary in summaries for item_id in summary["hierarchyIds"]]
    if len(hierarchy_ids) != len(set(hierarchy_ids)):
        raise ManagerError("section and subsection ids must be unique across the Intake")

    status = metadata["lifecycle"]["status"]
    blockers = unresolved_blockers(summaries)
    if status == "blocked" and not blockers:
        raise ManagerError("blocked Intake requires an unresolved blocking open item")
    if status in {"closed", "superseded"}:
        dispositions = [entry for summary in summaries for entry in summary["dispositions"]]
        matching = [
            entry
            for entry in dispositions
            if entry["targetStatus"] == status and entry["evidenceCount"] > 0
        ]
        if not matching:
            raise ManagerError(
                f"{status} Intake requires an evidence-backed disposition item targeting {status}"
            )
    if status != "ready":
        return

    readiness = metadata["readiness"]
    failed = [
        key
        for key in ("contractValid", "evidenceComplete", "requirementsComplete", "specificationConsistent", "executionReady")
        if not readiness[key]
    ]
    if failed:
        raise ManagerError(f"ready Intake has failed readiness flags: {', '.join(failed)}")
    if readiness["reviewedAt"] is None:
        raise ManagerError("ready Intake requires readiness.reviewedAt")
    if blockers:
        raise ManagerError(f"ready Intake has unresolved blocking open items: {', '.join(blockers)}")
    by_id = {summary["id"]: summary for summary in summaries}
    for section_rule in profile()["requiredSections"]:
        kinds = by_id[section_rule["id"]]["kinds"]
        missing = [kind for kind in section_rule["requiredKinds"] if kind not in kinds]
        if missing:
            raise ManagerError(
                f"ready Intake section {section_rule['id']} is missing required content kinds: {', '.join(missing)}"
            )
    pending_interviews = [item_id for summary in summaries for item_id in summary["pendingInterviews"]]
    if pending_interviews:
        raise ManagerError(f"ready Intake contains pending interviews: {', '.join(pending_interviews)}")


def validate_package(package_value: str | Path, *, full: bool = False) -> dict[str, Any]:
    package = resolve_package(package_value)
    for directory in (package / "data", package / SECTIONS_PATH, package / "blocks"):
        assert_plain_path(directory, "directory")
    for path in (package / METADATA_PATH, package / TITLE_PATH, package / TOC_PATH, package / BLOCK_INDEX_PATH):
        assert_plain_path(path, "file")

    metadata = load_metadata(package)
    title = load_object(package / TITLE_PATH, "title")
    toc = load_toc(package)
    validate_instance("metadata", metadata)
    validate_instance("title", title)
    validate_instance("toc", toc)
    if metadata["id"] != package.name:
        raise ManagerError(f"Intake id {metadata['id']!r} must match package directory {package.name!r}")
    if toc["sha256"] != toc_digest(toc["sections"]):
        raise ManagerError("manager-owned table of contents integrity check failed")
    indexed_section_files = {entry["path"] for entry in toc["sections"]}
    actual_section_files = {
        path.relative_to(package).as_posix()
        for path in (package / SECTIONS_PATH).iterdir()
        if path.is_file() or path.is_symlink()
    }
    if actual_section_files != indexed_section_files:
        extra = sorted(actual_section_files - indexed_section_files)
        missing = sorted(indexed_section_files - actual_section_files)
        raise ManagerError(
            f"section file set does not match table of contents; extra={extra}, missing={missing}"
        )
    summaries = summarize_sections(package, toc)
    validate_profile(metadata, summaries)
    validate_typed_paths(package, metadata, summaries)
    block_refs = [block_ref for summary in summaries for block_ref in summary["blockRefs"]]
    _, block_files = validate_blocks(package, block_refs, full=full)

    files = [METADATA_PATH.as_posix(), TITLE_PATH.as_posix(), TOC_PATH.as_posix(), BLOCK_INDEX_PATH.as_posix()]
    files.extend(entry["path"] for entry in toc["sections"])
    files.extend(block_files)
    return {
        "valid": True,
        "schemaVersion": metadata["schemaVersion"],
        "profile": f"{profile()['id']}@{profile()['version']}",
        "id": metadata["id"],
        "status": metadata["lifecycle"]["status"],
        "sectionCount": len(summaries),
        "validationMode": "full" if full else "fast",
        "files": files,
    }


def load_focused_section(package: Path, section_id: str) -> dict[str, Any]:
    for path in (package / METADATA_PATH, package / TITLE_PATH, package / TOC_PATH, package / BLOCK_INDEX_PATH):
        assert_plain_path(path, "file")
    metadata = load_metadata(package)
    title = load_object(package / TITLE_PATH, "title")
    toc = load_toc(package)
    validate_instance("metadata", metadata)
    validate_instance("title", title)
    validate_instance("toc", toc)
    if metadata["id"] != package.name:
        raise ManagerError(f"Intake id {metadata['id']!r} must match package directory {package.name!r}")
    if toc["sha256"] != toc_digest(toc["sections"]):
        raise ManagerError("manager-owned table of contents integrity check failed")
    toc_ids = [entry["id"] for entry in toc["sections"]]
    required = required_section_ids()
    positions = [toc_ids.index(required_id) for required_id in required if required_id in toc_ids]
    if len(positions) != len(required) or positions != sorted(positions):
        raise ManagerError("required sections must exist exactly once in profile order")
    allowed = set(required) | optional_section_ids()
    if len(toc_ids) != len(set(toc_ids)) or any(item_id not in allowed for item_id in toc_ids):
        raise ManagerError("table of contents does not match the Intake profile")
    indexed = {entry["path"] for entry in toc["sections"]}
    actual = {
        path.relative_to(package).as_posix()
        for path in (package / SECTIONS_PATH).iterdir()
        if path.is_file() or path.is_symlink()
    }
    if actual != indexed:
        raise ManagerError("section file set does not match table of contents")
    entry = next((candidate for candidate in toc["sections"] if candidate["id"] == section_id), None)
    if entry is None:
        raise ManagerError(f"section does not exist: {section_id}")
    path = section_path(package, section_id)
    if entry["path"] != path.relative_to(package).as_posix():
        raise ManagerError(f"section path does not match section id: {section_id}")
    assert_plain_path(path, "file")
    section = load_object(path, "section")
    validate_instance("section", section)
    if toc_entry(section) != entry:
        raise ManagerError(f"section hierarchy does not match table of contents: {section_id}")
    summary = summarize_section(section)
    validate_typed_paths(package, metadata, [summary])
    validate_blocks(package, summary["blockRefs"], full=False)
    return section


def install_section_and_toc(package: Path, section: dict[str, Any], toc: dict[str, Any]) -> None:
    validate_instance("section", section)
    validate_instance("toc", toc)
    target = section_path(package, section["id"])
    commit_transaction(
        package,
        json_writes={
            target: section,
            package / TOC_PATH: toc,
            package / METADATA_PATH: updated_metadata(package),
        },
    )


def command_check_schemas(_: argparse.Namespace) -> None:
    contracts = validate_schemas()
    current_profile = profile()
    print(
        json.dumps(
            {
                "valid": True,
                "schemaVersion": contracts["metadata"]["properties"]["schemaVersion"]["const"],
                "profile": f"{current_profile['id']}@{current_profile['version']}",
                "schemas": sorted(path.name for path in SCHEMA_PATHS.values()),
            }
        )
    )


def command_create(args: argparse.Namespace) -> None:
    package = resolve_package(args.package, must_exist=False)
    if package.name != args.id:
        raise ManagerError("--id must match the package directory name")
    if package.exists():
        raise ManagerError(f"package already exists: {package}")
    package.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".{args.id}.", dir=package.parent))
    staging_package = staging_root / ".agent-factory" / "intakes" / args.id
    timestamp = now()
    current_profile = profile()
    sections = [
        {"id": entry["id"], "title": entry["title"], "content": [], "subsections": []}
        for entry in current_profile["requiredSections"]
    ]
    metadata = {
        "schemaVersion": current_profile["version"],
        "documentVersion": "1.0.0",
        "id": args.id,
        "artifactType": "intake",
        "projectId": args.project_id,
        "lifecycle": {"phase": "intake", "status": "draft"},
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "language": args.language,
        "theme": args.theme,
        "provenance": {"createdBy": "Human", "generatedBy": "Agent Factory intake manager", "sourceRefs": []},
        "relations": [],
        "readiness": {
            "contractValid": True,
            "evidenceComplete": False,
            "requirementsComplete": False,
            "specificationConsistent": False,
            "executionReady": False,
            "reviewedAt": None,
            "findings": [],
        },
    }
    try:
        (staging_package / SECTIONS_PATH).mkdir(parents=True)
        (staging_package / "blocks").mkdir()
        write_json_atomically(staging_package / METADATA_PATH, metadata)
        write_json_atomically(staging_package / TITLE_PATH, {"title": args.title})
        for section in sections:
            write_json_atomically(section_path(staging_package, section["id"]), section)
        write_json_atomically(staging_package / TOC_PATH, new_toc(sections))
        write_json_atomically(staging_package / BLOCK_INDEX_PATH, {"blocks": []})
        validate_package(staging_package)
        os.rename(staging_package, package)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_show(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    if args.section is not None:
        print(json.dumps(load_focused_section(package, args.section), ensure_ascii=False, indent=2))
        return
    validate_package(package)
    toc = load_toc(package)
    document = {
        "metadata": load_metadata(package),
        "title": load_object(package / TITLE_PATH, "title")["title"],
        "tableOfContents": toc,
        "sections": load_sections(package, toc),
        "blocks": load_object(package / BLOCK_INDEX_PATH, "block index")["blocks"],
    }
    print(json.dumps(document, ensure_ascii=False, indent=2))


def command_title_set(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    candidate = {"title": args.title}
    validate_instance("title", candidate)
    commit_transaction(
        package,
        json_writes={package / TITLE_PATH: candidate, package / METADATA_PATH: updated_metadata(package)},
    )
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_metadata_set(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    if args.field in PROTECTED_METADATA_FIELDS:
        raise ManagerError(f"metadata field must not be updated directly: {args.field}")
    contract = validate_schemas()["metadata"]
    if args.field not in contract["properties"]:
        raise ManagerError(f"unknown metadata field: {args.field}")
    candidate = load_metadata(package)
    candidate[args.field] = replacement_value(args)
    candidate["documentVersion"] = next_document_version(candidate["documentVersion"])
    candidate["updatedAt"] = now()
    candidate["readiness"]["contractValid"] = True
    validate_instance("metadata", candidate)
    summaries = summarize_sections(package, load_toc(package))
    validate_profile(candidate, summaries)
    validate_typed_paths(package, candidate, summaries)
    commit_transaction(package, json_writes={package / METADATA_PATH: candidate})
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    candidate = replacement_value(args)
    if not isinstance(candidate, dict):
        raise ManagerError("section candidate must be a JSON object")
    validate_instance("section", candidate)
    toc = load_toc(package)
    entry_index = next((index for index, entry in enumerate(toc["sections"]) if entry["id"] == candidate["id"]), None)
    if entry_index is None:
        raise ManagerError("section-put only replaces an existing section; use section-add")
    toc["sections"][entry_index] = toc_entry(candidate)
    toc["sha256"] = toc_digest(toc["sections"])
    install_section_and_toc(package, candidate, toc)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_item_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    path = section_path(package, args.section_id)
    assert_plain_path(path, "file")
    section = load_object(path, "section")
    candidate = replacement_value(args)
    if not isinstance(candidate, dict):
        raise ManagerError("content item candidate must be a JSON object")
    if args.subsection is None:
        items = section["content"]
    else:
        subsection = next((entry for entry in section["subsections"] if entry["id"] == args.subsection), None)
        if subsection is None:
            raise ManagerError(f"subsection does not exist: {args.subsection}")
        items = subsection["content"]
    existing = next((index for index, entry in enumerate(items) if entry["id"] == candidate.get("id")), None)
    if existing is None:
        items.append(candidate)
    else:
        items[existing] = candidate
    validate_instance("section", section)
    toc = load_toc(package)
    install_section_and_toc(package, section, toc)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_items_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    path = section_path(package, args.section_id)
    assert_plain_path(path, "file")
    section = load_object(path, "section")
    candidates = replacement_value(args)
    if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
        raise ManagerError("content item batch must be a JSON array of objects")
    if args.subsection is None:
        items = section["content"]
    else:
        subsection = next((entry for entry in section["subsections"] if entry["id"] == args.subsection), None)
        if subsection is None:
            raise ManagerError(f"subsection does not exist: {args.subsection}")
        items = subsection["content"]
    positions = {entry["id"]: index for index, entry in enumerate(items)}
    candidate_ids = [candidate.get("id") for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ManagerError("content item ids must be unique within a batch")
    for candidate in candidates:
        item_id = candidate.get("id")
        if item_id in positions:
            items[positions[item_id]] = candidate
        else:
            positions[item_id] = len(items)
            items.append(candidate)
    validate_instance("section", section)
    install_section_and_toc(package, section, load_toc(package))
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_add(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    candidate = replacement_value(args)
    if not isinstance(candidate, dict):
        raise ManagerError("section candidate must be a JSON object")
    validate_instance("section", candidate)
    if candidate["id"] not in optional_section_ids():
        raise ManagerError(f"optional section is not declared by the Intake profile: {candidate['id']}")
    toc = load_toc(package)
    if any(entry["id"] == candidate["id"] for entry in toc["sections"]):
        raise ManagerError(f"section already exists: {candidate['id']}")
    index = len(toc["sections"])
    if args.before is not None:
        index = next((i for i, entry in enumerate(toc["sections"]) if entry["id"] == args.before), -1)
    elif args.after is not None:
        found = next((i for i, entry in enumerate(toc["sections"]) if entry["id"] == args.after), -1)
        index = found + 1 if found >= 0 else -1
    if index < 0:
        raise ManagerError("section positioning reference does not exist")
    toc["sections"].insert(index, toc_entry(candidate))
    toc["sha256"] = toc_digest(toc["sections"])
    install_section_and_toc(package, candidate, toc)
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_move(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    toc = load_toc(package)
    source_index = next((i for i, entry in enumerate(toc["sections"]) if entry["id"] == args.section_id), -1)
    if source_index < 0:
        raise ManagerError(f"section does not exist: {args.section_id}")
    entry = toc["sections"].pop(source_index)
    target_id = args.before if args.before is not None else args.after
    target_index = next((i for i, candidate in enumerate(toc["sections"]) if candidate["id"] == target_id), -1)
    if target_index < 0:
        raise ManagerError("section positioning reference does not exist")
    if args.after is not None:
        target_index += 1
    toc["sections"].insert(target_index, entry)
    required_positions = [next(i for i, item in enumerate(toc["sections"]) if item["id"] == section_id) for section_id in required_section_ids()]
    if required_positions != sorted(required_positions):
        raise ManagerError("section move must preserve required section profile order")
    toc["sha256"] = toc_digest(toc["sections"])
    validate_instance("toc", toc)
    commit_transaction(
        package,
        json_writes={package / TOC_PATH: toc, package / METADATA_PATH: updated_metadata(package)},
    )
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_section_remove(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    if args.section_id in required_section_ids():
        raise ManagerError(f"required section must not be removed: {args.section_id}")
    toc = load_toc(package)
    retained = [entry for entry in toc["sections"] if entry["id"] != args.section_id]
    if len(retained) == len(toc["sections"]):
        raise ManagerError(f"section does not exist: {args.section_id}")
    target = section_path(package, args.section_id)
    toc["sections"] = retained
    toc["sha256"] = toc_digest(retained)
    commit_transaction(
        package,
        json_writes={package / TOC_PATH: toc, package / METADATA_PATH: updated_metadata(package)},
        deletes=[target],
    )
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_transition(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    metadata = load_metadata(package)
    current = metadata["lifecycle"]["status"]
    allowed = validate_schemas()["metadata"]["x-statusTransitions"][current]
    if args.status not in allowed:
        raise ManagerError(f"invalid Intake transition: {current} -> {args.status}")
    metadata["lifecycle"]["status"] = args.status
    metadata["documentVersion"] = next_document_version(metadata["documentVersion"])
    metadata["updatedAt"] = now()
    metadata["readiness"]["contractValid"] = True
    summaries = summarize_sections(package, load_toc(package))
    validate_profile(metadata, summaries)
    validate_instance("metadata", metadata)
    commit_transaction(
        package,
        json_writes={package / METADATA_PATH: metadata},
        full_validation=args.status == "ready",
    )
    print(json.dumps(validate_package(package, full=args.status == "ready"), ensure_ascii=False))


def checked_block_target(package: Path, value: str) -> tuple[Path, str]:
    relative = safe_relative_path(value, "block path")
    if relative.parts[0] != "blocks" or relative == BLOCK_INDEX_PATH:
        raise ManagerError(f"block path must remain under blocks/ and not replace index: {relative}")
    target = package / relative
    block_root = (package / "blocks").resolve()
    try:
        target.resolve(strict=False).relative_to(block_root)
    except ValueError as error:
        raise ManagerError(f"block path escapes blocks directory: {relative}") from error
    for parent in target.parents:
        if parent == package:
            break
        if parent.exists() and parent.is_symlink():
            raise ManagerError(f"block parent must not be a symlink: {parent}")
    if target.is_symlink():
        raise ManagerError(f"block target must not be a symlink: {relative}")
    return target, relative.as_posix()


def command_block_put(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    source = Path(args.source)
    if source.is_symlink() or not source.is_file():
        raise ManagerError(f"block source must be a regular non-symlink file: {source}")
    target, relative = checked_block_target(package, args.path)
    index = load_object(package / BLOCK_INDEX_PATH, "block index")
    candidate = [entry for entry in index["blocks"] if entry["path"] != relative]
    candidate.append(
        {
            "path": relative,
            "mediaType": args.media_type,
            "description": args.description,
            "sha256": file_sha256(source),
            "sizeBytes": source.stat().st_size,
        }
    )
    candidate.sort(key=lambda entry: entry["path"])
    new_index = {"blocks": candidate}
    validate_instance("blocks", new_index)
    commit_transaction(
        package,
        json_writes={
            package / BLOCK_INDEX_PATH: new_index,
            package / METADATA_PATH: updated_metadata(package),
        },
        file_writes={target: source},
    )
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_block_remove(args: argparse.Namespace) -> None:
    package = resolve_package(args.package)
    validate_package(package)
    target, relative = checked_block_target(package, args.path)
    summaries = summarize_sections(package, load_toc(package))
    if any(relative in summary["blockRefs"] for summary in summaries):
        raise ManagerError(f"block is still referenced by section content: {relative}")
    index = load_object(package / BLOCK_INDEX_PATH, "block index")
    retained = [entry for entry in index["blocks"] if entry["path"] != relative]
    if len(retained) == len(index["blocks"]):
        raise ManagerError(f"canonical block reference does not exist: {relative}")
    commit_transaction(
        package,
        json_writes={
            package / BLOCK_INDEX_PATH: {"blocks": retained},
            package / METADATA_PATH: updated_metadata(package),
        },
        deletes=[target],
    )
    print(json.dumps(validate_package(package), ensure_ascii=False))


def command_validate(args: argparse.Namespace) -> None:
    print(json.dumps(validate_package(args.package, full=args.full), ensure_ascii=False))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage sectioned Agent Factory Intake packages")
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check-schemas", help="validate Intake schemas and profile")
    check.set_defaults(handler=command_check_schemas)

    create = commands.add_parser("create", help="create a split draft Intake package")
    create.add_argument("package")
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--project-id", required=True)
    create.add_argument("--language", default="ko")
    create.add_argument("--theme", required=True)
    create.set_defaults(handler=command_create)

    show = commands.add_parser("show", help="validate and display a package or one section")
    show.add_argument("package")
    show.add_argument("--section")
    show.set_defaults(handler=command_show)

    title_set = commands.add_parser("title-set", help="replace the canonical title")
    title_set.add_argument("package")
    title_set.add_argument("title")
    title_set.set_defaults(handler=command_title_set)

    metadata_set = commands.add_parser("metadata-set", help="replace one mutable metadata field")
    metadata_set.add_argument("package")
    metadata_set.add_argument("field")
    metadata_set.add_argument("value", nargs="?")
    metadata_set.add_argument("--value-file")
    metadata_set.set_defaults(handler=command_metadata_set)

    section_put = commands.add_parser("section-put", help="replace an existing canonical section")
    section_put.add_argument("package")
    section_put.add_argument("value", nargs="?")
    section_put.add_argument("--value-file")
    section_put.set_defaults(handler=command_section_put)

    item_put = commands.add_parser("section-item-put", help="add or replace one section content item")
    item_put.add_argument("package")
    item_put.add_argument("section_id")
    item_put.add_argument("value", nargs="?")
    item_put.add_argument("--value-file")
    item_put.add_argument("--subsection")
    item_put.set_defaults(handler=command_section_item_put)

    items_put = commands.add_parser("section-items-put", help="add or replace multiple content items in one revision")
    items_put.add_argument("package")
    items_put.add_argument("section_id")
    items_put.add_argument("value", nargs="?")
    items_put.add_argument("--value-file")
    items_put.add_argument("--subsection")
    items_put.set_defaults(handler=command_section_items_put)

    section_add = commands.add_parser("section-add", help="add a profile-declared optional section")
    section_add.add_argument("package")
    section_add.add_argument("value", nargs="?")
    section_add.add_argument("--value-file")
    position = section_add.add_mutually_exclusive_group()
    position.add_argument("--before")
    position.add_argument("--after")
    section_add.set_defaults(handler=command_section_add)

    section_move = commands.add_parser("section-move", help="move a section while preserving required order")
    section_move.add_argument("package")
    section_move.add_argument("section_id")
    move_position = section_move.add_mutually_exclusive_group(required=True)
    move_position.add_argument("--before")
    move_position.add_argument("--after")
    section_move.set_defaults(handler=command_section_move)

    section_remove = commands.add_parser("section-remove", help="remove an optional section")
    section_remove.add_argument("package")
    section_remove.add_argument("section_id")
    section_remove.set_defaults(handler=command_section_remove)

    validate = commands.add_parser("validate", help="validate a complete Intake package")
    validate.add_argument("package")
    validate.add_argument("--full", action="store_true", help="rehash every registered block")
    validate.set_defaults(handler=command_validate)

    transition = commands.add_parser("transition", help="apply a schema-owned Intake transition")
    transition.add_argument("package")
    transition.add_argument(
        "status",
        choices=["draft", "validating", "ready", "blocked", "closed", "superseded"],
    )
    transition.set_defaults(handler=command_transition)

    block_put = commands.add_parser("block-put", help="stream an external block into the canonical package")
    block_put.add_argument("package")
    block_put.add_argument("source")
    block_put.add_argument("--path", required=True)
    block_put.add_argument("--media-type", required=True)
    block_put.add_argument("--description", required=True)
    block_put.set_defaults(handler=command_block_put)

    block_remove = commands.add_parser("block-remove", help="remove an unreferenced canonical block")
    block_remove.add_argument("package")
    block_remove.add_argument("path")
    block_remove.set_defaults(handler=command_block_remove)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if not hasattr(args, "package"):
            args.handler(args)
            return 0
        package = resolve_package(args.package, must_exist=args.command != "create")
        with package_lock(package):
            if package.exists():
                recover_transaction(package)
            args.handler(args)
        return 0
    except ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
