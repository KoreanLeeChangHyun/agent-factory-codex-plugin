"""Claude print adapter. The parent runtime owns persistence and process containment.

Execution policies map to the nearest Claude permission mode (see policy.PERMISSION_MODES);
Claude tool permissions are not an implementation of Codex's filesystem/network sandbox.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.claude.policy import validate, effort, permission_arguments
import paths as runtime_paths
from prompt_delivery import PromptParts
from runtime_errors import ContractError
from runtime_storage import atomic_write, atomic_write_json, safe_read_bytes, safe_read_json

from adapters.claude.capabilities import MODELS


def build_command(session, state, session_id, *, prompt_parts=False):
    validate({**session, **state.get("executionOptions", {})})
    snapshot = Path(state["statePath"]).parent / "provider-session.json"
    atomic_write_json(snapshot, session)
    return [sys.executable, str(Path(__file__).resolve()), str(state["statePath"]), str(snapshot)]


PLAN_MODES = ("plan", "plan-work", "plan-work-verification")
PLAN_REQUEST = ("Plan this request only. Investigate as needed but do not modify files or run changing commands. "
                "Return the complete plan as resultText.")
EXECUTE_REQUEST = ("The plan above is approved. Implement it now in this session, run the necessary own checks, "
                   "and return the final result.")


def planning_phases(state):
    """Claude has no collaboration mode: plan in plan permission mode, then resume the same session to execute."""
    mode = state.get("executionOptions", {}).get("taskMode")
    if state.get("role") != "work" or mode not in PLAN_MODES:
        return [None]
    return ["plan"] if mode == "plan" else ["plan", "execute"]


def cli_command(session, state, parts, phase=None):
    directory = Path(state["statePath"]).parent
    fixed = directory / "claude-instructions.txt"
    root = Path(__file__).resolve().parents[3]
    bindings = f"\n\nAgent Factory plugin root (`<plugin-root>`): {root}\n" + \
        "Agent Factory installed skill sources (read only when needed):\n" + "\n".join(
        f"- agent-factory:{name}: {root / 'skills' / name / 'SKILL.md'}" for name in ("agent", "convention", "document"))
    atomic_write(fixed, (parts.fixed + bindings).encode("utf-8"))
    # Claude's validator does not register the 2020-12 meta-schema. Our result
    # contract uses only shared object/const/enum/type keywords; retain all of
    # those constraints and leave the persisted runtime schema unchanged.
    schema = dict(safe_read_json(Path(state["responseSchemaPath"])))
    schema.pop("$schema", None)
    command = [session["claude"], "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--replay-user-messages", "--append-system-prompt-file", str(fixed), "--system-prompt-snapshot", "off",
               "--json-schema", json.dumps(schema)]
    working_directory = session.get("workingDirectory", session.get("projectRoot"))
    if phase == "plan":
        command += ["--permission-mode", "plan", "--permission-prompts", "none"]
    else:
        command += permission_arguments(session, working_directory)
    if session.get("sessionId"):
        command += ["--resume", session["sessionId"]]
    if session.get("model"):
        command += ["--model", MODELS.get(session["model"], session["model"])]
    if effort(session.get("reasoningEffort")):
        command += ["--effort", effort(session["reasoningEffort"])]
    if phase == "execute":
        return command, {"type": "user", "uuid": str(uuid.uuid4()), "message": {"role": "user", "content": [{"type": "text", "text": EXECUTE_REQUEST}]}}
    text = parts.dynamic if phase != "plan" else parts.dynamic + "\n\n" + PLAN_REQUEST
    content = [{"type": "text", "text": text}]
    for image in state.get("imageInputs", []):
        content.append({"type": "image", "source": {"type": "base64", "media_type": image["mediaType"],
                       "data": base64.b64encode(safe_read_bytes(Path(image["path"]), None)).decode("ascii")}})
    return command, {"type": "user", "uuid": str(uuid.uuid4()), "message": {"role": "user", "content": content}}


class Events:
    """Translate only observed facts; never treat assistant prose as terminal JSON."""
    def __init__(self, expected_session=None, *, terminal=True, request_id=None):
        self.session = expected_session
        self.terminal = terminal
        self.started = False
        self.finished = False
        self.tools = {}
        self.context_tokens = None
        self.structured = None
        self.request_id = request_id
        self.acknowledged = request_id is None

    def translate(self, event):
        if not isinstance(event, dict):
            raise ValueError("Claude event must be an object")
        kind = event.get("type")
        if self.finished:
            # Trailing hook/system events after the result do not change the outcome.
            return []
        if kind == "system" and event.get("subtype") == "init":
            observed = event.get("session_id")
            if not isinstance(observed, str) or str(uuid.UUID(observed)) != observed:
                raise ValueError("Claude omitted a valid session ID")
            if self.session and observed != self.session:
                raise ValueError("Claude resumed a different session")
            if self.started:
                raise ValueError("Claude emitted a second initialization")
            self.session, self.started = observed, True
            return [{"type": "thread.started", "thread_id": observed},
                    {"type": "provider.model", "provider": "claude", "model": event.get("model")}]
        if not self.acknowledged and kind in ("assistant", "user", "result"):
            # Resume can drain a prior/background turn before processing stdin.
            # Its result (including a schema-less no-op) does not finish our request.
            if (kind == "user" and event.get("uuid") == self.request_id
                    and not event.get("parent_tool_use_id")
                    and self.started and event.get("session_id") == self.session):
                self.acknowledged = True
            return []
        if kind in ("assistant", "user") and not event.get("parent_tool_use_id"):
            result = []
            usage = event.get("message", {}).get("usage") if kind == "assistant" else None
            if isinstance(usage, dict):
                parts = [usage.get(key) for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")]
                if all(type(value) is int and value >= 0 for value in parts):
                    # The prompt size of the latest main-thread request is the context currently in use.
                    self.context_tokens = sum(parts)
            for block in event.get("message", {}).get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and kind == "assistant":
                    result.append({"type": "native.commentary", "text": block.get("text", "")})
                elif block.get("type") == "tool_use":
                    name, arguments = block.get("name"), block.get("input", {})
                    item = {"id": block["id"], "type": "mcp_tool_call", "server": "claude", "tool": name}
                    if name == "Bash":
                        item = {"id": block["id"], "type": "command_execution", "command": arguments.get("command", "")}
                    elif name in ("Write", "Edit"):
                        item = {"id": block["id"], "type": "file_change", "changes": [{"path": arguments.get("file_path", ""), "kind": "update"}]}
                    self.tools[block["id"]] = item
                    result.append({"type": "item.started", "item": dict(item)})
                elif block.get("type") == "tool_result":
                    item = self.tools.pop(block.get("tool_use_id"), None)
                    if item:
                        item = {**item, "status": "failed" if block.get("is_error") else "completed"}
                        if block.get("is_error"):
                            item["error"] = "Claude tool reported failure"
                        # is_error is not an OS exit code. Preserve it separately.
                        if item["type"] == "command_execution":
                            item["aggregated_output"] = json.dumps(block.get("content"), ensure_ascii=False)
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
                return [completed, *context]
            return [completed, *context, {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal, ensure_ascii=False)}}]
        return []


def finish_planning(state, structured, *, execute_next):
    """Mirror the Codex Plan contract: keep plan.json, stop on a decision, record plan-only completion."""
    from plan_receipt import record_plan, record_plan_only_receipt
    text = str(structured.get("resultText", "")).strip()
    if structured.get("status") == "failed" or not text:
        raise ValueError("Claude planning result is invalid")
    decision = structured.get("status") == "needs-human-decision"
    record_plan(state, {"status": "needs-human-decision" if decision else "planned", "plan": text})
    terminal = None
    if decision:
        terminal = {"status": "needs-human-decision", "resultPath": state["resultPath"], "resultText": text,
                    "decisionKind": "clarification"}
    elif not execute_next:
        # Plan mode cannot write files. The host records only read-only completion.
        record_plan_only_receipt(state)
        terminal = {"status": "completed", "resultPath": state["resultPath"], "resultText": text}
    elif safe_read_json(Path(state["statePath"])).get("cancelRequested"):
        return False
    if terminal is not None:
        emit({"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(terminal, ensure_ascii=False)}})
        return False
    emit({"type": "native.commentary", "text": "Planning is complete. Implementation is starting in the same Work session."})
    return True


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


def main():
    process = None
    try:
        state = safe_read_json(Path(sys.argv[1]))
        runtime_paths.bind(state["runtimeBinding"])
        session = safe_read_json(Path(sys.argv[2]))
        validate({**session, **state.get("executionOptions", {})})
        parts = PromptParts.decode(sys.stdin.read())
        # The host's Codex thread and Claude Code nesting markers must not describe this child.
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CODEX_THREAD_ID", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
        phases = planning_phases(state)
        session_id = session.get("sessionId")
        for index, phase in enumerate(phases):
            command, message = cli_command({**session, "sessionId": session_id}, state, parts, phase)
            # No new session/group: parent runtime containment must include all descendants.
            process = subprocess.Popen(command, cwd=session.get("workingDirectory", session["projectRoot"]),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True,
                                       encoding="utf-8", env=environment)
            process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.close()
            events = Events(session_id, terminal=phase != "plan", request_id=message["uuid"])
            for line in process.stdout:
                translated = events.translate(json.loads(line))
                # A resumed execution phase re-announces the same thread; the runtime saw it already.
                if index and translated and translated[0].get("type") == "thread.started":
                    translated = translated[2:]
                for event in translated:
                    emit(event)
            code = process.wait()
            if not events.acknowledged:
                raise ValueError(f"Claude exited with {code} before acknowledging the current request")
            if code != 0 or not events.finished:
                raise ValueError(f"Claude exited with {code}; terminal result received: {events.finished}")
            session_id = events.session
            process.stdout.close()
            if phase == "plan" and not finish_planning(state, events.structured, execute_next=len(phases) > 1):
                return 0
        return 0
    except (OSError, ValueError, KeyError, ContractError) as error:
        emit({"type": "error", "message": str(error)})
        return 1
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout:
                process.stdout.close()


if __name__ == "__main__":
    raise SystemExit(main())
