"""Claude print launch: phases, CLI arguments and the first stream-json user message."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import uuid

from adapters.claude.capabilities import MODELS
from adapters.claude.control import goal_commands
from adapters.claude.policy import effort, orchestrator_arguments, permission_arguments, validate, work_subagent_arguments
from storage.files import atomic_write, atomic_write_json, safe_read_bytes, safe_read_json
from contracts.receipts import result_only_schema

TRANSPORT = Path(__file__).with_name("transport.py")


def build_command(session, state, session_id, *, prompt_parts=False):
    validate({**session, **state.get("executionOptions", {})})
    snapshot = Path(state["statePath"]).parent / "provider-session.json"
    atomic_write_json(snapshot, session)
    return [sys.executable, str(TRANSPORT), str(state["statePath"]), str(snapshot)]


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
    root = Path(__file__).resolve().parents[3]  # plugin root
    bindings = f"\n\nAgent Factory plugin root (`<plugin-root>`): {root}\n" + \
        "Agent Factory installed skill sources (read only when needed):\n" + "\n".join(
        f"- agent-factory:{name}: {root / 'skills' / name / 'SKILL.md'}" for name in ("agent", "convention", "document", "tool"))
    atomic_write(fixed, (parts.fixed + bindings).encode("utf-8"))
    # Claude's validator does not register the 2020-12 meta-schema. Our result
    # contract uses only shared object/const/enum/type keywords; retain all of
    # those constraints and leave the persisted runtime schema unchanged.
    schema = dict(safe_read_json(Path(state["responseSchemaPath"])))
    schema.pop("$schema", None)
    if phase == "plan":
        schema = result_only_schema(schema)  # A plan completes no Work, so it returns no receipt fields.
    # Partial messages stream text as it is generated; every CLI with the options below supports them.
    command = [session["claude"], "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--include-partial-messages", "--replay-user-messages", "--append-system-prompt-file", str(fixed), "--system-prompt-snapshot", "off",
               "--json-schema", json.dumps(schema)]
    working_directory = session.get("workingDirectory", session.get("projectRoot"))
    if phase == "plan":
        command += ["--permission-mode", "plan", "--permission-prompts", "none"]
    elif state.get("role") == "main" and state.get("executionOptions", {}).get("taskMode") == "orchestrate":
        command += orchestrator_arguments(root, directory)
    else:
        command += permission_arguments(session, working_directory)
    if state.get("role") == "work":
        command += work_subagent_arguments()  # Every Work phase, including plan.
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


def setup_messages(session, state, phase=None):
    """User messages sent before the request; the plan phase never sets or clears a Goal."""
    if phase == "plan":
        return []
    return [{"type": "user", "uuid": str(uuid.uuid4()), "message": {"role": "user", "content": command}}
            for command in goal_commands(session, state)]
