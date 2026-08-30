#!/usr/bin/env python3
"""Install and serve Agent Factory Workspace browser assets."""

from __future__ import annotations

import argparse
import functools
import ipaddress
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit
import webbrowser


WORKSPACE_RELATIVE_PATH = Path(".agent-factory/workspace")
HUMAN_SPECIFICATION_RELATIVE_PATH = Path(".agent-factory/document/specification")
PROJECT_SKILLS_RELATIVE_PATH = Path(".codex/skills")
DOCUMENT_RELATIVE_PATH = Path(".agent-factory/document")
PACKAGED_ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "browser"
PACKAGED_LAUNCHER = Path(__file__).resolve().parents[1] / "assets" / "workspace.sh"
PACKAGED_WORKSPACE_IGNORE = Path(__file__).resolve().parents[1] / "assets" / "workspace.gitignore"
PACKAGED_BROWSER_ASSET_PATHS = frozenset(
    {
        Path("index.html"),
        Path("styles.css"),
        Path("app.js"),
        Path("THIRD_PARTY_NOTICES.txt"),
        Path("vendor/tabulator/6.5.2/tabulator.min.js"),
        Path("vendor/tabulator/6.5.2/tabulator.min.css"),
        Path("vendor/tabulator/6.5.2/LICENSE"),
    }
)
DEFAULT_HOST = "127.0.0.1"
FORBIDDEN_PORT = 8000
PORT_STATE_RELATIVE_PATH = WORKSPACE_RELATIVE_PATH / "port.json"
PORT_STATE_VERSION = 1
PORT_STATE_MAX_BYTES = 128
ACTIVITY_DIRECTORIES = ("explorer", "skills")
TREE_MAX_DEPTH = 5
TREE_MAX_ENTRIES = 120
TREE_MAX_RESPONSE_BYTES = 128 * 1024
PROJECT_TREE_EXCLUDED_PATHS = {
    PurePosixPath(".git"),
    PurePosixPath(".codex"),
    PurePosixPath(".agent-factory/agent"),
    PurePosixPath(".agent-factory/document"),
    PurePosixPath(".agent-factory/workspace"),
}


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
    if resolved_asset_root == PACKAGED_ASSET_ROOT.resolve(strict=True):
        discovered = {relative_path for _source, relative_path in files}
        missing = sorted(PACKAGED_BROWSER_ASSET_PATHS - discovered)
        unexpected = sorted(discovered - PACKAGED_BROWSER_ASSET_PATHS)
        if missing or unexpected:
            details = [
                *(f"missing {path.as_posix()}" for path in missing),
                *(f"unallowlisted {path.as_posix()}" for path in unexpected),
            ]
            raise ViewerError(
                "packaged browser asset allowlist mismatch: " + ", ".join(details)
            )
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

    workspace_root = project_root / WORKSPACE_RELATIVE_PATH
    destination_root = workspace_root / "common"
    _resolved_within(project_root, workspace_root, "Workspace directory")
    _resolved_within(project_root, destination_root, "common asset directory")

    activity_conflicts: list[Path] = []
    activity_directories: list[Path] = []
    for name in ACTIVITY_DIRECTORIES:
        activity_directory = workspace_root / name
        _resolved_within(project_root, activity_directory, f"{name} Activity directory")
        if activity_directory.is_symlink() or (
            activity_directory.exists() and not activity_directory.is_dir()
        ):
            activity_conflicts.append(activity_directory)
        activity_directories.append(activity_directory)

    try:
        resolved_launcher_source = launcher_source.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(f"packaged Workspace launcher is missing: {launcher_source}") from exc
    if launcher_source.is_symlink() or not resolved_launcher_source.is_file():
        raise ViewerError(
            f"packaged Workspace launcher must be a regular file: {launcher_source}"
        )

    launcher_destination = project_root / "workspace.sh"
    install_launcher = not (
        launcher_destination.exists() or launcher_destination.is_symlink()
    )

    ignore_destination = workspace_root / ".gitignore"
    try:
        ignore_source = PACKAGED_WORKSPACE_IGNORE.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ViewerError(
            f"packaged Workspace ignore rules are missing: {PACKAGED_WORKSPACE_IGNORE}"
        ) from exc
    if PACKAGED_WORKSPACE_IGNORE.is_symlink() or not ignore_source.is_file():
        raise ViewerError(
            f"packaged Workspace ignore rules must be a regular file: {PACKAGED_WORKSPACE_IGNORE}"
        )
    if ignore_destination.exists() or ignore_destination.is_symlink():
        try:
            ignore_rule_present = (
                not ignore_destination.is_symlink()
                and ignore_destination.is_file()
                and "/port.json"
                in ignore_destination.read_text(encoding="utf-8").splitlines()
            )
        except (OSError, UnicodeError):
            ignore_rule_present = False
        if not ignore_rule_present:
            activity_conflicts.append(ignore_destination)

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

    all_conflicts = activity_conflicts + conflicts
    if all_conflicts:
        rendered = "\n".join(f"  - {path}" for path in all_conflicts)
        suffix = "" if force else "\nRe-run init with --force to replace differing files."
        raise ViewerError(f"Workspace initialization conflicts:\n{rendered}{suffix}")

    for activity_directory in activity_directories:
        activity_directory.mkdir(parents=True, exist_ok=True)
    if not ignore_destination.exists():
        _atomic_copy_new(ignore_source, ignore_destination, 0o644)
    document_root = project_root / DOCUMENT_RELATIVE_PATH
    _resolved_within(project_root, document_root, "Document directory")
    for type_root in ("original", "processed", "specification"):
        (document_root / type_root).mkdir(parents=True, exist_ok=True)

    launcher_installed = False
    if install_launcher:
        launcher_installed = _atomic_copy_new(
            resolved_launcher_source, launcher_destination, 0o755
        )
    for source, destination in planned:
        _resolved_within(project_root, destination.parent, "browser asset directory")
        _atomic_copy(source, destination)
    return len(planned), unchanged, launcher_installed


def resolve_request_path(served_roots: dict[str, Path], request_target: str) -> tuple[Path, bool]:
    """Map an allowlisted URL prefix to its local root safely."""

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

    if not relative.parts:
        raise ViewerError("request path does not select a local document root")
    prefix = relative.parts[0]
    root = served_roots.get(prefix)
    if root is None:
        raise ViewerError("request path does not select an allowlisted local root")
    root = root.resolve(strict=True)
    candidate = root.joinpath(*relative.parts[1:]).resolve(strict=False)
    if not _is_within(root, candidate):
        raise ViewerError("request path escapes the served Workspace tree")
    return candidate, decoded_path.endswith("/")


def discover_project_skills(project_root: Path) -> list[dict[str, str]]:
    """Describe only actual, direct Project Skills in the owning project."""

    skills_root = _resolved_within(
        project_root,
        project_root / PROJECT_SKILLS_RELATIVE_PATH,
        "Project Skill directory",
    )
    if not skills_root.exists():
        return []
    if skills_root.is_symlink() or not skills_root.is_dir():
        raise ViewerError(f"Project Skill path is not a safe directory: {skills_root}")

    skills: list[dict[str, str]] = []
    for candidate in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        entry_point = candidate / "SKILL.md"
        if entry_point.is_symlink() or not entry_point.is_file():
            continue
        skills.append(
            {
                "name": candidate.name,
                "href": f"/project-skills/{quote(candidate.name, safe='')}/SKILL.md",
            }
        )
    return skills


def _project_tree_path_is_excluded(relative_path: PurePosixPath) -> bool:
    return any(
        relative_path == excluded or excluded in relative_path.parents
        for excluded in PROJECT_TREE_EXCLUDED_PATHS
    )


def _tree_children(
    root: Path,
    directory: Path,
    *,
    depth: int,
    budget: dict[str, int | bool],
    exclude_project_paths: bool,
) -> tuple[list[dict[str, object]], bool]:
    """Return bounded metadata only, without following any symbolic link."""

    if depth >= TREE_MAX_DEPTH:
        budget["truncated"] = True
        return [], False
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: (entry.name.casefold(), entry.name))
    except OSError:
        return [], True

    children: list[dict[str, object]] = []
    had_error = False
    for entry in entries:
        if int(budget["entries"]) >= TREE_MAX_ENTRIES:
            budget["truncated"] = True
            break
        candidate = Path(entry.path)
        try:
            relative = PurePosixPath(candidate.relative_to(root).as_posix())
        except ValueError:
            continue
        if exclude_project_paths and _project_tree_path_is_excluded(relative):
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

        budget["entries"] = int(budget["entries"]) + 1
        node: dict[str, object] = {
            "name": entry.name,
            "kind": "directory" if is_directory else "file",
        }
        if is_directory:
            descendants, descendant_error = _tree_children(
                root,
                candidate,
                depth=depth + 1,
                budget=budget,
                exclude_project_paths=exclude_project_paths,
            )
            node["children"] = descendants
            if descendant_error:
                node["state"] = "error"
                had_error = True
            elif not descendants:
                node["state"] = "empty"
            if depth + 1 >= TREE_MAX_DEPTH:
                node["truncated"] = True
                budget["truncated"] = True
        children.append(node)
    return children, had_error


def discover_explorer_trees(project_root: Path) -> dict[str, object]:
    """Project and classified Document trees for the internal read-only projection."""

    resolved_project = project_root.resolve(strict=True)
    project_budget: dict[str, int | bool] = {"entries": 0, "truncated": False}
    project_children, project_error = _tree_children(
        resolved_project,
        resolved_project,
        depth=0,
        budget=project_budget,
        exclude_project_paths=True,
    )
    project_tree: dict[str, object] = {
        "label": "프로젝트 트리",
        "role": "project",
        "state": "error" if project_error else ("ready" if project_children else "empty"),
        "children": project_children,
    }

    evidence_path = resolved_project / DOCUMENT_RELATIVE_PATH
    evidence_tree: dict[str, object] = {
        "label": "분류된 Document",
        "role": "evidence",
        "state": "missing",
        "children": [],
    }
    if evidence_path.exists() or evidence_path.is_symlink():
        try:
            evidence_root = evidence_path.resolve(strict=True)
            if evidence_path.is_symlink() or not evidence_root.is_dir() or not _is_within(
                resolved_project, evidence_root
            ):
                raise ViewerError("Document path is not a safe project directory")
            evidence_budget: dict[str, int | bool] = {"entries": 0, "truncated": False}
            evidence_children, evidence_error = _tree_children(
                evidence_root,
                evidence_root,
                depth=0,
                budget=evidence_budget,
                exclude_project_paths=False,
            )
            evidence_tree["children"] = evidence_children
            evidence_tree["state"] = (
                "error" if evidence_error else ("ready" if evidence_children else "empty")
            )
        except (OSError, ViewerError):
            evidence_tree["state"] = "error"
            evidence_budget = {"entries": 0, "truncated": False}
    else:
        evidence_budget = {"entries": 0, "truncated": False}

    return {
        "trees": [project_tree, evidence_tree],
        "limits": {
            "maxDepth": TREE_MAX_DEPTH,
            "maxEntries": TREE_MAX_ENTRIES,
            "maxResponseBytes": TREE_MAX_RESPONSE_BYTES,
        },
        "truncated": bool(project_budget["truncated"]) or bool(evidence_budget["truncated"]),
    }


def _json_response_bytes(payload: object) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > TREE_MAX_RESPONSE_BYTES:
        raise ViewerError("Workspace tree response exceeded its deterministic size limit")
    return body


class WorkspaceRequestHandler(BaseHTTPRequestHandler):
    """Read-only handler constrained to one resolved Workspace tree."""

    server_version = "AgentFactoryWorkspace/1"

    def __init__(
        self,
        *args: object,
        served_roots: dict[str, Path],
        project_root: Path,
        **kwargs: object,
    ) -> None:
        self.served_roots = {
            prefix: root.resolve(strict=True) for prefix, root in served_roots.items()
        }
        self.project_root = project_root.resolve(strict=True)
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._serve(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._serve(send_body=False)

    def _serve(self, send_body: bool) -> None:
        if urlsplit(self.path).path == "/api/explorer-tree":
            try:
                payload = _json_response_bytes(discover_explorer_trees(self.project_root))
            except (OSError, ViewerError) as exc:
                self.send_error(500, str(exc))
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
            try:
                payload = json.dumps(
                    {"skills": discover_project_skills(self.project_root)},
                    ensure_ascii=False,
                ).encode("utf-8")
            except ViewerError as exc:
                self.send_error(500, str(exc))
                return
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
            candidate, trailing_slash = resolve_request_path(self.served_roots, self.path)
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
            self.send_error(404, "Workspace file not found")
            return
        if not any(_is_within(root, resolved_file) for root in self.served_roots.values()) or not resolved_file.is_file():
            self.send_error(404, "Workspace file not found")
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


def _read_port_state(project_root: Path) -> int | None:
    state_path = project_root / PORT_STATE_RELATIVE_PATH
    _resolved_within(project_root, state_path, "Workspace port state")
    if not state_path.exists() and not state_path.is_symlink():
        return None
    if state_path.is_symlink() or not state_path.is_file():
        raise ViewerError(f"Workspace port state is not a regular file: {state_path}")
    try:
        if state_path.stat().st_size > PORT_STATE_MAX_BYTES:
            raise ViewerError(f"Workspace port state is too large: {state_path}")
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ViewerError(f"Workspace port state is malformed: {state_path}") from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "port"}:
        raise ViewerError(f"Workspace port state has an invalid shape: {state_path}")
    port = payload["port"]
    if (
        payload["version"] != PORT_STATE_VERSION
        or not isinstance(port, int)
        or isinstance(port, bool)
        or port not in range(1, 65536)
        or port == FORBIDDEN_PORT
    ):
        raise ViewerError(f"Workspace port state contains an invalid port: {state_path}")
    return port


def _publish_port_state(project_root: Path, port: int) -> None:
    state_path = project_root / PORT_STATE_RELATIVE_PATH
    workspace_root = state_path.parent
    _resolved_within(project_root, workspace_root, "Workspace port state directory")
    _resolved_within(project_root, state_path, "Workspace port state")
    if workspace_root.is_symlink() or not workspace_root.is_dir():
        raise ViewerError(f"Workspace port state directory is unsafe: {workspace_root}")
    if state_path.is_symlink() or (state_path.exists() and not state_path.is_file()):
        raise ViewerError(f"Workspace port state is not a regular file: {state_path}")
    body = json.dumps(
        {"version": PORT_STATE_VERSION, "port": port},
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{state_path.name}.", dir=workspace_root, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(body)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, state_path)
    except OSError as exc:
        raise ViewerError(f"cannot publish Workspace port state: {exc}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _validate_requested_port(port: int | None) -> None:
    if port is None:
        return
    if isinstance(port, bool) or port not in range(1, 65536):
        raise ViewerError("--port must be between 1 and 65535")
    if port == FORBIDDEN_PORT:
        raise ViewerError(f"port {FORBIDDEN_PORT} is reserved and cannot be used")


def serve(project_root: Path, host: str, port: int | None, allow_non_loopback: bool, open_browser: bool) -> None:
    workspace_root = project_root / WORKSPACE_RELATIVE_PATH
    resolved_root = _resolved_within(
        project_root, workspace_root, "served Workspace directory"
    )
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise ViewerError(
            f"Workspace directory does not exist: {workspace_root}; run init first"
        )
    human_specification_root = _resolved_within(
        project_root,
        project_root / HUMAN_SPECIFICATION_RELATIVE_PATH,
        "served Human Specification directory",
    )
    if not human_specification_root.exists() or not human_specification_root.is_dir():
        raise ViewerError(
            f"Human Specification directory does not exist: {human_specification_root}; run init first"
        )
    _validate_requested_port(port)
    stored_port = _read_port_state(project_root)
    served_roots = {
        "common": resolved_root / "common",
        "explorer": resolved_root / "explorer",
        "skills": resolved_root / "skills",
        "planning": human_specification_root,
    }
    project_skills_root = _resolved_within(
        project_root,
        project_root / PROJECT_SKILLS_RELATIVE_PATH,
        "served Project Skill directory",
    )
    if project_skills_root.exists():
        if project_skills_root.is_symlink() or not project_skills_root.is_dir():
            raise ViewerError(
                f"Project Skill path is not a safe directory: {project_skills_root}"
            )
        served_roots["project-skills"] = project_skills_root
    handler = functools.partial(
        WorkspaceRequestHandler,
        served_roots=served_roots,
        project_root=project_root,
    )

    def bind(candidate_port: int) -> ThreadingHTTPServer:
        addresses = _resolved_addresses(host, candidate_port)
        if not addresses_are_loopback(addresses) and not allow_non_loopback:
            raise ViewerError(
                f"refusing non-loopback bind host {host!r}; "
                "pass --allow-non-loopback to explicitly permit network exposure"
            )
        family, sockaddr = addresses[0]

        class AddressFamilyServer(ThreadingHTTPServer):
            address_family = family
            daemon_threads = True

        return AddressFamilyServer(sockaddr, handler)

    selected_port = port if port is not None else stored_port
    server: ThreadingHTTPServer | None = None
    if selected_port is not None:
        try:
            server = bind(selected_port)
        except OSError as exc:
            if port is not None:
                raise ViewerError(f"cannot bind {host}:{port}: {exc}") from exc
    if server is None:
        for _attempt in range(32):
            try:
                candidate = bind(0)
            except OSError as exc:
                raise ViewerError(f"cannot allocate an available loopback port: {exc}") from exc
            if int(candidate.server_address[1]) != FORBIDDEN_PORT:
                server = candidate
                break
            candidate.server_close()
        if server is None:
            raise ViewerError(f"could not allocate a port other than {FORBIDDEN_PORT}")

    actual_port = int(server.server_address[1])
    try:
        _publish_port_state(project_root, actual_port)
    except ViewerError:
        server.server_close()
        raise
    browser_host = host
    if host in {"0.0.0.0", "::", ""}:
        browser_host = DEFAULT_HOST
    if ":" in browser_host and not browser_host.startswith("["):
        browser_host = f"[{browser_host}]"
    url = f"http://{browser_host}:{actual_port}/common/"
    print(f"Serving local Workspace UI and Human Specifications read-only at {url}")
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
        description="Install or serve Agent Factory Workspace browser assets."
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

    serve_parser = subparsers.add_parser("serve", help="serve the existing Workspace tree read-only")
    serve_parser.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default: {DEFAULT_HOST})")
    serve_parser.add_argument(
        "--port",
        type=int,
        help="bind and persist this port (automatic per-project allocation when omitted; 8000 is reserved)",
    )
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
    requested_port = getattr(args, "port", None)
    if requested_port is not None and requested_port not in range(1, 65536):
        parser.error("--port must be between 1 and 65535")
    if requested_port == FORBIDDEN_PORT:
        parser.error(f"port {FORBIDDEN_PORT} is reserved and cannot be used")

    try:
        project_root = resolve_project_root(args.project_root)
        if args.command == "init":
            installed, unchanged, launcher_installed = install_assets(
                project_root, PACKAGED_ASSET_ROOT, args.force
            )
            destination = project_root / WORKSPACE_RELATIVE_PATH / "common"
            print(f"Installed {installed} browser asset(s) in {destination}; {unchanged} unchanged.")
            if launcher_installed:
                print(f"Installed project launcher at {project_root / 'workspace.sh'}.")
            else:
                print(f"Preserved existing project launcher at {project_root / 'workspace.sh'}.")
        else:
            serve(project_root, args.host, args.port, args.allow_non_loopback, args.open)
    except ViewerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
