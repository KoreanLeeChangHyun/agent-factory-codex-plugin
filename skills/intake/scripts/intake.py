#!/usr/bin/env python3
"""Intake adapter for the shared Agent Factory sectioned-document engine."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_ROOT.parent
COMMON_MANAGER = (
    SKILL_ROOT.parent / "lifecycle" / "assets" / "scripts" / "sectioned_document.py"
)
COMMON_SCHEMA_ROOT = (
    SKILL_ROOT.parent / "lifecycle" / "assets" / "schema" / "sectioned-document"
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
    lock_collection="intakes",
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


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
