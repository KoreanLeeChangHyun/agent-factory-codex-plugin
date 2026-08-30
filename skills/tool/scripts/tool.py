#!/usr/bin/env python3
"""Inspect bounded Git and Playwright Tool profiles without owning their state."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


SCHEMA_VERSION = "0.1.0"
PROFILES = ("git.cli", "github.cli", "git-lfs.cli", "playwright.browser")
OPERATIONS = (
    "discover", "inspect", "health", "install", "update", "remove",
    "connect", "disconnect", "enable", "disable",
)
AUTHORITY_KINDS = (
    "native-executable", "project-cli", "mcp-server", "plugin", "host-capability",
)
MAX_OUTPUT = 64 * 1024
SAFE_VALUE = re.compile(r"^[^\x00\r\n]{1,2048}$")


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ToolError("invalid_arguments", message)


def observed_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(command: Sequence[str], *, cwd: Path | None = None) -> dict[str, Any]:
    try:
        process = subprocess.run(
            list(command), cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"status": "unavailable", "detail": type(error).__name__}
    output = process.stdout[:MAX_OUTPUT].strip()
    diagnostic = process.stderr.lower()
    unsupported = any(fragment in diagnostic for fragment in (
        "unknown flag: --json", "unknown shorthand flag", "unknown json field",
        "invalid json field", "invalid argument for --json",
    ))
    return {
        "status": "available" if process.returncode == 0 else "unavailable",
        "exitCode": process.returncode,
        "output": output,
        "outputTruncated": len(process.stdout) > MAX_OUTPUT,
        "failureReason": "structured-inspection-unsupported" if unsupported else None,
    }


def executable_observation(name: str, version_command: Sequence[str]) -> dict[str, Any]:
    resolved = shutil.which(name)
    if resolved is None:
        return {"status": "unavailable", "executable": None, "version": None, "packageAuthority": "unknown"}
    version = run((resolved, *version_command))
    return {
        "status": "available",
        "executable": str(Path(resolved).resolve()),
        "version": version.get("output") if version.get("status") == "available" else None,
        "versionStatus": version["status"],
        "packageAuthority": "unknown",
    }


def git_repository(target: Path) -> dict[str, Any]:
    resolved_git = shutil.which("git")
    if resolved_git is None:
        return {"status": "unavailable"}
    values: dict[str, Any] = {"status": "unknown", "target": str(target)}
    queries = {
        "worktreeRoot": ("rev-parse", "--show-toplevel"),
        "gitDirectory": ("rev-parse", "--absolute-git-dir"),
        "commonGitDirectory": ("rev-parse", "--path-format=absolute", "--git-common-dir"),
        "head": ("rev-parse", "--verify", "HEAD"),
        "branch": ("symbolic-ref", "--quiet", "--short", "HEAD"),
    }
    for key, arguments in queries.items():
        result = run((resolved_git, "-C", str(target), *arguments))
        values[key] = result.get("output") or None
    values["status"] = "available" if values["gitDirectory"] else "unavailable"
    values["detachedHead"] = bool(values["head"] and not values["branch"])
    return values


def github_auth(hostname: str) -> dict[str, Any]:
    resolved = shutil.which("gh")
    if resolved is None:
        return {"status": "unavailable", "hostname": hostname}
    result = run((
        resolved, "auth", "status", "--hostname", hostname, "--json", "hosts",
    ))
    if result.get("failureReason") == "structured-inspection-unsupported":
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unsupported",
        }
    try:
        document = json.loads(result.get("output", ""))
    except json.JSONDecodeError:
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unknown",
        }
    hosts = document.get("hosts") if isinstance(document, dict) else None
    if not isinstance(hosts, dict):
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unknown",
        }
    entries = hosts.get(hostname) if isinstance(hosts, dict) else None
    if not isinstance(entries, list):
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unknown",
        }
    if any(not isinstance(entry, dict) for entry in entries):
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unknown",
        }
    accounts = []
    for entry in entries:
        accounts.append({
            key: entry.get(key) for key in
            ("login", "active", "host", "state", "tokenSource", "scopes") if key in entry
        })
    if any(
        not isinstance(account.get("active"), bool)
        or not isinstance(account.get("state"), str)
        for account in accounts
    ):
        return {
            "status": "unknown", "hostname": hostname,
            "inspectionSupport": "unknown", "accounts": accounts,
        }
    authenticated = any(
        account.get("active") is True and account.get("state") == "success"
        for account in accounts
    )
    return {
        "status": "available" if authenticated else "unavailable",
        "hostname": hostname,
        "inspectionSupport": "supported",
        "accounts": accounts,
    }


def manifests(target: Path) -> list[str]:
    names = (
        "package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
        "yarn.lock", "pyproject.toml", "requirements.txt", "poetry.lock", "uv.lock",
    )
    return [str((target / name).resolve()) for name in names if (target / name).is_file()]


def playwright_observation(target: Path, authority_kind: str) -> dict[str, Any]:
    facts: dict[str, Any] = {"project": str(target), "manifests": manifests(target)}
    if authority_kind in {"mcp-server", "plugin", "host-capability"}:
        facts.update({"status": "unknown", "package": None, "browsers": "unknown"})
        return facts
    candidates = (
        (target / "node_modules" / ".bin" / "playwright", ("--version",)),
        (Path(shutil.which("playwright") or ""), ("--version",)),
    )
    for candidate, arguments in candidates:
        if str(candidate) != "." and candidate.is_file() and os.access(candidate, os.X_OK):
            version = run((str(candidate.resolve()), *arguments), cwd=target)
            facts.update({
                "status": "available", "package": str(candidate.resolve()),
                "version": version.get("output"), "versionStatus": version["status"],
                "browsers": "unknown", "systemDependencies": "unknown",
            })
            return facts
    facts.update({"status": "unavailable", "package": None, "browsers": "unknown"})
    return facts


def profile_document(args: argparse.Namespace) -> dict[str, Any]:
    target = args.target.resolve(strict=False)
    if not target.is_dir():
        raise ToolError("target_unavailable", "target must be an existing directory")
    if args.authority_reference and not SAFE_VALUE.fullmatch(args.authority_reference):
        raise ToolError("authority_invalid", "authority reference is invalid")
    default_authority = {
        "git.cli": "executable:git",
        "github.cli": "executable:gh",
        "git-lfs.cli": "executable:git-lfs",
        "playwright.browser": f"project:{target}",
    }[args.profile]
    authority = {
        "kind": args.authority_kind,
        "reference": args.authority_reference or default_authority,
    }
    capabilities = [f"{args.profile}.inspect", f"{args.profile}.execute"]
    if args.profile == "git.cli":
        facts = {"executable": executable_observation("git", ("--version",)), "repository": git_repository(target)}
    elif args.profile == "github.cli":
        facts = {"executable": executable_observation("gh", ("--version",)), "authentication": github_auth(args.hostname)}
    elif args.profile == "git-lfs.cli":
        facts = {"executable": executable_observation("git-lfs", ("version",)), "repository": git_repository(target), "activation": "unknown", "remoteAccess": "unknown"}
    else:
        facts = playwright_observation(target, args.authority_kind)
    operation = args.operation
    mutating = operation not in {"discover", "inspect", "health"}
    if args.profile == "playwright.browser":
        availability = str(facts.get("status", "unknown"))
    else:
        executable = facts.get("executable")
        availability = str(executable.get("status", "unknown")) if isinstance(executable, dict) else "unknown"
    state = availability
    if operation == "health" and availability == "available":
        if args.profile == "git.cli":
            repository = facts.get("repository")
            state = str(repository.get("status", "unknown")) if isinstance(repository, dict) else "unknown"
        elif args.profile == "github.cli":
            authentication = facts.get("authentication")
            state = str(authentication.get("status", "unknown")) if isinstance(authentication, dict) else "unknown"
        else:
            state = "unknown"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "tool-observation" if not mutating else "tool-lifecycle-route",
        "operation": operation,
        "profileId": args.profile,
        "capabilityIds": capabilities,
        "authority": authority,
        "exactTarget": str(target),
        "state": state,
        "facts": facts,
        "route": {
            "performed": False,
            "authorityPreserved": True,
            "requiresHumanApproval": mutating,
            "status": "provider-route-required" if mutating else "not-applicable",
        },
        "observedAt": observed_at(),
        "secretMaterialStored": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = Parser(
        prog="tool.py",
        description="Stateless bounded Git/Playwright discovery and provider lifecycle routing",
    )
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--target", type=Path, default=Path.cwd())
    parser.add_argument("--authority-kind", choices=AUTHORITY_KINDS, default="native-executable")
    parser.add_argument("--authority-reference")
    parser.add_argument("--hostname", default="github.com")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        print(json.dumps(profile_document(parse_args(argv)), ensure_ascii=False, sort_keys=True))
        return 0
    except ToolError as error:
        print(json.dumps({"schemaVersion": SCHEMA_VERSION, "kind": "error", "error": {"code": error.code, "message": error.message}}, ensure_ascii=False, sort_keys=True))
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"schemaVersion": SCHEMA_VERSION, "kind": "error", "error": {"code": "inspection_failed", "message": str(error)}}, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
