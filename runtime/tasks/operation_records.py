"""Common operations records projected read-only from existing runtime files.

Task, Session, Decision and Observation records are recomputed on every query from
loop and run state, loop decisions and receipts. Nothing here writes a runtime record.

Execution ended, work completed and check passed are separate facts. A status
without enough evidence stays `unknown` instead of borrowing a neighbour's value.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage.errors import ContractError
from storage.files import safe_read_json
from tasks.decisions import DETAIL_FIELDS

# The design's single Task state; facets below keep the distinctions it summarizes.
STATES = ("assigned", "running", "waiting-external", "waiting-decision", "blocked",
          "execution-ended", "work-completed", "check-passed", "unknown")

# Run status sets mirror exec.py's ACTIVE_STATES/TERMINAL_STATES.
RUN_ACTIVE = {"accepted", "queued", "starting", "running", "cancelling"}
RUN_TERMINAL = {"completed", "needs-human-decision", "failed", "cancelled"}
LOOP_ENDED = {"completed", "cancelled"}
# Routes whose loop never dispatches a separate Verification.
NO_CHECK_ROUTES = {"work", "plan-work"}


def classify(evidence: dict[str, Any]) -> dict[str, Any]:
    """Map recorded run/loop facts for one task to the design's state and facets.

    `evidence` keys (all optional): route, current, assigned, requestHash, loopStatus,
    workStatus, verificationStatus, workRunId, verificationRunId, workRun,
    verificationRun (run state dicts, None when unreadable), workReceipt,
    verificationReceipt (receipt dicts or None), failureClass, pendingDecision,
    pendingDispatch, integrationWait, humanSkip. Pure: no I/O, input unchanged.
    """
    reasons: list[str] = []
    route = evidence.get("route") or "work-verification"
    request_hash = evidence.get("requestHash")
    work_id, check_id = evidence.get("workRunId"), evidence.get("verificationRunId")
    work_run, check_run = evidence.get("workRun"), evidence.get("verificationRun")
    loop_ended = evidence.get("loopStatus") in LOOP_ENDED

    receipt = evidence.get("workReceipt")
    if receipt is not None and request_hash and receipt.get("requestHash") not in (None, request_hash):
        reasons.append("work receipt addresses another request revision")
        receipt = None

    # Execution: whether the task's managed processes are running or have ended.
    statuses = [run.get("status") if isinstance(run, dict) else None
                for run_id, run in ((work_id, work_run), (check_id, check_run)) if run_id]
    if any(status in RUN_ACTIVE for status in statuses) or (evidence.get("current") and evidence.get("pendingDispatch")):
        execution = "running"
    elif not work_id:
        execution = "not-started"
    elif all(status in RUN_TERMINAL for status in statuses):
        execution = "ended"
    else:
        execution = "unknown"
        reasons.append("a dispatched run state is unavailable or has an unrecognized status")

    # Work: the loop's processed completion judgment, bound to the current request.
    work_status = evidence.get("workStatus")
    if work_status == "completed":
        work = "completed"
        if receipt is not None and receipt.get("outcome") not in (None, "completed"):
            work = "unknown"
            reasons.append("processed work status conflicts with the work receipt")
    elif work_status in {"failed", "cancelled", "blocked"}:
        work = "not-completed"
    elif work_status in {None, "pending", "running"}:
        work = "not-completed" if loop_ended or execution == "ended" else "pending"
    else:
        work = "unknown"
        reasons.append(f"unrecognized work status {work_status!r}")

    # Check: only an independent Verification receipt bound to this Work run passes.
    verdict = evidence.get("verificationReceipt")
    if verdict is not None and (verdict.get("verifiedWorkRunId") != work_id
                                or (request_hash and verdict.get("verifiedRequestHash") not in (None, request_hash))):
        reasons.append("verification receipt is bound to another work run or request revision")
        verdict = None
    check_status = evidence.get("verificationStatus")
    if route in NO_CHECK_ROUTES:
        check = "not-requested"
    elif verdict is not None and verdict.get("decision") in {"pass", "fail"}:
        check = "passed" if verdict["decision"] == "pass" else "failed"
    elif evidence.get("humanSkip") and work == "completed" and check_status != "completed":
        check = "skipped"
    elif check_status == "cancelled":
        check = "cancelled"
    elif check_id and isinstance(check_run, dict) and check_run.get("status") in RUN_ACTIVE:
        check = "in-progress"
    elif check_status == "completed" or (check_id and not isinstance(check_run, dict)):
        check = "unknown"
        reasons.append("verification receipt or run state is unavailable")
    else:
        check = "pending"

    # Waits apply only to the loop's current task while the loop has not ended.
    wait = "none"
    if evidence.get("current") and not loop_ended:
        failure = evidence.get("failureClass")
        if (evidence.get("pendingDecision") or evidence.get("loopStatus") == "needs-human-decision"
                or failure == "human"):
            wait = "decision"
        elif evidence.get("integrationWait"):
            wait = "external"
        elif evidence.get("loopStatus") == "runtime-error":
            wait = "blocked"
            if failure in (None, "unknown"):
                reasons.append("stopped loop has no recognized failure class")

    if wait != "none":
        state = {"decision": "waiting-decision", "external": "waiting-external", "blocked": "blocked"}[wait]
    elif check == "passed":
        state = "check-passed"
    elif work == "completed":
        state = "work-completed"
    elif execution in {"ended", "running"}:
        state = "execution-ended" if execution == "ended" else "running"
    elif execution == "not-started" and evidence.get("assigned") and not loop_ended:
        state = "assigned"
    else:
        state = "unknown"
        if execution == "not-started" and loop_ended:
            # The design has no withdrawn state; the loop's terminal reason stays in the evidence.
            reasons.append("loop ended before this task was dispatched")
    return {"state": state, "execution": execution, "work": work, "check": check, "wait": wait,
            "reasons": reasons}


def _read(path):
    try:
        return safe_read_json(path)
    except (OSError, ValueError, ContractError):
        return None  # An unreadable source leaves its facts unknown.


def _bound_run(agents_root, agent, run_id, task, workflow_id, role):
    """Read one task run and its receipt; a run bound elsewhere counts as unavailable."""
    if not agent or not run_id:
        return None, None
    directory = Path(agents_root) / agent / "runs" / run_id
    run = _read(directory / "state.json")
    bound = (run or {}).get("taskBinding") or {}
    if (run is None or run.get("agentId") != agent or run.get("runId") != run_id or run.get("role") != role
            or bound.get("taskId") != task or bound.get("workflowId") not in (None, workflow_id)):
        return None, None
    return run, _read(directory / "receipt.json") if run.get("status") in RUN_TERMINAL else None


def _decision(state, record_id, source, kind, **fields):
    """One Decision; target, reason, impact and alternatives stay null where the source never recorded them."""
    return {"kind": "decision", "id": record_id, "source": source, "loopId": state.get("loopId"),
            "taskId": None, "sessionId": None, "runId": None, "decisionKind": kind, "decisionScope": None,
            "questionHash": None, "target": None, "reason": None, "impact": None, "alternatives": None,
            **fields}


def project_loop(agents_root, loop_path, failure_class=None):
    """Project one loop state into Task, Decision and Observation records."""
    state = safe_read_json(Path(loop_path))
    workflow = state.get("workflow") or {}
    execution = state.get("execution") or {}
    route = execution.get("taskMode", "work-verification")
    parent = state.get("parentStatePath")
    owner = {"agentId": Path(parent).parents[2].name, "runId": Path(parent).parent.name} if parent else None
    failure = failure_class(state.get("controlPlaneError")) if failure_class else None
    tasks_list = workflow.get("tasks") or []

    decisions = []
    for item in (state.get("decisions") or {}).values():
        response = item.get("response") or {}
        decisions.append(_decision(
            state, item.get("id"), "loop-decision", item.get("kind"),
            taskId=(item.get("taskBinding") or {}).get("taskId"), sessionId=item.get("agentId"),
            runId=item.get("runId"), status=item.get("status"), decided=bool(response),
            decisionScope=item.get("scope"), questionHash=item.get("questionHash"),
            **{key: item.get(key) for key in DETAIL_FIELDS},
            answer=response.get("answer"), authorizationReference=response.get("authorizationReference"),
            evidence=response.get("evidence"), createdAt=item.get("createdAt"), updatedAt=item.get("createdAt")))
    review = state.get("draftReview")
    if isinstance(review, dict) and review.get("status"):
        decisions.append(_decision(
            state, f"draft-review-{state.get('loopId')}", "draft-review", "draft-review",
            sessionId=state.get("workAgentId"), runId=review.get("workRunId"), status=review["status"],
            decided=review["status"] != "pending", paths=copy.deepcopy(review.get("paths")),
            answer=review.get("note"), authorizationReference=review.get("authorizationReference"),
            evidence=review.get("decisionEvidence"), createdAt=review.get("recordedAt"),
            updatedAt=review.get("decidedAt") or review.get("recordedAt")))
    skip = state.get("humanSkip")
    if isinstance(skip, dict):
        decisions.append(_decision(
            state, f"verification-skip-{state.get('loopId')}", "human-skip", "verification-skip",
            status="answered", decided=True, authorizationReference=skip.get("authorizationReference"),
            evidence=skip.get("decisionEvidence"), createdAt=skip.get("recordedAt"),
            updatedAt=skip.get("recordedAt")))
    for record in decisions:
        # Loop-level decisions without a task binding belong to the loop's only task.
        if not record["taskId"] and len(tasks_list) == 1:
            record["taskId"] = tasks_list[0].get("id")

    tasks, observations = [], []
    pending = (state.get("decisions") or {}).get(state.get("pendingDecisionId")) or {}
    for index, task in enumerate(tasks_list):
        task_id = task.get("id")
        found = {}
        for role in ("work", "verification"):
            agent = task.get(role + "AgentId") or state.get(role + "AgentId")
            run_id = task.get(role + "RunId")
            run, receipt = _bound_run(agents_root, agent, run_id, task_id, workflow.get("id"), role)
            found[role] = {"agentId": agent, "runId": run_id, "run": run, "receipt": receipt}
            if run is not None and run.get("status") in RUN_TERMINAL:
                # A run-end fact sheet; the conductor's supervision verdict is not recorded yet.
                receipt = receipt or {}
                addressed = receipt.get("verifiedRequestHash") or receipt.get("requestHash")
                observations.append({
                    "kind": "observation", "id": "observation-" + run_id, "taskId": task_id,
                    "loopId": state.get("loopId"), "sessionId": agent, "runId": run_id, "role": role,
                    "trigger": "run-ended", "observedAt": run.get("finishedAt") or run.get("updatedAt"),
                    "runStatus": run.get("status"),
                    "verdict": receipt.get("decision" if role == "verification" else "outcome"),
                    "assessment": "unknown", "action": None, "requestHash": addressed,
                    "currentRevision": addressed == task.get("requestHash") if addressed and task.get("requestHash") else None,
                    "findings": copy.deepcopy(receipt.get("findings")),
                    "artifacts": {name: str(Path(agents_root) / agent / "runs" / run_id / name)
                                  for name in ("result.md", "receipt.json", "events.jsonl")}})
        work, check = found["work"], found["verification"]
        current = index == workflow.get("index", 0)
        status = classify({
            "route": route, "current": current, "assigned": bool(work["agentId"]),
            "requestHash": task.get("requestHash"), "loopStatus": state.get("status"),
            "workStatus": task.get("workStatus"), "verificationStatus": task.get("verificationStatus"),
            "workRunId": work["runId"], "verificationRunId": check["runId"],
            "workRun": work["run"], "verificationRun": check["run"],
            "workReceipt": work["receipt"], "verificationReceipt": check["receipt"],
            "failureClass": failure, "pendingDecision": pending.get("status") == "pending",
            "pendingDispatch": bool(state.get("pendingDispatch")),
            "integrationWait": bool(state.get("integrationWait")), "humanSkip": bool(state.get("humanSkip"))})
        allocation = task.get("allocation") or {}
        error = state.get("controlPlaneError") if current else None
        updated = [value for value in (state.get("updatedAt"), (work["run"] or {}).get("updatedAt"),
                                       (check["run"] or {}).get("updatedAt")) if isinstance(value, str)]
        tasks.append({
            "kind": "task", "id": task_id, "workflowId": workflow.get("id"),
            "workflowTitle": workflow.get("title"), "loopId": state.get("loopId"), "statePath": str(loop_path),
            "title": task.get("title"), "requestPath": task.get("requestPath"),
            "completionCriteria": task.get("completionCriteria"),
            "inputs": copy.deepcopy(allocation.get("inputs", [])),
            "dependencies": copy.deepcopy(allocation.get("dependencies", [])),
            "scope": {"readScope": copy.deepcopy(allocation.get("readScope")),
                      "writeScopeReason": allocation.get("writeScopeReason"),
                      "documentPaths": copy.deepcopy(task.get("documentPaths"))},
            "route": route, "workProfile": execution.get("workProfile"),
            "sessions": {"conductor": owner,
                         **{role: {"agentId": found[role]["agentId"], "runId": found[role]["runId"],
                                   "model": ((found[role]["run"] or {}).get("executionOptions") or {}).get("model")}
                            if found[role]["agentId"] else None for role in found}},
            # Loops accepted before revisions were recorded have no number; the hash still binds content.
            "revision": {"requestHash": task.get("requestHash"), "number": task.get("requestRevision"),
                         "loopRevisionCount": state.get("revisionCount", 0),
                         "stateRevision": state.get("stateRevision", 0)},
            "status": status,
            "statusEvidence": {
                "loopStatus": state.get("status"), "loopPhase": state.get("phase"),
                "workStatus": task.get("workStatus"), "verificationStatus": task.get("verificationStatus"),
                "workRunStatus": (work["run"] or {}).get("status"),
                "verificationRunStatus": (check["run"] or {}).get("status"),
                "workReceiptOutcome": (work["receipt"] or {}).get("outcome"),
                "verificationDecision": (check["receipt"] or {}).get("decision"),
                "failureClass": failure if current else None,
                "errorCode": error.get("code") if isinstance(error, dict) else None,
                "terminalReason": copy.deepcopy(state.get("terminalReason")),
            },
            "decisionIds": [record["id"] for record in decisions if record["taskId"] == task_id],
            "observationIds": [item["id"] for item in observations if item["taskId"] == task_id],
            "updatedAt": max(updated) if updated else None,
        })
    return tasks, decisions, observations


def project_session(agents_root, agent_id):
    """Project a Session from its newest run; at most one run per agent is active at a time."""
    runs = Path(agents_root) / agent_id / "runs"
    run_ids = sorted(path.name for path in runs.iterdir() if path.is_dir()) if runs.is_dir() else []
    latest = (_read(runs / run_ids[-1] / "state.json") if run_ids else None) or {}
    options = latest.get("executionOptions") or {}
    status = latest.get("status")
    return {
        "kind": "session", "id": agent_id, "role": latest.get("role"), "provider": latest.get("provider"),
        "providerSessionId": latest.get("sessionId"), "model": options.get("model"),
        "reasoningEffort": options.get("reasoningEffort"), "workProfile": latest.get("workProfile"),
        "runCount": len(run_ids), "latestRunId": run_ids[-1] if run_ids else None, "latestRunStatus": status,
        "running": status in RUN_ACTIVE if latest else None,
        "activeRunId": run_ids[-1] if status in RUN_ACTIVE else None,
        # No runtime record captures a handoff acknowledgement yet.
        "handoff": "unknown", "updatedAt": latest.get("updatedAt"),
    }


def query(agents_root, *, task_id=None, session_id=None, loop_id=None, state=None, updated_since=None,
          failure_class=None) -> dict:
    """Structural (layer 1) lookup by task, session, loop, state and update time; filters combine with AND.

    Every loop is read so each Session's owned tasks stay complete regardless of the filters.
    """
    if state is not None and state not in STATES:
        raise ValueError(f"unknown state {state!r}; expected one of {', '.join(STATES)}")
    tasks, decisions, observations, errors = [], [], [], []
    for path in sorted(Path(agents_root).glob("*/loops/*/state.json")):
        try:
            loop_tasks, loop_decisions, loop_observations = project_loop(agents_root, path, failure_class)
        except (OSError, ValueError, KeyError, TypeError, ContractError) as error:
            errors.append({"source": str(path), "error": f"{type(error).__name__}: {error}"})
            continue
        tasks += loop_tasks
        decisions += loop_decisions
        observations += loop_observations

    def sessions_of(task):
        return {owned["agentId"]: role for role, owned in task["sessions"].items() if owned}
    owned_tasks: dict[str, list] = {}
    for task in tasks:
        for agent, role in sessions_of(task).items():
            owned_tasks.setdefault(agent, []).append({"loopId": task["loopId"], "taskId": task["id"], "role": role,
                                                      "state": task["status"]["state"]})
    selected = sorted((task for task in tasks
                       if (task_id is None or task["id"] == task_id)
                       and (session_id is None or session_id in sessions_of(task))
                       and (loop_id is None or task["loopId"] == loop_id)
                       and (state is None or task["status"]["state"] == state)
                       and (updated_since is None or (task["updatedAt"] or "") >= updated_since)),
                      key=lambda task: (task["updatedAt"] or "", task["loopId"] or "", task["id"]))
    keys = {(task["loopId"], task["id"]) for task in selected}
    agents = sorted({agent for task in selected for agent in sessions_of(task)} | ({session_id} if session_id else set()))
    sessions = [{**project_session(agents_root, agent), "ownedTasks": owned_tasks.get(agent, [])}
                for agent in agents if (Path(agents_root) / agent).is_dir()]
    return {
        "schemaVersion": 1, "kind": "operations-records",
        "filters": {"taskId": task_id, "sessionId": session_id, "loopId": loop_id, "state": state,
                    "updatedSince": updated_since},
        "tasks": selected, "sessions": sessions,
        "decisions": [item for item in decisions if (item["loopId"], item["taskId"]) in keys],
        "observations": [item for item in observations if (item["loopId"], item["taskId"]) in keys],
        "errors": errors,
    }


SEARCH_KINDS = ("task", "session", "decision", "observation", "lesson")


def _instant(value):
    """An ISO-8601 time as an aware UTC instant; a date or zoneless time counts as UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _file_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace") if path else ""
    except OSError:
        return ""


def excerpt(text, terms, width=80):
    """A short single-line window around the first matched term, or the opening text."""
    folded = text.casefold()
    at = min((folded.find(term) for term in terms if term in folded), default=-1)
    start = max(0, at - width) if at >= 0 else 0
    end = at + width if at >= 0 else 2 * width
    return ("…" if start else "") + " ".join(text[start:end].split()) + ("…" if end < len(text) else "")


def search(agents_root, *, text=None, match="all", kinds=SEARCH_KINDS, lessons=(), semantic=None,
           task_id=None, session_id=None, loop_id=None, state=None, role=None, model=None,
           since=None, until=None, limit=50, failure_class=None) -> dict:
    """Layer 1 filters over the four records and lessons, then layer 2 lexical matching of their texts.

    Texts: a task's title, completion criteria and request file; a decision's recorded fields; an
    observation's run result; a session's identity; a lesson's metadata and body. `lessons` are lesson
    records whose `path` names their body. Lessons carry no task, loop, state or model, so those filters
    exclude them; a session filter keeps lessons with an occurrence from that agent.
    `semantic(text, hits)` is the optional layer 3 hook returning `[(hit, score)]`; no provider is
    bundled. Hits cite their source path; they never decide ownership or state.
    """
    if match not in ("all", "any"):
        raise ValueError("match must be all or any")
    low, high = _instant(since), _instant(until)
    if (since and low is None) or (until and high is None):
        raise ValueError("since and until must be ISO-8601 dates or times")

    def in_period(*values):
        if low is None and high is None:
            return True
        return any(moment is not None and (low is None or moment >= low) and (high is None or moment <= high)
                   for moment in map(_instant, values))

    records = query(agents_root, task_id=task_id, session_id=session_id, loop_id=loop_id, state=state,
                    failure_class=failure_class)
    tasks = {(task["loopId"], task["id"]): task for task in records["tasks"]
             if in_period(task["updatedAt"])
             and (role is None or task["sessions"].get(role) or task["workProfile"] == role)
             and (model is None or any((owned or {}).get("model") == model for owned in task["sessions"].values()))}
    candidates = []

    def add(kind, record_id, path, body, moment, **links):
        candidates.append({"kind": kind, "id": record_id, "path": str(path) if path else None, "body": body,
                           "updatedAt": moment, **links})
    if "task" in kinds:
        for task in tasks.values():
            add("task", task["id"], task["requestPath"] or task["statePath"],
                "\n".join(filter(None, (task["title"], task["completionCriteria"], _file_text(task["requestPath"])))),
                task["updatedAt"], loopId=task["loopId"], taskId=task["id"],
                sessionId=(task["sessions"]["work"] or {}).get("agentId"), state=task["status"]["state"])
    if "decision" in kinds:
        for item in records["decisions"]:
            task = tasks.get((item["loopId"], item["taskId"]))
            if task and in_period(item["updatedAt"]):
                add("decision", item["id"], task["statePath"], json.dumps(item, ensure_ascii=False),
                    item["updatedAt"], loopId=item["loopId"], taskId=item["taskId"], sessionId=item["sessionId"])
    if "observation" in kinds:
        for item in records["observations"]:
            if ((item["loopId"], item["taskId"]) in tasks and in_period(item["observedAt"])
                    and (role not in ("work", "verification") or item["role"] == role)):
                add("observation", item["id"], item["artifacts"]["result.md"],
                    _file_text(item["artifacts"]["result.md"]), item["observedAt"], loopId=item["loopId"],
                    taskId=item["taskId"], sessionId=item["sessionId"], role=item["role"])
    if "session" in kinds:
        for session in records["sessions"]:
            if ((role is None or role in (session["role"], session["workProfile"]))
                    and (model is None or session["model"] == model) and in_period(session["updatedAt"])):
                add("session", session["id"], Path(agents_root) / session["id"],
                    json.dumps({key: value for key, value in session.items() if key != "ownedTasks"},
                               ensure_ascii=False), session["updatedAt"], sessionId=session["id"])
    if "lesson" in kinds and not any((task_id, loop_id, state, role, model)):
        for lesson in lessons:
            occurrences = lesson.get("occurrences") or []
            if ((session_id is None or any(f"/agents/{session_id}/" in str(item.get("source")) for item in occurrences))
                    and in_period(*(item.get("recordedAt") for item in occurrences))):
                body = json.dumps({key: value for key, value in lesson.items() if key != "path"}, ensure_ascii=False)
                # The readable body first, so excerpts show prose rather than metadata.
                add("lesson", lesson["id"], lesson.get("path"), _file_text(lesson.get("path")) + "\n" + body,
                    max((item.get("recordedAt") or "" for item in occurrences), default=None),
                    scope=lesson.get("scope"), status=lesson.get("status"))

    terms = (text or "").casefold().split()
    if terms and semantic is not None:
        scored, mode = semantic(text, candidates), "semantic"
    elif terms:
        predicate = all if match == "all" else any
        folded = [(hit, hit["body"].casefold()) for hit in candidates]
        scored = [(hit, sum(body.count(term) for term in terms)) for hit, body in folded
                  if predicate(term in body for term in terms)]
        mode = "lexical"
    else:
        scored, mode = [(hit, 0) for hit in candidates], "structured"
    ranked = sorted(scored, key=lambda pair: (pair[1], _instant(pair[0]["updatedAt"] or "") or datetime.min.replace(tzinfo=timezone.utc)),
                    reverse=True)
    hits = [{**{key: value for key, value in hit.items() if key != "body"}, "score": score,
             "excerpt": excerpt(hit["body"], terms)} for hit, score in ranked[:limit]]
    return {"schemaVersion": 1, "kind": "operations-search", "mode": mode, "text": text, "match": match,
            "filters": {"kinds": list(kinds), "taskId": task_id, "sessionId": session_id, "loopId": loop_id,
                        "state": state, "role": role, "model": model, "since": since, "until": until},
            "total": len(scored), "hits": hits, "errors": records["errors"]}
