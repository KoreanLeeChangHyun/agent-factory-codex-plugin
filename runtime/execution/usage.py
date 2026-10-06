"""Reported model usage, kept separate from context occupancy and billing."""
from __future__ import annotations
from collections import OrderedDict


FIELDS = ("inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")
CLI_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def counts(value, names=FIELDS):
    if not isinstance(value, dict):
        return None
    result = {}
    for target, name in zip(FIELDS, names, strict=False):
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


def compare_orchestration(document, read_json):
    """Compare supplied observations, never infer missing usage or task quality.

    Run totals include retries. Cache input is a subset of input; reasoning is a
    subset of output. Attempts and detail reads remain breakdowns, not additions.
    Text byte counts are static transport observations, not model token savings.
    """
    import hashlib
    from pathlib import Path
    from storage.errors import ContractError

    def fail(message):
        raise ContractError('measurement_invalid', message)

    if not isinstance(document, dict) or document.get('schemaVersion') != 1 or not isinstance(document.get('cases'), list):
        fail('Use schemaVersion 1 and cases')

    def arm(value):
        if not isinstance(value, dict) or not isinstance(value.get('messages'), list) or not all(isinstance(item, str) for item in value['messages']):
            fail('Each arm requires its complete messages array')
        paths = value.get('runStatePaths', [])
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            fail('runStatePaths must contain observed state paths')
        seen, runs = set(), []
        for path in paths:
            state = read_json(Path(path))
            identity = (state.get('agentId'), state.get('runId'))
            if not all(isinstance(item, str) and item for item in identity) or identity in seen:
                fail('Each observed run must have a unique agentId/runId')
            seen.add(identity)
            usage = state.get('tokenUsage') or {}
            if not isinstance(usage, dict):
                fail('tokenUsage must be an observed object')
            for key in FIELDS:
                if usage.get(key) is not None and (type(usage[key]) is not int or usage[key] < 0):
                    fail('Usage counters must be nonnegative integers or null')
            for subset, whole in (('cachedInputTokens', 'inputTokens'), ('reasoningOutputTokens', 'outputTokens')):
                if usage.get(subset) is not None and usage.get(whole) is not None and usage[subset] > usage[whole]:
                    fail('Usage subset exceeds its parent counter')
            attempts = state.get('usageAttempts', {})
            runs.append({'agentId': identity[0], 'runId': identity[1], 'role': state.get('role'),
                         'status': state.get('status'), 'failureClass': state.get('failureClass'),
                         'source': path, 'requestHash': state.get('requestHash'),
                         'taskId': state.get('taskBinding', {}).get('taskId'),
                         'modelSettings': state.get('executionOptions', {}),
                         'executionPolicy': state.get('executionPolicy'),
                         'usage': {key: usage.get(key) for key in FIELDS},
                         'coverage': usage.get('coverage', 'unavailable'), 'attempts': attempts,
                         'cacheWriteTokens': None,
                         'reportedAttemptCount': len(attempts),
                         'retryCount': state['attempt'] - 1 if type(state.get('attempt')) is int and state['attempt'] >= 1 else None,
                         'startedAt': state.get('startedAt'), 'finishedAt': state.get('finishedAt')})
        roles = {}
        for role in ('main', 'work', 'verification'):
            group = [run for run in runs if run['role'] == role]
            roles[role] = {key: sum(run['usage'][key] for run in group)
                          if group and all(type(run['usage'][key]) is int for run in group) else None for key in FIELDS}
            roles[role]['cacheWriteTokens'] = None  # Not exposed by the maintained run usage contract.
        return {'staticInput': {'utf8Bytes': sum(len(item.encode('utf-8')) for item in value['messages']),
                               'characters': sum(len(item) for item in value['messages']),
                               'tokenEstimate': None},
                'reportedModelUsageByRole': roles, 'runs': runs,
                'detailReads': value.get('detailReads'),
                'quality': value.get('quality'), 'allocationErrors': value.get('allocationErrors'),
                'rework': value.get('rework'), 'elapsedSeconds': value.get('elapsedSeconds')}

    cases = []
    for case in document['cases']:
        if not isinstance(case, dict) or not all(isinstance(case.get(key), str) and case[key].strip() for key in ('id', 'input', 'completionCriteria')):
            fail('Each case needs id, the same original input and completionCriteria')
        before, after = arm(case.get('before')), arm(case.get('after'))
        cases.append({'id': case['id'], 'inputSha256': hashlib.sha256(case['input'].encode()).hexdigest(),
                      'completionCriteria': case['completionCriteria'], 'before': before, 'after': after,
                      'staticUtf8ByteDifference': after['staticInput']['utf8Bytes'] - before['staticInput']['utf8Bytes'],
                      'modelTokenSavingsPercent': None})
    return {'schemaVersion': 1, 'kind': 'orchestration-comparison', 'cases': cases,
            'provenance': document.get('provenance'),
            'accounting': 'Run usage includes attempts/retries; cached input and reasoning output are subsets. Detail read usage is already included in its run when reported. Missing observations are null, never zero. Static text bytes are not measured model token savings.'}
