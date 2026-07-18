#!/usr/bin/env python3
"""Shared sectioned-document package engine for Agent Factory artifacts."""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import os
import shutil
import stat
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
SKILL_ROOT = SCRIPT_ROOT.parent.parent
SCHEMA_ROOT = SKILL_ROOT / "schema"
PROFILE_PATH = SKILL_ROOT / "profiles" / "unconfigured.profile.json"
ARTIFACT_TYPE = "document"
ARTIFACT_LABEL = "Document"
PACKAGE_COLLECTION = "documents"
LOCK_COLLECTION = "documents"
LIFECYCLE_PHASE = "document"
INITIAL_STATUS = "draft"
INITIAL_READINESS: dict[str, Any] | None = {}
GENERATED_BY = "Agent Factory sectioned-document manager"
MUTATION_POLICY: dict[str, Any] | None = None
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
DIRECTORY_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
FILE_OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


class ManagerError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot read strict JSON from {path}: {error}") from error


def parse_json(value: str, source: str) -> Any:
    try:
        return json.loads(value, parse_constant=reject_constant)
    except (ValueError, json.JSONDecodeError) as error:
        raise ManagerError(
            f"cannot parse strict JSON from {source}: {error}"
        ) from error


def load_object(path: Path, label: str) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        raise ManagerError(f"{label} must be a JSON object: {path}")
    return value


@lru_cache(maxsize=1)
def profile() -> dict[str, Any]:
    return load_object(PROFILE_PATH, f"{ARTIFACT_LABEL} profile")


@lru_cache(maxsize=1)
def schemas() -> dict[str, dict[str, Any]]:
    return {
        name: load_object(path, f"{name} schema") for name, path in SCHEMA_PATHS.items()
    }


@lru_cache(maxsize=1)
def validate_schemas() -> dict[str, dict[str, Any]]:
    contracts = schemas()
    for contract in contracts.values():
        Draft202012Validator.check_schema(contract)
    current_profile = profile()
    metadata_artifact_type = contracts["metadata"]["properties"]["artifactType"].get(
        "const"
    )
    if current_profile.get("artifactType") != metadata_artifact_type:
        raise ManagerError(f"{ARTIFACT_LABEL} profile artifactType must match metadata")
    if current_profile.get("maximumSectionDepth") != 2:
        raise ManagerError(f"{ARTIFACT_LABEL} profile maximumSectionDepth must be 2")
    if (
        current_profile.get("version")
        != contracts["metadata"]["properties"]["schemaVersion"]["const"]
    ):
        raise ManagerError(
            f"{ARTIFACT_LABEL} profile version must match metadata schemaVersion"
        )
    required_ids = [
        entry["id"] for entry in current_profile.get("requiredSections", [])
    ]
    if not required_ids or len(required_ids) != len(set(required_ids)):
        raise ManagerError(
            f"{ARTIFACT_LABEL} profile required section ids must be non-empty and unique"
        )
    optional_ids = [
        entry["id"] for entry in current_profile.get("optionalSections", [])
    ]
    if set(required_ids) & set(optional_ids) or len(optional_ids) != len(
        set(optional_ids)
    ):
        raise ManagerError(
            f"{ARTIFACT_LABEL} profile optional section ids must be unique and disjoint"
        )
    families = current_profile.get("kindFamilies", {})
    if not isinstance(families, dict) or any(
        not isinstance(name, str)
        or not name
        or not isinstance(members, list)
        or not members
        or len(members) != len(set(members))
        or not all(isinstance(member, str) and member for member in members)
        for name, members in families.items()
    ):
        raise ManagerError(
            f"{ARTIFACT_LABEL} profile kind families must contain unique non-empty kind names"
        )
    attribute_contracts = current_profile.get("kindAttributeContracts", {})
    if not isinstance(attribute_contracts, dict) or any(
        not isinstance(kind, str)
        or not isinstance(contract, dict)
        or set(contract) != {"attribute", "allowedValues"}
        or not isinstance(contract["attribute"], str)
        or not contract["attribute"]
        or not isinstance(contract["allowedValues"], list)
        or not contract["allowedValues"]
        or len(contract["allowedValues"]) != len(set(contract["allowedValues"]))
        or not all(
            isinstance(value, str) and value for value in contract["allowedValues"]
        )
        for kind, contract in attribute_contracts.items()
    ):
        raise ManagerError(
            f"{ARTIFACT_LABEL} profile kind attribute contracts are invalid"
        )
    return contracts


def configure_contract(
    *,
    skill_root: Path,
    profile_path: Path,
    metadata_schema_path: Path,
    structural_schema_root: Path,
    artifact_type: str,
    artifact_label: str,
    package_collection: str,
    lock_collection: str,
    lifecycle_phase: str,
    initial_status: str,
    initial_readiness: dict[str, Any] | None,
    generated_by: str,
    mutation_policy: dict[str, Any] | None = None,
) -> None:
    """Configure one artifact adapter without duplicating package mechanics."""
    global SKILL_ROOT, SCHEMA_ROOT, PROFILE_PATH, SCHEMA_PATHS
    global ARTIFACT_TYPE, ARTIFACT_LABEL, PACKAGE_COLLECTION, LOCK_COLLECTION
    global \
        LIFECYCLE_PHASE, \
        INITIAL_STATUS, \
        INITIAL_READINESS, \
        GENERATED_BY, \
        MUTATION_POLICY

    SKILL_ROOT = skill_root.resolve()
    SCHEMA_ROOT = metadata_schema_path.resolve().parent
    PROFILE_PATH = profile_path.resolve()
    ARTIFACT_TYPE = artifact_type
    ARTIFACT_LABEL = artifact_label
    PACKAGE_COLLECTION = package_collection
    LOCK_COLLECTION = lock_collection
    LIFECYCLE_PHASE = lifecycle_phase
    INITIAL_STATUS = initial_status
    INITIAL_READINESS = copy.deepcopy(initial_readiness)
    GENERATED_BY = generated_by
    MUTATION_POLICY = copy.deepcopy(mutation_policy)
    shared = structural_schema_root.resolve()
    SCHEMA_PATHS = {
        "metadata": metadata_schema_path.resolve(),
        "title": shared / "title.schema.json",
        "toc": shared / "table-of-contents.schema.json",
        "section": shared / "section.schema.json",
        "blocks": shared / "blocks.schema.json",
    }
    profile.cache_clear()
    schemas.cache_clear()
    validate_schemas.cache_clear()


def validate_instance(kind: str, value: Any) -> None:
    contract = validate_schemas()[kind]
    validator = Draft202012Validator(contract, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(value), key=lambda error: list(error.absolute_path)
    )
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
    if (
        package.parent.name != PACKAGE_COLLECTION
        or package.parent.parent.name != ".agent-factory"
    ):
        raise ManagerError(
            f"package must be <project-root>/.agent-factory/{PACKAGE_COLLECTION}/<{ARTIFACT_TYPE}-id>"
        )
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


def checked_package_target(package: Path, target: Path, label: str) -> Path:
    try:
        relative = target.relative_to(package)
    except ValueError as error:
        raise ManagerError(f"{label} escapes canonical package: {target}") from error
    try:
        target.resolve(strict=False).relative_to(package.resolve())
    except ValueError as error:
        raise ManagerError(
            f"{label} escapes canonical package through a symlink: {relative}"
        ) from error
    for component in target.parents:
        if component == package:
            break
        if component.is_symlink():
            raise ManagerError(f"{label} parent must not be a symlink: {component}")
    if target.is_symlink():
        raise ManagerError(f"{label} must not be a symlink: {relative}")
    return relative


@contextmanager
def package_descriptor(package: Path) -> Iterable[int]:
    try:
        descriptor = os.open(package, DIRECTORY_OPEN_FLAGS)
    except OSError as error:
        raise ManagerError(
            f"cannot securely open canonical package: {package}: {error}"
        ) from error
    try:
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def relative_parent_descriptor(
    package_fd: int,
    relative: Path,
    *,
    create: bool = False,
) -> Iterable[tuple[int, str]]:
    safe = safe_relative_path(relative.as_posix(), "package-relative file")
    descriptor = os.dup(package_fd)
    try:
        for component in safe.parts[:-1]:
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            try:
                child = os.open(component, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
            except OSError as error:
                raise ManagerError(
                    f"cannot securely traverse package-relative parent {safe.parent}: {error}"
                ) from error
            os.close(descriptor)
            descriptor = child
        yield descriptor, safe.name
    finally:
        os.close(descriptor)


def relative_file_exists(package_fd: int, relative: Path) -> bool:
    try:
        with relative_parent_descriptor(package_fd, relative) as (parent_fd, name):
            try:
                details = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return False
            if not stat.S_ISREG(details.st_mode):
                raise ManagerError(
                    f"package-relative target must be a regular file: {relative}"
                )
            return True
    except ManagerError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return False
        raise


def write_bytes_relative(package_fd: int, relative: Path, content: bytes) -> None:
    with relative_parent_descriptor(package_fd, relative, create=True) as (
        parent_fd,
        name,
    ):
        temporary_name = f".{name}.{uuid.uuid4().hex}.tmp"
        descriptor = -1
        try:
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=parent_fd,
            )
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass


def write_json_relative(package_fd: int, relative: Path, value: Any) -> None:
    content = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        + b"\n"
    )
    write_bytes_relative(package_fd, relative, content)


def copy_relative_file(package_fd: int, source: Path, target: Path) -> None:
    with relative_parent_descriptor(package_fd, source) as (
        source_parent_fd,
        source_name,
    ):
        try:
            source_fd = os.open(source_name, FILE_OPEN_FLAGS, dir_fd=source_parent_fd)
        except OSError as error:
            raise ManagerError(
                f"cannot securely open package-relative file {source}: {error}"
            ) from error
        try:
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise ManagerError(
                    f"package-relative source must be a regular file: {source}"
                )
            chunks: list[bytes] = []
            while chunk := os.read(source_fd, 1024 * 1024):
                chunks.append(chunk)
        finally:
            os.close(source_fd)
    write_bytes_relative(package_fd, target, b"".join(chunks))


def copy_external_file_relative(package_fd: int, source: Path, target: Path) -> None:
    try:
        content = source.read_bytes()
    except OSError as error:
        raise ManagerError(
            f"cannot read transaction input file {source}: {error}"
        ) from error
    write_bytes_relative(package_fd, target, content)


def replace_relative_file(package_fd: int, source: Path, target: Path) -> None:
    with relative_parent_descriptor(package_fd, source) as (
        source_parent_fd,
        source_name,
    ):
        try:
            details = os.stat(
                source_name, dir_fd=source_parent_fd, follow_symlinks=False
            )
        except OSError as error:
            raise ManagerError(
                f"cannot inspect staged file {source}: {error}"
            ) from error
        if not stat.S_ISREG(details.st_mode):
            raise ManagerError(f"staged source must be a regular file: {source}")
        with relative_parent_descriptor(package_fd, target, create=True) as (
            target_parent_fd,
            target_name,
        ):
            os.replace(
                source_name,
                target_name,
                src_dir_fd=source_parent_fd,
                dst_dir_fd=target_parent_fd,
            )


def unlink_relative(package_fd: int, relative: Path) -> None:
    with relative_parent_descriptor(package_fd, relative) as (parent_fd, name):
        try:
            os.unlink(name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def load_object_relative(package_fd: int, relative: Path, label: str) -> dict[str, Any]:
    with relative_parent_descriptor(package_fd, relative) as (parent_fd, name):
        try:
            descriptor = os.open(name, FILE_OPEN_FLAGS, dir_fd=parent_fd)
        except OSError as error:
            raise ManagerError(
                f"cannot securely open {label}: {relative}: {error}"
            ) from error
        try:
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                value = json.load(handle, parse_constant=reject_constant)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ManagerError(
                f"cannot read strict JSON from {relative}: {error}"
            ) from error
    if not isinstance(value, dict):
        raise ManagerError(f"{label} must be a JSON object: {relative}")
    return value


def remove_tree_relative(package_fd: int, relative: Path) -> None:
    def remove_child(parent_fd: int, name: str) -> None:
        try:
            child_fd = os.open(name, DIRECTORY_OPEN_FLAGS, dir_fd=parent_fd)
        except FileNotFoundError:
            return
        except OSError:
            os.unlink(name, dir_fd=parent_fd)
            return
        try:
            with os.scandir(child_fd) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        remove_child(child_fd, entry.name)
                    else:
                        os.unlink(entry.name, dir_fd=child_fd)
        finally:
            os.close(child_fd)
        os.rmdir(name, dir_fd=parent_fd)

    try:
        with relative_parent_descriptor(package_fd, relative) as (parent_fd, name):
            remove_child(parent_fd, name)
    except ManagerError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return
        raise


def section_path(package: Path, section_id: str) -> Path:
    if not section_id or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
        for character in section_id
    ):
        raise ManagerError(f"section id must use lowercase kebab-case: {section_id}")
    return package / SECTIONS_PATH / f"{section_id}.json"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
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
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with (
            source.open("rb") as input_handle,
            os.fdopen(descriptor, "wb") as output_handle,
        ):
            shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def package_lock(package: Path, timeout: float = 10.0) -> Iterable[None]:
    project_root = package_project_root(package)
    lock_root = project_root / ".agent-factory" / "runtime" / "locks" / LOCK_COLLECTION
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
                    raise ManagerError(
                        f"timed out waiting for {ARTIFACT_LABEL} package lock: {package.name}"
                    )
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def recover_transaction_with_descriptor(package_fd: int) -> None:
    if not relative_file_exists(package_fd, JOURNAL_PATH):
        remove_tree_relative(package_fd, MANAGER_PATH / "transactions")
        return
    journal = load_object_relative(package_fd, JOURNAL_PATH, "transaction journal")
    if set(journal) != {"version", "id", "entries"} or journal["version"] != 1:
        raise ManagerError("transaction journal has an unsupported shape or version")
    if not isinstance(journal["id"], str) or not journal["id"].isalnum():
        raise ManagerError("transaction journal id is invalid")
    if not isinstance(journal["entries"], list):
        raise ManagerError("transaction journal entries must be an array")
    transaction_relative = MANAGER_PATH / "transactions" / journal["id"]
    for entry in journal["entries"]:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "existed",
            "backup",
            "stage",
        }:
            raise ManagerError("transaction journal entry has an unsupported shape")
        if not isinstance(entry["existed"], bool):
            raise ManagerError("transaction journal existed flag must be boolean")
        relative = safe_relative_path(entry["path"], "transaction target")
        try:
            if entry["existed"]:
                relative_file_exists(package_fd, relative)
                backup_relative = safe_relative_path(
                    entry["backup"], "transaction backup"
                )
                if backup_relative.parts[0] != "backup":
                    raise ManagerError("transaction backup must remain under backup/")
                copy_relative_file(
                    package_fd, transaction_relative / backup_relative, relative
                )
            else:
                unlink_relative(package_fd, relative)
        except ManagerError as error:
            raise ManagerError(
                f"cannot securely recover transaction target {relative}: {error}"
            ) from error
    unlink_relative(package_fd, JOURNAL_PATH)
    remove_tree_relative(package_fd, transaction_relative)


def recover_transaction(package: Path) -> None:
    with package_descriptor(package) as package_fd:
        recover_transaction_with_descriptor(package_fd)


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
    transaction_id = uuid.uuid4().hex
    transaction_relative = MANAGER_PATH / "transactions" / transaction_id
    checked_package_target(package, package / transaction_relative, "transaction state")
    stage_root = transaction_relative / "stage"
    backup_root = transaction_relative / "backup"
    entries: list[dict[str, Any]] = []
    targets = list(json_writes) + list(file_writes) + list(deletes)
    if len(targets) != len(set(targets)):
        raise ManagerError("transaction target paths must be unique")
    with package_descriptor(package) as package_fd:
        try:
            for index, target in enumerate(targets):
                relative = checked_package_target(package, target, "transaction target")
                stage_name = f"{index}.new"
                backup_name = f"{index}.old"
                existed = relative_file_exists(package_fd, relative)
                if existed:
                    copy_relative_file(package_fd, relative, backup_root / backup_name)
                if target in json_writes:
                    write_json_relative(
                        package_fd, stage_root / stage_name, json_writes[target]
                    )
                elif target in file_writes:
                    copy_external_file_relative(
                        package_fd, file_writes[target], stage_root / stage_name
                    )
                entries.append(
                    {
                        "path": relative.as_posix(),
                        "existed": existed,
                        "backup": f"backup/{backup_name}",
                        "stage": None if target in deletes else f"stage/{stage_name}",
                    }
                )
            journal = {"version": 1, "id": transaction_id, "entries": entries}
            write_json_relative(package_fd, JOURNAL_PATH, journal)
            for entry in entries:
                target_relative = Path(entry["path"])
                if entry["stage"] is None:
                    unlink_relative(package_fd, target_relative)
                else:
                    replace_relative_file(
                        package_fd,
                        transaction_relative / entry["stage"],
                        target_relative,
                    )
            validate_package(package, full=full_validation)
        except Exception:
            if relative_file_exists(package_fd, JOURNAL_PATH):
                recover_transaction_with_descriptor(package_fd)
            else:
                remove_tree_relative(package_fd, transaction_relative)
            raise
        unlink_relative(package_fd, JOURNAL_PATH)
        remove_tree_relative(package_fd, transaction_relative)


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
    apply_mutation_lifecycle(metadata)
    mark_contract_valid(metadata)
    validate_instance("metadata", metadata)
    return metadata


def mark_contract_valid(metadata: dict[str, Any]) -> None:
    readiness = metadata.get("readiness")
    if isinstance(readiness, dict) and "contractValid" in readiness:
        readiness["contractValid"] = True


def apply_mutation_lifecycle(metadata: dict[str, Any]) -> None:
    if MUTATION_POLICY is None:
        return
    status = metadata["lifecycle"]["status"]
    if status in set(MUTATION_POLICY["terminalStatuses"]):
        raise ManagerError(
            f"terminal {ARTIFACT_LABEL} does not allow mutation: {status}"
        )
    if status != MUTATION_POLICY["readyStatus"]:
        return
    metadata["lifecycle"]["status"] = MUTATION_POLICY["draftStatus"]
    invalidate_semantic_readiness(metadata)


def invalidate_semantic_readiness(metadata: dict[str, Any]) -> None:
    readiness = metadata["readiness"]
    if MUTATION_POLICY is None:
        return
    for field in MUTATION_POLICY["invalidateReadinessFields"]:
        readiness[field] = False
    readiness["reviewedAt"] = None


def reject_actual_style(value: Any, location: str = "content") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "").replace("_", "") in STYLE_KEYS:
                raise ManagerError(
                    f"actual style data is not allowed in canonical {ARTIFACT_LABEL} {location}: {key}"
                )
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


def load_sections(
    package: Path, toc: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    return list(iter_sections(package, toc))


def iter_sections(
    package: Path, toc: dict[str, Any] | None = None
) -> Iterable[dict[str, Any]]:
    current_toc = toc if toc is not None else load_toc(package)
    for entry in current_toc["sections"]:
        expected = section_path(package, entry["id"])
        if entry["path"] != expected.relative_to(package).as_posix():
            raise ManagerError(f"section path does not match section id: {entry['id']}")
        if expected.is_symlink() or not expected.is_file():
            raise ManagerError(
                f"canonical section file does not exist or is a symlink: {expected}"
            )
        section = load_object(expected, "section")
        validate_instance("section", section)
        if section["id"] != entry["id"]:
            raise ManagerError(
                f"section file id does not match table of contents: {entry['id']}"
            )
        if toc_entry(section) != entry:
            raise ManagerError(
                f"section hierarchy does not match table of contents: {entry['id']}"
            )
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
    kind_attributes: dict[str, list[dict[str, Any]]] = {}
    section_item_ids = [
        entry["id"]
        for container in [section, *section["subsections"]]
        for entry in container["content"]
    ]
    if len(section_item_ids) != len(set(section_item_ids)):
        raise ManagerError(
            f"content item ids must be unique across top-level section {section['id']}"
        )
    for container in [section, *section["subsections"]]:
        item_ids = [entry["id"] for entry in container["content"]]
        if len(item_ids) != len(set(item_ids)):
            raise ManagerError(
                f"content item ids must be unique within {container['id']}"
            )
        for content_item in container["content"]:
            reject_actual_style(content_item["content"])
            reject_actual_style(content_item.get("attributes", {}), "attributes")
            kinds.add(content_item["kind"])
            typed_refs.extend(content_item.get("sourceRefs", []))
            if "blockRef" in content_item:
                block_refs.append(content_item["blockRef"])
            attributes = content_item.get("attributes", {})
            kind_attributes.setdefault(content_item["kind"], []).append(attributes)
            if content_item["kind"] == "disposition":
                dispositions.append(
                    {
                        "id": content_item["id"],
                        "targetStatus": attributes.get("targetStatus"),
                        "evidenceCount": len(content_item.get("sourceRefs", [])),
                    }
                )
            if (
                content_item["kind"] == "open-item"
                and attributes.get("blocking") is True
                and attributes.get("resolved") is not True
            ):
                blockers.append(content_item["id"])
            if (
                content_item["kind"] == "interview"
                and attributes.get("status") == "pending"
            ):
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
        "kindAttributes": kind_attributes,
    }


def validate_typed_paths(
    package: Path, metadata: dict[str, Any], summaries: list[dict[str, Any]]
) -> None:
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
            raise ManagerError(
                f"typed reference escapes project root: {relative}"
            ) from error
        if not target.exists():
            raise ManagerError(f"typed reference does not exist: {relative}")
        if "anchor" not in reference:
            continue
        if not target.is_dir() or not (target / METADATA_PATH).is_file():
            raise ManagerError(
                "typed reference anchor path must target a sectioned package root"
            )
        target_metadata = load_object(target / METADATA_PATH, "referenced metadata")
        if (
            target_metadata.get("artifactType") != reference["artifactType"]
            or target_metadata.get("id") != reference["id"]
        ):
            raise ManagerError(
                "typed reference identity does not match referenced package metadata"
            )
        target_toc = load_object(target / TOC_PATH, "referenced table of contents")
        if target_toc.get("sha256") != toc_digest(target_toc.get("sections", [])):
            raise ManagerError(
                "typed reference target table of contents integrity check failed"
            )
        anchor = reference["anchor"]
        entry = next(
            (
                item
                for item in target_toc["sections"]
                if item.get("id") == anchor["sectionId"]
            ),
            None,
        )
        if entry is None:
            raise ManagerError("typed reference anchor section does not exist")
        expected = f"data/sections/{anchor['sectionId']}.json"
        if entry.get("path") != expected:
            raise ManagerError("typed reference anchor section path is not canonical")
        target_section_path = target / expected
        assert_plain_path(target_section_path, "file")
        target_section = load_object(target_section_path, "referenced section")
        if (
            target_section.get("id") != anchor["sectionId"]
            or toc_entry(target_section) != entry
        ):
            raise ManagerError(
                "typed reference anchor section does not match table of contents"
            )
        if not any(
            item.get("id") == anchor["itemId"]
            for item in all_content_items([target_section])
        ):
            raise ManagerError("typed reference anchor item does not exist")


def validate_blocks(
    package: Path, block_refs: Iterable[str], *, full: bool
) -> tuple[dict[str, Any], list[str]]:
    index = load_object(package / BLOCK_INDEX_PATH, "block index")
    validate_instance("blocks", index)
    indexed = {entry["path"]: entry for entry in index["blocks"]}
    if len(indexed) != len(index["blocks"]):
        raise ManagerError("block index paths must be unique")
    for relative_value, entry in indexed.items():
        relative = safe_relative_path(relative_value, "block path")
        if relative.parts[0] != "blocks" or relative == BLOCK_INDEX_PATH:
            raise ManagerError(
                f"block path must remain under blocks/ and not replace index: {relative}"
            )
        target = package / relative
        assert_plain_path(target, "file")
        try:
            target.resolve().relative_to(package / "blocks")
        except ValueError as error:
            raise ManagerError(
                f"block path escapes blocks directory: {relative}"
            ) from error
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
        raise ManagerError(
            f"block file set does not match block index; extra={extra}, missing={missing}"
        )
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
        raise ManagerError(
            f"sections are not declared by the {ARTIFACT_LABEL} profile: {', '.join(unknown)}"
        )
    hierarchy_ids = [
        item_id for summary in summaries for item_id in summary["hierarchyIds"]
    ]
    if len(hierarchy_ids) != len(set(hierarchy_ids)):
        raise ManagerError(
            f"section and subsection ids must be unique across the {ARTIFACT_LABEL}"
        )

    status = metadata["lifecycle"]["status"]
    blockers = unresolved_blockers(summaries)
    if status == "blocked" and not blockers:
        raise ManagerError(
            f"blocked {ARTIFACT_LABEL} requires an unresolved blocking open item"
        )
    if status in {"closed", "superseded"}:
        dispositions = [
            entry for summary in summaries for entry in summary["dispositions"]
        ]
        matching = [
            entry
            for entry in dispositions
            if entry["targetStatus"] == status and entry["evidenceCount"] > 0
        ]
        if not matching:
            raise ManagerError(
                f"{status} {ARTIFACT_LABEL} requires an evidence-backed disposition item targeting {status}"
            )
    if status != "ready":
        return

    readiness = metadata["readiness"]
    failed = [
        key for key, value in readiness.items() if isinstance(value, bool) and not value
    ]
    if failed:
        raise ManagerError(
            f"ready {ARTIFACT_LABEL} has failed readiness flags: {', '.join(failed)}"
        )
    if readiness["reviewedAt"] is None:
        raise ManagerError(f"ready {ARTIFACT_LABEL} requires readiness.reviewedAt")
    if blockers:
        raise ManagerError(
            f"ready {ARTIFACT_LABEL} has unresolved blocking open items: {', '.join(blockers)}"
        )
    by_id = {summary["id"]: summary for summary in summaries}
    for section_rule in profile()["requiredSections"]:
        kinds = by_id[section_rule["id"]]["kinds"]
        families = profile().get("kindFamilies", {})
        missing = [
            kind
            for kind in section_rule["requiredKinds"]
            if kind not in kinds and not (set(families.get(kind, [])) & kinds)
        ]
        if missing:
            raise ManagerError(
                f"ready {ARTIFACT_LABEL} section {section_rule['id']} is missing required content kinds: {', '.join(missing)}"
            )
    for kind, contract in profile().get("kindAttributeContracts", {}).items():
        values = [
            attributes.get(contract["attribute"])
            for summary in summaries
            for attributes in summary["kindAttributes"].get(kind, [])
        ]
        invalid = [value for value in values if value not in contract["allowedValues"]]
        if not values or invalid:
            rendered = (
                ", ".join(repr(value) for value in invalid) if invalid else "missing"
            )
            raise ManagerError(
                f"ready {ARTIFACT_LABEL} {kind} status is invalid: {rendered}"
            )
    pending_interviews = [
        item_id for summary in summaries for item_id in summary["pendingInterviews"]
    ]
    if pending_interviews:
        raise ManagerError(
            f"ready {ARTIFACT_LABEL} contains pending interviews: {', '.join(pending_interviews)}"
        )


def validate_package(
    package_value: str | Path, *, full: bool = False
) -> dict[str, Any]:
    package = resolve_package(package_value)
    for directory in (package / "data", package / SECTIONS_PATH, package / "blocks"):
        assert_plain_path(directory, "directory")
    for path in (
        package / METADATA_PATH,
        package / TITLE_PATH,
        package / TOC_PATH,
        package / BLOCK_INDEX_PATH,
    ):
        assert_plain_path(path, "file")

    metadata = load_metadata(package)
    title = load_object(package / TITLE_PATH, "title")
    toc = load_toc(package)
    validate_instance("metadata", metadata)
    validate_instance("title", title)
    validate_instance("toc", toc)
    if metadata["id"] != package.name:
        raise ManagerError(
            f"{ARTIFACT_LABEL} id {metadata['id']!r} must match package directory {package.name!r}"
        )
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
    block_refs = [
        block_ref for summary in summaries for block_ref in summary["blockRefs"]
    ]
    _, block_files = validate_blocks(package, block_refs, full=full)

    files = [
        METADATA_PATH.as_posix(),
        TITLE_PATH.as_posix(),
        TOC_PATH.as_posix(),
        BLOCK_INDEX_PATH.as_posix(),
    ]
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
    for path in (
        package / METADATA_PATH,
        package / TITLE_PATH,
        package / TOC_PATH,
        package / BLOCK_INDEX_PATH,
    ):
        assert_plain_path(path, "file")
    metadata = load_metadata(package)
    title = load_object(package / TITLE_PATH, "title")
    toc = load_toc(package)
    validate_instance("metadata", metadata)
    validate_instance("title", title)
    validate_instance("toc", toc)
    if metadata["id"] != package.name:
        raise ManagerError(
            f"{ARTIFACT_LABEL} id {metadata['id']!r} must match package directory {package.name!r}"
        )
    if toc["sha256"] != toc_digest(toc["sections"]):
        raise ManagerError("manager-owned table of contents integrity check failed")
    toc_ids = [entry["id"] for entry in toc["sections"]]
    required = required_section_ids()
    positions = [
        toc_ids.index(required_id) for required_id in required if required_id in toc_ids
    ]
    if len(positions) != len(required) or positions != sorted(positions):
        raise ManagerError("required sections must exist exactly once in profile order")
    allowed = set(required) | optional_section_ids()
    if len(toc_ids) != len(set(toc_ids)) or any(
        item_id not in allowed for item_id in toc_ids
    ):
        raise ManagerError(
            f"table of contents does not match the {ARTIFACT_LABEL} profile"
        )
    indexed = {entry["path"] for entry in toc["sections"]}
    actual = {
        path.relative_to(package).as_posix()
        for path in (package / SECTIONS_PATH).iterdir()
        if path.is_file() or path.is_symlink()
    }
    if actual != indexed:
        raise ManagerError("section file set does not match table of contents")
    entry = next(
        (candidate for candidate in toc["sections"] if candidate["id"] == section_id),
        None,
    )
    if entry is None:
        raise ManagerError(f"section does not exist: {section_id}")
    path = section_path(package, section_id)
    if entry["path"] != path.relative_to(package).as_posix():
        raise ManagerError(f"section path does not match section id: {section_id}")
    assert_plain_path(path, "file")
    section = load_object(path, "section")
    validate_instance("section", section)
    if toc_entry(section) != entry:
        raise ManagerError(
            f"section hierarchy does not match table of contents: {section_id}"
        )
    summary = summarize_section(section)
    validate_typed_paths(package, metadata, [summary])
    validate_blocks(package, summary["blockRefs"], full=False)
    return section


def install_section_and_toc(
    package: Path, section: dict[str, Any], toc: dict[str, Any]
) -> None:
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
                "schemaVersion": contracts["metadata"]["properties"]["schemaVersion"][
                    "const"
                ],
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
    staging_package = staging_root / ".agent-factory" / PACKAGE_COLLECTION / args.id
    timestamp = now()
    current_profile = profile()
    sections = [
        {"id": entry["id"], "title": entry["title"], "content": [], "subsections": []}
        for entry in current_profile["requiredSections"]
    ]
    metadata: dict[str, Any] = {
        "schemaVersion": current_profile["version"],
        "documentVersion": "1.0.0",
        "id": args.id,
        "artifactType": ARTIFACT_TYPE,
        "projectId": args.project_id,
        "lifecycle": {"phase": LIFECYCLE_PHASE, "status": INITIAL_STATUS},
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "language": args.language,
        "theme": args.theme,
        "provenance": {
            "createdBy": "Human",
            "generatedBy": GENERATED_BY,
            "sourceRefs": [],
        },
        "relations": [],
    }
    if INITIAL_READINESS is not None:
        metadata["readiness"] = copy.deepcopy(INITIAL_READINESS)
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
        print(
            json.dumps(
                load_focused_section(package, args.section),
                ensure_ascii=False,
                indent=2,
            )
        )
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
        json_writes={
            package / TITLE_PATH: candidate,
            package / METADATA_PATH: updated_metadata(package),
        },
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
    apply_mutation_lifecycle(candidate)
    mark_contract_valid(candidate)
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
    entry_index = next(
        (
            index
            for index, entry in enumerate(toc["sections"])
            if entry["id"] == candidate["id"]
        ),
        None,
    )
    if entry_index is None:
        raise ManagerError(
            "section-put only replaces an existing section; use section-add"
        )
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
        subsection = next(
            (
                entry
                for entry in section["subsections"]
                if entry["id"] == args.subsection
            ),
            None,
        )
        if subsection is None:
            raise ManagerError(f"subsection does not exist: {args.subsection}")
        items = subsection["content"]
    existing = next(
        (
            index
            for index, entry in enumerate(items)
            if entry["id"] == candidate.get("id")
        ),
        None,
    )
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
    if not isinstance(candidates, list) or not all(
        isinstance(item, dict) for item in candidates
    ):
        raise ManagerError("content item batch must be a JSON array of objects")
    if args.subsection is None:
        items = section["content"]
    else:
        subsection = next(
            (
                entry
                for entry in section["subsections"]
                if entry["id"] == args.subsection
            ),
            None,
        )
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
        raise ManagerError(
            f"optional section is not declared by the {ARTIFACT_LABEL} profile: {candidate['id']}"
        )
    toc = load_toc(package)
    if any(entry["id"] == candidate["id"] for entry in toc["sections"]):
        raise ManagerError(f"section already exists: {candidate['id']}")
    index = len(toc["sections"])
    if args.before is not None:
        index = next(
            (
                i
                for i, entry in enumerate(toc["sections"])
                if entry["id"] == args.before
            ),
            -1,
        )
    elif args.after is not None:
        found = next(
            (i for i, entry in enumerate(toc["sections"]) if entry["id"] == args.after),
            -1,
        )
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
    source_index = next(
        (
            i
            for i, entry in enumerate(toc["sections"])
            if entry["id"] == args.section_id
        ),
        -1,
    )
    if source_index < 0:
        raise ManagerError(f"section does not exist: {args.section_id}")
    entry = toc["sections"].pop(source_index)
    target_id = args.before if args.before is not None else args.after
    target_index = next(
        (
            i
            for i, candidate in enumerate(toc["sections"])
            if candidate["id"] == target_id
        ),
        -1,
    )
    if target_index < 0:
        raise ManagerError("section positioning reference does not exist")
    if args.after is not None:
        target_index += 1
    toc["sections"].insert(target_index, entry)
    required_positions = [
        next(i for i, item in enumerate(toc["sections"]) if item["id"] == section_id)
        for section_id in required_section_ids()
    ]
    if required_positions != sorted(required_positions):
        raise ManagerError("section move must preserve required section profile order")
    toc["sha256"] = toc_digest(toc["sections"])
    validate_instance("toc", toc)
    commit_transaction(
        package,
        json_writes={
            package / TOC_PATH: toc,
            package / METADATA_PATH: updated_metadata(package),
        },
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
        json_writes={
            package / TOC_PATH: toc,
            package / METADATA_PATH: updated_metadata(package),
        },
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
        raise ManagerError(
            f"invalid {ARTIFACT_LABEL} transition: {current} -> {args.status}"
        )
    metadata["lifecycle"]["status"] = args.status
    if (
        MUTATION_POLICY is not None
        and current == MUTATION_POLICY["readyStatus"]
        and args.status == MUTATION_POLICY["draftStatus"]
    ):
        invalidate_semantic_readiness(metadata)
    metadata["documentVersion"] = next_document_version(metadata["documentVersion"])
    metadata["updatedAt"] = now()
    mark_contract_valid(metadata)
    summaries = summarize_sections(package, load_toc(package))
    validate_profile(metadata, summaries)
    validate_instance("metadata", metadata)
    commit_transaction(
        package,
        json_writes={package / METADATA_PATH: metadata},
        full_validation=args.status == "ready",
    )
    print(
        json.dumps(
            validate_package(package, full=args.status == "ready"), ensure_ascii=False
        )
    )


def checked_block_target(package: Path, value: str) -> tuple[Path, str]:
    relative = safe_relative_path(value, "block path")
    if relative.parts[0] != "blocks" or relative == BLOCK_INDEX_PATH:
        raise ManagerError(
            f"block path must remain under blocks/ and not replace index: {relative}"
        )
    target = package / relative
    block_root = (package / "blocks").resolve()
    try:
        target.resolve(strict=False).relative_to(block_root)
    except ValueError as error:
        raise ManagerError(
            f"block path escapes blocks directory: {relative}"
        ) from error
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
    print(
        json.dumps(validate_package(args.package, full=args.full), ensure_ascii=False)
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description=f"Manage sectioned Agent Factory {ARTIFACT_LABEL} packages"
    )
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check-schemas", help=f"validate {ARTIFACT_LABEL} schemas and profile"
    )
    check.set_defaults(handler=command_check_schemas)

    create = commands.add_parser(
        "create", help=f"create a split draft {ARTIFACT_LABEL} package"
    )
    create.add_argument("package")
    create.add_argument("--id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--project-id", required=True)
    create.add_argument("--language", default="ko")
    create.add_argument("--theme", required=True)
    create.set_defaults(handler=command_create)

    show = commands.add_parser(
        "show", help="validate and display a package or one section"
    )
    show.add_argument("package")
    show.add_argument("--section")
    show.set_defaults(handler=command_show)

    title_set = commands.add_parser("title-set", help="replace the canonical title")
    title_set.add_argument("package")
    title_set.add_argument("title")
    title_set.set_defaults(handler=command_title_set)

    metadata_set = commands.add_parser(
        "metadata-set", help="replace one mutable metadata field"
    )
    metadata_set.add_argument("package")
    metadata_set.add_argument("field")
    metadata_set.add_argument("value", nargs="?")
    metadata_set.add_argument("--value-file")
    metadata_set.set_defaults(handler=command_metadata_set)

    section_put = commands.add_parser(
        "section-put", help="replace an existing canonical section"
    )
    section_put.add_argument("package")
    section_put.add_argument("value", nargs="?")
    section_put.add_argument("--value-file")
    section_put.set_defaults(handler=command_section_put)

    item_put = commands.add_parser(
        "section-item-put", help="add or replace one section content item"
    )
    item_put.add_argument("package")
    item_put.add_argument("section_id")
    item_put.add_argument("value", nargs="?")
    item_put.add_argument("--value-file")
    item_put.add_argument("--subsection")
    item_put.set_defaults(handler=command_section_item_put)

    items_put = commands.add_parser(
        "section-items-put",
        help="add or replace multiple content items in one revision",
    )
    items_put.add_argument("package")
    items_put.add_argument("section_id")
    items_put.add_argument("value", nargs="?")
    items_put.add_argument("--value-file")
    items_put.add_argument("--subsection")
    items_put.set_defaults(handler=command_section_items_put)

    section_add = commands.add_parser(
        "section-add", help="add a profile-declared optional section"
    )
    section_add.add_argument("package")
    section_add.add_argument("value", nargs="?")
    section_add.add_argument("--value-file")
    position = section_add.add_mutually_exclusive_group()
    position.add_argument("--before")
    position.add_argument("--after")
    section_add.set_defaults(handler=command_section_add)

    section_move = commands.add_parser(
        "section-move", help="move a section while preserving required order"
    )
    section_move.add_argument("package")
    section_move.add_argument("section_id")
    move_position = section_move.add_mutually_exclusive_group(required=True)
    move_position.add_argument("--before")
    move_position.add_argument("--after")
    section_move.set_defaults(handler=command_section_move)

    section_remove = commands.add_parser(
        "section-remove", help="remove an optional section"
    )
    section_remove.add_argument("package")
    section_remove.add_argument("section_id")
    section_remove.set_defaults(handler=command_section_remove)

    validate = commands.add_parser(
        "validate", help=f"validate a complete {ARTIFACT_LABEL} package"
    )
    validate.add_argument("package")
    validate.add_argument(
        "--full", action="store_true", help="rehash every registered block"
    )
    validate.set_defaults(handler=command_validate)

    transition = commands.add_parser(
        "transition", help=f"apply a schema-owned {ARTIFACT_LABEL} transition"
    )
    transition.add_argument("package")
    transition.add_argument(
        "status",
        choices=list(validate_schemas()["metadata"]["x-statusTransitions"]),
    )
    transition.set_defaults(handler=command_transition)

    block_put = commands.add_parser(
        "block-put", help="stream an external block into the canonical package"
    )
    block_put.add_argument("package")
    block_put.add_argument("source")
    block_put.add_argument("--path", required=True)
    block_put.add_argument("--media-type", required=True)
    block_put.add_argument("--description", required=True)
    block_put.set_defaults(handler=command_block_put)

    block_remove = commands.add_parser(
        "block-remove", help="remove an unreferenced canonical block"
    )
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
