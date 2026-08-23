#!/usr/bin/env python3
"""Install and serve Agent Factory Specification browser assets."""

from __future__ import annotations

import argparse
import functools
import ipaddress
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
import webbrowser


SPECIFICATION_RELATIVE_PATH = Path(".agent-factory/specification")
PACKAGED_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "browser"
PACKAGED_LAUNCHER = Path(__file__).resolve().parents[1] / "assets" / "spec.sh"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class ViewerError(RuntimeError):
    """A safe, user-facing viewer failure."""


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolved_within(parent: Path, candidate: Path, description: str) -> Path:
    resolved_parent = parent.resolve(strict=True)
    resolved_candidate = candidate.resolve(strict=False)
    if not _is_within(resolved_parent, resolved_candidate):
        raise ViewerError(f"{description} escapes the project root: {candidate}")
    return resolved_candidate


def resolve_project_root(override: str | None, cwd: Path | None = None) -> Path:
    """Resolve and validate the exact Git project root."""

    if override is not None:
        raw_override = Path(override).expanduser()
        if ".." in raw_override.parts:
            raise ViewerError("--project-root must not contain '..' traversal")
        candidate = raw_override
    else:
        candidate = cwd or Path.cwd()

    try:
        candidate = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(f"project path does not exist: {candidate}") from exc
    if not candidate.is_dir():
        raise ViewerError(f"project path is not a directory: {candidate}")

    try:
        completed = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ViewerError("Git is required to resolve the project root") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "not inside a Git work tree"
        raise ViewerError(f"cannot resolve Git project root: {detail}")

    output = completed.stdout.strip()
    if not output or "\n" in output:
        raise ViewerError("Git returned an invalid project root")
    try:
        git_root = Path(output).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(f"Git project root does not exist: {output}") from exc
    if not git_root.is_dir():
        raise ViewerError(f"Git project root is not a directory: {git_root}")
    if override is not None and candidate != git_root:
        raise ViewerError(
            f"--project-root must name the Git root itself (resolved root: {git_root})"
        )
    return git_root


def _packaged_files(asset_root: Path) -> list[tuple[Path, Path]]:
    try:
        resolved_asset_root = asset_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(f"packaged browser assets are missing: {asset_root}") from exc
    if not resolved_asset_root.is_dir():
        raise ViewerError(f"packaged browser asset path is not a directory: {asset_root}")

    files: list[tuple[Path, Path]] = []
    for source in sorted(resolved_asset_root.rglob("*")):
        if source.is_symlink():
            raise ViewerError(f"packaged browser asset must not be a symlink: {source}")
        if source.is_file():
            files.append((source, source.relative_to(resolved_asset_root)))
    if not files:
        raise ViewerError(f"packaged browser asset directory is empty: {asset_root}")
    return files


def _atomic_copy(source: Path, destination: Path, mode: int = 0o644) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with source.open("rb") as packaged:
                shutil.copyfileobj(packaged, temporary)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _atomic_copy_new(source: Path, destination: Path, mode: int) -> bool:
    """Atomically publish a new file without replacing any existing path."""

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with source.open("rb") as packaged:
                shutil.copyfileobj(packaged, temporary)
        os.chmod(temporary_path, mode)
        try:
            os.link(temporary_path, destination)
        except FileExistsError:
            return False
        return True
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def install_assets(
    project_root: Path,
    asset_root: Path,
    force: bool,
    launcher_source: Path = PACKAGED_LAUNCHER,
) -> tuple[int, int, bool]:
    """Install the root launcher and assets after one combined preflight."""

    specification_root = project_root / SPECIFICATION_RELATIVE_PATH
    destination_root = specification_root / "common"
    _resolved_within(project_root, specification_root, "Specification directory")
    _resolved_within(project_root, destination_root, "common asset directory")

    try:
        resolved_launcher_source = launcher_source.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(f"packaged Specification launcher is missing: {launcher_source}") from exc
    if launcher_source.is_symlink() or not resolved_launcher_source.is_file():
        raise ViewerError(
            f"packaged Specification launcher must be a regular file: {launcher_source}"
        )

    launcher_destination = project_root / "spec.sh"
    install_launcher = not (
        launcher_destination.exists() or launcher_destination.is_symlink()
    )

    planned: list[tuple[Path, Path]] = []
    unchanged = 0
    conflicts: list[Path] = []
    for source, relative_path in _packaged_files(asset_root):
        destination = destination_root / relative_path
        _resolved_within(project_root, destination, "browser asset destination")
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_file():
                conflicts.append(destination)
                continue
            if destination.read_bytes() == source.read_bytes():
                unchanged += 1
                continue
            if not force:
                conflicts.append(destination)
                continue
        planned.append((source, destination))

    if conflicts:
        rendered = "\n".join(f"  - {path}" for path in conflicts)
        suffix = "" if force else "\nRe-run init with --force to replace differing files."
        raise ViewerError(f"browser asset conflicts:\n{rendered}{suffix}")

    launcher_installed = False
    if install_launcher:
        launcher_installed = _atomic_copy_new(
            resolved_launcher_source, launcher_destination, 0o755
        )
    for source, destination in planned:
        _resolved_within(project_root, destination.parent, "browser asset directory")
        _atomic_copy(source, destination)
    return len(planned), unchanged, launcher_installed


def resolve_request_path(served_root: Path, request_target: str) -> tuple[Path, bool]:
    """Map a URL target to a path without permitting traversal or symlink escape."""

    raw_path = urlsplit(request_target).path
    try:
        decoded_path = unquote(raw_path, errors="strict")
    except UnicodeError as exc:
        raise ViewerError("request path is not valid UTF-8") from exc
    if not decoded_path.startswith("/") or decoded_path.startswith("//"):
        raise ViewerError("request path must be an absolute local path")
    if "\x00" in decoded_path or "\\" in decoded_path:
        raise ViewerError("request path contains an invalid character")

    relative = PurePosixPath(decoded_path.removeprefix("/"))
    if any(part in {".", ".."} for part in relative.parts):
        raise ViewerError("request path traversal is not allowed")

    root = served_root.resolve(strict=True)
    candidate = root.joinpath(*relative.parts).resolve(strict=False)
    if not _is_within(root, candidate):
        raise ViewerError("request path escapes the served Specification tree")
    return candidate, decoded_path.endswith("/")


class SpecificationRequestHandler(BaseHTTPRequestHandler):
    """Read-only handler constrained to one resolved Specification tree."""

    server_version = "AgentFactorySpecification/1"

    def __init__(self, *args: object, served_root: Path, **kwargs: object) -> None:
        self.served_root = served_root.resolve(strict=True)
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._serve(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._serve(send_body=False)

    def _serve(self, send_body: bool) -> None:
        if urlsplit(self.path).path == "/":
            self.send_response(302)
            self.send_header("Location", "/common/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            candidate, trailing_slash = resolve_request_path(self.served_root, self.path)
        except ViewerError as exc:
            self.send_error(400, str(exc))
            return

        if candidate.is_dir():
            if not trailing_slash:
                path = urlsplit(self.path).path
                self.send_response(301)
                self.send_header("Location", f"{path}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            candidate = candidate / "index.html"

        try:
            resolved_file = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            self.send_error(404, "Specification file not found")
            return
        if not _is_within(self.served_root, resolved_file) or not resolved_file.is_file():
            self.send_error(404, "Specification file not found")
            return

        try:
            source = resolved_file.open("rb")
            stat = resolved_file.stat()
        except OSError as exc:
            self.send_error(500, str(exc))
            return

        with source:
            content_type = mimetypes.guess_type(resolved_file.name)[0]
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body:
                try:
                    shutil.copyfileobj(source, self.wfile)
                except OSError as exc:
                    self.log_error("failed to send %s: %s", resolved_file, exc)


def _resolved_addresses(host: str, port: int) -> list[tuple[int, tuple[object, ...]]]:
    try:
        results = socket.getaddrinfo(
            host,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            flags=socket.AI_PASSIVE,
        )
    except socket.gaierror as exc:
        raise ViewerError(f"cannot resolve bind host {host!r}: {exc}") from exc
    addresses: list[tuple[int, tuple[object, ...]]] = []
    for family, _type, _protocol, _canonical_name, sockaddr in results:
        entry = (family, sockaddr)
        if entry not in addresses:
            addresses.append(entry)
    if not addresses:
        raise ViewerError(f"bind host resolved to no addresses: {host!r}")
    return addresses


def addresses_are_loopback(
    addresses: list[tuple[int, tuple[object, ...]]],
) -> bool:
    return all(
        ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0]).is_loopback
        for _family, sockaddr in addresses
    )


def serve(project_root: Path, host: str, port: int, allow_non_loopback: bool, open_browser: bool) -> None:
    specification_root = project_root / SPECIFICATION_RELATIVE_PATH
    resolved_root = _resolved_within(
        project_root, specification_root, "served Specification directory"
    )
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise ViewerError(
            f"Specification directory does not exist: {specification_root}; run init first"
        )
    addresses = _resolved_addresses(host, port)
    if not addresses_are_loopback(addresses) and not allow_non_loopback:
        raise ViewerError(
            f"refusing non-loopback bind host {host!r}; "
            "pass --allow-non-loopback to explicitly permit network exposure"
        )

    family, sockaddr = addresses[0]
    handler = functools.partial(SpecificationRequestHandler, served_root=resolved_root)

    class AddressFamilyServer(ThreadingHTTPServer):
        address_family = family
        daemon_threads = True

    try:
        server = AddressFamilyServer(sockaddr, handler)
    except OSError as exc:
        raise ViewerError(f"cannot bind {host}:{port}: {exc}") from exc

    actual_port = int(server.server_address[1])
    browser_host = host
    if host in {"0.0.0.0", "::", ""}:
        browser_host = DEFAULT_HOST
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    url = f"http://{browser_host}:{actual_port}/common/"
    print(f"Serving {resolved_root} read-only at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install or serve Agent Factory Specification browser assets."
    )
    parser.add_argument(
        "--project-root",
        help="exact Git project root (defaults to the Git root containing the current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="install the packaged common browser shell")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="replace differing regular asset files after conflict preflight",
    )

    serve_parser = subparsers.add_parser("serve", help="serve the existing Specification tree read-only")
    serve_parser.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default: {DEFAULT_HOST})")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"bind port (default: {DEFAULT_PORT})")
    serve_parser.add_argument("--open", action="store_true", help="open the common shell in the default browser")
    serve_parser.add_argument(
        "--allow-non-loopback",
        action="store_true",
        help="explicitly allow binding to a non-loopback network address",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "port", DEFAULT_PORT) not in range(0, 65536):
        parser.error("--port must be between 0 and 65535")

    try:
        project_root = resolve_project_root(args.project_root)
        if args.command == "init":
            installed, unchanged, launcher_installed = install_assets(
                project_root, PACKAGED_ASSET_ROOT, args.force
            )
            destination = project_root / SPECIFICATION_RELATIVE_PATH / "common"
            print(f"Installed {installed} browser asset(s) in {destination}; {unchanged} unchanged.")
            if launcher_installed:
                print(f"Installed project launcher at {project_root / 'spec.sh'}.")
            else:
                print(f"Preserved existing project launcher at {project_root / 'spec.sh'}.")
        else:
            serve(project_root, args.host, args.port, args.allow_non_loopback, args.open)
    except ViewerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
