#!/usr/bin/env python3
"""Initialize and append to a target repository's AI-facing Project Skill."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


RELATIVE_SKILL = Path(".agent-factory/skills/project")


def skill_root(project_root: Path) -> Path:
    root = project_root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Project root does not exist: {root}")
    candidate = root
    for part in RELATIVE_SKILL.parts:
        candidate /= part
        if candidate.is_symlink():
            raise SystemExit(f"Project Skill path must not contain symlinks: {candidate}")
    return candidate


def atomic_create(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        return


def append_entry(path: Path, heading: str, lines: list[str]) -> None:
    if not path.is_file():
        raise SystemExit(f"Project Skill is not initialized: {path}")
    timestamp = datetime.now(timezone.utc).isoformat()
    body = [f"\n## {timestamp} — {heading}\n"]
    body.extend(f"- {line}\n" for line in lines if line)
    with path.open("a", encoding="utf-8") as handle:
        handle.writelines(body)


def initialize(args: argparse.Namespace) -> None:
    root = skill_root(Path(args.project_root))
    atomic_create(
        root / "SKILL.md",
        "---\n"
        "name: project\n"
        "description: Load this target project's purpose, decisions, progress, and diagrams before project work.\n"
        "---\n\n"
        f"# {args.name}\n\n"
        "Read `references/project.md` for stable project context, "
        "`references/decisions.md` for accepted Human decisions, and "
        "`references/progress.md` for recent completed work. Load only the "
        "diagram sources relevant to the current task.\n",
    )
    atomic_create(
        root / "references/project.md",
        f"# {args.name}\n\n## Purpose\n\nUnspecified.\n\n"
        "## Boundaries\n\nUnspecified.\n",
    )
    atomic_create(root / "references/decisions.md", "# Decisions\n")
    atomic_create(root / "references/progress.md", "# Progress\n")
    (root / "diagrams").mkdir(parents=True, exist_ok=True)
    print(root)


def record_progress(args: argparse.Namespace) -> None:
    root = skill_root(Path(args.project_root))
    lines = [f"Status: {args.status}", f"Summary: {args.summary}"]
    lines.extend(f"Changed path: `{path}`" for path in args.changed_path)
    if args.feedback:
        lines.append(f"Human feedback: {args.feedback}")
    lines.append(f"Tests: {args.tests}")
    append_entry(root / "references/progress.md", args.title, lines)


def record_decision(args: argparse.Namespace) -> None:
    root = skill_root(Path(args.project_root))
    lines = [f"Decision: {args.decision}"]
    if args.rationale:
        lines.append(f"Rationale: {args.rationale}")
    append_entry(root / "references/decisions.md", args.title, lines)


def show(args: argparse.Namespace) -> None:
    root = skill_root(Path(args.project_root))
    if not root.is_dir():
        raise SystemExit(f"Project Skill is not initialized: {root}")
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        print(path.relative_to(root))


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
    progress.set_defaults(func=record_progress)

    decision = commands.add_parser("decision")
    decision.add_argument("--project-root", required=True)
    decision.add_argument("--title", required=True)
    decision.add_argument("--decision", required=True)
    decision.add_argument("--rationale")
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
