"""Regenerable progress views. Loop state and validated receipts retain authority."""
from __future__ import annotations

import json
from pathlib import Path


def cell(value):
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def snapshot(state):
    workflow = state.get("workflow") or {}
    return {
        "schemaVersion": 1,
        "loopId": state["loopId"],
        "stateRevision": state.get("stateRevision", 0),
        "updatedAt": state.get("updatedAt"),
        "status": state["status"], "phase": state["phase"],
        "taskMode": state.get("execution", {}).get("taskMode", "work-verification"),
        "contract": state.get("contract"),
        "workflowId": workflow.get("id"),
        "tasks": [{key: task.get(key) for key in (
            "id", "title", "workAgentId", "workRunId", "workStatus",
            "verificationAgentId", "verificationRunId", "verificationStatus"
        )} for task in workflow.get("tasks", [])],
        "terminalReason": state.get("terminalReason"),
        "humanSkip": state.get("humanSkip"),
        "taskWorkspaces": state.get("taskWorkspaces", {}),
        "controlPlaneError": state.get("controlPlaneError"),
        "pendingDispatchId": (state.get("pendingDispatch") or {}).get("dispatchId"),
    }


def render(view):
    contract = view.get("contract") or {}
    identity = (f"{cell(contract.get('id'))} v{cell(contract.get('version'))}"
                if contract else "not bound (legacy task list)")
    rows = ["# Workflow progress", "", "- Generated view; do not edit. Runtime state and receipts are authoritative.",
            f"- Loop: `{cell(view['loopId'])}`; revision: {view['stateRevision']}.",
            f"- Workflow: {cell(view['workflowId'])}; contract: {identity}.",
            f"- Status: {cell(view['status'])}; phase: {cell(view['phase'])}; route: {cell(view['taskMode'])}.",
            f"- Observed: {cell(view['updatedAt'])}.",
            "- This view records committed transitions, not live token activity.", "",
            "| Task | Title | Work | Verification | Work run | Verification run |",
            "|---|---|---|---|---|---|"]
    for task in view["tasks"]:
        verification = task.get("verificationStatus") or "pending"
        if view["taskMode"] in {"work", "plan-work"}:
            verification = "not requested"
        elif view.get("humanSkip") and verification != "completed":
            verification = "skipped" if task.get("workStatus") == "completed" else verification
        rows.append("| " + " | ".join(cell(x) for x in (
            task["id"], task["title"], task["workStatus"], verification,
            task["workRunId"], task["verificationRunId"])) + " |")
    rows += ["", "- Verification completion in a managed loop is recorded only after receipt processing.",
             "- Cancelled historical runs remain cancelled even if later direct work completes the same task."]
    if view.get("controlPlaneError"):
        rows += ["- Last recorded exception (may be historical): " + cell(json.dumps(view["controlPlaneError"], ensure_ascii=False))]
    if view.get("terminalReason"):
        rows += ["- Terminal reason: " + cell(json.dumps(view["terminalReason"], ensure_ascii=False))]
    for workspace in view.get("taskWorkspaces", {}).values():
        for unit in workspace.get("repositories", []):
            rows += ["- Work Unit: " + cell(unit.get("path")) + "; branch: " + cell(unit.get("branch"))
                     + " → " + cell(unit.get("targetBranch")) + "; state: " + cell(unit.get("phase"))
                     + "; base/result/merge: " + "/".join(cell(unit.get(key)) for key in ("baseCommit", "resultCommit", "mergeCommit"))
                     + "; source changes excluded: true; cleanup: " + cell(unit.get("cleanupPending", unit.get("cleaned")))]
    return "\n".join(rows) + "\n"


def publish(path: Path, state: dict, write):
    """Call under .loop.lock; retrying the same committed revision is idempotent."""
    view = snapshot(state)
    revision = view["stateRevision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid state revision")
    encoded = (json.dumps(view, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    history = path.parent / "progress-history" / f"revision-{revision:08d}.json"
    if history.parent.is_symlink() or history.is_symlink():
        raise ValueError("Progress history must not be a symlink")
    if history.exists():
        if history.read_bytes() != encoded:
            raise ValueError("Progress history revision conflict")
    else:
        write(history, encoded)
    write(path.parent / "progress.md", render(view).encode())
    write(path.parent / "progress-state.json", encoded)
    return {"stateRevision": revision, "path": str(path.parent / "progress.md"), "historyPath": str(history)}


def health(path: Path, state: dict):
    """Read-only freshness check; never dispatch, recover or alter runtime state."""
    try:
        current = path.parent / "progress-state.json"
        markdown = path.parent / "progress.md"
        if current.is_symlink() or markdown.is_symlink():
            return "stale"
        view = json.loads(current.read_text(encoding="utf-8"))
        if view != snapshot(state) or markdown.read_text(encoding="utf-8") != render(view):
            return "stale"
        revision = view["stateRevision"]
        if type(revision) is not int or revision < 0:
            return "stale"
        history = path.parent / "progress-history" / f"revision-{revision:08d}.json"
        if history.parent.is_symlink() or history.is_symlink():
            return "stale"
        return "current" if json.loads(history.read_text(encoding="utf-8")) == view else "stale"
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError, KeyError, TypeError):
        return "stale"
