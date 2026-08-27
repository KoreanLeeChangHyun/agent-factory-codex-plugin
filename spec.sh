#!/bin/sh

usage() {
    printf 'Usage: %s [--port <port>]\n' "${0##*/}"
}

port=8000
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -p|--port)
            if [ "$#" -lt 2 ]; then
                usage >&2
                exit 2
            fi
            case $2 in
                -[0-9]*) ;;
                -*)
                    usage >&2
                    exit 2
                    ;;
            esac
            port=$2
            shift 2
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done
set -- "$port"

script_path=$0
case $script_path in
    /*) ;;
    *) script_path=$PWD/$script_path ;;
esac

link_limit=40
while [ -L "$script_path" ]; do
    if [ "$link_limit" -eq 0 ]; then
        echo "error: too many symbolic links while resolving launcher: $0" >&2
        exit 1
    fi
    link_target=$(readlink "$script_path") || {
        echo "error: cannot read launcher symbolic link: $script_path" >&2
        exit 1
    }
    case $link_target in
        /*) script_path=$link_target ;;
        *) script_path=$(dirname "$script_path")/$link_target ;;
    esac
    link_limit=$((link_limit - 1))
done

script_dir=$(CDPATH= cd -P "$(dirname "$script_path")" && pwd) || {
    echo "error: cannot resolve launcher directory: $script_path" >&2
    exit 1
}
project_root=$script_dir
port=${1:-8000}

if [ "$#" -gt 1 ]; then
    echo "usage: $0 [port]" >&2
    exit 2
fi

exec python3 - "$project_root" "$port" <<'PY'
from __future__ import annotations

import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import shutil
import sys
from urllib.parse import unquote, urlsplit
import webbrowser


project_root = Path(sys.argv[1]).resolve(strict=True)
specification_path = project_root / ".agent-factory" / "specification"
human_refined_path = project_root / ".agent-factory" / "information" / "refined" / "human"
try:
    specification_root = specification_path.resolve(strict=True)
except FileNotFoundError:
    raise SystemExit(f"error: Specification tree is missing: {specification_path}")
try:
    specification_root.relative_to(project_root)
except ValueError:
    raise SystemExit(f"error: Specification tree escapes the project root: {specification_path}")
if not specification_root.is_dir():
    raise SystemExit(f"error: Specification tree is not a directory: {specification_path}")
try:
    human_refined_root = human_refined_path.resolve(strict=True)
    human_refined_root.relative_to(project_root)
except (FileNotFoundError, ValueError):
    raise SystemExit(f"error: Human refined tree is missing or unsafe: {human_refined_path}")
if not human_refined_root.is_dir():
    raise SystemExit(f"error: Human refined tree is not a directory: {human_refined_path}")

served_roots = {
    "common": specification_root / "common",
    "explorer": specification_root / "explorer",
    "skills": specification_root / "skills",
    "planning": human_refined_root,
}

try:
    port = int(sys.argv[2])
except ValueError:
    raise SystemExit("error: port must be an integer")
if port not in range(1, 65536):
    raise SystemExit("error: port must be between 1 and 65535")


def request_file(target: str) -> tuple[Path, bool]:
    raw_path = urlsplit(target).path
    try:
        decoded = unquote(raw_path, errors="strict")
    except UnicodeError as exc:
        raise ValueError("invalid UTF-8 in request path") from exc
    if not decoded.startswith("/") or decoded.startswith("//"):
        raise ValueError("request path must be local")
    if "\\" in decoded or "\0" in decoded:
        raise ValueError("invalid request path")
    relative = PurePosixPath(decoded.removeprefix("/"))
    if any(part in {".", ".."} for part in relative.parts):
        raise ValueError("request traversal is not allowed")
    if not relative.parts or relative.parts[0] not in served_roots:
        raise ValueError("request path does not select an allowlisted local root")
    root = served_roots[relative.parts[0]].resolve(strict=True)
    candidate = root.joinpath(*relative.parts[1:]).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("request escapes the Specification tree") from exc
    return candidate, decoded.endswith("/")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.serve(send_body=True)

    def do_HEAD(self) -> None:
        self.serve(send_body=False)

    def serve(self, send_body: bool) -> None:
        if urlsplit(self.path).path == "/":
            self.send_response(302)
            self.send_header("Location", "/common/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            candidate, trailing_slash = request_file(self.path)
        except ValueError as exc:
            self.send_error(400, str(exc))
            return
        if candidate.is_dir():
            if not trailing_slash:
                self.send_response(301)
                self.send_header("Location", f"{urlsplit(self.path).path}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            candidate = candidate / "index.html"
        try:
            candidate = candidate.resolve(strict=True)
            if not any(candidate.is_relative_to(root.resolve(strict=True)) for root in served_roots.values()):
                raise ValueError
        except (FileNotFoundError, OSError, ValueError):
            self.send_error(404, "Specification file not found")
            return
        if not candidate.is_file():
            self.send_error(404, "Specification file not found")
            return
        try:
            source = candidate.open("rb")
            size = candidate.stat().st_size
        except OSError as exc:
            self.send_error(500, str(exc))
            return
        with source:
            content_type = mimetypes.guess_type(candidate.name)[0]
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body:
                shutil.copyfileobj(source, self.wfile)


server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
url = f"http://127.0.0.1:{server.server_address[1]}/common/"
print(f"Serving local Specification UI and Human refined documents read-only at {url}")
webbrowser.open(url)
try:
    server.serve_forever()
finally:
    server.server_close()
PY
