"""Capability binding schema validation and race-safe caller file reads."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from runtime_errors import ContractError

SCHEMA_VERSION = "0.1.0"
MAX_CAPABILITY_BINDING_BYTES = 256 * 1024
CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
AUTHORITY_KINDS = {
    "native-executable", "project-cli", "mcp-server", "plugin",
    "host-capability", "external-provider",
}

def _bounded_text(value: object, label: str, *, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 4096:
        raise ContractError("capability_binding_invalid", f"{label} is invalid")
    if any(character in value for character in "\x00\r\n"):
        raise ContractError("capability_binding_invalid", f"{label} contains control characters")
    return value


def validate_capability_bindings(document: object) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "bindings"}:
        raise ContractError("capability_binding_invalid", "capability binding document has unknown or missing fields")
    if document.get("schemaVersion") != SCHEMA_VERSION or not isinstance(document.get("bindings"), list):
        raise ContractError("capability_binding_invalid", "capability binding document is invalid")
    bindings = document["bindings"]
    if not 1 <= len(bindings) <= 32:
        raise ContractError("capability_binding_invalid", "capability bindings must contain 1 through 32 entries")
    identities: set[str] = set()
    fields = {
        "capabilityId", "authority", "invocationRoute", "exactTarget",
        "allowedEffects", "allowedScopes", "approvalReference",
    }
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != fields:
            raise ContractError("capability_binding_invalid", "capability binding has unknown or missing fields")
        capability_id = binding.get("capabilityId")
        if not isinstance(capability_id, str) or CAPABILITY_ID.fullmatch(capability_id) is None:
            raise ContractError("capability_binding_invalid", "capabilityId is invalid")
        if capability_id in identities:
            raise ContractError("capability_binding_invalid", "capabilityId bindings must be unique")
        identities.add(capability_id)
        authority = binding.get("authority")
        if not isinstance(authority, dict) or set(authority) != {"kind", "reference"}:
            raise ContractError("capability_binding_invalid", "authority has unknown or missing fields")
        if authority.get("kind") not in AUTHORITY_KINDS:
            raise ContractError("capability_binding_invalid", "authority kind is invalid")
        _bounded_text(authority.get("reference"), "authority reference")
        _bounded_text(binding.get("invocationRoute"), "invocation route")
        _bounded_text(binding.get("exactTarget"), "exact target")
        _bounded_text(binding.get("approvalReference"), "approval reference", nullable=True)
        for field in ("allowedEffects", "allowedScopes"):
            values = binding.get(field)
            if not isinstance(values, list) or len(values) > 64:
                raise ContractError("capability_binding_invalid", f"{field} must be a bounded array")
            checked = [_bounded_text(value, field) for value in values]
            if len(set(checked)) != len(checked):
                raise ContractError("capability_binding_invalid", f"{field} must contain unique values")
    return document


def read_capability_bindings(path: Path | None) -> tuple[dict[str, Any] | None, bytes | None]:
    if path is None:
        return None, None
    raw = safe_read_caller_file(path, MAX_CAPABILITY_BINDING_BYTES)
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("capability_binding_invalid", "capability binding file is invalid JSON") from error
    validated = validate_capability_bindings(document)
    canonical = (json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return validated, canonical


def result_file_identity(info) -> dict[str, int]:
    return {key: getattr(info, key) for key in
            ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")}


def safe_hash_caller_file(path: Path, expected_identity=None) -> str:
    """Hash a stable regular file through safe traversal, using bounded memory."""
    return safe_read_caller_file(path, None, digest_only=True, expected_identity=expected_identity)


def safe_read_caller_file(path: Path, limit: int | None, *, private: bool = False,
                          digest_only: bool = False, expected_identity=None) -> bytes | str:
    """Read an explicit caller file without following any path component."""
    if ".." in path.parts:
        raise ContractError("capability_binding_invalid", "capability binding path contains traversal")
    if (
        not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NONBLOCK")
        or os.open not in os.supports_dir_fd
    ):
        raise ContractError(
            "capability_binding_unsupported",
            "safe capability binding file traversal is unavailable on this platform",
        )
    absolute = path if path.is_absolute() else Path.cwd() / path
    components = [part for part in absolute.parts if part not in {absolute.anchor, "."}]
    if not components:
        raise ContractError("capability_binding_invalid", "capability binding path is invalid")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = -1
    try:
        descriptor = os.open(absolute.anchor or os.sep, directory_flags)
        for component in components[:-1]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise ContractError("capability_binding_invalid", "capability binding parent is unsafe")
        file_descriptor = os.open(components[-1], file_flags, dir_fd=descriptor)
        os.close(descriptor)
        descriptor = file_descriptor
        info = os.fstat(descriptor)
        if private and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ContractError("reporting_file_unsafe", "Reporting file must be owned by this user and private")
        if not stat.S_ISREG(info.st_mode):
            raise ContractError("capability_binding_invalid", "capability binding is not a regular file")
        if digest_only:
            identity = result_file_identity(info)
            if expected_identity is not None and identity != expected_identity:
                raise ContractError("reporting_result_changed", "Reporting result identity changed")
            hasher = hashlib.sha256()
            remaining = info.st_size + 1
            count = 0
            while remaining > 0:
                chunk = os.read(descriptor, min(remaining, 65536))
                if not chunk:
                    break
                hasher.update(chunk)
                count += len(chunk)
                remaining -= len(chunk)
            if count != info.st_size or result_file_identity(os.fstat(descriptor)) != identity:
                raise ContractError("reporting_result_changed", "Reporting result changed during capture")
            return hasher.hexdigest()
        if info.st_size > limit:
            raise ContractError("file_too_large", f"file exceeds the size limit: {path}")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > limit:
            raise ContractError("file_too_large", f"file exceeds the size limit: {path}")
        return content
    except (FileNotFoundError, NotADirectoryError, OSError) as error:
        raise ContractError(
            "capability_binding_invalid",
            "capability binding path is missing or contains an unsafe component",
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)



