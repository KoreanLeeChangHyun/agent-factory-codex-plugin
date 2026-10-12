#!/usr/bin/env python3
"""One logical conductor with physical-instance pools: durable ingress, fenced turns and UI projection."""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from execution.cli import JsonArgumentParser, add_project_argument
from storage.errors import ContractError
from storage.files import emit, error_document
from tasks import conductor_queue, conductor_runtime

DEFAULT_POLICY = {"approvalPolicy": "bypass", "reference": "development harness", "executor": "fake", "conductor": "fake"}


def build_parser():
    parser = JsonArgumentParser(prog="conductor_queue.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("responsibility", "Query required tasks, pending instructions and completion blockers"),
                       ("register-required", "Atomically register an authorized required-task manifest"),
                       ("resume-required", "Reconcile durable required tasks without launching a provider"),
                       ("role-pools", "Query canonical area role counts and exact task verification bindings"),
                       ("configure-role", "Capture an existing role model and permission setting for an area"),
                       ("processing-policy", "Set the processing policy inherited only by newly accepted requests"),
                       ("hire-role", "Hire or reuse an attributed role with captured settings; native session starts on assignment"),
                       ("enroll-worker", "Adopt an explicitly attributed idle Work session with matching settings"),
                       ("pool-config", "Configure captured domain/subdomain employment limits and idle reuse"),
                       ("subdomain", "Add an explicit child area under an existing domain"),
                       ("init", "Create a chat with its captured policy (idempotent; a different policy conflicts)"),
                       ("ingest", "Accept one conversation/control/lifecycle/progress input"),
                       ("snapshot", "UI projection snapshot with its replay cursor"),
                       ("replay", "UI projection rows after a cursor; repeated state collapses to its latest version"),
                       ("metrics", "Measured accept/route/conductor/response/UI latencies and queue depths (ms)"),
                       ("quarantined", "Poison deliveries and inputs kept for operator recovery"),
                       ("requeue", "Make one quarantined delivery ready again after a fix"),
                       ("recover", "Requeue abandoned turns and list uncertain attempts (no worker is started)"),
                       ("serve", "Leader/follower runtime with a JSON-lines stdin command channel and stdout feed"),
                       ("demo", "Run a development scenario with the fake conductor and workers; prints the result")):
        p = commands.add_parser(name, help=text)
        add_project_argument(p)
        if name in {"init", "ingest", "snapshot", "replay", "demo"}:
            p.add_argument("--chat-id", required=name != "demo", default="dev-chat" if name == "demo" else None)
        if name in {"metrics", "serve"}:
            p.add_argument("--chat-id")
        if name in {"pool-config", "subdomain", "enroll-worker", "configure-role", "processing-policy", "hire-role", "register-required"}:
            p.add_argument("--input-json", required=True, help="Structured captured configuration or child-area declaration")
        if name in {"responsibility", "register-required"}:
            p.add_argument("--request-id", required=True)
        if name == "init":
            p.add_argument("--policy-json", help="Captured policy JSON; default is the fake development policy")
        if name == "ingest":
            p.add_argument("--class", dest="input_class", required=True, choices=conductor_queue.CLASSES)
            p.add_argument("--input-json", required=True, help="Input payload JSON")
        if name == "replay":
            p.add_argument("--after", type=int, default=0)
        if name == "requeue":
            p.add_argument("--subscription", required=True, choices=conductor_queue.SUBSCRIPTIONS)
            p.add_argument("--event-seq", type=int, required=True)
        if name in {"serve", "demo"}:
            p.add_argument("--conductor-delay", type=float, default=0.6, help="Fake conductor model latency in seconds")
            p.add_argument("--checkpoint-tokens", type=int, default=4000)
            p.add_argument("--tokens-per-turn", type=int, default=9000)
        if name == "demo":
            p.add_argument("--burst", type=int, default=200, help="Progress events per worker step in the flood scenario")
    return parser


def store_for(args):
    store = conductor_queue.Store(conductor_queue.database_path(args.project_root, runtime_home=args.runtime_home, project_id=args.project_id))
    store.project_root = args.project_root
    return store


def runtime_for(store, args):
    fake = conductor_runtime.FakeConductor(delay=args.conductor_delay, tokens_per_turn=args.tokens_per_turn,
                                           checkpoint_tokens=args.checkpoint_tokens)
    executors = {"fake": conductor_runtime.FakeExecutor(store),
                 "managed": conductor_runtime.ManagedExecutor(store, args.project_root)}
    conductors = {"fake": fake, "managed": conductor_runtime.ManagedConductor(args.project_root, store)}
    return conductor_runtime.Runtime(store, conductors=conductors, executors=executors)


def demo(store, args):
    """Two independent requests in parallel, a follow-up, a progress flood with a cancel, and the metrics."""
    chat = args.chat_id
    store.ensure_chat(chat, DEFAULT_POLICY)
    runtime = runtime_for(store, args)
    stop = threading.Event()
    loop = threading.Thread(target=lambda: [runtime.tick() or time.sleep(0.005) for _ in iter(stop.is_set, True)], daemon=True)
    loop.start()
    stamp = str(int(time.time() * 1000))
    send = lambda key, text, **extra: store.ingest(chat, "conversation", {"clientMessageId": key + "-" + stamp, "text": text,
                                                                         **extra}, sent_at=time.time())
    send("a", "보고서 초안 작업 2개 2초", relation="new")
    send("b", "테스트 정리 작업 3개 3초 폭주=%d" % args.burst, relation="new")

    def wait(predicate, limit=60):
        end = time.time() + limit
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.05)
        return False
    c = store.connection()
    wait(lambda: c.execute("SELECT COUNT(*) FROM delegations").fetchone()[0] >= 5)
    first = c.execute("SELECT id, version FROM requests ORDER BY created_at LIMIT 1").fetchone()
    send("a2", "첫 요청 후속: 표 형식으로 정리", requestId=first["id"])
    flood = c.execute("SELECT id, version FROM requests ORDER BY created_at DESC LIMIT 1").fetchone()
    wait(lambda: c.execute("SELECT COUNT(*) FROM inputs WHERE class='progress'").fetchone()[0] >= args.burst)
    cancel_sent = time.time()
    flood = c.execute("SELECT id, version FROM requests WHERE id=?", (flood["id"],)).fetchone()
    store.ingest(chat, "control", {"commandId": "cancel-" + stamp, "action": "cancel", "requestId": flood["id"],
                                   "expectedVersion": flood["version"]}, sent_at=cancel_sent)
    wait(lambda: c.execute("SELECT COUNT(*) FROM requests WHERE status NOT IN ('completed','cancelled')").fetchone()[0] == 0, 90)
    wait(lambda: not runtime.turns)
    stop.set()
    loop.join()
    runtime.drain(10)
    cancel = c.execute("SELECT routed_at - accepted_at FROM inputs WHERE class='control' ORDER BY seq DESC LIMIT 1").fetchone()[0]
    requests = [dict(r) for r in c.execute("SELECT id, conductor_id, status, version FROM requests WHERE chat_id=?", (chat,))]
    return {"kind": "conductor-queue-demo", "chatId": chat, "requests": requests,
            "conductors": c.execute("SELECT COUNT(*) FROM conductors WHERE chat_id=?", (chat,)).fetchone()[0],
            "progressInputs": c.execute("SELECT COUNT(*) FROM inputs WHERE class='progress'").fetchone()[0],
            "cancelRouteMs": round(cancel * 1000, 2), "metrics": store.metrics(chat)}


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
        store = store_for(args)
        if args.command == 'responsibility':
            result = store.responsibility.view(store.connection(), args.request_id)
        elif args.command == 'role-pools':
            result = store.roles.projection(store.connection())
        elif args.command == 'resume-required':
            with store.tx() as c:
                result = {'reconciled': store.responsibility.reconcile(c)}
        elif args.command in ('configure-role', 'processing-policy', 'hire-role', 'register-required'):
            value = json.loads(args.input_json)
            with store.tx() as c:
                if args.command == 'register-required':
                    result = store.responsibility.register(c, args.request_id, value['tasks'], value['source'])
                elif args.command == 'hire-role':
                    result = store.roles.hire(c, value['area'], value['profile'], value['settings'], value['reference'])
                else:
                    store.roles.configure(c, value['areaId'], value['reference'], route=value.get('route'), profile=value.get('profile'), settings=value.get('settings'))
                    result = store.roles.projection(c)
        elif args.command == 'enroll-worker':
            value = json.loads(args.input_json)
            result = store.pool.enroll_worker(value['chatId'], value['agentId'], value['area'], value['reference'])
        elif args.command == 'pool-config':
            value = json.loads(args.input_json)
            result = store.pool.configure(value['configuration'], value['reference'])
        elif args.command == 'subdomain':
            from tasks import domains
            value = json.loads(args.input_json)
            result = domains.subdomain(store.path.parent, value['domainId'], value['name'], value['actor'], value['source'],
                                       value.get('expectedRevision'), value.get('writeScope'))
        elif args.command == "init":
            result = store.ensure_chat(args.chat_id, json.loads(args.policy_json) if args.policy_json else DEFAULT_POLICY)
        elif args.command == "ingest":
            result = store.ingest(args.chat_id, args.input_class, json.loads(args.input_json), sent_at=time.time())
        elif args.command == "snapshot":
            result = store.ui_snapshot(args.chat_id)
        elif args.command == "replay":
            result = store.ui_replay(args.chat_id, args.after)
        elif args.command == "metrics":
            result = store.metrics(args.chat_id)
        elif args.command == "quarantined":
            result = store.quarantined()
        elif args.command == "requeue":
            result = store.requeue_quarantined(args.subscription, args.event_seq)
        elif args.command == "recover":
            result = store.recover()
        elif args.command == "serve":
            return conductor_runtime.serve(store, runtime_for(store, args), store.path.with_suffix(".lock"),
                                           chat_id=args.chat_id)
        else:
            result = demo(store, args)
        emit(result)
        return 0
    except ContractError as error:
        emit(error_document(error.code, error.message))
        return 2
    except (OSError, ValueError, KeyError, TypeError) as error:
        emit(error_document("conductor_queue_input_invalid", str(error)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
