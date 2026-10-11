#!/usr/bin/env python3
"""Install pinned Archify, validate Document JSON assets, and render/open standalone HTML."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from system import archify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install", help="Download and verify the pinned official renderer; no npm/global install.")
    install.add_argument("--tool-dir", type=Path, required=True, help="New renderer directory outside the project, with an existing parent.")
    preview = commands.add_parser("preview", help="Validate JSON from stdin and return an isolated SVG preview; writes no project files.")
    preview.add_argument("--tool-dir", type=Path, required=True, help="Directory prepared by install.")
    for name in ("validate", "render"):
        command = commands.add_parser(name, help="Validate JSON with the official schema." if name == "validate" else "Validate then deliver HTML without replacing files.")
        command.add_argument("--project-root", type=Path, required=True)
        command.add_argument("--tool-dir", type=Path, required=True, help="Directory prepared by install.")
        command.add_argument("input", type=Path, help="JSON inside a Document package assets/ directory.")
        if name == "render":
            command.add_argument("--output", type=Path, required=True, help="New docs/artifact/<category>/<topic>/*.html file; parent must exist.")
            command.add_argument("--open", action="store_true", help="Open generated HTML in the local OS browser.")
    opener = commands.add_parser("open", help="Open an existing artifact HTML in the local OS browser.")
    opener.add_argument("--project-root", type=Path, required=True)
    opener.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = archify.execute(args)
    except (OSError, ValueError, archify.ArchifyError) as error:
        result = {"ok": False, "error": str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
