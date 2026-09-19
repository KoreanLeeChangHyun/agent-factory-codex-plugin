#!/usr/bin/env python3
"""Synchronize .codex/skills from the authoritative docs/skills source."""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile

from export_documents import check_path, inventory


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
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(state_dir):
    lock = state_dir / "lock"
    check_path(lock, state_dir)
    if lock.is_dir():
        # An older installation may still own this directory. Never remove it
        # automatically: that could permit concurrent old and new sync writers.
        raise ValueError(f"Legacy document sync lock; confirm no sync is running before removing: {lock}")
    if lock.exists() and not lock.is_file():
        raise ValueError(f"Expected regular lock file: {lock}")
    # Keep the file in place so all contenders lock the same inode. Closing the
    # descriptor (including process termination) releases the operating-system lock.
    with lock.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError(f"Document sync already running: {lock}") from None
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(f"Document sync already running: {lock}") from None
        yield


def sync_directory(path):
    # Persist the journal before touching output, including its directory entry.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def snapshot(path, root):
    entries = inventory(path, root)
    return {name: "dir" if kind == "dir" else "sha256:" + digest(path / name)
            for name, kind in entries.items()}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def read_manifest(path, root):
    check_path(path, root)
    if not path.exists():
        # Missing state grants no ownership, even for byte-identical legacy copies.
        return {}
    if not path.is_file():
        raise ValueError(f"Expected regular ownership manifest: {path}")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    return validate_manifest(data)


def validate_manifest(data):
    if (not isinstance(data, dict) or set(data) != {"version", "entries"}
            or type(data["version"]) is not int or data["version"] != 1
            or not isinstance(data["entries"], dict)):
        raise ValueError("Invalid ownership manifest schema; preserve state and restore a trusted backup")
    entries = data["entries"]
    for name, state in entries.items():
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or any(ord(char) < 32 for char in name)
                or any(part in ("", ".", "..") for part in name.split("/"))):
            raise ValueError(f"Unsafe manifest path: {name!r}")
        if not isinstance(state, str) or (state != "dir" and not re.fullmatch(r"sha256:[0-9a-f]{64}", state)):
            raise ValueError(f"Invalid manifest state: {name}")
        parts = name.split("/")
        for size in range(1, len(parts)):
            if entries.get("/".join(parts[:size])) != "dir":
                raise ValueError(f"Missing manifest parent: {name}")
        if len(parts) == 1 and (state != "dir" or not isinstance(entries.get(name + "/SKILL.md"), str)
                                or not re.fullmatch(r"sha256:[0-9a-f]{64}", entries[name + "/SKILL.md"])):
            raise ValueError(f"Invalid manifest package: {name}")
    return entries


def document_state(entries):
    return {"version": 1, "entries": entries}


def sync(root):
    root = root.resolve(strict=True)
    source = root / "docs/skills"
    target = root / ".codex/skills"
    check_path(source, root)
    if not source.exists():
        return []
    check_path(target, root)
    if target.exists() and not target.is_dir():
        raise ValueError(f"Expected directory: {target}")
    state_dir = root / ".codex/.document-sync"
    check_path(state_dir, root)
    state_dir.mkdir(parents=True, exist_ok=True)
    with locked(state_dir):
        manifest = state_dir / "manifest.json"
        pending = state_dir / "pending.json"
        check_path(pending, root)
        if pending.exists():
            raise ValueError(f"Interrupted document sync: {pending}. Preserve output and journal; "
                             "review previous/planned hashes and reconcile with a backup before "
                             "manually clearing the journal. Automatic retry is blocked.")
        previous = read_manifest(manifest, root)
        wanted = snapshot(source, root)
        for package in source.iterdir():
            if wanted.get(package.name) != "dir" or not wanted.get(package.name + "/SKILL.md", "").startswith("sha256:"):
                raise ValueError(f"Document package needs SKILL.md: {package}")
        validate_manifest(document_state(wanted))
        actual = snapshot(target, root) if target.exists() else {}
        owned = {name for name in previous if "/" not in name}
        requested = {name for name in wanted if "/" not in name}
        conflicts = []
        for package in sorted(owned | requested):
            if package not in owned:
                if package in actual:
                    conflicts.append(f"Unowned destination: {target / package} (identical legacy copies are not adopted)")
                continue
            before = {name: value for name, value in previous.items()
                      if name == package or name.startswith(package + "/")}
            now = {name: value for name, value in actual.items()
                   if name == package or name.startswith(package + "/")}
            for name in sorted(set(before) | set(now)):
                if before.get(name) != now.get(name):
                    conflicts.append(f"Independent destination change: {target / name}")
        if conflicts:
            raise ValueError("; ".join(conflicts) + ". No documents changed. Back up and reconcile "
                             "destination changes with the source; move unowned collisions aside "
                             "only with the owner's approval, then invoke sync again.")
        if previous == wanted:
            return []
        # Never infer ownership from a partially completed copy. An interrupted run
        # retains both states for explicit recovery and blocks every subsequent write.
        atomic_write(pending, json.dumps({"version": 1, "previous": previous,
                                          "planned": wanted}, sort_keys=True).encode())
        changes = []
        for name in sorted(previous, key=lambda value: (len(value.split("/")), value), reverse=True):
            if name not in wanted or (previous[name] == "dir") != (wanted[name] == "dir"):
                path = target / name
                check_path(path, root)
                if previous[name] == "dir":
                    path.rmdir()
                else:
                    path.unlink()
                sync_directory(path.parent)
                changes.append({"path": str(path.relative_to(root)), "action": "delete"})
        target.mkdir(parents=True, exist_ok=True)
        for name, state in sorted(wanted.items()):
            path = target / name
            check_path(path, root)
            if state == "dir":
                if not path.exists():
                    path.mkdir()
                    sync_directory(path.parent)
            elif state != previous.get(name):
                content = (source / name).read_bytes()
                if "sha256:" + hashlib.sha256(content).hexdigest() != state:
                    raise ValueError(f"Source changed during sync: {source / name}; review {pending}")
                atomic_write(path, content)
                changes.append({"path": str(path.relative_to(root)), "action": "write"})
        atomic_write(manifest, json.dumps(document_state(wanted), sort_keys=True).encode())
        pending.unlink()
        sync_directory(state_dir)
        return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        operations = sync(args.project_root)
        print(json.dumps({"changes": operations}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
