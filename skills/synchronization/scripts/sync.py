#!/usr/bin/env python3
"""Manage and resolve project-owned Agent Factory sync destinations."""

from __future__ import annotations

import argparse
import errno
import json
import os
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
SCHEMA_PATH = SKILL_ROOT / "assets" / "schema" / "sync.schema.json"
CONFIG_RELATIVE_PATH = Path(".agent-factory/sync.json")
SCHEMA_VERSION = "1.0.0"
DEFAULT_DESTINATIONS = {
    "google-drive": Path("source/google/drive"),
    "google-gmail": Path("source/google/mail"),
}
DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
FILE_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class SyncConfigError(RuntimeError):
    pass


def load_schema() -> dict[str, Any]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncConfigError(f"cannot load sync schema: {error}") from error
    Draft202012Validator.check_schema(schema)
    return schema


def validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def git_top_level(start: Path) -> Path:
    probe = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        detail = probe.stderr.strip() or "not inside a Git repository"
        raise SyncConfigError(f"cannot resolve Git project root: {detail}")
    return Path(probe.stdout.strip()).resolve()


def resolve_project_root(
    project_root: str | Path | None = None, *, cwd: Path | None = None
) -> Path:
    if project_root is None:
        return git_top_level((cwd or Path.cwd()).resolve())
    requested = Path(project_root).expanduser().resolve()
    discovered = git_top_level(requested)
    if requested != discovered:
        raise SyncConfigError(
            f"project root does not match Git top-level: "
            f"requested={requested}, git={discovered}"
        )
    return requested


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_RELATIVE_PATH


def empty_config() -> dict[str, Any]:
    return {"schemaVersion": SCHEMA_VERSION, "sources": {}}


def validate_config(value: Any, path: Path) -> dict[str, Any]:
    errors = sorted(validator().iter_errors(value), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors
        )
        raise SyncConfigError(f"invalid sync config {path}: {detail}")
    assert isinstance(value, dict)
    return value


def open_agent_factory(root_descriptor: int, *, create: bool) -> int | None:
    # Reopen after a create race and require a real directory without following
    # symlinks; the project-root descriptor remains the trust anchor.
    try:
        return os.open(".agent-factory", DIRECTORY_OPEN_FLAGS, dir_fd=root_descriptor)
    except FileNotFoundError:
        if not create:
            return None
        try:
            os.mkdir(".agent-factory", mode=0o755, dir_fd=root_descriptor)
        except FileExistsError:
            pass
        try:
            return os.open(
                ".agent-factory", DIRECTORY_OPEN_FLAGS, dir_fd=root_descriptor
            )
        except OSError as error:
            raise SyncConfigError(
                f"cannot safely open canonical configuration directory: {error}"
            ) from error
    except OSError as error:
        raise SyncConfigError(
            f"cannot safely open canonical configuration directory: {error}"
        ) from error


def load_config(project_root: Path) -> dict[str, Any]:
    path = config_path(project_root)
    root_descriptor = -1
    agent_factory_descriptor = -1
    try:
        root_descriptor = os.open(project_root, DIRECTORY_OPEN_FLAGS)
        opened = open_agent_factory(root_descriptor, create=False)
        if opened is None:
            return empty_config()
        agent_factory_descriptor = opened
        try:
            descriptor = os.open(
                "sync.json",
                os.O_RDONLY | FILE_NOFOLLOW,
                dir_fd=agent_factory_descriptor,
            )
        except FileNotFoundError:
            return empty_config()
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            os.close(descriptor)
            raise SyncConfigError(f"sync config must be a regular file: {path}")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise SyncConfigError(f"cannot read sync config {path}: {error}") from error
    finally:
        if agent_factory_descriptor >= 0:
            os.close(agent_factory_descriptor)
        if root_descriptor >= 0:
            os.close(root_descriptor)
    return validate_config(value, path)


def validate_destination_text(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise SyncConfigError("destination must be a non-empty path")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() and not candidate.parts:
        raise SyncConfigError("relative destination must identify a path below the project")
    if not candidate.is_absolute() and ".." in candidate.parts:
        raise SyncConfigError("relative destination must not contain '..'")
    return candidate


def reject_relative_symlink_escape(project_root: Path, candidate: Path) -> None:
    # Relative destinations promise project ownership, so even an intermediate
    # symlink would silently change that ownership boundary.
    current = project_root
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            raise SyncConfigError(
                f"relative destination must not traverse a symlink: {current}"
            )


def normalize_destination(project_root: Path, value: str) -> Path:
    candidate = validate_destination_text(value)
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    reject_relative_symlink_escape(project_root, candidate)
    return (project_root / candidate).resolve(strict=False)


def resolve_sync_destination(
    source: str,
    *,
    destination: str | Path | None = None,
    project_root: str | Path | None = None,
    cwd: Path | None = None,
) -> dict[str, str]:
    if source not in DEFAULT_DESTINATIONS:
        raise SyncConfigError(f"unsupported sync source: {source}")
    root = resolve_project_root(project_root, cwd=cwd)
    config = load_config(root)
    configured = config["sources"].get(source, {}).get("destination")
    if destination is not None:
        selected = str(destination)
        origin = "explicit"
    elif configured is not None:
        selected = configured
        origin = "config"
    else:
        selected = str(DEFAULT_DESTINATIONS[source])
        origin = "default"
    resolved = normalize_destination(root, selected)
    return {
        "source": source,
        "projectRoot": str(root),
        "destination": str(resolved),
        "origin": origin,
        "configPath": str(config_path(root)),
    }


def write_config(project_root: Path, value: dict[str, Any]) -> None:
    path = config_path(project_root)
    validate_config(value, path)
    root_descriptor = -1
    agent_factory_descriptor = -1
    temporary_name: str | None = None
    try:
        root_descriptor = os.open(project_root, DIRECTORY_OPEN_FLAGS)
        opened = open_agent_factory(root_descriptor, create=True)
        assert opened is not None
        agent_factory_descriptor = opened
        try:
            target = os.stat(
                "sync.json",
                dir_fd=agent_factory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target = None
        if target is not None:
            if stat.S_ISLNK(target.st_mode):
                raise SyncConfigError(f"sync config must not be a symlink: {path}")
            if not stat.S_ISREG(target.st_mode):
                raise SyncConfigError(f"sync config must be a regular file: {path}")
        for _ in range(32):
            temporary_name = f".sync.{secrets.token_hex(12)}.json"
            try:
                descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | FILE_NOFOLLOW,
                    0o600,
                    dir_fd=agent_factory_descriptor,
                )
                break
            except OSError as error:
                if error.errno != errno.EEXIST:
                    raise
        else:
            raise SyncConfigError("cannot allocate temporary sync config")
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Replace and then sync the containing directory so a successful return
        # means the selected filename, not only its bytes, reached stable state.
        os.replace(
            temporary_name,
            "sync.json",
            src_dir_fd=agent_factory_descriptor,
            dst_dir_fd=agent_factory_descriptor,
        )
        temporary_name = None
        os.fsync(agent_factory_descriptor)
    except SyncConfigError:
        raise
    except OSError as error:
        raise SyncConfigError(f"cannot safely write sync config {path}: {error}") from error
    finally:
        if temporary_name is not None and agent_factory_descriptor >= 0:
            try:
                os.unlink(temporary_name, dir_fd=agent_factory_descriptor)
            except FileNotFoundError:
                pass
        if agent_factory_descriptor >= 0:
            os.close(agent_factory_descriptor)
        if root_descriptor >= 0:
            os.close(root_descriptor)


def command_show(args: argparse.Namespace) -> None:
    root = resolve_project_root(args.project_root)
    value = load_config(root)
    print(
        json.dumps(
            {
                **value,
                "projectRoot": str(root),
                "configPath": str(config_path(root)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_set(args: argparse.Namespace) -> None:
    root = resolve_project_root(args.project_root)
    normalize_destination(root, args.destination)
    value = load_config(root)
    value["sources"][args.source] = {"destination": args.destination}
    write_config(root, value)
    print(
        json.dumps(
            {
                **resolve_sync_destination(args.source, project_root=root),
                "configuredDestination": args.destination,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_resolve(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            resolve_sync_destination(
                args.source,
                destination=args.destination,
                project_root=args.project_root,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


def command_check_schema(_: argparse.Namespace) -> None:
    schema = load_schema()
    print(
        json.dumps(
            {
                "valid": True,
                "schemaVersion": schema["properties"]["schemaVersion"]["const"],
                "path": str(SCHEMA_PATH),
            },
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage project-owned Agent Factory sync destinations."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    show = commands.add_parser("show")
    show.add_argument("--project-root", type=Path)
    show.set_defaults(handler=command_show)

    set_command = commands.add_parser("set")
    set_command.add_argument("--source", choices=sorted(DEFAULT_DESTINATIONS), required=True)
    set_command.add_argument("--destination", required=True)
    set_command.add_argument("--project-root", type=Path)
    set_command.set_defaults(handler=command_set)

    resolve = commands.add_parser("resolve")
    resolve.add_argument("--source", choices=sorted(DEFAULT_DESTINATIONS), required=True)
    resolve.add_argument("--destination")
    resolve.add_argument("--project-root", type=Path)
    resolve.set_defaults(handler=command_resolve)

    check_schema = commands.add_parser("check-schema")
    check_schema.set_defaults(handler=command_check_schema)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.handler(args)
        return 0
    except SyncConfigError as error:
        print(f"sync: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
