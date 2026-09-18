#!/usr/bin/env python3
"""Build a live catalog for Original and Processed project Documents."""

import argparse
import json
from pathlib import Path
import sys

import yaml

from export_documents import check_path, inventory


CATALOG_TYPES = ("original", "processed")
REQUIRED_METADATA = ("document-type", "category", "domain", "name")


def read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML metadata: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Metadata must be a mapping: {path}")
    return value


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"Document needs YAML front matter: {path}")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError(f"Unclosed YAML front matter: {path}") from None
    try:
        value = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML front matter: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Front matter must be a mapping: {path}")
    return value


def validate_metadata(metadata: dict, kind: str, path: Path) -> None:
    missing = [field for field in REQUIRED_METADATA if field not in metadata]
    if missing:
        raise ValueError(f"Metadata missing {', '.join(missing)}: {path}")
    if metadata["document-type"] != kind:
        raise ValueError(f"Expected document-type {kind}: {path}")
    for field in ("category", "name"):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise ValueError(f"Metadata {field} must be a nonempty string: {path}")
    if metadata["domain"] is not None and (
        not isinstance(metadata["domain"], str) or not metadata["domain"].strip()
    ):
        raise ValueError(f"Metadata domain must be null or a nonempty string: {path}")
    try:
        json.dumps(metadata, ensure_ascii=False)
    except TypeError as error:
        raise ValueError(f"Metadata must contain JSON-compatible values: {path}") from error


def catalog_entry(root: Path, package: Path, kind: str) -> dict:
    files = inventory(package, root)
    if kind == "original":
        if files != {"metadata.yaml": "file"}:
            raise ValueError(
                f"Original package must contain only metadata.yaml: {package}"
            )
        metadata_path = package / "metadata.yaml"
        metadata = read_yaml(metadata_path)
        links = metadata.get("links")
        if not isinstance(links, list) or not links or any(
            not isinstance(link, str) or not link.strip() for link in links
        ):
            raise ValueError(f"Original metadata links must be nonempty strings: {metadata_path}")
        content_path = None
    else:
        if files.get("SKILL.md") != "file":
            raise ValueError(f"Processed package needs SKILL.md: {package}")
        metadata_path = package / "SKILL.md"
        metadata = read_frontmatter(metadata_path)
        links = metadata.get("links", [])
        if not isinstance(links, list) or any(
            not isinstance(link, str) or not link.strip() for link in links
        ):
            raise ValueError(f"Processed metadata links must be strings: {metadata_path}")
        content_path = str(metadata_path.relative_to(root))
    validate_metadata(metadata, kind, metadata_path)
    return {
        "documentType": kind,
        "category": metadata["category"],
        "domain": metadata["domain"],
        "name": metadata["name"],
        "language": metadata.get("language"),
        "packagePath": str(package.relative_to(root)),
        "metadataPath": str(metadata_path.relative_to(root)),
        "contentPath": content_path,
        "links": links,
        "metadata": metadata,
    }


def build_catalog(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Expected project directory: {root}")
    documents = []
    identities = set()
    for kind in CATALOG_TYPES:
        source = root / "docs" / kind
        check_path(source, root)
        if not source.exists():
            continue
        if not source.is_dir():
            raise ValueError(f"Expected directory: {source}")
        for package in sorted(source.iterdir()):
            check_path(package, root)
            if not package.is_dir():
                raise ValueError(f"Expected package directory: {package}")
            entry = catalog_entry(root, package, kind)
            identity = tuple(entry[field] for field in ("documentType", "category", "domain", "name"))
            if identity in identities:
                raise ValueError(f"Duplicate Document identity: {identity}")
            identities.add(identity)
            documents.append(entry)
    return {
        "schemaVersion": "0.1.0",
        "kind": "document-catalog",
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        catalog = build_catalog(args.project_root)
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
