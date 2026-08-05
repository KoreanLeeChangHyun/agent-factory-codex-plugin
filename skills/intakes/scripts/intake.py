#!/usr/bin/env python3
"""Intake adapter for the shared Agent Factory sectioned-document engine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
COMMON_MANAGER = (
    SKILL_ROOT.parent
    / "lifecycle"
    / "scripts"
    / "sectioned_document.py"
)
COMMON_SCHEMA_ROOT = (
    SKILL_ROOT.parent
    / "lifecycle"
    / "assets"
    / "schema"
    / "sectioned-document"
)


def load_base_manager() -> Any:
    spec = importlib.util.spec_from_file_location(
        "agent_factory_sectioned_document", COMMON_MANAGER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load sectioned document manager: {COMMON_MANAGER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base_manager()
base.configure_contract(
    skill_root=SKILL_ROOT,
    profile_path=SKILL_ROOT / "assets" / "profiles" / "intake.profile.json",
    metadata_schema_path=SKILL_ROOT / "assets" / "schema" / "metadata.schema.json",
    structural_schema_root=COMMON_SCHEMA_ROOT,
    artifact_type="intake",
    artifact_label="Intake",
    package_collection="intakes",
    lifecycle_phase="intake",
    initial_status="draft",
    initial_readiness={
        "contractValid": True,
        "evidenceComplete": False,
        "requirementsComplete": False,
        "specificationConsistent": False,
        "executionReady": False,
        "reviewedAt": None,
        "findings": [],
    },
    generated_by="Agent Factory intake manager",
    mutation_policy={
        "terminalStatuses": ["closed", "superseded"],
        "readyStatus": "ready",
        "draftStatus": "draft",
        "invalidateReadinessFields": [
            "evidenceComplete",
            "requirementsComplete",
            "specificationConsistent",
            "executionReady",
        ],
    },
)

# Preserve the manager's import API while keeping all implementation in the
# lifecycle-owned module. Artifact configuration above is applied before use.
for name in dir(base):
    if not name.startswith("_") and name not in globals():
        globals()[name] = getattr(base, name)


def session_binding(metadata: dict[str, Any]) -> str | None:
    operational = metadata.get("operational")
    if not isinstance(operational, dict):
        return None
    binding = operational.get("agentSessionBinding")
    return binding.get("sessionId") if isinstance(binding, dict) else None


def require_operational_mutation(metadata: dict[str, Any]) -> None:
    status = metadata["lifecycle"]["status"]
    if status in {"closed", "superseded"}:
        raise base.ManagerError(
            f"terminal Intake does not allow operational mutation: {status}"
        )


def command_session_show(args: argparse.Namespace) -> None:
    base.validate_package(args.package)
    metadata = base.load_metadata(args.package)
    print(
        json.dumps(
            {"intakeId": metadata["id"], "sessionId": session_binding(metadata)}
        )
    )


def command_session_bind(args: argparse.Namespace) -> None:
    base.validate_package(args.package)
    metadata = base.load_metadata(args.package)
    require_operational_mutation(metadata)
    operational = metadata.setdefault("operational", {})
    operational["agentSessionBinding"] = {"sessionId": args.session_id}
    base.validate_instance("metadata", metadata)
    base.commit_transaction(
        args.package,
        json_writes={args.package / "data" / "metadata.json": metadata},
    )
    print(json.dumps({"intakeId": metadata["id"], "sessionId": args.session_id}))


def command_session_clear(args: argparse.Namespace) -> None:
    base.validate_package(args.package)
    metadata = base.load_metadata(args.package)
    require_operational_mutation(metadata)
    operational = metadata.get("operational")
    if isinstance(operational, dict):
        operational.pop("agentSessionBinding", None)
        if not operational:
            metadata.pop("operational")
    base.validate_instance("metadata", metadata)
    base.commit_transaction(
        args.package,
        json_writes={args.package / "data" / "metadata.json": metadata},
    )
    print(json.dumps({"intakeId": metadata["id"], "sessionId": None}))


def parser() -> argparse.ArgumentParser:
    root = base.parser()
    subparsers = next(
        action
        for action in root._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    bind = subparsers.add_parser(
        "session-bind",
        help="bind one Codex session without semantic Intake mutation",
    )
    bind.add_argument("package")
    bind.add_argument("session_id")
    bind.set_defaults(handler=command_session_bind)

    show = subparsers.add_parser(
        "session-show", help="show the Codex session bound to an Intake"
    )
    show.add_argument("package")
    show.set_defaults(handler=command_session_show)

    clear = subparsers.add_parser(
        "session-clear", help="clear an Intake's Codex session association"
    )
    clear.add_argument("package")
    clear.set_defaults(handler=command_session_clear)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        if not hasattr(args, "package"):
            args.handler(args)
            return 0
        package = base.resolve_package(
            args.package, must_exist=args.command != "create"
        )
        if package.exists() and args.command != "delete":
            base.recover_transaction(package)
        args.package = package
        args.handler(args)
        return 0
    except base.ManagerError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
