"""Recommend a Work model from the detected model catalog and the Human-editable affinity table.

The catalog is the host's provider-observed `modelCatalog` (codex, claude, antigravity candidates); it says
which models were detected, not how good they are. The table (`model-affinity.json` in the project runtime
root) lists the Human's ordered model preferences per task type; only the Human's file is used and none is
created. Only detected candidates are chosen, a Human-specified role model is always kept, a missing table yields
`no-affinity-table` and a missing catalog yields `recheck-required`.
The record is stored in the accepted allocation as selection evidence; it grants no authority.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

FILE = "model-affinity.json"
TASK_TYPES = ("research", "small-change", "design-diagnosis", "documentation")
STATUSES = ("applied", "human-specified", "recommended", "no-affinity-table", "recheck-required", "no-match")
PROFILES = ("explore", "workLight", "work", "scribe")


def provider_of(model):
    """The catalog's own provider rule, used when an entry or a specified model has none."""
    return "claude" if model.startswith("claude-") else (
        "antigravity" if model.startswith(("gemini-", "antigravity/")) else "codex")


def load_table(runtime_root):
    """Read the Human's table; an absent file stays absent. Problems are returned, not raised."""
    path = Path(runtime_root) / FILE
    if not path.is_file():
        return None, {"path": str(path), "sha256": None, "source": "absent"}, None
    raw = path.read_bytes()
    reference = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "source": "file"}
    try:
        table = json.loads(raw.decode("utf-8"))
        problem = table_problem(table)
    except (UnicodeError, ValueError) as error:
        table, problem = None, "invalid JSON: " + str(error)
    return (None if problem else table), reference, problem


def table_problem(table):
    if not isinstance(table, dict) or table.get("schemaVersion") != 1 or not isinstance(table.get("taskTypes"), dict):
        return "schemaVersion 1 with a taskTypes object is required"
    for name, entry in table["taskTypes"].items():
        if name not in TASK_TYPES:
            return "unknown task type " + str(name) + "; use " + ", ".join(TASK_TYPES)
        if not isinstance(entry, dict) or not isinstance(entry.get("preferences"), list):
            return name + " requires a preferences array"
        if "profile" in entry and entry["profile"] not in PROFILES:
            return name + " profile must be one of " + ", ".join(PROFILES)
        for item in entry["preferences"]:
            if not isinstance(item, dict) or not isinstance(item.get("model"), str) or not item["model"].strip():
                return name + " preferences need a model ID or pattern"
    return None


def recommend(catalog, table, reference, task_type, *, specified=None, session_provider=None, apply=True,
              problem=None, clock=None):
    """Choose the first detected candidate in the table's order for this task type."""
    current = clock or datetime.now(timezone.utc)
    candidates = [item for item in (catalog or {}).get("candidates", []) if isinstance(item, dict)
                  and isinstance(item.get("id"), str) and item["id"]] if isinstance(catalog, dict) else []
    entry = (table or {}).get("taskTypes", {}).get(task_type) or {}
    record = {"taskType": task_type, "status": "no-match", "recommended": None, "selected": None,
              "suggestedProfile": entry.get("profile"), "humanSpecified": specified,
              "alternatives": [], "excluded": [], "undetectedPreferences": [], "warnings": [],
              "table": copy.deepcopy(reference),
              "catalog": {"checkedAt": catalog.get("checkedAt"), "availability": catalog.get("availability"),
                          "sha256": hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest(),
                          "candidateCount": len(candidates)} if isinstance(catalog, dict) else None,
              "recordedAt": current.isoformat().replace("+00:00", "Z")}
    if problem:
        record["warnings"].append("affinity table not used: " + problem)
    if not isinstance(catalog, dict) or catalog.get("availability") != "provider-catalog-observed" or not candidates:
        record["warnings"].append("no provider-observed model catalog; recheck detected models")
    eligible, seen = [], set()
    for preference in entry.get("preferences", []):
        matched = [item for item in candidates if fnmatch.fnmatchcase(item["id"], preference["model"])]
        if not matched:
            record["undetectedPreferences"].append(preference["model"])
        for item in matched:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            option = {"model": item["id"], "provider": item.get("provider") or provider_of(item["id"]),
                      "preference": preference["model"], "basis": preference.get("basis", "human"),
                      "reason": preference.get("reason", "")}
            if session_provider and option["provider"] != session_provider:
                record["excluded"].append({**option, "excludedBecause": "existing-session-provider-" + session_provider})
            else:
                eligible.append(option)
    if eligible:
        record["recommended"], record["alternatives"] = eligible[0], eligible[1:]
    if specified:
        # The Human's role model is never replaced; an undetected one is flagged, not substituted.
        record.update(status="human-specified", selected=specified)
        if specified not in {item["id"] for item in candidates}:
            record["warnings"].append("human-specified model is not in the detected catalog; kept unchanged, recheck availability")
    elif reference.get("source") == "absent":
        # No table means no recommendation; the runtime never supplies example preferences.
        record["status"] = "no-affinity-table"
    elif record["recommended"]:
        record.update(status="applied" if apply else "recommended",
                      selected=record["recommended"]["model"] if apply else None)
    elif record["excluded"] or problem or record["warnings"]:
        record["status"] = "recheck-required"
    return record


def validate_record(record, task_type, fail):
    """Shape check for the runtime-written record stored inside allocation."""
    if not isinstance(record, dict) or record.get("status") not in STATUSES or record.get("taskType") != task_type:
        fail("modelRecommendation must be the runtime record for this taskType")
    for key in ("selected", "humanSpecified"):
        if record.get(key) is not None and (not isinstance(record[key], str) or not record[key].strip()):
            fail("modelRecommendation " + key + " must be a model ID or null")
    recommended = record.get("recommended")
    if recommended is not None and (not isinstance(recommended, dict) or not isinstance(recommended.get("model"), str)):
        fail("modelRecommendation recommended must name a detected model")
    if record["status"] == "applied" and (recommended is None or record.get("selected") != recommended["model"]):
        fail("An applied recommendation selects its recommended model")
    if record["status"] == "human-specified" and record.get("selected") != record.get("humanSpecified"):
        fail("A Human-specified model is kept as the selection")
