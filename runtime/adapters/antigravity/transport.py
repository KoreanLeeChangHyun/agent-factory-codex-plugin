"""Antigravity print adapter. The parent runtime owns persistence and process containment.

Execution policies map to agy tool permissions (see policy.py); they are not an
implementation of Codex's filesystem/network sandbox. Launch arguments live in
command.py and stream translation in events.py.
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

from adapters.antigravity.command import (  # noqa: F401 - re-exported for callers and tests
    EXECUTE_REQUEST, PLAN_MODES, PLAN_REQUEST, build_command, cli_command, install_agent, install_guard, planning_phases, result_schema,
)
from adapters.antigravity.control import goal_record, publish_goal
from adapters.antigravity.events import Events  # noqa: F401
from adapters.antigravity.capabilities import effort_levels
from adapters.antigravity.policy import effort, native_model, validate
from execution.prompts import PromptParts
from storage import paths as runtime_paths
from storage.errors import ContractError
from tasks import orchestrator_guard
from storage.files import now, safe_read_json

# Host markers that describe the invoking agent, never this child.
HOST_MARKERS = ("CODEX_THREAD_ID", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_AGENT")


def finish_planning(state, structured, *, execute_next):
    from tasks.plan_receipt import finish_planning as finish
    return finish(state, structured, execute_next=execute_next, provider="Antigravity", emit=emit)


def emit(event):
    print(json.dumps(event, ensure_ascii=False), flush=True)


class GoalTracker:
    """Record the Goal this run set, or the stale Goal it cleared, and its outcome."""
    def __init__(self, session, state, turns):
        self.session, self.state = session, state
        kinds = [kind for kind, _ in turns]
        self.objective = state.get("goalObjective") if "goal" in kinds else None
        self.clearing = "setup" in kinds
        self.session_id = None

    def publish(self, goal, error=None):
        publish_goal(self.state, self.session, goal, now(), error)
        emit({"type": "goal.updated", "thread_id": self.session_id, "goal": goal})
        if error:
            emit({"type": "goal.error", "message": error})

    def observe(self, events):
        """Publish the active Goal once agy names the conversation, before the goal work streams."""
        if self.session_id is None and events.session and events.started:
            self.session_id = events.session
            if self.objective:
                self.publish(goal_record(self.session_id, self.objective, "active"))

    def finish(self, events, *, succeeded):
        result = (events.result_event or {}) if events else {}
        if self.clearing and succeeded and not self.objective:
            self.publish(None)
        if not self.objective or self.session_id is None:
            return
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        tokens = sum(value for key in ("input_tokens", "cache_read_tokens", "output_tokens")
                     if type(value := usage.get(key)) is int and value >= 0)
        seconds = result.get("duration_seconds")
        seconds = int(seconds) if type(seconds) in (int, float) and seconds >= 0 else 0
        complete = succeeded and events.goal_complete
        # agy marks a met condition with <!-- GOAL_COMPLETE -->; anything else leaves it resumable.
        self.publish(goal_record(self.session_id, self.objective, "complete" if complete else "paused",
                                 tokens=tokens, seconds=seconds),
                     None if complete or not succeeded else "Antigravity ended the Goal turn without confirming the condition")


def main():
    process = None
    goal = events = None
    try:
        state = safe_read_json(Path(sys.argv[1]))
        runtime_paths.bind(state["runtimeBinding"])
        session = safe_read_json(Path(sys.argv[2]))
        validate({**session, **state.get("executionOptions", {})})
        parts = PromptParts.decode(sys.stdin.read())
        environment = {key: value for key, value in os.environ.items()
                       if key not in HOST_MARKERS and key != orchestrator_guard.ENV}
        install_agent()
        install_guard()
        if orchestrator_guard.orchestrating(state, session):
            environment.update(orchestrator_guard.environment(state))
        elif orchestrator_guard.work_profile(state, session):
            environment.update(orchestrator_guard.profile_environment(state, session))
        # Base Gemini ids take --effort only at levels the model offers (gemini-3.1-pro: low and high).
        levels = {}
        if effort(session.get("reasoningEffort")) and str(native_model(session.get("model")) or "").startswith("gemini-"):
            levels = effort_levels(session["agy"], runtime_home=state["runtimeBinding"].get("home"))
        phases = planning_phases(state)
        session_id = session.get("sessionId")
        for index, phase in enumerate(phases):
            command, turns = cli_command({**session, "sessionId": session_id, "effortLevels": levels}, state, parts, phase)
            if len(turns) > 1:
                goal = GoalTracker(session, state, turns)
            # No new session/group: parent runtime containment must include all descendants.
            process = subprocess.Popen(command, cwd=session.get("workingDirectory", session["projectRoot"]),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True,
                                       encoding="utf-8", env=environment)
            for _, message in turns:
                process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            process.stdin.close()
            events = Events(session_id, terminal=phase != "plan", nullable=result_schema(state)[1],
                            turns=[kind for kind, _ in turns])
            for line in process.stdout:
                if not line.strip():
                    continue
                translated = events.translate(json.loads(line))
                # A resumed execution phase re-announces the same thread; the runtime saw it already.
                if index and translated and translated[0].get("type") == "thread.started":
                    translated = translated[2:]
                if goal:
                    if translated[:1] and translated[0].get("type") == "thread.started":
                        # The runtime learns the session before goal.updated names it.
                        for item in translated[:2]:
                            emit(item)
                        translated = translated[2:]
                    goal.observe(events)
                for item in translated:
                    emit(item)
            code = process.wait()
            if code != 0 or not events.finished:
                raise ContractError("native_backend_error" if code else "result_missing",
                                    f"Antigravity exited with {code}; terminal result received: {events.finished}")
            if goal:
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
              "stage": "adapter", "acceptance": "started" if events and events.started else "unknown"})
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
