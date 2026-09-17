#!/usr/bin/env python3
"""Synchronize docs to Codex projections, using docs as the authoritative source."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from export_documents import ROUTES, check_path, inventory


def digest(path):
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Expected regular file: {path}")
    with path.open("rb") as stream:
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".document-sync-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(state_dir):
    lock = state_dir / "lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Document sync already running, or stale lock: {lock}") from None
    try:
        yield
    finally:
        lock.rmdir()


def sync(root):
    root = root.resolve(strict=True)
    plans = []
    # Preflight all active roots before overwriting any document. A missing source
    # root is skipped; an existing empty root intentionally clears its projection.
    for kind, destination in ROUTES.items():
        source = root / "docs" / kind
        target = root / ".codex" / destination
        check_path(source, root)
        check_path(target, root)
        if not source.exists():
            continue
        wanted = inventory(source, root)
        for package in source.iterdir():
            entries = inventory(package, root)
            if kind != "original" and entries.get("SKILL.md") != "file":
                raise ValueError(f"Document package needs SKILL.md: {package}")
        actual = inventory(target, root) if target.is_dir() else {}
        if target.exists() and not target.is_dir():
            raise ValueError(f"Expected directory: {target}")
        plans.append((source, target, wanted, actual))
    if not plans:
        return []
    lock_dir = root / ".codex/.document-sync"
    check_path(lock_dir, root)
    lock_dir.mkdir(parents=True, exist_ok=True)
    changes = []
    with locked(lock_dir):
        for source, target, wanted, actual in plans:
            # Re-read while holding the lock, in case another sync just finished.
            actual = inventory(target, root) if target.exists() else {}
            for name in sorted(actual, key=lambda key: len(Path(key).parts), reverse=True):
                if wanted.get(name) != actual[name]:
                    path = target / name
                    check_path(path, root)
                    path.rmdir() if actual[name] == "dir" else path.unlink()
                    changes.append({"path": str(path.relative_to(root)), "action": "delete"})
            target.mkdir(parents=True, exist_ok=True)
            for name, kind in sorted(wanted.items()):
                path = target / name
                check_path(path, root)
                if kind == "dir":
                    path.mkdir(parents=True, exist_ok=True)
                elif digest(source / name) != digest(path):
                    atomic_write(path, (source / name).read_bytes())
                    changes.append({"path": str(path.relative_to(root)), "action": "write"})
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--hook", action="store_true", help="Read Codex hook JSON from stdin.")
    args = parser.parse_args()
    try:
        root = args.project_root
        if args.hook:
            payload = json.load(sys.stdin)
            cwd = payload.get("cwd") if isinstance(payload, dict) else None
            if not isinstance(cwd, str) or not Path(cwd).is_absolute():
                raise ValueError("Hook requires an absolute cwd")
            root = Path(cwd)
        if root is None:
            parser.error("--project-root or --hook is required")
        # Do not initialize unrelated repositories or infer an ancestor project.
        if args.hook and not any((root / "docs" / kind).exists() for kind in ROUTES):
            print("{}")
            return 0
        operations = sync(root)
        print(json.dumps({} if args.hook else {"changes": operations}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as error:
        if args.hook:
            # Surface conflicts without blocking Stop and creating a continuation loop.
            print(json.dumps({"systemMessage": f"Document sync incomplete: {error}"}))
            return 0
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
