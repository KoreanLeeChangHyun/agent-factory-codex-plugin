#!/usr/bin/env python3
"""Manage append-only, topic-scoped Agent Factory Intake ledgers."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = SKILL_ROOT / "assets" / "schema"
COMMON_BLOCK_SCHEMA = (
    SKILL_ROOT.parent
    / "lifecycle"
    / "assets"
    / "schema"
    / "sectioned-document"
    / "blocks.schema.json"
)
COMMON_MANAGER = SKILL_ROOT.parent / "lifecycle" / "scripts" / "sectioned_document.py"
METADATA = Path("data/metadata.json")
ENTRIES = Path("data/entries")
BLOCK_INDEX = Path("blocks/index.json")
ID_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*$")


class ManagerError(Exception):
    pass


def load_security_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_intake_security", COMMON_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load secure package helpers: {COMMON_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


security = load_security_helpers()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ManagerError(f"{label} must be a regular file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerError(f"cannot read {label}: {path}") from error


def schemas() -> dict[str, dict[str, Any]]:
    values = {
        "metadata": load_json(SCHEMA_ROOT / "metadata.schema.json", "metadata schema"),
        "entry": load_json(SCHEMA_ROOT / "entry.schema.json", "entry schema"),
        "blocks": load_json(COMMON_BLOCK_SCHEMA, "block schema"),
    }
    for name, value in values.items():
        try:
            Draft202012Validator.check_schema(value)
        except Exception as error:
            raise ManagerError(f"invalid {name} schema: {error}") from error
    return values


def validate_instance(kind: str, value: Any) -> None:
    validator = Draft202012Validator(
        schemas()[kind], format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"/{'/'.join(str(part) for part in error.path)}: {error.message}"
            for error in errors
        )
        raise ManagerError(f"{kind} schema validation failed: {details}")


def resolve_package(value: str, *, must_exist: bool) -> Path:
    package = Path(value).expanduser().absolute()
    if package.name in {"", ".", ".."}:
        raise ManagerError("invalid Intake package path")
    if package.parent.name != "intakes" or package.parent.parent.name != ".agent-factory":
        raise ManagerError("Intake package must be under .agent-factory/intakes/")
    if must_exist:
        if package.is_symlink() or not package.is_dir():
            raise ManagerError(f"Intake package must be a regular directory: {package}")
    return package


def project_root(package: Path) -> Path:
    return package.parent.parent.parent


def safe_relative(value: str, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ManagerError(f"{label} must be a safe project-relative path")
    return relative


def entry_path(package: Path, entry_id: str) -> Path:
    if not ID_PATTERN.fullmatch(entry_id):
        raise ManagerError(f"invalid Intake entry id: {entry_id}")
    return package / ENTRIES / f"{entry_id}.json"


def next_version(value: str) -> str:
    major, minor, patch = (int(part) for part in value.split("."))
    return f"{major}.{minor}.{patch + 1}"


def updated_metadata(package: Path, *, package_fd: int | None = None) -> dict[str, Any]:
    source = Path(f"/proc/self/fd/{package_fd}") if package_fd is not None else package
    metadata = load_json(source / METADATA, "Intake metadata")
    metadata["documentVersion"] = next_version(metadata["documentVersion"])
    metadata["updatedAt"] = now()
    return metadata


def descriptor_identity(descriptor: int) -> tuple[int, int]:
    details = os.fstat(descriptor)
    return details.st_dev, details.st_ino


def descriptor_view(descriptor: int) -> Path:
    return Path(f"/proc/self/fd/{descriptor}")


@contextlib.contextmanager
def semantic_package_descriptor(package: Path) -> Iterable[int]:
    try:
        with security.package_descriptor(package) as descriptor:
            yield descriptor
    except security.ManagerError as error:
        raise ManagerError(str(error)) from error


def rename_noreplace(
    old_dir_fd: int, old_name: str, new_dir_fd: int, new_name: str
) -> None:
    """Atomically publish a staged package without replacing an existing one."""
    try:
        renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise ManagerError("atomic no-replace rename is unavailable") from error
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        old_dir_fd,
        os.fsencode(old_name),
        new_dir_fd,
        os.fsencode(new_name),
        1,  # RENAME_NOREPLACE
    ) == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ManagerError(f"package already exists: {new_name}")
    raise ManagerError(
        f"cannot atomically publish Intake package: {os.strerror(error_number)}"
    )


def assign(root: Any, pointer: str, value: Any) -> None:
    if not pointer.startswith("/") or pointer == "/":
        raise ManagerError(f"data path must be a non-root JSON Pointer: {pointer}")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    current = root
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        next_list = not last and parts[index + 1].isdigit()
        if isinstance(current, list):
            if not part.isdigit():
                raise ManagerError(f"list data path segment must be an index: {pointer}")
            position = int(part)
            while len(current) <= position:
                current.append(None)
            if last:
                if current[position] is not None:
                    raise ManagerError(f"data path assigned twice: {pointer}")
                current[position] = value
                return
            if current[position] is None:
                current[position] = [] if next_list else {}
            current = current[position]
        else:
            if not isinstance(current, dict):
                raise ManagerError(f"data path crosses scalar: {pointer}")
            if last:
                if part in current:
                    raise ManagerError(f"data path assigned twice: {pointer}")
                current[part] = value
                return
            if part not in current:
                current[part] = [] if next_list else {}
            current = current[part]


def add_data_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--string", action="append", nargs=2, default=[])
    command.add_argument("--integer", action="append", nargs=2, default=[])
    command.add_argument("--number", action="append", nargs=2, default=[])
    command.add_argument("--boolean", action="append", nargs=2, default=[])
    command.add_argument("--null", action="append", default=[])
    command.add_argument("--empty-object", action="append", default=[])
    command.add_argument("--empty-list", action="append", default=[])


def structured(args: argparse.Namespace) -> Any:
    root: Any = {}
    operations: list[tuple[str, Any]] = []
    operations.extend((path, value) for path, value in args.string)
    for path, value in args.integer:
        try:
            operations.append((path, int(value)))
        except ValueError as error:
            raise ManagerError(f"integer value is invalid: {value}") from error
    for path, value in args.number:
        try:
            parsed = float(value)
        except ValueError as error:
            raise ManagerError(f"number value is invalid: {value}") from error
        if parsed in {float("inf"), float("-inf")} or parsed != parsed:
            raise ManagerError("number value must be finite")
        operations.append((path, parsed))
    for path, value in args.boolean:
        if value not in {"true", "false"}:
            raise ManagerError("boolean value must be true or false")
        operations.append((path, value == "true"))
    operations.extend((path, None) for path in args.null)
    operations.extend((path, {}) for path in args.empty_object)
    operations.extend((path, []) for path in args.empty_list)
    if not operations:
        raise ManagerError("typed data arguments are required")
    first = operations[0][0].split("/", 2)[1]
    if first.isdigit():
        root = []
    for path, value in operations:
        assign(root, path, value)
    return root


def entries(package: Path) -> list[dict[str, Any]]:
    directory = package / ENTRIES
    if directory.is_symlink() or not directory.is_dir():
        raise ManagerError("Intake entries directory is missing or unsafe")
    values = [load_json(path, "Intake entry") for path in directory.iterdir()]
    if not all(isinstance(value, dict) for value in values):
        raise ManagerError("Intake entry must be a JSON object")
    return sorted(values, key=lambda item: item.get("sequence", 0))


def validate_refs(
    package: Path, values: Iterable[dict[str, Any]], *, root: Path | None = None
) -> None:
    root = (root or project_root(package)).resolve()
    metadata = load_json(package / METADATA, "Intake metadata")
    refs = list(metadata["provenance"]["sourceRefs"])
    refs.extend(relation["target"] for relation in metadata["relations"])
    for entry in values:
        refs.extend(entry.get("sourceRefs", []))
    for reference in refs:
        relative = safe_relative(reference["path"], "source reference")
        target = root / relative
        try:
            target.resolve(strict=False).relative_to(root)
        except ValueError as error:
            raise ManagerError("source reference escapes project root") from error
        if not target.exists():
            raise ManagerError(f"source reference does not exist: {relative}")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_blocks(package: Path, values: Iterable[dict[str, Any]], *, full: bool) -> None:
    index = load_json(package / BLOCK_INDEX, "block index")
    validate_instance("blocks", index)
    indexed = {item["path"]: item for item in index["blocks"]}
    referenced = {path for value in values for path in value.get("blockRefs", [])}
    actual = {
        path.relative_to(package).as_posix()
        for path in (package / "blocks").rglob("*")
        if path.is_file() and path != package / BLOCK_INDEX
    }
    if set(indexed) != actual:
        raise ManagerError("registered block set does not match block files")
    if referenced - set(indexed):
        raise ManagerError("Intake entry references an unregistered block")
    for relative, item in indexed.items():
        path = package / safe_relative(relative, "block path")
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item["sizeBytes"]:
            raise ManagerError(f"registered block changed: {relative}")
        if full and file_hash(path) != item["sha256"]:
            raise ManagerError(f"registered block hash changed: {relative}")


def validate_package(
    package: Path, *, full: bool = False, package_fd: int | None = None
) -> dict[str, Any]:
    canonical = resolve_package(str(package), must_exist=True)
    view = (
        Path(f"/proc/self/fd/{package_fd}")
        if package_fd is not None
        else canonical
    )
    metadata = load_json(view / METADATA, "Intake metadata")
    validate_instance("metadata", metadata)
    if metadata["id"] != canonical.name:
        raise ManagerError("Intake id must match package directory")
    values = entries(view)
    actual_entry_files = {
        path.name for path in (view / ENTRIES).iterdir() if path.is_file()
    }
    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    for value in values:
        validate_instance("entry", value)
        if value["id"] in seen_ids or value["sequence"] in seen_sequences:
            raise ManagerError("Intake entry ids and sequences must be unique")
        seen_ids.add(value["id"])
        seen_sequences.add(value["sequence"])
    expected_entry_files = {f"{value['id']}.json" for value in values}
    if actual_entry_files != expected_entry_files:
        raise ManagerError("Intake entry file set does not match entry ids")
    expected = list(range(1, len(values) + 1))
    if [value["sequence"] for value in values] != expected:
        raise ManagerError("Intake entry sequence must be contiguous")
    for value in values:
        for relation in value.get("relations", []):
            if relation["entryId"] not in seen_ids:
                raise ManagerError(f"Intake entry relation does not resolve: {relation['entryId']}")
    validate_refs(view, values, root=project_root(canonical))
    validate_blocks(view, values, full=full)
    return {
        "valid": True,
        "id": metadata["id"],
        "topic": metadata["topic"],
        "entryCount": len(values),
        "schemaVersion": metadata["schemaVersion"],
        "validation": "full" if full else "fast",
    }


def anchored_read_bytes(package_fd: int, relative: Path) -> bytes:
    with security.relative_parent_descriptor(package_fd, relative) as (parent_fd, name):
        descriptor = os.open(name, security.FILE_OPEN_FLAGS, dir_fd=parent_fd)
        try:
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)


def commit(
    package: Path,
    writes: dict[Path, Any],
    deletes: Iterable[Path] = (),
    byte_writes: dict[Path, bytes] | None = None,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    byte_writes = byte_writes or {}
    targets = list(writes) + list(byte_writes) + list(deletes)
    relatives = {
        path: security.checked_package_target(package, path, "Intake mutation target")
        for path in targets
    }
    before: dict[Path, bytes | None] = {}
    try:
        with security.package_descriptor(package) as package_fd:
            opened = os.fstat(package_fd)
            if expected_identity is not None and (
                opened.st_dev, opened.st_ino
            ) != expected_identity:
                raise ManagerError("Intake package changed after semantic read")
            current = os.stat(package, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise ManagerError("Intake package changed before mutation")
            for path, relative in relatives.items():
                before[path] = (
                    anchored_read_bytes(package_fd, relative)
                    if security.relative_file_exists(package_fd, relative)
                    else None
                )
            try:
                for path, value in writes.items():
                    security.write_json_relative(package_fd, relatives[path], value)
                for path, value in byte_writes.items():
                    security.write_bytes_relative(package_fd, relatives[path], value)
                for path in deletes:
                    security.unlink_relative(package_fd, relatives[path])
                validate_package(package, package_fd=package_fd)
                current = os.stat(package, follow_symlinks=False)
                if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                    raise ManagerError("Intake package changed during mutation")
            except Exception:
                for path, value in before.items():
                    relative = relatives[path]
                    if value is None:
                        security.unlink_relative(package_fd, relative)
                    else:
                        security.write_bytes_relative(package_fd, relative, value)
                raise
    except security.ManagerError as error:
        raise ManagerError(str(error)) from error


def command_check_schemas(_: argparse.Namespace) -> None:
    values = schemas()
    print(json.dumps({"valid": True, "schemaVersion": "3.0.0", "schemas": sorted(path.name for path in [SCHEMA_ROOT / 'metadata.schema.json', SCHEMA_ROOT / 'entry.schema.json', COMMON_BLOCK_SCHEMA])}))


def command_create(args: argparse.Namespace) -> None:
    package = resolve_package(args.package, must_exist=False)
    if args.id != package.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.id):
        raise ManagerError("--id must be a kebab-case package directory name")
    if package.exists():
        raise ManagerError(f"package already exists: {package}")
    timestamp = now()
    metadata = {
        "schemaVersion": "3.0.0",
        "documentVersion": "1.0.0",
        "id": args.id,
        "artifactType": "intake",
        "projectId": args.project_id,
        "topic": args.topic,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "language": args.language,
        "provenance": {"createdBy": "Human", "generatedBy": "Agent Factory intake manager", "sourceRefs": []},
        "relations": [],
    }
    validate_instance("metadata", metadata)
    validate_instance("blocks", {"blocks": []})
    root = project_root(package)
    root_fd = os.open(root, security.DIRECTORY_OPEN_FLAGS)
    factory_fd = -1
    intakes_fd = -1
    staging_fd = -1
    staging_name = f".create-{args.id}-{uuid.uuid4().hex}"
    try:
        try:
            os.mkdir(".agent-factory", mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            pass
        factory_fd = os.open(".agent-factory", security.DIRECTORY_OPEN_FLAGS, dir_fd=root_fd)
        try:
            os.mkdir("intakes", mode=0o700, dir_fd=factory_fd)
        except FileExistsError:
            pass
        intakes_fd = os.open("intakes", security.DIRECTORY_OPEN_FLAGS, dir_fd=factory_fd)
        try:
            os.stat(args.id, dir_fd=intakes_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ManagerError(f"package already exists: {package}")
        os.mkdir(staging_name, mode=0o700, dir_fd=intakes_fd)
        staging_fd = os.open(staging_name, security.DIRECTORY_OPEN_FLAGS, dir_fd=intakes_fd)
        security.write_json_relative(staging_fd, METADATA, metadata)
        security.write_json_relative(staging_fd, BLOCK_INDEX, {"blocks": []})
        data_fd = os.open("data", security.DIRECTORY_OPEN_FLAGS, dir_fd=staging_fd)
        try:
            os.mkdir("entries", mode=0o700, dir_fd=data_fd)
        finally:
            os.close(data_fd)
        rename_noreplace(intakes_fd, staging_name, intakes_fd, args.id)
    except OSError as error:
        raise ManagerError(f"cannot securely create Intake collection: {error}") from error
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if intakes_fd >= 0:
            with contextlib.suppress(OSError):
                os.rmdir(staging_name, dir_fd=intakes_fd)
            os.close(intakes_fd)
        if factory_fd >= 0:
            os.close(factory_fd)
        os.close(root_fd)
    print(json.dumps({"valid": True, "id": args.id, "topic": args.topic, "entryCount": 0, "schemaVersion": "3.0.0", "validation": "fast"}, ensure_ascii=False))


def command_show(args: argparse.Namespace) -> None:
    validate_package(args.package)
    if args.entry:
        print(json.dumps(load_json(entry_path(args.package, args.entry), "Intake entry"), ensure_ascii=False, indent=2))
        return
    print(json.dumps({"metadata": load_json(args.package / METADATA, "Intake metadata"), "entries": entries(args.package), "blocks": load_json(args.package / BLOCK_INDEX, "block index")}, ensure_ascii=False, indent=2))


def prepare_entry(package: Path, value: Any, sequence: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManagerError("Intake entry must be an object")
    if "sequence" in value or "recordedAt" in value:
        raise ManagerError("sequence and recordedAt are manager-owned")
    result = dict(value)
    result["sequence"] = sequence
    result["recordedAt"] = now()
    validate_instance("entry", result)
    return result


def command_entry_put(args: argparse.Namespace) -> None:
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        current = entries(descriptor_view(package_fd))
        value = prepare_entry(args.package, structured(args), len(current) + 1)
        target = entry_path(args.package, value["id"])
        relative = ENTRIES / f"{value['id']}.json"
        if security.relative_file_exists(package_fd, relative):
            raise ManagerError(
                "Intake entries are append-only; add a correction entry instead"
            )
        metadata = updated_metadata(args.package, package_fd=package_fd)
    commit(
        args.package,
        {target: value, args.package / METADATA: metadata},
        expected_identity=identity,
    )
    print(json.dumps(value, ensure_ascii=False))


def command_entry_items_put(args: argparse.Namespace) -> None:
    raw = structured(args)
    if not isinstance(raw, list) or not raw:
        raise ManagerError("entry-items-put requires a non-empty array")
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        current = entries(descriptor_view(package_fd))
        values = [
            prepare_entry(args.package, value, len(current) + index + 1)
            for index, value in enumerate(raw)
        ]
        paths = [entry_path(args.package, value["id"]) for value in values]
        relatives = [ENTRIES / f"{value['id']}.json" for value in values]
        if len(set(paths)) != len(paths) or any(
            security.relative_file_exists(package_fd, relative)
            for relative in relatives
        ):
            raise ManagerError("Intake entry ids must be new and unique")
        metadata = updated_metadata(args.package, package_fd=package_fd)
    writes = {path: value for path, value in zip(paths, values)}
    writes[args.package / METADATA] = metadata
    commit(args.package, writes, expected_identity=identity)
    print(json.dumps({"appended": [value["id"] for value in values]}, ensure_ascii=False))


def command_topic_set(args: argparse.Namespace) -> None:
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        metadata = updated_metadata(args.package, package_fd=package_fd)
        metadata["topic"] = args.topic
        validate_instance("metadata", metadata)
    commit(
        args.package,
        {args.package / METADATA: metadata},
        expected_identity=identity,
    )
    print(json.dumps({"id": metadata["id"], "topic": metadata["topic"]}, ensure_ascii=False))


def session_id(metadata: dict[str, Any]) -> str | None:
    return metadata.get("operational", {}).get("agentSessionBinding", {}).get("sessionId")


def command_session_show(args: argparse.Namespace) -> None:
    validate_package(args.package)
    metadata = load_json(args.package / METADATA, "Intake metadata")
    print(json.dumps({"intakeId": metadata["id"], "sessionId": session_id(metadata)}))


def command_session_bind(args: argparse.Namespace) -> None:
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        validate_package(args.package, package_fd=package_fd)
        metadata = security.load_object_relative(
            package_fd, METADATA, "Intake metadata"
        )
        metadata["operational"] = {
            "agentSessionBinding": {"sessionId": args.session_id}
        }
        validate_instance("metadata", metadata)
    commit(
        args.package,
        {args.package / METADATA: metadata},
        expected_identity=identity,
    )
    print(json.dumps({"intakeId": metadata["id"], "sessionId": args.session_id}))


def command_session_clear(args: argparse.Namespace) -> None:
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        validate_package(args.package, package_fd=package_fd)
        metadata = security.load_object_relative(
            package_fd, METADATA, "Intake metadata"
        )
        metadata.pop("operational", None)
    commit(
        args.package,
        {args.package / METADATA: metadata},
        expected_identity=identity,
    )
    print(json.dumps({"intakeId": metadata["id"], "sessionId": None}))


def command_validate(args: argparse.Namespace) -> None:
    print(json.dumps(validate_package(args.package, full=args.full), ensure_ascii=False))


def command_block_put(args: argparse.Namespace) -> None:
    source = Path(args.source).absolute()
    try:
        source_fd = os.open(source, security.FILE_OPEN_FLAGS)
    except OSError as error:
        raise ManagerError("block source must be a regular non-symlink file") from error
    try:
        details = os.fstat(source_fd)
        if not stat.S_ISREG(details.st_mode):
            raise ManagerError("block source must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(source_fd, 1024 * 1024):
            chunks.append(chunk)
        content = b"".join(chunks)
    finally:
        os.close(source_fd)
    relative = safe_relative(args.path, "block path")
    if not relative.parts or relative.parts[0] != "blocks" or relative == BLOCK_INDEX:
        raise ManagerError("block path must be below blocks/")
    target = args.package / relative
    item = {"path": relative.as_posix(), "mediaType": args.media_type, "description": args.description, "sha256": hashlib.sha256(content).hexdigest(), "sizeBytes": len(content)}
    with semantic_package_descriptor(args.package) as package_fd:
        identity = descriptor_identity(package_fd)
        if security.relative_file_exists(package_fd, relative):
            raise ManagerError("block path already exists")
        index = security.load_object_relative(
            package_fd, BLOCK_INDEX, "block index"
        )
        index["blocks"].append(item)
        metadata = updated_metadata(args.package, package_fd=package_fd)
    commit(
        args.package,
        {
            args.package / BLOCK_INDEX: index,
            args.package / METADATA: metadata,
        },
        byte_writes={target: content},
        expected_identity=identity,
    )
    print(json.dumps(item, ensure_ascii=False))


def command_delete(args: argparse.Namespace) -> None:
    package = args.package
    if args.confirm_id != package.name:
        raise ManagerError("confirmation id must equal canonical Intake id")
    valid = True
    collection_fd = -1
    package_fd = -1
    root_fd = -1
    factory_fd = -1
    tombstone = f".delete-{package.name}-{uuid.uuid4().hex}"
    try:
        root_fd = os.open(project_root(package), security.DIRECTORY_OPEN_FLAGS)
        factory_fd = os.open(".agent-factory", security.DIRECTORY_OPEN_FLAGS, dir_fd=root_fd)
        collection_fd = os.open("intakes", security.DIRECTORY_OPEN_FLAGS, dir_fd=factory_fd)
        package_fd = os.open(package.name, security.DIRECTORY_OPEN_FLAGS, dir_fd=collection_fd)
        opened = os.fstat(package_fd)
        anchored_metadata = security.load_object_relative(
            package_fd, METADATA, "Intake metadata"
        )
        if anchored_metadata.get("id") != package.name:
            raise ManagerError("Intake identity changed before deletion")
        try:
            validate_package(package, full=True, package_fd=package_fd)
        except ManagerError:
            valid = False
            if not args.allow_invalid:
                raise ManagerError("invalid Intake deletion requires --allow-invalid")
        current = os.stat(package.name, dir_fd=collection_fd, follow_symlinks=False)
        if not stat.S_ISDIR(current.st_mode) or (
            current.st_dev, current.st_ino
        ) != (opened.st_dev, opened.st_ino):
            raise ManagerError("Intake package changed before deletion")
        os.rename(
            package.name,
            tombstone,
            src_dir_fd=collection_fd,
            dst_dir_fd=collection_fd,
        )
        renamed = os.stat(tombstone, dir_fd=collection_fd, follow_symlinks=False)
        if (renamed.st_dev, renamed.st_ino) != (opened.st_dev, opened.st_ino):
            os.rename(tombstone, package.name, src_dir_fd=collection_fd, dst_dir_fd=collection_fd)
            raise ManagerError("Intake package changed during deletion")
        try:
            security.remove_directory_contents(package_fd)
            os.rmdir(tombstone, dir_fd=collection_fd)
        except Exception:
            with contextlib.suppress(OSError):
                os.rename(tombstone, package.name, src_dir_fd=collection_fd, dst_dir_fd=collection_fd)
            raise
    except security.ManagerError as error:
        raise ManagerError(str(error)) from error
    finally:
        for descriptor in (package_fd, collection_fd, factory_fd, root_fd):
            if descriptor >= 0:
                os.close(descriptor)
    print(json.dumps({"id": anchored_metadata["id"], "path": str(package), "validation": "valid" if valid else "invalid", "operationResult": "deleted"}))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-schemas")
    check.set_defaults(handler=command_check_schemas)
    create = commands.add_parser("create")
    create.add_argument("package")
    create.add_argument("--id", required=True)
    create.add_argument("--topic", required=True)
    create.add_argument("--project-id", required=True)
    create.add_argument("--language", required=True)
    create.set_defaults(handler=command_create)
    show = commands.add_parser("show")
    show.add_argument("package")
    show.add_argument("--entry")
    show.set_defaults(handler=command_show)
    entry_put = commands.add_parser("entry-put")
    entry_put.add_argument("package")
    add_data_arguments(entry_put)
    entry_put.set_defaults(handler=command_entry_put)
    entries_put = commands.add_parser("entry-items-put")
    entries_put.add_argument("package")
    add_data_arguments(entries_put)
    entries_put.set_defaults(handler=command_entry_items_put)
    topic = commands.add_parser("topic-set")
    topic.add_argument("package")
    topic.add_argument("topic")
    topic.set_defaults(handler=command_topic_set)
    validate = commands.add_parser("validate")
    validate.add_argument("package")
    validate.add_argument("--full", action="store_true")
    validate.set_defaults(handler=command_validate)
    for name, handler in (("session-show", command_session_show), ("session-clear", command_session_clear)):
        command = commands.add_parser(name)
        command.add_argument("package")
        command.set_defaults(handler=handler)
    bind = commands.add_parser("session-bind")
    bind.add_argument("package")
    bind.add_argument("session_id")
    bind.set_defaults(handler=command_session_bind)
    block = commands.add_parser("block-put")
    block.add_argument("package")
    block.add_argument("source")
    block.add_argument("--path", required=True)
    block.add_argument("--media-type", required=True)
    block.add_argument("--description", required=True)
    block.set_defaults(handler=command_block_put)
    delete = commands.add_parser("delete")
    delete.add_argument("package")
    delete.add_argument("--confirm-id", required=True)
    delete.add_argument("--allow-invalid", action="store_true")
    delete.set_defaults(handler=command_delete)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if hasattr(args, "package"):
            args.package = resolve_package(args.package, must_exist=args.command != "create")
        args.handler(args)
        return 0
    except ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
