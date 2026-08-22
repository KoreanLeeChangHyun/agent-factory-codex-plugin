"""Shared safe destination and provenance helpers for Gather provider scripts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path


SYNC_MANAGER = Path(__file__).resolve().parent / "sync.py"


def _load_manager():
    spec = importlib.util.spec_from_file_location("agent_factory_sync_manager", SYNC_MANAGER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sync manager: {SYNC_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_manager = _load_manager()
DIRECTORY_OPEN_FLAGS = sync_manager.DIRECTORY_OPEN_FLAGS
FILE_NOFOLLOW = sync_manager.FILE_NOFOLLOW


def resolve(source, destination=None, project_root=None):
    result = sync_manager.resolve_sync_destination(
        source, destination=destination, project_root=project_root
    )
    print(json.dumps({"event": "destination-resolved", **result}, ensure_ascii=False))
    return Path(result["destination"])


def safe_name(value, fallback="item"):
    cleaned = re.sub(r"[\\/\x00-\x1f:]", "_", str(value or fallback)).strip(" .")
    return cleaned[:180] or fallback


class DestinationStore:
    """Keep all destination traversal anchored to directory descriptors."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise ValueError("resolved destination must be absolute")
        self.descriptor = -1

    def __enter__(self):
        descriptor = os.open(self.root.anchor, DIRECTORY_OPEN_FLAGS)
        try:
            for part in self.root.parts[1:]:
                try:
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                except FileNotFoundError:
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor = descriptor
        return self

    def __exit__(self, *_):
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    @staticmethod
    def _parts(relative):
        candidate = Path(relative)
        if candidate.is_absolute() or not candidate.parts:
            raise ValueError(f"destination-relative path required: {relative}")
        if any(part in {"", ".", ".."} for part in candidate.parts):
            raise ValueError(f"unsafe destination-relative path: {relative}")
        return candidate.parts

    def _open_directory(self, parts, *, create):
        descriptor = os.dup(self.descriptor)
        try:
            for part in parts:
                try:
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, mode=0o755, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(part, DIRECTORY_OPEN_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def read_text(self, relative):
        parts = self._parts(relative)
        try:
            parent = self._open_directory(parts[:-1], create=False)
        except FileNotFoundError:
            return None
        descriptor = -1
        try:
            try:
                descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | FILE_NOFOLLOW, dir_fd=parent)
            except FileNotFoundError:
                return None
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeError(f"destination file must be regular: {relative}")
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                descriptor = -1
                return stream.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(parent)

    def write_bytes(self, relative, payload):
        parts = self._parts(relative)
        parent = self._open_directory(parts[:-1], create=True)
        temporary_name = None
        try:
            try:
                existing = os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | FILE_NOFOLLOW, dir_fd=parent)
            except FileNotFoundError:
                existing = -1
            if existing >= 0:
                try:
                    if not stat.S_ISREG(os.fstat(existing).st_mode):
                        raise RuntimeError(f"destination file must be regular: {relative}")
                finally:
                    os.close(existing)
            for _ in range(32):
                temporary_name = f".gather.{secrets.token_hex(12)}"
                try:
                    descriptor = os.open(
                        temporary_name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NONBLOCK | FILE_NOFOLLOW,
                        0o600,
                        dir_fd=parent,
                    )
                    break
                except FileExistsError:
                    continue
            else:
                raise RuntimeError("cannot allocate destination temporary file")
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            temporary_name = None
            os.fsync(parent)
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=parent)
                except FileNotFoundError:
                    pass
            os.close(parent)
        return self.root / Path(relative)


def write_bytes(store, relative, payload):
    return store.write_bytes(relative, payload)


def write_json(store, relative, value):
    return write_bytes(
        store,
        relative,
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(),
    )


def load_index(store):
    entries = {}
    content = store.read_text("index.jsonl")
    if content is not None:
        for line in content.splitlines():
            if line.strip():
                entry = json.loads(line)
                entries[entry["id"]] = entry
    return entries


def save_index(store, entries):
    rows = [json.dumps(entries[key], ensure_ascii=False, sort_keys=True) for key in sorted(entries)]
    write_bytes(store, "index.jsonl", ("\n".join(rows) + ("\n" if rows else "")).encode())


def provenance(identifier, source_url, local_path, payload, **extra):
    return {
        "id": identifier,
        "source_url": source_url,
        "local_path": str(local_path),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name}; credentials must not be stored in the repository.")
    return value
