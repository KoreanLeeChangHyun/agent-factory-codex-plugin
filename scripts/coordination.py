#!/usr/bin/env python3
"""Append Main's sourced control/decision record to its bound contract execution record."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from tasks.commits import bound_main  # noqa: E402
from tasks import announcement, binding  # noqa: E402
from tasks.orchestrator_guard import ENV, authorized_write, has_symlink, inside  # noqa: E402
from storage.errors import ContractError  # noqa: E402
from sync_documents import atomic_write  # noqa: E402 - Document writer; runtime atomic_write rejects project paths
from storage.files import file_lock, safe_read_json  # noqa: E402


def append_record(root, state, value):
    def reject(message):
        raise ContractError("coordination_scope_invalid", message)
    if state.get("role") != "main" or state.get("roleBoundaryPolicy") != 1:
        reject("Only a newly bound Main owns coordination records")
    if not isinstance(value, dict) or set(value) != {"announcementPath", "record"}:
        reject("Use the bound announcement and a sourced control/decision record")
    path = Path(value["announcementPath"])
    record = value["record"]
    required = {"kind", "source", "time", "scope", "note"}
    if (not isinstance(record, dict) or set(record) != required
            or record.get("kind") not in {"assignment", "waiting", "blocked", "retry", "stop", "decision"}
            or any(not isinstance(record.get(key), str) or not record[key].strip() for key in required)):
        reject("Record actual control reasons or Human decisions with source, time and affected scope")
    run = Path(state["statePath"]).parent
    if has_symlink(path) or not inside(path, run / "task-announcements", None):
        reject("Use this Main run's immutable task announcement")
    captured = safe_read_json(path)
    document = captured.get("taskList")
    if not isinstance(document, dict) or not document.get("tasks"):
        reject("Missing bound task list")
    if path != run / "task-announcements" / document["id"] / "announcement.json":
        reject("Announcement path is not canonical")
    announcement.check_submission(safe_read_json, Path(state["statePath"]),
                                  {"agentId": state["agentId"], "runId": state["runId"]}, document)
    binding.resolve(document, document["tasks"][0]["id"], "0" * 64)
    progress = (document.get("contract") or {}).get("progress") or {}
    if progress.get("owner") != "main" or not progress.get("path"):
        reject("This task has no Main-owned contract execution record; use the run record")
    target = root / progress["path"]
    if has_symlink(target) or not inside(target, root / "docs/progress", None) or not authorized_write(target, state, {}):
        reject("Contract record escapes its authorized Documents workspace")
    key = hashlib.sha256(str(target).encode()).hexdigest()[:24]
    location = Path(state["runtimeBinding"]["runtimeRoot"])
    with file_lock(location / ("coordination-" + key + ".lock"), blocking=False):
        original = target.read_bytes()
        marker = b"<!-- contract-execution-record -->"
        if original.count(marker) != 1:
            reject("Existing contract must contain its unique execution-record marker")
        # Append only: never rewrite the accepted contract, other records, state or approval facts.
        lines = [f"\n- {record['kind']} · {record['time']}"]
        for key in ("source", "scope", "note"):
            lines.append(f"  - {key}: " + record[key].replace("\n", "\n    "))
        addition = ("\n".join(lines) + "\n").encode()
        if has_symlink(target) or target.read_bytes() != original:
            reject("Contract record changed concurrently; preserve it and retry from current evidence")
        atomic_write(target, original + addition)
    return {"status": "recorded", "path": progress["path"], "kind": record["kind"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON control/decision record inside this Main run")
    args = parser.parse_args()
    try:
        root, state = bound_main(json.loads(os.environ.get(ENV, "{}")))
        if has_symlink(args.input) or not inside(args.input, Path(state["statePath"]).parent, None):
            raise ContractError("coordination_scope_invalid", "Input must belong to this Main run")
        print(json.dumps(append_record(root, state, safe_read_json(Path(args.input)))))
        return 0
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "blocked", "code": getattr(error, "code", "coordination_scope_invalid"), "message": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
