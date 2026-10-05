"""Local stdio Codex adapter; execution and containment remain exec.py-owned."""
from __future__ import annotations

from collections import deque
import contextlib
import hashlib
import os
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contracts.receipts import receipt_judgment_defect
from execution.prompts import PromptParts
from execution.streaming import DeltaBuffer
from execution.interview import codex_request_events, extract_markers
from adapters.codex.capabilities import (  # noqa: F401 - re-exported; callers patch these names here
    NativeError, RpcError, CAPABILITY_CACHE_TTL, _cached_capabilities, _capability_identity, _probe_capabilities, inspect_capabilities,
)
from adapters.codex.events import NotificationHandlers
from adapters.codex import policy as codex_policy


def service_tier(models: list[dict], model: str, fast: bool | None) -> str | None:
    if fast is None:
        return None
    if fast is False:
        return "default"
    selected = next((item for item in models if model in (item.get("model"), item.get("id"))), None)
    if selected is None:
        raise NativeError(f"Model {model!r} is absent from Codex model/list; Fast cannot be selected")
    tiers = selected.get("serviceTiers", [])
    matches = [tier["id"] for tier in tiers if isinstance(tier, dict) and isinstance(tier.get("id"), str)
               and (tier.get("name", "").casefold() == "fast" or tier["id"] in ("fast", "priority"))]
    if len(matches) != 1:
        raise NativeError(f"Model {model!r} does not advertise one unambiguous Fast tier; choose a supporting model or turn Fast off")
    return matches[0]


# Defer JSON decoding until consumption; normal execution has no payload ceiling.
MAX_RPC_FRAME_BYTES = None
MAX_RPC_QUEUE_BYTES = None


class FrameQueue(queue.Queue):
    def __init__(self):
        super().__init__()
        self.wire_bytes = 0

    def put(self, value):
        size = len(value) if isinstance(value, bytes) else 0
        with self.not_full:
            while MAX_RPC_QUEUE_BYTES is not None and self.wire_bytes + size > MAX_RPC_QUEUE_BYTES:
                self.not_full.wait()
            self._put(value)
            self.wire_bytes += size
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def _get(self):
        value = super()._get()
        self.wire_bytes -= len(value) if isinstance(value, bytes) else 0
        return value


class Rpc:
    """JSONL RPC; unsolicited events are retained while awaiting replies."""
    def __init__(self, process, observer=None, process_factory=None):
        self.process_factory = process_factory
        self.observer = observer
        self.process = process
        self.incoming = FrameQueue()
        self.pending = deque()
        self.pending_bytes = 0
        self.last_frame = b""
        self.serial = 0
        self.initialized = False
        self.server_request_handler = None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def restart_owned(self):
        """Replace only this adapter's child; never reuse a loaded thread config."""
        if self.process_factory is None:
            raise NativeError("Owned app-server reload is unavailable")
        old_pid = self.process.pid
        self.process.stdin.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired as error:
            raise NativeError("Owned app-server did not stop; refusing competing thread owner") from error
        self.reader.join(timeout=1)
        if self.reader.is_alive():
            raise NativeError("Owned app-server reader did not stop")
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        factory, observer, server_request_handler = self.process_factory, self.observer, self.server_request_handler
        if observer:
            observer("owned-restart", {"stoppedPid": old_pid, "pendingCount": len(self.pending)})
        self.__init__(factory(), observer=observer, process_factory=factory)
        self.server_request_handler = server_request_handler
        self.call("initialize", {"clientInfo": {"name": "agent_factory", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
        self.write({"method": "initialized"})
        self.initialized = True

    def _read(self):
        try:
            while True:
                stream = getattr(self.process.stdout, "buffer", self.process.stdout)
                line = stream.readline() if MAX_RPC_FRAME_BYTES is None else stream.readline(MAX_RPC_FRAME_BYTES + 1)
                if not line:
                    raise NativeError("Codex app-server closed its event stream")
                if isinstance(line, str):
                    line = line.encode("utf-8")
                if MAX_RPC_FRAME_BYTES is not None and len(line) > MAX_RPC_FRAME_BYTES:
                    raise NativeError(f"Codex app-server frame exceeds {MAX_RPC_FRAME_BYTES} bytes "
                                      f"(received at least {len(line)} bytes)")
                self.incoming.put(line)
        except Exception as error:
            self.incoming.put(error)

    def write(self, value):
        if self.observer is not None:
            self.observer("send", value)
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout=0.2):
        while True:
            value = self.incoming.get(timeout=timeout)
            if isinstance(value, Exception):
                if self.observer is not None:
                    self.observer("read-error", {"message": str(value)})
                raise value
            self.last_frame = value
            value = json.loads(value)
            if self.observer is not None:
                self.observer("receive", value)
            if not isinstance(value, dict):
                raise NativeError("Invalid app-server message")
            if "method" not in value or "id" not in value:
                return value
            result = self.server_request_handler(value["method"], value.get("params")) if self.server_request_handler else None
            if result is None:
                # Interactive approvals cannot be silently granted by a background host.
                self.write({"id": value["id"], "error": {"code": -32601, "message": "Interactive request unsupported in managed run; use Human input"}})
                raise NativeError(f"Codex requested interactive input: {value['method']}")
            self.write({"id": value["id"], "result": result})

    def call(self, method, params, timeout=None):
        self.serial += 1
        request_id = self.serial
        self.write({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout if timeout else float("inf")
        while time.monotonic() < deadline:
            try:
                value = self.receive(min(0.2, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if value.get("id") == request_id:
                self.last_frame = b""
                if "error" in value:
                    raise RpcError(method, value["error"])
                return value.get("result", {})
            if MAX_RPC_QUEUE_BYTES is not None and self.pending_bytes + len(self.last_frame) > MAX_RPC_QUEUE_BYTES:
                raise NativeError("Too many pending app-server notifications")
            self.pending.append(self.last_frame)
            self.pending_bytes += len(self.last_frame)
        raise NativeError(f"{method} timed out; do not replay an ambiguous operation")

    def event(self):
        if not self.pending:
            try:
                return self.receive()
            finally:
                self.last_frame = b""
        frame = self.pending.popleft()
        self.pending_bytes -= len(frame)
        return json.loads(frame)


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


# A Goal turn cannot carry a per-turn outputSchema, so its final message is constrained by
# instructions only. One schema-constrained turn restates the result instead of failing finished work;
# a final message that already satisfies the contract starts no extra turn.
RESULT_REPAIR_REQUEST = (
    "Your previous final message did not satisfy this run's result contract: {reason}\n"
    "The work itself is not in question. Do not use tools, change files or repeat any work in this turn. "
    "Return only the final JSON required by the output schema: the status you reached, `resultPath` exactly "
    "as required, and the complete answer you already reached in `resultText`."
)
# Response contract 2: the same turn also returns the receipt judgment, which only the Agent knows.
RECEIPT_REPAIR_REQUEST = (
    " The schema's receipt fields (`outcome`, `changedPaths`, `tests`, `addressedFindingIds`) must carry "
    "this run's real values: the project-root-relative paths you changed and the own checks you actually ran."
)


def activate_persisted_goal(rpc, thread_id, params, turn):
    """Reload a confirmed paused goal, then let native activation start work.

    Per-turn outputSchema cannot precede native goal activation without starting
    unaccounted work. Put the exact contract in developer instructions instead;
    the runtime continues enforcing JSON/result/receipt validation at exit.
    """
    if turn.get("threadId") != thread_id or "outputSchema" not in turn:
        raise NativeError("Goal startup requires exact thread identity and result contract")
    if any(item.get("type") == "localImage" for item in turn.get("input", [])):
        raise NativeError("Native Goal activation does not support local image input")
    before = rpc.call("thread/goal/get", {"threadId": thread_id}).get("goal")
    if not before or before.get("status") != "paused":
        raise NativeError("Owned Goal must be confirmed paused before backend reload")
    rpc.restart_owned()
    config = {**params.get("config", {}), "features.goals": True}
    if turn.get("effort"):
        config["model_reasoning_effort"] = turn["effort"]
    resume = {**params, "threadId": thread_id, "config": config,
              "developerInstructions": params["developerInstructions"] +
              "\nMandatory final JSON contract for every Goal turn (runtime enforced):\n" + json.dumps(turn["outputSchema"])}
    for key in ("model", "serviceTier"):
        if key in turn:
            resume[key] = turn[key]
    result = rpc.call("thread/resume", resume)
    if result["thread"]["id"] != thread_id:
        raise NativeError("Codex changed session while reloading persisted Goal")
    after = rpc.call("thread/goal/get", {"threadId": thread_id}).get("goal")
    for key in ("threadId", "objective", "status", "tokensUsed", "timeUsedSeconds", "tokenBudget"):
        if not after or after.get(key) != before.get(key):
            raise NativeError("Persisted Goal identity/accounting changed during backend reload")
    # Resuming changes configuration, but existing history can retain the old
    # developer baseline until compaction. Goal activation supplies no turn input.
    # Install this run's request and result contract before it can start a turn.
    rpc.call("thread/inject_items", {"threadId": thread_id, "items": [
        {"type": "message", "role": "developer", "content": [
            {"type": "input_text", "text": resume["developerInstructions"]}]}]})
    return rpc.call("thread/goal/set", {"threadId": thread_id, "status": "active"}).get("goal")


class Bridge(NotificationHandlers):
    def __init__(self, runtime, session, state, rpc):
        self.runtime, self.session, self.state, self.rpc = runtime, session, state, rpc
        self.thread_id = None
        self.turn_id = None
        self.goal = None
        self.last_message = None
        self.turn_messages = {}
        # Live previews of agent messages keyed by item id; see stream_text.
        self.deltas = DeltaBuffer()
        self.streams = {}
        self.completed_turns = {}
        self.control_id = None
        self.next_completion_check = 0.0
        self.goal_supported = session.get("nativeCapabilities", {}).get("goal", True)
        self.goal_enabled = session.get("role") in {"main", "work"} and self.goal_supported and (
            session.get("goalMode") is not None or bool(session.get("goal")) or bool(state.get("goalAction")))
        self.stopped = False
        self.planning = state.get("role") == "work" and state.get("executionOptions", {}).get("taskMode") in ("plan", "plan-work", "plan-work-verification")
        self.plan_only = self.planning and state.get("executionOptions", {}).get("taskMode") == "plan"
        self.execution_turn = None
        self.planning_turn_id = None
        self.goal_transition_id = None
        self.goal_start = None
        self.goal_started = False
        self.next_idle_goal_check = 0.0
        # The run's own result turn parameters, and the single repair turn started from them.
        self.result_turn = None
        self.repair_turn_id = None
        self.rpc.server_request_handler = self.handle_server_request

    def handle_server_request(self, method, params):
        """Surface Plan-mode request_user_input without inventing a Human answer."""
        if method != "item/tool/requestUserInput":
            return None
        events = codex_request_events(params)
        if not events:
            raise NativeError("Codex request_user_input did not match the Interview question contract")
        for event in events:
            emit(event)
        return {"answers": {question["id"]: {"answers": []}
                            for question in (params or {}).get("questions", [])}}

    def publish_goal(self, goal):
        if goal is not None and (not isinstance(goal, dict) or goal.get("threadId") != self.thread_id):
            raise NativeError("Native goal belongs to a different session")
        self.goal = goal
        fields = {"goal": goal, "goalObservedAt": self.runtime.now()}
        if goal is None or goal.get("status") != "active":
            fields["goalError"] = None
        state_path = Path(self.state["statePath"])
        self.runtime.update_json(state_path, state_path.parent / ".state.lock", lambda value: value.update(fields))
        session_path = self.runtime.session_file(Path(self.session["projectRoot"]), self.state["agentId"])
        self.runtime.update_json(session_path, session_path.parent / ".session-state.lock", lambda value: value.update(fields))
        emit({"type": "goal.updated", "thread_id": self.thread_id, "goal": goal})

    def get_goal(self):
        goal = self.rpc.call("thread/goal/get", {"threadId": self.thread_id}).get("goal")
        self.publish_goal(goal)
        return goal

    def set_goal(self, **values):
        result = self.rpc.call("thread/goal/set", {"threadId": self.thread_id, **values})
        self.publish_goal(result.get("goal"))

    def control(self, action):
        if action == "get":
            self.get_goal()
            return
        if action in ("clear", "disable", "cancel"):
            session_path = self.runtime.session_file(Path(self.session["projectRoot"]), self.state["agentId"])
            self.runtime.update_json(session_path, session_path.parent / ".session-state.lock", lambda value: value.update({"goalMode": False}))
            self.rpc.call("thread/goal/clear", {"threadId": self.thread_id})
            self.publish_goal(None)
        elif action == "pause":
            if self.goal:
                self.set_goal(status="paused")
        else:
            raise NativeError("Unsupported live Goal control")
        if self.turn_id is None:
            thread = self.rpc.call("thread/read", {"threadId": self.thread_id, "includeTurns": True}).get("thread", {})
            active = [turn for turn in thread.get("turns", []) if turn.get("status") == "inProgress"]
            if active:
                self.turn_id = active[-1]["id"]
        if self.turn_id:
            self.rpc.call("turn/interrupt", {"threadId": self.thread_id, "turnId": self.turn_id})
        self.stopped = True

    def finish_control(self, action):
        # A Human control is an operational result, never an objective completion.
        text = f"Goal {action}. Native goal: {self.goal.get('status') if self.goal else 'cleared'}.\n"
        terminal = {"status": "needs-human-decision", "resultPath": self.state["resultPath"]}
        if self.runtime.inline_result(self.state):
            terminal["resultText"] = text
        else:
            self.runtime.atomic_write(Path(self.state["resultPath"]), text.encode())
        emit({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal)}})

    def setup(self, prompt):
        # The core owns reinjection of developer instructions during compaction,
        # including inside a turn. Never race notifications with a user turn.
        # Every owned start/resume installs today's fixed text, also for sessions
        # created before this protocol. A sidecar hash tracks updates without
        # scanning history markers; the core handles compaction reinjection.
        parts = prompt if isinstance(prompt, PromptParts) else None
        if parts is not None:
            developer_instructions = prompt.fixed
            full_prompt = prompt.full
            prompt = prompt.dynamic
        else:
            # Historical direct adapter callers retain full-prompt semantics.
            developer_instructions = full_prompt = prompt
        if not getattr(self.rpc, "initialized", False):
            self.rpc.call("initialize", {"clientInfo": {"name": "agent_factory", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
            self.rpc.write({"method": "initialized"})
            self.rpc.initialized = True
        if codex_policy.guard_environment(self.state, self.session):
            codex_policy.ensure_guard_trusted(self.rpc, self.session.get("workingDirectory", self.session["projectRoot"]))
        if self.session.get("nativeCapabilities", {}).get("instructionDelivery") is True:
            # Compose effective user/project configuration before creating a thread.
            # A failed/ambiguous read must not silently discard user instructions.
            effective = self.rpc.call("config/read", {"cwd": self.session.get("workingDirectory", self.session["projectRoot"]), "includeLayers": False})
            values = effective.get("config") if isinstance(effective, dict) else None
            if not isinstance(values, dict):
                raise NativeError("Effective Codex configuration is unavailable")
            inherited = values.get("developer_instructions")
            if inherited is not None and not isinstance(inherited, str):
                raise NativeError("Invalid configured developer instructions")
            if inherited:
                developer_instructions = inherited + "\n\n" + developer_instructions
                full_prompt = inherited + "\n\n" + full_prompt
        wants_goal = self.session.get("goalMode") is True or bool(self.state.get("goalAction"))
        if wants_goal and not self.goal_supported:
            raise NativeError("Installed backend lacks Goal APIs; update/select Codex to manage this objective")
        if self.session.get("goal") and not self.goal_supported:
            self.runtime.record_goal_uncertainty(Path(self.state["statePath"]),
                "Goal APIs unavailable: off disables continuation locally but native clearing is unconfirmed; restore Goal support and refresh")
        # Loading a persisted active goal must not race schema installation.
        # Native lifecycle RPCs remain available with continuation disabled.
        # Reasoning items carry an empty summary unless one is requested; the chat shows this summary.
        config = {"features.goals": False, "model_reasoning_summary": "auto"}
        if self.session.get("fast") is False:
            config["service_tier"] = "default"
        if self.session.get("reasoningEffort"):
            config["model_reasoning_effort"] = self.session["reasoningEffort"]
        policy = self.runtime.execution_policy.session_policy(self.session)
        config.update(self.runtime.execution_policy.config(policy, Path(self.state["statePath"]).parent))
        params = {"cwd": self.session.get("workingDirectory", self.session["projectRoot"]),
                  **({"permissions": config["default_permissions"]} if "default_permissions" in config else {"sandbox": policy["sandboxPolicy"]["type"]}),
                  "approvalPolicy": policy["approvalPolicy"], "config": config,
                  "developerInstructions": developer_instructions}
        if self.planning:
            params["developerInstructions"] += "\nHost phase contract: while actual collaboration mode is plan, inspect and plan only, produce the planning output schema and no receipt. In default mode implement and follow the original final result/receipt contract. For taskMode plan, stop after planning; the host records its read-only completion receipt. Other Plan routes automatically transition within this same Work session after a planned result; required unresolved Human choices stop execution.\n"
        if self.session.get("model"):
            params["model"] = self.session["model"]
        prior = self.session.get("sessionId")
        if prior:
            params["threadId"] = prior
        if getattr(self.rpc, "retained_thread", None):
            # Run-scoped environment (parent state and permission snapshot) changes
            # on every send. Restart our owned server before resume so a loaded
            # thread cannot retain the previous run's configuration. Codex has no
            # thread/unload RPC; thread/unsubscribe leaves it loaded for a grace
            # period and therefore cannot provide this configuration boundary.
            self.rpc.restart_owned()
            self.rpc.retained_thread = None
        response = self.rpc.call("thread/resume" if prior else "thread/start", params, timeout=None)
        self.thread_id = response["thread"]["id"]
        if prior and prior != self.thread_id:
            raise NativeError("Codex resumed a different session")
        delivery_record = None
        if parts is not None:
            delivery_path = self.runtime.session_file(
                Path(self.session["projectRoot"]), self.state["agentId"]
            ).with_name("instruction-delivery.json")
            delivery_record = {"version": 1, "threadId": self.thread_id,
                               "fixedSha256": hashlib.sha256(developer_instructions.encode("utf-8")).hexdigest()}
            try:
                previous_delivery = self.runtime.safe_read_json(delivery_path)
            except self.runtime.ContractError as error:
                if error.code != "file_not_found":
                    raise
                previous_delivery = None
            if prior and previous_delivery != delivery_record:
                # Resume restores a history baseline; changing configuration alone
                # need not emit new developer text before the next compaction.
                # Install updates once, before any model turn, as developer text.
                # The durable configuration handles all later compactions.
                try:
                    self.rpc.call("thread/inject_items", {"threadId": self.thread_id, "items": [
                        {"type": "message", "role": "developer", "content": [
                            {"type": "input_text", "text": developer_instructions}]}]})
                except RpcError as error:
                    if error.code != -32601:
                        raise
                    # A definite method-not-found has no ambiguous side effect.
                    # Older backends keep their historical full-prompt delivery.
                    prompt = full_prompt
                    delivery_record = None
        emit({"type": "thread.started", "thread_id": self.thread_id})
        fast = self.session.get("fast") if self.state.get("goalAction") in (None, "resume", "reopen") else None
        models = []
        if fast is True:
            cursor = None
            while True:
                page = self.rpc.call("model/list", {"limit": 100, **({"cursor": cursor} if cursor else {})})
                models.extend(page.get("data", []))
                cursor = page.get("nextCursor")
                if not cursor:
                    break
        tier = service_tier(models, response.get("model", self.session.get("model", "")), fast)
        inputs = [{"type": "text", "text": prompt}]
        inputs.extend({"type": "localImage", "path": image["path"]} for image in self.state.get("imageInputs", []))
        turn = {"threadId": self.thread_id, "input": inputs,
                "cwd": self.session.get("workingDirectory", self.session["projectRoot"]),
                "outputSchema": self.runtime.safe_read_json(Path(self.state["responseSchemaPath"]))}
        if self.session.get("model"):
            turn["model"] = self.session["model"]
        if self.session.get("reasoningEffort"):
            turn["effort"] = self.session["reasoningEffort"]
        if tier is not None and self.session.get("nativeCapabilities", {}).get("fast", True):
            turn["serviceTier"] = tier
        self.result_turn = {key: value for key, value in turn.items() if key != "input"}
        if self.planning:
            if self.session.get("nativeCapabilities", {}).get("plan") is not True:
                raise NativeError("Installed Codex lacks genuine Plan collaboration mode")
            masks = self.rpc.call("collaborationMode/list", {}).get("data", [])
            if not all(any(isinstance(mask, dict) and mask.get("mode") == mode for mask in masks) for mode in ("plan", "default")):
                raise NativeError("Codex does not advertise both Plan and default collaboration modes")
            model = response.get("model") or self.session.get("model")
            if not model:
                raise NativeError("Plan collaboration requires the resolved Codex model")
            settings = {"model": model, "reasoning_effort": self.session.get("reasoningEffort"), "developer_instructions": None}
            self.execution_turn = {**turn, "collaborationMode": {"mode": "default", "settings": settings},
                                   "input": [{"type": "text", "text": "Execute the plan in this same Work session within the already authorized request. Respect unresolved Human decisions. Complete the original result and receipt contract.\n" + prompt}]}
            turn = {**turn, "collaborationMode": {"mode": "plan", "settings": settings},
                    "input": [*inputs, {"type": "text", "text": "This is the planning phase only. Inspect and plan the bounded request without implementation or a Work receipt. Return the planning schema. Use needs-human-decision only for a required unresolved Human choice; otherwise return planned. The host stops after planning for taskMode plan; otherwise it transitions this same session to execution automatically."}],
                    "outputSchema": {"type": "object", "additionalProperties": False,
                                     "properties": {"status": {"type": "string", "enum": ["planned", "needs-human-decision"]}, "plan": {"type": "string", "minLength": 1}},
                                     "required": ["status", "plan"]}}
        activate_goal = False
        if self.goal_enabled:
            self.get_goal()
            action = self.state.get("goalAction")
            if action in ("get", "pause", "cancel", "clear", "disable"):
                self.control(action)
                self.finish_control(action)
                return False
            mode = self.session.get("goalMode")
            if mode is False:
                if self.goal:
                    self.rpc.call("thread/goal/clear", {"threadId": self.thread_id})
                    self.publish_goal(None)
            elif mode is True:
                objective = self.state.get("goalObjective")
                if objective:
                    self.set_goal(objective=objective, status="paused")
                    activate_goal = True
                elif self.goal:
                    activate_goal = self.goal.get("status") == "active" or self.state.get("executionOptions", {}).get("goalMode") is True or action in ("resume", "reopen")
                    if activate_goal:
                        self.set_goal(status="paused")
                else:
                    raise NativeError("Goal needs a nonempty objective (--goal-objective)")
        if activate_goal and self.planning:
            # Keep Goal paused until an actual default-mode transition completes.
            self.goal_start = ({**params, "developerInstructions": full_prompt}, self.execution_turn)
            activate_goal = False
        if activate_goal:
            # Native Goal activation starts without turn/start input. Its owned
            # reload must retain this run's complete request/result contract.
            params["developerInstructions"] = full_prompt
            goal = activate_persisted_goal(self.rpc, self.thread_id, params, turn)
            self.turn_id = None
            self.publish_goal(goal)
            self.goal_started = True
        else:
            result = self.rpc.call("turn/start", turn)
            self.turn_id = result["turn"]["id"]
            if self.planning:
                self.planning_turn_id = self.turn_id
        if delivery_record is not None:
            self.runtime.atomic_write_json(delivery_path, delivery_record)
        return True

    def start_result_repair(self, reason):
        """Start the one repair turn for an invalid final result; False when none is available."""
        if self.repair_turn_id is not None or self.result_turn is None or self.planning:
            return False
        request = RESULT_REPAIR_REQUEST.format(reason=reason)
        if self.runtime.structured_receipt(self.state):
            request += RECEIPT_REPAIR_REQUEST
        try:
            result = self.rpc.call("turn/start", {**self.result_turn, "input": [{"type": "text", "text": request}]})
        except RpcError:
            return False  # Report the original contract failure, not the failed repair.
        self.repair_turn_id = self.turn_id = result["turn"]["id"]
        self.last_message = None
        emit({"type": "native.commentary",
              "text": "The final response did not match the result contract; the runtime requested it once more."})
        return True

    def finish_turn(self, turn_id=None):
        """Emit the terminal result. False means a repair turn started and the run continues."""
        if not self.last_message:
            raise NativeError("Native turn returned no final result")
        message = self.last_message
        try:
            terminal = json.loads(message)
        except (json.JSONDecodeError, TypeError) as error:
            failure = (
                "Native final result is not valid JSON "
                f"(stage=finish_turn, turn={turn_id or self.turn_id or 'unknown'}, "
                f"characters={len(message) if isinstance(message, str) else 'non-text'}). "
                "The Goal status does not prove managed result completion; the final response must match the result schema."
            )
            if self.start_result_repair(failure):
                return False
            raise NativeError(failure) from error
        if isinstance(terminal, dict) and isinstance(terminal.get("resultText"), str):
            terminal["resultText"], questions = extract_markers(terminal["resultText"])
            for question in questions:
                emit(question)
            message = json.dumps(terminal, ensure_ascii=False)
        try:
            self.runtime.validate_terminal_result(terminal, self.state)
        except self.runtime.ContractError as error:
            if self.start_result_repair(error.message):
                return False
            raise NativeError(error.message) from error
        if self.goal_started and (not self.goal or self.goal.get("status") != "complete"):
            # Never rewrite a reported failure or a real Human decision as success.
            if terminal["status"] == "completed":
                status = self.goal.get("status") if self.goal else "cleared"
                terminal["status"] = "needs-human-decision" if status in {"blocked", "paused"} else "failed"
                terminal["decisionKind"] = "clarification" if terminal["status"] == "needs-human-decision" else None
                terminal["resultText"] = f"Native Goal stopped without completion ({status}).\n" + terminal["resultText"]
                message = json.dumps(terminal)
        if terminal["status"] == "completed" and self.runtime.structured_receipt(self.state):
            # The runtime never fills receipt values. Ask the Agent once, schema-constrained; a result
            # still lacking them is emitted as returned and fails as `receipt_missing` at the run boundary.
            defect = receipt_judgment_defect(terminal)
            if defect and self.start_result_repair(f"the result is `completed` but {defect}."):
                return False
        emit({"type": "item.completed", "item": {"type": "agent_message", "text": message}})
        return True

    def finish_latest_goal_turn(self, *, force=False):
        """Join current native state to consumed events for the same latest turn.

        RPC reads can overtake our event consumer. A terminal goal snapshot is
        not a completion marker for whichever turn happened to be consumed last.
        """
        if self.planning or self.goal_transition_id:
            return False
        if self.repair_turn_id is not None and self.repair_turn_id not in self.completed_turns:
            return False  # The repair turn owns the result; never re-judge the turn it replaces.
        now = time.monotonic()
        if not force and now < self.next_completion_check:
            return False
        # New completions bypass coalescing; idle retries retain recovery.
        goal = self.get_goal()
        if goal and goal.get("status") == "active":
            return False
        thread = self.rpc.call("thread/read", {"threadId": self.thread_id, "includeTurns": True}).get("thread", {})
        self.next_completion_check = time.monotonic() + 1.0
        if thread.get("id") != self.thread_id:
            raise NativeError("Native completion history belongs to a different thread")
        turns = thread.get("turns")
        if not isinstance(turns, list) or not turns:
            raise NativeError("Native completion history has no applicable turn")
        latest = turns[-1]
        latest_id, status = latest.get("id"), latest.get("status")
        if not isinstance(latest_id, str):
            raise NativeError("Native latest turn has no identity")
        if status == "inProgress" or thread.get("status", {}).get("type") == "active":
            return False
        # Wait for the authoritative latest turn's own completion and item
        # events, not queue emptiness or a fixed delay. Earlier turns cannot win.
        if latest_id not in self.completed_turns:
            return False
        if status != "completed" or self.completed_turns[latest_id] != status:
            raise NativeError(f"Native final turn {status}: {json.dumps(latest.get('error'))[:2000]}")
        self.last_message = self.turn_messages.get(latest_id)
        return self.finish_turn(turn_id=latest_id)

    def run(self, prompt):
        try:
            if not self.setup(prompt):
                return
            from storage.files import ChangedJsonReader
            control_reader = ChangedJsonReader(Path(self.state["statePath"]), self.runtime.safe_read_json)
            while True:
                current = control_reader.read()
                control = current.get("goalControl")
                if current.get("cancelRequested"):
                    if self.goal_enabled:
                        self.control("pause")
                    return
                if control and control.get("id") != self.control_id:
                    self.control_id = control["id"]
                    self.control(control["action"])
                    emit({"type": "goal.control", "controlId": self.control_id, "action": control["action"]})
                    if control["action"] != "get":
                        self.finish_control(control["action"])
                        return
                try:
                    event = self.rpc.event()
                except queue.Empty:
                    for pending in self.deltas.flush():
                        emit(pending)
                    # A native idle/status transition can lag turn completion.
                    # Recheck authoritative history, never treat an empty queue
                    # itself as evidence that all native work is complete.
                    if self.goal_enabled and self.completed_turns and (self.goal is None or self.goal.get("status") != "active"):
                        if time.monotonic() >= self.next_idle_goal_check:
                            self.next_idle_goal_check = time.monotonic() + 1.0
                            if self.finish_latest_goal_turn():
                                return
                    continue
                method, params = event.get("method"), event.get("params", {})
                if params.get("threadId") not in (None, self.thread_id):
                    continue
                if self.handle(method, params):
                    return
        except Exception:
            # Best effort only: state/events report an unconfirmed pause if RPC fails.
            if self.thread_id and self.goal_enabled and self.goal and self.goal.get("status") == "active":
                try:
                    self.set_goal(status="paused")
                except Exception:
                    self.runtime.record_goal_uncertainty(Path(self.state["statePath"]), "Native pause unconfirmed; refresh Goal before reopening")
            raise


def bridge_services():
    """Explicit services consumed by the native bridge; no CLI orchestrator import."""
    from types import SimpleNamespace
    from storage import paths as runtime_paths  # noqa: F401 - collected through locals() below
    from adapters.codex import policy as execution_policy  # noqa: F401 - collected through locals() below
    from adapters.codex.control import record_goal_uncertainty  # noqa: F401 - collected through locals() below
    from storage.errors import ContractError  # noqa: F401 - collected through locals() below
    from storage.files import atomic_write, atomic_write_json, safe_read_json, session_file, update_json  # noqa: F401 - collected through locals() below
    from system.containment import now  # noqa: F401 - collected through locals() below
    from system.transport import inline_result, structured_receipt, validate_terminal_result  # noqa: F401 - collected through locals() below
    return SimpleNamespace(**{name: value for name, value in locals().items() if name != "SimpleNamespace"})


# A pool is owned by the extension's stdin pipe, never by an individual run.
# Workers retain their own containment and are exclusively leased per agent.
def connection_worker():
    runtime = bridge_services()
    rpc = None
    current = {}
    try:
        for line in sys.stdin:
            request = json.loads(line)
            state = runtime.safe_read_json(Path(request["statePath"]))
            runtime.runtime_paths.bind(state["runtimeBinding"])
            session = runtime.safe_read_json(Path(state["nativeSessionPath"]))
            current.update(state=state, session=session)
            if rpc is None:
                def factory():
                    command, environment = codex_policy.app_server(current["session"], current["state"])
                    return subprocess.Popen(command,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                        text=True, encoding="utf-8", bufsize=1, env=environment)
                rpc = Rpc(factory(), process_factory=factory)
                rpc.guard_signature = codex_policy.guard_signature(state, session)
            elif rpc.guard_signature != codex_policy.guard_signature(state, session):
                # The hook and its arming variable are process-wide; switch them with the run's mode.
                rpc.restart_owned()
                rpc.guard_signature = codex_policy.guard_signature(state, session)
            prompt = PromptParts.decode(request["prompt"]) if request["parts"] else request["prompt"]
            bridge = Bridge(runtime, session, state, rpc)
            bridge.run(prompt)
            rpc.retained_thread = bridge.thread_id
            # A cancelled turn must not continue in a retained server.
            if runtime.safe_read_json(Path(request["statePath"])).get("cancelRequested"):
                emit({"poolDone": True, "reusable": False})
                return 0
            emit({"poolDone": True, "reusable": True})
            # Complete the accepted request before preparing the next connection.
            # Only initialize a fresh server here: no thread, model call or tool.
            # A subsequent request remains serial and applies its own configuration.
            try:
                rpc.restart_owned()
                rpc.retained_thread = None
            except Exception as error:
                # The preceding terminal response has already been delivered.
                # Do not emit another result or replay a queued request on failure.
                print(f"Codex connection preparation failed: {error}", file=sys.stderr, flush=True)
                return 1
    except Exception as error:
        emit({"type": "error", "message": str(error)[:4000]})
        emit({"poolDone": True, "reusable": False, "failed": True})
        return 1
    finally:
        if rpc is not None:
            with contextlib.suppress(Exception):
                rpc.process.stdin.close()
                rpc.process.terminate()
                rpc.process.wait(timeout=2)
    return 0


def pool_identity(state, session):
    # Include effective policy/configuration and runtime binding; never reuse a
    # loaded thread after privilege, provider, model, working directory or role changes.
    fields = ("codex", "projectRoot", "workingDirectory", "executionPolicy", "model",
              "reasoningEffort", "fast", "role", "taskMode", "nativeCapabilities", "goalMode")
    values = {key: session.get(key) for key in fields}
    return json.dumps([state["runtimeBinding"], state["agentId"], values], sort_keys=True)


def connection_host():
    import secrets
    import socket
    from system.containment import spawn_contained_process, release_contained_process, terminate_attempt_group
    token = secrets.token_hex(32)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    workers, lock = {}, threading.RLock()
    closing = threading.Event()

    def stop(worker):
        terminate_attempt_group(worker["process"], worker["identity"])
        for stream in (worker["process"].stdin, worker["process"].stdout):
            with contextlib.suppress(Exception):
                stream.close()

    def shutdown():
        # EOF is the extension lifetime signal, including crashes and reloads.
        sys.stdin.buffer.read()
        closing.set()
        # Closing a UI host must not cancel accepted background work. Drain
        # active leases; their run proxies still own cancellation and completion.
        while True:
            with lock:
                idle = [(key, worker) for key, worker in workers.items() if not worker["busy"]]
                for key, _ in idle:
                    del workers[key]
                active = bool(workers)
            for _, worker in idle:
                with contextlib.suppress(Exception):
                    stop(worker)
            if not active:
                break
            time.sleep(0.1)
        os._exit(0)

    def serve(connection):
        worker = None
        leased = False
        finished = threading.Event()
        disconnected = threading.Event()
        wire = connection.makefile("rwb")
        try:
            request = json.loads(wire.readline())
            if not secrets.compare_digest(str(request.pop("token", "")), token):
                raise NativeError("Invalid connection pool credential")
            runtime = bridge_services()
            state = runtime.safe_read_json(Path(request["statePath"]))
            session = runtime.safe_read_json(Path(state["nativeSessionPath"]))
            key = json.dumps([state["runtimeBinding"], state["agentId"]], sort_keys=True)
            fingerprint = pool_identity(state, session)
            with lock:
                if closing.is_set():
                    raise NativeError("Connection host is closing")
                worker = workers.get(key)
                if worker and worker["busy"]:
                    worker = None
                    raise NativeError("Agent connection already has an active request")
                if worker and (worker["fingerprint"] != fingerprint or worker["process"].poll() is not None):
                    stop(worker)
                    del workers[key]
                    worker = None
                if worker is None:
                    environment = {**os.environ, "AGENT_FACTORY_EXECUTION_POLICY": json.dumps(runtime.execution_policy.session_policy(session))}
                    environment.pop("AGENT_FACTORY_CODEX_POOL", None)
                    process, identity, barrier = spawn_contained_process(
                        [sys.executable, str(Path(__file__).resolve()), "--connection-worker"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                        text=True, encoding="utf-8", env=environment,
                        cwd=session.get("workingDirectory", session["projectRoot"]))
                    worker = {"process": process, "identity": identity, "fingerprint": fingerprint, "busy": True}
                    workers[key] = worker
                    release_contained_process(process, identity, barrier)
                worker["busy"] = True
                leased = True

            def watch_disconnect():
                # The client sends nothing after its request. EOF during a turn
                # kills the worker's entire containment, not just the proxy.
                try:
                    connection.recv(1)
                except OSError:
                    pass
                disconnected.set()
                if not finished.is_set():
                    with contextlib.suppress(Exception):
                        stop(worker)
            threading.Thread(target=watch_disconnect, daemon=True).start()
            worker["process"].stdin.write(json.dumps(request) + "\n")
            worker["process"].stdin.flush()
            reusable = False
            for output in worker["process"].stdout:
                event = json.loads(output)
                if event.get("poolDone"):
                    reusable = event.get("reusable") is True and not disconnected.is_set() and not closing.is_set()
                    # Cleanup must complete before acknowledging a cancelled turn.
                    if not reusable:
                        stop(worker)
                    finished.set()
                    with lock:
                        wire.write(output.encode("utf-8"))
                        wire.flush()
                        if reusable:
                            worker["busy"] = False
                        elif workers.get(key) is worker:
                            del workers[key]
                    break
                wire.write(output.encode("utf-8"))
                wire.flush()
            else:
                raise NativeError("Retained Codex worker closed before completion; request was not replayed")
        except Exception as error:
            if leased:
                with contextlib.suppress(Exception):
                    stop(worker)
                with lock:
                    if workers.get(key) is worker:
                        del workers[key]
            finished.set()
            with contextlib.suppress(Exception):
                wire.write((json.dumps({"type": "error", "message": str(error)}) + "\n").encode())
                wire.flush()
        finally:
            finished.set()
            with contextlib.suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            wire.close()
            connection.close()

    threading.Thread(target=shutdown, daemon=True).start()
    emit({"port": listener.getsockname()[1], "token": token})
    while not closing.is_set():
        connection, _ = listener.accept()
        threading.Thread(target=serve, args=(connection,), daemon=True).start()
    return 0


def pooled_request():
    import socket
    endpoint = json.loads(os.environ["AGENT_FACTORY_CODEX_POOL"])
    request = {"statePath": str(Path(sys.argv[1]).resolve()), "prompt": sys.stdin.read(),
               "parts": sys.argv[2:] == ["--prompt-parts"], "token": endpoint["token"]}
    # No automatic replay: a disconnected request may already have started work.
    with socket.create_connection(("127.0.0.1", endpoint["port"])) as connection:
        with connection.makefile("rwb") as wire:
            wire.write((json.dumps(request) + "\n").encode())
            wire.flush()
            for line in wire:
                event = json.loads(line)
                if event.get("poolDone"):
                    return 1 if event.get("failed") else 0
                sys.stdout.write(line.decode("utf-8"))
                sys.stdout.flush()
    raise NativeError("Connection host closed before completion; request was not replayed")


def main():
    if sys.argv[1:] == ["--connection-host"]:
        return connection_host()
    if sys.argv[1:] == ["--connection-worker"]:
        return connection_worker()
    runtime = bridge_services()
    state = runtime.safe_read_json(Path(sys.argv[1]))
    runtime.runtime_paths.bind(state["runtimeBinding"])
    session = runtime.safe_read_json(Path(state["nativeSessionPath"]))
    if (os.environ.get("AGENT_FACTORY_CODEX_POOL") and session.get("role") == "main"
            and not session.get("goalMode") and not session.get("goal") and not state.get("goalAction")):
        return pooled_request()
    prompt = sys.stdin.read()
    if sys.argv[2:] == ["--prompt-parts"]:
        prompt = PromptParts.decode(prompt)
    elif sys.argv[2:]:
        raise NativeError("Unsupported native prompt transport")
    def process_factory():
        command, environment = codex_policy.app_server(session, state)
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                                text=True, encoding="utf-8", bufsize=1, env=environment)
    rpc = Rpc(process_factory(), process_factory=process_factory)
    try:
        Bridge(runtime, session, state, rpc).run(prompt)
        return 0
    except Exception as error:
        emit({"type": "error", "message": str(error)[:4000]})
        return 1
    finally:
        # No detached service: parent containment owns this process and descendants.
        with contextlib.suppress(Exception):
            rpc.process.stdin.close()
            rpc.process.terminate()
            rpc.process.wait(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
