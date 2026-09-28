#!/usr/bin/env python3
"""Copy project Skill documents from docs/skills into .codex/skills."""

import argparse
import filecmp
import json
from pathlib import Path
import shutil
import sys


ROUTES = {"skills": "skills"}


def check_path(path: Path, root: Path) -> None:
    """Reject symlinks, including dangling links and linked parent directories."""
    for item in (path, *path.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError(f"Symlinks are not supported: {item}")
        if item != path and item.exists() and not item.is_dir():
            raise ValueError(f"Expected directory: {item}")


def inventory(path: Path, root: Path) -> dict[str, str]:
    check_path(path, root)
    if not path.is_dir():
        raise ValueError(f"Expected package directory: {path}")
    entries = {}
    for child in sorted(path.rglob("*")):
        check_path(child, root)
        if not child.is_dir() and not child.is_file():
            raise ValueError(f"Unsupported file: {child}")
        entries[child.relative_to(path).as_posix()] = "dir" if child.is_dir() else "file"
    return entries


def export_documents(root: Path, apply: bool = False) -> list[dict[str, str]]:
    """Preflight all packages before copying; never merge or overwrite a target."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Expected project directory: {root}")
    plan = []
    for source_type, destination_type in ROUTES.items():
        source_root = root / "docs" / source_type
        target_root = root / ".codex" / destination_type
        check_path(source_root, root)
        check_path(target_root, root)
        if target_root.exists() and not target_root.is_dir():
            raise ValueError(f"Expected directory: {target_root}")
        if not source_root.exists():
            continue
        if not source_root.is_dir():
            raise ValueError(f"Expected directory: {source_root}")
        for source in sorted(source_root.iterdir()):
            files = inventory(source, root)
            if files.get("SKILL.md") != "file":
                raise ValueError(f"Document package needs SKILL.md: {source}")
            target = target_root / source.name
            check_path(target, root)
            action = "copy"
            if target.exists():
                target_files = inventory(target, root)
                identical = files == target_files and all(
                    filecmp.cmp(source / name, target / name, shallow=False)
                    for name, kind in files.items() if kind == "file"
                )
                if not identical:
                    raise ValueError(f"Destination conflict (no files copied): {target}")
                action = "unchanged"
            plan.append({"source": str(source), "destination": str(target), "action": action})
    if apply:
        for entry in plan:
            if entry["action"] == "copy":
                target = Path(entry["destination"])
                check_path(target, root)
                target.parent.mkdir(parents=True, exist_ok=True)
                # copytree refuses a target that appeared after preflight.
                shutil.copytree(entry["source"], target)
                entry["action"] = "copied"
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Copy packages; default only previews.")
    args = parser.parse_args()
    try:
        result = export_documents(args.project_root, args.apply)
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"mode": "apply" if args.apply else "preview", "packages": result},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
