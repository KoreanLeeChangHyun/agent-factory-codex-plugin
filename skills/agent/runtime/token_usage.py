"""Reported model usage, kept separate from context occupancy and billing."""
from __future__ import annotations
from collections import OrderedDict


FIELDS = ("inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")
CLI_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def counts(value, names=FIELDS):
    if not isinstance(value, dict):
        return None
    result = {}
    for target, name in zip(FIELDS, names):
        number = value.get(name)
        result[target] = number if type(number) is int and number >= 0 else None
    if result["inputTokens"] is None or result["outputTokens"] is None:
        return None
    for subset, whole in (("cachedInputTokens", "inputTokens"), ("reasoningOutputTokens", "outputTokens")):
        if result[subset] is not None and result[subset] > result[whole]:
            return None
    return result


class UsageAccumulator:
    """Count observed usage only; missing counters are unknown, never zero.

    Native totals are session-cumulative. The first notification contributes only
    its last inference, avoiding charging a resumed session's history again.
    Later notifications contribute deltas; repeated totals contribute nothing.
    This is reported usage, not a guarantee that a failed provider reported all work.
    """

    def __init__(self):
        self.total = {key: 0 for key in FIELDS}
        self.reports = 0
        self.previous = None
        self.turns = set()
        self.discontinuities = 0
        self.native_reports = OrderedDict()

    def observe(self, event):
        if event.get("type") == "token.usage":
            usage = event.get("tokenUsage")
            if not isinstance(usage, dict):
                return False
            total, latest = counts(usage.get("total")), counts(usage.get("last"))
            if total is None or latest is None:
                return False
            if any(latest[key] is not None and total[key] is not None and latest[key] > total[key]
                   for key in FIELDS):
                return False
            turn = event.get("turn_id")
            identity = (turn if isinstance(turn, str) else None, tuple(total[key] for key in FIELDS))
            if identity in self.native_reports:
                return False
            if total == self.previous:
                return False
            delta = latest
            if self.previous is not None:
                delta = {key: total[key] - self.previous[key]
                         if total[key] is not None and self.previous[key] is not None else None for key in FIELDS}
                if any(value is not None and value < 0 for value in delta.values()):
                    self.discontinuities += 1
                    delta = latest
            self.previous = total
            # Retain a bounded replay window without retaining conversation content.
            self.native_reports[identity] = None
            if len(self.native_reports) > 256:
                self.native_reports.popitem(last=False)
        elif event.get("type") == "turn.completed":
            delta = counts(event.get("usage"), CLI_FIELDS)
            if delta is None:
                return False
            turn = event.get("turn_id")
            if isinstance(turn, str):
                if turn in self.turns:
                    return False
                self.turns.add(turn)
        else:
            return False
        self.reports += 1
        for key in FIELDS:
            self.total[key] = (self.total[key] + delta[key]
                               if self.total[key] is not None and delta[key] is not None else None)
        return True

    def snapshot(self):
        return {"schemaVersion": 1, "coverage": "reported" if self.reports else "unavailable",
                "reports": self.reports, "counterDiscontinuities": self.discontinuities,
                **(self.total if self.reports else {key: None for key in FIELDS})}


def record_attempt(state, attempt, snapshot):
    attempts = dict(state.get("usageAttempts", {}))
    attempts[str(attempt)] = snapshot
    state["usageAttempts"] = attempts
    values = list(attempts.values())
    state["tokenUsage"] = {
        "schemaVersion": 1,
        "coverage": "reported" if any(value["reports"] for value in values) else "unavailable",
        "reports": sum(value["reports"] for value in values),
        "counterDiscontinuities": sum(value["counterDiscontinuities"] for value in values),
        **{key: sum(value[key] for value in values) if all(value[key] is not None for value in values)
           else None for key in FIELDS},
    }
