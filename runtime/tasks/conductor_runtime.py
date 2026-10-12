"""Single-process runtime over the conductor queue ledger: relay, router, consumers and turns.

One leader (an exclusive lock on the project's queue) routes and consumes; any other
process is a follower that still accepts input and streams the UI feed. Drivers are
pluggable: the fake conductor/executor exist for development and fault tests, the
managed executor hands delegations to the existing exec.py Work lifecycle.
"""
from __future__ import annotations

import contextlib
import json
import re
import sys
import threading
import time
import types
from pathlib import Path

from storage import files
from storage.errors import ContractError
from tasks.conductor_queue import DELEGATION_TERMINAL, StaleOwner, digest, iso

HANGUL = re.compile("[가-힣]")


class FakeConductor:
    """Deterministic stand-in for a conductor model: interpret, plan, delegate, synthesize.

    It sleeps to imitate model latency, so inputs arriving meanwhile wait in the
    conductor's mailbox until the next turn boundary, exactly as with a real session.
    """

    def __init__(self, *, delay=0.6, chunk_delay=0.12, tokens_per_turn=9000, window=100000, checkpoint_tokens=4000):
        self.delay, self.chunk_delay = delay, chunk_delay
        self.tokens_per_turn, self.window, self.checkpoint_tokens = tokens_per_turn, window, checkpoint_tokens
        self.used = {}
        self.lock = threading.Lock()

    @staticmethod
    def plan(text, *, followup=False):
        lower = text.lower()
        count = re.search(r"(\d+)\s*(?:개|tasks?\b)|tasks?\s*=\s*(\d+)", lower)
        seconds = re.search(r"(\d+(?:\.\d+)?)\s*(?:s\b|sec|초)", lower)
        burst = re.search(r"(?:burst|폭주)\s*=?\s*(\d+)", lower)
        question = lower.rstrip().endswith("?") and not count
        # A follow-up refines the owner's plan; it adds workers only when it asks for them explicitly.
        tasks = 0 if question else int(count.group(1) or count.group(2)) if count else 0 if followup else 2
        return {"tasks": tasks, "durationMs": int(float(seconds.group(1)) * 1000) if seconds else 3000,
                "failOnce": "fail-once" in lower or "실패 1회" in text, "progressBurst": int(burst.group(1)) if burst else 0}

    def turn(self, context, stream):
        time.sleep(self.delay)
        commands = []
        for request_id, request in context["requests"].items():
            say = (lambda k, e: k) if HANGUL.search(request["title"]) else (lambda k, e: e)
            items = [item for item in context["items"] if item["request_id"] == request_id]
            delegations = request["delegations"]
            if request["status"] == "decomposed":
                children = context.get("children", {}).get(request_id, [])
                if children and all(ch["status"] in ("completed", "cancelled") for ch in children):
                    commands.append({"type": "reply", "requestId": request_id, "final": True,
                                     "text": say("분리된 작업 결과를 종합했습니다.", "Separated intents have finished.")})
                continue
            if request["status"] in ("cancelled", "cancelling"):
                if any(i["kind"] == "request-cancelled" for i in items):
                    commands.append({"type": "reply", "requestId": request_id,
                                     "text": say("요청 취소를 확인했습니다. 이미 끝난 작업 결과는 그대로 보존됩니다.",
                                                 "Cancellation acknowledged. Work that already finished keeps its result.")})
                continue
            for item in [i for i in items if i['kind'] == 'required-task']:
                commands.append({'type': 'delegate', 'requestId': request_id, **item['payload']})
            for item in [i for i in items if i["kind"] == "user-message"]:
                if item['payload'].get('instructionId'):
                    coverage = [t['id'] for t in context.get('responsibility', {}).get(request_id, {}).get('tasks', [])]
                    commands.append({'type': 'ack-instruction', 'requestId': request_id, 'instructionId': item['payload']['instructionId'], 'taskIds': coverage, 'evidence': 'Fake driver applied exact accepted input'})
                if context.get('responsibility', {}).get(request_id, {}).get('tasks'):
                    continue
                lines = [line.split(":", 1)[1].strip() for line in item["payload"]["text"].splitlines()
                         if line.lower().startswith(("independent:", "독립:"))]
                if len(lines) > 1 and not request.get("intent") and not delegations:
                    commands.append({"type": "split", "requestId": request_id, "intents": [
                        {"key": str(n), "title": line, "reason": "explicit independent development scenario",
                         "spec": {"goal": line, "completionCriteria": line, "writeScope": [], "workspace": {"mode": "read-only"}}}
                        for n, line in enumerate(lines)]})
                    continue
                plan = self.plan(item["payload"]["text"], followup=bool(delegations))
                key = "msg-" + item["id"]
                if plan["tasks"] and not delegations:
                    text = say("요청을 이해했습니다. 작업을 %d개로 나누어 수행자에게 맡기고 결과를 종합하겠습니다." % plan["tasks"],
                               "Understood. I will split this into %d tasks for workers and combine the results." % plan["tasks"])
                elif plan["tasks"]:
                    text = say("후속 요청을 반영해 작업 %d개를 추가합니다." % plan["tasks"],
                               "Follow-up applied: adding %d tasks." % plan["tasks"])
                elif delegations:
                    text = say("후속 요청을 현재 계획에 반영했습니다.", "Follow-up applied to the current plan.")
                else:
                    text = say("답변드립니다: 이 요청은 수행자 위임 없이 지휘자가 바로 응답합니다.",
                               "Answer: this request needs no worker; the conductor replies directly.")
                for part in self.chunks(text):
                    try:
                        stream(request_id, part, key)
                    except StaleOwner:
                        return [], None  # Ownership moved during the turn: stop writing.
                    time.sleep(self.chunk_delay)
                open_delegations = [d for d in delegations if d["status"] not in DELEGATION_TERMINAL]
                commands.append({"type": "reply", "requestId": request_id, "messageKey": key, "text": text,
                                 "final": not plan["tasks"] and not open_delegations})
                for index in range(plan["tasks"]):
                    commands.append({"type": "delegate", "requestId": request_id,
                                     "title": say("작업 %d: %s" % (index + 1, request["title"]),
                                                  "Task %d: %s" % (index + 1, request["title"])),
                                     "spec": {"goal": item["payload"]["text"], "part": index + 1, "of": plan["tasks"],
                                              "durationMs": plan["durationMs"], "failOnce": plan["failOnce"] and index == 0,
                                              "workerQuestion": "ask-worker" in item["payload"]["text"], "progressBurst": plan["progressBurst"], "writeScope": [], "workspace": {"mode": "read-only"}}})
            results = [i for i in items if i["kind"] in ("delegation-result", "worker-question")]
            if results and not any(i["kind"] == "user-message" for i in items):
                states = {d["id"]: d for d in delegations}
                for item in results:
                    d = item["payload"].get("delegation") or {}
                    states[d.get("id")] = {**states.get(d.get("id"), {}), **d}
                done = [d for d in states.values() if d.get("status") in DELEGATION_TERMINAL]
                if len(done) == len(states):
                    lines = ["- %s: %s" % (d["title"], d["status"]) for d in sorted(states.values(), key=lambda d: d["title"])]
                    commands.append({"type": "reply", "requestId": request_id, "final": True,
                                     "text": say("모든 작업이 끝났습니다. 결과를 종합합니다.\n", "All tasks finished. Summary:\n")
                                     + "\n".join(lines)})
                else:
                    commands.append({"type": "reply", "requestId": request_id,
                                     "text": say("작업 결과를 받았습니다 (%d/%d 완료)." % (len(done), len(states)),
                                                 "Received a result (%d/%d done)." % (len(done), len(states)))})
        return commands, self.usage(context)

    @staticmethod
    def chunks(text):
        words = text.split(" ")
        third = max(1, len(words) // 3)
        return [" ".join(words[i:i + third]) + (" " if i + third < len(words) else "") for i in range(0, len(words), third)]

    def usage(self, context):
        key = (context["conductorId"], context["slot"], context["epoch"])
        with self.lock:
            base = self.checkpoint_tokens if context["epoch"] else 0
            self.used[key] = self.used.get(key, base) + self.tokens_per_turn
            return {"usedTokens": self.used[key], "contextWindowTokens": self.window}


CONDUCTOR_INSTRUCTIONS = """You are a physical instance of ONE logical conductor in Agent Factory's shared chat queue, never a separate logical conductor.
The domain/subdomain area is your responsibility and A/B are execution handoff slots.
Confirmed fixedDecisions are immutable, outside compression; preserve their exact values and sources.
Current pendingQuestions carry authoritative question ownership, overriding old checkpoint slot fields.
Every delegate must declare writeScope paths or scopeBySubdomain with a recorded path scope.
Register every authorized deliverable and mandatory follow-up using register-required (stable key, title, spec, prerequisites); delegate each required task with obligationId. Acknowledge pending instructions with ack-instruction and explicit coverage/evidence. A model turn ending is not request completion. Internal capacity/dependency waits do not require new approval. For a genuine Human decision, ask with decisionKind/decisionScope, reason, impact, target, alternatives and recommendation when available; preserve free-text answers and keep independent eligible tasks progressing. Never silently omit required follow-ups or receipts.
Every intent must have an explicit existing domainId/subdomainId area; ask when uncertain.
You own the requests listed under "requests": interpret them, plan, delegate bounded work to workers
and synthesize worker results into the answer. You never implement work yourself.
Before delegation, identify independent goals in each user-message. For two or more goals use
{"type":"split","requestId":ID,"intents":[{"key":TEXT,"title":TEXT,"reason":TEXT,
 "dependsOn":[KEY],"spec":{"goal":TEXT,"completionCriteria":TEXT,"writeScope":[PROJECT_RELATIVE_PATH],
 "sharedResources":[RESOURCE],"workspace":{"mode":"read-only"|"shared"|"code",
 "repositories":[{"path":PROJECT_RELATIVE_REPOSITORY,"targetBranch":BRANCH,"checks":[[EXECUTABLE,ARG]]}]}}}]}
Only split independently assessable goals. Dependencies name intent keys; do not parallelize overlapping
write scopes or shared mutable state. Code work that could run alongside another writer uses code
workspace isolation with exact repositories, existing target branches and real check argv arrays.
Shared is sequential; read-only writes nothing. Ask when goals, ownership, repositories or checks are
unclear. Never guess these from IDs. Follow-ups retain their requestId. A request with intent already
contains a bounded plan: delegate that goal without splitting again. Parent synthesis uses children.
Return ONLY one JSON object (no prose) of the form
{"commands": [ ... ]} where each command is one of
  {"type": "reply", "requestId": ID, "text": TEXT, "final": BOOLEAN}
  {"type": "delegate", "requestId": ID, "title": TEXT, "spec": {"goal": TEXT, "completionCriteria": TEXT,
     "inputs": [TEXT], "writeScope": [PATH]}}
  {"type": "ask", "requestId": ID, "text": QUESTION, "reason": TEXT, "impact": TEXT, "alternatives": [TEXT]}
  {"type": "register-required", "requestId": ID, "tasks": [{"key": KEY, "title": TEXT, "spec": SPEC, "prerequisites": [KEY]}]}
  {"type": "ack-instruction", "requestId": ID, "instructionId": ID, "taskIds": [REQUIRED_TASK_ID], "evidence": TEXT}
Use only requestIds from "requests". A final reply is allowed only when that request has no open
delegation. Answer in the user's language. "checkpoint", when present, is your predecessor's confirmed
decisions, pending inputs, open delegations and processing position; continue from it."""


def parse_commands(text):
    """The conductor's committed output: one JSON object with a commands list, nothing inferred."""
    if not isinstance(text, str):
        raise ContractError("conductor_output", "Conductor returned no text")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ContractError("conductor_output", "Conductor output has no JSON object")
    try:
        value = json.loads(text[start:end + 1])
    except ValueError as error:
        raise ContractError("conductor_output", "Conductor output is not valid JSON") from error
    commands = value.get("commands") if isinstance(value, dict) else None
    if not isinstance(commands, list) or not all(isinstance(c, dict) and c.get("type") in {"reply", "delegate", "ask", "split", "register-required", "ack-instruction"}
                                                 for c in commands):
        raise ContractError("conductor_output", "Conductor output needs an explicitly supported fenced command list")
    return commands


class ManagedConductor:
    """LLM conductor over the existing managed lifecycle: exec.py submit/send, provider adapter, policy.

    Each conductor slot (A/B of the handoff reducer) is one managed agent with its own native
    session, so a compaction switch hands the next turn to a fresh session that receives the
    checkpoint. The turn's dispatch ID is derived from the turn ID: a recovered turn finds an
    accepted run instead of submitting twice. Answers are committed whole (no token streaming).
    """

    def __init__(self, project_root, store, *, poll_seconds=1.0, backend=None):
        from tasks.conductor_backend import ManagedBackend
        self.store, self.poll = store, poll_seconds
        self.project_root = Path(project_root)
        store.project_root = self.project_root
        owner = types.SimpleNamespace(root=Path(project_root), path=store.path, chat_id="conductor-queue")
        self.backend = backend or ManagedBackend(owner)

    @staticmethod
    def agent_id(context):
        return "cq-%s-%s" % (context["conductorId"].split("-", 1)[1], context["slot"].lower())

    def request(self, context):
        policy = context["policy"]
        settings = policy["conductorSettings"]
        agent = self.agent_id(context)
        sessions = Path(self.store.path).parent / "agents" / agent / "session.json"
        payload = {k: context[k] for k in ("conductorId", "slot", "epoch", "turnId", "checkpoint", "items", "requests", "children", "fixedDecisions", "responsibility", "pendingQuestions", "areaCatalog", "area", "logicalConductorId")}
        payload["workspacePolicy"] = {"workIsolation": policy.get("workIsolation", False), "projectRoot": str(self.project_root)}
        return {"run": {"dispatchId": "cq-" + context["turnId"]},
                "session": {"agentId": agent, "managedCreated": sessions.exists(), "role": "conversation",
                            "settings": settings, "handoff": None, "area": context.get("area")},
                "message": {"kind": "question", "taskId": None,
                            "text": CONDUCTOR_INSTRUCTIONS + "\n\n" + json.dumps(payload, ensure_ascii=False)},
                "task": None,
                "policy": {"sandbox": policy.get("conductorSandbox", "read-only"),
                           "approvalPolicy": policy["approvalPolicy"], "reference": policy["reference"]}}

    def turn(self, context, stream):
        request = self.request(context)
        run = self.backend.lookup(request) or self.backend.submit(request)
        agent = request["session"]["agentId"]
        while run.get("status") not in ("completed", "failed", "cancelled", "runtime-error", "needs-human-decision"):
            time.sleep(self.poll)
            run = self.backend.call(["status", "--agent", agent, "--run-id", run["runId"]]).get("run") or run
        if run["status"] != "completed":
            raise ContractError("conductor_run_" + run["status"].replace("-", "_"), "Conductor run did not complete")
        text = Path(run["resultPath"]).read_text(encoding="utf-8") if run.get("resultPath") else run.get("response")
        usage = run.get("contextUsage") or {}
        observed = ({"usedTokens": usage["usedTokens"], "contextWindowTokens": usage["contextWindowTokens"]}
                    if type(usage.get("usedTokens")) is int and type(usage.get("contextWindowTokens")) is int else None)
        return parse_commands(text), observed


class FakeExecutor:
    """Worker pool stand-in: emits started/progress/terminal events through the same ingress."""

    def __init__(self, store, *, step_count=5):
        self.store, self.step_count = store, step_count
        self.workers, self.cancelled = {}, set()
        self.lock = threading.Lock()

    def emit(self, ctx, kind, event_id, cls="lifecycle", **data):
        try:
            return self.store.ingest(ctx["chatId"], cls, {"delegationId": ctx["delegationId"], "attemptId": ctx["attemptId"],
                                                          "workerEventId": event_id, "kind": kind, "sentAt": time.time(), **data},
                                     sent_at=time.time())
        except ContractError:
            return None

    def start(self, ctx):
        with self.lock:
            if ctx["attemptId"] in self.workers:
                return  # Redelivered start for a live attempt is idempotent.
            thread = threading.Thread(target=self.run, args=(ctx,), daemon=True, name="fake-worker-" + ctx["attemptId"])
            self.workers[ctx["attemptId"]] = thread
        thread.start()

    def run(self, ctx):
        spec, attempt = ctx["spec"], ctx["attemptId"]
        try:
            self.emit(ctx, "started", "started")
            if spec.get('workerQuestion'):
                self.emit(ctx, 'question', 'question', question={'text': 'Which output format?', 'decisionKind': 'clarification'})
                return
            steps = self.step_count
            for step in range(1, steps + 1):
                time.sleep(spec.get("durationMs", 3000) / 1000 / steps)
                if attempt in self.cancelled:
                    self.emit(ctx, "cancelled", "cancelled")
                    return
                if spec.get("failOnce") and ctx["number"] == 1 and step == steps // 2 + 1:
                    self.emit(ctx, "failed", "failed", error={"code": "fake-transient", "retryable": True,
                                                              "message": "Injected first-attempt failure"})
                    return
                for burst in range(spec.get("progressBurst", 0)):
                    self.emit(ctx, "progress", "p%d-b%d" % (step, burst), cls="progress", step="burst",
                              detail="burst %d" % burst)
                self.emit(ctx, "progress", "p%d" % step, cls="progress", step="step %d" % step,
                          detail=ctx["title"], completed=step, total=steps)
            self.emit(ctx, "completed", "completed", result={"summary": "%s done" % ctx["title"], "steps": steps, "resultPath": "fake-result:" + attempt, "receiptPath": "fake-receipt:" + attempt, "workRunId": attempt, "resultRevision": attempt})
        finally:
            self.store.close()
            with self.lock:
                self.workers.pop(attempt, None)

    def cancel(self, ctx):
        with self.lock:
            self.cancelled.add(ctx["attemptId"])
            alive = ctx["attemptId"] in self.workers
        if not alive:
            self.emit(ctx, "cancelled", "cancelled")

    def answer(self, ctx, text, command_id):
        self.emit(ctx, "completed", "answer:" + command_id, result={"summary": text})

    def recover(self, ctx):
        """A restarted runtime lost in-process workers: report it so the retry policy decides."""
        with self.lock:
            alive = ctx["attemptId"] in self.workers
        if alive:
            return
        if ctx["status"] == "starting":
            # Start never confirmed by the worker: the fake backend can start it now under the same attempt ID.
            self.start(ctx)
            return
        self.emit(ctx, "failed", "lost", error={"code": "worker-lost", "retryable": True,
                                                "message": "Runtime restarted while the worker was running"})


class ManagedExecutor:
    """Delegation → existing exec.py Work submission; taskBinding, policy and model come from the captured chat policy.

    Implemented over tasks.conductor_backend.ManagedBackend; status is observed with
    exec.py status because the managed lifecycle offers no push channel to this runtime.
    """

    def __init__(self, store, project_root, *, poll_seconds=2.0, backend=None):
        from tasks.conductor_backend import ManagedBackend
        self.store, self.poll = store, poll_seconds
        self.project_root = Path(project_root)
        store.project_root = self.project_root
        owner = types.SimpleNamespace(root=Path(project_root), path=store.path, chat_id="conductor-queue")
        self.backend = backend or ManagedBackend(owner)
        self.watchers = {}
        self.lock = threading.Lock()

    def request(self, ctx):
        policy = ctx["policy"]
        worker = ctx.get('worker')
        agent = worker['id'] if worker else 'work-cq-' + ctx['attemptId'][4:]
        settings = ctx['spec'].get('executionSettings') or policy['work']
        settings = {k: v for k, v in settings.items() if k not in ('sandbox', 'approvalPolicy') and not (k == 'workProfile' and v == 'work')}
        verification = {'agentId': ctx['verifier'], 'area': json.loads(worker['area']), 'settings': ctx['spec']['verificationSettings']} if ctx.get('verifier') else None
        return {"verification": verification, "run": {"dispatchId": "cq-" + ctx["attemptId"]},
                "session": {"agentId": agent, "managedCreated": (Path(self.store.path).parent / "agents" / agent / "session.json").exists(), "role": "work",
                            "area": json.loads(worker["area"]) if worker else None,
                            "settings": settings, "handoff": None},
                "message": {"kind": "task", "text": ctx["spec"].get("goal") or ctx["title"]},
                "task": {"id": ctx["delegationId"], "spec": {
                    "goal": ctx["spec"].get("goal") or ctx["title"], "inputs": ctx["spec"].get("inputs", []),
                    "completionCriteria": ctx["spec"].get("completionCriteria") or ctx["title"],
                    "writeScope": ctx["spec"].get("writeScope", []), "dependencies": ctx["spec"].get("dependencies", []),
                    **{k: ctx["spec"][k] for k in ("taskMode", "workProfile", "verificationSettings", "workIsolation", "executionSettings") if k in ctx["spec"]},
                    **({"workspace": ctx["spec"]["workspace"]} if "workspace" in ctx["spec"] else {})}},
                "policy": {"sandbox": "read-only" if (ctx["spec"].get("workspace") or {}).get("mode") == "read-only" else policy["sandbox"], "approvalPolicy": policy["approvalPolicy"],
                           "reference": policy["reference"]}}

    def start(self, ctx):
        with self.lock:
            if ctx["attemptId"] in self.watchers:
                return
            thread = threading.Thread(target=self.launch, args=(ctx,), daemon=True)
            self.watchers[ctx["attemptId"]] = thread
        thread.start()

    def launch(self, ctx):
        try:
            self.launch_run(ctx)
        except (ContractError, OSError) as error:
            # Submission acknowledgement can be lost after acceptance. Resolve the
            # stable dispatch key before failing or releasing a resource reservation.
            request = self.request(ctx)
            while True:
                try:
                    accepted = self.backend.lookup(request)
                    break
                except (ContractError, OSError) as observation_error:
                    self.store.record_observation(ctx['attemptId'], 'start-uncertain:' + getattr(observation_error, 'code', type(observation_error).__name__))
                    if hasattr(self.backend, 'classify_error') and self.backend.classify_error(observation_error) not in ('transient', 'provider'):
                        return  # Retain the reservation and exact dispatch; recover after the source fault is repaired.
                    time.sleep(self.poll)
            if accepted:
                external = {**accepted, 'agentId': request['session']['agentId'], 'runId': accepted['runId'], 'dispatchId': request['run']['dispatchId']}
                self.store.record_external(ctx['attemptId'], external)
                self.observe({**ctx, 'external': external})
                return
            if hasattr(self.backend, 'workspace'):
                workspace = self.backend.workspace(ctx['delegationId'])
                if workspace:
                    self.store.record_workspace(ctx['attemptId'], workspace)
            self.store.ingest(ctx["chatId"], "lifecycle", {"delegationId": ctx["delegationId"], "attemptId": ctx["attemptId"],
                "workerEventId": "start-error", "kind": "failed", "error": {"code": getattr(error, "code", "start_error"), "message": str(error), "retryable": False}})
        finally:
            self.store.close()
            with self.lock:
                self.watchers.pop(ctx["attemptId"], None)

    def launch_run(self, ctx):
        request = self.request(ctx)
        run = (ctx["external"] and ctx["external"].get("runId") and ctx["external"]) or self.backend.lookup(request)
        if not run:
            run = self.backend.submit(request)
        external = {**run, "agentId": request["session"]["agentId"], "runId": run["runId"], "dispatchId": request["run"]["dispatchId"]}
        self.store.record_external(ctx["attemptId"], external)
        row = self.store.row(self.store.connection(), 'SELECT cancel_requested FROM delegations WHERE id=?', ctx['delegationId'])
        if row['cancel_requested']:
            self.backend.workflows.cancel(external, 'human-queue-cancel:' + ctx['delegationId']) if external.get('workflow') else self.backend.call(['cancel', '--agent', external['agentId'], '--run-id', external['runId']])
        self.observe({**ctx, "external": external})

    def answer(self, ctx, text, command_id):
        if ctx['external'].get('workflow'):
            self.backend.workflows.answer(ctx['external'], text, 'human-control:' + command_id, expected_decision=(ctx.get('answeredQuestion') or {}).get('decision'))
            self.watch(ctx)
            return
        request = self.request(ctx)
        request['session']['agentId'] = ctx['external']['agentId']
        request['session']['managedCreated'] = True
        request['run']['dispatchId'] = 'cq-answer-' + command_id
        request['message']['text'] = text
        run = self.backend.lookup(request) or self.backend.submit(request)
        external = {**ctx['external'], 'runId': run['runId'], 'dispatchId': request['run']['dispatchId']}
        self.store.record_external(ctx['attemptId'], external)
        self.watch({**ctx, 'external': external})

    def workspace_action(self, ctx, action, authorization):
        try:
            self.backend.workspace_action(ctx, action, authorization)
        except (ContractError, OSError):
            pass  # The adapter records the exact retained failure; no automatic force/retry.
        workspace = self.backend.workspace(ctx['delegationId'])
        if workspace:
            self.store.record_workspace(ctx['attemptId'], workspace)

    def watch(self, ctx):
        with self.lock:
            if ctx["attemptId"] in self.watchers:
                return
            thread = threading.Thread(target=self.observe, args=(ctx,), daemon=True)
            self.watchers[ctx["attemptId"]] = thread
        thread.start()

    def observe(self, ctx):
        mapping = {"completed": "completed", "failed": "failed", "runtime-error": "failed", "cancelled": "cancelled",
                   "needs-human-decision": "question"}
        try:
            started = False
            def ingest(kind, **data):
                try:
                    self.store.ingest(ctx["chatId"], "lifecycle", {"delegationId": ctx["delegationId"],
                                                                   "attemptId": ctx["attemptId"], "workerEventId": ctx["external"]["runId"] + ":" + kind + (":" + digest(data.get("question"))[:24] if kind == "question" else ""),
                                                                   "kind": kind, **data})
                except ContractError:
                    pass  # Already recorded by an earlier observer; the ledger keeps the first fact.
            while True:
                try:
                    run = self.backend.status(ctx['external']) if hasattr(self.backend, 'status') else self.backend.call(["status", "--agent", ctx["external"]["agentId"], "--run-id", ctx["external"]["runId"]]).get("run") or {}
                    if ctx['external'].get('workflow'):
                        self.store.record_workflow(ctx['attemptId'], run)
                except (ContractError, OSError) as error:
                    self.store.record_observation(ctx["attemptId"], "observation-unavailable:" + getattr(error, "code", type(error).__name__))
                    time.sleep(self.poll)  # The managed record is the source of truth; keep observing it.
                    continue
                status = run.get("status")
                try:
                    health = self.backend.health(ctx["external"]) if hasattr(self.backend, "health") else {}
                    workspace = self.backend.workspace(ctx["delegationId"]) if hasattr(self.backend, "workspace") else None
                except (ContractError, OSError) as error:
                    self.store.record_observation(ctx["attemptId"], 'observation-unavailable:' + getattr(error, 'code', type(error).__name__))
                    time.sleep(self.poll)
                    continue
                self.store.record_observation(ctx["attemptId"], 'heartbeat-timeout' if health.get('heartbeatStale') and status not in mapping else None)
                if health.get("zombie"):
                    ingest("failed", error={"code": "worker-zombie", "retryable": False,
                                            "message": "Managed process containment is confirmed empty"})
                    return
                if workspace:
                    self.store.record_workspace(ctx["attemptId"], workspace)
                progress = health.get('progress') or {}
                if isinstance(progress.get('action'), str) and progress.get('source'):
                    self.store.ingest(ctx['chatId'], 'progress', {'delegationId': ctx['delegationId'], 'attemptId': ctx['attemptId'],
                        'workerEventId': 'progress:' + digest([ctx['external']['runId'], progress]), 'kind': 'progress',
                        'step': progress['action'], 'source': progress['source']})
                if not started and status in ("running", "starting", "accepted", "queued", *mapping):
                    ingest("started")
                    started = True
                if status in mapping:
                    if hasattr(self.backend, 'health') and not health.get('stopped'):
                        self.store.record_observation(ctx['attemptId'], 'termination-unconfirmed')
                        time.sleep(self.poll)
                        continue
                    kind = mapping[status]
                    data = {"result": {"resultPath": run.get("resultPath"), "receiptPath": run.get("receiptPath"), "workspace": workspace,
                                             "integrationStatus": "awaiting-integration" if workspace and workspace.get("mode") == "code" else None}}
                    if kind == 'completed' and hasattr(self.backend, 'completion'):
                        try:
                            data['result'].update(self.backend.completion(ctx['external']))
                            if ctx['external'].get('workflow'):
                                self.store.record_workflow(ctx['attemptId'], data['result'])
                        except ContractError as error:
                            kind = 'failed'
                            data = {'error': {'code': error.code, 'message': error.message, 'retryable': False}}
                    if kind == "failed" and 'error' not in data:
                        data = {"error": {"code": (run.get("error") or {}).get("code", status), "retryable": False}}
                    if kind == "question":
                        data = {"question": {"runId": run.get("runId"), "decisionKind": run.get("decisionKind"),
                                             "text": run.get("response") or run.get("blocker"), "resultPath": run.get("resultPath")}}
                    if kind == 'question' and hasattr(self.backend, 'question'):
                        try:
                            data['question'].update(self.backend.question(ctx['external']))
                        except (ContractError, OSError) as error:
                            self.store.record_observation(ctx['attemptId'], 'observation-unavailable:' + getattr(error, 'code', type(error).__name__))
                            time.sleep(self.poll)
                            continue
                    ingest(kind, **data)
                    return
                time.sleep(self.poll)
        finally:
            self.store.close()
            with self.lock:
                self.watchers.pop(ctx["attemptId"], None)

    def cancel(self, ctx):
        external = ctx["external"] or {}
        if external.get("runId"):
            self.backend.workflows.cancel(external, "human-queue-cancel:" + ctx["delegationId"]) if external.get("workflow") else self.backend.call(["cancel", "--agent", external["agentId"], "--run-id", external["runId"]])

    def recover(self, ctx):
        if ctx["external"] and ctx["external"].get("runId"):
            self.watch(ctx)
        else:
            self.start(ctx)  # lookup by dispatch ID first: an accepted start is observed, never resubmitted


class Runtime:
    def __init__(self, store, *, conductor=None, conductors=None, executors=None, idle=0.02, max_idle=0.25):
        self.store = store
        # Drivers by the chat's captured policy ("fake" development driver, "managed" LLM conductor).
        self.conductors = conductors or {"fake": conductor or FakeConductor()}
        self.executors = executors or {"fake": FakeExecutor(store)}
        self.idle, self.max_idle = idle, max_idle
        self.turns = {}
        self.effects = {}
        self.lock = threading.Lock()

    def executor(self, ctx):
        return self.executors[ctx["policy"]["executor"]]

    def dispatching(self):
        runtime = self

        class Dispatch:
            def start(self, ctx):
                runtime.executor(ctx).start(ctx)

            def cancel(self, ctx):
                runtime.executor(ctx).cancel(ctx)

            def answer(self, ctx, text, command_id):
                runtime.executor(ctx).answer(ctx, text, command_id)

            def workspace(self, ctx, action, authorization):
                runtime.executor(ctx).workspace_action(ctx, action, authorization)
        return Dispatch()

    def recover(self):
        report = self.store.recover()
        for attempt in report["uncertainAttempts"]:
            ctx = self.store.attempt_context(attempt)
            self.executor(ctx).recover(ctx)
        for attempt in report["pendingCancels"]:
            ctx = self.store.attempt_context(attempt)
            self.executor(ctx).cancel(ctx)
        return report

    def tick(self):
        handled = self.store.publish_pending()
        handled += self.store.route_batch()
        handled += self.store.schedule_instances()
        with self.store.tx() as c:
            handled += self.store.responsibility.reconcile(c)
        handled += self.store.schedule_waiting()
        handled += self.store.consume("conductor", self.store.conductor_handler)
        handled += self.store.consume("executor", self.store.executor_handler(self.dispatching()))
        handled += self.store.consume("ui", self.store.ui_handler)
        handled += self.start_effects()
        handled += self.start_turns()
        return handled

    def start_effects(self):
        with self.store.tx() as c:
            events = [json.loads(r['payload']) for r in c.execute("SELECT payload FROM operator_effects WHERE status='pending'")]
            for event in events:
                c.execute("UPDATE operator_effects SET status='running' WHERE id=?", (event['id'],))
        for event in events:
            thread = threading.Thread(target=self.run_effect, args=(event,), daemon=True)
            self.effects[event['id']] = thread
            thread.start()
        return len(events)

    def run_effect(self, event):
        ctx = self.store.attempt_context(event['payload']['delegation']['attemptId'])
        try:
            if event['type'] == 'worker-answer':
                original = event['payload']['delegation'].get('external') or {}
                current = ctx['external'] or {}
                # A newer answer or cancellation supersedes this exact paused run.
                # Recovery observes the current accepted run; it never sends stale text.
                if not ctx['cancelRequested'] and (not original.get('runId') or current.get('runId') == original['runId']):
                    self.executor({**ctx, 'answeredQuestion': event['payload'].get('question')}).answer(ctx, event['payload']['text'], event['payload']['commandId'])
            else:
                self.executor(ctx).workspace_action(ctx, event['payload']['action'], event['payload']['authorizationReference'])
            with self.store.tx() as c:
                c.execute("UPDATE operator_effects SET status='done' WHERE id=?", (event['id'],))
        except (ContractError, OSError) as error:
            self.store.record_observation(ctx['attemptId'], 'operator-error:' + getattr(error, 'code', type(error).__name__))
            with self.store.tx() as c:
                c.execute("UPDATE operator_effects SET status='failed' WHERE id=?", (event['id'],))
            # Exact input remains pending for restart/operator recovery; no new dispatch ID.
        finally:
            self.store.close()
            self.effects.pop(event['id'], None)

    def start_turns(self):
        c = self.store.connection()
        ready = [r[0] for r in c.execute("SELECT DISTINCT c.id FROM conductors c JOIN mailbox m ON m.conductor_id=c.id"
                                         " WHERE c.status='idle' AND m.status='queued'")]
        started = 0
        for cid in ready:
            with self.lock:
                if cid in self.turns:
                    continue
            context = self.store.begin_turn(cid)
            if not context:
                continue
            thread = threading.Thread(target=self.run_turn, args=(context,), daemon=True, name="turn-" + context["turnId"])
            with self.lock:
                self.turns[cid] = thread
            thread.start()
            started += 1
        return started

    def run_turn(self, context):
        token = {k: context[k] for k in ("conductorId", "slot", "epoch", "turnId")}
        try:
            driver = self.conductors.get(context["policy"].get("conductor", "fake"))
            if driver is None:
                raise ContractError("driver_unavailable", "This runtime has no driver for the chat's conductor policy")
            commands, usage = driver.turn(context, lambda rid, text, key: self.store.stream(token, rid, text, key))
            self.store.end_turn(token, commands, usage)
        except StaleOwner:
            pass
        except Exception as error:  # Driver failure: inputs return to the mailbox, repeated failure quarantines them.
            self.store.fail_turn(token, type(error).__name__)
        finally:
            self.store.close()
            with self.lock:
                self.turns.pop(context["conductorId"], None)

    def drain(self, timeout=30.0):
        """Run until no work, live turn or live worker remains (development and tests)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            handled = self.tick()
            busy = bool(self.turns) or bool(self.effects) or any(getattr(e, "workers", None) or getattr(e, "watchers", None)
                                           for e in self.executors.values())
            if not handled and not busy:
                c = self.store.connection()
                pending = c.execute("SELECT (SELECT COUNT(*) FROM inputs WHERE status='pending') +"
                                    " (SELECT COUNT(*) FROM events WHERE published=0) +"
                                    " (SELECT COUNT(*) FROM deliveries WHERE status='ready') +"
                                    " (SELECT COUNT(*) FROM mailbox WHERE status='queued')").fetchone()[0]
                if not pending:
                    return True
            time.sleep(0.005 if handled else self.idle)
        return False


def serve(store, runtime, lock_path, *, source=sys.stdin, sink=sys.stdout, stop=None, chat_id=None):
    """Leader/follower loop with a JSON-lines command channel and live UI feed.

    Commands (stdin): ensure-chat, ingest, snapshot, board, replay, metrics, quarantined, requeue.
    Output (stdout): {"type":"reply"} per command, {"type":"feed"} for new UI rows,
    {"type":"role"} when leadership changes. Feed rows carry their projection cursor.
    """
    stop = stop or threading.Event()
    write_lock = threading.Lock()

    def write(value):
        with write_lock:
            sink.write(json.dumps(value, ensure_ascii=False) + "\n")
            sink.flush()

    def handle(line):
        try:
            message = json.loads(line)
        except ValueError:
            write({"type": "reply", "ok": False, "error": {"code": "command_invalid", "message": "JSON line required"}})
            return
        reply = {"type": "reply", "id": message.get("id")}
        try:
            op = message.get("op")
            if op == "ensure-chat":
                result = store.ensure_chat(message["chatId"], message["policy"])
            elif op == 'role-pools':
                result = store.roles.projection(store.connection())
            elif op == 'responsibility':
                result = store.responsibility.view(store.connection(), message['requestId'])
            elif op == 'resume-required':
                with store.tx() as c:
                    result = {'reconciled': store.responsibility.reconcile(c)}
            elif op == 'register-required':
                with store.tx() as c:
                    result = store.responsibility.register(c, message['requestId'], message['tasks'], message['source'])
            elif op == 'catalog':
                result = store.pool.catalog()
            elif op == 'configure-pools':
                result = store.pool.configure(message['configuration'], message['reference'])
            elif op == 'enroll-worker':
                result = store.pool.enroll_worker(message['chatId'], message['agentId'], message['area'], message['reference'])
            elif op == 'subdomain':
                from tasks import domains
                value = message['declaration']
                result = domains.subdomain(store.path.parent, value['domainId'], value['name'], value['actor'], value['source'],
                                           value.get('expectedRevision'), value.get('writeScope'))
            elif op == "ingest":
                result = store.ingest(message["chatId"], message["class"], message["payload"], sent_at=message.get("sentAt"))
            elif op == "snapshot":
                result = store.ui_snapshot(message["chatId"])
            elif op == "board":
                result = store.ui_board()
            elif op == "replay":
                result = store.ui_replay(message["chatId"], int(message.get("after", 0)))
            elif op == "metrics":
                result = store.metrics(message.get("chatId"))
            elif op == "quarantined":
                result = store.quarantined()
            elif op == "requeue":
                result = store.requeue_quarantined(message["subscription"], int(message["eventSeq"]))
            elif op == "stop":
                stop.set()
                result = {"stopping": True}
            else:
                raise ContractError("command_unknown", "Unknown op")
            write({**reply, "ok": True, "result": result})
        except ContractError as error:
            write({**reply, "ok": False, "error": {"code": error.code, "message": error.message}})
        except (KeyError, TypeError, ValueError) as error:
            write({**reply, "ok": False, "error": {"code": "command_invalid", "message": str(error)}})
        finally:
            store.close()

    def commands():
        for line in source:
            if line.strip():
                threading.Thread(target=handle, args=(line,), daemon=True).start()
        stop.set()  # The host closed the channel: this process ends with it.

    threading.Thread(target=commands, daemon=True).start()
    c = store.connection()
    cursor = c.execute("SELECT COALESCE(MAX(id), 0) FROM ui_feed").fetchone()[0]
    role, last_try, wait = "starting", 0.0, runtime.idle
    with contextlib.ExitStack() as stack:
        write({"type": "role", "role": role, "cursor": cursor, "at": iso(time.time())})
        while not stop.is_set():
            if role != "leader" and time.time() - last_try >= 1.0:
                # A follower retries leadership, so a crashed leader's work resumes in another process.
                last_try = time.time()
                try:
                    stack.enter_context(files.file_lock(lock_path, blocking=False))
                    role = "leader"
                    write({"type": "role", "role": role, "recovered": runtime.recover(), "at": iso(time.time())})
                except ContractError as error:
                    if error.code != "lock_busy":
                        raise
                    if role != "follower":
                        role = "follower"
                        write({"type": "role", "role": role, "at": iso(time.time())})
            handled = runtime.tick() if role == "leader" else 0
            rows = store.feed_since(cursor)
            if rows:
                cursor = max(r["id"] for r in rows)
                rows = [r for r in rows if not chat_id or r["chatId"] == chat_id]
                if rows:
                    write({"type": "feed", "cursor": cursor, "entries": rows, "emittedAt": time.time()})
            if handled or rows:
                wait = runtime.idle
            else:
                wait = min(runtime.max_idle, wait * 2)
                time.sleep(wait)
    return 0
