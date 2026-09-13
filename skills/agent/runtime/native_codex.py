"""Local stdio Codex adapter; execution and containment remain exec.py-owned."""
from __future__ import annotations

import contextlib
import fcntl
import os
import shutil
import stat
import importlib.util
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


class NativeError(Exception):
    pass


def _probe_capabilities(codex: str) -> dict:
    """Inspect this executable's protocol, never infer support from wrapper flags."""
    supported = {"model": True, "reasoning": True, "fast": False, "goal": False}
    reason = None
    try:
        with tempfile.TemporaryDirectory(prefix="agent-factory-codex-schema-") as directory:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run([codex, "app-server", "generate-json-schema", "--experimental", "--out", directory],
                                        stdout=output, stderr=output, timeout=12, check=False)
                if result.returncode:
                    raise NativeError("installed Codex cannot generate the experimental app-server schema")
            def schema(name):
                path = Path(directory) / name
                if path.stat().st_size > 8 * 1024 * 1024:
                    raise NativeError("Codex schema exceeds the inspection bound")
                return json.loads(path.read_text())
            for feature in ("fast", "goal"):
                try:
                    turn = schema("v2/TurnStartParams.json")["properties"]
                    if feature == "fast":
                        start = schema("v2/ThreadStartParams.json")["properties"]
                        resume = schema("v2/ThreadResumeParams.json")["properties"]
                        catalog = schema("v2/ModelListResponse.json")["definitions"]["Model"]["properties"]
                        supported[feature] = all("serviceTier" in fields for fields in (start, resume, turn)) and "serviceTiers" in catalog
                    else:
                        methods = json.dumps(schema("ClientRequest.json"))
                        statuses = schema("v2/ThreadGoalSetParams.json")["definitions"]["ThreadGoalStatus"]["enum"]
                        supported[feature] = all(method in methods for method in ("thread/goal/set", "thread/goal/get", "thread/goal/clear")) and all(status in statuses for status in ("active", "paused", "complete")) and "outputSchema" in turn
                except (OSError, ValueError, KeyError, NativeError):
                    supported[feature] = False

    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired, NativeError) as error:
        reason = f"Native Fast/Goal requires a Codex build with service-tier catalog and thread/goal APIs: {error}. Update/select Codex, then retry."
    if not all(supported.values()) and reason is None:
        reason = "Installed Codex protocol lacks required native fields. Update/select Codex, then retry."
    return {"schemaVersion": "0.1.0", "kind": "execution-capabilities", "backend": "codex-app-server-stdio",
            "submit": supported, "send": dict(supported), "diagnostic": reason}



# One bounded entry per operational home; account/model availability is never stored.
CAPABILITY_CACHE_TTL = 60


def _capability_identity(codex):
    executable = shutil.which(codex)
    if not executable:
        raise OSError("Codex executable not found")
    path = Path(executable).resolve(strict=True)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise OSError("Codex executable is not a regular file")
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino,
            "size": info.st_size, "mtimeNs": info.st_mtime_ns, "ctimeNs": info.st_ctime_ns,
            "codexHome": str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve())}


def _cached_capabilities(paths, file, identity):
    try:
        value = paths.read(file)
        if (not isinstance(value, dict) or set(value) != {"version", "identity", "created", "capabilities"}
                or value["version"] != 1 or value["identity"] != identity
                or type(value["created"]) not in (int, float)
                or not 0 <= time.time() - value["created"] < CAPABILITY_CACHE_TTL):
            return None
        caps = value["capabilities"]
        expected = {"model": True, "reasoning": True, "fast": True, "goal": True}
        if (not isinstance(caps, dict) or set(caps) != {"schemaVersion", "kind", "backend", "submit", "send", "diagnostic"}
                or caps["schemaVersion"] != "0.1.0" or caps["kind"] != "execution-capabilities"
                or caps["backend"] != "codex-app-server-stdio" or caps["diagnostic"] is not None):
            return None
        for verb in ("submit", "send"):
            fields = caps[verb]
            if not isinstance(fields, dict) or fields != expected or any(type(v) is not bool for v in fields.values()):
                return None
        return caps
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return None


def inspect_capabilities(codex: str, *, refresh: bool = False, runtime_home=None) -> dict:
    """Reuse only recent successful protocol probes for this binary and Codex home."""
    if os.environ.get("AF_CODEX_CAPABILITY_CACHE") == "0":
        return _probe_capabilities(codex)
    result = None
    try:
        import paths
        identity = _capability_identity(codex)
        directory = paths.home_path(runtime_home) / "cache" / "native-capabilities"
        file = directory / "capabilities.json"
        cached = _cached_capabilities(paths, file, identity)
        if cached is not None:
            return cached
        if not refresh:
            return _probe_capabilities(codex)
        paths.mkdir(directory)
        # A short bounded wait coalesces ordinary concurrent probes; a stuck
        # writer cannot add its full probe timeout to another caller's latency.
        fd = os.open(directory / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("unsafe capability cache lock")
            deadline = time.monotonic() + .5
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise OSError("capability cache lock busy")
                    time.sleep(.01)
            cached = _cached_capabilities(paths, file, identity)
            if cached is not None:
                return cached
            result = _probe_capabilities(codex)
            # Missing/failed/partial schemas are retried next time. A replacement
            # during inspection cannot publish support for the old identity.
            if result["diagnostic"] is None and _capability_identity(codex) == identity:
                paths.write(file, {"version": 1, "identity": identity, "created": time.time(), "capabilities": result})
            return result
        finally:
            os.close(fd)
    except (OSError, ValueError, ImportError):
        return result if result is not None else _probe_capabilities(codex)


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


class Rpc:
    """Bounded JSONL RPC; unsolicited events are retained while awaiting replies."""
    def __init__(self, process, observer=None, process_factory=None):
        self.process_factory = process_factory
        self.observer = observer
        self.process = process
        self.incoming = queue.Queue(maxsize=128)
        self.pending = []
        self.serial = 0
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
        factory, observer = self.process_factory, self.observer
        if observer:
            observer("owned-restart", {"stoppedPid": old_pid, "pending": self.pending})
        self.__init__(factory(), observer=observer, process_factory=factory)
        self.call("initialize", {"clientInfo": {"name": "agent_factory", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
        self.write({"method": "initialized"})

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(1024 * 1024 + 1)
                if not line:
                    raise NativeError("Codex app-server closed its event stream")
                if len(line.encode()) > 1024 * 1024:
                    raise NativeError("Codex app-server event exceeds 1 MiB")
                self.incoming.put(json.loads(line))
        except Exception as error:
            self.incoming.put(error)

    def write(self, value):
        if self.observer is not None:
            self.observer("send", value)
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def receive(self, timeout=0.2):
        value = self.incoming.get(timeout=timeout)
        if isinstance(value, Exception):
            if self.observer is not None:
                self.observer("read-error", {"message": str(value)})
            raise value
        if self.observer is not None:
            self.observer("receive", value)
        if not isinstance(value, dict):
            raise NativeError("Invalid app-server message")
        if "method" in value and "id" in value:
            # Interactive approvals cannot be silently granted by a background host.
            self.write({"id": value["id"], "error": {"code": -32601, "message": "Interactive request unsupported in managed run; use Human input"}})
            raise NativeError(f"Codex requested interactive input: {value['method']}")
        return value

    def call(self, method, params, timeout=15):
        self.serial += 1
        request_id = self.serial
        self.write({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = self.receive(min(0.2, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if value.get("id") == request_id:
                if "error" in value:
                    raise NativeError(f"{method}: {json.dumps(value['error'])[:2000]}")
                return value.get("result", {})
            if len(self.pending) >= 128:
                raise NativeError("Too many pending app-server notifications")
            self.pending.append(value)
        raise NativeError(f"{method} timed out; do not replay an ambiguous operation")

    def event(self):
        return self.pending.pop(0) if self.pending else self.receive()


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


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
    return rpc.call("thread/goal/set", {"threadId": thread_id, "status": "active"}).get("goal")


class Bridge:
    def __init__(self, runtime, session, state, rpc):
        self.runtime, self.session, self.state, self.rpc = runtime, session, state, rpc
        self.thread_id = None
        self.turn_id = None
        self.goal = None
        self.last_message = None
        self.turn_messages = {}
        self.completed_turns = {}
        self.control_id = None
        self.goal_supported = session.get("nativeCapabilities", {}).get("goal", True)
        self.goal_enabled = session.get("role") == "main" and self.goal_supported and (
            session.get("goalMode") is not None or bool(session.get("goal")) or bool(state.get("goalAction")))
        self.stopped = False

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
        self.rpc.call("initialize", {"clientInfo": {"name": "agent_factory", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
        self.rpc.write({"method": "initialized"})
        wants_goal = self.session.get("goalMode") is True or bool(self.state.get("goalAction"))
        if wants_goal and not self.goal_supported:
            raise NativeError("Installed backend lacks Goal APIs; update/select Codex to manage this objective")
        if self.session.get("goal") and not self.goal_supported:
            self.runtime.record_goal_uncertainty(Path(self.state["statePath"]),
                "Goal APIs unavailable: off disables continuation locally but native clearing is unconfirmed; restore Goal support and refresh")
        # Loading a persisted active goal must not race schema installation.
        # Native lifecycle RPCs remain available with continuation disabled.
        config = {"features.goals": False}
        if self.session.get("fast") is False:
            config["service_tier"] = "default"
        if self.session.get("reasoningEffort"):
            config["model_reasoning_effort"] = self.session["reasoningEffort"]
        policy = self.runtime.execution_policy.session_policy(self.session)
        config.update(self.runtime.execution_policy.config(policy, Path(self.state["statePath"]).parent))
        params = {"cwd": self.session["projectRoot"],
                  **({"permissions": config["default_permissions"]} if "default_permissions" in config else {"sandbox": policy["sandboxPolicy"]["type"]}),
                  "approvalPolicy": policy["approvalPolicy"], "config": config,
                  "developerInstructions": prompt}
        if self.session.get("model"):
            params["model"] = self.session["model"]
        prior = self.session.get("sessionId")
        if prior:
            params["threadId"] = prior
        response = self.rpc.call("thread/resume" if prior else "thread/start", params, timeout=float(self.session["startTimeout"]))
        self.thread_id = response["thread"]["id"]
        if prior and prior != self.thread_id:
            raise NativeError("Codex resumed a different session")
        emit({"type": "thread.started", "thread_id": self.thread_id})
        fast = self.session.get("fast") if self.state.get("goalAction") in (None, "resume", "reopen") else None
        models = []
        if fast is True:
            cursor = None
            for _ in range(20):
                page = self.rpc.call("model/list", {"limit": 100, **({"cursor": cursor} if cursor else {})})
                models.extend(page.get("data", []))
                cursor = page.get("nextCursor")
                if not cursor:
                    break
            if cursor:
                raise NativeError("Codex model catalog exceeds pagination bound")
        tier = service_tier(models, response.get("model", self.session.get("model", "")), fast)
        inputs = [{"type": "text", "text": prompt}]
        inputs.extend({"type": "localImage", "path": image["path"]} for image in self.state.get("imageInputs", []))
        turn = {"threadId": self.thread_id, "input": inputs,
                "outputSchema": self.runtime.safe_read_json(Path(self.state["responseSchemaPath"]))}
        if self.session.get("model"):
            turn["model"] = self.session["model"]
        if self.session.get("reasoningEffort"):
            turn["effort"] = self.session["reasoningEffort"]
        if tier is not None and self.session.get("nativeCapabilities", {}).get("fast", True):
            turn["serviceTier"] = tier
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
                    raise NativeError("Goal needs an objective of 1–4000 characters (--goal-objective)")
        if activate_goal:
            goal = activate_persisted_goal(self.rpc, self.thread_id, params, turn)
            self.turn_id = None
            self.publish_goal(goal)
        else:
            result = self.rpc.call("turn/start", turn)
            self.turn_id = result["turn"]["id"]
        return True

    def finish_turn(self):
        if not self.last_message:
            raise NativeError("Native turn returned no final result")
        message = self.last_message
        terminal = json.loads(message)
        try:
            self.runtime.validate_terminal_result(terminal, self.state)
        except self.runtime.ContractError as error:
            raise NativeError(error.message) from error
        if self.goal and self.goal.get("status") != "complete":
            terminal = json.loads(message)
            terminal["status"] = "needs-human-decision"
            message = json.dumps(terminal)
        emit({"type": "item.completed", "item": {"type": "agent_message", "text": message}})

    def finish_latest_goal_turn(self):
        """Join current native state to consumed events for the same latest turn.

        RPC reads can overtake our event consumer. A terminal goal snapshot is
        not a completion marker for whichever turn happened to be consumed last.
        """
        goal = self.get_goal()
        if goal and goal.get("status") == "active":
            return False
        thread = self.rpc.call("thread/read", {"threadId": self.thread_id, "includeTurns": True}).get("thread", {})
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
        self.finish_turn()
        return True

    def run(self, prompt):
        try:
            if not self.setup(prompt):
                return
            while True:
                current = self.runtime.safe_read_json(Path(self.state["statePath"]))
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
                    # A native idle/status transition can lag turn completion.
                    # Recheck authoritative history, never treat an empty queue
                    # itself as evidence that all native work is complete.
                    if self.goal_enabled and self.completed_turns and (self.goal is None or self.goal.get("status") != "active"):
                        if self.finish_latest_goal_turn():
                            return
                    continue
                method, params = event.get("method"), event.get("params", {})
                if params.get("threadId") not in (None, self.thread_id):
                    continue
                if method == "thread/goal/updated":
                    self.publish_goal(params.get("goal"))
                    if self.completed_turns and self.goal and self.goal.get("status") != "active":
                        if self.finish_latest_goal_turn():
                            return
                elif method == "thread/goal/cleared":
                    self.publish_goal(None)
                    if self.completed_turns and self.finish_latest_goal_turn():
                        return
                elif method == "thread/status/changed":
                    if self.goal_enabled and self.completed_turns and params.get("status", {}).get("type") == "idle":
                        if self.finish_latest_goal_turn():
                            return
                elif method == "turn/started":
                    self.turn_id = params["turn"]["id"]
                    self.last_message = None
                    emit({"type": "turn.started", "turn_id": self.turn_id})
                elif method in ("item/started", "item/completed"):
                    item = dict(params.get("item", {}))
                    kind = item.get("type")
                    if kind == "agentMessage":
                        if method == "item/completed" and item.get("phase") != "commentary":
                            owner = params.get("turnId", self.turn_id)
                            if not isinstance(owner, str):
                                raise NativeError("Native final message has no turn identity")
                            self.turn_messages[owner] = item.get("text")
                        # Retain commentary; terminal messages are emitted only at run end.
                        if item.get("phase") == "commentary":
                            emit({"type": "native.commentary", "text": item.get("text", "")})
                    else:
                        item["type"] = {"commandExecution": "command_execution", "fileChange": "file_change", "mcpToolCall": "mcp_tool_call"}.get(kind, kind)
                        if "exitCode" in item:
                            item["exit_code"] = item.pop("exitCode")
                        emit({"type": method.replace("/", "."), "item": item})
                elif method == "turn/completed":
                    turn = params["turn"]
                    if self.turn_id == turn["id"]:
                        self.turn_id = None
                    self.completed_turns[turn["id"]] = turn.get("status")
                    self.last_message = self.turn_messages.get(turn["id"])
                    emit({"type": "turn.completed", "turn_id": turn["id"]})
                    if turn.get("status") != "completed":
                        raise NativeError(f"Native turn {turn.get('status')}: {json.dumps(turn.get('error'))[:2000]}")
                    if self.goal_enabled:
                        if self.finish_latest_goal_turn():
                            return
                        emit({"type": "goal.continuing", "thread_id": self.thread_id})
                        continue
                    self.finish_turn()
                    return
                elif method == "error":
                    if not params.get("willRetry"):
                        raise NativeError(json.dumps(params.get("error", params))[:2000])
        except Exception:
            # Best effort only: state/events report an unconfirmed pause if RPC fails.
            if self.thread_id and self.goal_enabled and self.goal and self.goal.get("status") == "active":
                try:
                    self.set_goal(status="paused")
                except Exception:
                    self.runtime.record_goal_uncertainty(Path(self.state["statePath"]), "Native pause unconfirmed; refresh Goal before reopening")
            raise


def main():
    spec = importlib.util.spec_from_file_location("agent_factory_exec", Path(__file__).parents[1] / "scripts" / "exec.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    state = runtime.safe_read_json(Path(sys.argv[1]))
    runtime.runtime_paths.bind(state["runtimeBinding"])
    session = runtime.safe_read_json(Path(state["nativeSessionPath"]))
    def process_factory():
        return subprocess.Popen([session["codex"], "app-server", "--listen", "stdio://"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                                text=True, encoding="utf-8", bufsize=1)
    rpc = Rpc(process_factory(), process_factory=process_factory)
    try:
        Bridge(runtime, session, state, rpc).run(sys.stdin.read())
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
