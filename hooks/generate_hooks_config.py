#!/usr/bin/env python3
"""Generate the Agent Factory plugin hook configuration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


OUTPUT = Path(__file__).with_name("hooks.json")


def config() -> dict[str, Any]:
    return {
        "description": (
            "Block direct LLM authoring of canonical Agent Factory Artifact JSON."
        ),
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "^(Bash|apply_patch|Edit|Write)$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                'python3 "$PLUGIN_ROOT/hooks/'
                                'artifact_json_guard.py" hook'
                            ),
                            "timeout": 5,
                            "statusMessage": (
                                "Checking canonical Artifact JSON authoring"
                            ),
                        }
                    ],
                }
            ]
        },
    }


def rendered() -> str:
    return json.dumps(config(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    expected = rendered()
    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except OSError as error:
            print(f"hook configuration is unavailable: {error}", file=sys.stderr)
            return 1
        if actual != expected:
            print(
                f"hook configuration is stale; run {Path(__file__).name}",
                file=sys.stderr,
            )
            return 1
        print(f"hook configuration is current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"generated hook configuration: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
