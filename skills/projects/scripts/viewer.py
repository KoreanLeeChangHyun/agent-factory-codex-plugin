#!/usr/bin/env python3
"""Serve the read-only Agent Factory project view on loopback."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from urllib.parse import urlparse


SKILL_RELATIVE = Path(".agent-factory/skills/project")
ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "viewer"


def read_text(path: Path, boundary: Path) -> str:
    if path.is_symlink() or not path.is_file():
        return ""
    try:
        path.resolve().relative_to(boundary)
    except ValueError:
        return ""
    return path.read_text(encoding="utf-8")


def git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=3,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def files_under(root: Path, boundary: Path) -> list[dict[str, str]]:
    if not root.is_dir():
        return []
    return [
        {"path": str(path.relative_to(root)), "content": read_text(path, boundary)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]


def project_payload(project_root: Path) -> dict[str, object]:
    safe_root = project_root
    for part in SKILL_RELATIVE.parts:
        safe_root /= part
        if safe_root.is_symlink():
            safe_root = project_root / "__invalid__"
            break
    return {
        "projectRoot": str(project_root),
        "skill": read_text(safe_root / "SKILL.md", safe_root),
        "references": files_under(safe_root / "references", safe_root),
        "diagrams": files_under(safe_root / "diagrams", safe_root),
        "git": {
            "branch": git(project_root, "branch", "--show-current"),
            "head": git(project_root, "log", "-1", "--format=%h %s"),
            "status": git(project_root, "status", "--short"),
        },
    }


class ViewerHandler(BaseHTTPRequestHandler):
    project_root: Path

    def send_bytes(self, content: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/project":
            payload = json.dumps(
                project_payload(self.project_root), ensure_ascii=False
            ).encode("utf-8")
            self.send_bytes(payload, "application/json; charset=utf-8")
            return
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        asset = assets.get(route)
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_bytes((ASSET_ROOT / asset[0]).read_bytes(), asset[1])

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        raise SystemExit(f"Project root does not exist: {project_root}")
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Non-loopback binding requires an explicit code change")
    ViewerHandler.project_root = project_root
    server = ThreadingHTTPServer((args.host, args.port), ViewerHandler)
    print(f"http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
