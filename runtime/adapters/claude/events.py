"""Translate Claude stream-json into runtime events. Only observed facts become events."""
from __future__ import annotations

import json
import uuid

from execution.streaming import DeltaBuffer, JsonStringField

# Claude tools that change files, and the input field naming the changed path.
FILE_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
MAX_TOOL_OUTPUT_CHARACTERS = 64 * 1024


class Events:
    """Translate only observed facts; never treat assistant prose as terminal JSON."""
    def __init__(self, expected_session=None, *, terminal=True, request_id=None, setup_ids=()):
        self.session = expected_session
        self.terminal = terminal
        self.started = False
        self.finished = False
        self.tools = {}
        self.hidden_tools = set()
        self.context_tokens = None
        self.structured = None
        self.request_id = request_id
        self.acknowledged = request_id is None
        # Slash commands (/goal) sent before the request. Work they start is ours to show,
        # but only a result after the request itself finishes the run.
        self.setup_ids = frozenset(setup_ids)
        self.visible = self.acknowledged
        self.setup_replies = []
        self.result_event = None
        self.deltas = DeltaBuffer()
        self.message_id = None
        self.blocks = {}

    def translate(self, event):
        if not isinstance(event, dict):
            raise ValueError("Claude event must be an object")
        kind = event.get("type")
        if self.finished:
            # Trailing hook/system events after the result do not change the outcome.
            return []
        if kind == "rate_limit_event":
            # Account-wide limits apply whichever turn reported them; utilization is a 0-1 ratio.
            windows = (event.get("rate_limit_info") or {}).get("unifiedWindows") or {}
            limits = {}
            for name, field in (("five_hour", "fiveHour"), ("seven_day", "weekly")):
                window = windows.get(name)
                if not isinstance(window, dict):
                    continue
                used = window.get("utilization")
                if type(used) in (int, float) and 0 <= used <= 1:
                    limits[field + "UsedPercent"] = round(used * 100, 2)
                # resetsAt is Unix seconds when the window next refills.
                resets = window.get("resetsAt")
                if type(resets) in (int, float) and resets > 0:
                    limits[field + "ResetsAt"] = resets
            return [{"type": "provider.rate_limits", **limits}] if limits else []
        if kind == "system" and event.get("subtype") == "init":
            observed = event.get("session_id")
            if not isinstance(observed, str) or str(uuid.UUID(observed)) != observed:
                raise ValueError("Claude omitted a valid session ID")
            if self.session and observed != self.session:
                raise ValueError("Claude resumed a different session")
            if self.started:
                # A local slash command (/goal clear) completes without a model turn; the
                # request's turn then initializes the same session again.
                return []
            self.session, self.started = observed, True
            return [{"type": "thread.started", "thread_id": observed},
                    {"type": "provider.model", "provider": "claude", "model": event.get("model")}]
        if kind == "stream_event":
            return self.stream(event) if self.visible and not event.get("parent_tool_use_id") else []
        if not self.acknowledged and kind in ("assistant", "user", "result"):
            # Resume can drain a prior/background turn before processing stdin.
            # Its result (including a schema-less no-op) does not finish our request.
            ours = (not event.get("parent_tool_use_id") and self.started and event.get("session_id") == self.session)
            if kind == "user" and ours and event.get("uuid") == self.request_id:
                self.acknowledged = self.visible = True
                return []
            if kind == "user" and ours and event.get("uuid") in self.setup_ids:
                self.visible = True
                return []
            if kind == "assistant" and ours and self.setup_ids and not self.visible:
                # A local slash command answers with plain text before its replay (e.g. "Goal set: …").
                self.setup_replies += [block.get("text", "") for block in event.get("message", {}).get("content", [])
                                       if isinstance(block, dict) and block.get("type") == "text"]
                return []
            if not self.visible or kind == "result":
                return []
        if kind in ("assistant", "user"):
            parent = event.get("parent_tool_use_id")
            # Complete blocks supersede their live preview; emit pending deltas first.
            result = [] if parent else self.deltas.flush()
            usage = event.get("message", {}).get("usage") if kind == "assistant" and not parent else None
            if isinstance(usage, dict):
                parts = [usage.get(key) for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")]
                if all(type(value) is int and value >= 0 for value in parts):
                    # The prompt size of the latest main-thread request is the context currently in use.
                    self.context_tokens = sum(parts)
            for block in event.get("message", {}).get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and kind == "assistant" and not parent:
                    result.append({"type": "native.commentary", "text": block.get("text", "")})
                elif block.get("type") == "tool_use" and block.get("name") == "StructuredOutput" and not parent:
                    # The final answer's transport; it arrives as the result, not a visible tool.
                    self.hidden_tools.add(block.get("id"))
                elif block.get("type") == "tool_use":
                    name, arguments = block.get("name"), block.get("input", {})
                    if not isinstance(arguments, dict):
                        arguments = {}
                    item = {"id": block["id"], "type": "mcp_tool_call", "server": "claude", "tool": name}
                    if name == "Bash":
                        item = {"id": block["id"], "type": "command_execution", "command": arguments.get("command", "")}
                    elif name in FILE_TOOLS:
                        item = {"id": block["id"], "type": "file_change",
                                "changes": [{"path": arguments.get(FILE_TOOLS[name], ""), "kind": "update"}]}
                    if parent:
                        # Tools a subagent (Task) runs stay visible and name the call that started them.
                        item["parentToolUseId"] = parent
                    self.tools[block["id"]] = item
                    result.append({"type": "item.started", "item": dict(item)})
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in self.hidden_tools:
                    self.hidden_tools.discard(block.get("tool_use_id"))
                elif block.get("type") == "tool_result":
                    item = self.tools.pop(block.get("tool_use_id"), None)
                    if item:
                        item = {**item, "status": "failed" if block.get("is_error") else "completed"}
                        output = tool_output(block.get("content"))
                        if block.get("is_error"):
                            # is_error is not an OS exit code; keep the tool's own message.
                            item["error"] = output[:2000] or "Claude tool reported failure"
                        if item["type"] == "command_execution":
                            item["aggregated_output"] = json.dumps(block.get("content"), ensure_ascii=False)
                        elif output:
                            item["result"] = output[:MAX_TOOL_OUTPUT_CHARACTERS]
                        # A failed tool call is ordinary agent work (e.g. a nonzero Bash exit), not a runtime failure.
                        result.append({"type": "item.completed", "item": item})
            return result
        if kind == "result":
            if not self.started or event.get("session_id") != self.session:
                raise ValueError("Claude terminal session does not match initialization")
            if event.get("is_error") is not False or event.get("subtype") != "success":
                raise ValueError("Claude execution failed: " + str(event.get("errors") or event.get("subtype")))
            terminal = event.get("structured_output")
            if not isinstance(terminal, dict):
                raise ValueError("Claude returned no schema-validated structured_output")
            self.finished = True
            self.structured = terminal
            self.result_event = event
            pending = self.deltas.flush()
            usage = event.get("usage", {})
            def count(key):
                value = usage.get(key)
                return value if type(value) is int and value >= 0 else None
            inputs = [count(key) for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")]
            total_input = sum(inputs) if all(v is not None for v in inputs) else None
            # Anthropic reports fresh/cache-read/cache-write separately; normalized
            # cached_input_tokens is a subset of total input for UsageAccumulator.
            completed = {"type": "turn.completed", "turn_id": event.get("uuid", self.session),
                         "usage": {"input_tokens": total_input, "cached_input_tokens": count("cache_read_input_tokens"),
                                   "output_tokens": count("output_tokens"), "reasoning_output_tokens": None}}
            windows = [value.get("contextWindow") for value in (event.get("modelUsage") or {}).values() if isinstance(value, dict)]
            windows = [value for value in windows if type(value) is int and value > 0]
            context = ([{"type": "provider.context", "usedTokens": self.context_tokens, "contextWindowTokens": max(windows)}]
                       if windows and self.context_tokens is not None else [])
            if not self.terminal:
                return [*pending, completed, *context]
            return [*pending, completed, *context, {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal, ensure_ascii=False)}}]
        return []

    def stream(self, event):
        """Preview main-thread text blocks and the terminal resultText while Claude generates them."""
        data = event.get("event")
        if not isinstance(data, dict):
            return []
        kind, index = data.get("type"), data.get("index")
        if kind == "message_start":
            message = data.get("message")
            self.message_id = message.get("id") if isinstance(message, dict) else None
            self.blocks = {}
        elif kind == "content_block_start" and isinstance(data.get("content_block"), dict):
            block = data["content_block"]
            if block.get("type") == "text":
                self.blocks[index] = ("commentary", f"{self.message_id}:{index}", None)
            elif block.get("type") == "tool_use" and block.get("name") == "StructuredOutput" and self.terminal:
                self.blocks[index] = ("final", str(block.get("id") or index), JsonStringField())
        elif kind == "content_block_delta" and index in self.blocks and isinstance(data.get("delta"), dict):
            stream, identity, field = self.blocks[index]
            delta = data["delta"]
            if stream == "commentary" and delta.get("type") == "text_delta":
                return self.deltas.add(stream, identity, str(delta.get("text", "")))
            if stream == "final" and delta.get("type") == "input_json_delta":
                return self.deltas.add(stream, identity, field.feed(str(delta.get("partial_json", ""))))
        elif kind == "content_block_stop" and index in self.blocks:
            return self.deltas.flush(self.blocks.pop(index)[1])
        return []


def tool_output(content):
    """Plain text of a tool_result: a string, or the text parts of a content list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content
                         if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str))
    return ""
