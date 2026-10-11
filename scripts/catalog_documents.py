#!/usr/bin/env python3
"""Build a live catalog for Original, Refined, Progress and Lessons Learned project Documents."""

import argparse
import json
from pathlib import Path
import re
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from storage import lessons as body_store  # noqa: E402

REFINED_CATEGORIES = ("analysis", "research", "interview", "comparison", "history")

from export_documents import check_path, inventory  # noqa: E402


CATALOG_TYPES = ("original", "processed", "progress", "lessons-learned")
# Refined keeps the compatible `processed` document type.
TYPE_ALIASES = {"refined": "processed"}
SOURCES = (
    ("original", "docs/original", "canonical"),
    ("processed", "docs/refined", "canonical"),
    ("processed", "docs/processed", "legacy"),
    ("progress", "docs/progress", "canonical"),
    ("progress", "progress", "legacy"),
    ("lessons-learned", "docs/lessons-learned", "canonical"),
)
REQUIRED_METADATA = ("document-type", "category", "domain", "name")
CONTRACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
CONTRACT_FILE = re.compile(r"contract-v([1-9][0-9]{0,5})\.md")
DIRECT_EXECUTION = "direct-execution"
MARKDOWN_LINK = re.compile(r"\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
TEXT_SUFFIXES = {".md", ".csv", ".json", ".txt", ".yaml", ".yml"}


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


def document_metadata(frontmatter: dict, path: Path) -> dict:
    """Accept flat front matter or Skill-style nesting under `metadata`."""
    if "document-type" in frontmatter:
        return frontmatter
    nested = frontmatter.get("metadata")
    if isinstance(nested, dict) and "document-type" in nested:
        return nested
    raise ValueError(f"Metadata missing document-type: {path}")


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


def read_lesson(path: Path) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("schemaVersion") != 1:
        raise ValueError(f"Unsupported lesson schema: {path}")
    for field in ("id", "category", "title", "language", "scope", "status"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Missing lesson field {field}: {path}")
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,100}", record["id"]):
        raise ValueError(f"Invalid lesson id: {path}")
    if record["category"] not in ("error", "judgment"):
        raise ValueError(f"Invalid lesson category: {path}")
    for field in ("occurrences", "applications", "candidates", "publications"):
        if not isinstance(record.get(field), list) or any(not isinstance(v, dict) for v in record[field]):
            raise ValueError(f"Invalid lesson field {field}: {path}")
    if not (path.name == "lesson.json" and path.parent.name == "assets") and path.name != record["id"] + ".json":
        raise ValueError(f"Lesson filename/id mismatch: {path}")
    return record


def lesson_entry(root: Path, path: Path, identity_root=None) -> dict:
    record = (body_store.read(identity_root or root, path, root) if path.suffix == ".md"
              else read_lesson(path))
    relative = str(path.relative_to(root))
    metadata = {"document-type": "lessons-learned", "category": record["category"],
                "domain": None, "name": record["id"], "language": record["language"],
                "title": record["title"], "scope": record["scope"], "status": record["status"]}
    related = list(dict.fromkeys(name for event in record['occurrences'] for name in event.get('relatedIds', [])))
    metadata['relatedIds'] = related
    related_links = []
    for name in related:
        meta = body_store.metadata_path(identity_root or root, name)
        if meta is not None and meta.exists():
            info = body_store.paths.read(meta)
            related_links.append(info['documentPath'])
        elif (root / f'docs/lessons-learned/{name}.json').is_file():
            related_links.append(f'docs/lessons-learned/{name}.json')
    return {"documentType": "lessons-learned", "category": record["category"],
            "domain": None, "name": record["id"], "language": record["language"],
            "packagePath": relative, "metadataPath": (str(body_store.metadata_path(identity_root or root, record["id"]))
                if path.suffix == ".md" else relative), "contentPath": relative,
            "scope": record["scope"], "status": record["status"],
            "relatedIds": related, "links": list(dict.fromkeys(o.get("source", "") for o in record["occurrences"])) + related_links, "metadata": metadata}


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
            raise ValueError(f"{kind.capitalize()} package needs SKILL.md: {package}")
        metadata_path = package / "SKILL.md"
        metadata = document_metadata(read_frontmatter(metadata_path), metadata_path)
        links = metadata.get("links", [])
        if not isinstance(links, list) or any(
            not isinstance(link, str) or not link.strip() for link in links
        ):
            raise ValueError(f"{kind.capitalize()} metadata links must be strings: {metadata_path}")
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
        "contentPaths": ([content_path] + [
            str((package / name).relative_to(root))
            for name, shape in sorted(files.items())
            if shape == "file" and name.startswith("references/") and name.endswith(".md")
        ]) if content_path else [],
        "links": links,
        "metadata": metadata,
    }


def local_links(text: str) -> set[str]:
    """Return sibling file names linked from Markdown, ignoring anchors and other paths."""
    names = set()
    for target in MARKDOWN_LINK.findall(text):
        target = target.split("#", 1)[0]
        if target.startswith("./"):
            target = target[2:]
        if target and "/" not in target and ":" not in target:
            names.add(target)
    return names


def task_ids(text: str) -> list[str]:
    """Collect first-column values of Markdown tables whose first header names an ID."""
    ids = []
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        separator = lines[index + 1].strip()
        if not line.lstrip().startswith("|") or not re.fullmatch(r"\|?[\s:|-]+\|?", separator):
            continue
        if not re.search(r"\bID\b", cells[0], re.IGNORECASE):
            continue
        for row in lines[index + 2:]:
            if not row.lstrip().startswith("|"):
                break
            value = row.strip().strip("|").split("|")[0].strip().strip("`")
            if value and value not in ids:
                ids.append(value)
    return ids


def contract_entry(root: Path, folder: Path) -> dict:
    """Catalog a contract package below canonical or legacy Progress roots with its versions, task IDs and linked attachments."""
    contract_id = folder.name
    if not CONTRACT_ID.fullmatch(contract_id):
        raise ValueError(f"Invalid contract ID directory: {folder}")
    files = inventory(folder, root)
    nested = sorted(name for name, kind in files.items() if kind == "dir")
    if nested:
        raise ValueError(f"Contract directory must contain only files: {folder / nested[0]}")
    if files.get("progress.md") != "file":
        raise ValueError(f"Contract directory needs progress.md: {folder}")
    progress_path = folder / "progress.md"
    metadata = document_metadata(read_frontmatter(progress_path), progress_path)
    validate_metadata(metadata, "progress", progress_path)
    if metadata.get("contract-id", contract_id) != contract_id:
        raise ValueError(f"Progress contract-id does not match its directory: {progress_path}")
    links = metadata.get("links", [])
    if not isinstance(links, list) or any(not isinstance(link, str) or not link.strip() for link in links):
        raise ValueError(f"Progress metadata links must be strings: {progress_path}")

    linked = local_links(progress_path.read_text(encoding="utf-8"))
    versions = []
    for name in sorted(files):
        match = CONTRACT_FILE.fullmatch(name)
        if not match:
            continue
        path = folder / name
        text = path.read_text(encoding="utf-8")
        contract = document_metadata(read_frontmatter(path), path)
        validate_metadata(contract, "processed", path)
        if contract.get("contract-id") != contract_id:
            raise ValueError(f"Contract contract-id does not match its directory: {path}")
        if contract.get("contract-version") != int(match.group(1)):
            raise ValueError(f"Contract contract-version does not match its filename: {path}")
        linked |= local_links(text)
        versions.append({
            "version": int(match.group(1)),
            "path": str(path.relative_to(root)),
            "status": contract.get("status"),
            "taskIds": task_ids(text),
        })
    # A direct-execution record documents work run without a contract, so it has no versions.
    direct = metadata.get("record-type") == DIRECT_EXECUTION
    if direct and (versions or "contract-version" in metadata):
        raise ValueError(f"Direct-execution record cannot carry contract versions: {folder}")
    if not versions and not direct:
        raise ValueError(f"Contract directory needs contract-v<N>.md: {folder}")
    versions.sort(key=lambda item: item["version"])

    attachments = []
    for name in sorted(files):
        if name == "progress.md" or CONTRACT_FILE.fullmatch(name):
            continue
        if name not in linked:
            raise ValueError(f"Contract attachment is not linked from progress.md or a contract: {folder / name}")
        attachments.append(str((folder / name).relative_to(root)))
    missing = sorted(name for name in linked if name not in files)
    if missing:
        raise ValueError(f"Linked contract attachment does not exist: {folder / missing[0]}")

    content_path = str(progress_path.relative_to(root))
    return {
        "documentType": "progress",
        "category": metadata["category"],
        "domain": metadata["domain"],
        "name": metadata["name"],
        "language": metadata.get("language"),
        "packagePath": str(folder.relative_to(root)),
        "metadataPath": content_path,
        "contentPath": content_path,
        "contentPaths": [content_path, *(item["path"] for item in versions),
                         *(path for path in attachments if Path(path).suffix in TEXT_SUFFIXES)],
        "links": links,
        "metadata": metadata,
        "contract": {
            "id": contract_id,
            "latestVersion": versions[-1]["version"] if versions else None,
            "taskIds": versions[-1]["taskIds"] if versions else [],
            "versions": versions,
            "attachments": attachments,
        },
    }


def build_catalog(root: Path, documents_root=None) -> dict:
    identity_root = root.resolve(strict=True)
    root = body_store.document_root(identity_root, documents_root)
    if not root.is_dir():
        raise ValueError(f"Expected project directory: {root}")
    documents = []
    identities = {}
    contracts = {}
    for kind, relative, location in SOURCES:
        source = root / relative
        check_path(source, root)
        if not source.exists():
            continue
        if not source.is_dir():
            raise ValueError(f"Expected directory: {source}")
        packages = []
        for child in sorted(source.iterdir()):
            check_path(child, root)
            if kind == "lessons-learned" and child.name == ".gitignore" and child.is_file():
                continue
            nested = (kind == "processed" and child.name in REFINED_CATEGORIES and not (child / "SKILL.md").exists())
            typed = kind == "lessons-learned" and child.name in body_store.FOLDERS.values()
            if nested or typed:
                if not child.is_dir():
                    raise ValueError(f"Expected category directory: {child}")
                packages.extend(sorted(child.iterdir()))
            else:
                packages.append(child)
        for package in packages:
            check_path(package, root)
            if kind == "lessons-learned" and package.is_file() and package.suffix in (".json", ".md"):
                entry = lesson_entry(root, package, identity_root)
            elif kind == "lessons-learned" and package.is_dir() and (package / "assets/lesson.json").is_file():
                check_path(package / "assets/lesson.json", root)
                entry = lesson_entry(root, package / "assets/lesson.json", identity_root)
                entry["location"] = "legacy"
            else:
                if not package.is_dir():
                    raise ValueError(f"Expected package directory: {package}")
                if kind == "progress" and ((package / "progress.md").exists() or any(CONTRACT_FILE.fullmatch(child.name) for child in package.iterdir())):
                    entry = contract_entry(root, package)
                else:
                    entry = catalog_entry(root, package, kind)
                    if kind == "progress":
                        entry["location"] = "legacy"
            entry.setdefault("location", location)
            identity = tuple(entry[field] for field in ("documentType", "category", "domain", "name"))
            if identity in identities:
                raise ValueError(
                    f"Duplicate Document identity: {identity}: "
                    f"{identities[identity]} and {entry['packagePath']}"
                )
            identities[identity] = entry["packagePath"]
            if "contract" in entry:
                # The same contract in canonical and legacy storage is a conflict even when metadata names differ.
                contract_id = entry["contract"]["id"]
                if contract_id in contracts:
                    raise ValueError(
                        f"Duplicate contract ID: {contract_id}: "
                        f"{contracts[contract_id]} and {entry['packagePath']}"
                    )
                contracts[contract_id] = entry["packagePath"]
            documents.append(entry)
    return {
        "schemaVersion": "0.1.0",
        "kind": "document-catalog",
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--documents-root", type=Path, help="Physical workspace containing docs; runtime identity stays --project-root")
    args = parser.parse_args()
    try:
        catalog = build_catalog(args.project_root, args.documents_root)
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
