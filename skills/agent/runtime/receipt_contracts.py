"""Role receipt schemas and strict run/request/path binding validation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from capability_contracts import validate_capability_bindings
from runtime_errors import ContractError
from runtime_storage import agent_root, resolve_project_root, safe_read_bytes, validate_id

SCHEMA_VERSION = "0.1.0"
AGENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CHANGED_PATH_PATTERN = r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[^\r\n]+$"
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_CAPABILITY_BINDING_BYTES = 256 * 1024
CAPABILITY_OUTCOMES = {"succeeded", "failed", "unknown", "not-invoked"}

def receipt_schema_document(
    *, role: str, run_id: str, request_hash: str, verified_work_run_id: str | None,
    capability_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tests = {
        "type": "object",
        "properties": {
            "run": {"const": False},
            "reason": {
                "const": (
                    "work-agent-prohibited" if role == "work" else "verification-recorded-separately"
                )
            },
        },
        "required": ["run", "reason"],
        "additionalProperties": False,
    }
    capability_outcomes = None
    if capability_bindings is not None:
        outcome_items = []
        for binding in capability_bindings["bindings"]:
            outcome_items.append({
                "type": "object",
                "properties": {
                    "requestHash": {"const": request_hash},
                    "runId": {"const": run_id},
                    "capabilityId": {"const": binding["capabilityId"]},
                    "authority": {"const": binding["authority"]},
                    "exactTarget": {"const": binding["exactTarget"]},
                    "outcome": {"enum": sorted(CAPABILITY_OUTCOMES)},
                },
                "required": ["requestHash", "runId", "capabilityId", "authority", "exactTarget", "outcome"],
                "additionalProperties": False,
            })
        capability_outcomes = {
            "type": "array", "prefixItems": outcome_items,
            "minItems": len(outcome_items), "maxItems": len(outcome_items),
        }
    if role == "work":
        properties: dict[str, Any] = {
            "schemaVersion": {"const": SCHEMA_VERSION},
            "kind": {"const": "work-receipt"},
            "runId": {"const": run_id},
            "requestHash": {"const": request_hash},
            "outcome": {"const": "implemented"},
            "changedPaths": {
                "type": "array",
                "description": (
                    "Project-root-relative paths changed by Work. Runtime-only "
                    "artifacts belong in result.md and do not appear here."
                ),
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": CHANGED_PATH_PATTERN,
                },
                "uniqueItems": True,
            },
            "addressedFindingIds": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "tests": tests,
        }
        required = list(properties)
    else:
        finding = {
            "type": "object",
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "path": {"type": "string"},
                "location": {"type": "string"},
                "problem": {"type": "string", "minLength": 1},
                "evidence": {"type": "string", "minLength": 1},
                "correction": {"type": "string", "minLength": 1},
            },
            "required": [
                "id", "path", "location", "problem", "evidence", "correction"
            ],
            "additionalProperties": False,
        }
        verified_id_schema: dict[str, Any] = {"type": "string", "minLength": 1}
        if verified_work_run_id is not None:
            verified_id_schema = {"const": verified_work_run_id}
        properties = {
            "schemaVersion": {"const": SCHEMA_VERSION},
            "kind": {"const": "verification-receipt"},
            "runId": {"const": run_id},
            "verifiedWorkRunId": verified_id_schema,
            "verifiedRequestHash": {"const": request_hash},
            "decision": {"enum": ["pass", "fail"]},
            "findings": {"type": "array", "items": finding},
        }
        required = list(properties)
    if capability_outcomes is not None:
        properties["capabilityOutcomes"] = capability_outcomes
        required.append("capabilityOutcomes")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ContractError("receipt_invalid", f"{label} contains unknown or missing fields")


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ContractError("receipt_invalid", f"{label} must be a string array")
    if len(set(value)) != len(value):
        raise ContractError("receipt_invalid", f"{label} must contain unique values")
    return value


def _require_managed_directory(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        raise ContractError("receipt_path_invalid", "managed run directory is missing") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ContractError("receipt_path_invalid", "managed run directory is unsafe")


def _require_managed_file(path: Path, *, allow_missing: bool = False) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as error:
        if allow_missing:
            return
        raise ContractError("receipt_path_invalid", "managed run file is missing") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ContractError("receipt_path_invalid", "managed run file is unsafe")


def validate_receipt(
    project_root: Path,
    state: dict[str, Any],
    *,
    agent_id: str,
    run_id: str,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    role = state.get("role")
    if role not in {"work", "verification"}:
        raise ContractError("receipt_unexpected", "this Agent role has no receipt contract")
    validate_id(agent_id, AGENT_ID, "agent_id")
    validate_id(run_id, AGENT_ID, "run_id")
    if state.get("agentId") != agent_id or state.get("runId") != run_id:
        raise ContractError("receipt_path_invalid", "receipt Agent/run binding is invalid")
    managed_root = agent_root(root, create=False)
    agent_path = managed_root / agent_id
    runs_path = agent_path / "runs"
    run_path = runs_path / run_id
    for directory in (managed_root.parent, managed_root, agent_path, runs_path, run_path):
        _require_managed_directory(directory)
    canonical = {
        "statePath": run_path / "state.json",
        "resultPath": run_path / "result.md",
        "receiptSchemaPath": run_path / "receipt.schema.json",
        "receiptPath": run_path / "receipt.json",
    }
    for field, expected in canonical.items():
        if state.get(field) != str(expected):
            raise ContractError("receipt_path_invalid", f"{field} is not canonically bound")
    _require_managed_file(canonical["statePath"])
    _require_managed_file(canonical["resultPath"])
    _require_managed_file(canonical["receiptSchemaPath"])
    _require_managed_file(canonical["receiptPath"], allow_missing=True)
    receipt_path = canonical["receiptPath"]
    try:
        receipt = json.loads(safe_read_bytes(receipt_path, MAX_RECEIPT_BYTES))
    except FileNotFoundError as error:
        raise ContractError("receipt_missing", "Agent did not publish its receipt") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError("receipt_format_invalid", "Agent receipt is malformed JSON") from error
    except ContractError as error:
        if error.code == "file_not_found":
            raise ContractError("receipt_missing", "Agent did not publish its receipt") from error
        raise ContractError("receipt_path_invalid", "Agent receipt path is unsafe") from error
    if not isinstance(receipt, dict):
        raise ContractError("receipt_format_invalid", "Agent receipt must be a JSON object")
    expected_hash = state.get("receiptRequestHash") or state.get("requestHash")
    binding_document = None
    binding_hash = state.get("capabilityBindingHash")
    if binding_hash is not None:
        binding_path = canonical["statePath"].parent / "capability-bindings.json"
        if state.get("capabilityBindingPath") != str(binding_path):
            raise ContractError("receipt_path_invalid", "capability binding path is not canonically bound")
        _require_managed_file(binding_path)
        binding_bytes = safe_read_bytes(binding_path, MAX_CAPABILITY_BINDING_BYTES)
        if hashlib.sha256(binding_bytes).hexdigest() != binding_hash:
            raise ContractError("capability_binding_invalid", "capability binding hash does not match")
        try:
            binding_document = validate_capability_bindings(json.loads(binding_bytes))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContractError("capability_binding_invalid", "capability binding is invalid JSON") from error
    expected_fields = {
        "schemaVersion", "kind", "runId", "requestHash", "outcome",
        "changedPaths", "addressedFindingIds", "tests",
    }
    if binding_document is not None:
        expected_fields.add("capabilityOutcomes")
    if role == "work":
        tests = receipt.get("tests")
        if not isinstance(tests, dict):
            raise ContractError("receipt_tests_invalid", "receipt tests proof is missing")
        if set(tests) != {"run", "reason"}:
            raise ContractError("receipt_tests_invalid", "receipt tests proof has unknown or missing fields")
        if tests != {"run": False, "reason": "work-agent-prohibited"}:
            raise ContractError("receipt_tests_invalid", "Work receipt must prove Work ran no tests")
        if binding_document is not None and (
            ("capabilityOutcomes" in receipt) != ("capabilityOutcomes" in expected_fields)
        ):
            raise ContractError("receipt_capability_invalid", "work receipt omitted capability outcomes")
        _exact_keys(receipt, expected_fields, "work receipt")
        if (
            receipt.get("schemaVersion") != SCHEMA_VERSION
            or receipt.get("kind") != "work-receipt"
            or receipt.get("runId") != state.get("runId")
            or receipt.get("requestHash") != expected_hash
            or receipt.get("outcome") != "implemented"
        ):
            raise ContractError("receipt_binding_invalid", "work receipt binding is invalid")
        work_changed_paths = _string_list(receipt.get("changedPaths"), "changedPaths")
        _string_list(receipt.get("addressedFindingIds"), "addressedFindingIds")
    else:
        expected_fields = {
            "schemaVersion", "kind", "runId", "verifiedWorkRunId",
            "verifiedRequestHash", "decision", "findings",
        }
        if binding_document is not None:
            expected_fields.add("capabilityOutcomes")
        _exact_keys(receipt, expected_fields, "verification receipt")
    if role == "work":
        validated_receipt = receipt
    else:
        verified_work_run_id = receipt.get("verifiedWorkRunId")
        expected_work_run_id = state.get("verifiedWorkRunId")
        if (
            receipt.get("schemaVersion") != SCHEMA_VERSION
            or receipt.get("kind") != "verification-receipt"
            or receipt.get("runId") != state.get("runId")
            or not isinstance(verified_work_run_id, str)
            or not AGENT_ID.fullmatch(verified_work_run_id)
            or (expected_work_run_id is not None and verified_work_run_id != expected_work_run_id)
            or receipt.get("verifiedRequestHash") != expected_hash
        ):
            raise ContractError("receipt_binding_invalid", "verification receipt binding is invalid")
        findings = receipt.get("findings")
        if not isinstance(findings, list):
            raise ContractError("receipt_invalid", "findings must be an array")
        finding_ids: list[str] = []
        finding_fields = {"id", "path", "location", "problem", "evidence", "correction"}
        for finding in findings:
            if not isinstance(finding, dict):
                raise ContractError("receipt_invalid", "each finding must be an object")
            _exact_keys(finding, finding_fields, "finding")
            finding_id = finding.get("id")
            if not isinstance(finding_id, str) or not finding_id:
                raise ContractError("receipt_invalid", "finding id is invalid")
            finding_ids.append(finding_id)
            for field in ("path", "location", "problem", "evidence", "correction"):
                if not isinstance(finding.get(field), str):
                    raise ContractError("receipt_invalid", f"finding {field} must be a string")
            if not finding["problem"] or not finding["evidence"] or not finding["correction"]:
                raise ContractError("receipt_invalid", "finding details must not be empty")
        if len(set(finding_ids)) != len(finding_ids):
            raise ContractError("receipt_invalid", "finding identifiers must be unique")
        decision = receipt.get("decision")
        if decision == "pass" and findings:
            raise ContractError("receipt_decision_invalid", "passing verification has findings")
        if decision == "fail" and not findings:
            raise ContractError("receipt_decision_invalid", "failed verification requires a finding")
        if decision not in {"pass", "fail"}:
            raise ContractError("receipt_decision_invalid", "verification decision is invalid")
        validated_receipt = receipt
    if binding_document is not None:
        outcomes = receipt.get("capabilityOutcomes")
        bindings = binding_document["bindings"]
        if not isinstance(outcomes, list) or len(outcomes) != len(bindings):
            raise ContractError("receipt_capability_invalid", "capability outcomes must match bound capabilities")
        for outcome, binding in zip(outcomes, bindings):
            expected_outcome_fields = {"requestHash", "runId", "capabilityId", "authority", "exactTarget", "outcome"}
            if not isinstance(outcome, dict):
                raise ContractError("receipt_capability_invalid", "capability outcome must be an object")
            if set(outcome) != expected_outcome_fields:
                raise ContractError("receipt_capability_invalid", "capability outcome has unknown or missing fields")
            if (
                outcome.get("requestHash") != expected_hash
                or outcome.get("runId") != state.get("runId")
                or outcome.get("capabilityId") != binding["capabilityId"]
                or outcome.get("authority") != binding["authority"]
                or outcome.get("exactTarget") != binding["exactTarget"]
                or outcome.get("outcome") not in CAPABILITY_OUTCOMES
            ):
                raise ContractError("receipt_capability_invalid", "capability outcome binding is invalid")
    if role == "work":
        for changed_path in work_changed_paths:
            candidate = Path(changed_path)
            if (
                re.fullmatch(CHANGED_PATH_PATTERN, changed_path) is None
                or candidate.is_absolute() or ".." in candidate.parts
            ):
                raise ContractError(
                    "receipt_path_contract_invalid",
                    "changedPaths must contain only project-root-relative paths",
                )
    return validated_receipt



