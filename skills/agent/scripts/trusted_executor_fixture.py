#!/usr/bin/env python3
"""Exercise the lifecycle when available or record its fail-closed refusal."""

from __future__ import annotations

import argparse
import json
import os
import platform
import stat
import sys
from pathlib import Path

import trusted_executor as executor


def prepare_run_directory(project: Path, requested: Path, run_id: str) -> Path:
    """Create the fixture-owned run directory after validating its exact location."""
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("run ID must be one path component")
    project = project.resolve(strict=True)
    run = Path(os.path.abspath(requested))
    try:
        relative = run.relative_to(project)
    except ValueError as error:
        raise ValueError("run directory must be beneath the project root") from error
    parts = relative.parts
    if len(parts) != 5 or parts[:2] != (".agent-factory", "agent") or parts[3:] != ("runs", run_id) or not parts[2]:
        raise ValueError("run directory must match .agent-factory/agent/<agent-id>/runs/<run-id>")

    current = project
    for part in parts[:-1]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ValueError("run directory parents must be real directories")
    try:
        mode = run.lstat().st_mode
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(mode):
            raise ValueError("run directory must not be a symlink")
        raise ValueError("run directory must not already exist")

    run.mkdir(parents=True)
    mode = run.lstat().st_mode
    resolved = run.resolve(strict=True)
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode) or resolved != run or not resolved.is_relative_to(project):
        raise ValueError("created run directory failed location validation")
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--expect-refusal-record", type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve(strict=True)
    run = prepare_run_directory(project, args.run_directory, args.run_id)
    payload_path = "tests/fixtures/trusted_executor_payload.py"
    payload = executor.read_regular(project / payload_path)
    inputs = [{"path": payload_path, "sha256": executor.digest_bytes(payload)}]
    interpreter = Path(sys.executable).resolve(strict=True)
    image_digest = os.environ["AF_RUNNER_IMAGE_DIGEST"]
    manifest = {
        "schemaVersion": executor.SCHEMA_VERSION, "kind": "agent-factory-execution",
        "source": {"inputs": inputs, "ignoredPolicy": "exclude-and-unmount", "ignoreFileDigests": {}, "submodules": [], "snapshotDigest": executor.digest_bytes(executor.canonical_bytes(inputs))},
        "dependencies": {"lockfiles": [], "noExternalDependencies": True},
        "toolchain": {"executables": [], "interpreter": {"path": str(interpreter), "version": platform.python_version(), "sha256": executor.digest_bytes(executor.read_regular(interpreter, executor.MAX_ARTIFACT_BYTES))}, "runnerImage": {"kind": "github-observed", "digest": image_digest, "sbomDigest": os.environ["AF_RUNNER_SBOM_DIGEST"]}},
        "environment": {"clear": True, "allow": {"LANG": "C.UTF-8", "TZ": "UTC", "SOURCE_DATE_EPOCH": "0", **({"SystemRoot": os.environ["SystemRoot"]} if "SystemRoot" in os.environ else {})}, "forbidPrefixes": ["LD_", "DYLD_", "PYTHON"]},
        "platform": {"os": platform.system().lower(), "architecture": platform.machine().lower(), "runnerImageDigest": image_digest},
        "command": {"argv": [str(interpreter), payload_path], "cwd": ".", "stdin": "closed", "umask": "0022"},
        "policy": {"network": {"mode": "inherit"}, "time": {"mode": "host", "unixSeconds": 0}, "randomness": {"mode": "host", "seedDigest": "0" * 64}, "filesystem": {"mode": "host"}, "limits": {"wallSeconds": 60, "memoryBytes": 536870912, "pids": 32, "cpu": "100000 100000", "enforce": False}},
        "outputs": {"root": "out", "symlinks": "reject", "specialFiles": "reject"},
        "builder": {"id": "agent-factory-ci-fixture", "backend": "auto", "requiredGrade": "best-effort-tree"},
    }
    manifest_path = run / "requested.manifest.json"
    manifest_path.write_bytes(executor.canonical_bytes(manifest))
    try:
        executor.execute(manifest_path=manifest_path, project_root=project, run_dir=run, run_id=args.run_id, private_key=args.private_key, public_key=args.public_key, verifier_policy=args.policy)
    except executor.ExecutorError as error:
        if args.expect_refusal_record is None or error.code != "capability_unsatisfied":
            raise
        args.expect_refusal_record.write_text(json.dumps({"status": "refused", "code": error.code, "reason": error.message}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
