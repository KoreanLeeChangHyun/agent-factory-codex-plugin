"""Antigravity print launch: phases, CLI arguments and the stream-json user message."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

from adapters.antigravity.control import goal_commands
from adapters.antigravity.policy import NOTICES, effort_arguments, native_model, permission_arguments, sandbox, validate
from storage.errors import ContractError
from storage.files import atomic_write_json, safe_read_json

TRANSPORT = Path(__file__).with_name("transport.py")
PLAN_MODES = ("plan", "plan-work", "plan-work-verification")
PLAN_REQUEST = ("Plan this request only. Investigate as needed but do not modify files or run changing commands. "
                "Return the complete plan as resultText.")
EXECUTE_REQUEST = ("The plan above is approved. Implement it now in this session, run the necessary own checks, "
                   "and return the final result.")

# agy's default agent sends a ~12k-token system prompt with ~57 tools (browser, image, schedule,
# subagents, ...). A custom agent replaces the prompt text and lists only the tools a managed run
# uses; agy keeps its workspace components and, like Codex and Claude, the project's rule files
# (AGENTS.md/GEMINI.md). `finish` must be listed: it carries --json-schema results.
AGENT_NAME = "agent-factory"
AGENT_TOOLS = ("view_file", "list_dir", "find_by_name", "grep_search", "write_to_file", "replace_file_content",
               "multi_replace_file_content", "notebook_edit", "run_command", "search_web", "read_url_content", "generate_image", "finish")
AGENT_PROMPT = ("You are an autonomous coding agent launched by Agent Factory in headless print mode. The user "
                "message holds your role instructions and the current request; follow them exactly. Nobody can "
                "answer questions or approve actions during the run. Use absolute paths with the file tools. "
                "Use generate_image when the request needs a generated picture; it saves outside the workspace, "
                "so copy the file where the request expects it. "
                "End every turn by calling finish once with the final result the request requires; omit optional "
                "result fields instead of setting them to null.")


def agent_definition():
    return ("---\n"
            f"name: {AGENT_NAME}\n"
            "description: Agent Factory managed runs (installed by the Agent Factory runtime).\n"
            "mainAgent: true\n"
            "hidden: true\n"
            "inheritCustomizations: true\n"
            "inheritMcp: false\n"
            f"tools: [{', '.join(AGENT_TOOLS)}]\n"
            "---\n"
            "# System Prompt\n"
            f"{AGENT_PROMPT}\n")


def install_agent(home=None):
    """Write the agent where agy discovers global agents; the user's project stays untouched."""
    path = Path(home or Path.home()) / ".gemini" / "config" / "agents" / AGENT_NAME / "agent.md"
    content = agent_definition().encode("utf-8")
    try:
        if path.read_bytes() == content:
            return path
    except OSError:
        pass
    # Outside the runtime storage root, so not storage.files.atomic_write; concurrent runs write identical bytes.
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".agent.md.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


def build_command(session, state, session_id, *, prompt_parts=False):
    validate({**session, **state.get("executionOptions", {})})
    snapshot = Path(state["statePath"]).parent / "provider-session.json"
    atomic_write_json(snapshot, session)
    return [sys.executable, str(TRANSPORT), str(state["statePath"]), str(snapshot)]


def planning_phases(state):
    """agy's plan mode waits for Human review, which print mode cannot give. Plan by instruction
    without skipped permissions, then resume the same conversation to execute."""
    mode = state.get("executionOptions", {}).get("taskMode")
    if state.get("role") != "work" or mode not in PLAN_MODES:
        return [None]
    return ["plan"] if mode == "plan" else ["plan", "execute"]


def result_schema(state):
    """The run's result schema in a form Gemini accepts, and the fields it made optional.

    Gemini function declarations reject null enum members. A required field whose enum allows
    null becomes an optional non-null field; events.py restores null when the model omits it."""
    schema = dict(safe_read_json(Path(state["responseSchemaPath"])))
    schema.pop("$schema", None)
    properties, nullable = dict(schema.get("properties", {})), []
    for key, value in properties.items():
        if isinstance(value, dict) and None in (value.get("enum") or []):
            types = value.get("type") if isinstance(value.get("type"), list) else [value.get("type")]
            kinds = [kind for kind in types if kind not in (None, "null")]
            properties[key] = {**value, "enum": [item for item in value["enum"] if item is not None],
                               **({"type": kinds[0]} if len(kinds) == 1 else {}),
                               "description": "Omit this field when its value would be null."}
            nullable.append(key)
    required = [key for key in schema.get("required", []) if key not in nullable]
    return {**schema, "properties": properties, "required": required}, tuple(nullable)


def user(text):
    return {"event": "user", "message": {"content": [{"type": "text", "text": text}]}}


def cli_command(session, state, parts, phase=None):
    """Return argv and the phase's stream-json turns as (kind, message) pairs.

    agy answers each message as its own turn. `/goal clear` is a setup turn before the request;
    `/goal <condition>` follows it as the final turn, continuing until the condition holds.
    The plan phase never sets or clears a Goal."""
    if state.get("imageInputs"):
        raise ContractError("images_unsupported", "Antigravity print mode accepts text only; remove the images")
    root = Path(__file__).resolve().parents[3]  # plugin root
    bindings = f"\n\nAgent Factory plugin root (`<plugin-root>`): {root}\n" + \
        "Agent Factory installed skill sources (read only when needed):\n" + "\n".join(
        f"- agent-factory:{name}: {root / 'skills' / name / 'SKILL.md'}" for name in ("agent", "convention", "document", "tool"))
    schema, _ = result_schema(state)
    working_directory = session.get("workingDirectory", session.get("projectRoot"))
    goal = [] if phase == "plan" else goal_commands(session, state)
    command = [session["agy"], "--input-format", "stream-json", "--output-format", "stream-json",
               "--agent", AGENT_NAME, "--json-schema", json.dumps(schema)]
    if not goal:
        # Slash expansion stays off unless a Goal command needs it; requests never start with "/".
        command.append("--disable-slash-commands")
    if phase == "plan" or sandbox(session)["type"] != "danger-full-access":
        # Without skipped permissions agy denies reads outside its workspace; the run's own files and the
        # Agent Factory Skills its instructions reference are needed.
        command += ["--add-dir", str(Path(state["statePath"]).parent), "--add-dir", str(root / "skills")]
    command += [] if phase == "plan" else permission_arguments(session, working_directory)
    if session.get("sessionId"):
        command += ["--conversation", session["sessionId"]]
    if session.get("model"):
        command += ["--model", native_model(session["model"])]
    command += effort_arguments(session)
    command.append("--print=")  # The request arrives on stdin.
    if phase == "execute":
        text = EXECUTE_REQUEST
    else:
        # agy has no system-prompt option; the fixed instructions lead every request, as for Codex.
        text = ("<agent-factory-instructions>\n" + parts.fixed + bindings
                + f"\nWorking directory (resolve relative paths here): {working_directory}"
                + "\n</agent-factory-instructions>\n\n"
                + parts.dynamic + ("\n\n" + PLAN_REQUEST if phase == "plan" else ""))
    notice = NOTICES.get("plan" if phase == "plan" else sandbox(session)["type"])
    if notice:
        text += "\n\n" + notice
    setup = [("setup", user(line)) for line in goal if line == "/goal clear"]
    final = [("goal", user(line)) for line in goal if line != "/goal clear"]
    return command, [*setup, ("request", user(text)), *final]
