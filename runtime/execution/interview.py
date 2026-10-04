"""Provider-neutral structured Interview question events."""
from __future__ import annotations

import json
import re


MARKER = re.compile(
    r"<agent-factory-interview-question>(\{[^\n]*\})</agent-factory-interview-question>"
)
PROS_CONS = re.compile(
    r"^(?:Pros|Advantages|장점)\s*:\s*(.*?)\s*[;|]\s*(?:Cons|Disadvantages|단점)\s*:\s*(.+)$",
    re.IGNORECASE,
)
RECOMMENDED = re.compile(r"\s*\((?:recommended|권고)\)\s*$", re.IGNORECASE)
POSITION = re.compile(r"(?:interview[-_.])?(\d+)(?:-of-|[/_.-])(\d+)$", re.IGNORECASE)


def normalize_question(value: object) -> dict | None:
    """Return one validated interview.question event, or None for unrelated/invalid data."""
    if not isinstance(value, dict):
        return None
    identity, text = value.get("id"), value.get("text")
    current, total = value.get("current"), value.get("total")
    options = value.get("options")
    if (not isinstance(identity, str) or not identity or len(identity) > 128
            or not isinstance(text, str) or not text.strip()
            or type(current) is not int or type(total) is not int
            or current < 1 or total < current
            or not isinstance(options, list) or not 2 <= len(options) <= 3):
        return None
    normalized = []
    values = set()
    for option in options:
        if not isinstance(option, dict):
            return None
        answer, label, pros, cons = (option.get(key) for key in ("value", "label", "pros", "cons"))
        if (not all(isinstance(item, str) for item in (answer, label, pros, cons))
                or not answer or answer in values or not label.strip() or not pros.strip() or not cons.strip()):
            return None
        values.add(answer)
        normalized.append({"value": answer, "label": label.strip(), "pros": pros.strip(), "cons": cons.strip()})
    recommended = value.get("recommendedValue")
    if recommended is not None and (not isinstance(recommended, str) or recommended not in values):
        return None
    yes_no = value.get("yesNo", False)
    if type(yes_no) is not bool:
        return None
    return {"type": "interview.question", "question": {
        "id": identity, "current": current, "total": total, "text": text.strip(),
        "options": normalized, "recommendedValue": recommended, "yesNo": yes_no,
    }}


def extract_markers(text: object) -> tuple[str, list[dict]]:
    """Remove only valid exact markers and return their normalized events."""
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else "", []
    events = []

    def replace(match: re.Match) -> str:
        try:
            event = normalize_question(json.loads(match.group(1)))
        except (TypeError, ValueError):
            event = None
        if event is None:
            return match.group(0)
        events.append(event)
        return ""

    cleaned = MARKER.sub(replace, text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip(), events


def codex_request_events(params: object) -> list[dict]:
    """Normalize observed Codex item/tool/requestUserInput parameters."""
    if not isinstance(params, dict) or not isinstance(params.get("questions"), list):
        return []
    questions = params["questions"]
    events = []
    for index, question in enumerate(questions, 1):
        if not isinstance(question, dict) or not isinstance(question.get("options"), list):
            return []
        identity = question.get("id")
        match = POSITION.search(identity) if isinstance(identity, str) else None
        current, total = (int(match.group(1)), int(match.group(2))) if match else (index, len(questions))
        normalized_options = []
        recommended = None
        labels = []
        for option_index, option in enumerate(question["options"], 1):
            if not isinstance(option, dict):
                return []
            raw_label, description = option.get("label"), option.get("description")
            if not isinstance(raw_label, str) or not isinstance(description, str):
                return []
            is_recommended = bool(RECOMMENDED.search(raw_label))
            label = RECOMMENDED.sub("", raw_label).strip()
            detail = PROS_CONS.match(description.strip())
            if not detail:
                return []
            answer = str(option_index)
            if is_recommended:
                recommended = answer
            labels.append(label.casefold())
            normalized_options.append({"value": answer, "label": label,
                                       "pros": detail.group(1).strip(), "cons": detail.group(2).strip()})
        event = normalize_question({
            "id": identity, "current": current, "total": total, "text": question.get("question"),
            "options": normalized_options, "recommendedValue": recommended,
            "yesNo": labels == ["yes", "no"],
        })
        if event is None:
            return []
        events.append(event)
    return events
