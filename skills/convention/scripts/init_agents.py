#!/usr/bin/env python3
"""Copy the packaged Agent Factory AGENTS.md template once."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the Agent Factory AGENTS.md template without overwriting."
    )
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve(strict=True)
    if not project_root.is_dir():
        parser.error("--project-root must be a directory")
    destination = project_root / "AGENTS.md"
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"refusing to overwrite existing project instructions: {destination}")

    source = Path(__file__).resolve().parents[1] / "assets" / "AGENTS.md"
    payload = source.read_bytes()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".AGENTS.md.", dir=project_root, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.chmod(temporary, 0o644)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise SystemExit(
                f"refusing to overwrite existing project instructions: {destination}"
            )
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Installed {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
