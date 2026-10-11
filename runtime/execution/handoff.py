"""Opt-in two-orchestrator state transitions; storage and dispatch retain ownership.

This reducer launches no sessions. Main supplies prepared session identities and
read receipts; callers persist under the conversation dispatch lock before using
the resulting owner/epoch to accept a response or assignment.
"""
from __future__ import annotations

from copy import deepcopy
import contextlib
import hashlib
import json
import os
import math
from pathlib import Path

from execution.usage import fresh_context_percent
from storage.errors import ContractError


def fail(message):
    raise ContractError("handoff_invalid", message)


def configure(*, sessions, prepare_percent, target_percent, max_age_seconds, references):
    if (not isinstance(sessions, dict) or set(sessions) != {"A", "B"}
            or not all(isinstance(v, str) and v for v in sessions.values())
            or sessions["A"] == sessions["B"]):
        fail("A and B require distinct Main-allocated session identities")
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (prepare_percent, target_percent, max_age_seconds))
            or not 0 < prepare_percent < target_percent <= 100 or not max_age_seconds > 0):
        fail("Supply experimental preparation/target percentages and freshness policy")
    if not isinstance(references, list) or not references or not all(isinstance(v, str) and v for v in references):
        fail("Supply shared skills, task/decision/approval originals and record references")
    return {"schemaVersion": 1, "enabled": True, "sessions": dict(sessions), "owner": "A", "epoch": 0,
            "preparePercent": prepare_percent, "targetPercent": target_percent, "maxAgeSeconds": max_age_seconds,
            "references": list(references), "cursor": 0, "events": [], "processed": [],
            "preparation": None, "observation": None, "activeTurn": None, "tools": [], "switches": []}


def authorized(state, slot, epoch):
    return bool(type(epoch) is int and state and state.get("enabled") and state.get("owner") == slot and state.get("epoch") == epoch)


def transition(state, action):
    """Preserve messages/results and fence stale preparation/owner operations.

    Event IDs are stable source IDs, not summary text. A new event invalidates a
    readiness receipt by changing the cursor; preparation can catch up without
    discarding the earlier read evidence. Tool and turn boundaries are explicit.
    """
    value = deepcopy(state)
    kind = action.get("type")
    if kind in {"event", "processed", "turn-start", "turn-end", "tool-start", "tool-end"}:
        if not authorized(value, action.get("slot"), action.get("epoch")):
            fail("Stale owner cannot respond, assign work or acknowledge events")
    if kind == "event":
        identity = action.get("id")
        if not isinstance(identity, str) or not identity or not isinstance(action.get("reference"), str):
            fail("Events require a stable source ID and original reference")
        previous = next((event for event in value["events"] if event["id"] == identity), None)
        if previous and (previous["reference"] != action["reference"] or previous["kind"] != action.get("kind")):
            fail("A source ID cannot change its original reference or event kind")
        if not any(event["id"] == identity for event in value["events"]):
            value["events"].append({"id": identity, "reference": action["reference"], "kind": action.get("kind")})
            value["cursor"] += 1
            value["observation"] = None
    elif kind == "processed":
        identity = action.get("id")
        if not any(event["id"] == identity for event in value["events"]):
            fail("Cannot acknowledge an unknown message/result")
        if identity not in value["processed"]:
            value["processed"].append(identity)
            value["cursor"] += 1
    elif kind == "observe":
        observation = action.get("observation")
        percent = fresh_context_percent(observation, now=action["now"], max_age_seconds=value["maxAgeSeconds"],
                                        session_id=value["sessions"][value["owner"]], turn_id=action.get("turnId"))
        if not authorized(value, action.get("slot"), action.get("epoch")):
            fail("Observation belongs to a former owner")
        value["observation"] = {"value": observation, "turnId": action.get("turnId")} if percent is not None else None
        if percent is not None and percent >= value["preparePercent"] and value["preparation"] is None:
            value["preparation"] = {"slot": "B" if value["owner"] == "A" else "A", "epoch": value["epoch"],
                                    "cursor": value["cursor"], "status": "requested", "receipt": None}
    elif kind in {"ready", "prepare-failed"}:
        prep = value["preparation"]
        if not prep or prep["slot"] != action.get("slot") or prep["epoch"] != action.get("epoch"):
            fail("Preparation receipt is stale or belongs to another slot")
        if kind == "ready":
            if action.get("cursor") != value["cursor"] or action.get("references") != value["references"]:
                fail("Read receipt must cover current messages/results and shared original references")
            if not isinstance(action.get("receipt"), str) or not action["receipt"]:
                fail("Readiness requires a stored successful preparation result reference")
            prep.update(status="ready", cursor=value["cursor"], receipt=action["receipt"])
        else:
            prep.update(status="failed", receipt=action.get("receipt"))
    elif kind == "turn-start":
        if value["activeTurn"] is not None:
            fail("A turn already owns the response boundary")
        value["activeTurn"] = action["id"]
        value["observation"] = None
    elif kind == "turn-end":
        if value["activeTurn"] != action.get("id") or value["tools"]:
            fail("Turn cannot end before its own tools are settled")
        value["activeTurn"] = None
    elif kind == "tool-start":
        if value["activeTurn"] is None or action["id"] in value["tools"]:
            fail("Tool must belong to the live turn and have a unique identity")
        value["tools"].append(action["id"])
        value["observation"] = None
    elif kind == "tool-end":
        if action["id"] not in value["tools"]:
            fail("Unknown tool boundary")
        value["tools"].remove(action["id"])
        value["observation"] = None
    elif kind == "switch":
        if not authorized(value, action.get("slot"), action.get("epoch")):
            fail("Switch requires current response/assignment ownership")
        prep, observation = value["preparation"], value["observation"]
        percent = fresh_context_percent(observation["value"], now=action["now"],
                                        max_age_seconds=value["maxAgeSeconds"],
                                        session_id=value["sessions"][value["owner"]], turn_id=observation["turnId"]) if observation else None
        if (value["activeTurn"] or value["tools"] or not prep or prep["status"] != "ready"
                or prep["cursor"] != value["cursor"] or percent is None or percent < value["targetPercent"]):
            fail("Switch requires a fresh target observation, caught-up standby and settled turn/tools")
        value["switches"].append({"from": value["owner"], "to": prep["slot"], "epoch": value["epoch"] + 1,
                                  "cursor": value["cursor"], "receipt": prep["receipt"], "at": action["now"]})
        value["owner"], value["epoch"] = prep["slot"], value["epoch"] + 1
        value["preparation"] = {"slot": action["slot"], "epoch": value["epoch"], "cursor": value["cursor"],
                                "status": "requested", "receipt": None}
        value["observation"] = None
        # The former owner is eligible for a fresh context only after this
        # persisted transfer; existing session/record identities are retained.
    else:
        fail("Unknown handoff transition")
    return value


def snapshot(state):
    """Original references and exact processing positions for the standby reader."""
    content = {key: state[key] for key in ("owner", "epoch", "cursor", "references", "events", "processed")}
    revisions = {}
    for reference in [*state["references"], *(event["reference"] for event in state["events"])]:
        path = Path(reference)
        if not path.is_absolute():
            revisions[reference] = None
            continue
        try:
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(65536), b""):
                    digest.update(block)
            revisions[reference] = digest.hexdigest()
        except OSError:
            revisions[reference] = None
    content["sourceRevisions"] = revisions
    return {**content, "snapshotHash": hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}


def capture_children(runtime, root, agent_id, state, runs):
    """Join original managed child requests/results to their stable parent runs.

    Reading a child never dispatches or acknowledges its work. Late results
    invalidate readiness; the chat's existing delivery route remains responsible.
    """
    parents = {run["runId"] for run in runs}
    observation = state["observation"]
    for child in runtime.iter_run_states(root, strict=True):
        if child.get("parentAgentId") != agent_id or child.get("parentRunId") not in parents:
            continue
        sources = [("request", child.get("requestPath"))]
        if child.get("status") not in runtime.ACTIVE_STATES:
            sources.append(("result", child.get("resultPath") if Path(child.get("resultPath", "")).is_file() else child.get("statePath")))
        for kind, reference in sources:
            if reference and Path(reference).is_file():
                state = transition(state, {"type": "event", "slot": state["owner"], "epoch": state["epoch"],
                    "id": f'child:{child["agentId"]}:{child["runId"]}:{kind}', "kind": "child-" + kind,
                    "reference": reference})
    state["observation"] = observation
    return state


def check_dispatch(session, *, preparation_for=None, runtime=None, root=None):
    if preparation_for:
        target = runtime.load_session(root, preparation_for)
        state = target.get("handoff")
        if (session.get("role") != "main" or session.get("handoffExperiment") is not True
                or target.get("handoffExperiment") is not True or session.get("handoff")
                or session.get("handoffReservedFor") not in (None, preparation_for)):
            fail("Only the explicitly allocated standby can perform read preparation")
        if state and session.get("sessionId") == state["sessions"][state["owner"]]:
            fail("The active response owner cannot also run as standby")
        if target.get("goalMode") or session.get("goalMode"):
            fail("Standby preparation preserves native Goal settings; use --no-goal-mode experiments")
    elif session.get("handoffReservedFor"):
        fail("This preparation session is reserved for its experiment; submit through the stable Main identity")
    state = session.get("handoff")
    if state and session.get("sessionId") != state["sessions"][state["owner"]]:
        fail("Native session does not match the persisted response/assignment owner")


def begin_preparation(runtime, root, session, preparation_for):
    path = runtime.session_file(root, preparation_for)
    def update(target):
        state = target.get("handoff")
        if not state:
            return  # Explicit Main allocation may initialize B before configuration.
        preparation = state["preparation"]
        if not preparation:
            fail("The system has not requested preparation at the configured occupancy")
        native_id = session.get("sessionId")
        if native_id in state.get("retiredSessions", []):
            fail("After transfer, allocate a fresh context for the retired slot")
        preparation.update(status="requested", receipt=None, snapshotHash=None)
    runtime.update_json(path, path.parent / ".session-state.lock", update)


def accept_run(runtime, root, session, run):
    state = session.get("handoff")
    if not state:
        return
    check_dispatch(session)
    updated = transition(state, {"type": "event", "slot": state["owner"], "epoch": state["epoch"],
                                "id": run["runId"], "kind": "request", "reference": run["requestPath"]})
    binding = {"slot": state["owner"], "epoch": state["epoch"]}
    path = runtime.session_file(root, session["agentId"])
    runtime.update_json(path, path.parent / ".session-state.lock", lambda value: value.update(handoff=updated))
    run["handoffBinding"] = binding
    runtime.update_json(Path(run["requestPath"]).parent / "state.json",
                        Path(run["requestPath"]).parent / ".state.lock", lambda value: value.update(handoffBinding=binding))


def observe_runtime(runtime, root, run, event):
    """Persist provider boundaries while A is active; no session is launched here."""
    binding = run.get("handoffBinding")
    if not binding:
        return
    path = runtime.session_file(root, run["agentId"])
    def update(session):
        state = session.get("handoff")
        if not authorized(state, binding["slot"], binding["epoch"]):
            fail("Provider event belongs to a former response owner")
        action = dict(binding)
        kind = event.get("type")
        if kind == "turn.started":
            # Retry/reconnect to the same turn retains its tool boundary.
            if state["activeTurn"] == event.get("turn_id"):
                return
            action.update(type="turn-start", id=event.get("turn_id"))
        elif kind == "turn.completed":
            if state["activeTurn"] is None:
                return
            action.update(type="turn-end", id=event.get("turn_id"))
        elif kind == "provider.context":
            from execution.usage import context_observation
            observation = context_observation(event, provider=session.get("provider"),
                                              observed_at=event.get("observedAt"),
                                              provider_version=event.get("providerVersion"))
            action.update(type="observe", observation=observation, now=runtime.now(), turnId=event.get("turn_id"))
        elif kind in ("item.started", "item.completed"):
            item = event.get("item") or {}
            if item.get("type") not in {"command_execution", "file_change", "mcp_tool_call", "dynamicToolCall"}:
                return
            identity = item.get("id")
            if not isinstance(identity, str) or not identity:
                return
            if kind == "item.started" and identity in state["tools"]:
                return  # Provider replay after reconnect retains the live tool.
            if kind == "item.completed" and identity not in state["tools"]:
                return
            action.update(type="tool-start" if kind == "item.started" else "tool-end", id=identity)
        else:
            return
        session["handoff"] = transition(state, action)
    runtime.update_json(path, path.parent / ".session-state.lock", update)


def command(runtime, args):
    """Manage only fresh explicitly opted-in experiments under dispatch locks.

    Standby preparation is Main-owned. A completed donor run must return the
    exact snapshot hash, cursor and original references in its resultText JSON.
    Claiming the donor first is fail-safe: an interrupted two-file write may
    leave it reserved, but can never leave two writable response owners.
    """
    root = runtime.resolve_project_root(args.project_root)
    runtime.validate_id(args.agent, runtime.AGENT_ID, "agent_id")
    payload = runtime.safe_read_json(args.input) if args.input else {}
    if not isinstance(payload, dict):
        fail("Handoff input must be an object")
    parent_path = os.environ.get("AGENT_FACTORY_PARENT_STATE")
    if parent_path and args.action != "status":
        parent = runtime.safe_read_json(Path(parent_path))
        if parent.get("role") != "main" or parent.get("executionOptions", {}).get("handoffPreparationFor"):
            fail("Only the active Main or host may control session allocation/transfer")
    donor_id = payload.get("donorAgentId") if args.action in {"configure", "ready"} else None
    identities = [args.agent]
    if donor_id:
        runtime.validate_id(donor_id, runtime.AGENT_ID, "agent_id")
        if donor_id == args.agent:
            fail("Standby preparation must use a separately Main-allocated session")
        identities.append(donor_id)
    directory = runtime.agent_directory(root, args.agent)
    with contextlib.ExitStack() as locks:
        for identity in sorted(identities):
            locks.enter_context(runtime.file_lock(runtime.agent_directory(root, identity) / ".dispatch.lock"))
        locks.enter_context(runtime.file_lock(directory / ".session-state.lock"))
        session = runtime.load_session(root, args.agent)
        if session.get("role") != "main" or session.get("handoffExperiment") is not True:
            fail("Create a new Main with --handoff-experiment; existing conversations cannot be activated")
        state = session.get("handoff")
        runs = list(runtime.iter_run_states(root, args.agent, strict=True))
        if state:
            captured = capture_children(runtime, root, args.agent, state, runs)
            if captured != state:
                state = captured
                session["handoff"] = state
                runtime.atomic_write_json(directory / "session.json", session)
        if args.action == "status":
            from runs.commands import emit_read_page
            emit_read_page(runtime, args, {"schemaVersion": 1, "kind": "handoff", "state": state,
                                           "preparationSnapshot": snapshot(state) if state else None})
            return 0
        if args.action in {"configure", "switch"}:
            if any(run.get("status") in runtime.ACTIVE_STATES for run in runs):
                fail("Transfer/configuration requires an idle managed turn boundary")
            if runs and max(runs, key=lambda run: run.get("acceptedAt", "")).get("status") == "needs-human-decision":
                fail("Preserve the pending Human decision on its current native session")
            if session.get("goalMode") or session.get("goalError") or session.get("goal"):
                fail("Native Goal settings/state retain their original session; this experiment requires --no-goal-mode")
        if args.action in {"configure", "ready"}:
            if not donor_id:
                fail("Supply the separately Main-allocated donorAgentId")
            donor = runtime.load_session(root, donor_id)
            if donor.get("handoffExperiment") is not True or donor.get("handoff"):
                fail("Standby must also be a newly opted-in, separately Main-allocated experiment")
            if donor.get("role") != "main" or donor.get("provider", "codex") != "codex" or session.get("provider", "codex") != "codex":
                fail("This experimental transfer currently supports Codex Main sessions only")
            if donor.get("handoffReservedFor") not in (None, args.agent):
                fail("The standby native session belongs to another experiment")
            keys = ("model", "reasoningEffort", "fast", "executionPolicy", "humanApprovalPolicy", "worktree", "taskWorkspace")
            if any(donor.get(key) != session.get(key) for key in keys):
                fail("Both arms require identical observed model/effort/Fast/permission settings")
            donor_runs = list(runtime.iter_run_states(root, donor_id, strict=True))
            if any(run.get("status") in runtime.ACTIVE_STATES for run in donor_runs):
                fail("Standby preparation has not settled")
            if donor.get("goalMode") or donor.get("goal") or donor.get("goalError"):
                fail("Standby preparation cannot transfer native Goal state")
            native_id = donor.get("sessionId")
            if not native_id or native_id == session.get("sessionId"):
                fail("Standby requires a distinct observed native session identity")
        if args.action == "configure":
            if state:
                fail("Experiment configuration is immutable; use a new experiment for another threshold pair")
            state = configure(sessions={"A": session.get("sessionId"), "B": native_id},
                              prepare_percent=payload.get("preparePercent"), target_percent=payload.get("targetPercent"),
                              max_age_seconds=payload.get("maxAgeSeconds"), references=payload.get("references"))
            state["retiredSessions"] = []
            if any(value is None for value in snapshot(state)["sourceRevisions"].values()):
                fail("Shared references must resolve to readable absolute original files")
        elif not state:
            fail("Configure the experiment before applying transitions")
        elif args.action == "ready":
            prep = state["preparation"]
            if not prep:
                fail("No system-requested standby preparation exists")
            if native_id in state.get("retiredSessions", []):
                fail("The retired owner needs a fresh Main-allocated native context")
            donor_run = runtime.find_run(root, donor_id, payload.get("donorRunId"))
            if donor_run.get("status") != "completed" or donor_run.get("sessionId") != native_id:
                fail("Readiness requires a successful result from this exact standby session")
            try:
                receipt = json.loads(runtime.safe_read_bytes(Path(donor_run["resultPath"]), None).decode())
            except (ValueError, UnicodeError):
                fail("Standby resultText must be the preparation receipt JSON")
            expected = snapshot(state)
            if any(value is None for value in expected["sourceRevisions"].values()):
                fail("A required original reference is unavailable; standby cannot be declared ready")
            if not isinstance(receipt, dict) or any(receipt.get(key) != expected[key] for key in ("snapshotHash", "cursor", "references")):
                fail("Standby result does not confirm the latest originals and processing cursor")
            state = transition(state, {"type": "ready", "slot": prep["slot"], "epoch": payload.get("epoch"),
                                      "cursor": expected["cursor"], "references": expected["references"], "receipt": donor_run["resultPath"]})
            state["preparation"]["snapshotHash"] = expected["snapshotHash"]
            state["sessions"][prep["slot"]] = native_id
        elif args.action == "event":
            if not authorized(state, payload.get("slot"), payload.get("epoch")):
                fail("Only the current owner may record queue processing positions")
            if payload.get("operation") == "processed":
                state = transition(state, {**payload, "type": "processed"})
            else:
                if payload.get("kind") == "pending-input":
                    identity, original = payload.get("id"), payload.get("original")
                    if not isinstance(identity, str) or not identity or not isinstance(original, dict):
                        fail("Queued input requires stable identity and its complete original")
                    source = directory / ("handoff-input-" + hashlib.sha256(identity.encode()).hexdigest() + ".json")
                    content = json.dumps(original, ensure_ascii=False, sort_keys=True).encode()
                    if source.exists() and source.read_bytes() != content:
                        fail("A queued input identity cannot be reused with another original")
                    if not source.exists():
                        runtime.atomic_write(source, content)
                    payload = {**payload, "reference": str(source)}
                reference = payload.get("reference")
                if not isinstance(reference, str) or not Path(reference).is_absolute() or not Path(reference).is_file():
                    fail("Message/result events must reference readable absolute originals")
                observation = state["observation"]
                state = transition(state, {**payload, "type": "event"})
                # Pending host input has not entered the native context. Its
                # original still invalidates standby readiness through cursor.
                if payload.get("kind") == "pending-input":
                    state["observation"] = observation
        elif args.action == "switch":
            if not state["preparation"] or state["preparation"].get("snapshotHash") != snapshot(state)["snapshotHash"]:
                fail("Original files or processing positions changed after standby readiness")
            state = transition(state, {**payload, "type": "switch", "now": runtime.now()})
            state["retiredSessions"] = [*state.get("retiredSessions", []), session["sessionId"]]
        if donor_id and args.action == "ready":
            donor_path = runtime.session_file(root, donor_id)
            runtime.update_json(donor_path, donor_path.parent / ".session-state.lock",
                                lambda value: value.update(handoffReservedFor=args.agent))
        def persist(value):
            value["handoff"] = state
            if args.action == "switch":
                value["sessionId"] = state["sessions"][state["owner"]]
        persist(session)
        runtime.atomic_write_json(directory / "session.json", session)
    runtime.emit({"schemaVersion": 1, "kind": "handoff", "state": state, "preparationSnapshot": snapshot(state)})
    return 0


def finish_run(runtime, root, run):
    binding = run.get("handoffBinding")
    if not binding:
        return
    path = runtime.session_file(root, run["agentId"])
    def update(session):
        state = session.get("handoff")
        if not authorized(state, binding["slot"], binding["epoch"]):
            fail("Terminal result belongs to a former response owner")
        observation = state["observation"]
        if run.get("status") == "completed":
            state = transition(state, {**binding, "type": "processed", "id": run["runId"]})
        state = transition(state, {**binding, "type": "event", "id": run["runId"] + ":result",
                                  "kind": "completed-result", "reference": run["resultPath"] if Path(run["resultPath"]).is_file() else run["statePath"]})
        # The last inference observation already includes this final output.
        state["observation"] = observation
        session["handoff"] = state
    runtime.update_json(path, path.parent / ".session-state.lock", update)
