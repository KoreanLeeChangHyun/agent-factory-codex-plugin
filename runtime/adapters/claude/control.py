"""Claude stop and Goal controls.

Claude's `/goal <condition>` registers a Stop hook that keeps the session working until the
condition holds; it persists in the session transcript across `--resume`. The shared
command-Goal state lives in execution.goals.
"""
from execution.goals import (  # noqa: F401 - Claude's Goal surface
    BOUNDED_OBJECTIVE, GOAL_ROLES, MAX_OBJECTIVE_CHARACTERS, PAUSED,
    goal_command, goal_commands, goal_objective, goal_record, publish_goal,
)


def before_stop(state_path, state, *, cancel=False):
    # Nothing to negotiate: containment sends SIGTERM to the whole process group (Claude and its
    # tools included) and waits PROCESS_TERM_TIMEOUT before SIGKILL, so Claude can close its session.
    pass
