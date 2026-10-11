"""Pinned Archify boundary: official validation/delivery, private scratch, no-clobber output."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

LOCK = json.loads(Path(__file__).with_name("archify-lock.json").read_text(encoding="utf-8"))
TYPES = ("architecture", "sequence")


class ArchifyError(Exception):
    """An actionable renderer or browser failure."""


def unlinked_path(value: Path) -> Path:
    """Reject traversal and symlinks before resolving any filesystem operation."""
    value = value.expanduser()
    if ".." in value.parts:
        raise ValueError("Path traversal ('..') is not allowed.")
    path = Path(os.path.abspath(value))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Symlink paths are not allowed: {part}")
    return path


def tree_digest(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unsupported renderer entry: {path}")
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{path.relative_to(root).as_posix()}\0{digest}\n")
    return hashlib.sha256("".join(entries).encode()).hexdigest()


def renderer(root: Path) -> tuple[str, Path]:
    root = unlinked_path(root)
    if not root.is_dir():
        raise ArchifyError("Renderer is missing. Run archify.py install --tool-dir <directory> first.")
    if tree_digest(root) != LOCK["treeSha256"]:
        raise ArchifyError("Renderer integrity mismatch. Install the pinned version into a new directory.")
    node = shutil.which("node")
    if not node:
        raise ArchifyError("Node.js >=18 is required; 'node' was not found on PATH.")
    version = run_process([node, "--version"]).stdout.strip()
    try:
        major = int(version.removeprefix("v").split(".")[0])
    except ValueError as error:
        raise ArchifyError(f"Could not identify Node.js version: {version}") from error
    if major < 18:
        raise ArchifyError(f"Node.js >=18 is required; found {version}.")
    return node, root / "bin" / "archify.mjs"


def run_process(argv: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as error:
        raise ArchifyError(f"Could not start {argv[0]}: {error}") from error


def install(root: Path) -> dict:
    root = unlinked_path(root)
    if os.path.lexists(root):
        raise ValueError("Install target already exists; choose a new directory. Nothing was replaced.")
    if not root.parent.is_dir():
        raise ValueError("Install target parent must already exist in run storage or an agreed dependency location.")
    # Dependencies are runtime material, never a project Document or source directory.
    if (root.parent / ".git").exists() or any((p / ".git").exists() for p in root.parents):
        raise ValueError("Install outside the project/Git checkout, in run storage or an agreed dependency location.")
    try:
        with urllib.request.urlopen(LOCK["archive"], timeout=30) as response:
            archive = response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise ArchifyError(f"Could not download pinned Archify: {error}. Retry install when the network is available.") from error
    if hashlib.sha256(archive).hexdigest() != LOCK["archiveSha256"]:
        raise ArchifyError("Official archive checksum mismatch; no renderer was installed.")
    prefix = f"archify-{LOCK['commit']}/archify/"
    with tempfile.TemporaryDirectory(prefix="agent-factory-archify-install-") as scratch:
        staged = Path(scratch) / "renderer"
        staged.mkdir()
        try:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
                for member in source.getmembers():
                    if not member.name.startswith(prefix) or member.isdir():
                        continue
                    relative = PurePosixPath(member.name[len(prefix):])
                    if not member.isfile() or relative.is_absolute() or ".." in relative.parts:
                        raise ArchifyError("Unsafe archive entry; no renderer was installed.")
                    target = staged.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(member) as stream, target.open("xb") as output:
                        shutil.copyfileobj(stream, output)
            if tree_digest(staged) != LOCK["treeSha256"]:
                raise ArchifyError("Extracted renderer checksum mismatch; no renderer was installed.")
            # mkdir is exclusive, and copytree never merges an independently created target.
            shutil.copytree(staged, root)
        except tarfile.TarError as error:
            raise ArchifyError(f"Invalid Archify archive: {error}") from error
    return {"ok": True, "toolDir": str(root), "version": LOCK["version"], "commit": LOCK["commit"]}


def project_path(value: Path, root: Path) -> Path:
    path = unlinked_path(value if value.is_absolute() else root / value)
    if not path.is_relative_to(root):
        raise ValueError("Path must stay inside --project-root.")
    return path


def artifact_path(value: Path, root: Path) -> Path:
    path = project_path(value, root)
    artifact = root / "docs" / "artifact"
    if not path.is_relative_to(artifact) or len(path.relative_to(artifact).parts) < 3:
        raise ValueError("Output must be docs/artifact/<category>/<topic>/<name>.html.")
    if path.suffix.lower() != ".html":
        raise ValueError("Output must have the .html extension.")
    if not path.parent.is_dir():
        raise ValueError("Output parent does not exist. Prepare the agreed docs/artifact/<category>/<topic>/ directory first.")
    return path


def document_input(value: Path, root: Path) -> tuple[Path, bytes, str]:
    path = project_path(value, root)
    docs = root / "docs"
    if (not path.is_relative_to(docs) or path.suffix.lower() != ".json"
            or path.relative_to(docs).parts[0] not in ("skills", "refined")):
        raise ValueError("Input must be a JSON asset in a docs/ Document package.")
    packages = [p.parent for p in path.parents if p.name == "assets" and p.is_relative_to(docs)]
    if not any((p / "SKILL.md").is_file() for p in packages):
        raise ValueError("Input must be under a Document package assets/ with a SKILL.md entry.")
    if not path.is_file():
        raise ValueError(f"JSON input does not exist: {path}")
    raw = path.read_bytes()
    return path, raw, parse_document(raw, str(path))["diagram_type"]


def parse_document(raw: bytes, source: str) -> dict:
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f"Invalid JSON in {source}: {error}") from error
    kind = document.get("diagram_type") if isinstance(document, dict) else None
    if kind not in TYPES:
        raise ValueError(f"Unsupported diagram_type {kind!r}. Supported here: architecture, sequence; ERD is unsupported.")
    # The authored output is validated officially, but never used as a write destination.
    # Remote/custom brand fetching is outside this local rendering boundary.
    nodes = []
    for field in ("components", "participants"):
        if isinstance(document.get(field), list):
            nodes.extend(document[field])
    for node in nodes:
        if isinstance(node, dict) and "brand" in node:
            brand = node["brand"]
            if isinstance(brand, dict) or (isinstance(brand, str) and "://" in brand):
                raise ValueError("Remote brand URLs are unsupported in this local renderer; use a built-in brand or omit brand.")
    return document


class DiagramHTML(HTMLParser):
    """Extract the authored SVG and pinned CSS, excluding the standalone viewer scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.svg = []
        self.styles = []
        self.depth = 0
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag == "style" and not self.depth:
            self.in_style = True
        if tag == "svg":
            self.depth += 1
        if self.depth:
            self.svg.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if self.depth:
            self.svg.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.depth:
            self.svg.append(f"</{tag}>")
        if tag == "svg":
            self.depth -= 1
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.depth:
            self.svg.append(data)
        elif self.in_style:
            self.styles.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def render_snapshot(node: str, cli: Path, raw: bytes, kind: str, stage: Path) -> tuple[dict, dict, bytes]:
    snapshot = stage / "input.json"
    snapshot.write_bytes(raw)
    validation = official([node, str(cli), "validate", kind, str(snapshot), "--json"], stage)
    generated = stage / "diagram.html"
    delivery = official([node, str(cli), "deliver", kind, str(snapshot), str(generated), "--json"], stage)
    return validation, delivery, generated.read_bytes()


def official(command: list[str], cwd: Path) -> dict:
    result = run_process(command, cwd=cwd)
    try:
        report = json.loads(result.stdout)
    except ValueError:
        report = None
    if result.returncode:
        diagnostic = result.stdout.strip() or result.stderr.strip() or f"exit {result.returncode}"
        if result.stdout.strip() and result.stderr.strip():
            diagnostic += "\n" + result.stderr.strip()
        raise ArchifyError(f"Official Archify failed: {diagnostic}")
    if not isinstance(report, dict):
        raise ArchifyError("Official Archify returned an invalid JSON report.")
    if report.get("ok") is not True:
        raise ArchifyError(f"Official Archify did not confirm success: {result.stdout.strip()}")
    return report


def publish_html(path: Path, html: bytes):
    """Exclusive creation through unlinked directory descriptors on POSIX."""
    if os.name == "nt":
        unlinked_path(path)
        with path.open("xb") as stream:
            stream.write(html)
        return
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        target = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=fd)
        with os.fdopen(target, "wb") as stream:
            stream.write(html)
    finally:
        os.close(fd)


def open_artifact(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"HTML artifact does not exist: {path}")
    if sys.platform == "win32":
        os.startfile(str(path))
    else:
        name = "open" if sys.platform == "darwin" else "xdg-open"
        opener = shutil.which(name)
        if not opener:
            raise ArchifyError(f"Browser opener '{name}' is unavailable. Open {path.as_uri()} on the machine hosting these files.")
        result = run_process([opener, path.as_uri()])
        if result.returncode:
            raise ArchifyError(f"Browser could not be opened: {result.stderr.strip()}. HTML remains at {path}.")
    return {"ok": True, "opened": True, "html": str(path), "uri": path.as_uri()}


def execute(args) -> dict:
    if args.command == "install":
        return install(args.tool_dir)
    if args.command == "preview":
        raw = sys.stdin.buffer.read()
        document = parse_document(raw, "editor")
        node, cli = renderer(args.tool_dir)
        with tempfile.TemporaryDirectory(prefix="agent-factory-archify-preview-") as scratch:
            _, _, html = render_snapshot(node, cli, raw, document["diagram_type"], Path(scratch))
        parsed = DiagramHTML()
        parsed.feed(html.decode("utf-8"))
        if not parsed.svg or parsed.depth:
            raise ArchifyError("Official renderer returned no complete SVG diagram.")
        return {"ok": True, "title": document["meta"]["title"], "type": document["diagram_type"],
                "svg": "".join(parsed.svg), "styles": "".join(parsed.styles),
                "version": LOCK["version"], "commit": LOCK["commit"]}
    root = unlinked_path(args.project_root)
    if not root.is_dir():
        raise ValueError("--project-root must be an existing directory.")
    if args.command == "open":
        return open_artifact(artifact_path(args.output, root))
    source, raw, kind = document_input(args.input, root)
    output = None
    if args.command == "render":
        output = artifact_path(args.output, root)
        if os.path.lexists(output):
            raise ValueError("Output already exists; choose a new filename. Input and existing files were preserved.")
    node, cli = renderer(args.tool_dir)
    with tempfile.TemporaryDirectory(prefix="agent-factory-archify-") as scratch:
        stage = Path(scratch)
        if output is None:
            snapshot = stage / "input.json"
            snapshot.write_bytes(raw)
            validation = official([node, str(cli), "validate", kind, str(snapshot), "--json"], stage)
        else:
            validation, delivery, html = render_snapshot(node, cli, raw, kind, stage)
        result = {"ok": True, "input": str(source), "type": kind,
                  "inputSha256": hashlib.sha256(raw).hexdigest(), "version": LOCK["version"],
                  "commit": LOCK["commit"], "validation": validation}
        if output is None:
            return result
        # Delivery sidecars are scratch only: their bindings describe the private staged
        # output, not the published artifact. No existing public file is ever replaced.
        output = artifact_path(args.output, root)
        publish_html(output, html)
        result.update(html=str(output), uri=output.as_uri(), htmlSha256=hashlib.sha256(html).hexdigest(),
                      delivery=delivery, opened=False)
    if args.open:
        try:
            open_artifact(output)
            result["opened"] = True
        except (OSError, ValueError, ArchifyError) as error:
            result.update(ok=False, error=str(error))
    return result
