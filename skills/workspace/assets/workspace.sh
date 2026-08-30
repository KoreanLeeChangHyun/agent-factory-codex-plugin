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

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
import shutil
import sys
from urllib.parse import quote, unquote, urlsplit
import webbrowser


project_root = Path(sys.argv[1]).resolve(strict=True)
workspace_path = project_root / ".agent-factory" / "workspace"
human_refined_path = project_root / ".agent-factory" / "information" / "refined" / "human"
project_skills_path = project_root / ".codex" / "skills"
explorer_evidence_path = project_root / ".agent-factory" / "explorer"
tree_max_depth = 5
tree_max_entries = 120
tree_max_response_bytes = 128 * 1024
project_tree_excluded_paths = {
    PurePosixPath(".git"),
    PurePosixPath(".codex"),
    PurePosixPath(".agent-factory/agent"),
    PurePosixPath(".agent-factory/explorer"),
    PurePosixPath(".agent-factory/workspace"),
    PurePosixPath(".agent-factory/sync.json"),
}
try:
    workspace_root = workspace_path.resolve(strict=True)
except FileNotFoundError:
    raise SystemExit(f"error: Workspace tree is missing: {workspace_path}")
try:
    workspace_root.relative_to(project_root)
except ValueError:
    raise SystemExit(f"error: Workspace tree escapes the project root: {workspace_path}")
if not workspace_root.is_dir():
    raise SystemExit(f"error: Workspace tree is not a directory: {workspace_path}")
try:
    human_refined_root = human_refined_path.resolve(strict=True)
    human_refined_root.relative_to(project_root)
except (FileNotFoundError, ValueError):
    raise SystemExit(f"error: Human Specification tree is missing or unsafe: {human_refined_path}")
if not human_refined_root.is_dir():
    raise SystemExit(f"error: Human Specification tree is not a directory: {human_refined_path}")

served_roots = {
    "common": workspace_root / "common",
    "explorer": workspace_root / "explorer",
    "skills": workspace_root / "skills",
    "planning": human_refined_root,
}
if project_skills_path.exists():
    try:
        project_skills_root = project_skills_path.resolve(strict=True)
        project_skills_root.relative_to(project_root)
    except (FileNotFoundError, ValueError):
        raise SystemExit(f"error: Project Skill tree is unsafe: {project_skills_path}")
    if not project_skills_root.is_dir():
        raise SystemExit(f"error: Project Skill tree is not a directory: {project_skills_path}")
    served_roots["project-skills"] = project_skills_root

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
        raise ValueError("request escapes the Workspace tree") from exc
    return candidate, decoded.endswith("/")


def project_skills() -> list[dict[str, str]]:
    root = served_roots.get("project-skills")
    if root is None:
        return []
    skills = []
    for candidate in sorted(root.iterdir(), key=lambda path: path.name):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        entry_point = candidate / "SKILL.md"
        if entry_point.is_symlink() or not entry_point.is_file():
            continue
        skills.append({
            "name": candidate.name,
            "href": f"/project-skills/{quote(candidate.name, safe='')}/SKILL.md",
        })
    return skills


def project_path_is_excluded(relative_path: PurePosixPath) -> bool:
    return any(
        relative_path == excluded or excluded in relative_path.parents
        for excluded in project_tree_excluded_paths
    )


def tree_children(root: Path, directory: Path, depth: int, budget: dict, exclude_project_paths: bool):
    if depth >= tree_max_depth:
        budget["truncated"] = True
        return [], False
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: (entry.name.casefold(), entry.name))
    except OSError:
        return [], True
    children = []
    had_error = False
    for entry in entries:
        if budget["entries"] >= tree_max_entries:
            budget["truncated"] = True
            break
        candidate = Path(entry.path)
        try:
            relative = PurePosixPath(candidate.relative_to(root).as_posix())
        except ValueError:
            continue
        if exclude_project_paths and project_path_is_excluded(relative):
            continue
        try:
            if entry.is_symlink():
                continue
            is_directory = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
        except OSError:
            had_error = True
            continue
        if not is_directory and not is_file:
            continue
        budget["entries"] += 1
        node = {"name": entry.name, "kind": "directory" if is_directory else "file"}
        if is_directory:
            descendants, descendant_error = tree_children(
                root, candidate, depth + 1, budget, exclude_project_paths
            )
            node["children"] = descendants
            if descendant_error:
                node["state"] = "error"
                had_error = True
            elif not descendants:
                node["state"] = "empty"
            if depth + 1 >= tree_max_depth:
                node["truncated"] = True
                budget["truncated"] = True
        children.append(node)
    return children, had_error


def explorer_trees():
    project_budget = {"entries": 0, "truncated": False}
    project_children, project_error = tree_children(project_root, project_root, 0, project_budget, True)
    project_tree = {
        "label": "프로젝트 트리",
        "role": "project",
        "state": "error" if project_error else ("ready" if project_children else "empty"),
        "children": project_children,
    }
    evidence_tree = {
        "label": "임시 Explorer 근거",
        "role": "evidence",
        "state": "missing",
        "children": [],
    }
    if explorer_evidence_path.exists() or explorer_evidence_path.is_symlink():
        try:
            evidence_root = explorer_evidence_path.resolve(strict=True)
            evidence_root.relative_to(project_root)
            if explorer_evidence_path.is_symlink() or not evidence_root.is_dir():
                raise ValueError
            evidence_budget = {"entries": 0, "truncated": False}
            evidence_children, evidence_error = tree_children(
                evidence_root, evidence_root, 0, evidence_budget, False
            )
            evidence_tree["children"] = evidence_children
            evidence_tree["state"] = (
                "error" if evidence_error else ("ready" if evidence_children else "empty")
            )
        except (FileNotFoundError, OSError, ValueError):
            evidence_tree["state"] = "error"
            evidence_budget = {"entries": 0, "truncated": False}
    else:
        evidence_budget = {"entries": 0, "truncated": False}
    return {
        "trees": [project_tree, evidence_tree],
        "limits": {
            "maxDepth": tree_max_depth,
            "maxEntries": tree_max_entries,
            "maxResponseBytes": tree_max_response_bytes,
        },
        "truncated": project_budget["truncated"] or evidence_budget["truncated"],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.serve(send_body=True)

    def do_HEAD(self) -> None:
        self.serve(send_body=False)

    def serve(self, send_body: bool) -> None:
        if urlsplit(self.path).path == "/api/explorer-tree":
            payload = json.dumps(explorer_trees(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(payload) > tree_max_response_bytes:
                self.send_error(500, "Workspace tree response exceeded its deterministic size limit")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body:
                self.wfile.write(payload)
            return
        if urlsplit(self.path).path == "/api/project-skills":
            payload = json.dumps({"skills": project_skills()}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if send_body:
                self.wfile.write(payload)
            return
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
            self.send_error(404, "Workspace file not found")
            return
        if not candidate.is_file():
            self.send_error(404, "Workspace file not found")
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
print(f"Serving local Workspace UI and Human Specifications read-only at {url}")
webbrowser.open(url)
try:
    server.serve_forever()
finally:
    server.server_close()
PY
