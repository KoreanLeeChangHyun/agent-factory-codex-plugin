#!/usr/bin/env python3
"""Verify complete, ordered AI-source coverage in a Human Specification."""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import sys


SOURCE_EXTENSIONS = {".md", ".yaml", ".yml"}
RANGE_PATTERN = re.compile(r"([1-9][0-9]*)-([1-9][0-9]*)")


class VerificationError(RuntimeError):
    """A fail-closed Specification coverage error."""


class _CoverageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: dict[str, dict[str, object]] = {}
        self._source_stack: list[tuple[str, str]] = []
        self._block_stack: list[tuple[str, dict[str, object]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {name: value or "" for name, value in attrs}
        source = attributes.get("data-ai-source")
        source_hash = attributes.get("data-ai-sha256")
        if source and source_hash:
            if source in self.sources:
                raise VerificationError(f"duplicate Human source container: {source}")
            record: dict[str, object] = {"sha256": source_hash, "blocks": []}
            self.sources[source] = record
            self._source_stack.append((tag, source))

        source_range = attributes.get("data-source-lines")
        block_hash = attributes.get("data-source-sha256")
        if source_range and block_hash:
            if not self._source_stack:
                raise VerificationError("translation block has no source container")
            block: dict[str, object] = {
                "range": source_range,
                "sha256": block_hash,
                "text": [],
            }
            current_source = self._source_stack[-1][1]
            blocks = self.sources[current_source]["blocks"]
            assert isinstance(blocks, list)
            blocks.append(block)
            self._block_stack.append((tag, block))

    def handle_endtag(self, tag: str) -> None:
        if self._block_stack and self._block_stack[-1][0] == tag:
            self._block_stack.pop()
        if self._source_stack and self._source_stack[-1][0] == tag:
            self._source_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._block_stack:
            return
        text = self._block_stack[-1][1]["text"]
        assert isinstance(text, list)
        text.append(data)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _project_root(value: str | None) -> Path:
    candidate = Path(value).expanduser() if value else Path.cwd()
    completed = subprocess.run(
        ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VerificationError(completed.stderr.strip() or "not inside a Git work tree")
    root = Path(completed.stdout.strip()).resolve(strict=True)
    if value and candidate.resolve(strict=True) != root:
        raise VerificationError("--project-root must identify the exact Git root")
    return root


def instruction_sources(skill_root: Path) -> list[Path]:
    """Return the complete first-party natural-language instruction source set."""

    if skill_root.is_symlink() or not skill_root.is_dir():
        raise VerificationError(f"Skill root is not a safe directory: {skill_root}")
    sources = [
        path
        for path in skill_root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and (
            path.suffix.casefold() in SOURCE_EXTENSIONS
            and (path.suffix.casefold() == ".md" or path.parent.name == "agents")
        )
    ]
    entry = skill_root / "SKILL.md"
    if entry not in sources:
        raise VerificationError(f"Skill entry is missing: {entry}")
    return sorted(sources, key=lambda path: (path != entry, path.relative_to(skill_root).as_posix()))


def verify_pair(project_root: Path, specification_id: str) -> list[str]:
    skill_root = project_root / "skills" / specification_id
    human_entry = (
        project_root
        / ".agent-factory"
        / "document"
        / "specification"
        / specification_id
        / "index.html"
    )
    if human_entry.is_symlink() or not human_entry.is_file():
        raise VerificationError(f"Human Specification entry is missing: {human_entry}")

    parser = _CoverageParser()
    try:
        parser.feed(human_entry.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise VerificationError(f"Human Specification is unreadable: {human_entry}") from exc

    expected_paths = instruction_sources(skill_root)
    expected_sources = {
        path.relative_to(project_root).as_posix(): path for path in expected_paths
    }
    actual_names = set(parser.sources)
    expected_names = set(expected_sources)
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing sources: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected sources: {', '.join(extra)}")
        raise VerificationError("; ".join(details))
    if list(parser.sources) != list(expected_sources):
        raise VerificationError("Human source containers are not in AI source order")

    verified: list[str] = []
    for source_name, source_path in expected_sources.items():
        source_bytes = source_path.read_bytes()
        record = parser.sources[source_name]
        if record["sha256"] != _sha256(source_bytes):
            raise VerificationError(f"stale source hash: {source_name}")
        source_text = source_bytes.decode("utf-8")
        source_lines = source_text.splitlines(keepends=True)
        blocks = record["blocks"]
        assert isinstance(blocks, list)
        if not blocks:
            raise VerificationError(f"source has no translated blocks: {source_name}")
        next_line = 1
        for block in blocks:
            assert isinstance(block, dict)
            match = RANGE_PATTERN.fullmatch(str(block["range"]))
            if match is None:
                raise VerificationError(
                    f"invalid source range {block['range']!r}: {source_name}"
                )
            start, end = (int(value) for value in match.groups())
            if start != next_line or end < start or end > len(source_lines):
                raise VerificationError(
                    f"non-contiguous source range {start}-{end}: {source_name}"
                )
            segment = "".join(source_lines[start - 1 : end]).encode("utf-8")
            if block["sha256"] != _sha256(segment):
                raise VerificationError(
                    f"stale source range hash {start}-{end}: {source_name}"
                )
            rendered_text = "".join(block["text"]).strip()
            if not rendered_text:
                raise VerificationError(
                    f"translated block is empty at {start}-{end}: {source_name}"
                )
            next_line = end + 1
        if next_line != len(source_lines) + 1:
            raise VerificationError(
                f"source ranges do not reach line {len(source_lines)}: {source_name}"
            )
        verified.append(source_name)
    return verified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify complete ordered AI-source coverage in a Human Specification."
    )
    parser.add_argument("--project-root")
    parser.add_argument("--specification-id", required=True)
    args = parser.parse_args(argv)
    try:
        verified = verify_pair(_project_root(args.project_root), args.specification_id)
    except VerificationError as exc:
        print(f"misaligned: {exc}", file=sys.stderr)
        return 1
    print(f"coverage-passed: {args.specification_id} ({len(verified)} sources)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
