"""Translate Codex app-server item notifications into runtime events."""
from __future__ import annotations

import json
from pathlib import Path

from execution.streaming import JsonStringField
from adapters.codex.capabilities import NativeError

# app-server item types -> runtime item types shared with the Claude adapter and the extension.
ITEM_TYPES = {"commandExecution": "command_execution", "fileChange": "file_change", "mcpToolCall": "mcp_tool_call"}


def item_event(method: str, item: dict) -> dict:
    """item/started|completed for a non-message item as an item.started|completed runtime event."""
    item = dict(item)
    item["type"] = ITEM_TYPES.get(item.get("type"), item.get("type"))
    if "exitCode" in item:
        item["exit_code"] = item.pop("exitCode")
    return {"type": method.replace("/", "."), "item": item}


class CommentaryText:
    """Stream plain commentary verbatim or extract resultText from schema JSON."""

    def __init__(self):
        self.buffer = ""
        self.decoder = None

    def feed(self, fragment: str) -> str:
        if self.decoder is False:
            return fragment
        if self.decoder is not None:
            return self.decoder.feed(fragment)
        self.buffer += fragment
        stripped = self.buffer.lstrip()
        if not stripped:
            return ""
        if not stripped.startswith("{"):
            text, self.buffer, self.decoder = self.buffer, "", False
            return text
        self.decoder = JsonStringField()
        text, self.buffer = self.buffer, ""
        return self.decoder.feed(text)


def agent_message_stream(item: dict):
    """Live-preview stream for an agent message, unwrapping structured resultText."""
    return ("commentary", CommentaryText()) if item.get("phase") == "commentary" else ("final", JsonStringField())


def commentary_text(item: dict) -> str:
    """Return the authoritative commentary text without exposing its schema envelope."""
    text = item.get("text", "")
    if not isinstance(text, str):
        return ""
    try:
        structured = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    result = structured.get("resultText") if isinstance(structured, dict) else None
    return result if isinstance(result, str) else text


def emit(event):
    from adapters.codex import transport
    transport.emit(event)


def activate_persisted_goal(*args, **kwargs):
    from adapters.codex import transport
    return transport.activate_persisted_goal(*args, **kwargs)


class NotificationHandlers:
    """app-server notification handlers mixed into the transport Bridge, which owns the state."""

    # app-server notification -> handler; a handler returning True ends the run.
    HANDLERS = {
        "thread/tokenUsage/updated": "on_token_usage",
        "thread/goal/updated": "on_goal_updated",
        "thread/goal/cleared": "on_goal_cleared",
        "thread/status/changed": "on_status_changed",
        "turn/started": "on_turn_started",
        "item/started": "on_item",
        "item/completed": "on_item",
        "item/agentMessage/delta": "on_agent_message_delta",
        "turn/completed": "on_turn_completed",
        "error": "on_error",
    }

    def handle(self, method, params):
        handler = self.HANDLERS.get(method)
        return bool(handler and getattr(self, handler)(method, params))

    def on_token_usage(self, method, params):
        # Ignore restored history notifications from earlier managed runs.
        owner = params.get("turnId")
        if isinstance(owner, str) and (owner == self.turn_id or owner in self.completed_turns):
            emit({"type": "token.usage", "turn_id": owner,
                  "tokenUsage": params.get("tokenUsage")})
        return False

    def on_goal_updated(self, method, params):
        self.publish_goal(params.get("goal"))
        if self.completed_turns and self.goal and self.goal.get("status") != "active":
            if self.finish_latest_goal_turn():
                return True
        return False

    def on_goal_cleared(self, method, params):
        self.publish_goal(None)
        if self.completed_turns and self.finish_latest_goal_turn():
            return True
        return False

    def on_status_changed(self, method, params):
        if self.goal_enabled and self.completed_turns and params.get("status", {}).get("type") == "idle":
            if self.finish_latest_goal_turn():
                return True
        return False

    def on_turn_started(self, method, params):
        self.turn_id = params["turn"]["id"]
        self.last_message = None
        emit({"type": "turn.started", "turn_id": self.turn_id})
        return False

    def on_item(self, method, params):
        item = dict(params.get("item", {}))
        kind = item.get("type")
        if kind == "agentMessage":
            identity = str(item.get("id", ""))
            if method == "item/started":
                # Current Codex versions can schema-wrap commentary as well as the final message.
                self.streams[identity] = agent_message_stream(item)
            else:
                for pending in self.deltas.flush(identity):
                    emit(pending)
                self.streams.pop(identity, None)
            if method == "item/completed" and item.get("phase") != "commentary":
                owner = params.get("turnId", self.turn_id)
                if not isinstance(owner, str):
                    raise NativeError("Native final message has no turn identity")
                self.turn_messages[owner] = item.get("text")
            # Retain commentary; terminal messages are emitted only at run end.
            if item.get("phase") == "commentary":
                emit({"type": "native.commentary", "text": commentary_text(item)})
        else:
            emit(item_event(method, item))
        return False

    def on_agent_message_delta(self, method, params):
        identity = str(params.get("itemId", ""))
        if identity in self.streams:
            stream, field = self.streams[identity]
            text = str(params.get("delta", ""))
            for pending in self.deltas.add(stream, identity, field.feed(text) if field else text):
                emit(pending)
        return False

    def on_turn_completed(self, method, params):
        turn = params["turn"]
        if self.turn_id == turn["id"]:
            self.turn_id = None
        self.completed_turns[turn["id"]] = turn.get("status")
        self.last_message = self.turn_messages.get(turn["id"])
        emit({"type": "turn.completed", "turn_id": turn["id"]})
        if turn.get("status") != "completed":
            raise NativeError(f"Native turn {turn.get('status')}: {json.dumps(turn.get('error'))[:2000]}")
        if self.planning and turn["id"] == self.planning_turn_id:
            plan = json.loads(self.last_message or "null")
            if (not isinstance(plan, dict) or set(plan) != {"status", "plan"}
                    or plan.get("status") not in {"planned", "needs-human-decision"}
                    or not isinstance(plan.get("plan"), str) or not plan["plan"].strip()):
                raise NativeError("Native planning result is invalid")
            from tasks.plan_receipt import record_plan, record_plan_only_receipt
            record_plan(self.state, plan)
            if plan["status"] == "needs-human-decision":
                self.last_message = json.dumps({"status": "needs-human-decision", "resultPath": self.state["resultPath"], "resultText": plan["plan"], "decisionKind": "clarification"})
                self.finish_turn()
                return True
            # Cancellation/input authority is checked again before the automatic transition.
            current = self.runtime.safe_read_json(Path(self.state["statePath"]))
            if current.get("cancelRequested"):
                return True
            if self.plan_only:
                # Plan mode cannot write files. The host records only read-only completion.
                record_plan_only_receipt(self.state)
                self.last_message = json.dumps({"status": "completed", "resultPath": self.state["resultPath"], "resultText": plan["plan"]})
                self.finish_turn()
                return True
            self.planning = False
            emit({"type": "native.commentary", "text": "Planning is complete. Implementation is starting in the same Work session."})
            execution_turn = self.execution_turn
            if self.goal_start:
                # This turn switches the persisted collaboration mode only;
                # native Goal owns implementation and continued execution.
                execution_turn = {**execution_turn,
                    "input": [{"type": "text", "text": "Switch to default collaboration mode. Do not implement or use tools in this transition turn. Return only {\"status\":\"ready\"}; the host will activate the bounded native Goal next."}],
                    "outputSchema": {"type": "object", "properties": {"status": {"const": "ready"}},
                                     "required": ["status"], "additionalProperties": False}}
            result = self.rpc.call("turn/start", execution_turn)
            self.turn_id = result["turn"]["id"]
            if self.goal_start:
                self.goal_transition_id = self.turn_id
            self.last_message = None
            return False
        if self.goal_transition_id == turn["id"]:
            if json.loads(self.last_message or "null") != {"status": "ready"}:
                raise NativeError("Native default-mode transition did not complete")
            current = self.runtime.safe_read_json(Path(self.state["statePath"]))
            if current.get("cancelRequested"):
                return True
            params, execution_turn = self.goal_start
            goal = activate_persisted_goal(self.rpc, self.thread_id, params, execution_turn)
            self.goal_transition_id = None
            self.goal_started = True
            self.publish_goal(goal)
            self.last_message = None
            # Planning and transition output cannot complete the Goal.
            self.completed_turns.clear()
            self.turn_messages.clear()
            return False
        if self.goal_enabled:
            if self.finish_latest_goal_turn(force=True):
                return True
            emit({"type": "goal.continuing", "thread_id": self.thread_id})
            return False
        self.finish_turn()
        return True

    def on_error(self, method, params):
        if not params.get("willRetry"):
            raise NativeError(json.dumps(params.get("error", params))[:2000])
        return False
