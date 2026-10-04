#!/usr/bin/env python3
"""PreToolUse hook that lets a Work run start only the read-only exploration sub-agent.

The Claude adapter attaches it to Work launches for the tool that spawns sub-agents; it is never
registered for Main or Verification. Every other sub-agent type is denied.
Standard library only: hooks start a fresh interpreter for every tool call.
"""
import json
from pathlib import Path
import shlex
import sys

# Claude's built-in read-only search agent; it has no edit tools and cannot spawn agents itself.
ALLOWED_TYPE = "Explore"
# Claude names its sub-agent tool `Agent` (formerly `Task`).
MATCHER = "^(Agent|Task)$"
REASON = (f"Work may start only the read-only {ALLOWED_TYPE} sub-agent, for search. Do the work yourself; "
          "never use a sub-agent to review or verify this run's own work.")
HOOK_COMMAND = shlex.quote(sys.executable or "python3") + " " + shlex.quote(str(Path(__file__).resolve()))


def allowed(event):
    arguments = event.get("tool_input")
    return isinstance(arguments, dict) and arguments.get("subagent_type") == ALLOWED_TYPE


def main():
    try:
        permitted = allowed(json.load(sys.stdin))
    except Exception:
        permitted = False  # Fail closed.
    if not permitted:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": REASON}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
