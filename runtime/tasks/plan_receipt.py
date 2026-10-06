"""Host-recorded completion for plan-only Work: planning cannot write files or run tests."""
import json
from pathlib import Path

from storage.files import atomic_write, safe_read_json


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


def finish_planning(state, structured, *, execute_next, provider, emit):
    """Publish a print adapter's plan result and decide whether execution may start."""
    text = str(structured.get("resultText", "")).strip()
    if structured.get("status") == "failed" or not text:
        raise ValueError(f"{provider} planning result is invalid")
    decision = structured.get("status") == "needs-human-decision"
    record_plan(state, {"status": "needs-human-decision" if decision else "planned", "plan": text})
    terminal = None
    if decision:
        terminal = {"status": "needs-human-decision", "resultPath": state["resultPath"], "resultText": text,
                    "decisionKind": "clarification"}
    elif not execute_next:
        record_plan_only_receipt(state)
        terminal = {"status": "completed", "resultPath": state["resultPath"], "resultText": text}
    elif safe_read_json(Path(state["statePath"])).get("cancelRequested"):
        return False
    if terminal is not None:
        emit({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal, ensure_ascii=False)}})
        return False
    emit({"type": "native.commentary", "text": "Planning is complete. Implementation is starting in the same Work session."})
    return True
