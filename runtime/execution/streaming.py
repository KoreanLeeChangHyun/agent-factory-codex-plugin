"""Incremental text streaming shared by provider adapters.

Providers deliver assistant text in small deltas. The runtime appends one
``native.delta`` event per flush to ``events.jsonl`` so the extension can render
text as it is generated. Deltas are only a live preview: the complete
``native.commentary`` event and the terminal result stay authoritative.
"""
from __future__ import annotations

import json
import time

FLUSH_SECONDS = 0.08
RESULT_FIELD = "resultText"


class JsonStringField:
    """Decode the growing value of one top-level string field from partial JSON.

    Only the prefix that is already complete is returned, so an escape sequence
    split across deltas is decoded once its remaining characters arrive.
    """

    def __init__(self, field: str = RESULT_FIELD):
        self.field = field
        self.buffer = ""
        self.start = None
        self.decoded = ""
        self.position = 0
        self.closed = False
        self.cursor = 0
        self.state = "object"
        self.key = None
        self.invalid = False

    def feed(self, fragment: str) -> str:
        """Append raw JSON and return newly decoded field text."""
        if self.closed or not fragment:
            return ""
        self.buffer += fragment
        if self.start is None and not self._locate():
            return ""
        before = len(self.decoded)
        self._decode()
        return self.decoded[before:]

    def _locate(self) -> bool:
        # Read root members in order. raw_decode skips each complete non-target
        # value, including its nested objects/arrays and quoted field names.
        decoder = json.JSONDecoder()
        while self.cursor < len(self.buffer):
            char = self.buffer[self.cursor]
            if char in " \t\r\n":
                self.cursor += 1
                continue
            if self.state == "object":
                if char != "{":
                    self.invalid = self.closed = True
                    return False
                self.state = "key"
            elif self.state == "key":
                if char == "}":
                    self.closed = True
                    return False
                if char != '"':
                    self.invalid = self.closed = True
                    return False
                try:
                    self.key, self.cursor = decoder.raw_decode(self.buffer, self.cursor)
                except json.JSONDecodeError:
                    return False
                self.state = "colon"
                continue
            elif self.state == "colon":
                if char != ":":
                    self.invalid = self.closed = True
                    return False
                self.state = "value"
            elif self.state == "value":
                if self.key == self.field:
                    if char != '"':
                        self.closed = True  # Not a string value; nothing to stream.
                        return False
                    self.start = self.position = self.cursor + 1
                    return True
                try:
                    _, end = decoder.raw_decode(self.buffer, self.cursor)
                except json.JSONDecodeError:
                    tail = self.buffer[self.cursor:]
                    if char not in '"{[-0123456789ntf' or (char in "ntf" and not any(
                            literal.startswith(tail) for literal in ("null", "true", "false"))):
                        self.invalid = self.closed = True
                    return False
                # Numbers can grow across fragments; wait for a delimiter.
                if end == len(self.buffer) or self.buffer[end] not in " \t\r\n,}":
                    return False
                self.cursor = end
                self.state = "separator"
                continue
            elif self.state == "separator":
                if char == "}":
                    self.closed = True
                    return False
                if char != ",":
                    self.invalid = self.closed = True
                    return False
                self.state = "key"
            self.cursor += 1
        return False

    def _decode(self) -> None:
        text, cursor = self.buffer, self.position
        pieces = []
        while cursor < len(text):
            character = text[cursor]
            if character == '"':
                self.closed = True
                cursor += 1
                break
            if character != "\\":
                end = cursor
                while end < len(text) and text[end] not in '"\\':
                    end += 1
                pieces.append(text[cursor:end])
                cursor = end
                continue
            if cursor + 1 >= len(text):
                break
            escape = text[cursor + 1]
            if escape == "u":
                if cursor + 6 > len(text):
                    break
                code = int(text[cursor + 2:cursor + 6], 16)
                if 0xD800 <= code <= 0xDBFF:
                    # A surrogate pair must be decoded together.
                    if cursor + 12 > len(text):
                        break
                    if text[cursor + 6:cursor + 8] == "\\u":
                        low = int(text[cursor + 8:cursor + 12], 16)
                        pieces.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
                        cursor += 12
                        continue
                pieces.append(chr(code))
                cursor += 6
                continue
            pieces.append({"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}.get(escape, escape))
            cursor += 2
        self.position = cursor
        self.decoded += "".join(pieces)


class DeltaBuffer:
    """Coalesce deltas per stream so each flush is one small JSONL record."""

    def __init__(self, interval: float = FLUSH_SECONDS, clock=time.monotonic):
        self.interval = interval
        self.clock = clock
        self.pending: dict[tuple[str, str], str] = {}
        self.last = clock()

    def add(self, stream: str, identity: str, text: str) -> list[dict]:
        if text:
            key = (stream, identity)
            self.pending[key] = self.pending.get(key, "") + text
        return self.flush() if self.clock() - self.last >= self.interval else []

    def flush(self, identity: str | None = None) -> list[dict]:
        """Emit pending text, optionally only for one stream identity."""
        events = []
        for key in list(self.pending):
            if identity is not None and key[1] != identity:
                continue
            text = self.pending.pop(key)
            if text:
                events.append({"type": "native.delta", "stream": key[0], "id": key[1], "text": text})
        if identity is None:
            self.last = self.clock()
        return events
