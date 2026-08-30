#!/usr/bin/env python3
"""Build and inspect the non-authoritative Agent Factory local catalog."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable


CATALOG_RELATIVE_PATH = Path(".agent-factory/db.sqlite")
AGENT_RELATIVE_PATH = Path(".agent-factory/agent")
DOCUMENT_RELATIVE_PATH = Path(".agent-factory/document")
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "assets" / "schema" / "catalog.sql"
SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")
MAX_JSON_BYTES = 1024 * 1024
MAX_HASH_BYTES = 8 * 1024 * 1024
MAX_AGENTS = 2048
MAX_RUNS = 20_000
MAX_LOOPS = 4096
MAX_DISPATCHES = 20_000
MAX_DOCUMENT_FILES = 20_000
MAX_DOCUMENT_DEPTH = 8
MAX_SEARCH_TEXT_BYTES = 256 * 1024
MAX_SEARCH_TOTAL_BYTES = 8 * 1024 * 1024
MAX_SEARCH_RESULTS = 100
MAX_SEARCH_QUERY_BYTES = 4096
SEARCHABLE_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
}
CURRENT_SCHEMA_VERSION = 3
SUPPORTED_REBUILD_MIGRATION_VERSIONS = frozenset({1, 2})

SPECIFICATION_META_NAMES = {
    "agent-factory:specification-id",
    "agent-factory:ai-root",
    "agent-factory:ai-binding-entry",
}
SPECIFICATION_SKILL_METADATA_KEYS = {
    "specification-id",
    "human-entry",
    "ai-root",
}


class CatalogError(RuntimeError):
    """A visible catalog operation failure."""


class _SpecificationMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "meta":
            return
        attributes = {name.casefold(): value for name, value in attrs}
        name = attributes.get("name")
        content = attributes.get("content")
        if name in SPECIFICATION_META_NAMES and content is not None:
            self.values[name] = content.strip()


def _within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_project_root(override: str | None) -> Path:
    candidate = Path(override).expanduser() if override else Path.cwd()
    if override and ".." in candidate.parts:
        raise CatalogError("--project-root must not contain '..' traversal")
    try:
        candidate = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise CatalogError(f"project path does not exist: {candidate}") from exc
    completed = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise CatalogError(completed.stderr.strip() or "not inside a Git work tree")
    output = completed.stdout.strip()
    if not output or "\n" in output:
        raise CatalogError("Git returned an invalid project root")
    root = Path(output).resolve(strict=True)
    if override and candidate != root:
        raise CatalogError(f"--project-root must name the Git root itself: {root}")
    return root


def _safe_path(project_root: Path, relative: Path, description: str) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise CatalogError(f"invalid {description} path: {relative}")
    candidate = project_root / relative
    current = project_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise CatalogError(f"{description} must not use a symbolic link: {current}")
        if current.exists() and not _within(project_root, current.resolve(strict=True)):
            raise CatalogError(f"{description} escapes the project root: {current}")
    return candidate


def _relative(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        if path.is_symlink():
            raise CatalogError(f"catalog source must not be a symbolic link: {path}")
        if not path.is_file():
            return None, "unsafe-source"
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                return None, "unsafe-source"
            if metadata.st_size > MAX_JSON_BYTES:
                return None, "source-too-large"
            with os.fdopen(descriptor, "r", encoding="utf-8") as source:
                descriptor = -1
                value = json.load(source)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not isinstance(value, dict):
            return None, "malformed-json"
        return value, None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "malformed-json"


def _text(value: Any, maximum: int = 512) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        rendered = str(value)
        return rendered[:maximum]
    return None


def _sha256(value: Any) -> str | None:
    rendered = _text(value, 65)
    if rendered is None or len(rendered) != 64:
        return None
    try:
        int(rendered, 16)
    except ValueError:
        return None
    return rendered.lower()


def _hash_id(prefix: str, source_path: str) -> str:
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


def _bounded_utf8(path: Path, maximum: int = MAX_JSON_BYTES) -> tuple[str | None, str | None]:
    try:
        if path.is_symlink() or not path.is_file():
            return None, "unsafe-source"
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
                return None, "source-too-large"
            with os.fdopen(descriptor, "r", encoding="utf-8") as source:
                descriptor = -1
                return source.read(), None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except (OSError, UnicodeError):
        return None, "unreadable-source"


def _specification_html_metadata(path: Path) -> tuple[dict[str, str], str | None]:
    content, error = _bounded_utf8(path)
    if content is None:
        return {}, error
    parser = _SpecificationMetaParser()
    try:
        parser.feed(content)
    except ValueError:
        return {}, "malformed-binding"
    missing = SPECIFICATION_META_NAMES - parser.values.keys()
    if missing:
        return parser.values, "missing-binding"
    return parser.values, None


def _skill_binding_metadata(path: Path) -> tuple[dict[str, str], str | None]:
    content, error = _bounded_utf8(path)
    if content is None:
        return {}, error
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "missing-frontmatter"
    try:
        closing = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}, "malformed-frontmatter"
    values: dict[str, str] = {}
    in_metadata = False
    for line in lines[1:closing]:
        if line == "metadata:":
            in_metadata = True
            continue
        if in_metadata and line and not line.startswith((" ", "\t")):
            break
        if not in_metadata:
            continue
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key in SPECIFICATION_SKILL_METADATA_KEYS:
            values[key] = value.strip().strip("'\"")
    missing = SPECIFICATION_SKILL_METADATA_KEYS - values.keys()
    if missing:
        return values, "missing-reciprocal-binding"
    return values, None


def _binding_path(
    project_root: Path, value: str | None, description: str
) -> tuple[Path | None, str | None]:
    if not value:
        return None, "missing-binding"
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != value.rstrip("/")
    ):
        return None, "invalid-binding-path"
    try:
        return _safe_path(project_root, relative, description), None
    except CatalogError:
        return None, "invalid-binding-path"


def _error_fields(data: dict[str, Any] | None, parse_error: str | None) -> tuple[str | None, str | None]:
    if parse_error:
        return parse_error, "Source metadata could not be safely parsed."
    error = data.get("error") if data else None
    if not isinstance(error, dict):
        error = data.get("controlPlaneError") if data else None
    if isinstance(error, dict):
        return _text(error.get("code"), 128), "Authoritative source reports an error."
    return None, None


def _bounded_children(root: Path, maximum: int, kind: str) -> list[Path]:
    if root.is_symlink():
        raise CatalogError(f"{kind} root must not be a symbolic link: {root}")
    if not root.exists():
        return []
    if not root.is_dir():
        raise CatalogError(f"{kind} root is not a safe directory: {root}")
    children = list(root.iterdir())
    children.sort(key=lambda path: (path.name.casefold(), path.name))
    if len(children) > maximum:
        raise CatalogError(f"{kind} scan exceeds the limit of {maximum} entries")
    for child in children:
        if child.is_symlink():
            raise CatalogError(f"{kind} source must not be a symbolic link: {child}")
    return children


def _agent_rows(project_root: Path) -> dict[str, list[tuple[Any, ...]]]:
    rows: dict[str, list[tuple[Any, ...]]] = {
        "agents": [], "sessions": [], "runs": [], "loops": [],
        "loop_runs": [], "relationships": [], "dispatches": [],
    }
    agent_root = _safe_path(project_root, AGENT_RELATIVE_PATH, "Agent runtime")
    agent_dirs = [path for path in _bounded_children(agent_root, MAX_AGENTS, "Agent") if path.is_dir()]
    known_agents: set[str] = set()
    session_owner: dict[str, str] = {}
    run_owner: dict[str, str] = {}
    ambiguous_run_ids: set[str] = set()
    loop_sources: list[tuple[Path, str]] = []
    dispatch_sources: list[tuple[Path, str]] = []

    for agent_dir in agent_dirs:
        agent_id = agent_dir.name
        known_agents.add(agent_id)
        session_path = agent_dir / "session.json"
        data, parse_error = (
            _read_json(session_path)
            if session_path.is_symlink() or session_path.exists()
            else (None, "missing-session")
        )
        source = _relative(project_root, session_path if session_path.exists() else agent_dir)
        role = _text(data.get("role")) if data else None
        rows["agents"].append((agent_id, role, source, None))
        session_id = _text(data.get("sessionId"), 256) if data else None
        if not session_id and session_path.exists():
            session_id = _hash_id("unknown-session", source)
        if session_id:
            if session_id in session_owner:
                session_id = _hash_id("legacy-session", f"{agent_id}/{source}")
                parse_error = parse_error or "duplicate-session-id"
            error_code, error_summary = _error_fields(data, parse_error)
            rows["sessions"].append((
                session_id, agent_id, role, _text(data.get("status")) if data else "unknown",
                _text(data.get("codexIdentity")) if data else None, source,
                _text(data.get("createdAt")) if data else None,
                _text(data.get("updatedAt")) if data else None, None,
                error_code, error_summary,
            ))
            session_owner[session_id] = agent_id

        runs_root = agent_dir / "runs"
        run_dirs = [path for path in _bounded_children(runs_root, MAX_RUNS, "run") if path.is_dir()]
        if len(rows["runs"]) + len(run_dirs) > MAX_RUNS:
            raise CatalogError(f"run scan exceeds the limit of {MAX_RUNS} entries")
        for run_dir in run_dirs:
            state_path = run_dir / "state.json"
            run_data, run_error = (
                _read_json(state_path)
                if state_path.is_symlink() or state_path.exists()
                else (None, "missing-state")
            )
            source_path = _relative(project_root, state_path if state_path.exists() else run_dir)
            run_id = _text(run_data.get("runId"), 256) if run_data else None
            run_id = run_id or run_dir.name
            if run_id in run_owner:
                ambiguous_run_ids.add(run_id)
                run_id = _hash_id("legacy-run", f"{agent_id}/{source_path}")
                run_error = run_error or "duplicate-run-id"
            run_owner[run_id] = agent_id
            run_session = _text(run_data.get("sessionId"), 256) if run_data else None
            if run_session and session_owner.get(run_session) != agent_id:
                run_session = None
            error_code, error_summary = _error_fields(run_data, run_error)
            rows["runs"].append((
                run_id, agent_id, run_session,
                _text(run_data.get("role")) if run_data else role,
                _text(run_data.get("actor")) if run_data else None,
                _text(run_data.get("status")) if run_data else "unknown",
                _sha256(run_data.get("requestHash")) if run_data else None,
                source_path,
                _text(run_data.get("acceptedAt")) if run_data else None,
                _text(run_data.get("startedAt")) if run_data else None,
                _text(run_data.get("finishedAt")) if run_data else None,
                _text(run_data.get("updatedAt")) if run_data else None,
                None, error_code, error_summary,
            ))
            verified = _text(run_data.get("verifiedWorkRunId"), 256) if run_data else None
            if verified:
                rows["relationships"].append((verified, run_id, "verification-of", source_path, None))

        for loop_dir in _bounded_children(agent_dir / "loops", MAX_LOOPS, "loop"):
            if loop_dir.is_dir():
                loop_sources.append((loop_dir / "state.json", agent_id))
        for dispatch_path in _bounded_children(agent_dir / "dispatches", MAX_DISPATCHES, "dispatch"):
            if dispatch_path.is_file() and dispatch_path.suffix == ".json":
                dispatch_sources.append((dispatch_path, agent_id))

    for state_path, owner_agent_id in sorted(loop_sources, key=lambda item: str(item[0])):
        data, parse_error = _read_json(state_path)
        source = _relative(project_root, state_path)
        loop_id = _text(data.get("loopId"), 256) if data else None
        loop_id = loop_id or state_path.parent.name
        work_agent = _text(data.get("workAgentId"), 256) if data else None
        verification_agent = _text(data.get("verificationAgentId"), 256) if data else None
        if work_agent and work_agent == verification_agent:
            verification_agent = None
            parse_error = parse_error or "malformed-loop-agents"
        for referenced in (work_agent, verification_agent):
            if referenced and referenced not in known_agents:
                rows["agents"].append((referenced, None, source, None))
                known_agents.add(referenced)
        latest_work = _text(data.get("latestWorkRunId"), 256) if data else None
        latest_verification = _text(data.get("latestVerificationRunId"), 256) if data else None
        if latest_work and (
            latest_work in ambiguous_run_ids or run_owner.get(latest_work) != work_agent
        ):
            latest_work = None
        if latest_verification and (
            latest_verification in ambiguous_run_ids
            or run_owner.get(latest_verification) != verification_agent
        ):
            latest_verification = None
        terminal = data.get("terminalReason") if data else None
        terminal = terminal if isinstance(terminal, dict) else {}
        error_code, error_summary = _error_fields(data, parse_error)
        rows["loops"].append((
            loop_id, work_agent, verification_agent,
            _text(data.get("status")) if data else "unknown",
            _text(data.get("phase")) if data else None,
            _sha256(data.get("originalRequestHash")) if data else None,
            _text(data.get("originalRequestPath")) if data else None,
            latest_work, latest_verification,
            _text(data.get("lastVerificationDecision")) if data else None,
            _text(terminal.get("code"), 128),
            "Authoritative source reports a terminal reason." if terminal else None,
            source,
            _text(data.get("createdAt")) if data else None,
            _text(data.get("updatedAt")) if data else None,
            None, error_code, error_summary,
        ))
        explicit_runs = [(latest_work, "work", 0), (latest_verification, "verification", 1)]
        for run_id, graph_role, sequence in explicit_runs:
            if run_id:
                rows["loop_runs"].append((loop_id, run_id, sequence, graph_role, "latest", None))

    if len(dispatch_sources) > MAX_DISPATCHES:
        raise CatalogError(f"dispatch scan exceeds the limit of {MAX_DISPATCHES} entries")
    for dispatch_path, _owner in sorted(dispatch_sources, key=lambda item: str(item[0])):
        data, parse_error = _read_json(dispatch_path)
        source = _relative(project_root, dispatch_path)
        dispatch_id = _text(data.get("dispatchId"), 256) if data else None
        dispatch_id = dispatch_id or dispatch_path.stem
        dispatch_tuple = data.get("dispatchTuple") if data else None
        dispatch_tuple = dispatch_tuple if isinstance(dispatch_tuple, dict) else {}
        target_agent = _text(dispatch_tuple.get("agentId"), 256)
        target_run = None
        source_run = _text(dispatch_tuple.get("verifiedWorkRunId"), 256)
        rows["dispatches"].append((
            dispatch_id, None,
            source_run if source_run in run_owner and source_run not in ambiguous_run_ids else None,
            target_run,
            _text(dispatch_tuple.get("operation")), _text(dispatch_tuple.get("role")),
            "malformed" if parse_error else _text(data.get("kind")) or "reserved",
            _sha256(dispatch_tuple.get("requestHash")), source,
            None, None, None,
            parse_error, "Source metadata could not be safely parsed." if parse_error else None,
        ))

    for key in rows:
        rows[key].sort(key=lambda row: tuple("" if item is None else str(item) for item in row))
    rows["ambiguous_run_ids"] = [(value,) for value in sorted(ambiguous_run_ids)]
    return rows


def _agent_search_rows(rows: dict[str, list[tuple[Any, ...]]]) -> list[tuple[Any, ...]]:
    projected: list[tuple[Any, ...]] = []

    def add(
        kind: str, entity_id: Any, agent_id: Any, role: Any, status: Any,
        error_summary: Any, timestamp: Any, source_path: Any,
    ) -> None:
        identity = str(entity_id)
        source = str(source_path)
        projected.append((
            _hash_id("agent-search", f"{kind}:{identity}:{source}"), kind,
            identity, agent_id, role, status, error_summary, timestamp, source,
        ))

    for row in rows["agents"]:
        add("agent", row[0], row[0], row[1], None, None, row[3], row[2])
    for row in rows["sessions"]:
        add("session", row[0], row[1], row[2], row[3], row[10], row[7] or row[6], row[5])
    for row in rows["runs"]:
        add("run", row[0], row[1], row[3], row[5], row[14], row[12] or row[11] or row[10] or row[9] or row[8], row[7])
    for row in rows["loops"]:
        add("loop", row[0], row[1], "work-verification-loop", row[3], row[17], row[14] or row[13], row[12])
    for row in rows["dispatches"]:
        add("dispatch", row[0], None, row[5], row[6], row[13], row[10] or row[9], row[8])
    projected.sort(key=lambda row: tuple("" if value is None else str(value) for value in row))
    return projected


def _walk_files(root: Path) -> Iterable[Path]:
    count = 0
    stack = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if depth > MAX_DOCUMENT_DEPTH:
            raise CatalogError(f"Document scan exceeds maximum depth {MAX_DOCUMENT_DEPTH}: {directory}")
        entries = _bounded_children(directory, MAX_DOCUMENT_FILES, "Document")
        for entry in reversed(entries):
            if entry.is_dir():
                if entry.name.startswith("."):
                    continue
                stack.append((entry, depth + 1))
            elif entry.is_file():
                count += 1
                if count > MAX_DOCUMENT_FILES:
                    raise CatalogError(f"Document scan exceeds the limit of {MAX_DOCUMENT_FILES} files")
                yield entry


def _file_hash(path: Path) -> tuple[str | None, str]:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                return None, "inaccessible"
            if metadata.st_size > MAX_HASH_BYTES:
                return None, "available-unhashed-large"
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb") as source:
                descriptor = -1
                for chunk in iter(lambda: source.read(128 * 1024), b""):
                    digest.update(chunk)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return digest.hexdigest(), "available"
    except OSError:
        return None, "inaccessible"


def _search_text(path: Path, remaining: int) -> tuple[str, str, int | None, int, int, str | None]:
    if path.suffix.lower() not in SEARCHABLE_MEDIA_TYPES:
        return "excluded-format", "", path.stat().st_size, 0, 0, None
    if remaining <= 0:
        return "excluded-total-limit", "", path.stat().st_size, 0, 0, "total-text-limit"
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                return "inaccessible", "", None, 0, 0, "unsafe-source"
            source_bytes = metadata.st_size
            maximum = min(MAX_SEARCH_TEXT_BYTES, remaining)
            with os.fdopen(descriptor, "rb") as source:
                descriptor = -1
                content = source.read(maximum + 1)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except OSError:
        return "inaccessible", "", None, 0, 0, "read-error"
    if b"\0" in content:
        return "excluded-binary", "", source_bytes, 0, 0, "binary-content"
    indexed = content[:maximum]
    try:
        text_value = indexed.decode("utf-8")
    except UnicodeDecodeError as exc:
        if source_bytes > len(indexed) and exc.start >= max(0, len(indexed) - 3):
            indexed = indexed[:exc.start]
            text_value = indexed.decode("utf-8")
        else:
            return "invalid-utf8", "", source_bytes, 0, 0, "invalid-utf8"
    truncated = source_bytes > len(indexed)
    return (
        "truncated" if truncated else "indexed", text_value, source_bytes,
        len(indexed), 1 if truncated else 0, "per-file-limit" if truncated else None,
    )


def _document_rows(project_root: Path) -> dict[str, list[tuple[Any, ...]]]:
    rows: dict[str, list[tuple[Any, ...]]] = {
        "documents": [], "representations": [], "pairs": [], "search": [],
    }
    indexed_total = 0

    def add_search(
        path: Path, document_id: str, representation_id: str,
        document_type: str, representation_kind: str, title: str,
        source: str, media_type: str | None,
    ) -> None:
        nonlocal indexed_total
        status, body, source_bytes, indexed_bytes, truncated, error_code = _search_text(
            path, MAX_SEARCH_TOTAL_BYTES - indexed_total
        )
        indexed_total += indexed_bytes
        rows["search"].append((
            _hash_id("document-search", source), document_id, representation_id,
            document_type, representation_kind, title, source, media_type,
            status, source_bytes, indexed_bytes, truncated, error_code, body,
        ))
    document_root = _safe_path(project_root, DOCUMENT_RELATIVE_PATH, "Document")
    if not document_root.exists():
        return rows
    roots = (("original", document_root / "original"), ("processed", document_root / "processed"))
    for document_type, root in roots:
        if not root.exists():
            continue
        packages = _bounded_children(root, MAX_DOCUMENT_FILES, f"{document_type} Document")
        for package in packages:
            if not package.is_dir():
                raise CatalogError(
                    f"{document_type} Document roots accept only package directories: {package}"
                )
            package_source = _relative(project_root, package)
            document_id = f"{document_type}-{package.name}"
            is_legacy = (
                document_type == "processed"
                and package.name.startswith("legacy-inquery-")
            )
            status = "legacy-historical" if is_legacy else None
            rows["documents"].append((
                document_id, document_type, package.name, status, "local",
                package_source, None, None, None, None, None,
            ))
            for path in sorted(
                _walk_files(package), key=lambda item: _relative(project_root, item)
            ):
                source = _relative(project_root, path)
                content_hash, availability = _file_hash(path)
                if is_legacy:
                    kind = "legacy"
                elif document_type == "processed" and path.suffix.lower() == ".md":
                    kind = "processed-markdown"
                elif document_type == "original":
                    kind = "source-native"
                else:
                    kind = "other"
                representation_id = _hash_id("representation", source)
                media_type = (
                    "text/markdown" if path.suffix.lower() == ".md" else None
                )
                rows["representations"].append((
                    representation_id, document_id, kind, "local", source,
                    media_type, content_hash, availability, None, None, None,
                    None, None,
                ))
                add_search(
                    path, document_id, representation_id, document_type, kind,
                    package.name, source,
                    media_type or SEARCHABLE_MEDIA_TYPES.get(path.suffix.lower()),
                )

    specification_root = document_root / "specification"
    if specification_root.exists():
        specification_directories = _bounded_children(
            specification_root, MAX_DOCUMENT_FILES, "Specification"
        )
        for path in specification_directories:
            if not path.is_dir():
                raise CatalogError(
                    f"Specification roots accept only package directories: {path}"
                )
        binding_entry_counts: dict[str, int] = {}
        for candidate in specification_directories:
            metadata, _ = _specification_html_metadata(candidate / "index.html")
            locator = metadata.get("agent-factory:ai-binding-entry")
            if locator:
                binding_entry_counts[locator] = binding_entry_counts.get(locator, 0) + 1
        for spec_dir in specification_directories:
            spec_source = _relative(project_root, spec_dir)
            document_id = f"specification-{spec_dir.name}"
            rows["documents"].append((document_id, "specification", spec_dir.name, None, "local", spec_source, None, None, None, None, None))
            human_id = None
            human_path = spec_dir / "index.html"
            binding_error: str | None = None
            for path in sorted(_walk_files(spec_dir), key=lambda item: _relative(project_root, item)):
                source = _relative(project_root, path)
                representation_id = _hash_id("representation", source)
                if path.name == "index.html":
                    human_id = representation_id
                    kind, media_type = "human-html", "text/html"
                else:
                    kind, media_type = "other", None
                content_hash, availability = _file_hash(path)
                rows["representations"].append((representation_id, document_id, kind, "local", source, media_type, content_hash, availability, None, None, None, None, None))
                add_search(path, document_id, representation_id, "specification", kind, spec_dir.name, source, media_type or SEARCHABLE_MEDIA_TYPES.get(path.suffix.lower()))
            ai_id = None
            pair_status: str | None = None
            evidence_path = _relative(project_root, human_path) if human_id else spec_source
            error_summary: str | None = None
            if human_id:
                human_metadata, binding_error = _specification_html_metadata(human_path)
                ai_entry, locator_error = _binding_path(
                    project_root,
                    human_metadata.get("agent-factory:ai-binding-entry"),
                    "Specification AI binding entry",
                )
                ai_root, root_error = _binding_path(
                    project_root,
                    human_metadata.get("agent-factory:ai-root"),
                    "Specification AI root",
                )
                binding_error = binding_error or locator_error or root_error
                if ai_entry is not None and ai_entry.is_file() and not ai_entry.is_symlink():
                    source = _relative(project_root, ai_entry)
                    ai_id = _hash_id("representation", source)
                    content_hash, availability = _file_hash(ai_entry)
                    rows["representations"].append((ai_id, document_id, "ai-skill", "local", source, "text/markdown", content_hash, availability, None, None, None, None, None))
                    add_search(ai_entry, document_id, ai_id, "specification", "ai-skill", spec_dir.name, source, "text/markdown")
                    skill_metadata, skill_error = _skill_binding_metadata(ai_entry)
                    binding_error = binding_error or skill_error
                    expected_human = _relative(project_root, human_path)
                    human_specification_id = human_metadata.get("agent-factory:specification-id")
                    human_ai_root = human_metadata.get("agent-factory:ai-root")
                    reciprocal = (
                        human_specification_id == spec_dir.name
                        and skill_metadata.get("specification-id") == human_specification_id
                        and skill_metadata.get("human-entry") == expected_human
                        and skill_metadata.get("ai-root") == human_ai_root
                        and ai_root is not None
                        and ai_root.is_dir()
                        and _within(ai_root.resolve(strict=True), ai_entry.resolve(strict=True))
                        and binding_entry_counts.get(source) == 1
                    )
                    if reciprocal and binding_error is None:
                        pair_status = "unknown"
                        binding_error = "semantic-alignment-unverified"
                        error_summary = (
                            "Reciprocal identity and locators match; semantic alignment "
                            "has not been independently established."
                        )
                    else:
                        pair_status = "misaligned"
                        binding_error = binding_error or "reciprocal-binding-mismatch"
                        error_summary = "Specification binding metadata is not reciprocal."
                else:
                    pair_status = "missing-ai"
                    binding_error = binding_error or "missing-ai-binding-entry"
                    error_summary = "The declared AI binding entry is unavailable."
            if human_id or ai_id:
                pair_status = pair_status or ("missing-ai" if human_id else "missing-human")
                rows["pairs"].append((document_id, human_id, ai_id, pair_status, evidence_path, None, None, binding_error, error_summary))

    represented_ai_sources = {
        row[4] for row in rows["representations"] if row[2] == "ai-skill"
    }
    known_document_ids = {row[0] for row in rows["documents"]}
    for skill_root_relative in (Path("skills"), Path(".codex/skills")):
        skill_root = _safe_path(project_root, skill_root_relative, "Skill root")
        if not skill_root.exists():
            continue
        for skill_dir in _bounded_children(skill_root, MAX_DOCUMENT_FILES, "Skill"):
            if not skill_dir.is_dir():
                continue
            skill_entry = skill_dir / "SKILL.md"
            if not skill_entry.is_file() or skill_entry.is_symlink():
                continue
            source = _relative(project_root, skill_entry)
            if source in represented_ai_sources:
                continue
            metadata, metadata_error = _skill_binding_metadata(skill_entry)
            if metadata_error is not None:
                continue
            specification_id = metadata["specification-id"]
            declared_ai_root = metadata["ai-root"].rstrip("/")
            actual_ai_root = _relative(project_root, skill_dir)
            human_entry, human_error = _binding_path(
                project_root, metadata.get("human-entry"), "Specification Human entry"
            )
            if (
                not specification_id
                or declared_ai_root != actual_ai_root
                or human_entry is None
                or human_error is not None
                or human_entry.is_file()
            ):
                continue
            document_id = f"specification-{specification_id}"
            if document_id in known_document_ids:
                continue
            human_source = _relative(project_root, human_entry.parent)
            rows["documents"].append((document_id, "specification", specification_id, None, "local", human_source, None, None, None, "missing-human-entry", "The declared Human Specification entry is unavailable."))
            ai_id = _hash_id("representation", source)
            content_hash, availability = _file_hash(skill_entry)
            rows["representations"].append((ai_id, document_id, "ai-skill", "local", source, "text/markdown", content_hash, availability, None, None, None, None, None))
            add_search(skill_entry, document_id, ai_id, "specification", "ai-skill", specification_id, source, "text/markdown")
            rows["pairs"].append((document_id, None, ai_id, "missing-human", source, None, None, "missing-human-entry", "The declared Human Specification entry is unavailable."))
            represented_ai_sources.add(source)
            known_document_ids.add(document_id)

    for key in rows:
        rows[key].sort(key=lambda row: tuple("" if item is None else str(item) for item in row))
    return rows


def _populate(connection: sqlite3.Connection, project_root: Path) -> None:
    agents = _agent_rows(project_root)
    agent_search = _agent_search_rows(agents)
    documents = _document_rows(project_root)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.executemany("INSERT INTO agents VALUES (?, ?, ?, ?)", agents["agents"])
        connection.executemany("INSERT INTO agent_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", agents["sessions"])
        connection.executemany("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", agents["runs"])
        ambiguous_run_ids = {row[0] for row in agents.pop("ambiguous_run_ids")}
        valid_relationships = [
            row
            for row in agents["relationships"]
            if row[0] in {run[0] for run in agents["runs"]}
            and row[0] not in ambiguous_run_ids
            and row[0] != row[1]
        ]
        connection.executemany("INSERT INTO run_relationships VALUES (?, ?, ?, ?, ?)", valid_relationships)
        connection.executemany("INSERT INTO work_verification_loops VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", agents["loops"])
        connection.executemany("INSERT INTO loop_runs VALUES (?, ?, ?, ?, ?, ?)", agents["loop_runs"])
        connection.executemany("INSERT INTO dispatches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", agents["dispatches"])
        connection.executemany("INSERT INTO agent_search_entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", agent_search)
        connection.executemany(
            "INSERT INTO agent_search_fts VALUES (?, ?, ?, ?, ?, ?, ?)",
            ((row[0], row[2], row[4], row[5], row[6], row[7], row[8]) for row in agent_search),
        )
        connection.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", documents["documents"])
        connection.executemany("INSERT INTO document_representations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", documents["representations"])
        connection.executemany(
            "INSERT INTO document_search_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (row[:13] for row in documents["search"]),
        )
        connection.executemany(
            "INSERT INTO document_search_fts VALUES (?, ?, ?, ?)",
            ((row[0], row[5], row[6], row[13]) for row in documents["search"]),
        )
        connection.executemany(
            "INSERT INTO specification_pair_status (document_id, human_representation_id, ai_representation_id, pair_status, evidence_path, checked_at, observed_at, error_code, error_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            documents["pairs"],
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _validate_target(project_root: Path) -> Path:
    catalog_path = _safe_path(project_root, CATALOG_RELATIVE_PATH, "catalog")
    for suffix in ("", *SIDECAR_SUFFIXES):
        candidate = Path(f"{catalog_path}{suffix}")
        if candidate.is_symlink():
            raise CatalogError(f"catalog artifact must not be a symbolic link: {candidate}")
    if catalog_path.exists() and not catalog_path.is_file():
        raise CatalogError(f"catalog path is not a regular file: {catalog_path}")
    return catalog_path


def _schema_text() -> str:
    if SCHEMA_PATH.is_symlink() or not SCHEMA_PATH.is_file():
        raise CatalogError(f"maintained catalog DDL is unavailable: {SCHEMA_PATH}")
    return SCHEMA_PATH.read_text(encoding="utf-8")


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_database(temporary_path: Path, catalog_path: Path) -> None:
    """Publish durably or restore the exact prior catalog before failing."""
    backup_path: Path | None = None
    prior_exists = catalog_path.exists()
    if prior_exists:
        descriptor, name = tempfile.mkstemp(
            prefix=".db.sqlite.last-good-", dir=catalog_path.parent
        )
        backup_path = Path(name)
        try:
            source_descriptor = os.open(
                catalog_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            try:
                metadata = os.fstat(source_descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise CatalogError("existing catalog is not a regular file")
                with os.fdopen(source_descriptor, "rb") as source, os.fdopen(
                    descriptor, "wb"
                ) as backup:
                    source_descriptor = -1
                    descriptor = -1
                    for chunk in iter(lambda: source.read(128 * 1024), b""):
                        backup.write(chunk)
                    backup.flush()
                    os.fsync(backup.fileno())
            finally:
                if source_descriptor >= 0:
                    os.close(source_descriptor)
                if descriptor >= 0:
                    os.close(descriptor)
            os.chmod(backup_path, 0o600)
            _fsync_directory(catalog_path.parent)
        except (OSError, CatalogError):
            if descriptor >= 0:
                os.close(descriptor)
            backup_path.unlink(missing_ok=True)
            raise

    published = False
    try:
        os.replace(temporary_path, catalog_path)
        published = True
        try:
            _fsync_directory(catalog_path.parent)
        except OSError as publication_error:
            try:
                if backup_path is not None:
                    os.replace(backup_path, catalog_path)
                    backup_path = None
                else:
                    catalog_path.unlink(missing_ok=True)
                _fsync_directory(catalog_path.parent)
            except OSError as recovery_error:
                raise CatalogError(
                    "catalog publication durability failed and prior-state "
                    f"recovery could not be confirmed: {recovery_error}"
                ) from publication_error
            raise publication_error
    finally:
        if backup_path is not None:
            try:
                backup_path.unlink(missing_ok=True)
                if published:
                    _fsync_directory(catalog_path.parent)
            except OSError:
                # Publication is already durable; backup cleanup is best-effort
                # and must not turn a successful replacement into a false failure.
                pass


def _build_database(project_root: Path, populate: bool) -> tuple[Path, dict[str, int]]:
    catalog_path = _validate_target(project_root)
    active_sidecars = [
        Path(f"{catalog_path}{suffix}")
        for suffix in SIDECAR_SUFFIXES
        if Path(f"{catalog_path}{suffix}").exists()
    ]
    if active_sidecars:
        rendered = ", ".join(path.name for path in active_sidecars)
        raise CatalogError(
            "refusing to replace a catalog with SQLite sidecars present; "
            f"close catalog users and inspect or checkpoint these files first: {rendered}"
        )
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    _safe_path(project_root, Path(".agent-factory"), "local adapter")
    temporary_path: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(prefix=".db.sqlite.rebuild-", dir=catalog_path.parent)
        os.close(descriptor)
        temporary_path = Path(name)
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.executescript(_schema_text())
            if populate:
                _populate(connection, project_root)
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok" or foreign_keys:
                raise CatalogError("rebuilt catalog failed SQLite integrity checks")
            counts = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("agents", "agent_sessions", "runs", "work_verification_loops", "dispatches", "documents", "document_representations", "agent_search_entities", "document_search_entries", "agent_search_fts", "document_search_fts")
            }
            connection.commit()
        finally:
            connection.close()
        for suffix in SIDECAR_SUFFIXES:
            Path(f"{temporary_path}{suffix}").unlink(missing_ok=True)
        with temporary_path.open("rb") as source:
            os.fsync(source.fileno())
        os.chmod(temporary_path, 0o600)
        _publish_database(temporary_path, catalog_path)
        temporary_path = None
        return catalog_path, counts
    except (OSError, sqlite3.Error) as exc:
        raise CatalogError(f"catalog build failed: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        for suffix in SIDECAR_SUFFIXES:
            temp_sidecar = Path(f"{temporary_path}{suffix}") if temporary_path else None
            if temp_sidecar:
                temp_sidecar.unlink(missing_ok=True)


def _existing_catalog_version(catalog_path: Path) -> int:
    """Read and validate only the version marker needed to route initialization."""
    try:
        connection = sqlite3.connect(
            f"file:{catalog_path.as_posix()}?mode=ro&immutable=1", uri=True
        )
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise CatalogError("existing catalog failed SQLite integrity checks")
            rows = connection.execute(
                "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CatalogError(f"existing catalog schema version is unavailable: {exc}") from exc

    if len(rows) != 1:
        raise CatalogError("existing catalog schema version is missing or ambiguous")
    raw_version = rows[0][0]
    if not isinstance(raw_version, str) or not raw_version.isascii() or not raw_version.isdigit():
        raise CatalogError("existing catalog schema version is unparseable")
    version = int(raw_version)
    if str(version) != raw_version:
        raise CatalogError("existing catalog schema version is unparseable")
    return version


def initialize_catalog(project_root: Path) -> tuple[Path, dict[str, Any]]:
    catalog_path = _validate_target(project_root)
    if catalog_path.exists():
        source_version = _existing_catalog_version(catalog_path)
        if source_version == CURRENT_SCHEMA_VERSION:
            return catalog_path, {
                "outcome": "unchanged",
                "created": False,
                "migrated": False,
                "sourceSchemaVersion": str(source_version),
                "targetSchemaVersion": str(CURRENT_SCHEMA_VERSION),
            }
        if source_version not in SUPPORTED_REBUILD_MIGRATION_VERSIONS:
            relationship = "future" if source_version > CURRENT_SCHEMA_VERSION else "unsupported"
            raise CatalogError(
                f"existing catalog schema version {source_version} is {relationship}; "
                f"automatic rebuild migration supports only versions "
                f"{sorted(SUPPORTED_REBUILD_MIGRATION_VERSIONS)} to "
                f"{CURRENT_SCHEMA_VERSION}"
            )
        path, counts = _build_database(project_root, populate=True)
        return path, {
            "outcome": "migrated",
            "created": False,
            "migrated": True,
            "sourceSchemaVersion": str(source_version),
            "targetSchemaVersion": str(CURRENT_SCHEMA_VERSION),
            "counts": counts,
        }
    path, counts = _build_database(project_root, populate=False)
    return path, {
        "outcome": "created",
        "created": True,
        "migrated": False,
        "sourceSchemaVersion": None,
        "targetSchemaVersion": str(CURRENT_SCHEMA_VERSION),
        "counts": counts,
    }


def rebuild_catalog(project_root: Path) -> tuple[Path, dict[str, int]]:
    return _build_database(project_root, populate=True)


def catalog_status(project_root: Path) -> dict[str, Any]:
    catalog_path = _validate_target(project_root)
    if not catalog_path.exists():
        return {
            "path": _relative(project_root, catalog_path), "exists": False,
            "integrity": "missing", "sidecars": [],
            "search": {"engine": "sqlite-fts5", "available": False},
        }
    sidecars = [suffix for suffix in SIDECAR_SUFFIXES if Path(f"{catalog_path}{suffix}").exists()]
    try:
        uri = f"file:{catalog_path.as_posix()}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            schema_version = connection.execute("SELECT value FROM schema_metadata WHERE key = 'schema_version'").fetchone()[0]
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema WHERE type IN ('table', 'view')"
                )
            }
            count_tables = (
                "agents", "agent_sessions", "runs", "work_verification_loops",
                "dispatches", "documents", "document_representations",
                "agent_search_entities", "document_search_entries",
                "agent_search_fts", "document_search_fts",
            )
            counts = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in count_tables if table in existing_tables
            }
            search_tables = {
                "agent_search_entities", "document_search_entries",
                "agent_search_fts", "document_search_fts",
            }
            search_capability = {
                "engine": "sqlite-fts5",
                "available": search_tables <= existing_tables,
                "agentEntities": counts.get("agent_search_entities", 0),
                "agentEntityKinds": dict(connection.execute(
                    "SELECT entity_kind, count(*) FROM agent_search_entities "
                    "GROUP BY entity_kind ORDER BY entity_kind"
                ).fetchall()) if "agent_search_entities" in existing_tables else {},
                "documentEntries": counts.get("document_search_entries", 0),
                "documentIndexStates": dict(connection.execute(
                    "SELECT index_status, count(*) FROM document_search_entries "
                    "GROUP BY index_status ORDER BY index_status"
                ).fetchall()) if "document_search_entries" in existing_tables else {},
                "searchableDocumentEntries": counts.get("document_search_fts", 0),
                "indexedTextEntries": connection.execute(
                    "SELECT count(*) FROM document_search_entries "
                    "WHERE index_status IN ('indexed', 'truncated')"
                ).fetchone()[0] if "document_search_entries" in existing_tables else 0,
            }
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise CatalogError(f"catalog inspection failed: {exc}") from exc
    return {"path": _relative(project_root, catalog_path), "exists": True, "integrity": integrity, "schemaVersion": schema_version, "sidecars": sidecars, "counts": counts, "search": search_capability}


def _search_connection(project_root: Path) -> sqlite3.Connection:
    catalog_path = _validate_target(project_root)
    if not catalog_path.exists():
        raise CatalogError("catalog is missing; initialize or rebuild it before searching")
    try:
        connection = sqlite3.connect(f"file:{catalog_path.as_posix()}?mode=ro&immutable=1", uri=True)
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE name IN "
                "('agent_search_entities', 'agent_search_fts', "
                "'document_search_entries', 'document_search_fts')"
            )
        }
        if len(names) != 4:
            connection.close()
            raise CatalogError("catalog search schema is unavailable; rebuild with schema version 3")
        return connection
    except sqlite3.Error as exc:
        raise CatalogError(f"catalog search open failed: {exc}") from exc


def _validated_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_SEARCH_RESULTS:
        raise CatalogError(f"result limit must be between 1 and {MAX_SEARCH_RESULTS}")
    return limit


def _literal_fts_query(query: str) -> str:
    """Return one quoted FTS5 phrase with a generated final-token prefix."""
    if not isinstance(query, str):
        raise CatalogError("search query must be text")
    literal = query.strip()
    if not literal:
        raise CatalogError("search query must not be empty")
    if "\x00" in literal:
        raise CatalogError("search query must not contain NUL")
    try:
        encoded = literal.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CatalogError("search query must be valid Unicode text") from exc
    if len(encoded) > MAX_SEARCH_QUERY_BYTES:
        raise CatalogError(
            f"search query must not exceed {MAX_SEARCH_QUERY_BYTES} UTF-8 bytes"
        )
    return '"' + literal.replace('"', '""') + '"*'


def search_agents(project_root: Path, query: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = _validated_limit(limit)
    match_query = _literal_fts_query(query)
    connection = _search_connection(project_root)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT e.entity_kind, e.entity_id, e.agent_id, e.role, e.status, "
            "e.error_summary, e.timestamp, e.source_path, bm25(agent_search_fts) AS rank "
            "FROM agent_search_fts JOIN agent_search_entities AS e "
            "ON e.search_entity_id = agent_search_fts.search_entity_id "
            "WHERE agent_search_fts MATCH ? "
            "ORDER BY rank, e.source_path, e.search_entity_id LIMIT ?",
            (match_query, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise CatalogError(f"Agent search failed: {exc}") from exc
    finally:
        connection.close()


def search_documents(project_root: Path, query: str, limit: int = 20) -> list[dict[str, Any]]:
    limit = _validated_limit(limit)
    match_query = _literal_fts_query(query)
    connection = _search_connection(project_root)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT e.document_id, e.representation_id, e.document_type, "
            "e.representation_kind, e.title, e.source_path, e.media_type, "
            "e.index_status, e.source_bytes, e.indexed_bytes, e.truncated, "
            "e.error_code, bm25(document_search_fts) AS rank "
            "FROM document_search_fts JOIN document_search_entries AS e "
            "ON e.search_entry_id = document_search_fts.search_entry_id "
            "WHERE document_search_fts MATCH ? "
            "ORDER BY rank, e.source_path, e.search_entry_id LIMIT ?",
            (match_query, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise CatalogError(f"Document search failed: {exc}") from exc
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Agent Factory local SQLite catalog.")
    parser.add_argument("--project-root", help="exact Git project root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "rebuild", "status"):
        subparsers.add_parser(command)
    for command in ("search-agents", "search-documents"):
        search_parser = subparsers.add_parser(command)
        search_parser.add_argument("query")
        search_parser.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project_root = resolve_project_root(args.project_root)
        if args.command == "init":
            path, result = initialize_catalog(project_root)
            payload = {"operation": "init", "path": _relative(project_root, path), **result}
        elif args.command == "rebuild":
            path, counts = rebuild_catalog(project_root)
            payload = {"operation": "rebuild", "path": _relative(project_root, path), "counts": counts}
        elif args.command == "status":
            payload = catalog_status(project_root)
        elif args.command == "search-agents":
            payload = {"operation": args.command, "query": args.query, "results": search_agents(project_root, args.query, args.limit)}
        else:
            payload = {"operation": args.command, "query": args.query, "results": search_documents(project_root, args.query, args.limit)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
