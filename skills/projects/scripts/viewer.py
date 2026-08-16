#!/usr/bin/env python3
"""Serve the read-only Agent Factory project view on loopback."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
from urllib.parse import urlparse


SKILL_RELATIVE = Path(".agent-factory/skills/project")
ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "viewer"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_FILES = 200


def open_directory(parent: int, name: str) -> int | None:
    try:
        return os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    except OSError:
        return None


def open_skill(project_root: Path) -> int | None:
    try:
        descriptor = os.open(project_root, DIRECTORY_FLAGS)
    except OSError:
        return None
    for part in SKILL_RELATIVE.parts:
        next_descriptor = open_directory(descriptor, part)
        os.close(descriptor)
        if next_descriptor is None:
            return None
        descriptor = next_descriptor
    return descriptor


def read_file(directory: int, name: str, budget: list[int]) -> str | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    except OSError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_FILE_BYTES
            or metadata.st_size > budget[0]
        ):
            return None
        chunks: list[bytes] = []
        remaining = metadata.st_size
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) != metadata.st_size:
            return None
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
        budget[0] -= len(content)
        return decoded
    finally:
        os.close(descriptor)


def files_under(directory: int | None, budget: list[int]) -> list[dict[str, str]]:
    if directory is None:
        return []
    output: list[dict[str, str]] = []

    def visit(current: int, prefix: str) -> None:
        if len(output) >= MAX_FILES or budget[0] <= 0:
            return
        try:
            names = sorted(os.listdir(current))
        except OSError:
            return
        for name in names:
            if len(output) >= MAX_FILES or budget[0] <= 0:
                return
            try:
                metadata = os.stat(name, dir_fd=current, follow_symlinks=False)
            except OSError:
                continue
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(metadata.st_mode):
                child = open_directory(current, name)
                if child is None:
                    continue
                try:
                    visit(child, relative)
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                content = read_file(current, name, budget)
                if content is not None:
                    output.append({"path": relative, "content": content})

    try:
        visit(directory, "")
    finally:
        os.close(directory)
    return output


def git(project_root: Path, *args: str) -> str:
    environment = {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
    }
    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(project_root),
                *args,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def project_payload(project_root: Path) -> dict[str, object]:
    budget = [MAX_TOTAL_BYTES]
    skill = open_skill(project_root)
    if skill is None:
        skill_text = ""
        references: list[dict[str, str]] = []
        diagrams: list[dict[str, str]] = []
    else:
        try:
            skill_text = read_file(skill, "SKILL.md", budget) or ""
            references_descriptor = open_directory(skill, "references")
            diagrams_descriptor = open_directory(skill, "diagrams")
        finally:
            os.close(skill)
        references = files_under(references_descriptor, budget)
        diagrams = files_under(diagrams_descriptor, budget)
    return {
        "projectRoot": str(project_root),
        "skill": skill_text,
        "references": references,
        "diagrams": diagrams,
        "limits": {
            "maxFileBytes": MAX_FILE_BYTES,
            "maxTotalBytes": MAX_TOTAL_BYTES,
            "maxFilesPerTree": MAX_FILES,
        },
        "git": {
            "branch": git(project_root, "branch", "--show-current"),
            "head": git(project_root, "log", "-1", "--format=%h %s"),
            "status": git(
                project_root, "status", "--short", "--untracked-files=normal"
            ),
        },
    }


def loopback_host(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    if not addresses:
        return False
    try:
        return all(ipaddress.ip_address(item[4][0]).is_loopback for item in addresses)
    except ValueError:
        return False


class ViewerHandler(BaseHTTPRequestHandler):
    project_root: Path
    allowed_hosts: frozenset[str]

    def send_bytes(self, content: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def valid_host_header(self) -> bool:
        value = self.headers.get("Host", "")
        if not value:
            return False
        if value.startswith("["):
            host = value[1:].split("]", 1)[0]
        else:
            host = value.rsplit(":", 1)[0]
        return host.casefold().rstrip(".") in self.allowed_hosts

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if not self.valid_host_header():
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Host header")
            return
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


class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--allow-non-loopback", action="store_true")
    args = parser.parse_args()
    try:
        project_root = Path(args.project_root).resolve(strict=True)
    except OSError as error:
        raise SystemExit(
            f"Project root does not exist: {args.project_root}: {error}"
        ) from error
    if not project_root.is_dir():
        raise SystemExit(f"Project root does not exist: {project_root}")
    is_loopback = loopback_host(args.host)
    if not is_loopback and not args.allow_non_loopback:
        raise SystemExit("Non-loopback binding requires --allow-non-loopback")
    allowed = {args.host.casefold().rstrip(".")}
    if is_loopback:
        allowed.update({"localhost", "127.0.0.1", "::1"})
    ViewerHandler.project_root = project_root
    ViewerHandler.allowed_hosts = frozenset(allowed)
    server_type = (
        IPv6ThreadingHTTPServer
        if any(
            item[0] == socket.AF_INET6
            for item in socket.getaddrinfo(args.host, args.port, type=socket.SOCK_STREAM)
        )
        else ThreadingHTTPServer
    )
    server = server_type((args.host, args.port), ViewerHandler)
    print(f"http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
