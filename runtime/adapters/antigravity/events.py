"""Translate agy stream-json into runtime events. Only observed facts become events."""
from __future__ import annotations

import json
import uuid

from adapters.antigravity.control import COMPLETE, strip_markers
from execution.streaming import DeltaBuffer, JsonStringField

# agy tools that change files, and the parameter naming the changed path.
FILE_TOOLS = {"write_to_file": "TargetFile", "replace_file_content": "TargetFile",
              "multi_replace_file_content": "TargetFile", "sed_file": "TargetFile", "notebook_edit": "TargetFile"}
MAX_TOOL_OUTPUT_CHARACTERS = 64 * 1024


def split_answer(text, structured):
    """Split a final response into its prose and the result object, or None without one.

    A resumed conversation reports the last structured_output it ever produced; it belongs to
    this turn only when this turn's response contains that object (agy adds its own keys).
    Some models put prose before it, and a Goal hook's confirmation can follow it."""
    if not isinstance(text, str) or not isinstance(structured, dict):
        return None
    body = text.strip()
    decoder = json.JSONDecoder()
    found = None
    index = body.find("{")
    while index >= 0:
        try:
            value, end = decoder.raw_decode(body, index)
        except ValueError:
            value, end = None, index
        if isinstance(value, dict) and all(value.get(key) == item for key, item in structured.items()):
            found = index, end
        index = body.find("{", index + 1)
    if found is None:
        return None
    return (body[:found[0]].strip() + "\n\n" + body[found[1]:].strip()).strip()


class Events:
    """Translate only observed facts; the terminal result is agy's schema-validated structured_output."""
    def __init__(self, expected_session=None, *, terminal=True, nullable=(), turns=("request",)):
        self.session = expected_session
        # One result arrives per stdin message; only the last turn's result finishes the run.
        self.turns = list(turns)
        self.goal_complete = False
        self.request_answer = None
        # Result fields made optional for Gemini (command.result_schema); an omitted one is null.
        self.nullable = tuple(nullable)
        self.terminal = terminal
        self.started = False
        self.finished = False
        self.tools = {}
        self.structured = None
        self.result_event = None
        self.deltas = DeltaBuffer()
        # Text of the latest completed response step. With a schema the last one is the result
        # JSON, so it becomes commentary only once later work shows it was not the last.
        self.held = None
        self.responses = {}
        self.model = ""

    def translate(self, event):
        if not isinstance(event, dict):
            raise ValueError("Antigravity event must be an object")
        kind = event.get("event")
        if self.finished:
            return []
        if kind == "init":
            observed = event.get("conversation_id")
            try:
                valid = isinstance(observed, str) and str(uuid.UUID(observed)) == observed
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Antigravity omitted a valid conversation ID")
            if self.session and observed != self.session:
                raise ValueError("Antigravity resumed a different conversation")
            self.session, self.started = observed, True
            model = (event.get("init") or {}).get("model")
            self.model = model if isinstance(model, str) else ""
            return [{"type": "thread.started", "thread_id": observed},
                    {"type": "provider.model", "provider": "antigravity", "model": model}]
        if not self.started:
            if kind == "result":
                raise ValueError("Antigravity failed before initialization: " + str((event.get("result") or {}).get("error")))
            return []
        if kind == "step_update":
            step = event.get("step_update")
            return self.step(step) if isinstance(step, dict) else []
        if kind == "result":
            return self.result(event.get("result") if isinstance(event.get("result"), dict) else {})
        return []

    def step(self, step):
        kind, index, state = step.get("step_type"), step.get("step_index"), step.get("state")
        if self.turns[0] == "setup":
            return []  # A /goal clear turn is runtime bookkeeping, not agent work.
        if kind == "agent_response":
            identity = f"{self.session}:{index}"
            if identity not in self.responses:
                self.responses[identity] = ["", None]
            text, field = self.responses[identity]
            delta = step.get("text_delta") if isinstance(step.get("text_delta"), str) else ""
            text += delta
            if field is None and text.strip():
                # A response that opens as JSON is the schema result; preview its resultText.
                final = self.terminal and len(self.turns) == 1 and text.lstrip().startswith("{")
                field = JsonStringField() if final else False
                delta = text
            self.responses[identity] = [text, field]
            result = []
            if delta and field is not None:
                result = (self.deltas.add("final", identity, field.feed(delta)) if field
                          else self.deltas.add("commentary", identity, delta))
            if state != "ACTIVE":
                del self.responses[identity]
                result = [*result, *self.deltas.flush(identity)]
                if text.strip():
                    result = [*self.release(), *result]
                    self.held = text.strip()
            return result
        if kind != "tool":
            return []
        info = step.get("tool_info") if isinstance(step.get("tool_info"), dict) else {}
        name = step.get("tool_name") or info.get("name")
        if name == "finish":
            return []  # agy's own turn-ending call; the held response is still the result.
        identity = f"{self.session}:{index}"
        if state == "ACTIVE":
            if identity in self.tools:
                return []
            arguments = info.get("parameters") if isinstance(info.get("parameters"), dict) else {}
            item = {"id": identity, "type": "mcp_tool_call", "server": "antigravity", "tool": name}
            if name == "run_command":
                item = {"id": identity, "type": "command_execution", "command": str(arguments.get("CommandLine", ""))}
            elif name in FILE_TOOLS:
                item = {"id": identity, "type": "file_change",
                        "changes": [{"path": str(arguments.get(FILE_TOOLS[name], "")), "kind": "update"}]}
            self.tools[identity] = item
            return [*self.release(), {"type": "item.started", "item": dict(item)}]
        item = self.tools.pop(identity, None)
        if item is None:
            return []
        output = info.get("output") if isinstance(info.get("output"), str) else ""
        item = {**item, "status": "failed" if state == "ERROR" else "completed"}
        if state == "ERROR":
            error = info.get("error") if isinstance(info.get("error"), dict) else {}
            # A failed or denied tool call is ordinary agent work, not a runtime failure.
            item["error"] = (str(error.get("message") or "") or output)[:2000] or "Antigravity tool reported failure"
        if item["type"] == "command_execution":
            item["aggregated_output"] = output[:MAX_TOOL_OUTPUT_CHARACTERS]
        elif output:
            item["result"] = output[:MAX_TOOL_OUTPUT_CHARACTERS]
        return [{"type": "item.completed", "item": item}]

    def intermediate(self, kind, result):
        """A setup or request turn that a later Goal turn continues; its answer is commentary."""
        pending = self.deltas.flush()
        self.responses, self.tools = {}, {}
        held, self.held = self.held, None
        answer = result.get("structured_output")
        if kind == "request" and split_answer(result.get("response"), answer) is not None:
            self.request_answer = answer
        if kind == "setup" or not held:
            return pending
        text = answer.get("resultText") if isinstance(answer, dict) and split_answer(held, answer) is not None else None
        return [*pending, {"type": "native.commentary", "text": strip_markers(str(text) if text else held)}]

    def release(self):
        """Later work shows the held response was commentary, not the result."""
        held, self.held = self.held, None
        try:
            value = json.loads(held) if held else None
        except ValueError:
            value = None
        if isinstance(value, dict):
            # A superseded result attempt: show its answer text, not the JSON envelope.
            held = value.get("resultText") if isinstance(value.get("resultText"), str) else None
        held = strip_markers(held) if held else None
        return [{"type": "native.commentary", "text": held}] if held else []

    def result(self, result):
        if result.get("conversation_id") != self.session:
            raise ValueError("Antigravity terminal conversation does not match initialization")
        if result.get("status") != "SUCCESS":
            raise ValueError("Antigravity execution failed: " + str(result.get("error") or result.get("status")))
        kind = self.turns.pop(0) if len(self.turns) > 1 else None
        if kind is not None:
            return self.intermediate(kind, result)
        answer = result.get("structured_output")
        if "goal" in self.turns:
            # The marker may follow the result JSON or sit inside it, where the raw response escapes `<`.
            self.goal_complete = (COMPLETE in str(result.get("response"))
                                  or COMPLETE in json.dumps(answer, ensure_ascii=False))
        if split_answer(result.get("response"), answer) is None:
            if self.request_answer is None:
                denied = [str(action.get("action")) for action in result.get("denied_actions") or [] if isinstance(action, dict)]
                raise ValueError("Antigravity returned no schema-validated structured_output for this turn"
                                 + (f"; denied permissions: {', '.join(denied)}" if denied else ""))
            # A Goal turn that only confirms the condition leaves the request turn's answer as the result.
            answer = self.request_answer
        terminal = {**{key: None for key in self.nullable}, **strip_markers(answer)}
        self.finished, self.structured, self.result_event = True, terminal, result
        pending = self.deltas.flush()
        # The final response carries the result object; only prose around it is commentary.
        held = split_answer(self.held, answer) if self.held else None
        commentary = self.release() if held is None else [{"type": "native.commentary", "text": held}] if held else []
        self.held = None
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        def count(key):
            value = usage.get(key)
            return value if type(value) is int and value >= 0 else None
        # Normalized input includes cache reads and output includes thinking (UsageAccumulator subsets).
        # agy reports Gemini input that way but Anthropic-served input without its cache reads.
        fresh, cached = count("input_tokens"), count("cache_read_tokens")
        exclusive = self.model.startswith("claude-") or (None not in (fresh, cached) and cached > fresh)
        total_input = fresh + cached if exclusive and None not in (fresh, cached) else fresh
        completed = {"type": "turn.completed", "turn_id": self.session,
                     "usage": {"input_tokens": total_input, "cached_input_tokens": cached,
                               "output_tokens": count("output_tokens"), "reasoning_output_tokens": count("thinking_tokens")}}
        if not self.terminal:
            return [*pending, *commentary, completed]
        return [*pending, *commentary, completed,
                {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal, ensure_ascii=False)}}]
