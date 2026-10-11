"""One editable project list of work-area domains and worker memberships, shared by the Human and Main.

Immutable execution evidence (allocation, taskBinding, receipts, run states) is never rewritten here: a task keeps
the domain name Main recorded when it was accepted. This store only names domains and links workers to them.
Every worker belongs to one real, named domain: there is no "unclassified" state, placeholder domain or catch-all
name, and no write may leave a worker without a domain. Human edits are protected: Main ("ai") may reuse any domain
and create new ones, but may not rename a domain whose current name the Human set, nor move a worker the Human placed.
Every write is serialized by one project lock and may carry the revision the writer read; a stale revision fails
instead of overwriting a newer edit. Entries written before membership was required (no entry, a Human
"unclassified" choice, an unnamed provisional domain) are kept as they are and reported as unresolved until a worker
is placed explicitly or recovered from its own recorded allocation domain.
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path

from storage.errors import ContractError
from storage.files import AGENT_ID, atomic_write_json, file_lock, safe_read_json
from system.containment import now

SCHEMA_VERSION = 1
FILE = "domains.json"
LOCK = ".domains.lock"
ACTORS = ("human", "ai")
DOMAIN_ID = re.compile(r"^domain-[0-9a-f]{12}$")
HISTORY_LIMIT = 500
# Names that mean "no domain" are not domains, for any actor. Main must also name the actual work area instead of a
# catch-all; the Human's own names are otherwise theirs to choose.
NO_DOMAIN_NAMES = frozenset({"미분류", "분류 없음", "무소속", "미지정", "unclassified", "uncategorized", "unassigned", "none"})
CATCH_ALL_NAMES = frozenset({"기본", "기타", "일반", "default", "misc", "miscellaneous", "other", "others", "general"})
MEMBERSHIP_REQUIRED = "Every worker belongs to a real named domain; create or reuse one and place the worker in it"


def empty():
    return {"schemaVersion": SCHEMA_VERSION, "kind": "project-domains", "revision": 0, "domains": [], "assignments": {},
            "removedWorkers": {}, "history": []}


def name_of(value):
    """Domain names follow allocation.domain: a trimmed single line of at most 80 characters."""
    if (not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 80
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ContractError("domain_name_invalid", "A domain name is a trimmed single line of at most 80 characters")
    return value


def key(value):
    return " ".join(value.split()).casefold()


def _real_name(name, actor):
    name = name_of(name)
    if key(name) in NO_DOMAIN_NAMES or (actor == "ai" and key(name) in CATCH_ALL_NAMES):
        raise ContractError("domain_name_reserved", f"{name!r} does not name a work area; " + MEMBERSHIP_REQUIRED)
    return name


def _actor(actor, source):
    if actor not in ACTORS:
        raise ContractError("domain_actor_invalid", "actor must be human or ai")
    if not isinstance(source, str) or not source.strip() or len(source) > 500:
        raise ContractError("domain_source_invalid", "Record the evidence for this change (a run, loop or control-center action)")
    return {"actor": actor, "at": now(), "source": source}


def read(runtime_root: Path):
    path = Path(runtime_root) / FILE
    if not path.exists():
        return empty()
    value = safe_read_json(path)
    if not isinstance(value, dict) or value.get("schemaVersion") != SCHEMA_VERSION or value.get("kind") != "project-domains":
        raise ContractError("domain_store_invalid", "Unsupported project domain store")
    value.setdefault("removedWorkers", {})  # Stores written before worker removal existed.
    return value


def find(document, name):
    """The domain whose current name or a former name matches; renamed domains keep earlier task names linked."""
    wanted = key(name)
    for domain in document["domains"]:
        if domain.get("provisional"):
            continue
        if key(domain["name"]) == wanted or any(key(alias) == wanted for alias in domain.get("aliases", [])):
            return domain
    return None


def placeable(document, domain_id):
    """A real domain a worker may belong to: it exists and has a name (legacy provisional domains do not)."""
    return any(item["id"] == domain_id and not item.get("provisional") for item in document["domains"])


def _keep_memberships(previous, document):
    """No write may leave a worker without a domain: changed placements need a placeable domain, and a domain that
    holds workers is never dropped. Legacy entries that were already unresolved are left untouched."""
    for agent_id, assignment in document["assignments"].items():
        if assignment != previous["assignments"].get(agent_id) and not placeable(document, assignment.get("domainId")):
            raise ContractError("domain_membership_required", MEMBERSHIP_REQUIRED)
    if set(previous["assignments"]) - set(document["assignments"]):
        raise ContractError("domain_membership_required", "A placement is moved to another domain, never removed")
    held = {item.get("domainId") for item in previous["assignments"].values()}
    if held & ({item["id"] for item in previous["domains"]} - {item["id"] for item in document["domains"]}):
        raise ContractError("domain_in_use", "This domain still holds workers; move them to another domain first")


def _mutate(runtime_root, expected_revision, change):
    root = Path(runtime_root)
    root.mkdir(parents=True, exist_ok=True)
    with file_lock(root / LOCK):
        document = read(root)
        if expected_revision is not None and expected_revision != document["revision"]:
            raise ContractError("domain_conflict", f"Domains changed since revision {expected_revision}; reload and retry")
        before = json.dumps(document, sort_keys=True)
        previous = copy.deepcopy(document)
        result = change(document)
        _keep_memberships(previous, document)
        if json.dumps(document, sort_keys=True) != before:
            document["revision"] += 1
            for event in document["history"]:
                event.setdefault("revision", document["revision"])
            document["history"] = document["history"][-HISTORY_LIMIT:]
            atomic_write_json(root / FILE, document)
        return {**result, "revision": document["revision"], "domains": copy.deepcopy(document)}


def _event(document, by, action, **fields):
    document["history"].append({**by, "action": action, **fields})


def create(runtime_root, name, actor, source, expected_revision=None):
    """Create a domain with a real work-area name; for Main ("ai") an existing matching name is reused."""
    name, by = _real_name(name, actor), _actor(actor, source)

    def change(document):
        existing = find(document, name)
        if existing:
            if actor == "human":
                raise ContractError("domain_name_taken", f"A domain named {existing['name']!r} already exists")
            return {"domainId": existing["id"], "reused": True}
        domain = {"id": "domain-" + uuid.uuid4().hex[:12], "name": name, "aliases": [], "createdBy": by, "nameSetBy": by}
        document["domains"].append(domain)
        _event(document, by, "create", domainId=domain["id"], name=name)
        return {"domainId": domain["id"], "reused": False}
    return _mutate(runtime_root, expected_revision, change)


def rename(runtime_root, domain_id, name, actor, source, expected_revision=None):
    """Rename a domain; naming a legacy provisional domain makes it a real one its workers then belong to."""
    name, by = _real_name(name, actor), _actor(actor, source)

    def change(document):
        domain = next((item for item in document["domains"] if item["id"] == domain_id), None)
        if domain is None:
            raise ContractError("domain_missing", "Unknown domain")
        if actor == "ai" and domain["nameSetBy"]["actor"] == "human":
            raise ContractError("domain_protected", "The Human named this domain; only the Human renames it")
        other = find(document, name)
        if other and other["id"] != domain_id:
            raise ContractError("domain_name_taken", f"Another domain is already named {other['name']!r}; domains are not merged")
        provisional = bool(domain.pop("provisional", False))
        if domain["name"] == name and not provisional:
            return {"domainId": domain_id}
        # A provisional name is not a former name: it would link every other unnamed domain's tasks.
        if not provisional and key(domain["name"]) not in {key(alias) for alias in domain["aliases"]}:
            domain["aliases"].append(domain["name"])
        domain["aliases"] = [alias for alias in domain["aliases"] if key(alias) != key(name)]
        _event(document, by, "rename", domainId=domain_id, previous=domain["name"], name=name)
        domain["name"], domain["nameSetBy"] = name, by
        return {"domainId": domain_id}
    return _mutate(runtime_root, expected_revision, change)


def assign(runtime_root, agent_id, domain_id, actor, source, expected_revision=None):
    """Place a worker in a real domain. Main cannot move a worker the Human placed, or one the Human left in a legacy
    "unclassified" state: that choice is resolved only by the Human placing the worker."""
    if not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id):
        raise ContractError("domain_agent_invalid", "Invalid worker agent ID")
    if domain_id is None:
        raise ContractError("domain_membership_required", MEMBERSHIP_REQUIRED)
    by = _actor(actor, source)

    def change(document):
        if not any(item["id"] == domain_id for item in document["domains"]):
            raise ContractError("domain_missing", "Unknown domain")
        if not placeable(document, domain_id):
            raise ContractError("domain_name_required", "Name this domain before placing workers in it")
        current = document["assignments"].get(agent_id)
        if actor == "ai" and current and current["setBy"]["actor"] == "human":
            raise ContractError("domain_protected", "The Human placed this worker; only the Human moves it")
        if current and current["domainId"] == domain_id and (actor == "ai" or current["setBy"]["actor"] == "human"):
            return {"agentId": agent_id, "domainId": domain_id}
        document["assignments"][agent_id] = {"domainId": domain_id, "setBy": by}
        _event(document, by, "assign", agentId=agent_id, domainId=domain_id, previous=(current or {}).get("domainId"))
        return {"agentId": agent_id, "domainId": domain_id}
    return _mutate(runtime_root, expected_revision, change)


def link_dispatch(runtime_root, agent_id, name, source):
    """Main's chosen work area: reuse a matching domain or create it, then place a worker the Human has not placed.

    A worker the Human placed stays where the Human put it; the accepted allocation itself is not changed.
    `member` tells whether the worker now belongs to a real domain (false only for an unresolved legacy Human entry).
    """
    created = create(runtime_root, name, "ai", source)
    try:
        placed = assign(runtime_root, agent_id, created["domainId"], "ai", source)
        return {"domainId": created["domainId"], "reused": created["reused"], "assigned": True, "member": True,
                "revision": placed["revision"]}
    except ContractError as error:
        if error.code != "domain_protected":
            raise
        document = read(runtime_root)
        current = document["assignments"].get(agent_id, {})
        return {"domainId": created["domainId"], "reused": created["reused"], "assigned": False,
                "protectedDomainId": current.get("domainId"), "member": placeable(document, current.get("domainId")),
                "revision": document["revision"]}


def membership(document, agent_id):
    """None when the worker belongs to a real domain, otherwise why its membership is unresolved."""
    current = document["assignments"].get(agent_id)
    if current is None:
        return "unassigned"
    if current.get("domainId") is None:
        return "legacy-unclassified"
    if not any(item["id"] == current["domainId"] for item in document["domains"]):
        return "missing-domain"
    return None if placeable(document, current["domainId"]) else "unnamed-domain"


def workers(runtime_root):
    """Worker agents recorded in this project: every agent whose session role is not Main."""
    found = []
    for session_path in sorted((Path(runtime_root) / "agents").glob("*/session.json")):
        agent_id = session_path.parent.name
        try:
            role = safe_read_json(session_path).get("role")
        except (ContractError, OSError, ValueError):
            role = None
        if role != "main" and AGENT_ID.fullmatch(agent_id):
            found.append(agent_id)
    return found


def recorded_domains(runtime_root, agent_id):
    """The allocation domain names Main recorded for this worker's own runs and loops, with their sources."""
    agent = Path(runtime_root) / "agents" / agent_id
    names = {}

    def note(name, source):
        if isinstance(name, str) and name.strip():
            names.setdefault(key(name), {"name": name, "sources": []})["sources"].append(source)
    for state_path in sorted(agent.glob("runs/*/state.json")):
        try:
            state = safe_read_json(state_path)
        except (ContractError, OSError, ValueError):
            continue
        note(((state.get("taskBinding") or {}).get("allocation") or {}).get("domain"), "run " + state_path.parent.name)
    for state_path in sorted(agent.glob("loops/*/state.json")):
        try:
            state = safe_read_json(state_path)
        except (ContractError, OSError, ValueError):
            continue
        for task in (state.get("workflow") or {}).get("tasks") or []:
            if isinstance(task, dict):
                note((task.get("allocation") or {}).get("domain"), "loop " + state_path.parent.name)
    return list(names.values())


def unresolved(runtime_root, document=None):
    """Workers without a real domain, kept visible (removed workers included) with the reason; nothing is inferred."""
    document = document if document is not None else read(runtime_root)
    found = []
    for agent_id in sorted(set(workers(runtime_root)) | set(document["assignments"])):
        reason = membership(document, agent_id)
        if reason:
            entry = {"agentId": agent_id, "reason": reason}
            if agent_id in document["assignments"]:
                entry["setBy"] = document["assignments"][agent_id]["setBy"]
            if agent_id in document["removedWorkers"]:
                entry["removed"] = True
            found.append(entry)
    return found


def recover(runtime_root, actor, source, expected_revision=None, dry_run=False):
    """Restore memberships only from evidence: a worker with no entry at all whose own runs and loops recorded exactly
    one allocation domain is placed in that domain (reused, or created under its recorded name). Every other worker
    stays unresolved with its recorded names as candidates for an explicit `assign`; nothing is hidden or deleted."""
    by = _actor(actor, source)
    document = read(runtime_root)
    plan, left = [], []
    for entry in unresolved(runtime_root, document):
        recorded = recorded_domains(runtime_root, entry["agentId"])
        candidates = [item["name"] for item in recorded]
        usable = entry["reason"] == "unassigned" and len(recorded) == 1
        if usable:
            try:
                _real_name(recorded[0]["name"], actor)
            except ContractError:
                usable = False
        if usable:
            plan.append({"agentId": entry["agentId"], "name": recorded[0]["name"], "evidence": recorded[0]["sources"]})
        else:
            left.append({**entry, "candidates": candidates})
    if dry_run or not plan:
        return {"recovered": plan, "unresolved": left, "dryRun": bool(dry_run), "revision": document["revision"],
                "domains": copy.deepcopy(document)}

    def change(current):
        done = []
        for item in plan:
            if item["agentId"] in current["assignments"]:
                continue  # Placed since the plan was read; an explicit placement wins.
            domain = find(current, item["name"])
            if domain is None:
                domain = {"id": "domain-" + uuid.uuid4().hex[:12], "name": item["name"], "aliases": [], "createdBy": by, "nameSetBy": by}
                current["domains"].append(domain)
                _event(current, by, "create", domainId=domain["id"], name=item["name"])
            current["assignments"][item["agentId"]] = {"domainId": domain["id"], "setBy": by}
            _event(current, by, "recover", agentId=item["agentId"], domainId=domain["id"], evidence=item["evidence"])
            done.append({**item, "domainId": domain["id"]})
        return {"recovered": done}
    result = _mutate(runtime_root, expected_revision, change)
    return {**result, "unresolved": left, "dryRun": False}


ACTIVE_RUN_STATES = {"accepted", "queued", "starting", "running", "cancelling"}


def _worker_active(runtime_root, agent_id):
    """A worker with a live run or an active loop must be stopped first; its records are only read."""
    agent = Path(runtime_root) / "agents" / agent_id
    for state_path in list(agent.glob("runs/*/state.json")) + list(agent.glob("loops/*/state.json")):
        try:
            state = safe_read_json(state_path)
        except (ContractError, OSError, ValueError):
            continue
        status = state.get("status")
        if state_path.parent.parent.name == "loops" and status == "active":
            return True
        if state_path.parent.parent.name == "runs" and status in ACTIVE_RUN_STATES:
            return True
    return False


def remove_worker(runtime_root, agent_id, actor, source, expected_revision=None):
    """Hide a worker from the worker list (Human only). Its sessions, runs, results and loops are untouched."""
    if not isinstance(agent_id, str) or not AGENT_ID.fullmatch(agent_id):
        raise ContractError("domain_agent_invalid", "Invalid worker agent ID")
    if actor != "human":
        raise ContractError("domain_protected", "Only the Human removes a worker from the list")
    by = _actor(actor, source)

    def change(document):
        if agent_id in document["removedWorkers"]:
            return {"agentId": agent_id, "removed": True}
        # Checked under the domain lock; the run/loop records themselves are owned by the runtime.
        if _worker_active(runtime_root, agent_id):
            raise ContractError("worker_running", "Stop this worker's running task before removing it")
        document["removedWorkers"][agent_id] = {"removedBy": by}
        _event(document, by, "remove-worker", agentId=agent_id)
        return {"agentId": agent_id, "removed": True}
    return _mutate(runtime_root, expected_revision, change)
