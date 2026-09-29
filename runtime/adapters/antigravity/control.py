"""Antigravity stop and Goal controls.

agy's `/goal <condition>` runs a turn that keeps working until the condition holds and ends
its answer with `<!-- GOAL_COMPLETE -->`; `/goal clear` answers `<!-- GOAL_CANCELLED -->`.
The shared command-Goal state lives in execution.goals.
"""
from execution.goals import (  # noqa: F401 - Antigravity's Goal surface
    goal_command, goal_commands, goal_objective, goal_record, publish_goal,
)

COMPLETE = "<!-- GOAL_COMPLETE -->"
MARKERS = (COMPLETE, "<!-- GOAL_CANCELLED -->")


def before_stop(state_path, state, *, cancel=False):
    # Containment sends SIGTERM to the whole process group (agy and its tools included)
    # and waits before SIGKILL, so agy can save its conversation.
    pass


def strip_markers(value):
    """Remove agy's Goal protocol markers from result strings; they are not answer text."""
    if isinstance(value, str):
        for marker in MARKERS:
            value = value.replace(marker, "")
        return value.strip()
    if isinstance(value, dict):
        return {key: strip_markers(item) for key, item in value.items()}
    return value
