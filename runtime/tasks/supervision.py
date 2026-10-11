"""Supervision verdicts and periodic one-line reports for long-running loops.

Each unfinished loop's current task is judged `normal`, `delayed`, `stuck` or
`decision-needed` from the operations records (`operation_records.classify`), the
last recorded activity, a repeating control-plane error and the decision wait.
Reports are appended beside the loop for Main and the extension to read. Nothing
here cancels, retries, dispatches or changes a loop or run record.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.errors import ContractError
from storage.files import atomic_write_json, file_lock, reject_symlink, safe_read_json
from tasks import operation_records

VERDICTS = ("normal", "delayed", "stuck", "decision-needed")
# Reported immediately, regardless of the report interval.
ALERT_VERDICTS = {"stuck", "decision-needed"}
DEFAULTS = {"intervalMinutes": 10, "delayMinutes": 20, "stuckMinutes": 60, "repeatLimit": 3}
# Optional runtime-level overrides of DEFAULTS, written by `operation_records.py supervise --save-settings`.
SETTINGS_FILE = "supervision.json"
REPORT_LOG = "supervision.jsonl"
REPORT_STATE = "supervision-state.json"
# Titles often hold the whole request; the report line keeps only their start.
TITLE_LIMIT = 60
# Next action per recorded stop class; the classes and their meaning are owned by loop.py.
STOP_ACTIONS = {
    "contract": "repair the run's output contract (receipt recovery) or use a stronger profile",
    "transient": "inspect the control-plane error, then reconcile the loop",
    "provider": "check the model backend, then reconcile the loop",
    "environment": "change the host or policy first; another attempt fails the same way",
    "human": "await the Human's decision",
}
PHASE_ACTIONS = {"work-running": "continue Work", "verification-running": "continue Verification",
                 "integrating": "finish integration", "preparing": "dispatch the next run",
                 "starting": "dispatch the first run"}


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def stamp(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def seconds_since(moment, now):
    return max(0, int((now - moment).total_seconds())) if moment else None


def duration(seconds):
    if seconds is None:
        return "?"
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def load_settings(runtime_root, **overrides):
    """DEFAULTS, then the runtime's saved settings, then non-None overrides."""
    settings = dict(DEFAULTS)
    path = Path(runtime_root) / SETTINGS_FILE if runtime_root else None
    if path and path.is_file():
        try:
            saved = safe_read_json(path)
        except (OSError, ValueError, ContractError):
            saved = {}
        settings.update({key: saved[key] for key in DEFAULTS if isinstance(saved.get(key), int) and saved[key] > 0})
    settings.update({key: value for key, value in overrides.items() if key in DEFAULTS and value is not None})
    for key, value in settings.items():
        if type(value) is not int or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
    return settings


def save_settings(runtime_root, settings):
    atomic_write_json(Path(runtime_root) / SETTINGS_FILE, {"schemaVersion": 1, **settings})


def judge(evidence: dict[str, Any], settings: dict[str, int], now: datetime) -> dict[str, Any]:
    """Pure verdict for one task. Long duration alone never stops anything; it is only reported.

    `evidence`: status (classify result), phase, failureClass, errorCode, lastActivityAt, startedAt,
    waitingSince, decision (pending decision record or None), recovery (loop recovery
    record or None), revisionCount, lastVerificationDecision.
    """
    status = evidence.get("status") or {}
    state = status.get("state")
    idle = seconds_since(parse_time(evidence.get("lastActivityAt")), now)
    waiting = seconds_since(parse_time(evidence.get("waitingSince")), now)
    delay, stuck = settings["delayMinutes"] * 60, settings["stuckMinutes"] * 60
    recovery = evidence.get("recovery") if isinstance(evidence.get("recovery"), dict) else {}
    recovery_age = seconds_since(parse_time(recovery.get("observedAt")), now)
    reasons: list[str] = []

    if state == "waiting-decision":
        verdict = "decision-needed"
        decision = evidence.get("decision") or {}
        reasons.append("decision-pending")
        subject = " ".join(str(part) for part in (decision.get("kind"), decision.get("target")) if part)
        action = "await the Human's decision" + (f": {subject}" if subject else "")
    elif state == "blocked":
        verdict = "stuck"
        failure = evidence.get("failureClass") or "unknown"
        reasons.append(f"loop-stopped:{failure}" + (f":{evidence['errorCode']}" if evidence.get("errorCode") else ""))
        action = STOP_ACTIONS.get(failure, "inspect the recorded control-plane error")
    elif (recovery.get("attempts", 0) >= settings["repeatLimit"] and recovery_age is not None
          and recovery_age < delay):
        # The driver's own bounded backoff keeps retrying; supervision only reports the repetition.
        verdict = "stuck"
        reasons.append(f"repeated-error:{recovery.get('code')}x{recovery['attempts']}")
        action = f"inspect the repeating {recovery.get('code')} before the next reconcile"
    elif idle is not None and idle >= stuck:
        verdict = "stuck"
        reasons.append("no-progress")
        action = "inspect the active run's events and outputs; nothing is cancelled automatically"
    elif idle is not None and idle >= delay:
        verdict = "delayed"
        reasons.append("no-progress")
        action = "compare intermediate outputs with the completion criteria at the next report"
    else:
        verdict = "normal"
        action = PHASE_ACTIONS.get(evidence.get("phase"), f"continue ({state})")
    if verdict in {"normal", "delayed"}:
        if (evidence.get("lastVerificationDecision") == "fail"
                and (evidence.get("revisionCount") or 0) >= settings["repeatLimit"]):
            verdict = "delayed"
            reasons.append(f"repeated-verification-fail:x{evidence['revisionCount']}")
            action = "check whether the rework addresses the repeated findings"
        if state == "waiting-external":
            reasons.append("external-wait")
        if state == "unknown":
            reasons.append("state-unknown")
    return {"verdict": verdict, "reasons": reasons, "nextAction": action,
            "elapsedSeconds": seconds_since(parse_time(evidence.get("startedAt")), now),
            "idleSeconds": idle, "waitingSeconds": waiting}


def line(task: dict[str, Any]) -> str:
    """One line: task name, verdict and state, elapsed time, next action."""
    times = f"elapsed {duration(task['elapsedSeconds'])}, idle {duration(task['idleSeconds'])}"
    if task["verdict"] == "decision-needed" and task["waitingSeconds"] is not None:
        times += f", waiting {duration(task['waitingSeconds'])}"
    reasons = f" ({', '.join(task['reasons'])})" if task["reasons"] else ""
    title = " ".join(str(task["title"]).split())
    title = title if len(title) <= TITLE_LIMIT else title[:TITLE_LIMIT - 1] + "…"
    return f"[{task['verdict']}] {title} — {task['state']}{reasons}; {times}; next: {task['nextAction']}"


def _activity(agents_root, task, state):
    """Latest recorded activity: loop/run updates and the active run's event stream."""
    moments = [parse_time(task.get("updatedAt"))]
    for owned in (task["sessions"].get("work"), task["sessions"].get("verification")):
        if owned and owned.get("runId"):
            events = Path(agents_root) / owned["agentId"] / "runs" / owned["runId"] / "events.jsonl"
            try:
                moments.append(datetime.fromtimestamp(events.stat().st_mtime, timezone.utc))
            except OSError:
                pass
    moments = [moment for moment in moments if moment]
    return stamp(max(moments)) if moments else state.get("updatedAt")


def observe(agents_root, path, settings, now, failure_class=None):
    """Verdict for one loop's current task, or None when the loop has ended or has no task."""
    state = safe_read_json(Path(path))
    workflow = state.get("workflow") or {}
    if state.get("status") in operation_records.LOOP_ENDED or not workflow.get("tasks"):
        return None
    tasks, _, _ = operation_records.project_loop(agents_root, path, failure_class)
    index = workflow.get("index", 0)
    if not 0 <= index < len(tasks):
        return None
    task = tasks[index]
    decision = (state.get("decisions") or {}).get(state.get("pendingDecisionId"))
    decision = decision if isinstance(decision, dict) and decision.get("status") == "pending" else None
    work = task["sessions"].get("work") or {}
    work_run = (operation_records._read(Path(agents_root) / work["agentId"] / "runs" / work["runId"] / "state.json")
                if work.get("runId") else None)
    waiting_since = None
    if task["status"]["state"] == "waiting-decision":
        waiting_since = ((decision or {}).get("createdAt") or (work_run or {}).get("finishedAt")
                         or state.get("updatedAt"))
    verdict = judge({"status": task["status"], "phase": state.get("phase"),
                     "failureClass": task["statusEvidence"].get("failureClass"),
                     "errorCode": task["statusEvidence"].get("errorCode"),
                     "lastActivityAt": _activity(agents_root, task, state),
                     "startedAt": state.get("createdAt"), "waitingSince": waiting_since,
                     "decision": decision, "recovery": state.get("recovery"),
                     "revisionCount": state.get("revisionCount", 0),
                     "lastVerificationDecision": state.get("lastVerificationDecision")}, settings, now)
    result = {"loopId": state.get("loopId"), "taskId": task["id"],
              "title": task.get("title") or workflow.get("title") or task["id"],
              "state": task["status"]["state"], "loopStatus": state.get("status"), "phase": state.get("phase"),
              "decisionId": (decision or {}).get("id"), "statePath": str(path), **verdict}
    result["line"] = line(result)
    return result


def _record(directory, observed, settings, now):
    """Append a report when due: each new alert at once, otherwise every interval while the loop is active.

    A stopped loop (decision wait, runtime error) needs someone to act, not a repeated line; its
    verdict stays in every tick's result and a changed alert is reported again.
    """
    with file_lock(directory / ".supervision.lock"):
        state_path = directory / REPORT_STATE
        memory = operation_records._read(state_path) if state_path.exists() else None
        memory = memory if isinstance(memory, dict) else {"schemaVersion": 1, "tasks": {}}
        previous = memory.setdefault("tasks", {}).get(observed["taskId"]) or {}
        alert_key = ("|".join([observed["verdict"], *observed["reasons"], observed["decisionId"] or ""])
                     if observed["verdict"] in ALERT_VERDICTS else None)
        last = parse_time(previous.get("reportedAt"))
        if alert_key and alert_key != previous.get("alertKey"):
            trigger = "alert"
        elif observed["loopStatus"] == "active" and (
                last is None or (now - last).total_seconds() >= settings["intervalMinutes"] * 60):
            trigger = "periodic"
        else:
            return None
        report = {"schemaVersion": 1, "kind": "supervision-report", "trigger": trigger, "reportedAt": stamp(now),
                  **{key: value for key, value in observed.items() if key != "statePath"}}
        log = directory / REPORT_LOG
        reject_symlink(log)
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")
        memory["tasks"][observed["taskId"]] = {"reportedAt": report["reportedAt"], "verdict": observed["verdict"],
                                                "alertKey": alert_key}
        atomic_write_json(state_path, memory)
        return {**report, "reportPath": str(log)}


def tick(agents_root, *, settings, now=None, loop_id=None, failure_class=None, record=True) -> dict[str, Any]:
    """Judge every unfinished loop (or one loop) and record the reports that are due."""
    now = now or datetime.now(timezone.utc)
    verdicts, reports, errors = [], [], []
    for path in sorted(Path(agents_root).glob("*/loops/*/state.json")):
        if loop_id is not None and path.parent.name != loop_id:
            continue
        try:
            observed = observe(agents_root, path, settings, now, failure_class)
            if observed is None:
                continue
            verdicts.append(observed)
            report = _record(path.parent, observed, settings, now) if record else None
            if report:
                reports.append(report)
        except (OSError, ValueError, KeyError, TypeError, ContractError) as error:
            errors.append({"source": str(path), "error": f"{type(error).__name__}: {error}"})
    return {"schemaVersion": 1, "kind": "supervision", "observedAt": stamp(now), "settings": settings,
            "alerts": [report for report in reports if report["trigger"] == "alert"],
            "reports": reports, "verdicts": verdicts, "errors": errors}
