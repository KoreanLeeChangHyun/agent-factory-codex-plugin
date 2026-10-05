#!/usr/bin/env python3
"""Preview, back up, and safely apply contract-listed document path moves."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from storage import document_migration  # noqa: E402


MANIFEST_NAME = "migration-manifest.json"
MARKDOWN_LINK = re.compile(r"(?P<prefix>\]\()(?P<target>[^)\n]+)(?P<suffix>\))")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_relative(raw: str, field: str) -> Path:
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe {field}: {raw!r}")
    normalized = Path(os.path.normpath(raw))
    if normalized == Path("."):
        raise ValueError(f"Unsafe {field}: {raw!r}")
    return normalized


def check_no_symlinks(path: Path, root: Path) -> None:
    if path != root and root not in path.parents:
        raise ValueError(f"Path is outside {root}: {path}")
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"Symlinks are not supported: {current}")
        if current.exists() and current != path and not current.is_dir():
            raise ValueError(f"Expected directory: {current}")
        current = current.parent
    if path.is_symlink():
        raise ValueError(f"Symlinks are not supported: {path}")


def task_ids(raw: str) -> set[str]:
    return {part.strip() for part in re.split(r"[,|]", raw) if part.strip()}


def load_moves(operations: Path, task_id: str) -> list[dict[str, str]]:
    with operations.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required = {"taskIds", "operation", "path", "destination"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Operations CSV needs columns: {sorted(required)}")
        moves = [row for row in reader if task_id in task_ids(row["taskIds"])
                 and row["operation"] == "move"]
    if not moves:
        raise ValueError(f"No move operations found for task ID {task_id!r}")
    return moves


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(path)))


def rewrite_current_links(content: bytes, source: Path, destination: Path,
                          destinations: dict[Path, Path], relative_source: Path) -> tuple[bytes, int]:
    """Rewrite live Markdown links in package roots; archived asset text stays unchanged."""
    if source.name != "SKILL.md" or "assets" in relative_source.parts:
        return content, 0
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content, 0
    changes = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changes
        raw = match.group("target")
        if not raw or raw.startswith(("#", "/", "<")) or "://" in raw or any(c.isspace() for c in raw):
            return match.group(0)
        path_text, marker, fragment = raw.partition("#")
        current_target = lexical(source.parent / path_text)
        moved_target = destinations.get(current_target)
        if moved_target is None:
            return match.group(0)
        new_target = Path(os.path.relpath(moved_target, destination.parent)).as_posix()
        rewritten = new_target + (marker + fragment if marker else "")
        if rewritten == raw:
            return match.group(0)
        changes += 1
        return f"{match.group('prefix')}{rewritten}{match.group('suffix')}"

    rewritten = MARKDOWN_LINK.sub(replace, text)
    return rewritten.encode("utf-8"), changes


def build_plan(root: Path, operations: Path, task_id: str,
               backup: Path | None = None) -> list[dict[str, object]]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Expected project directory: {root}")
    rows = load_moves(operations, task_id)
    source_paths: set[Path] = set()
    destination_paths: set[Path] = set()
    pairs: list[tuple[Path, Path, Path, Path]] = []
    for row in rows:
        source_relative = check_relative(row["path"], "source path")
        destination_relative = check_relative(row["destination"], "destination path")
        source = lexical(root / source_relative)
        destination = lexical(root / destination_relative)
        if root not in source.parents or root not in destination.parents or source == destination:
            raise ValueError(f"Move escapes project or has identical endpoints: {row}")
        if source in source_paths or destination in destination_paths:
            raise ValueError(f"Duplicate move endpoint: {row}")
        source_paths.add(source)
        destination_paths.add(destination)
        pairs.append((source, destination, source_relative, destination_relative))
    destinations = {source: destination for source, destination, _, _ in pairs}
    plan = []
    for source, destination, source_relative, destination_relative in pairs:
        check_no_symlinks(source, root)
        check_no_symlinks(destination, root)
        source_exists = source.exists()
        destination_exists = destination.exists()
        if source_exists and not source.is_file():
            raise ValueError(f"Expected regular source file: {source}")
        if destination_exists and not destination.is_file():
            raise ValueError(f"Expected regular destination file: {destination}")
        backup_source = None if backup is None else backup / "files" / source_relative
        if backup_source is not None:
            check_no_symlinks(backup_source, backup)
        original = source.read_bytes() if source_exists else (
            backup_source.read_bytes() if backup_source is not None and backup_source.is_file() else None
        )
        expected, link_changes = ((None, 0) if original is None else
                                  rewrite_current_links(original, source, destination,
                                                        destinations, source_relative))
        plan.append({
            "source": source,
            "destination": destination,
            "sourceRelative": source_relative.as_posix(),
            "destinationRelative": destination_relative.as_posix(),
            "sourceExists": source_exists,
            "destinationExists": destination_exists,
            "sourceSha256": None if original is None else sha256_bytes(original),
            "expectedBytes": expected,
            "destinationSha256": None if expected is None else sha256_bytes(expected),
            "linkChanges": link_changes,
        })
    return plan


def manifest_payload(root: Path, operations: Path, task_id: str,
                     plan: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "projectRoot": str(root),
        "operationsFile": str(operations),
        "operationsSha256": sha256_file(operations),
        "taskId": task_id,
        "entries": [
            {
                "source": entry["sourceRelative"],
                "destination": entry["destinationRelative"],
                "sourceSha256": entry["sourceSha256"],
                "destinationSha256": entry["destinationSha256"],
                "linkChanges": entry["linkChanges"],
            }
            for entry in plan
        ],
    }


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def create_backup(root: Path, backup: Path, payload: dict[str, object],
                  plan: list[dict[str, object]]) -> None:
    backup.mkdir(parents=True, exist_ok=True)
    check_no_symlinks(backup, backup.parent)
    for entry in plan:
        target = backup / "files" / str(entry["sourceRelative"])
        check_no_symlinks(target, backup)
        if target.exists():
            if not target.is_file() or sha256_file(target) != entry["sourceSha256"]:
                raise ValueError(f"Backup conflict: {target}")
            continue
        if not entry["sourceExists"]:
            raise ValueError(f"Cannot back up missing source: {entry['sourceRelative']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            shutil.copy2(entry["source"], temporary_path)
            if sha256_file(temporary_path) != entry["sourceSha256"]:
                raise ValueError(f"Backup verification failed: {entry['sourceRelative']}")
            os.link(temporary_path, target)
        finally:
            temporary_path.unlink(missing_ok=True)
    manifest = backup / MANIFEST_NAME
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if manifest.exists():
        if manifest.read_bytes() != encoded:
            raise ValueError(f"Backup manifest conflict: {manifest}")
    else:
        write_atomic(manifest, encoded)


def validate_backup(backup: Path, payload: dict[str, object],
                    plan: list[dict[str, object]]) -> None:
    manifest = backup / MANIFEST_NAME
    if not manifest.is_file():
        raise ValueError(f"Apply requires a completed backup manifest: {manifest}")
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    if recorded != payload:
        raise ValueError(f"Backup manifest does not match the current migration: {manifest}")
    for entry in plan:
        copy = backup / "files" / str(entry["sourceRelative"])
        check_no_symlinks(copy, backup)
        if not copy.is_file() or sha256_file(copy) != entry["sourceSha256"]:
            raise ValueError(f"Missing or changed backup: {copy}")


def classify(plan: list[dict[str, object]], backup_valid: bool) -> dict[str, int]:
    summary = {"pending": 0, "alreadyMoved": 0, "interrupted": 0}
    for entry in plan:
        source = entry["source"]
        destination = entry["destination"]
        source_exists = source.is_file()
        destination_exists = destination.is_file()
        source_matches = source_exists and sha256_file(source) == entry["sourceSha256"]
        destination_matches = destination_exists and sha256_file(destination) == entry["destinationSha256"]
        if source_exists and not destination_exists and source_matches:
            summary["pending"] += 1
        elif not source_exists and destination_exists and destination_matches and backup_valid:
            summary["alreadyMoved"] += 1
        elif source_exists and destination_exists and source_matches and destination_matches and backup_valid:
            summary["interrupted"] += 1
        elif source_exists and destination_exists:
            raise ValueError(f"Destination collision: {destination}")
        elif not source_exists and destination_exists:
            raise ValueError(f"Unverified destination with missing source: {destination}")
        elif source_exists:
            raise ValueError(f"Source changed since planning: {source}")
        else:
            raise ValueError(f"Both source and destination are missing: {entry['sourceRelative']}")
    return summary


def publish_new(destination: Path, content: bytes, source: Path, expected_sha256: str) -> None:
    """Expose the destination only after its complete, verified bytes exist; never replace a file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".migrate-", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        shutil.copystat(source, temporary_path)
        if sha256_file(temporary_path) != expected_sha256:
            raise ValueError(f"Destination verification failed: {destination}")
        try:
            os.link(temporary_path, destination)
        except FileExistsError as error:
            raise ValueError(f"Destination appeared during apply: {destination}") from error
    finally:
        temporary_path.unlink(missing_ok=True)


def apply_plan(plan: list[dict[str, object]], root: Path) -> dict[str, int]:
    result = {"moved": 0, "completedInterrupted": 0, "unchanged": 0}
    for entry in plan:
        source = entry["source"]
        destination = entry["destination"]
        if not source.exists():
            result["unchanged"] += 1
            continue
        if destination.exists():
            # Re-check both copies now; classify() ran before any earlier entry was applied.
            if (sha256_file(source) != entry["sourceSha256"]
                    or sha256_file(destination) != entry["destinationSha256"]):
                raise ValueError(f"Interrupted move changed before completion: {destination}")
            source.unlink()
            result["completedInterrupted"] += 1
            continue
        if sha256_file(source) != entry["sourceSha256"]:
            raise ValueError(f"Source changed since planning: {source}")
        publish_new(destination, entry["expectedBytes"], source, entry["destinationSha256"])
        source.unlink()
        result["moved"] += 1
    source_parents = {entry["source"].parent for entry in plan}
    for directory in sorted(source_parents, key=lambda item: len(item.parts), reverse=True):
        current = directory
        while current != root and root in current.parents and current.exists():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
    return result


def public_plan(plan: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{key: entry[key] for key in ("sourceRelative", "destinationRelative", "linkChanges")}
            for entry in plan]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--operations", type=Path, help="Contract-listed file moves (required without --storage-layout)")
    parser.add_argument("--storage-layout", action="store_true", help="Migrate legacy JSON lessons and flat refined packages")
    parser.add_argument("--documents-root", type=Path, help="Physical workspace containing docs; runtime identity stays --project-root")
    parser.add_argument("--language", help="Selected lesson body language; preserves original language and quoted source text")
    parser.add_argument("--classifications", type=Path, help="JSON mapping of source package paths to categories after inspecting their bodies")
    parser.add_argument("--exclude-path", action="append", default=[], help="Preserve a dirty/untracked document or package; repeat as needed")
    parser.add_argument("--task-id", default="T3")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--backup", action="store_true", help="Create and verify a backup after preview.")
    mode.add_argument("--apply", action="store_true", help="Apply contract moves after backup, or create a recoverable storage-layout backup and apply.")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    try:
        root = args.project_root.resolve(strict=True)
        if args.storage_layout:
            docs = (args.documents_root or root).resolve(strict=True)
            classifications = {} if args.classifications is None else json.loads(args.classifications.read_text(encoding="utf-8"))
            if not isinstance(classifications, dict) or any(value not in document_migration.CATEGORIES for value in classifications.values()):
                raise ValueError("Classifications must map document paths to supported refined categories")
            if args.backup or args.operations:
                raise ValueError("--storage-layout uses dry-run or --apply --backup-dir, without --operations/--backup")
            if args.apply:
                if args.backup_dir is None:
                    raise ValueError("--apply requires --backup-dir")
                result = document_migration.apply(root, docs, args.backup_dir, classifications, args.exclude_path, args.language)
            else:
                plan = document_migration.preview(root, docs, classifications, args.exclude_path, args.language)
                result = {"mode": "dry-run", **document_migration.summary(plan)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.operations is None:
            raise ValueError("--operations is required without --storage-layout")
        if args.classifications or args.exclude_path or args.language:
            raise ValueError("--classifications, --exclude-path and --language require --storage-layout")
        root = (args.documents_root or root).resolve(strict=True)
        operations = args.operations.resolve(strict=True)
        if (args.backup or args.apply) and args.backup_dir is None:
            raise ValueError("--backup and --apply require --backup-dir")
        backup = None if args.backup_dir is None else args.backup_dir.resolve()
        if backup is not None and (backup == root or root in backup.parents):
            raise ValueError("--backup-dir must be outside the project root")
        plan = build_plan(root, operations, args.task_id, backup)
        payload = manifest_payload(root, operations, args.task_id, plan)
        if args.backup:
            classify(plan, backup_valid=False)
            create_backup(root, backup, payload, plan)
            validate_backup(backup, payload, plan)
            summary = classify(plan, backup_valid=True)
            result = {"mode": "backup", "backup": str(backup), "summary": summary}
        elif args.apply:
            validate_backup(backup, payload, plan)
            before = classify(plan, backup_valid=True)
            applied = apply_plan(plan, root)
            after = classify(plan, backup_valid=True)
            result = {"mode": "apply", "backup": str(backup), "before": before,
                      "applied": applied, "after": after}
        else:
            backup_valid = False
            if backup is not None and (backup / MANIFEST_NAME).is_file():
                validate_backup(backup, payload, plan)
                backup_valid = True
            summary = classify(plan, backup_valid=backup_valid)
            result = {"mode": "preview", "summary": summary,
                      "linkChanges": sum(int(entry["linkChanges"]) for entry in plan),
                      "operations": public_plan(plan)}
    except (OSError, ValueError, csv.Error, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
