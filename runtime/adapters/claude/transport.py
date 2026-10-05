"""Claude print adapter. The parent runtime owns persistence and process containment.

Execution policies map to the nearest Claude permission mode (see policy.PERMISSION_MODES);
Claude tool permissions are not an implementation of Codex's filesystem/network sandbox.
Launch arguments live in command.py and stream translation in events.py.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.claude.command import (  # noqa: F401 - re-exported for callers and tests
    EXECUTE_REQUEST, PLAN_MODES, PLAN_REQUEST, build_command, cli_command, planning_phases, setup_messages,
)
from adapters.claude.control import goal_record, publish_goal
from adapters.claude.events import Events  # noqa: F401
from adapters.claude.policy import validate
from execution.prompts import PromptParts
from storage import paths as runtime_paths
from storage.errors import ContractError
from storage.files import now, safe_read_json


def finish_planning(state, structured, *, execute_next):
    """Mirror the Codex Plan contract: keep plan.json, stop on a decision, record plan-only completion."""
    from tasks.plan_receipt import record_plan, record_plan_only_receipt
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


class GoalTracker:
    """Record the Goal Claude confirmed for this run and its outcome."""
    def __init__(self, session, state):
        self.session, self.state = session, state
        self.objective = state.get("goalObjective")
        self.clearing = not self.objective and bool(session.get("goal"))
        self.confirmed = False
        self.session_id = None

    def publish(self, goal, error=None):
        publish_goal(self.state, self.session, goal, now(), error)
        emit({"type": "goal.updated", "thread_id": self.session_id, "goal": goal})
        if error:
            emit({"type": "goal.error", "message": error})

    def observe(self, events):
        """Publish once Claude answers the setup command, before the goal work streams."""
        if self.confirmed or not events.visible or not events.setup_ids:
            return
        self.confirmed, self.session_id = True, events.session
        reply = " ".join(events.setup_replies).strip()
        if self.objective and not reply.startswith("Goal set:"):
            self.objective = None
            self.publish(None, "Claude did not set the Goal: " + (reply or "no confirmation"))
        elif self.objective:
            self.publish(goal_record(self.session_id, self.objective, "active"))
        elif self.clearing:
            self.publish(None)

    def finish(self, events, *, succeeded):
        if not self.objective or not self.confirmed:
            return
        result = events.result_event or {}
        usage = result.get("usage", {})
        tokens = sum(value for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")
                     if type(value := usage.get(key)) is int and value >= 0)
        seconds = result.get("duration_ms")
        seconds = seconds // 1000 if type(seconds) is int and seconds >= 0 else 0
        # Claude stops successfully only after its Stop hook judged the condition met.
        complete = succeeded and isinstance(events.structured, dict) and events.structured.get("status") == "completed"
        self.publish(goal_record(self.session_id, self.objective, "complete" if complete else "paused",
                                 tokens=tokens, seconds=seconds))


def main():
    process = None
    goal = events = None
    try:
        state = safe_read_json(Path(sys.argv[1]))
        runtime_paths.bind(state["runtimeBinding"])
        session = safe_read_json(Path(sys.argv[2]))
        validate({**session, **state.get("executionOptions", {})})
        parts = PromptParts.decode(sys.stdin.read())
        # The host's Codex thread and Claude Code nesting markers must not describe this child.
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CODEX_THREAD_ID", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
        from tasks import orchestrator_guard
        environment.pop(orchestrator_guard.ENV, None)
        if orchestrator_guard.work_profile(state, session):
            environment.update(orchestrator_guard.profile_environment(state, session))
        phases = planning_phases(state)
        session_id = session.get("sessionId")
        goal = None
        for index, phase in enumerate(phases):
            command, message = cli_command({**session, "sessionId": session_id}, state, parts, phase)
            setup = setup_messages(session, state, phase) if goal is None else []
            if setup:
                goal = GoalTracker(session, state)
            # No new session/group: parent runtime containment must include all descendants.
            process = subprocess.Popen(command, cwd=session.get("workingDirectory", session["projectRoot"]),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True,
                                       encoding="utf-8", env=environment)
            for line in (*setup, message):
                process.stdin.write(json.dumps(line, ensure_ascii=False) + "\n")
            process.stdin.close()
            events = Events(session_id, terminal=phase != "plan", request_id=message["uuid"],
                            setup_ids=[line["uuid"] for line in setup])
            for line in process.stdout:
                translated = events.translate(json.loads(line))
                # A resumed execution phase re-announces the same thread; the runtime saw it already.
                if index and translated and translated[0].get("type") == "thread.started":
                    translated = translated[2:]
                if setup:
                    goal.observe(events)
                for event in translated:
                    emit(event)
            code = process.wait()
            if not events.acknowledged:
                raise ContractError("start_ack_missing", f"Claude exited with {code} before acknowledging the current request")
            if code != 0 or not events.finished:
                raise ContractError("native_backend_error" if code else "result_missing",
                                    f"Claude exited with {code}; terminal result received: {events.finished}")
            if setup:
                goal.finish(events, succeeded=True)
            session_id = events.session
            process.stdout.close()
            if phase == "plan" and not finish_planning(state, events.structured, execute_next=len(phases) > 1):
                return 0
        return 0
    except (OSError, ValueError, KeyError, ContractError) as error:
        if goal is not None:
            with contextlib.suppress(Exception):
                goal.finish(events, succeeded=False)
        emit({"type": "error", "message": str(error),
              "code": getattr(error, "code", "result_invalid" if isinstance(error, (ValueError, KeyError)) else "native_backend_error"),
              "stage": "adapter", "requestId": getattr(events, "request_id", None),
              "acceptance": "started" if events and events.acknowledged else "unknown"})
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
