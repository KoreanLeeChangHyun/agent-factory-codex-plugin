"""Step progress an agent reports through its own to-do list (Claude TodoWrite, Codex plan updates).

Only the provider's list is counted: completed steps over all steps. A run whose agent keeps
no list reports no progress, never an estimate."""
from __future__ import annotations

MAX_STEPS = 200
MAX_CURRENT_CHARACTERS = 160
COMPLETED = {"completed"}
ACTIVE = {"in_progress", "inProgress", "in-progress"}


def plan_progress(steps, *, text_keys=("activeForm", "content", "step")):
    """A `plan.progress` event for a provider step list, or None when the list is unusable."""
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        return None
    statuses = [step.get("status") if isinstance(step, dict) else None for step in steps]
    if not all(isinstance(status, str) for status in statuses):
        return None
    event = {"type": "plan.progress", "completed": sum(status in COMPLETED for status in statuses), "total": len(steps)}
    active = next((step for step, status in zip(steps, statuses, strict=False) if status in ACTIVE), None)
    text = next((active.get(key) for key in text_keys if isinstance(active, dict) and isinstance(active.get(key), str)
                 and active.get(key).strip()), None)
    if text:
        event["current"] = " ".join(text.split())[:MAX_CURRENT_CHARACTERS]
    return event


def first_line(text, limit=MAX_CURRENT_CHARACTERS):
    """The first non-empty line of agent commentary, bounded for a one-line status."""
    if not isinstance(text, str):
        return ""
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return line[:limit]
