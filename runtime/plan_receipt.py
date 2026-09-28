"""Host-recorded completion for plan-only Work: planning cannot write files or run tests."""
import json
from pathlib import Path

from runtime_storage import atomic_write, safe_read_json


def record_plan(state, plan):
    atomic_write(Path(state["statePath"]).parent / "plan.json", json.dumps(plan, ensure_ascii=False).encode())


def record_plan_only_receipt(state):
    receipt = {"schemaVersion": "0.1.0", "kind": "work-receipt",
               "runId": state["runId"],
               "requestHash": state.get("receiptRequestHash") or state["requestHash"],
               "outcome": "completed", "changedPaths": [], "addressedFindingIds": [],
               "tests": {"run": False, "reason": "plan-only"}}
    schema = safe_read_json(Path(state["receiptSchemaPath"]))
    captured_reason = schema.get("properties", {}).get("tests", {}).get("properties", {}).get("reason", {}).get("const")
    if captured_reason == "work-agent-prohibited":
        receipt["tests"]["reason"] = captured_reason
    outcomes = schema.get("properties", {}).get("capabilityOutcomes")
    if outcomes is not None:
        receipt["capabilityOutcomes"] = [
            {**{key: value["const"] for key, value in item["properties"].items() if "const" in value},
             "outcome": "not-invoked"} for item in outcomes["prefixItems"]]
    atomic_write(Path(state["receiptPath"]), json.dumps(receipt).encode())
