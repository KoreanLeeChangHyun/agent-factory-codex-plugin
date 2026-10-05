"""Antigravity print launch: phases, CLI arguments and the stream-json user message."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile

from adapters.antigravity.control import goal_commands
from adapters.antigravity.policy import NOTICES, effort_arguments, native_model, permission_arguments, sandbox, validate
from storage.errors import ContractError
from tasks import orchestrator_guard
from storage.files import atomic_write_json, safe_read_json
from contracts.receipts import result_only_schema

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
AGENT_PREFIX = "agent-factory-"
AGENT_DESCRIPTION = "Agent Factory managed runs (installed by the Agent Factory runtime)."
AGENT_TOOLS = ("view_file", "list_dir", "find_by_name", "grep_search", "write_to_file", "replace_file_content",
               "multi_replace_file_content", "notebook_edit", "run_command", "search_web", "read_url_content", "generate_image", "finish")
AGENT_PROMPT = ("You are an Agent Factory agent launched in headless print mode. The user message holds your "
                "role instructions and the current request; follow them exactly, including whether the request is "
                "conversation or work. Nobody can reply during the run; put any required Human decision in the final "
                "result. Use absolute paths with the file tools. "
                "Use generate_image when the request needs a generated picture; it saves outside the workspace, "
                "so copy the file where the request expects it. "
                "End every turn by calling finish once with the final result the request requires; omit optional "
                "result fields instead of setting them to null.")


# Agent Factory's own Skills (agent, convention, document, tool), listed for agy's progressive
# disclosure like Codex and Claude plugin Skills: names and descriptions up front, bodies read on demand.
SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills"
# agy reads agents from one global directory, while Codex, Claude and a source checkout each run their
# own plugin copy. Each copy owns an agent named for its location, so copies never overwrite each other.
AGENT_NAME = AGENT_PREFIX + hashlib.sha256(str(SKILLS_ROOT).encode("utf-8")).hexdigest()[:12]


def agent_definition(skills_root=SKILLS_ROOT):
    return ("---\n"
            f"name: {AGENT_NAME}\n"
            f"description: {AGENT_DESCRIPTION}\n"
            "mainAgent: true\n"
            "hidden: true\n"
            "inheritCustomizations: true\n"
            "inheritMcp: false\n"
            f"skills: [{json.dumps(str(skills_root))}]\n"
            f"tools: [{', '.join(AGENT_TOOLS)}]\n"
            "---\n"
            "# System Prompt\n"
            f"{AGENT_PROMPT}\n")


def install_agent(home=None):
    """Write the agent where agy discovers global agents; the user's project stays untouched."""
    agents = Path(home or Path.home()) / ".gemini" / "config" / "agents"
    path = agents / AGENT_NAME / "agent.md"
    prune_agents(agents)
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


# agy runs plugin hooks for every session, so the guard stays inert unless the runtime arms it
# (orchestrate Main and explore/scribe Work). Named per plugin copy like the agent, and pruned the same way.
GUARD_PLUGIN = AGENT_NAME + "-guard"
GUARD_DESCRIPTION = "Agent Factory orchestrator-mode guard (installed by the Agent Factory runtime)."


def guard_files():
    manifest = {"name": GUARD_PLUGIN, "version": "1.0.0", "description": GUARD_DESCRIPTION}
    hooks = {"agent-factory-orchestrator-guard": {"PreToolUse": [{"matcher": "*", "hooks": [
        {"type": "command", "command": orchestrator_guard.HOOK_COMMAND, "timeout": 30}]}]}}
    return {"plugin.json": json.dumps(manifest, indent=2) + "\n", "hooks.json": json.dumps(hooks, indent=2) + "\n"}


def install_guard(home=None):
    """Write the guard plugin where agy discovers global plugins."""
    plugins = Path(home or Path.home()) / ".gemini" / "config" / "plugins"
    directory = plugins / GUARD_PLUGIN
    prune_guards(plugins)
    for name, text in guard_files().items():
        path = directory / name
        try:
            if path.read_text(encoding="utf-8") == text:
                continue
        except OSError:
            pass
        directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    return directory


def prune_guards(plugins):
    """Remove guard plugins whose plugin copy no longer exists."""
    try:
        candidates = [path for path in plugins.iterdir()
                      if path.name.startswith(AGENT_PREFIX) and path.name.endswith("-guard") and path.name != GUARD_PLUGIN]
    except OSError:
        return
    for directory in candidates:
        try:
            if json.loads((directory / "plugin.json").read_text(encoding="utf-8")).get("description") != GUARD_DESCRIPTION:
                continue
            hooks = (directory / "hooks.json").read_text(encoding="utf-8")
            command = json.loads(hooks)["agent-factory-orchestrator-guard"]["PreToolUse"][0]["hooks"][0]["command"]
            if Path(command.split(" ", 1)[1].strip("'\"")).exists():
                continue  # Its plugin copy is still installed.
            for name in ("plugin.json", "hooks.json"):
                (directory / name).unlink(missing_ok=True)
            directory.rmdir()
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue  # Best effort: a leftover inert guard is harmless.


def prune_agents(agents):
    """Remove agents this runtime wrote for plugin copies that no longer exist (e.g. replaced versions)."""
    try:
        candidates = [path for path in agents.iterdir() if path.name.startswith(AGENT_PREFIX) and path.name != AGENT_NAME]
    except OSError:
        return
    for directory in candidates:
        try:
            text = (directory / "agent.md").read_text(encoding="utf-8")
            match = re.search(r'^skills: \[(".*")\]$', text, re.MULTILINE)
            if f"description: {AGENT_DESCRIPTION}\n" not in text or not match or Path(json.loads(match.group(1))).exists():
                continue  # Not ours, or its plugin copy is still installed.
            (directory / "agent.md").unlink()
            directory.rmdir()
        except (OSError, ValueError):
            continue  # Best effort: a leftover agent is harmless.


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
    if phase == "plan":
        schema = result_only_schema(schema)  # A plan completes no Work, so it returns no receipt fields.
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
        command += ["--add-dir", str(Path(state["statePath"]).parent), "--add-dir", str(SKILLS_ROOT)]
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
