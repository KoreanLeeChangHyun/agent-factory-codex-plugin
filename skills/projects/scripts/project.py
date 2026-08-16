#!/usr/bin/env python3
"""Initialize and append to a target repository's AI-facing Project Skill."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Iterator
from uuid import uuid4


RELATIVE_SKILL = Path(".agent-factory/skills/project")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
RECEIPT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
MAX_LEDGER_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 64 * 1024


def write_all(descriptor: int, content: bytes, label: str) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written == 0:
            raise OSError(f"write made no progress: {label}")
        offset += written


def project_directory(project_root: str) -> tuple[Path, int]:
    try:
        root = Path(project_root).resolve(strict=True)
    except OSError as error:
        raise SystemExit(f"Project root does not exist: {project_root}: {error}") from error
    if not root.is_dir():
        raise SystemExit(f"Project root does not exist: {root}")
    try:
        descriptor = os.open(root, DIRECTORY_FLAGS)
    except OSError as error:
        raise SystemExit(f"Cannot open project root safely: {root}: {error}") from error
    return root, descriptor


def open_directory(parent: int, name: str, *, create: bool = False) -> int:
    if create:
        try:
            os.mkdir(name, mode=0o755, dir_fd=parent)
        except FileExistsError:
            pass
    try:
        return os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    except OSError as error:
        raise SystemExit(f"Project Skill path component is not a safe directory: {name}: {error}") from error


@contextmanager
def skill_directory(project_root: str, *, create: bool = False) -> Iterator[tuple[Path, int]]:
    root, descriptor = project_directory(project_root)
    try:
        for part in RELATIVE_SKILL.parts:
            next_descriptor = open_directory(descriptor, part, create=create)
            os.close(descriptor)
            descriptor = next_descriptor
        yield root / RELATIVE_SKILL, descriptor
    finally:
        os.close(descriptor)


def create_file(directory: int, name: str, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, 0o644, dir_fd=directory)
    except FileExistsError:
        try:
            existing = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except OSError as error:
            raise SystemExit(f"Cannot inspect existing Project Skill file: {name}: {error}") from error
        if not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1:
            raise SystemExit(f"Project Skill file is not a regular file: {name}")
        return
    except OSError as error:
        raise SystemExit(f"Cannot create Project Skill file safely: {name}: {error}") from error
    try:
        encoded = content.encode("utf-8")
        write_all(descriptor, encoded, name)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def markdown_inline(value: str) -> str:
    """Keep one CLI value inside one Markdown line without structural injection."""
    compact = " ".join(value.split())
    escaped = compact.replace("\\", "\\\\")
    for character in "`*_{}[]<>#|":
        escaped = escaped.replace(character, f"\\{character}")
    return escaped or "unspecified"


def append_entry(
    skill_path: Path,
    skill: int,
    relative_path: tuple[str, str],
    heading: str,
    lines: list[str],
    receipt: str | None,
    disposition: str,
) -> str:
    if receipt is not None and RECEIPT_PATTERN.fullmatch(receipt) is None:
        raise SystemExit("Receipt must contain 1-128 letters, numbers, '.', '_', ':', or '-'")
    record_id = receipt or f"project-{uuid4().hex}"
    lock_root = Path(tempfile.gettempdir())
    lock_name = (
        "agent-factory-project-"
        + hashlib.sha256(os.fsencode(skill_path)).hexdigest()
        + ".lock"
    )
    lock_flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    try:
        lock_directory = os.open(lock_root, DIRECTORY_FLAGS)
        try:
            lock = os.open(lock_name, lock_flags, 0o600, dir_fd=lock_directory)
        finally:
            os.close(lock_directory)
    except OSError as error:
        raise SystemExit(f"Cannot open Project Skill recording lock safely: {error}") from error
    try:
        lock_metadata = os.fstat(lock)
        if (
            not stat.S_ISREG(lock_metadata.st_mode)
            or lock_metadata.st_nlink != 1
            or lock_metadata.st_uid != os.getuid()
        ):
            raise SystemExit("Project Skill recording lock is not a safe regular file")
        fcntl.flock(lock, fcntl.LOCK_EX)
        references = open_directory(skill, relative_path[0])
        try:
            flags = os.O_RDONLY | os.O_NOFOLLOW
            target = os.open(relative_path[1], flags, dir_fd=references)
            target_metadata = os.fstat(target)
            if (
                not stat.S_ISREG(target_metadata.st_mode)
                or target_metadata.st_nlink != 1
                or target_metadata.st_size > MAX_LEDGER_BYTES
            ):
                os.close(target)
                raise SystemExit(
                    "Project Skill record target must be one bounded, regular, "
                    "non-linked file: "
                    f"{'/'.join(relative_path)}"
                )
            timestamp = datetime.now(timezone.utc).isoformat()
            body = [
                f"\n## {timestamp} — {markdown_inline(heading)}\n",
                f"- Receipt: `{markdown_inline(record_id)}`\n",
                f"- Disposition: {markdown_inline(disposition)}\n",
            ]
            body.extend(f"- {line}\n" for line in lines if line)
            encoded = "".join(body).encode("utf-8")
            if len(encoded) > MAX_RECORD_BYTES:
                os.close(target)
                raise SystemExit(
                    f"Project Skill record exceeds {MAX_RECORD_BYTES} bytes"
                )
            temporary_name = f".{relative_path[1]}.{uuid4().hex}.tmp"
            temporary = -1
            try:
                temporary = os.open(
                    temporary_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=references,
                )
                remaining = target_metadata.st_size
                while remaining:
                    chunk = os.read(target, min(64 * 1024, remaining))
                    if not chunk:
                        raise OSError("record target changed while being copied")
                    write_all(temporary, chunk, relative_path[1])
                    remaining -= len(chunk)
                write_all(temporary, encoded, relative_path[1])
                os.fchmod(temporary, stat.S_IMODE(target_metadata.st_mode))
                os.fsync(temporary)
                os.close(temporary)
                temporary = -1
                os.rename(
                    temporary_name,
                    relative_path[1],
                    src_dir_fd=references,
                    dst_dir_fd=references,
                )
                os.fsync(references)
            finally:
                if temporary >= 0:
                    os.close(temporary)
                os.close(target)
                try:
                    os.unlink(temporary_name, dir_fd=references)
                except FileNotFoundError:
                    pass
        except FileNotFoundError as error:
            raise SystemExit(
                f"Project Skill is not initialized: {'/'.join(relative_path)}"
            ) from error
        except OSError as error:
            raise SystemExit(
                f"Cannot append Project Skill record safely: {'/'.join(relative_path)}: {error}"
            ) from error
        finally:
            os.close(references)
    finally:
        os.close(lock)
    return record_id


def initialize(args: argparse.Namespace) -> None:
    with skill_directory(args.project_root, create=True) as (root, skill):
        references = open_directory(skill, "references", create=True)
        diagrams = open_directory(skill, "diagrams", create=True)
        try:
            name = markdown_inline(args.name)
            create_file(
                skill,
                "SKILL.md",
                "---\n"
                "name: project\n"
                "description: Load this target project's purpose, decisions, progress, and diagrams before project work.\n"
                "---\n\n"
                f"# {name}\n\n"
                "Read `references/project.md` for stable project context, "
                "`references/decisions.md` for accepted Human decisions, and "
                "`references/progress.md` for recent completed work. Load only the "
                "diagram sources relevant to the current task.\n",
            )
            create_file(
                references,
                "project.md",
                f"# {name}\n\n## Purpose\n\nUnspecified.\n\n"
                "## Boundaries\n\nUnspecified.\n",
            )
            create_file(references, "decisions.md", "# Decisions\n")
            create_file(references, "progress.md", "# Progress\n")
        finally:
            os.close(diagrams)
            os.close(references)
        print(root)


def record_progress(args: argparse.Namespace) -> None:
    with skill_directory(args.project_root) as (skill_path, skill):
        lines = [
            f"Status: {markdown_inline(args.status)}",
            f"Summary: {markdown_inline(args.summary)}",
        ]
        lines.extend(
            f"Changed path: `{markdown_inline(path)}`" for path in args.changed_path
        )
        if args.feedback:
            lines.append(f"Human feedback: {markdown_inline(args.feedback)}")
        lines.append(f"Tests: {markdown_inline(args.tests)}")
        record_id = append_entry(
            skill_path,
            skill,
            ("references", "progress.md"),
            args.title,
            lines,
            args.receipt,
            args.disposition,
        )
    print(record_id)


def record_decision(args: argparse.Namespace) -> None:
    with skill_directory(args.project_root) as (skill_path, skill):
        lines = [f"Decision: {markdown_inline(args.decision)}"]
        if args.rationale:
            lines.append(f"Rationale: {markdown_inline(args.rationale)}")
        record_id = append_entry(
            skill_path,
            skill,
            ("references", "decisions.md"),
            args.title,
            lines,
            args.receipt,
            args.disposition,
        )
    print(record_id)


def show(args: argparse.Namespace) -> None:
    with skill_directory(args.project_root) as (root, _):
        print(root / "SKILL.md")
        print(root / "references/decisions.md")
        print(root / "references/progress.md")
        print(root / "references/project.md")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--name", required=True)
    init.set_defaults(func=initialize)

    progress = commands.add_parser("progress")
    progress.add_argument("--project-root", required=True)
    progress.add_argument("--title", required=True)
    progress.add_argument("--summary", required=True)
    progress.add_argument("--status", default="completed")
    progress.add_argument("--changed-path", action="append", default=[])
    progress.add_argument("--feedback")
    progress.add_argument("--tests", default="tests not run")
    progress.add_argument("--receipt")
    progress.add_argument(
        "--disposition", choices=("accepted", "corrected"), default="accepted"
    )
    progress.set_defaults(func=record_progress)

    decision = commands.add_parser("decision")
    decision.add_argument("--project-root", required=True)
    decision.add_argument("--title", required=True)
    decision.add_argument("--decision", required=True)
    decision.add_argument("--rationale")
    decision.add_argument("--receipt")
    decision.add_argument(
        "--disposition", choices=("accepted", "corrected"), default="accepted"
    )
    decision.set_defaults(func=record_decision)

    display = commands.add_parser("show")
    display.add_argument("--project-root", required=True)
    display.set_defaults(func=show)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
