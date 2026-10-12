"""Persistent workers, their tasks and the runs of each task, read from existing records.

A worker is a stable session (agentId) that outlives any one task; a task is the
accepted taskBinding (Main, workflow, task); a run is one execution with its own
request, result and receipt. Finishing a task never ends the worker.

Reads are sequential observations, never a scheduler: nothing here picks a worker
for Main. Candidates are listed with exact exclusion reasons, and loop start
re-checks the named workers under one project lock so two starts cannot hand the
same session to two tasks. Records are never rewritten here; the only state this
module adds is the start-time assignment evidence loop.py stores in a new loop.
"""
from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
from pathlib import Path

from storage.errors import ContractError

SCHEMA_VERSION = 1
WORKER_ROLES = ("work", "verification")
ENDED_LOOPS = {"completed", "cancelled", "failed"}
TERMINAL_RUNS = {"completed", "needs-human-decision", "failed", "cancelled", "runtime-error"}
ASSIGNMENT_LOCK = ".team-assignment.lock"
# Holds that make a worker unavailable for another task, strongest first.
BLOCKING = ("uncertain", "waiting-human", "busy", "queued")


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read(runtime, path, problems, **identity):
    try:
        return runtime.safe_read_json(path)
    except (ContractError, OSError, ValueError) as error:
        problems.append({**identity, "path": str(path), "code": getattr(error, "code", "record_unreadable"),
                         "message": str(error)})
        return None


def observe(runtime, root):
    """One pass over sessions, runs and loops; unreadable records become problems, not silent gaps."""
    workers, loops, problems = {}, [], []
    for directory in runtime.iter_agent_directories(root):
        agent = directory.name
        entry = {"agentId": agent, "session": None, "runs": [], "problems": []}
        if (directory / "session.json").exists():
            entry["session"] = _read(runtime, directory / "session.json", entry["problems"], agentId=agent, kind="session")
        runs = directory / "runs"
        if runs.is_dir() and not runs.is_symlink():
            for item in sorted(runs.iterdir(), key=lambda path: path.name):
                if not item.is_dir() or item.is_symlink() or not (item / "state.json").exists():
                    continue  # A run directory without state never accepted a run.
                state = _read(runtime, item / "state.json", entry["problems"], agentId=agent, kind="run", runId=item.name)
                if state is not None:
                    entry["runs"].append(state)
        for path in sorted((directory / "loops").glob("*/state.json")) if (directory / "loops").is_dir() else ():
            state = _read(runtime, path, entry["problems"], agentId=agent, kind="loop", loopId=path.parent.name)
            if state is not None:
                loops.append({"ownerAgentId": agent, "path": path, "state": state})
        problems.extend(entry["problems"])
        workers[agent] = entry
    return {"observedAt": _now(), "workers": workers, "loops": loops, "problems": problems}


def _loop_tasks(state):
    workflow = state.get("workflow")
    if workflow and workflow.get("tasks"):
        return workflow, workflow["tasks"], workflow.get("index", 0)
    # Loops accepted before workflows carry one implicit task bound in execution.
    binding = (state.get("execution") or {}).get("taskBinding") or {}
    return {"id": binding.get("workflowId")}, [{"id": binding.get("taskId"),
        "workRunId": state.get("latestWorkRunId"), "verificationRunId": state.get("latestVerificationRunId")}], 0


def _requests_verification(state):
    return (state.get("execution") or {}).get("taskMode", "work-verification") not in {"work", "plan-work"}


def _parent_agent(state):
    parent = state.get("parentStatePath")
    return Path(parent).parent.parent.parent.name if parent else None


def holds(observation):
    """What each worker is still bound to: unfinished loop positions and unlooped active or waiting runs."""
    held, referenced = {}, set()
    for loop in observation["loops"]:
        state = loop["state"]
        for key in ("latestWorkRunId", "latestVerificationRunId"):
            referenced.add(state.get(key))
        referenced.add((state.get("currentChild") or {}).get("runId"))
        workflow, tasks, index = _loop_tasks(state)
        for task in tasks:
            referenced.update((task.get("workRunId"), task.get("verificationRunId")))
        status = state.get("status")
        if status in ENDED_LOOPS:
            continue
        for position, task in enumerate(tasks):
            if position < index:
                continue
            for role in WORKER_ROLES:
                if role == "verification" and not _requests_verification(state):
                    continue
                agent = task.get(role + "AgentId", state.get(role + "AgentId"))
                if not agent:
                    continue
                current = position == index
                kind = ("waiting-human" if status == "needs-human-decision" and current else
                        "failed" if status == "runtime-error" else "busy" if current else "queued")
                held.setdefault(agent, []).append({
                    "kind": kind, "source": "loop", "loopId": state.get("loopId"), "ownerAgentId": loop["ownerAgentId"],
                    "loopStatus": status, "phase": state.get("phase"), "parentAgentId": _parent_agent(state),
                    "workflowId": workflow.get("id"), "taskId": task.get("id"), "role": role,
                    "position": "current" if current else "queued", "runId": task.get(role + "RunId"),
                    "statePath": str(loop["path"])})
    for agent, entry in observation["workers"].items():
        runs = sorted(entry["runs"], key=lambda run: (run.get("acceptedAt") or "", run.get("runId") or ""))
        for run in runs:
            if run.get("status") in {"accepted", "queued", "starting", "running", "cancelling"}:
                held.setdefault(agent, []).append(_run_hold("busy", run))
        latest = runs[-1] if runs else None
        if latest and latest.get("status") == "needs-human-decision" and latest.get("runId") not in referenced:
            # A direct run's pending question resumes this same session; a looped one is held by its loop.
            held.setdefault(agent, []).append(_run_hold("waiting-human", latest))
        for problem in entry["problems"]:
            held.setdefault(agent, []).append({"kind": "uncertain", "source": problem["kind"], "code": problem["code"],
                                               "path": problem["path"], "message": problem["message"]})
    return held


def _binding(run):
    """The accepted task identity; the immutable dispatch tuple carries the same binding."""
    return run.get("taskBinding") or (run.get("dispatchTuple") or {}).get("taskBinding") or {}


def _run_hold(kind, run):
    binding = _binding(run)
    return {"kind": kind, "source": "run", "runId": run.get("runId"), "runStatus": run.get("status"),
            "parentAgentId": run.get("parentAgentId"), "workflowId": binding.get("workflowId"),
            "taskId": binding.get("taskId"), "role": run.get("role"), "statePath": run.get("statePath")}


def availability(worker_holds):
    kinds = {hold["kind"] for hold in worker_holds}
    return next((kind for kind in BLOCKING if kind in kinds), "idle")


def _profile(entry):
    session = entry["session"] or {}
    latest = max(entry["runs"], key=lambda run: (run.get("acceptedAt") or "", run.get("runId") or ""), default={})
    options = latest.get("executionOptions") or {}
    return {"role": session.get("role"), "provider": session.get("provider", "codex") if session else None,
            "model": session.get("model"), "reasoningEffort": session.get("reasoningEffort"),
            "fast": session.get("fast"), "humanApprovalPolicy": session.get("humanApprovalPolicy", "required") if session else None,
            "sandbox": session.get("sandbox"), "workProfile": latest.get("workProfile"),
            "lastModel": options.get("model"), "worktree": copy.deepcopy(session.get("worktree")),
            "taskWorkspace": copy.deepcopy(session.get("taskWorkspace"))}


def _domain(domains, agent):
    if domains is None:
        return None, False
    assignment = domains["assignments"].get(agent)
    domain = next((item for item in domains["domains"] if assignment and item["id"] == assignment.get("domainId")), None)
    placed = None
    if domain:
        placed = {"domainId": domain["id"], "name": domain.get("name"), "setBy": (assignment.get("setBy") or {}).get("actor")}
    return placed, agent in domains.get("removedWorkers", {})


def _run_entry(run, trigger):
    binding = _binding(run)
    tuple_ = run.get("dispatchTuple") or {}
    terminal = run.get("status") in TERMINAL_RUNS
    result = run.get("resultPath")
    receipt = run.get("receiptPath")
    return {"runId": run.get("runId"), "agentId": run.get("agentId"), "role": run.get("role"),
            "status": run.get("status"), "trigger": trigger, "operation": tuple_.get("operation"),
            "attempt": run.get("attempt"), "sessionId": run.get("sessionId"),
            "dispatchId": run.get("dispatchId"), "acceptedAt": run.get("acceptedAt"),
            "startedAt": run.get("startedAt"), "updatedAt": run.get("updatedAt"),
            "workProfile": run.get("workProfile"), "model": (run.get("executionOptions") or {}).get("model"),
            "provider": run.get("provider"),
            "parentAgentId": run.get("parentAgentId"), "parentRunId": run.get("parentRunId"),
            "workflowId": binding.get("workflowId"), "taskId": binding.get("taskId"),
            "taskRequestHash": binding.get("requestHash"), "verifiedWorkRunId": run.get("verifiedWorkRunId"),
            "requestPath": run.get("requestPath"), "requestHash": run.get("requestHash"),
            "receiptRequestHash": run.get("receiptRequestHash"),
            "resultPath": result, "receiptPath": receipt, "statePath": run.get("statePath"),
            # Existence is observed now; a terminal run without its result is reported, never filled from a later one.
            "report": ("pending" if not terminal else
                       "present" if result and Path(result).is_file() else "missing"),
            "receipt": ("pending" if not terminal else
                        "present" if receipt and Path(receipt).is_file() else "missing"),
            "error": copy.deepcopy(run.get("error")), "decisionKind": run.get("decisionKind"),
            "decisionScope": run.get("decisionScope"), "cancelRequested": run.get("cancelRequested", False)}


def _continuations(state):
    """Runs a loop started for a reason other than a plain revision: answers, additions, recovery, handoff."""
    found = {item["runId"]: item["trigger"] for item in state.get("dispatchHistory", []) if item.get("trigger")}
    for decision in (state.get("decisions") or {}).values():
        if decision.get("continuationRunId"):
            found.setdefault(decision["continuationRunId"], "decision-answer")
    for item in state.get("steering", []):
        if item.get("continuationRunId"):
            found.setdefault(item["continuationRunId"], "steering")
    recovery = state.get("receiptRecovery") or {}
    if recovery.get("recoveryWorkRunId"):
        found.setdefault(recovery["recoveryWorkRunId"], "receipt-recovery")
    for handoff in state.get("handoffs", []):
        if handoff.get("toRunId"):
            found.setdefault(handoff["toRunId"], "handoff")
    return found


def _task_state(loop_state, position, index, task, verification):
    status = loop_state.get("status")
    if status not in ENDED_LOOPS and position > index:
        return "queued"
    if status not in ENDED_LOOPS and position == index:
        return {"needs-human-decision": "waiting-human", "runtime-error": "failed"}.get(status, "current")
    done = task.get("workStatus") == "completed" and (not verification or task.get("verificationStatus") == "completed")
    if done or (loop_state.get("humanSkip") and task.get("workStatus") == "completed"):
        return "completed"
    return {"cancelled": "cancelled", "failed": "failed"}.get(status, task.get("workStatus") or "unknown")


def _run_state(status):
    return {"accepted": "current", "queued": "current", "starting": "current", "running": "current",
            "cancelling": "current", "needs-human-decision": "waiting-human"}.get(status, status or "unknown")


def tasks_for(observation, agent):
    """Every task this worker ran or is assigned, newest first, each with all of its runs in order."""
    entry = observation["workers"].get(agent) or {"runs": []}
    tasks = {}

    def task(key):
        return tasks.setdefault(key, {"parentAgentId": key[0], "workflowId": key[1], "taskId": key[2],
                                      "title": None, "completionCriteria": None, "domain": None, "state": None,
                                      "loops": [], "runs": [], "_continuations": {}, "_dispatches": {},
                                      "userRevisionCount": None})

    for loop in observation["loops"]:
        state = loop["state"]
        workflow, items, index = _loop_tasks(state)
        verification = _requests_verification(state)
        for position, item in enumerate(items):
            roles = [role for role in WORKER_ROLES if item.get(role + "AgentId", state.get(role + "AgentId")) == agent
                     and (role == "work" or verification)]
            if not roles:
                continue
            record = task((_parent_agent(state), workflow.get("id"), item.get("id")))
            record.update(title=item.get("title"), completionCriteria=item.get("completionCriteria"),
                          domain=(item.get("allocation") or {}).get("domain"), userRevisionCount=item.get("userRevisionCount"))
            record["loops"].append({"loopId": state.get("loopId"), "ownerAgentId": loop["ownerAgentId"],
                                    "statePath": str(loop["path"]), "loopStatus": state.get("status"),
                                    "phase": state.get("phase"), "roles": roles, "position": position,
                                    "current": position == index and state.get("status") not in ENDED_LOOPS,
                                    "workStatus": item.get("workStatus"), "verificationStatus": item.get("verificationStatus"),
                                    "requestRevision": item.get("requestRevision"), "requestPath": item.get("requestPath"),
                                    "requestHash": item.get("requestHash"),
                                    "assignment": copy.deepcopy(state.get("teamAssignment")) if position == 0 else None,
                                    "taskState": _task_state(state, position, index, item, verification)})
            record["_continuations"].update(_continuations(state))
            record["_dispatches"].update({item["runId"]: item for item in state.get("dispatchHistory", [])
                                          if item.get("taskId") == record["taskId"]})
    for run in entry["runs"]:
        binding = _binding(run)
        key = (run.get("parentAgentId"), binding.get("workflowId"), binding.get("taskId")) if binding else (None, None, None)
        record = task(key)
        if binding:
            record["title"] = record["title"] or binding.get("title")
            record["completionCriteria"] = record["completionCriteria"] or binding.get("completionCriteria")
            record["domain"] = record["domain"] or (binding.get("allocation") or {}).get("domain")
        record["runs"].append(run)
    result = []
    for record in tasks.values():
        continuations = record.pop("_continuations")
        dispatches = record.pop("_dispatches")
        runs = sorted(record["runs"], key=lambda run: (run.get("acceptedAt") or "", run.get("runId") or ""))
        entries, seen_work = [], False
        for run in runs:
            if run.get("role") == "verification":
                trigger = "verification"
            elif run.get("runId") in continuations:
                trigger = continuations[run["runId"]]
            elif record["taskId"] is None:
                trigger = "untracked"  # No taskBinding: a Main, conversation or legacy run.
            else:
                trigger = "revision" if seen_work else "initial"
            seen_work = seen_work or run.get("role") == "work"
            entry = _run_entry(run, trigger)
            dispatch = dispatches.get(run.get("runId")) or {}
            entry.update({key: dispatch.get(key) for key in ("requestRevision", "userRevisionNumber", "context")})
            entries.append(entry)
        record["runs"] = entries
        record["latestRunId"] = entries[-1]["runId"] if entries else None
        loop_states = [loop["taskState"] for loop in record["loops"]]
        record["state"] = (next((value for value in ("current", "waiting-human", "failed", "queued") if value in loop_states), None)
                           or (loop_states[-1] if loop_states else _run_state(entries[-1]["status"]) if entries else "unknown"))
        record["lastActivityAt"] = max([run["updatedAt"] or run["acceptedAt"] or "" for run in entries] or [""]) or None
        result.append(record)
    result.sort(key=lambda item: (item["lastActivityAt"] or "", item["workflowId"] or "", item["taskId"] or ""), reverse=True)
    return result


def _read_domains(runtime, root):
    from tasks import domains
    try:
        binding = runtime.runtime_paths.resolve(root)
        return domains.read(Path(binding["runtimeRoot"])), None
    except (ContractError, OSError, ValueError) as error:
        return None, {"code": getattr(error, "code", "domain_store_unreadable"), "message": str(error)}


def worker_view(observation, held, domains, agent, task_list=None):
    # A worker named for a queued task may have no session or records yet.
    entry = observation["workers"].get(agent) or {"agentId": agent, "session": None, "runs": [], "problems": []}
    domain, removed = _domain(domains, agent)
    worker_holds = held.get(agent, [])
    task_list = tasks_for(observation, agent) if task_list is None else task_list
    counts = {}
    for item in task_list:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    latest = max(entry["runs"], key=lambda run: (run.get("acceptedAt") or "", run.get("runId") or ""), default=None)
    return {"agentId": agent, **_profile(entry), "domain": domain, "removed": removed,
            "availability": availability(worker_holds), "holds": copy.deepcopy(worker_holds),
            "attention": [hold for hold in worker_holds if hold["kind"] == "failed"],
            "currentTasks": [_task_summary(item) for item in task_list if item["state"] in {"current", "waiting-human"}],
            "queuedTasks": [_task_summary(item) for item in task_list if item["state"] == "queued"],
            "failedTasks": [_task_summary(item) for item in task_list if item["state"] == "failed"],
            "taskCounts": counts, "runCount": len(entry["runs"]),
            "latestRun": _run_entry(latest, None) if latest else None,
            "problems": copy.deepcopy(entry["problems"])}


def _task_summary(item):
    return {key: item[key] for key in ("parentAgentId", "workflowId", "taskId", "title", "state", "latestRunId")}


def _is_worker(entry):
    session = entry["session"]
    if session is not None:
        return session.get("role") in WORKER_ROLES
    # No session yet: a worker only while it has runs or unreadable records.
    return bool(entry["runs"] or entry["problems"]) and all(run.get("role") in WORKER_ROLES for run in entry["runs"])


def roster(runtime, root):
    """Workers grouped by domain with current, queued, waiting and failed tasks; history is one call away."""
    observation = observe(runtime, root)
    held = holds(observation)
    domains, domain_error = _read_domains(runtime, root)
    agents = {agent for agent, entry in observation["workers"].items() if _is_worker(entry)} | set(held)
    workers = [worker_view(observation, held, domains, agent) for agent in sorted(agents)]
    groups = []
    for domain in (domains or {}).get("domains", []):
        members = [worker["agentId"] for worker in workers if (worker["domain"] or {}).get("domainId") == domain["id"]]
        groups.append({"domainId": domain["id"], "name": domain.get("name"), "workers": members})
    return {"schemaVersion": SCHEMA_VERSION, "kind": "team-roster", "consistency": "sequential-observations",
            "domainsRevision": (domains or {}).get("revision"),
            "domainError": domain_error, "domains": groups,
            "unplaced": [worker["agentId"] for worker in workers if worker["domain"] is None],
            "workers": workers, "problems": observation["problems"]}


def history(runtime, root, agent, workflow_id=None, task_id=None, parent_agent=None):
    """All tasks and runs of one worker, or one exact task; every run keeps its own request, result and receipt."""
    runtime.validate_id(agent, runtime.AGENT_ID, "agent_id")
    observation = observe(runtime, root)
    held = holds(observation)
    if agent not in observation["workers"] and agent not in held:
        raise ContractError("team_worker_missing", f"No records exist for worker {agent}")
    domains, _ = _read_domains(runtime, root)
    task_list = tasks_for(observation, agent)
    selected = [item for item in task_list
                if (workflow_id is None or item["workflowId"] == workflow_id)
                and (task_id is None or item["taskId"] == task_id)
                and (parent_agent is None or item["parentAgentId"] == parent_agent)]
    if (workflow_id or task_id or parent_agent) and not selected:
        raise ContractError("team_task_missing", "This worker has no records for the selected task")
    return {"schemaVersion": SCHEMA_VERSION, "kind": "team-history", "consistency": "sequential-observations",
            "worker": worker_view(observation, held, domains, agent, task_list), "tasks": selected}


def compare(profile, requirements):
    """Exact differences between a worker's recorded profile and what a new task requires."""
    differences = []

    def differ(code, field, wanted, actual):
        differences.append({"code": code, "field": field, "required": wanted, "recorded": actual})

    if requirements.get("role") and profile["role"] != requirements["role"]:
        differ("role-mismatch", "role", requirements["role"], profile["role"])
    model = requirements.get("model")
    provider = requirements.get("provider")
    if model and not provider:
        from adapters import provider_for
        with contextlib.suppress(ContractError):
            provider = provider_for(model)
    if provider and profile["provider"] != provider:
        differ("provider-mismatch", "provider", provider, profile["provider"])
    # The same model name never makes two workers one; it only compares this worker's own setting.
    if model and (profile["model"] or profile["lastModel"]) != model:
        differ("model-mismatch", "model", model, profile["model"] or profile["lastModel"])
    for code, field in (("effort-mismatch", "reasoningEffort"), ("fast-mismatch", "fast")):
        if requirements.get(field) is not None and profile[field] is not None and profile[field] != requirements[field]:
            differ(code, field, requirements[field], profile[field])
    # Work runs without a label used the default Expert (work) profile.
    recorded_profile = profile["workProfile"] or ("work" if profile["role"] == "work" else None)
    if requirements.get("workProfile") and recorded_profile and recorded_profile != requirements["workProfile"]:
        differ("profile-mismatch", "workProfile", requirements["workProfile"], recorded_profile)
    for field in ("humanApprovalPolicy", "sandbox"):
        if requirements.get(field) and profile[field] and profile[field] != requirements[field]:
            differ("permission-mismatch", field, requirements[field], profile[field])
    return differences


def candidates(runtime, root, requirements):
    """Existing workers that fit, and every other worker with its exclusion reasons; Main still decides."""
    if requirements.get("role") not in WORKER_ROLES:
        raise ContractError("team_role_invalid", "Candidates are listed for the work or verification role")
    observation = observe(runtime, root)
    held = holds(observation)
    domains, domain_error = _read_domains(runtime, root)
    eligible, excluded = [], []
    for agent, entry in sorted(observation["workers"].items()):
        if not _is_worker(entry):
            continue
        view = worker_view(observation, held, domains, agent)
        reasons = [{"code": hold["kind"], **{key: hold.get(key) for key in ("source", "loopId", "runId", "workflowId", "taskId", "code") if hold.get(key)}}
                   for hold in view["holds"] if hold["kind"] in BLOCKING]
        if view["removed"]:
            reasons.append({"code": "removed-by-human"})
        if entry["session"] is None:
            reasons.append({"code": "session-missing"})
        else:
            reasons.extend(compare(view, requirements))
        summary = {key: view[key] for key in ("agentId", "role", "provider", "model", "reasoningEffort", "fast",
                                              "workProfile", "humanApprovalPolicy", "sandbox", "domain", "availability",
                                              "attention", "taskCounts", "runCount")}
        summary["lastActivityAt"] = (view["latestRun"] or {}).get("updatedAt") or (view["latestRun"] or {}).get("acceptedAt")
        summary["sameDomain"] = bool(requirements.get("domain") and view["domain"]
                                     and view["domain"]["name"] == requirements["domain"])
        (excluded if reasons else eligible).append({**summary, **({"reasons": reasons} if reasons else {})})
    # Order only presents evidence (same domain, then most recent activity); it selects nothing.
    eligible.sort(key=lambda item: item["lastActivityAt"] or "", reverse=True)
    eligible.sort(key=lambda item: not item["sameDomain"])
    return {"schemaVersion": SCHEMA_VERSION, "kind": "team-candidates", "consistency": "sequential-observations",
            "requirements": copy.deepcopy(requirements),
            "eligible": eligible, "excluded": excluded, "domainError": domain_error,
            # Without a fitting worker Main records why it creates one (allocation.session.reason).
            "newWorkerReasonRequired": not eligible,
            "recheck": "loop.py start re-checks the named workers under the project assignment lock"}


def assignment_lock(runtime, root):
    binding = runtime.runtime_paths.resolve(root, create=True)
    return runtime.file_lock(Path(binding["runtimeRoot"]) / ASSIGNMENT_LOCK)


def check_start(runtime, root, workflow_id, tasks, requirements, verification_agent=None):
    """Refuse a new loop whose workers are still bound elsewhere or contradict Main's recorded session choice.

    Called by loop.py under assignment_lock before the loop is written, so the new
    loop's own hold is visible to the next start. Returns the assignment evidence.
    """
    observation = observe(runtime, root)
    held = holds(observation)
    workers, earlier = [], set()
    named = []
    for task in tasks:
        for role in WORKER_ROLES:
            agent = task.get(role + "AgentId") or (verification_agent if role == "verification" else None)
            if agent and (agent, role) not in named:
                named.append((agent, role))
    for agent, _role in named:
        worker_holds = held.get(agent, [])
        state = availability(worker_holds)
        if state != "idle":
            hold = next(item for item in worker_holds if item["kind"] == state)
            where = (f"loop {hold.get('loopId')} task {hold.get('taskId')}" if hold.get("source") == "loop"
                     else f"run {hold.get('runId')}" if hold.get("runId") else hold.get("path"))
            code = {"uncertain": "worker_uncertain", "waiting-human": "worker_waiting_human"}.get(state, "worker_busy")
            raise ContractError(code, f"Worker {agent} is {state} ({where}); finish, answer or close that task, "
                                      "or assign another worker. No concurrent run is created for one session.")
    for task in tasks:
        agent = task.get("workAgentId")
        allocation = task.get("allocation") or {}
        strategy = (allocation.get("session") or {}).get("strategy")
        entry = observation["workers"].get(agent) or {"session": None, "runs": [], "problems": []}
        exists = entry["session"] is not None
        if agent in earlier:
            continue  # Later tasks of this list continue the session an earlier task opened.
        earlier.add(agent)
        if strategy == "reuse" and not exists:
            raise ContractError("worker_reuse_missing", f"allocation.session.strategy is reuse but worker {agent} has no session; "
                                                        "name an existing worker or record strategy new with its reason")
        # A retried start of this same task is not another task.
        other_tasks = sorted({(_binding(run).get("workflowId"), _binding(run).get("taskId"))
                              for run in entry["runs"]} - {(None, None), (workflow_id, task.get("id"))})
        if strategy == "new" and exists and other_tasks:
            raise ContractError("worker_strategy_conflict", f"allocation.session.strategy is new but worker {agent} already ran "
                                                            "other tasks; use a new agent ID or record strategy reuse")
        differences = compare(_profile(entry), {**requirements, "role": "work"}) if exists else []
        blocking = [item for item in differences if item["code"] in {"role-mismatch", "provider-mismatch"}
                    or strategy == "reuse"]
        if blocking:
            raise ContractError("worker_incompatible", f"Worker {agent} does not fit this task: "
                                + ", ".join(f"{item['field']} {item['recorded']!r} != {item['required']!r}" for item in blocking)
                                + ". Reuse needs the same role, provider, model, tools and permissions; "
                                  "use loop.py handoff to move a task to another model.")
        workers.append({"agentId": agent, "taskId": task.get("id"), "disposition": "reused" if exists else "new",
                        "strategy": strategy, "reason": (allocation.get("session") or {}).get("reason"),
                        "priorTaskCount": len(other_tasks), "priorRunCount": len(entry["runs"]),
                        "differences": differences,
                        "attention": [hold for hold in held.get(agent, []) if hold["kind"] == "failed"]})
    return {"schemaVersion": SCHEMA_VERSION, "checkedAt": observation["observedAt"],
            "requirements": copy.deepcopy(requirements), "workers": workers,
            "checkedAgents": [{"agentId": agent, "role": role} for agent, role in named]}
