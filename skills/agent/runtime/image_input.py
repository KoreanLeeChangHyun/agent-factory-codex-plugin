"""Validated, file-backed image input contract for managed Agent turns."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capability_contracts import safe_read_caller_file
from runtime_errors import ContractError

SCHEMA_VERSION = "0.1.0"
MAX_CONTRACT_BYTES = 8 * 1024 * 1024 + 64 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGES = 8
IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def validate_execution(images: list[dict[str, Any]], effective: dict[str, Any]) -> None:
    if images and effective.get("goalMode") is True:
        raise ContractError(
            "image_goal_unsupported",
            "Native Goal activation cannot accept images; disable Goal mode for this turn",
        )


def _signature_matches(content: bytes, media_type: str) -> bool:
    if media_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if media_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if media_type == "image/gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if media_type == "image/webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    return False


def read_agent_input(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    """Read one exact contract and capture its sibling images without symlink races."""
    try:
        raw = safe_read_caller_file(path, MAX_CONTRACT_BYTES)
        document = json.loads(raw)
    except (ContractError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("input_contract_invalid", "agent input contract is invalid") from error
    if not isinstance(document, dict) or set(document) != {"schemaVersion", "kind", "message", "images"}:
        raise ContractError("input_contract_invalid", "agent input contract has unknown or missing fields")
    if document.get("schemaVersion") != SCHEMA_VERSION or document.get("kind") != "agent-input":
        raise ContractError("input_contract_invalid", "agent input contract version or kind is unsupported")
    message = document.get("message")
    images = document.get("images")
    if not isinstance(message, str) or not message.strip():
        raise ContractError("request_invalid", "request must not be empty")
    request = message.encode("utf-8")
    if len(request) > 8 * 1024 * 1024:
        raise ContractError("request_too_large", "request exceeds the size limit")
    if not isinstance(images, list) or len(images) > MAX_IMAGES:
        raise ContractError("input_contract_invalid", "agent input images exceed the count limit")
    captured: list[dict[str, Any]] = []
    total = 0
    for index, image in enumerate(images):
        if not isinstance(image, dict) or set(image) != {"path", "mediaType"}:
            raise ContractError("input_contract_invalid", "agent input image has unknown or missing fields")
        name = image.get("path")
        media_type = image.get("mediaType")
        if (not isinstance(name, str) or Path(name).name != name or name in {"", ".", ".."}
                or not isinstance(media_type, str) or media_type not in IMAGE_TYPES
                or Path(name).suffix.lower() not in ({".jpg", ".jpeg"} if media_type == "image/jpeg" else {IMAGE_TYPES[media_type]})):
            raise ContractError("input_contract_invalid", "agent input image path or media type is invalid")
        try:
            content = safe_read_caller_file(path.parent / name, MAX_IMAGE_BYTES, stable=True)
        except ContractError as error:
            raise ContractError("input_image_invalid", f"agent input image {index} is unsafe or invalid") from error
        total += len(content)
        if not _signature_matches(content, media_type):
            raise ContractError("input_image_invalid", f"agent input image {index} content does not match its media type")
        if total > MAX_TOTAL_IMAGE_BYTES:
            raise ContractError("input_images_too_large", "agent input images exceed the total size limit")
        captured.append({"content": content, "mediaType": media_type, "suffix": IMAGE_TYPES[media_type]})
    return request, captured
