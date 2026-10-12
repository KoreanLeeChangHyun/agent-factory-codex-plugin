"""One logical conductor with pooled physical instances over a durable SQLite queue.

Every accepted input commits its inbox/dedup key, canonical state transition and
outbox event in one transaction. The relay and the per-subscription consumers are
at-least-once; a consumer inbox key makes redelivery harmless. Conductor, executor
and UI projection are separate subscriptions, so no event is lost to a competing
consumer. Conductor ownership reuses the execution.handoff owner/epoch reducer and
every conductor write sink (delegation, state, stream chunk, final answer) is fenced.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from execution import handoff
from tasks import conductor_intents as intents
from tasks import conductor_pool, conductor_responsibility, conductor_roles
from storage import paths
from storage.errors import ContractError

SCHEMA_VERSION = 1
CLASSES = ("control", "conversation", "lifecycle", "progress")
# Inputs taken per class in one router pass: every class is served on every pass, so
# a progress flood delays other classes by at most one bounded batch and never drops.
WEIGHTS = {"control": 16, "conversation": 16, "lifecycle": 32, "progress": 256}
# Queue depth reported to producers as a slow-down signal; nothing is rejected.
BACKPRESSURE_DEPTH = {"control": 64, "conversation": 64, "lifecycle": 512, "progress": 2048}
SUBSCRIPTIONS = ("conductor", "executor", "ui")
POISON_ATTEMPTS = 3
OPEN_REQUEST = ("accepted", "planning", "delegated", "awaiting-synthesis", "cancelling", "decomposed", "queued-for-instance")
DELEGATION_TERMINAL = ("completed", "failed", "cancelled")
ATTEMPT_TERMINAL = ("completed", "failed", "cancelled", "lost")
ROUTES = {
    "delegation-created": ("executor", "ui"), "delegation-unblocked": ("executor", "ui"), "delegation-approved": ("executor", "ui"),
    "attempt-retry": ("executor", "ui"), "worker-answer": ("executor", "ui"), "workspace-action": ("executor", "ui"), "delegation-cancel-requested": ("executor", "ui"),
    "delegation-completed": ("conductor", "ui"), "delegation-failed": ("conductor", "ui"),
    "delegation-cancelled": ("conductor", "ui"), "worker-question": ("conductor", "ui"),
    "request-cancelled": ("conductor", "ui"),
}


class StaleOwner(ContractError):
    def __init__(self, message):
        super().__init__("stale_owner", message)


class SimulatedCrash(BaseException):
    """Fault injection: abandons the process path without running cleanup handlers."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def ident(prefix):
    return prefix + "-" + uuid.uuid4().hex[:16]


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def require(condition, code, message):
    if not condition:
        raise ContractError(code, message)


def database_path(project_root, *, runtime_home=None, project_id=None):
    binding = paths.resolve(project_root, home=runtime_home, project_id=project_id)
    paths.require_ready(binding)
    require(binding["registered"], "project_uninitialized", "Initialize the managed project first")
    return Path(binding["runtimeRoot"]) / "conductor-queue.sqlite3"


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY, policy TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS inbox(dedup_key TEXT PRIMARY KEY, input_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
  accepted_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS inputs(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, chat_id TEXT NOT NULL,
  class TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, sent_at REAL,
  accepted_at REAL NOT NULL, routed_at REAL, reason TEXT, request_id TEXT, conductor_id TEXT,
  failures INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS inputs_pending ON inputs(status, class, seq);
CREATE TABLE IF NOT EXISTS conductors(id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
  status TEXT NOT NULL, handoff TEXT NOT NULL, turn_id TEXT, turn_started_at REAL, checkpoint TEXT,
  usage TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, conductor_id TEXT NOT NULL,
  owner_epoch INTEGER NOT NULL, parent_id TEXT, title TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
  received_at REAL NOT NULL, first_response_at REAL, final_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mailbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
  conductor_id TEXT NOT NULL, request_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
  turn_id TEXT, enqueued_at REAL NOT NULL, delivered_at REAL, processed_at REAL, source TEXT NOT NULL,
  failures INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS mailbox_queued ON mailbox(conductor_id, status, seq);
CREATE TABLE IF NOT EXISTS delegations(id TEXT PRIMARY KEY, request_id TEXT NOT NULL, chat_id TEXT NOT NULL,
  conductor_id TEXT NOT NULL, title TEXT NOT NULL, spec TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
  attempt_id TEXT NOT NULL, attempt_count INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
  cancel_requested INTEGER NOT NULL DEFAULT 0, result TEXT, error TEXT, created_at REAL NOT NULL,
  updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, delegation_id TEXT NOT NULL, number INTEGER NOT NULL,
  status TEXT NOT NULL, backend TEXT NOT NULL, external TEXT, started_at REAL, ended_at REAL, progress TEXT,
  error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, chat_id TEXT,
  type TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL, published INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS events_unpublished ON events(published, seq);
CREATE TABLE IF NOT EXISTS deliveries(subscription TEXT NOT NULL, event_seq INTEGER NOT NULL, status TEXT NOT NULL,
  failures INTEGER NOT NULL DEFAULT 0, last_error TEXT, available_at REAL NOT NULL, acked_at REAL,
  PRIMARY KEY(subscription, event_seq));
CREATE INDEX IF NOT EXISTS deliveries_ready ON deliveries(subscription, status, event_seq);
CREATE TABLE IF NOT EXISTS consumer_inbox(subscription TEXT NOT NULL, event_id TEXT NOT NULL, applied_at REAL NOT NULL,
  PRIMARY KEY(subscription, event_id));
CREATE TABLE IF NOT EXISTS ui_state(key TEXT PRIMARY KEY, chat_id TEXT NOT NULL, kind TEXT NOT NULL,
  payload TEXT NOT NULL, version INTEGER NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ui_feed(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, kind TEXT NOT NULL,
  key TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, event_seq INTEGER NOT NULL,
  event_at REAL NOT NULL, applied_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ui_feed_chat ON ui_feed(chat_id, id);
CREATE TABLE IF NOT EXISTS intent_plans(request_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS request_intents(request_id TEXT PRIMARY KEY, parent_id TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operator_effects(id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempt_waits(attempt_id TEXT PRIMARY KEY, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, detail TEXT NOT NULL,
  at REAL NOT NULL);
"""


class Store:
    """One SQLite file per project; a connection per thread, IMMEDIATE write transactions."""

    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.local = threading.local()
        self.faults = {}
        self.pool = conductor_pool.Pool(self)
        self.responsibility = conductor_responsibility.Responsibility(self)
        self.roles = conductor_roles.Roles(self)
        with self.tx() as c:
            for statement in filter(str.strip, (SCHEMA + conductor_pool.SCHEMA + conductor_responsibility.SCHEMA + conductor_roles.SCHEMA).split(";")):
                c.execute(statement)
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schemaVersion', ?)", (str(SCHEMA_VERSION),))
            for name in SUBSCRIPTIONS:
                c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES(?, '0')", ("relay:" + name,))

    # -- plumbing -------------------------------------------------------------
    def connection(self):
        conn = getattr(self.local, "conn", None)
        if conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.path), isolation_level=None, timeout=60, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=60000")
            self.local.conn = conn
        return conn

    def close(self):
        conn = getattr(self.local, "conn", None)
        if conn is not None:
            conn.close()
            self.local.conn = None

    @contextlib.contextmanager
    def tx(self):
        c = self.connection()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        else:
            c.execute("COMMIT")

    def fault(self, name, **context):
        hook = self.faults.get(name)
        if hook and hook(**context):
            raise SimulatedCrash(name)

    def event(self, c, chat_id, kind, payload, *, key=None):
        """Outbox append inside the caller's transaction; a stable key makes it idempotent."""
        eid = "ev-" + (digest([kind, key])[:24] if key else uuid.uuid4().hex[:24])
        cur = c.execute("INSERT OR IGNORE INTO events(id, chat_id, type, payload, created_at) VALUES(?,?,?,?,?)",
                        (eid, chat_id, kind, json.dumps(payload, ensure_ascii=False), self.clock()))
        return eid if cur.rowcount else None

    def op(self, c, kind, **detail):
        """Observability record: identifiers and codes only, never message text or secrets."""
        c.execute("INSERT INTO ops(kind, detail, at) VALUES(?,?,?)", (kind, json.dumps(detail, sort_keys=True), self.clock()))

    @staticmethod
    def row(c, sql, *args):
        value = c.execute(sql, args).fetchone()
        return dict(value) if value else None

    # -- chats and ingress ------------------------------------------------------
    def ensure_chat(self, chat_id, policy):
        require(isinstance(chat_id, str) and chat_id and len(chat_id) <= 200, "chat_id", "Chat ID required")
        require(policy.get("approvalPolicy") in {"bypass", "required"} and policy.get("reference"),
                "authority_missing", "Captured approval policy and authorization reference required")
        require(policy.get("executor") in {"fake", "managed"} and policy.get("conductor") in {"fake", "managed"},
                "driver_unsupported", "Conductor and executor drivers are fake or managed")
        if policy["conductor"] == "managed":
            # The LLM conductor runs through exec.py with captured settings; nothing is chosen for the Human.
            require(isinstance(policy.get("conductorSettings"), dict) and policy["conductorSettings"].get("model"),
                    "authority_missing", "Managed conductor needs the captured conductor model settings")
        if policy["executor"] == "managed":
            # Managed delegations keep the existing exec.py authority and model selection; nothing is inferred.
            require(policy.get("sandbox") in {"read-only", "workspace-write", "danger-full-access"}
                    and isinstance(policy.get("work"), dict) and policy["work"].get("model"),
                    "authority_missing", "Managed executor needs the captured sandbox and Work model settings")
        with self.tx() as c:
            old = self.row(c, "SELECT policy FROM chats WHERE id=?", chat_id)
            if old:
                require(json.loads(old["policy"]) == policy, "chat_conflict", "Existing chat keeps its captured policy")
                return {"chatId": chat_id, "policy": policy, "created": False}
            c.execute("INSERT INTO chats(id, policy, created_at) VALUES(?,?,?)",
                      (chat_id, json.dumps(policy, sort_keys=True), self.clock()))
        return {"chatId": chat_id, "policy": policy, "created": True}

    def policy(self, c, chat_id):
        value = self.row(c, "SELECT policy FROM chats WHERE id=?", chat_id)
        require(value, "chat_unknown", "Initialize the chat first")
        return json.loads(value["policy"])

    def ingest(self, chat_id, cls, payload, *, sent_at=None):
        """Accept and persist; routing happens later on the router's fair schedule."""
        require(cls in CLASSES, "input_class", "Unknown input class")
        require(isinstance(payload, dict), "input_invalid", "Payload must be an object")
        if cls == "conversation":
            require(isinstance(payload.get("text"), str) and payload["text"].strip(), "message_empty", "Text required")
            key = "chat:%s:message:%s" % (chat_id, payload.get("clientMessageId"))
            require(payload.get("clientMessageId"), "message_id", "clientMessageId required")
            require(payload.get("relation") in (None, "new", "followup"), "relation_invalid", "relation is new or followup")
            kind = "message"
        elif cls == "control":
            require(payload.get("action") in {"cancel", "approve", "resolve-input", "reassign", "answer-worker", "integrate-workspace", "cleanup-workspace", "resolve-area", "confirm-decision", "answer-question", "hire-role", "configure-area", "configure-role", "accept-area-task", "register-required", "exclude-required", "create-child"}, "control_action",
                    "Unknown control action")
            require(payload.get("commandId"), "command_id", "commandId required")
            key, kind = "chat:%s:control:%s" % (chat_id, payload["commandId"]), payload["action"]
        else:
            for field in ("delegationId", "attemptId", "workerEventId", "kind"):
                require(isinstance(payload.get(field), str) and payload[field], "worker_event", "Missing " + field)
            require(cls != "progress" or payload["kind"] == "progress", "worker_event", "Progress class carries progress")
            require(cls != "lifecycle" or payload["kind"] in {"started", "completed", "failed", "cancelled", "question"},
                    "worker_event", "Unknown lifecycle kind")
            key, kind = "attempt:%s:%s" % (payload["attemptId"], payload["workerEventId"]), payload["kind"]
        value_hash = digest(payload)
        with self.tx() as c:
            self.policy(c, chat_id)
            old = self.row(c, "SELECT input_id, payload_hash, accepted_at FROM inbox WHERE dedup_key=?", key)
            if old:
                require(old["payload_hash"] == value_hash, "input_conflict", "Duplicate key with different content")
                state = self.row(c, "SELECT status, request_id, conductor_id FROM inputs WHERE id=?", old["input_id"])
                return {"disposition": "duplicate", "inputId": old["input_id"], "acceptedAt": iso(old["accepted_at"]),
                        **({"status": state["status"]} if state else {})}
            now = self.clock()
            iid = ident("in")
            c.execute("INSERT INTO inbox(dedup_key, input_id, payload_hash, accepted_at) VALUES(?,?,?,?)",
                      (key, iid, value_hash, now))
            c.execute("INSERT INTO inputs(id, chat_id, class, kind, payload, status, sent_at, accepted_at)"
                      " VALUES(?,?,?,?,?,?,?,?)", (iid, chat_id, cls, kind, json.dumps(payload, ensure_ascii=False),
                                                   "pending", sent_at, now))
            if cls in ("conversation", "control"):
                self.event(c, chat_id, "input-accepted", {"inputId": iid, "class": cls, "kind": kind,
                                                          "clientMessageId": payload.get("clientMessageId"),
                                                          "commandId": payload.get("commandId"),
                                                          "text": payload.get("text"), "acceptedAt": now,
                                                          "sentAt": sent_at}, key=iid)
            depth = c.execute("SELECT COUNT(*) FROM inputs WHERE status='pending' AND class=?", (cls,)).fetchone()[0]
        return {"disposition": "accepted", "inputId": iid, "acceptedAt": iso(now), "class": cls,
                "queueDepth": depth, "backpressure": depth >= BACKPRESSURE_DEPTH[cls]}

    # -- router ---------------------------------------------------------------
    def route_batch(self, weights=None):
        weights = weights or WEIGHTS
        handled = 0
        for cls in CLASSES:
            c = self.connection()
            ids = [r[0] for r in c.execute("SELECT id FROM inputs WHERE status='pending' AND class=? ORDER BY seq LIMIT ?",
                                           (cls, weights[cls]))]
            if not ids:
                continue
            if cls == "progress":
                handled += self.route_progress(ids)
            else:
                for iid in ids:
                    self.route_one(iid)
                    handled += 1
        return handled

    def route_one(self, iid):
        try:
            with self.tx() as c:
                inp = self.row(c, "SELECT * FROM inputs WHERE id=?", iid)
                if not inp or inp["status"] != "pending":
                    return
                payload = json.loads(inp["payload"])
                handler = {"conversation": self.route_conversation, "control": self.route_control,
                           "lifecycle": self.route_lifecycle}[inp["class"]]
                outcome = handler(c, inp, payload) or {}
                if inp['class'] == 'control' and payload.get('action') in ('hire-role','configure-area','configure-role','accept-area-task','create-child'):
                    self.event(c, inp['chat_id'], 'role-pool-control-result', {'commandId': payload['commandId'], 'outcome': outcome}, key='role-control:' + payload['commandId'])
                c.execute("UPDATE inputs SET status=?, routed_at=?, reason=?, request_id=COALESCE(?, request_id),"
                          " conductor_id=COALESCE(?, conductor_id) WHERE id=?",
                          (outcome.get("status", "processed"), self.clock(), outcome.get("reason"),
                           outcome.get("requestId"), outcome.get("conductorId"), iid))
        except ContractError as error:
            with self.tx() as c:
                inp = self.row(c, "SELECT chat_id, class, kind FROM inputs WHERE id=?", iid)
                c.execute("UPDATE inputs SET status='rejected', routed_at=?, reason=? WHERE id=?",
                          (self.clock(), error.code, iid))
                self.event(c, inp["chat_id"], "input-rejected", {"inputId": iid, "class": inp["class"],
                                                                 "kind": inp["kind"], "code": error.code,
                                                                 "message": error.message}, key="rejected:" + iid)
        except SimulatedCrash:
            raise
        except Exception as error:  # Poison input: isolate after bounded retries, keep the record.
            with self.tx() as c:
                inp = self.row(c, "SELECT chat_id, failures FROM inputs WHERE id=?", iid)
                failures = inp["failures"] + 1
                status = "quarantined" if failures >= POISON_ATTEMPTS else "pending"
                c.execute("UPDATE inputs SET failures=?, status=?, reason=? WHERE id=?",
                          (failures, status, type(error).__name__, iid))
                self.op(c, "input-failure", inputId=iid, error=type(error).__name__, failures=failures)
                if status == "quarantined":
                    self.event(c, inp["chat_id"], "input-quarantined", {"inputId": iid, "error": type(error).__name__},
                               key="quarantine:" + iid)

    def open_requests(self, c, chat_id):
        return [dict(r) for r in c.execute("SELECT * FROM requests WHERE chat_id=? AND status IN (%s) ORDER BY created_at"
                                           % ",".join("?" * len(OPEN_REQUEST)), (chat_id, *OPEN_REQUEST))]

    def route_conversation(self, c, inp, p):
        chat = inp["chat_id"]
        if p.get("requestId"):
            req = self.row(c, "SELECT * FROM requests WHERE id=? AND chat_id=?", p["requestId"], chat)
            require(req, "request_unknown", "Follow-up names an unknown request")
            require(req["status"] != "cancelled", "request_cancelled", "Start a new request after cancellation")
            if req["status"] == "completed":
                req = self.set_request(c, req, "accepted")
        else:
            opened = self.open_requests(c, chat)
            if p.get("relation") == "followup" and len(opened) == 1:
                req = opened[0]
            elif p.get("relation") == "new" or not opened:
                area = None
                if conductor_pool.enabled(self.policy(c, chat)):
                    try:
                        area = self.pool.area(p.get('area'))
                    except ContractError:
                        qid = self.question(c, None, None, 'area', 'Select domain and subdomain before hiring', 'input:' + inp['id'], input_id=inp['id'])
                        self.event(c, chat, 'area-question', {'inputId': inp['id'], 'clientMessageId': p.get('clientMessageId'),
                                   'questionId': qid, 'question': 'Select domain and subdomain before hiring', 'catalog': self.pool.catalog()}, key='area:' + inp['id'])
                        return {'status': 'held', 'reason': 'area-required'}
                req = self.create_request(c, chat, p["text"], {**inp, "areaSource": p.get("areaSource"), "processingChoice": p.get("processingChoice")}, area=area)
            else:
                # Ambiguous reference: never attribute arbitrarily. The input stays durable and visible.
                self.event(c, chat, "clarification-needed", {
                    "inputId": inp["id"], "clientMessageId": p.get("clientMessageId"),
                    "candidates": [{"requestId": r["id"], "title": r["title"], "status": r["status"],
                                    "version": r["version"]} for r in opened]}, key="clarify:" + inp["id"])
                return {"status": "held", "reason": "relation-ambiguous"}
        if conductor_pool.enabled(self.policy(c, chat)) and req['conductor_id']:
            current = self.row(c, 'SELECT * FROM conductors WHERE id=?', req['conductor_id'])
            if current['chat_id'] != chat:
                c.execute("UPDATE requests SET conductor_id='',owner_epoch=owner_epoch+1 WHERE id=?", (req['id'],))
                req = self.set_request(c, self.row(c, 'SELECT * FROM requests WHERE id=?', req['id']), 'queued-for-instance')
        if req["status"] == "decomposed":
            children = [dict(r) for r in c.execute("SELECT * FROM requests WHERE parent_id=?", (req["id"],))]
            self.event(c, chat, "clarification-needed", {"inputId": inp["id"], "clientMessageId": p.get("clientMessageId"),
                       "candidates": [{"requestId": r["id"], "title": r["title"], "status": r["status"], "version": r["version"]}
                                      for r in children]}, key="clarify:" + inp["id"])
            return {"status": "held", "reason": "intent-target-ambiguous"}
        if p.get('routingSource'):
            self.pool.decide(c, req['id'], 'assignment', {'inputId': inp['id'], 'requestId': req['id'], 'relation': p.get('relation')}, p['routingSource'], 'human', 'route:' + inp['id'])
        if p.get('requiredTasks'):
            self.responsibility.register(c, req['id'], p['requiredTasks'], 'input:' + inp['id'])
        instruction_id = self.responsibility.instruction(c, req['id'], p['text'], 'input:' + inp['id']) if p.get('requestId') or p.get('requiredTasks') or self.policy(c, chat)['conductor'] == 'managed' else None
        self.deliver_user(c, req, {
            "instructionId": instruction_id, "inputId": inp["id"], "text": p["text"], "clientMessageId": p.get("clientMessageId")},
            "input:" + inp["id"], mid="mb-" + inp["id"])
        self.event(c, chat, "input-routed", {"inputId": inp["id"], "clientMessageId": p.get("clientMessageId"),
                                             "requestId": req["id"], "conductorId": req["conductor_id"],
                                             "acceptedAt": inp["accepted_at"]}, key="routed:" + inp["id"])
        return {"status": "routed", "requestId": req["id"], "conductorId": req["conductor_id"]}

    def create_request(self, c, chat, text, inp, *, area=None, parent=None):
        conductor = self.pick_conductor(c, chat, area=area, parent=parent)
        now = self.clock()
        rid = ident("req")
        title = " ".join(text.split())
        title = title if len(title) <= 80 else title[:79] + "…"  # display label; the full text stays in the input
        c.execute("INSERT INTO requests(id, chat_id, conductor_id, owner_epoch, title, status, version, received_at,"
                  " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (rid, chat, conductor["id"] if conductor else "", 1, title, "accepted" if conductor else "queued-for-instance", 1, inp["accepted_at"], now, now))
        if area:
            self.pool.set_area(c, "request", rid, area)
            self.pool.decide(c, rid, "assignment", area, inp.get("areaSource") or "input:" + str(inp.get("id", rid)), "declared" if str(inp.get("areaSource", "")).startswith("turn:") else "human", "area")
        policy = self.policy(c, chat)
        self.pool.decide(c, rid, "authorization", {"approvalPolicy": policy["approvalPolicy"], "reference": policy["reference"]}, policy["reference"], "captured", "authorization")
        self.roles.capture(c, rid, area, inp.get("processingChoice"), "input:" + str(inp.get("id", rid)), profile=inp.get("requestProfile") or (policy.get("work") or {}).get("workProfile", "work"))
        req = self.row(c, "SELECT * FROM requests WHERE id=?", rid)
        self.event(c, chat, "request-created", {"request": self.public_request(req)}, key="request:" + rid)
        return req

    def pick_conductor(self, c, chat, *, area=None, parent=None):
        """Allocate or reuse a physical instance; every instance belongs to the same logical conductor."""
        if conductor_pool.enabled(self.policy(c, chat)):
            if not area:
                raise ContractError('area_required', 'Conductor instance needs a declared domain and child area')
            self.refresh_instances(c)
            signature = conductor_pool.signature(self.policy(c, chat), "conductor")
            if parent:
                con = self.row(c, 'SELECT * FROM conductors WHERE id=?', parent['conductor_id'])
                owned = self.pool.get_area(c, 'conductor', con['id']) if con else None
                if owned and owned['subdomainId'] == area['subdomainId']:
                    return con  # Child planning shares the parent's physical instance at the next safe turn boundary.
            if self.pool.room(c, 'conductor', area):
                return None
            member = self.pool.idle(c, 'conductor', area, signature, chat_id=chat)
            if member:
                c.execute("UPDATE pool_members SET state='busy',last_used=? WHERE id=?", (self.clock(), member['id']))
                c.execute('UPDATE conductors SET chat_id=? WHERE id=?', (chat, member['id']))
                return self.row(c, 'SELECT * FROM conductors WHERE id=?', member['id'])
            if self.pool.room(c, 'conductor', area):
                return None
            retired = self.pool.idle(c, 'conductor', area, signature, retired=True, chat_id=chat)
            if retired:
                c.execute("UPDATE pool_members SET state='busy',last_used=? WHERE id=?", (self.clock(), retired['id']))
                c.execute('UPDATE conductors SET chat_id=? WHERE id=?', (chat, retired['id']))
                return self.row(c, 'SELECT * FROM conductors WHERE id=?', retired['id'])
        busy = {r["conductor_id"] for r in self.open_requests(c, chat)}
        for row in c.execute("SELECT * FROM conductors WHERE chat_id=? ORDER BY ordinal", (chat,)):
            if not area and row["id"] not in busy and row["status"] == "idle":
                return dict(row)
        ordinal = c.execute("SELECT COUNT(*) FROM conductors WHERE chat_id=?", (chat,)).fetchone()[0] + 1
        cid = ident("cond")
        policy = self.policy(c, chat)
        compaction = policy.get("compaction") or {}
        state = handoff.configure(sessions={"A": cid + "-A", "B": cid + "-B"},
                                  prepare_percent=compaction.get("preparePercent", 60),
                                  target_percent=compaction.get("targetPercent", 75),
                                  max_age_seconds=compaction.get("maxAgeSeconds", 300),
                                  references=["conductor-queue:" + cid])
        now = self.clock()
        c.execute("INSERT INTO conductors(id, chat_id, ordinal, status, handoff, created_at, updated_at)"
                  " VALUES(?,?,?,?,?,?,?)", (cid, chat, ordinal, "idle", json.dumps(state), now, now))
        if area:
            self.pool.set_area(c, 'conductor', cid, area)
            self.pool.member(c, cid, 'conductor', area, signature, 'busy')
        row = self.row(c, "SELECT * FROM conductors WHERE id=?", cid)
        self.event(c, chat, "conductor-created", {"conductor": self.public_conductor(row)}, key="conductor:" + cid)
        return row

    def refresh_instances(self, c):
        for member in list(c.execute("SELECT * FROM pool_members WHERE role='conductor' AND state='busy'")):
            con = self.row(c, 'SELECT * FROM conductors WHERE id=?', member['id'])
            busy = c.execute("SELECT COUNT(*) FROM requests WHERE conductor_id=? AND status IN ('accepted','planning','delegated','awaiting-synthesis','cancelling')", (member['id'],)).fetchone()[0]
            if con and con['status'] == 'idle' and not busy:
                c.execute("UPDATE pool_members SET state='idle',last_used=? WHERE id=?", (self.clock(), member['id']))

    def deliver_user(self, c, req, payload, source, *, mid=None):
        if not req['conductor_id']:
            previous = self.row(c, 'SELECT message FROM request_waits WHERE request_id=?', req['id'])
            messages = json.loads(previous['message']) if previous else []
            message = {'payload': payload, 'source': source, 'mid': mid}
            if not any(item['source'] == source for item in messages):
                messages.append(message)
            c.execute('INSERT OR REPLACE INTO request_waits VALUES(?,?)', (req['id'], json.dumps(messages)))
            return
        self.enqueue(c, req['conductor_id'], req['id'], 'user-message', payload, source, mid=mid)

    def schedule_instances(self):
        with self.tx() as c:
            self.refresh_instances(c)
            handled = self.pool.retire_idle(c)
            for wait in list(c.execute("SELECT w.* FROM request_waits w JOIN requests r ON r.id=w.request_id ORDER BY r.received_at,r.id")):
                req = self.row(c, 'SELECT * FROM requests WHERE id=?', wait['request_id'])
                if req['status'] == 'cancelled':
                    c.execute('DELETE FROM request_waits WHERE request_id=?', (req['id'],))
                    continue
                area = self.pool.get_area(c, 'request', req['id'])
                con = self.pick_conductor(c, req['chat_id'], area=area)
                if not con:
                    continue
                c.execute('UPDATE requests SET conductor_id=? WHERE id=?', (con['id'], req['id']))
                req = self.set_request(c, self.row(c, 'SELECT * FROM requests WHERE id=?', req['id']), 'accepted')
                for message in json.loads(wait['message']):
                    self.deliver_user(c, req, message['payload'], message['source'], mid=message['mid'])
                    if message['payload'].get('inputId'):
                        self.event(c, req['chat_id'], 'input-routed', {'inputId': message['payload']['inputId'], 'clientMessageId': message['payload'].get('clientMessageId'), 'requestId': req['id'], 'conductorId': con['id']})
                c.execute('DELETE FROM request_waits WHERE request_id=?', (req['id'],))
                handled += 1
            return handled

    def enqueue(self, c, conductor_id, request_id, kind, payload, source, *, mid=None):
        mid = mid or ident("mb")
        cur = c.execute("INSERT OR IGNORE INTO mailbox(id, conductor_id, request_id, kind, payload, status, enqueued_at,"
                        " source) VALUES(?,?,?,?,?,?,?,?)", (mid, conductor_id, request_id, kind,
                                                             json.dumps(payload, ensure_ascii=False), "queued",
                                                             self.clock(), source))
        if cur.rowcount:
            self.handoff_update(c, conductor_id, lambda s: handoff.transition(s, {
                "type": "event", "slot": s["owner"], "epoch": s["epoch"], "id": mid, "reference": "mailbox:" + mid,
                "kind": kind}))
        return mid

    def handoff_update(self, c, conductor_id, change):
        row = self.row(c, "SELECT handoff FROM conductors WHERE id=?", conductor_id)
        state = change(json.loads(row["handoff"]))
        c.execute("UPDATE conductors SET handoff=?, updated_at=? WHERE id=?", (json.dumps(state), self.clock(), conductor_id))
        return state

    def set_request(self, c, req, status, **extra):
        fields = {"status": status, "version": req["version"] + 1, "updated_at": self.clock(), **extra}
        c.execute("UPDATE requests SET %s WHERE id=?" % ", ".join(k + "=?" for k in fields), (*fields.values(), req["id"]))
        new = self.row(c, "SELECT * FROM requests WHERE id=?", req["id"])
        self.event(c, req["chat_id"], "request-status", {"request": self.public_request(new)})
        return new

    def set_delegation(self, c, d, status, **extra):
        fields = {"status": status, "version": d["version"] + 1, "updated_at": self.clock(), **extra}
        c.execute("UPDATE delegations SET %s WHERE id=?" % ", ".join(k + "=?" for k in fields), (*fields.values(), d["id"]))
        return self.row(c, "SELECT * FROM delegations WHERE id=?", d["id"])

    def question_view(self, row):
        stored = self.row(self.connection(), 'SELECT payload FROM question_details WHERE id=?', row['id'])
        return {**json.loads(stored['payload'] if stored else '{}'), 'id': row['id'], 'requestId': row['request_id'], 'inputId': row['input_id'], 'delegationId': row['delegation_id'],
                'logicalConductorId': 'logical-conductor', 'conductorInstanceId': row['conductor_id'],
                'slot': row['slot'], 'epoch': row['epoch'], 'kind': row['kind'], 'state': row['state'], 'text': row['text'], 'source': row['source']}

    def question(self, c, request_id, conductor_id, kind, text, source, *, input_id=None, delegation_id=None, details=None):
        qid = 'question-' + digest([request_id, input_id, delegation_id, source])[:24]
        con = self.row(c, 'SELECT * FROM conductors WHERE id=?', conductor_id) if conductor_id else None
        state = json.loads(con['handoff']) if con else {}
        c.execute('INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                  (qid, request_id, input_id, delegation_id, conductor_id, state.get('owner'), state.get('epoch'), kind, 'pending', text, source))
        if details:
            kept = {k: details.get(k) for k in ('decisionKind', 'decisionScope', 'reason', 'impact', 'alternatives', 'recommendation', 'decision', 'target')}
            c.execute('INSERT OR IGNORE INTO question_details VALUES(?,?)', (qid, json.dumps(kept)))
        # Values are structural identity and actual text; no question merging or output ordering here.
        row = self.row(c, 'SELECT * FROM questions WHERE id=?', qid)
        self.event(c, con['chat_id'] if con else self.row(c, 'SELECT chat_id FROM inputs WHERE id=?', input_id)['chat_id'],
                   'question-state', {'question': row})
        return qid

    def answer_question(self, c, qid, source):
        row = self.row(c, "SELECT * FROM questions WHERE id=? AND state='pending'", qid)
        require(row, 'question_unknown', 'Select the current pending question')
        c.execute("UPDATE questions SET state='answered' WHERE id=?", (qid,))
        chat = self.row(c, 'SELECT chat_id FROM requests WHERE id=?', row['request_id']) if row['request_id'] else self.row(c, 'SELECT chat_id FROM inputs WHERE id=?', row['input_id'])
        self.event(c, chat['chat_id'], 'question-state', {'question': self.row(c, 'SELECT * FROM questions WHERE id=?', qid), 'answerSource': source})

    def close_questions(self, c, request_id, status, *, delegation_id=None, kind=None):
        for row in list(c.execute("SELECT * FROM questions WHERE request_id=? AND state='pending'", (request_id,))):
            if delegation_id is not None and row['delegation_id'] != delegation_id:
                continue
            if kind is not None and row['kind'] != kind:
                continue
            c.execute('UPDATE questions SET state=? WHERE id=?', (status, row['id']))
            chat = self.row(c, 'SELECT chat_id FROM requests WHERE id=?', request_id)['chat_id']
            self.event(c, chat, 'question-state', {'question': self.row(c, 'SELECT * FROM questions WHERE id=?', row['id'])})

    # -- control (version-checked transitions) ---------------------------------
    def route_control(self, c, inp, p):
        chat, action = inp["chat_id"], p["action"]

        def reject(reason, **detail):
            self.event(c, chat, "control-rejected", {"inputId": inp["id"], "commandId": p["commandId"], "action": action,
                                                     "reason": reason, **detail}, key="control-rejected:" + inp["id"])
            return {"status": "processed", "reason": reason}

        if action == 'resolve-area':
            held = self.row(c, 'SELECT * FROM inputs WHERE id=? AND chat_id=?', p.get('inputId'), chat)
            require(held and held['status'] == 'held' and held['reason'] == 'area-required', 'input_not_held', 'Select the pending area question')
            area = self.pool.area(p.get('area'))
            original = json.loads(held['payload'])
            original.update(area=area, areaSource='control:' + p['commandId'])
            c.execute("UPDATE inputs SET payload=?,status='pending',reason='resolved' WHERE id=?", (json.dumps(original), held['id']))
            for question in c.execute("SELECT id FROM questions WHERE input_id=? AND kind='area' AND state='pending'", (held['id'],)):
                self.answer_question(c, question['id'], 'control:' + p['commandId'])
            self.event(c, chat, 'input-resolved', {'inputId': held['id'], 'area': area})
            return {'status': 'processed'}
        if action == "resolve-input":
            held = self.row(c, "SELECT * FROM inputs WHERE id=? AND chat_id=?", p.get("inputId"), chat)
            if not held or held["status"] != "held":
                return reject("not-held")
            require(p.get("relation") in {"new", "followup"}, "relation_invalid", "Resolve with new or followup")
            original = json.loads(held["payload"])
            original.update({"relation": p["relation"], "routingSource": "control:" + p["commandId"], **({"requestId": p["requestId"]} if p.get("requestId") else {})})
            c.execute("UPDATE inputs SET payload=?, status='pending', reason='resolved' WHERE id=?",
                      (json.dumps(original, ensure_ascii=False), held["id"]))
            self.event(c, chat, "input-resolved", {"inputId": held["id"], "relation": p["relation"],
                                                   "requestId": p.get("requestId")}, key="resolved:" + held["id"])
            return {"status": "processed", "reason": "resolved"}
        if action == 'create-child':
            from tasks import domains
            result = domains.subdomain(self.path.parent, p.get('areaId'), p.get('name'), 'human', 'human-control:' + p['commandId'], p.get('expectedRevision'))
            self.event(c, chat, 'role-pools-state', self.roles.projection(c))
            return result
        if action == 'accept-area-task':
            require(isinstance(p.get('text'), str) and p['text'].strip(), 'message_empty', 'Request text required')
            area = self.pool.area(p.get('area'))
            req = self.create_request(c, chat, p['text'], {**inp, 'processingChoice': p.get('route'), 'requestProfile': p.get('profile', 'work'), 'areaSource': 'human-control:' + p['commandId']}, area=area)
            instruction_id = self.responsibility.instruction(c, req['id'], p['text'], 'human-control:' + p['commandId']) if self.policy(c, chat)['conductor'] == 'managed' else None
            self.deliver_user(c, req, {'instructionId': instruction_id, 'text': p['text'], 'clientMessageId': p['commandId']}, 'human-control:' + p['commandId'])
            self.event(c, chat, 'role-pools-state', self.roles.projection(c))
            return {'requestId': req['id']}
        if action in ('hire-role', 'configure-area', 'configure-role'):
            if action == 'hire-role':
                result = self.roles.hire(c, p.get('area'), p.get('profile'), p.get('settings'), 'human-control:' + p['commandId'])
            else:
                self.roles.configure(c, p.get('areaId'), 'human-control:' + p['commandId'], route=p.get('route'), profile=p.get('profile'), settings=p.get('settings'))
                result = {'configured': True}
            self.event(c, chat, 'role-pools-state', self.roles.projection(c))
            return result
        if action == 'exclude-required':
            req = self.row(c, 'SELECT * FROM requests WHERE id=? AND chat_id=?', p.get('requestId'), chat)
            require(req is not None, 'request_unknown', 'Select the exact request')
            self.responsibility.exclude(c, req['id'], p.get('obligationId'), p.get('expectedTaskVersion'), p.get('reason'), 'human-control:' + p['commandId'])
            return {'status': 'processed', 'requestId': req['id']}
        if action == 'register-required':
            req = self.row(c, 'SELECT * FROM requests WHERE id=? AND chat_id=?', p.get('requestId'), chat)
            require(req and req['version'] == p.get('expectedVersion'), 'version_conflict', 'Register obligations against the observed request version')
            return self.responsibility.register(c, req['id'], p.get('tasks'), 'human-control:' + p['commandId'])
        expected = p.get("expectedVersion")
        require(type(expected) is int, "version_required", "Control needs the version the Human saw")
        if action in ('confirm-decision', 'answer-question'):
            req = self.row(c, 'SELECT * FROM requests WHERE id=? AND chat_id=?', p.get('requestId'), chat)
            require(req and req['version'] == expected, 'version_conflict', 'Use the current request version')
            source = 'control:' + p['commandId']
            if action == 'confirm-decision':
                require(p.get('decisionKind') in ('approval', 'scope', 'assignment'), 'decision_invalid', 'Confirm approval, scope or assignment')
                self.pool.decide(c, req['id'], p['decisionKind'], p.get('value'), source, 'human', p['commandId'])
            else:
                question = self.row(c, "SELECT * FROM questions WHERE id=? AND request_id=? AND state='pending'", p.get('questionId'), req['id'])
                require(question and question['kind'] in ('conductor', 'declaration'), 'question_unknown', 'Select this request conductor question')
                require(isinstance(p.get('text'), str) and p['text'].strip(), 'message_empty', 'Question answer required')
                self.answer_question(c, question['id'], source)
                self.enqueue(c, req['conductor_id'], req['id'], 'user-message', {'text': p['text'], 'questionId': question['id']}, source)
            self.event(c, chat, 'fixed-decisions', {'requestId': req['id'], 'fixedDecisions': self.pool.decisions(c, req['id'])})
            return {'status': 'processed', 'requestId': req['id']}
        if action == "reassign":
            req = self.row(c, "SELECT * FROM requests WHERE id=? AND chat_id=?", p.get("requestId"), chat)
            if not req:
                return reject("unknown-target")
            if req["status"] not in OPEN_REQUEST:
                return reject("already-terminal", status=req["status"], version=req["version"])
            if req["version"] != expected:
                return reject("version-conflict", version=req["version"])
            self.reassign(c, req, p.get("toConductorId"))
            return {"status": "processed", "requestId": req["id"]}
        if p.get("delegationId"):
            d = self.row(c, "SELECT * FROM delegations WHERE id=? AND chat_id=?", p["delegationId"], chat)
            if not d:
                return reject("unknown-target")
            if action in ('integrate-workspace', 'cleanup-workspace'):
                require(d['version'] == expected and d['status'] == 'completed', 'workspace_action_invalid', 'Exact completed delegation version required')
                self.event(c, chat, 'workspace-action', {'delegation': self.public_delegation(c, d), 'action': action.split('-')[0],
                           'authorizationReference': 'human-control:' + p['commandId']}, key=p['commandId'])
                return {'status': 'processed', 'requestId': d['request_id']}
            if action == 'answer-worker':
                require(d['version'] == expected and d['status'] == 'awaiting-answer', 'worker_answer_invalid', 'Answer the current worker question')
                require(isinstance(p.get('text'), str) and p['text'].strip(), 'message_empty', 'Worker answer text required')
                pending = list(c.execute("SELECT * FROM questions WHERE delegation_id=? AND state='pending'", (d['id'],)))
                chosen = next((q for q in pending if q['id'] == p.get('questionId')), None) if p.get('questionId') else pending[0] if len(pending) == 1 else None
                require(chosen is not None, 'question_ambiguous', 'Select the exact worker question')
                self.answer_question(c, chosen['id'], 'control:' + p['commandId'])
                d = self.set_delegation(c, d, 'dispatched')
                self.event(c, chat, 'worker-answer', {'delegation': self.public_delegation(c, d), 'text': p['text'], 'commandId': p['commandId'], 'question': self.question_view(chosen)}, key=p['commandId'])
                return {'status': 'processed', 'requestId': d['request_id']}
            if d["status"] in DELEGATION_TERMINAL:
                # A finished external effect is reported as finished, never relabelled cancelled.
                return reject("already-terminal", status=d["status"], version=d["version"])
            if d["version"] != expected:
                return reject("version-conflict", status=d["status"], version=d["version"])
            if action == "approve":
                if d["status"] != "awaiting-approval":
                    return reject("not-awaiting-approval", status=d["status"], version=d["version"])
                self.pool.decide(c, d['request_id'], 'approval', {'delegationId': d['id'], 'writeScope': json.loads(d['spec']).get('writeScope'), 'expectedVersion': expected},
                                 'control:' + p['commandId'], 'human', p['commandId'])
                d = self.set_delegation(c, d, "ready")
                self.event(c, chat, "delegation-approved", {"delegation": self.public_delegation(c, d),
                                                            "commandId": p["commandId"]})
            else:
                self.cancel_delegation(c, d, p["commandId"])
            return {"status": "processed", "requestId": d["request_id"]}
        req = self.row(c, "SELECT * FROM requests WHERE id=? AND chat_id=?", p.get("requestId"), chat)
        if not req:
            return reject("unknown-target")
        require(action == "cancel", "control_action", "Approval targets a delegation")
        if req["status"] not in OPEN_REQUEST or req["status"] == "cancelling":
            return reject("already-terminal", status=req["status"], version=req["version"])
        if req["version"] != expected:
            return reject("version-conflict", status=req["status"], version=req["version"])
        req = self.set_request(c, req, "cancelling")
        for child in list(c.execute("SELECT * FROM requests WHERE parent_id=? AND status NOT IN ('completed','cancelled')", (req['id'],))):
            child = self.set_request(c, dict(child), 'cancelling')
            for delegation in list(c.execute("SELECT * FROM delegations WHERE request_id=? AND status NOT IN (?,?,?)", (child['id'], *DELEGATION_TERMINAL))):
                self.cancel_delegation(c, dict(delegation), p['commandId'])
            self.settle_request(c, child['id'])
        for d in [dict(r) for r in c.execute("SELECT * FROM delegations WHERE request_id=? AND status NOT IN (?,?,?)",
                                             (req["id"], *DELEGATION_TERMINAL))]:
            self.cancel_delegation(c, d, p["commandId"])
        self.settle_request(c, req["id"])
        return {"status": "processed", "requestId": req["id"]}

    def cancel_delegation(self, c, d, command_id):
        if d["status"] in ("awaiting-approval", "awaiting-answer"):
            # Approval never started; an awaiting-answer worker already confirmed process exit.
            # Cancellation closes the pending continuation without relabelling its managed history.
            d = self.set_delegation(c, d, "cancelled", cancel_requested=1)
            c.execute("UPDATE attempts SET status='cancelled', ended_at=?, updated_at=? WHERE id=? AND status IN ('pending','running','starting')",
                      (self.clock(), self.clock(), d["attempt_id"]))
            self.close_questions(c, d['request_id'], 'cancelled', delegation_id=d['id'])
            self.pool.release_worker(c, d["attempt_id"])
            self.event(c, d["chat_id"], "delegation-cancelled", {"delegation": self.public_delegation(c, d),
                                                                 "commandId": command_id})
        elif d["status"] != "cancel-requested":
            d = self.set_delegation(c, d, "cancel-requested", cancel_requested=1)
            self.event(c, d["chat_id"], "delegation-cancel-requested", {"delegation": self.public_delegation(c, d),
                                                                        "commandId": command_id})
        return d

    def reassign(self, c, req, target=None):
        """Owner change: the request's fencing epoch advances; queued work follows the new owner."""
        if target:
            new = self.row(c, "SELECT * FROM conductors WHERE id=? AND chat_id=?", target, req["chat_id"])
            require(new and new["id"] != req["conductor_id"], "conductor_invalid", "Target conductor is not usable")
        else:
            busy = {r["conductor_id"] for r in self.open_requests(c, req["chat_id"])}
            new = next((dict(r) for r in c.execute("SELECT * FROM conductors WHERE chat_id=? AND status='idle' ORDER BY ordinal",
                                                    (req["chat_id"],)) if r["id"] not in busy), None)
            new = new or self.pick_conductor(c, req["chat_id"], area=self.pool.get_area(c, "request", req["id"]))
            require(new is not None, "employment_limit", "No eligible conductor instance; request ownership is preserved")
            if new["id"] == req["conductor_id"]:
                c.execute("UPDATE conductors SET status='idle' WHERE id=?", (new["id"],))
                new = self.pick_conductor(c, req["chat_id"], area=self.pool.get_area(c, "request", req["id"]))
        if conductor_pool.enabled(self.policy(c, req['chat_id'])):
            require(all((self.pool.get_area(c, 'conductor', new['id']) or {}).get(key) == (self.pool.get_area(c, 'request', req['id']) or {}).get(key) for key in ('domainId', 'subdomainId')), 'area_mismatch', 'Instance responsibility must match the request area')
        old = req["conductor_id"]
        moved = [dict(r) for r in c.execute("SELECT * FROM mailbox WHERE request_id=? AND status IN ('queued','delivered')",
                                            (req["id"],))]
        for item in moved:
            c.execute("UPDATE mailbox SET status='moved' WHERE id=?", (item["id"],))
            self.enqueue(c, new["id"], req["id"], item["kind"], json.loads(item["payload"]), "moved:" + item["id"])
        new_state = json.loads(new['handoff'])
        c.execute("UPDATE questions SET conductor_id=?,slot=?,epoch=? WHERE request_id=? AND state='pending'", (new['id'], new_state['owner'], new_state['epoch'], req['id']))
        for question in c.execute("SELECT * FROM questions WHERE request_id=? AND state='pending'", (req['id'],)):
            self.event(c, req['chat_id'], 'question-state', {'question': dict(question)})
        c.execute("UPDATE delegations SET conductor_id=? WHERE request_id=?", (new["id"], req["id"]))
        c.execute("UPDATE requests SET conductor_id=?, owner_epoch=owner_epoch+1 WHERE id=?", (new["id"], req["id"]))
        # The former owner's unfinished planning is not inherited as progress: the new owner starts it again.
        status = "accepted" if req["status"] == "planning" else req["status"]
        req = self.set_request(c, self.row(c, "SELECT * FROM requests WHERE id=?", req["id"]), status)
        self.event(c, req["chat_id"], "owner-changed", {"requestId": req["id"], "fromConductorId": old,
                                                        "toConductorId": new["id"], "ownerEpoch": req["owner_epoch"],
                                                        "movedItems": len(moved)})
        self.op(c, "owner-changed", requestId=req["id"], fromConductor=old, toConductor=new["id"])

    # -- executor lifecycle -------------------------------------------------------
    def route_lifecycle(self, c, inp, p):
        d = self.row(c, "SELECT * FROM delegations WHERE id=? AND chat_id=?", p["delegationId"], inp["chat_id"])
        a = self.row(c, "SELECT * FROM attempts WHERE id=?", p["attemptId"])
        require(d and a and a["delegation_id"] == d["id"], "attempt_unknown", "Event names an unknown attempt")
        kind, now = p["kind"], self.clock()
        status = {"started": "running", "completed": "completed", "failed": "failed", "cancelled": "cancelled"}.get(kind)
        if status and a["status"] not in ATTEMPT_TERMINAL:
            c.execute("UPDATE attempts SET status=?, started_at=COALESCE(started_at, ?), ended_at=?, error=?, updated_at=?"
                      " WHERE id=?", (status, now, now if status in ATTEMPT_TERMINAL else None,
                                      json.dumps(p.get("error")) if p.get("error") else None, now, a["id"]))
        if a["id"] != d["attempt_id"]:
            # A late event of a superseded attempt is kept but cannot overwrite the current attempt.
            self.event(c, d["chat_id"], "attempt-late-event", {"delegationId": d["id"], "attemptId": a["id"],
                                                               "currentAttemptId": d["attempt_id"], "kind": kind})
            self.op(c, "late-attempt-event", delegationId=d["id"], attemptId=a["id"], eventKind=kind)
            return {"status": "processed", "reason": "stale-attempt", "requestId": d["request_id"]}
        if d["status"] in DELEGATION_TERMINAL:
            return {"status": "processed", "reason": "already-terminal", "requestId": d["request_id"]}
        if kind == "started":
            if d["status"] in ("ready", "dispatched"):
                d = self.set_delegation(c, d, "running")
            self.event(c, d["chat_id"], "attempt-started", {"delegation": self.public_delegation(c, d)})
        elif kind == "question":
            qid = self.question(c, d['request_id'], d['conductor_id'], 'worker', (p.get('question') or {}).get('text'),
                                'worker:' + p['workerEventId'], delegation_id=d['id'], details=p.get('question'))
            question = p.get('question') or {}
            if question.get('decisionKind') == 'approval' and question.get('decisionScope') == 'task-execution' and self.policy(c, d['chat_id'])['approvalPolicy'] == 'bypass':
                retries = c.execute("SELECT COUNT(*) FROM fixed_decisions WHERE request_id=? AND kind='captured-authorization-resume'", (d['request_id'],)).fetchone()[0]
                if retries < int(self.policy(c, d['chat_id']).get('maxAttempts', 2)):
                    self.answer_question(c, qid, 'captured-task-policy')
                    self.pool.decide(c, d['request_id'], 'captured-authorization-resume', {'questionId': qid}, self.policy(c, d['chat_id'])['reference'], 'captured', qid)
                    self.event(c, d['chat_id'], 'worker-answer', {'delegation': self.public_delegation(c, d), 'text': 'Continue the already authorized bounded task under the captured bypass policy. Preserve credentials, scope and permissions.', 'commandId': 'captured-' + qid}, key='captured-' + qid)
                    return {'status': 'processed', 'reason': 'captured-policy-resume', 'requestId': d['request_id']}
            d = self.set_delegation(c, d, "awaiting-answer")
            self.event(c, d["chat_id"], "worker-question", {"delegation": self.public_delegation(c, d),
                                                            "question": {**(p.get("question") or {}), "questionId": qid}})
        elif kind == "completed":
            # Completion that wins a race with cancellation stays completed; cancelRequested records the race.
            d = self.set_delegation(c, d, "completed", result=json.dumps(p.get("result"), ensure_ascii=False))
            self.event(c, d["chat_id"], "delegation-completed", {"delegation": self.public_delegation(c, d)})
        elif kind == "cancelled":
            d = self.set_delegation(c, d, "cancelled")
            self.event(c, d["chat_id"], "delegation-cancelled", {"delegation": self.public_delegation(c, d)})
        else:
            error = p.get("error") or {}
            if error.get("retryable") and not d["cancel_requested"] and d["attempt_count"] < d["max_attempts"]:
                aid = ident("att")
                c.execute("INSERT INTO attempts(id, delegation_id, number, status, backend, created_at, updated_at)"
                          " VALUES(?,?,?,?,?,?,?)", (aid, d["id"], d["attempt_count"] + 1, "pending", a["backend"], now, now))
                d = self.set_delegation(c, d, "dispatched", attempt_id=aid, attempt_count=d["attempt_count"] + 1,
                                        error=json.dumps(error, ensure_ascii=False))
                self.event(c, d["chat_id"], "attempt-retry", {"delegation": self.public_delegation(c, d),
                                                              "previousAttemptId": a["id"], "error": error})
            else:
                d = self.set_delegation(c, d, "failed", error=json.dumps(error, ensure_ascii=False))
                self.event(c, d["chat_id"], "delegation-failed", {"delegation": self.public_delegation(c, d)})
        if kind in ('completed', 'failed', 'cancelled'):
            self.close_questions(c, d['request_id'], 'closed-' + kind, delegation_id=d['id'])
            self.pool.release_worker(c, a['id'])
        self.settle_request(c, d["request_id"])
        return {"status": "processed", "requestId": d["request_id"]}

    def route_progress(self, ids):
        """Coalesce a burst per attempt: every raw input stays recorded, the latest drives the projection."""
        with self.tx() as c:
            rows = [dict(r) for r in c.execute("SELECT * FROM inputs WHERE id IN (%s) AND status='pending' ORDER BY seq"
                                               % ",".join("?" * len(ids)), ids)]
            latest = {}
            for row in rows:
                latest[json.loads(row["payload"])["attemptId"]] = row
            now = self.clock()
            for row in rows:
                p = json.loads(row["payload"])
                if latest[p["attemptId"]] is not row:
                    c.execute("UPDATE inputs SET status='processed', routed_at=?, reason='coalesced' WHERE id=?", (now, row["id"]))
                    continue
                a = self.row(c, "SELECT * FROM attempts WHERE id=?", p["attemptId"])
                d = self.row(c, "SELECT * FROM delegations WHERE id=?", p["delegationId"])
                reason = None
                if not a or not d or a["delegation_id"] != d["id"]:
                    reason = "attempt-unknown"
                elif a["id"] != d["attempt_id"] or d["status"] in DELEGATION_TERMINAL or a["status"] in ATTEMPT_TERMINAL:
                    reason = "stale-attempt"
                else:
                    progress = {"step": p.get("step"), "detail": p.get("detail"), "at": now, "sentAt": p.get("sentAt"), "source": p.get("source")}
                    if type(p.get("completed")) is int and type(p.get("total")) is int and 0 <= p["completed"] <= p["total"]:
                        progress.update(completed=p["completed"], total=p["total"])  # numeric only when measured
                    c.execute("UPDATE attempts SET progress=?, updated_at=? WHERE id=?",
                              (json.dumps(progress, ensure_ascii=False), now, a["id"]))
                    self.event(c, d["chat_id"], "attempt-progress", {"delegationId": d["id"], "attemptId": a["id"],
                                                                     "progress": progress})
                c.execute("UPDATE inputs SET status='processed', routed_at=?, reason=? WHERE id=?", (now, reason, row["id"]))
        return len(rows)

    def settle_request(self, c, request_id):
        req = self.row(c, "SELECT * FROM requests WHERE id=?", request_id)
        rows = [r["status"] for r in c.execute("SELECT status FROM delegations WHERE request_id=?", (request_id,))]
        children = [r['status'] for r in c.execute('SELECT status FROM requests WHERE parent_id=?', (request_id,))]
        if any(s not in DELEGATION_TERMINAL for s in rows) or any(s not in ('completed', 'cancelled') for s in children):
            return req
        if not rows and not children and req['status'] != 'cancelling':
            return req
        if req["status"] == "cancelling":
            req = self.set_request(c, req, "cancelled", final_at=self.clock())
            self.close_questions(c, req["id"], "cancelled")
            self.event(c, req["chat_id"], "request-cancelled", {"request": self.public_request(req)})
            self.notify_parent(c, req)
            if req.get('parent_id'):
                self.settle_request(c, req['parent_id'])
        elif req["status"] in ("delegated", "planning", "accepted"):
            req = self.set_request(c, req, "awaiting-synthesis")
        return req

    # -- relay and consumers ------------------------------------------------------
    def publish_pending(self, limit=512):
        """Outbox relay: publish, then mark. A crash between the two republishes harmlessly."""
        c = self.connection()
        rows = [dict(r) for r in c.execute("SELECT seq, type FROM events WHERE published=0 ORDER BY seq LIMIT ?", (limit,))]
        for row in rows:
            with self.tx() as t:
                for name in ROUTES.get(row["type"], ("ui",)):
                    t.execute("INSERT OR IGNORE INTO deliveries(subscription, event_seq, status, available_at)"
                              " VALUES(?,?,?,?)", (name, row["seq"], "ready", self.clock()))
            self.fault("after-publish", seq=row["seq"])
            with self.tx() as t:
                t.execute("UPDATE events SET published=1 WHERE seq=?", (row["seq"],))
        return len(rows)

    def consume(self, subscription, handler, limit=128):
        """Apply each delivery once: consumer inbox + effects commit together, ack afterwards."""
        c = self.connection()
        now = self.clock()
        rows = [dict(r) for r in c.execute(
            "SELECT d.event_seq, d.failures, e.id, e.chat_id, e.type, e.payload, e.created_at FROM deliveries d"
            " JOIN events e ON e.seq=d.event_seq WHERE d.subscription=? AND d.status='ready' AND d.available_at<=?"
            " ORDER BY d.event_seq LIMIT ?", (subscription, now, limit))]
        after = []
        for row in rows:
            try:
                with self.tx() as t:
                    seen = t.execute("SELECT 1 FROM consumer_inbox WHERE subscription=? AND event_id=?",
                                     (subscription, row["id"])).fetchone()
                    if not seen:
                        event = {"seq": row["event_seq"], "id": row["id"], "chatId": row["chat_id"], "type": row["type"],
                                 "payload": json.loads(row["payload"]), "createdAt": row["created_at"]}
                        effect = handler(t, event)
                        if effect:
                            after.append(effect)
                        t.execute("INSERT INTO consumer_inbox(subscription, event_id, applied_at) VALUES(?,?,?)",
                                  (subscription, row["id"], self.clock()))
                self.fault("after-consume-commit", subscription=subscription, seq=row["event_seq"])
                with self.tx() as t:
                    t.execute("UPDATE deliveries SET status='acked', acked_at=? WHERE subscription=? AND event_seq=?",
                              (self.clock(), subscription, row["event_seq"]))
            except SimulatedCrash:
                raise
            except Exception as error:
                with self.tx() as t:
                    failures = row["failures"] + 1
                    quarantined = failures >= POISON_ATTEMPTS
                    t.execute("UPDATE deliveries SET failures=?, status=?, last_error=?, available_at=?"
                              " WHERE subscription=? AND event_seq=?",
                              (failures, "quarantined" if quarantined else "ready", type(error).__name__,
                               self.clock() + 0.05 * 2 ** failures, subscription, row["event_seq"]))
                    self.op(t, "delivery-failure", subscription=subscription, eventSeq=row["event_seq"],
                            error=type(error).__name__, failures=failures)
                    if quarantined:
                        self.event(t, row["chat_id"], "event-quarantined", {
                            "subscription": subscription, "eventSeq": row["event_seq"], "eventType": row["type"],
                            "error": type(error).__name__}, key="quarantine:%s:%s" % (subscription, row["event_seq"]))
        for effect in after:
            effect()
        return len(rows)

    def requeue_quarantined(self, subscription, event_seq):
        """Operator recovery after a fix: the preserved delivery becomes ready again."""
        with self.tx() as c:
            cur = c.execute("UPDATE deliveries SET status='ready', failures=0, available_at=? WHERE subscription=?"
                            " AND event_seq=? AND status='quarantined'", (self.clock(), subscription, event_seq))
            require(cur.rowcount == 1, "delivery_unknown", "No quarantined delivery for that subscription and event")
            self.op(c, "delivery-requeued", subscription=subscription, eventSeq=event_seq)
        return {"subscription": subscription, "eventSeq": event_seq, "status": "ready"}

    def quarantined(self):
        c = self.connection()
        return {"deliveries": [dict(r) for r in c.execute(
                    "SELECT d.subscription, d.event_seq AS eventSeq, d.failures, d.last_error AS lastError, e.type"
                    " FROM deliveries d JOIN events e ON e.seq=d.event_seq WHERE d.status='quarantined' ORDER BY d.event_seq")],
                "inputs": [dict(r) for r in c.execute(
                    "SELECT id, chat_id AS chatId, class, kind, failures, reason FROM inputs WHERE status='quarantined'")]}

    def conductor_handler(self, c, event):
        """Results return to the request's current owner, looked up at delivery time."""
        p = event["payload"]
        delegation = p.get("delegation") or {}
        request_id = delegation.get("requestId") or (p.get("request") or {}).get("id")
        req = self.row(c, "SELECT * FROM requests WHERE id=?", request_id)
        if not req:
            return None
        kind = "request-cancelled" if event["type"] == "request-cancelled" else (
            "worker-question" if event["type"] == "worker-question" else "delegation-result")
        self.enqueue(c, req["conductor_id"], req["id"], kind, {"eventType": event["type"], **p},
                     "event:" + event["id"], mid="mb-" + event["id"])
        return None

    # -- conductor turns (fenced write sinks) -------------------------------------
    def begin_turn(self, conductor_id):
        """Safe processing boundary: the queued mailbox at turn start becomes this turn's input."""
        with self.tx() as c:
            con = self.row(c, "SELECT * FROM conductors WHERE id=?", conductor_id)
            if not con or con["status"] != "idle":
                return None
            items = [dict(r) for r in c.execute("SELECT * FROM mailbox WHERE conductor_id=? AND status='queued' ORDER BY seq",
                                                (conductor_id,))]
            if not items:
                return None
            member = self.row(c, 'SELECT * FROM pool_members WHERE id=?', conductor_id)
            if member and member['state'] != 'busy':
                reason = self.pool.room(c, 'conductor', json.loads(member['area']))
                if reason:
                    old = self.row(c, 'SELECT reason FROM instance_waits WHERE conductor_id=?', conductor_id)
                    if not old or old['reason'] != reason:
                        c.execute('INSERT OR REPLACE INTO instance_waits VALUES(?,?)', (conductor_id, reason))
                        self.event(c, con['chat_id'], 'instance-waiting', {'conductor': self.public_conductor(con)})
                    return None
                c.execute("UPDATE pool_members SET state='busy',last_used=? WHERE id=?", (self.clock(), conductor_id))
            c.execute('DELETE FROM instance_waits WHERE conductor_id=?', (conductor_id,))
            tid, now = ident("turn"), self.clock()
            state = self.handoff_update(c, conductor_id, lambda s: handoff.transition(s, {
                "type": "turn-start", "slot": s["owner"], "epoch": s["epoch"], "id": tid}))
            c.execute("UPDATE conductors SET status='busy', turn_id=?, turn_started_at=? WHERE id=?", (tid, now, conductor_id))
            c.execute("UPDATE mailbox SET status='delivered', turn_id=?, delivered_at=? WHERE conductor_id=? AND status='queued'"
                      " AND seq<=?", (tid, now, conductor_id, items[-1]["seq"]))
            requests = {}
            for item in items:
                if item["request_id"] and item["request_id"] not in requests:
                    req = self.row(c, "SELECT * FROM requests WHERE id=?", item["request_id"])
                    if req["status"] == "accepted":
                        req = self.set_request(c, req, "planning")
                    requests[req["id"]] = req
            con = self.row(c, "SELECT * FROM conductors WHERE id=?", conductor_id)
            self.event(c, con["chat_id"], "turn-started", {"conductor": self.public_conductor(con), "turnId": tid,
                                                           "items": len(items)})
            context = {"conductorId": conductor_id, "chatId": con["chat_id"], "slot": state["owner"],
                       "epoch": state["epoch"], "turnId": tid, "checkpoint": json.loads(con["checkpoint"] or "null"),
                       "items": [{**{k: item[k] for k in ("id", "kind", "request_id")}, "payload": json.loads(item["payload"])}
                                 for item in items],
                       "requests": {rid: {**self.public_request(req), "delegations": self.request_delegations(c, rid)}
                                    for rid, req in requests.items()},
                       "responsibility": {rid: self.responsibility.view(c, rid) for rid in requests},
                       "fixedDecisions": [decision for rid in requests for decision in self.pool.decisions(c, rid)],
                       "areaCatalog": self.pool.catalog(),
                       "area": self.pool.get_area(c, 'conductor', conductor_id),
                       "logicalConductorId": 'logical-conductor',
                       "pendingQuestions": [self.question_view(q) for q in c.execute("SELECT * FROM questions WHERE conductor_id=? AND state='pending'", (conductor_id,))],
                       "policy": self.policy(c, con["chat_id"]),
                       "children": {rid: [self.public_request(dict(r)) for r in c.execute("SELECT * FROM requests WHERE parent_id=?", (rid,))] for rid in requests}}
        return context

    def request_delegations(self, c, request_id):
        return [self.public_delegation(c, dict(r)) for r in
                c.execute("SELECT * FROM delegations WHERE request_id=? ORDER BY created_at", (request_id,))]

    def fence(self, c, token, request_id=None, *, turn=True):
        con = self.row(c, "SELECT * FROM conductors WHERE id=?", token.get("conductorId"))
        state = json.loads(con["handoff"]) if con else None
        if not con or not handoff.authorized(state, token.get("slot"), token.get("epoch")):
            raise StaleOwner("Conductor slot/epoch is no longer the owner")
        if turn and con["turn_id"] != token.get("turnId"):
            raise StaleOwner("Turn is no longer active for this conductor")
        if request_id:
            req = self.row(c, "SELECT * FROM requests WHERE id=?", request_id)
            if not req or req["conductor_id"] != con["id"]:
                raise StaleOwner("Request is owned by another conductor")
            return con, req
        return con, None

    def rejected(self, token, error, kind, request_id=None, c=None):
        if c is None:
            with self.tx() as c:
                return self.rejected(token, error, kind, request_id, c)
        con = self.row(c, "SELECT chat_id FROM conductors WHERE id=?", token.get("conductorId"))
        stale = isinstance(error, StaleOwner)
        self.event(c, con["chat_id"] if con else None, "stale-owner-rejected" if stale else "command-rejected", {
            "conductorId": token.get("conductorId"), "slot": token.get("slot"), "epoch": token.get("epoch"),
            "turnId": token.get("turnId"), "write": kind, "requestId": request_id, "code": error.code,
            "reason": error.message})
        if not stale and request_id and error.code in ('scope_required', 'area_required', 'role_settings_required', 'role_permission_invalid'):
            req = self.row(c, 'SELECT * FROM requests WHERE id=?', request_id)
            if req:
                qid = self.question(c, request_id, token['conductorId'], 'declaration', error.message, 'rejected:' + str(token.get('turnId')) + ':' + error.code)
                self.event(c, con['chat_id'], 'conductor-question', {'requestId': request_id, 'conductorId': token['conductorId'], 'text': error.message, 'questionId': qid, 'code': error.code})
        self.op(c, "stale-owner-rejected" if stale else "command-rejected", conductorId=token.get("conductorId"),
                write=kind, requestId=request_id, code=error.code)

    def stream(self, token, request_id, text, message_key):
        """One fenced stream chunk of a conductor answer."""
        try:
            with self.tx() as c:
                con, req = self.fence(c, token, request_id)
                if req["first_response_at"] is None:
                    c.execute("UPDATE requests SET first_response_at=? WHERE id=?", (self.clock(), req["id"]))
                self.event(c, con["chat_id"], "conductor-reply", {
                    "requestId": req["id"], "conductorId": con["id"], "messageKey": message_key, "text": text,
                    "chunk": True, "final": False, "epoch": token["epoch"], "slot": token["slot"]})
        except StaleOwner as error:
            self.rejected(token, error, "stream-chunk", request_id)
            raise

    def end_turn(self, token, commands, usage=None):
        """Apply the turn's commands atomically; any stale owner token rejects the whole result."""
        try:
            with self.tx() as c:
                con, _ = self.fence(c, token)
                applied = []
                for command in commands:
                    # Each command is its own savepoint: a stale or invalid write is rejected and recorded
                    # without discarding the conductor's other legitimate results or wedging the turn.
                    c.execute("SAVEPOINT cmd")
                    try:
                        applied.append(self.apply_command(c, token, con, command))
                        c.execute("RELEASE cmd")
                    except ContractError as error:
                        c.execute("ROLLBACK TO cmd")
                        c.execute("RELEASE cmd")
                        self.rejected(token, error, command.get("type") or "command", command.get("requestId"), c)
                        applied.append({"type": command.get("type"), "requestId": command.get("requestId"),
                                        "rejected": error.code})
                now = self.clock()
                c.execute("UPDATE mailbox SET status='processed', processed_at=? WHERE turn_id=? AND status='delivered'",
                          (now, token["turnId"]))
                for item in c.execute("SELECT id FROM mailbox WHERE turn_id=? AND status='processed'", (token["turnId"],)):
                    self.handoff_update(c, con["id"], lambda s, i=item["id"]: handoff.transition(s, {
                        "type": "processed", "slot": token["slot"], "epoch": token["epoch"], "id": i}))
                state = self.handoff_update(c, con["id"], lambda s: handoff.transition(s, {
                    "type": "turn-end", "slot": token["slot"], "epoch": token["epoch"], "id": token["turnId"]}))
                c.execute("UPDATE conductors SET status='idle', turn_id=NULL, turn_started_at=NULL, usage=? WHERE id=?",
                          (json.dumps(usage) if usage else con["usage"], con["id"]))
                switched = self.compaction(c, con["id"], token, usage, state) if usage else None
                con = self.row(c, "SELECT * FROM conductors WHERE id=?", con["id"])
                self.event(c, con["chat_id"], "turn-ended", {"conductor": self.public_conductor(con), "turnId": token["turnId"],
                                                             "commands": len(applied), "switched": switched})
                return {"applied": applied, "switched": switched}
        except StaleOwner as error:
            self.rejected(token, error, "turn-result")
            raise

    def apply_command(self, c, token, con, command):
        kind, request_id = command.get("type"), command.get("requestId")
        _, req = self.fence(c, token, request_id)
        now = self.clock()
        if kind == 'register-required':
            return self.responsibility.register(c, req['id'], command.get('tasks'), 'turn:' + token['turnId'])
        if kind == 'ack-instruction':
            self.responsibility.acknowledge(c, req['id'], command.get('instructionId'), command.get('taskIds'), command.get('evidence'))
            return {'type': kind}
        if kind == "split":
            require(req["status"] in ("accepted", "planning"), "intent_plan_invalid", "Split only an unstarted request")
            require(not self.request_delegations(c, req["id"]), "intent_plan_invalid", "Do not split work already delegated")
            plan = intents.validate(command.get("intents"))
            if conductor_pool.enabled(self.policy(c, con['chat_id'])):
                for item in plan:
                    item['spec']['area'] = self.pool.area(item['spec'].get('area') or self.pool.get_area(c, 'request', req['id']))
                for item in plan:
                    area = item['spec']['area']
                    rule = self.pool.rule(c, 'worker', area)
                    same_domain = sum(other['spec']['area']['domainId'] == area['domainId'] for other in plan)
                    same_child = sum(other['spec']['area']['subdomainId'] == area['subdomainId'] for other in plan)
                    if (rule['domainLimit'] == 1 and same_domain > 1) or (rule['subdomainLimit'] == 1 and same_child > 1):
                        item['parallelCandidate'] = False
                        item['admissionReason'] = 'employment-policy'

            children = {}
            for item in plan:
                child = self.create_request(c, con["chat_id"], item["title"], {"accepted_at": req["received_at"], "areaSource": "turn:" + token["turnId"]}, area=self.pool.area(item["spec"].get("area") or self.pool.get_area(c, "request", req["id"])) if conductor_pool.enabled(self.policy(c, con["chat_id"])) else None, parent=req)
                children[item["key"]] = child
                c.execute("UPDATE requests SET parent_id=? WHERE id=?", (req["id"], child["id"]))
            for item in plan:
                child = children[item["key"]]
                item = {**item, "requestId": child["id"], "dependencies": [children[k]["id"] for k in item["dependsOn"]]}
                c.execute("INSERT INTO request_intents VALUES(?,?,?)", (child["id"], req["id"], json.dumps(item, ensure_ascii=False)))
                self.event(c, con["chat_id"], "request-status", {"request": self.public_request(self.row(c, "SELECT * FROM requests WHERE id=?", child["id"]))})
                self.deliver_user(c, child, {"text": item["spec"]["goal"], "intent": item}, "intent:" + child["id"])
            payload = {"requestId": req["id"], "count": len(plan), "intents": [self.public_request(self.row(c, "SELECT * FROM requests WHERE id=?", ch["id"]))["intent"] for ch in children.values()]}
            c.execute("INSERT INTO intent_plans VALUES(?,?)", (req["id"], json.dumps(payload, ensure_ascii=False)))
            self.set_request(c, req, "decomposed")
            self.event(c, con["chat_id"], "intent-plan", payload)
            return {"type": kind, **payload}
        if kind == "reply":
            final = bool(command.get("final"))
            if final:
                require(req["status"] not in ("completed", "cancelled"), "request_terminal", "Request already ended")
                open_count = c.execute("SELECT COUNT(*) FROM delegations WHERE request_id=? AND status NOT IN (?,?,?)",
                                       (req["id"], *DELEGATION_TERMINAL)).fetchone()[0]
                open_count += c.execute("SELECT COUNT(*) FROM requests WHERE parent_id=? AND status NOT IN ('completed','cancelled')", (req["id"],)).fetchone()[0]
                require(open_count == 0, "delegations_open", "Final answer waits for open delegations")
                require(c.execute("SELECT COUNT(*) FROM questions WHERE request_id=? AND state='pending'", (req['id'],)).fetchone()[0] == 0,
                        'questions_open', 'Final answer waits for pending Human questions')
                self.responsibility.reconcile(c)
                require(not self.responsibility.blockers(c, req['id']), 'responsibility_open', 'Final answer waits for required work, instructions and exact completion receipts')
                for delegation in c.execute('SELECT * FROM delegations WHERE request_id=?', (req['id'],)):
                    spec = json.loads(delegation['spec'])
                    if spec.get('taskMode') == 'work-verification':
                        result = json.loads(delegation['result'] or '{}')
                        observed = self.roles.task(c, dict(delegation))
                        require(result.get('verificationState') == 'pass' and observed['verificationState'] == 'pass' and result.get('binding') == observed['binding']
                                or result.get('verificationState') == 'skipped-by-human' and (result.get('binding') or {}).get('humanSkip'),
                                'verification_open', 'Final answer waits for an exact validated Verification receipt or recorded Human skip')
            if req["first_response_at"] is None:
                c.execute("UPDATE requests SET first_response_at=? WHERE id=?", (now, req["id"]))
            self.event(c, con["chat_id"], "conductor-reply", {
                "requestId": req["id"], "conductorId": con["id"], "messageKey": command.get("messageKey") or ident("msg"),
                "text": command.get("text", ""), "chunk": False, "final": final, "epoch": token["epoch"],
                "slot": token["slot"]})
            if final and req["status"] != "cancelling":
                self.set_request(c, self.row(c, "SELECT * FROM requests WHERE id=?", req["id"]), "completed", final_at=now)
                self.notify_parent(c, req)
            return {"type": kind, "requestId": req["id"], "final": final}
        if kind == "delegate":
            require(req["status"] in ("planning", "delegated", "awaiting-synthesis", "accepted"), "request_terminal",
                    "Delegation needs an open request")
            spec = command.get("spec") or {}
            owned = self.row(c, "SELECT payload FROM request_intents WHERE request_id=?", req["id"])
            if owned:
                # The child conductor cannot widen the committed write/resource/isolation plan.
                intent = json.loads(owned["payload"])
                spec = {**spec, **intent["spec"], "dependencies": intent["dependencies"]}

            require(isinstance(command.get("title"), str) and command["title"].strip(), "delegation_invalid", "Title required")
            policy = self.policy(c, con["chat_id"])
            if policy.get('workIsolation'):
                require((spec.get('workspace') or {}).get('mode') in ('code', 'read-only'), 'task_workspace_required', 'Work isolation requires code or read-only workspace')
            area = None
            if conductor_pool.enabled(policy):
                area = self.pool.area(spec.get('area') or self.pool.get_area(c, 'request', req['id']))
                spec['area'] = area
            if 'writeScope' not in spec:
                declared = self.pool.area(spec.get('scopeBySubdomain')) if spec.get('scopeBySubdomain') else None
                require(declared and declared.get('writeScope') is not None, 'scope_required', 'Declare write paths or a child area with a recorded path scope')
                require(area is None or declared['subdomainId'] == area['subdomainId'], 'area_mismatch', 'Declared child scope must match performer responsibility')
                spec['writeScope'] = declared['writeScope']
            spec = self.roles.freeze(c, req, spec, area, policy)
            intents.scope_paths(spec['writeScope'])
            self.close_questions(c, req['id'], 'resolved-by-declaration', kind='declaration')
            did, aid = ident("del"), ident("att")
            status = "awaiting-approval" if policy["approvalPolicy"] == "required" else "ready"
            c.execute("INSERT INTO delegations(id, request_id, chat_id, conductor_id, title, spec, status, version, attempt_id,"
                      " attempt_count, max_attempts, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (did, req["id"], con["chat_id"], con["id"], command["title"], json.dumps(spec, ensure_ascii=False),
                       status, 1, aid, 1, int(policy.get("maxAttempts", 2)), now, now))
            c.execute("INSERT INTO attempts(id, delegation_id, number, status, backend, created_at, updated_at)"
                      " VALUES(?,?,?,?,?,?,?)", (aid, did, 1, "pending", policy["executor"], now, now))
            if command.get('obligationId'):
                self.responsibility.bind(c, req['id'], command['obligationId'], did)
            elif policy['executor'] == 'managed':
                registered = self.responsibility.register(c, req['id'], [{'key': 'delegation:' + did, 'title': command['title'], 'spec': spec}], 'turn:' + token['turnId'])
                automatic_id = 'required-' + digest([req['id'], 'delegation:' + did])[:24]
                automatic = next(t for t in registered['tasks'] if t['id'] == automatic_id)
                self.responsibility.bind(c, req['id'], automatic['id'], did)
            if area:
                self.pool.set_area(c, 'delegation', did, area)
            self.pool.decide(c, req['id'], 'scope', {'delegationId': did, 'writeScope': spec['writeScope'], 'area': area}, 'turn:' + token['turnId'], 'declared', did)
            d = self.row(c, "SELECT * FROM delegations WHERE id=?", did)
            self.event(c, con["chat_id"], "delegation-created", {"delegation": self.public_delegation(c, d)})
            if req["status"] in ("planning", "accepted", "awaiting-synthesis"):
                self.set_request(c, req, "delegated")
            return {"type": kind, "requestId": req["id"], "delegationId": did, "status": status}
        if kind == "ask":
            qid = self.question(c, req['id'], con['id'], 'conductor', command.get('text', ''), 'turn:' + token['turnId'] + ':' + digest(command), details=command)
            self.event(c, con["chat_id"], "conductor-question", {"requestId": req["id"], "conductorId": con["id"],
                                                                 "text": command.get("text", ""), "questionId": qid})
            return {"type": kind, "requestId": req["id"]}
        raise ContractError("command_unknown", "Conductor command must be reply, delegate or ask")

    def compaction(self, c, conductor_id, token, usage, state):
        """Existing handoff reducer: observe at the turn boundary; a caught-up standby takes ownership."""
        now = iso(self.clock())
        observation = {"availability": "observed", "sessionId": state["sessions"][state["owner"]], "turnId": token["turnId"],
                       "observedAt": now, "usedTokens": usage.get("usedTokens"),
                       "contextWindowTokens": usage.get("contextWindowTokens")}
        state = self.handoff_update(c, conductor_id, lambda s: handoff.transition(s, {
            "type": "observe", "slot": s["owner"], "epoch": s["epoch"], "observation": observation,
            "turnId": token["turnId"], "now": now}))
        prep = state.get("preparation")
        if not prep or prep["status"] not in ("requested", "ready"):
            return None
        checkpoint = self.checkpoint(c, conductor_id, state)
        c.execute("UPDATE conductors SET checkpoint=? WHERE id=?", (json.dumps(checkpoint, ensure_ascii=False), conductor_id))
        state = self.handoff_update(c, conductor_id, lambda s: handoff.transition(s, {
            "type": "ready", "slot": prep["slot"], "epoch": prep["epoch"], "cursor": s["cursor"],
            "references": s["references"], "receipt": "checkpoint:" + checkpoint["hash"]}))
        before = state["owner"]
        try:
            state = self.handoff_update(c, conductor_id, lambda s: handoff.transition(s, {
                "type": "switch", "slot": s["owner"], "epoch": s["epoch"], "now": now}))
        except ContractError:
            return None  # Below the switch target: the prepared standby waits for a later boundary.
        for question in list(c.execute("SELECT * FROM questions WHERE conductor_id=? AND state='pending'", (conductor_id,))):
            c.execute('UPDATE questions SET slot=?,epoch=? WHERE id=?', (state['owner'], state['epoch'], question['id']))
            self.event(c, self.row(c, 'SELECT chat_id FROM conductors WHERE id=?', conductor_id)['chat_id'], 'question-state',
                       {'question': self.row(c, 'SELECT * FROM questions WHERE id=?', question['id'])})
        self.event(c, self.row(c, "SELECT chat_id FROM conductors WHERE id=?", conductor_id)["chat_id"], "owner-changed", {
            "conductorId": conductor_id, "fromSlot": before, "toSlot": state["owner"], "epoch": state["epoch"],
            "checkpoint": checkpoint["hash"], "reason": "compaction"})
        self.op(c, "compaction-switch", conductorId=conductor_id, epoch=state["epoch"])
        return {"fromSlot": before, "toSlot": state["owner"], "epoch": state["epoch"], "checkpoint": checkpoint["hash"]}

    def checkpoint(self, c, conductor_id, state):
        """Operational summary plus immutable confirmed records and question identities for the successor."""
        requests = [dict(r) for r in c.execute("SELECT * FROM requests WHERE conductor_id=? ORDER BY created_at", (conductor_id,))]
        body = {"conductorId": conductor_id, "cursor": state["cursor"], "processed": len(state["processed"]),
                "decisions": [{"requestId": r["id"], "title": r["title"], "status": r["status"], "version": r["version"]}
                              for r in requests],
                "pendingInputs": [{"mailboxId": m["id"], "kind": m["kind"], "requestId": m["request_id"]} for m in
                                  c.execute("SELECT * FROM mailbox WHERE conductor_id=? AND status IN ('queued','delivered')"
                                            " ORDER BY seq", (conductor_id,))],
                "fixedDecisions": [decision for r in requests for decision in self.pool.decisions(c, r["id"])],
                "pendingQuestions": [self.question_view(q) for q in c.execute("SELECT * FROM questions WHERE conductor_id=? AND state='pending'", (conductor_id,))],
                "openDelegations": [{"delegationId": d["id"], "requestId": d["request_id"], "status": d["status"],
                                     "attemptId": d["attempt_id"]} for d in
                                    c.execute("SELECT * FROM delegations WHERE conductor_id=? AND status NOT IN (?,?,?)",
                                              (conductor_id, *DELEGATION_TERMINAL))]}
        return {**body, "hash": digest(body)[:24]}

    # -- executor subscription ------------------------------------------------------
    def executor_handler(self, backend):
        def handle(c, event):
            d = (event["payload"].get("delegation") or {})
            row = self.row(c, "SELECT * FROM delegations WHERE id=?", d.get("id"))
            if not row:
                return None
            attempt = self.row(c, "SELECT * FROM attempts WHERE id=?", row["attempt_id"])
            if event['type'] in ('workspace-action', 'worker-answer'):
                c.execute('INSERT OR IGNORE INTO operator_effects VALUES(?,?,?)', (event['id'], json.dumps(event), 'pending'))
                return None
            if event["type"] == "delegation-cancel-requested":
                if attempt["status"] in ATTEMPT_TERMINAL:
                    return None
                if attempt["status"] == "pending":
                    # Never started: no external effect exists, so cancellation completes here.
                    c.execute("UPDATE attempts SET status='cancelled', ended_at=?, updated_at=? WHERE id=?",
                              (self.clock(), self.clock(), attempt["id"]))
                    row = self.set_delegation(c, row, "cancelled")
                    self.event(c, row["chat_id"], "delegation-cancelled", {"delegation": self.public_delegation(c, row)})
                    self.settle_request(c, row["request_id"])
                    return None
                return lambda: backend.cancel(self.attempt_context(attempt["id"]))
            if row["status"] not in ("ready", "dispatched") or attempt["status"] != "pending":
                return None
            reason = self.admission(c, row)
            if reason:
                c.execute("INSERT OR REPLACE INTO attempt_waits VALUES(?,?)", (attempt["id"], reason))
                self.event(c, row["chat_id"], "delegation-waiting", {"delegation": self.public_delegation(c, row), "reason": reason})
                return None
            if conductor_pool.enabled(self.policy(c, row['chat_id'])):
                worker, reason = self.pool.reserve_worker(c, row, conductor_pool.signature(self.policy(c, row['chat_id']), 'worker', json.loads(row['spec'])))
                if reason:
                    c.execute('INSERT OR REPLACE INTO attempt_waits VALUES(?,?)', (attempt['id'], reason))
                    self.event(c, row['chat_id'], 'delegation-waiting', {'delegation': self.public_delegation(c, row), 'reason': reason})
                    return None
            c.execute("DELETE FROM attempt_waits WHERE attempt_id=?", (attempt["id"],))
            spec = json.loads(row['spec'])
            if spec.get('taskMode') == 'work-verification':
                verifier, reason = self.roles.reserve_verifier(c, row, spec, worker)
                if reason:
                    self.pool.release_worker(c, row['attempt_id'])
                    c.execute('DELETE FROM attempt_workers WHERE attempt_id=?', (row['attempt_id'],))
                    c.execute('INSERT OR REPLACE INTO attempt_waits VALUES(?,?)', (row['attempt_id'], reason))
                    self.event(c, row['chat_id'], 'delegation-waiting', {'delegation': self.public_delegation(c, row), 'reason': reason})
                    return None
            c.execute("UPDATE attempts SET status='starting', updated_at=? WHERE id=?", (self.clock(), attempt["id"]))
            if row["status"] == "ready":
                self.set_delegation(c, row, "dispatched")
            return lambda: backend.start(self.attempt_context(attempt["id"]))
        return handle

    def notify_parent(self, c, req):
        if not req.get("parent_id"):
            return
        parent = self.row(c, "SELECT * FROM requests WHERE id=?", req["parent_id"])
        if parent["status"] == "decomposed":
            self.enqueue(c, parent["conductor_id"], parent["id"], "intent-result", {"request": self.public_request(req)}, "intent-result:" + req["id"] + ":" + str(req["version"]))

    def admission(self, c, row):
        spec = json.loads(row["spec"])
        for dep in spec.get("dependencies", []):
            state = self.row(c, "SELECT status FROM requests WHERE id=?", dep)
            failed = c.execute("SELECT COUNT(*) FROM delegations WHERE request_id=? AND status IN ('failed','cancelled')", (dep,)).fetchone()[0]
            if failed:
                return 'dependency-failed:' + dep
            if not state or state["status"] != "completed":
                return "dependency:" + dep
        if conductor_pool.enabled(self.policy(c, row['chat_id'])):
            area = self.pool.get_area(c, 'delegation', row['id'])
            if not area:
                return 'area-required'
            if not c.execute('SELECT 1 FROM attempt_workers WHERE attempt_id=?', (row['attempt_id'],)).fetchone():
                reason = self.pool.room(c, self.roles.pool_role(spec.get('workProfile', 'work')), area)
                if reason:
                    return reason
        active = c.execute("SELECT d.* FROM delegations d JOIN attempts a ON a.id=d.attempt_id WHERE a.status IN ('starting','running') AND d.id!=?", (row["id"],))
        for other in active:
            # Fake legacy tasks have no filesystem effects. Managed unknown scopes remain exclusive.
            if self.policy(c, row["chat_id"])["executor"] == 'fake' and not spec and not json.loads(other["spec"]):
                continue
            if intents.conflict(spec, json.loads(other["spec"])):
                return "resource:" + other["id"]
        return None

    def schedule_waiting(self):
        with self.tx() as c:
            count = 0
            for wait in list(c.execute("SELECT * FROM attempt_waits")):
                row = self.row(c, "SELECT * FROM delegations WHERE attempt_id=?", wait["attempt_id"])
                if not row or row["status"] in DELEGATION_TERMINAL:
                    c.execute("DELETE FROM attempt_waits WHERE attempt_id=?", (wait["attempt_id"],))
                elif not self.admission(c, row):
                    c.execute("DELETE FROM attempt_waits WHERE attempt_id=?", (wait["attempt_id"],))
                    self.event(c, row["chat_id"], "delegation-unblocked", {"delegation": self.public_delegation(c, row)})
                    count += 1
            return count

    def attempt_context(self, attempt_id):
        c = self.connection()
        a = self.row(c, "SELECT * FROM attempts WHERE id=?", attempt_id)
        d = self.row(c, "SELECT * FROM delegations WHERE id=?", a["delegation_id"])
        return {"attemptId": a["id"], "number": a["number"], "status": a["status"], "delegationId": d["id"],
                "requestId": d["request_id"], "chatId": d["chat_id"], "title": d["title"], "spec": json.loads(d["spec"]), "verifier": (self.row(c, "SELECT agent_id FROM attempt_verifiers WHERE attempt_id=?", attempt_id) or {}).get("agent_id"),
                "worker": self.row(c, 'SELECT p.* FROM pool_members p JOIN attempt_workers w ON w.worker_id=p.id WHERE w.attempt_id=?', a['id']),
                "cancelRequested": bool(d["cancel_requested"]), "external": json.loads(a["external"] or "null"), "policy": self.policy(c, d["chat_id"])}

    def record_external(self, attempt_id, external):
        with self.tx() as c:
            c.execute("UPDATE attempts SET external=?, updated_at=? WHERE id=?",
                      (json.dumps(external, ensure_ascii=False), self.clock(), attempt_id))

    def record_observation(self, attempt_id, reason):
        with self.tx() as c:
            a = self.row(c, "SELECT * FROM attempts WHERE id=?", attempt_id)
            external = json.loads(a['external'] or '{}')
            if external.get('observation') == reason:
                return
            external['observation'] = reason
            c.execute('UPDATE attempts SET external=? WHERE id=?', (json.dumps(external), attempt_id))
            d = self.row(c, 'SELECT * FROM delegations WHERE id=?', a['delegation_id'])
            self.event(c, d['chat_id'], 'worker-observation', {'delegation': self.public_delegation(c, d), 'reason': reason})

    def record_workflow(self, attempt_id, observation):
        with self.tx() as c:
            a = self.row(c, 'SELECT * FROM attempts WHERE id=?', attempt_id)
            d = self.row(c, 'SELECT * FROM delegations WHERE id=?', a['delegation_id'])
            if d['attempt_id'] != attempt_id:
                return
            old = self.row(c, 'SELECT payload FROM workflow_observations WHERE attempt_id=?', attempt_id)
            previous = json.loads(old['payload']) if old else {}
            value = {k: observation.get(k) for k in ('verificationState', 'binding', 'activeRole', 'activeStatus', 'implementationState')}
            if previous.get('verificationState') == 'pass' and value.get('verificationState') == 'pass':
                before, after = previous.get('binding') or {}, value.get('binding') or {}
                if any(before.get(k) != after.get(k) for k in ('workRunId', 'resultRevision')) and before.get('verificationRunId') == after.get('verificationRunId'):
                    value['verificationState'] = 'revision-waiting'
            if value == previous:
                return
            c.execute('INSERT OR REPLACE INTO workflow_observations VALUES(?,?)', (attempt_id, json.dumps(value)))
            self.event(c, d['chat_id'], 'role-pools-state', self.roles.projection(c))

    def record_workspace(self, attempt_id, workspace):
        with self.tx() as c:
            a = self.row(c, "SELECT * FROM attempts WHERE id=?", attempt_id)
            external = json.loads(a["external"] or '{}')
            if external.get('workspace') == workspace:
                return
            external['workspace'] = workspace
            c.execute("UPDATE attempts SET external=? WHERE id=?", (json.dumps(external), attempt_id))
            d = self.row(c, "SELECT * FROM delegations WHERE id=?", a['delegation_id'])
            self.event(c, d['chat_id'], 'workspace-status', {'delegation': self.public_delegation(c, d)})

    # -- UI projection subscription ---------------------------------------------------
    def ui_handler(self, c, event):
        p, kind, chat = event["payload"], event["type"], event["chatId"]
        if chat is None:
            return None
        def state(key, kind_, payload):
            cur = c.execute("INSERT INTO ui_state(key, chat_id, kind, payload, version, updated_at) VALUES(?,?,?,?,?,?)"
                            " ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, version=excluded.version,"
                            " updated_at=excluded.updated_at WHERE excluded.version > ui_state.version",
                            (key, chat, kind_, json.dumps(payload, ensure_ascii=False), event["seq"], self.clock()))
            if cur.rowcount:  # An older redelivered event never regresses the canonical projection.
                feed("state", key, payload)
        def feed(kind_, key, payload):
            c.execute("INSERT INTO ui_feed(chat_id, kind, key, version, payload, event_seq, event_at, applied_at)"
                      " VALUES(?,?,?,?,?,?,?,?)", (chat, kind_, key, event["seq"], json.dumps(payload, ensure_ascii=False),
                                                   event["seq"], event["createdAt"], self.clock()))
        def chat_entry(role, text, **extra):
            feed("chat", "chat:" + event["id"], {"role": role, "text": text, "eventType": kind,
                                                 "at": event["createdAt"], **extra})
        if kind == 'role-pool-control-result':
            state('role-control:' + p['commandId'], 'role-control', p)
        elif kind == 'role-pools-state':
            state('role-pools', 'role-pools', p)
        elif kind == 'responsibility-state':
            state('responsibility:' + p['requestId'], 'responsibility', p)
        elif kind == "input-accepted":
            if p["class"] == "conversation":
                chat_entry("user", p.get("text"), clientMessageId=p.get("clientMessageId"), inputId=p["inputId"],
                           acceptedAt=p["acceptedAt"], sentAt=p.get("sentAt"))
            state("input:" + p["inputId"], "input", {"inputId": p["inputId"], "class": p["class"], "status": "accepted",
                                                     "clientMessageId": p.get("clientMessageId"),
                                                     "commandId": p.get("commandId"), "acceptedAt": p["acceptedAt"]})
        elif kind in ("input-routed", "input-rejected", "input-resolved", "input-quarantined"):
            status = {"input-routed": "routed", "input-rejected": "rejected", "input-resolved": "resolved",
                      "input-quarantined": "quarantined"}[kind]
            old = self.row(c, "SELECT payload FROM ui_state WHERE key=?", "input:" + p["inputId"])
            state("input:" + p["inputId"], "input", {**(json.loads(old["payload"]) if old else {"inputId": p["inputId"]}),
                                                     "status": status, **{k: v for k, v in p.items() if k != "text"}})
            if kind == "input-rejected":
                chat_entry("notice", p.get("message"), code=p.get("code"), inputId=p["inputId"])
        elif kind == 'question-state':
            state('question:' + p['question']['id'], 'question', self.question_view(p['question']))
        elif kind == 'fixed-decisions':
            state('decisions:' + p['requestId'], 'decisions', p)
        elif kind == 'area-question':
            state('input:' + p['inputId'], 'input', {'inputId': p['inputId'], 'status': 'held', 'waitReason': 'area-required', 'catalog': p['catalog']})
            chat_entry('question', p['question'], inputId=p['inputId'], question='area', catalog=p['catalog'])
        elif kind == "clarification-needed":
            chat_entry("question", None, inputId=p["inputId"], clientMessageId=p.get("clientMessageId"),
                       candidates=p["candidates"], question="relation")
        elif kind == "intent-plan":
            state("plan:" + p["requestId"], "plan", p)
            chat_entry("plan", None, **p)
        elif kind in ("request-created", "request-status", "request-cancelled"):
            state("request:" + p["request"]["id"], "request", p["request"])
            if kind == "request-cancelled":
                chat_entry("status", None, requestId=p["request"]["id"], status="cancelled")
        elif kind in ("conductor-created", "instance-waiting", "turn-started", "turn-ended"):
            state("conductor:" + p["conductor"]["id"], "conductor", {**p["conductor"], "lastTurnId": p.get("turnId")})
        elif kind == "owner-changed":
            chat_entry("status", None, requestId=p.get("requestId"), conductorId=p.get("conductorId") or p.get("toConductorId"),
                       status="owner-changed", detail={k: v for k, v in p.items()})
        elif kind == "conductor-reply":
            chat_entry("assistant", p["text"], requestId=p["requestId"], conductorId=p["conductorId"],
                       messageKey=p["messageKey"], chunk=p["chunk"], final=p["final"])
        elif kind == "conductor-question":
            chat_entry("question", p["text"], requestId=p["requestId"], conductorId=p["conductorId"], question="conductor", questionId=p.get("questionId"))
        elif kind in ("worker-observation", "workspace-status", "delegation-created", "delegation-waiting", "delegation-unblocked", "delegation-approved", "attempt-started", "attempt-retry",
                      "delegation-cancel-requested", "delegation-completed", "delegation-failed",
                      "delegation-cancelled", "worker-question"):
            d = p["delegation"]
            old = self.row(c, "SELECT payload FROM ui_state WHERE key=?", "worker:" + d["id"])
            previous = json.loads(old["payload"]) if old else {}
            wait = {"awaiting-approval": "approval", "ready": "dispatch", "dispatched": "worker-start",
                    "cancel-requested": "cancellation"}.get(d["status"])
            if kind == "worker-question":
                wait = "question"
                chat_entry("question", (p.get("question") or {}).get("text"), requestId=d["requestId"], delegationId=d["id"], conductorId=d["conductorId"], question="worker", detail=p.get("question"))
            if kind in ("delegation-waiting", "worker-observation"):
                wait = p["reason"]
            state("worker:" + d["id"], "worker", {**d, "progress": previous.get("progress") if kind != "attempt-retry" else None,
                                                  "waitReason": wait, "lastEvent": kind, "lastUpdateAt": event["createdAt"]})
            if kind in ("delegation-created", "delegation-approved", "delegation-completed", "delegation-failed",
                        "delegation-cancelled", "attempt-retry"):
                chat_entry("status", None, requestId=d["requestId"], delegationId=d["id"], status=d["status"],
                           title=d["title"], version=d["version"], attemptCount=d["attemptCount"])
        elif kind == "attempt-progress":
            old = self.row(c, "SELECT payload FROM ui_state WHERE key=?", "worker:" + p["delegationId"])
            if old:
                current = json.loads(old["payload"])
                if current.get("attemptId") == p["attemptId"]:
                    state("worker:" + p["delegationId"], "worker", {**current, "progress": p["progress"], "waitReason": None,
                                                                    "lastEvent": kind, "lastUpdateAt": event["createdAt"]})
        elif kind in ("stale-owner-rejected", "command-rejected", "event-quarantined", "attempt-late-event",
                      "control-rejected", "turn-abandoned"):
            feed("ops", "ops:" + event["id"], {"eventType": kind, **p, "at": event["createdAt"]})
            if kind == "control-rejected":
                chat_entry("notice", None, code=p["reason"], commandId=p.get("commandId"), action=p.get("action"),
                           detail={k: p.get(k) for k in ("status", "version")})
        if kind in ('request-created', 'request-status', 'delegation-created', 'delegation-waiting', 'delegation-unblocked', 'attempt-started', 'delegation-completed', 'delegation-failed', 'delegation-cancelled', 'worker-question'):
            state('role-pools', 'role-pools', self.roles.projection(c))
        return None

    # -- reads: snapshot, replay, metrics ------------------------------------------------
    def ui_snapshot(self, chat_id):
        c = self.connection()
        c.execute("BEGIN")
        try:
            cursor = c.execute("SELECT COALESCE(MAX(id), 0) FROM ui_feed WHERE chat_id=?", (chat_id,)).fetchone()[0]
            rows = [dict(r) for r in c.execute("SELECT key, kind, payload, version FROM ui_state WHERE chat_id=?", (chat_id,))]
            chat = [self.feed_row(dict(r)) for r in c.execute("SELECT * FROM ui_feed WHERE chat_id=? AND kind='chat' AND id<=?"
                                                             " ORDER BY id", (chat_id, cursor))]
            queue = self.queue_depths(c)
            logical = {'id': 'logical-conductor', 'instanceCount': c.execute('SELECT COUNT(*) FROM conductors').fetchone()[0]}
            role_pools = self.roles.projection(c)
            employment = self.pool.configuration(c)
            members = [{'id': m['id'], 'role': m['role'], 'area': json.loads(m['area']), 'state': m['state'], 'lastUsedAt': m['last_used']}
                       for m in c.execute('SELECT * FROM pool_members ORDER BY role,id')]
        finally:
            c.execute("COMMIT")
        return {"rolePools": role_pools, "logicalConductor": logical, "employment": employment, "poolMembers": members, "schemaVersion": SCHEMA_VERSION, "kind": "conductor-queue-snapshot", "chatId": chat_id, "cursor": cursor,
                "state": [{"key": r["key"], "kind": r["kind"], "version": r["version"], "payload": json.loads(r["payload"])}
                          for r in rows], "chat": chat, "queue": queue, "observedAt": iso(self.clock())}

    def ui_board(self):
        """Project-wide projection for the control center: every chat's conductors, requests and workers."""
        c = self.connection()
        c.execute("BEGIN")
        try:
            cursor = c.execute("SELECT COALESCE(MAX(id), 0) FROM ui_feed").fetchone()[0]
            rows = [dict(r) for r in c.execute("SELECT key, kind, payload, version FROM ui_state WHERE kind != 'input'")]
            queue = self.queue_depths(c)
            logical = {'id': 'logical-conductor', 'instanceCount': c.execute('SELECT COUNT(*) FROM conductors').fetchone()[0]}
            role_pools = self.roles.projection(c)
            employment = self.pool.configuration(c)
            members = [{'id': m['id'], 'role': m['role'], 'area': json.loads(m['area']), 'state': m['state'], 'lastUsedAt': m['last_used']}
                       for m in c.execute('SELECT * FROM pool_members ORDER BY role,id')]
        finally:
            c.execute("COMMIT")
        return {"rolePools": role_pools, "logicalConductor": logical, "employment": employment, "poolMembers": members, "schemaVersion": SCHEMA_VERSION, "kind": "conductor-queue-board", "cursor": cursor,
                "state": [{"key": r["key"], "kind": r["kind"], "version": r["version"], "payload": json.loads(r["payload"])}
                          for r in rows], "chat": [], "queue": queue, "observedAt": iso(self.clock())}

    def ui_replay(self, chat_id, after, *, coalesce=True):
        """Rows after a cursor; repeated state of one key collapses to its latest version."""
        c = self.connection()
        rows = [self.feed_row(dict(r)) for r in c.execute("SELECT * FROM ui_feed WHERE chat_id=? AND id>? ORDER BY id",
                                                         (chat_id, after))]
        if coalesce:
            last = {}
            for r in rows:
                if r["kind"] == "state" and r["version"] >= last.get(r["key"], (-1, 0))[0]:
                    last[r["key"]] = (r["version"], r["id"])
            rows = [r for r in rows if r["kind"] != "state" or last[r["key"]][1] == r["id"]]
        cursor = max([after] + [r["id"] for r in rows])
        return {"schemaVersion": SCHEMA_VERSION, "kind": "conductor-queue-replay", "chatId": chat_id, "after": after,
                "cursor": cursor, "entries": rows}

    def feed_since(self, after):
        c = self.connection()
        return [self.feed_row(dict(r)) for r in c.execute("SELECT * FROM ui_feed WHERE id>? ORDER BY id", (after,))]

    @staticmethod
    def feed_row(r):
        return {"id": r["id"], "chatId": r["chat_id"], "kind": r["kind"], "key": r["key"], "version": r["version"],
                "payload": json.loads(r["payload"]), "eventSeq": r["event_seq"], "eventAt": r["event_at"],
                "appliedAt": r["applied_at"]}

    def queue_depths(self, c):
        now = self.clock()
        result = {}
        for cls in CLASSES:
            count, oldest = c.execute("SELECT COUNT(*), MIN(accepted_at) FROM inputs WHERE status='pending' AND class=?",
                                      (cls,)).fetchone()
            result[cls] = {"depth": count, "oldestAgeMs": round((now - oldest) * 1000) if oldest else None}
        held = c.execute("SELECT COUNT(*) FROM inputs WHERE status='held'").fetchone()[0]
        mailbox = c.execute("SELECT COUNT(*), MIN(enqueued_at) FROM mailbox WHERE status='queued'").fetchone()
        result["held"] = {"depth": held}
        result["mailbox"] = {"depth": mailbox[0], "oldestAgeMs": round((now - mailbox[1]) * 1000) if mailbox[1] else None}
        result["deliveries"] = {name: c.execute("SELECT COUNT(*) FROM deliveries WHERE subscription=? AND status='ready'",
                                                (name,)).fetchone()[0] for name in SUBSCRIPTIONS}
        return result

    def metrics(self, chat_id=None):
        """Measured latencies in milliseconds from recorded timestamps; nothing is estimated."""
        c = self.connection()
        where, args = ("WHERE chat_id=?", (chat_id,)) if chat_id else ("", ())
        def summary(values):
            values = sorted(v * 1000 for v in values if v is not None and v >= 0)
            if not values:
                return {"count": 0}
            pick = lambda q: round(values[min(len(values) - 1, int(q * (len(values) - 1) + 0.5))], 2)
            return {"count": len(values), "p50": pick(0.5), "p95": pick(0.95), "max": round(values[-1], 2)}
        inputs = [dict(r) for r in c.execute("SELECT class, sent_at, accepted_at, routed_at FROM inputs " + where, args)]
        requests = [dict(r) for r in c.execute("SELECT received_at, first_response_at, final_at FROM requests " + where, args)]
        mailbox = [dict(r) for r in c.execute("SELECT kind, enqueued_at, delivered_at FROM mailbox WHERE delivered_at IS NOT NULL")]
        ui = [dict(r) for r in c.execute("SELECT event_at, applied_at FROM ui_feed " + where, args)]
        return {"schemaVersion": SCHEMA_VERSION, "kind": "conductor-queue-metrics", "unit": "ms",
                "accept": summary([i["accepted_at"] - i["sent_at"] for i in inputs if i["sent_at"]]),
                "routeDwell": {cls: summary([i["routed_at"] - i["accepted_at"] for i in inputs if i["class"] == cls
                                             and i["routed_at"]]) for cls in CLASSES},
                "conductorWait": summary([m["delivered_at"] - m["enqueued_at"] for m in mailbox]),
                "firstResponse": summary([r["first_response_at"] - r["received_at"] for r in requests if r["first_response_at"]]),
                "finalResponse": summary([r["final_at"] - r["received_at"] for r in requests if r["final_at"]]),
                "uiProjection": summary([u["applied_at"] - u["event_at"] for u in ui]),
                # Recovery and fencing observations (identifiers/codes only), counted per kind.
                "observations": {r[0]: r[1] for r in c.execute("SELECT kind, COUNT(*) FROM ops GROUP BY kind")},
                "queue": self.queue_depths(c), "observedAt": iso(self.clock())}

    # -- recovery -------------------------------------------------------------------------
    def abandon_turn(self, c, con, reason, *, count_failure):
        """Return a turn's undelivered work to the queue; an input failing every turn is quarantined."""
        if count_failure:
            c.execute("UPDATE mailbox SET failures=failures+1 WHERE turn_id=? AND status='delivered'", (con["turn_id"],))
            for item in [dict(r) for r in c.execute("SELECT * FROM mailbox WHERE turn_id=? AND status='delivered' AND failures>=?",
                                                    (con["turn_id"], POISON_ATTEMPTS))]:
                c.execute("UPDATE mailbox SET status='quarantined' WHERE id=?", (item["id"],))
                self.event(c, con["chat_id"], "event-quarantined", {"subscription": "conductor-turn", "mailboxId": item["id"],
                                                                    "eventType": item["kind"], "error": reason},
                           key="quarantine:mailbox:" + item["id"])
        c.execute("UPDATE mailbox SET status='queued', turn_id=NULL, delivered_at=NULL WHERE turn_id=? AND status='delivered'",
                  (con["turn_id"],))
        self.handoff_update(c, con["id"], lambda s, t=con["turn_id"]: handoff.transition(
            {**s, "tools": []}, {"type": "turn-end", "slot": s["owner"], "epoch": s["epoch"], "id": t})
            if s.get("activeTurn") == t else s)
        c.execute("UPDATE conductors SET status='idle', turn_id=NULL, turn_started_at=NULL WHERE id=?", (con["id"],))
        self.event(c, con["chat_id"], "turn-abandoned", {"conductorId": con["id"], "turnId": con["turn_id"], "reason": reason})
        self.op(c, "turn-abandoned", conductorId=con["id"], reason=reason)

    def fail_turn(self, token, reason):
        """The driver failed: the turn's inputs return to the queue unless they keep failing."""
        with self.tx() as c:
            con = self.row(c, "SELECT * FROM conductors WHERE id=?", token["conductorId"])
            if con and con["turn_id"] == token["turnId"]:
                self.abandon_turn(c, con, reason, count_failure=True)

    def recover(self):
        """After a runtime restart: requeue abandoned turns, report attempts whose start/outcome is uncertain."""
        with self.tx() as c:
            c.execute("UPDATE operator_effects SET status='pending' WHERE status IN ('running','failed')")
            abandoned = [dict(r) for r in c.execute("SELECT * FROM conductors WHERE status='busy'")]
            for con in abandoned:
                self.abandon_turn(c, con, "runtime-restart", count_failure=False)
            answers = {}
            for effect in c.execute("SELECT payload FROM operator_effects WHERE status='pending'"):
                event = json.loads(effect['payload'])
                if event['type'] == 'worker-answer':
                    delegation = event['payload']['delegation']
                    answers[delegation['attemptId']] = (delegation.get('external') or {}).get('runId')
            uncertain = []
            for attempt in c.execute("SELECT a.* FROM attempts a JOIN delegations d ON d.attempt_id=a.id WHERE a.status IN ('starting','running') AND d.status!='awaiting-answer'"):
                external = json.loads(attempt['external'] or '{}')
                if attempt['id'] in answers and external.get('runId') == answers[attempt['id']]:
                    continue  # The pending answer effect owns this paused run's continuation.
                uncertain.append(attempt['id'])
            cancels = [r[0] for r in c.execute("SELECT a.id FROM attempts a JOIN delegations d ON d.attempt_id=a.id WHERE"
                                               " d.status='cancel-requested' AND a.status IN ('starting','running')")]
        return {"abandonedTurns": [con["turn_id"] for con in abandoned], "uncertainAttempts": uncertain,
                "pendingCancels": cancels}

    # -- public shapes -----------------------------------------------------------------------
    def public_request(self, r):
        owned = self.row(self.connection(), "SELECT payload FROM request_intents WHERE request_id=?", r["id"])
        return {"processing": json.loads((self.row(self.connection(), "SELECT source FROM request_processing WHERE request_id=?", r["id"]) or {}).get("source", "null")), "logicalConductorId": "logical-conductor", "conductorInstanceId": r["conductor_id"] or None, "area": self.pool.get_area(self.connection(), "request", r["id"]), "waitReason": "employment-limit" if r["status"] == "queued-for-instance" else None, "parentId": r["parent_id"], "intent": json.loads(owned["payload"]) if owned else None,"id": r["id"], "chatId": r["chat_id"], "conductorId": r["conductor_id"], "ownerEpoch": r["owner_epoch"],
                "title": r["title"], "status": r["status"], "version": r["version"], "receivedAt": r["received_at"],
                "firstResponseAt": r["first_response_at"], "finalAt": r["final_at"], "updatedAt": r["updated_at"]}

    def public_conductor(self, r):
        state = json.loads(r["handoff"])
        return {"waitReason": (self.row(self.connection(), "SELECT reason FROM instance_waits WHERE conductor_id=?", r["id"]) or {}).get("reason"), "logicalConductorId": "logical-conductor", "instanceId": r["id"], "role": "conductor-instance", "area": self.pool.get_area(self.connection(), "conductor", r["id"]), "id": r["id"], "chatId": r["chat_id"], "ordinal": r["ordinal"], "status": r["status"],
                "slot": state["owner"], "epoch": state["epoch"], "cursor": state["cursor"],
                "turnStartedAt": r["turn_started_at"], "usage": json.loads(r["usage"] or "null"),
                "preparation": copy.deepcopy(state.get("preparation")), "updatedAt": r["updated_at"]}

    def public_delegation(self, c, d):
        a = self.row(c, "SELECT * FROM attempts WHERE id=?", d["attempt_id"])
        return {"logicalConductorId": "logical-conductor", "conductorInstanceId": d["conductor_id"], "area": self.pool.get_area(c, "delegation", d["id"]), "workerId": (self.row(c, "SELECT worker_id FROM attempt_workers WHERE attempt_id=?", d["attempt_id"]) or {}).get("worker_id"), "id": d["id"], "requestId": d["request_id"], "chatId": d["chat_id"], "conductorId": d["conductor_id"],
                "title": d["title"], "status": d["status"], "version": d["version"], "attemptId": d["attempt_id"],
                "attemptCount": d["attempt_count"], "maxAttempts": d["max_attempts"],
                "cancelRequested": bool(d["cancel_requested"]), "result": json.loads(d["result"] or "null"),
                "error": json.loads(d["error"] or "null"), "attemptStatus": a["status"] if a else None,
                "external": json.loads(a["external"] or "null") if a else None, "updatedAt": d["updated_at"]}
