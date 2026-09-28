"""Explicit internal transport for fixed instructions and the current run contract."""
from __future__ import annotations

import json
from dataclasses import dataclass

from runtime_errors import ContractError


@dataclass(frozen=True)
class PromptParts:
    fixed: str
    dynamic: str

    def __post_init__(self):
        for value in (self.fixed, self.dynamic):
            if not isinstance(value, str) or not value.strip():
                raise ContractError("prompt_invalid", "Managed prompt parts must be nonempty text")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ContractError("prompt_invalid", "Managed prompt parts must be UTF-8") from error

    @property
    def full(self) -> str:
        return self.fixed + "\n\n" + self.dynamic

    def encode(self) -> str:
        return json.dumps({"version": 1, "fixed": self.fixed, "dynamic": self.dynamic}, ensure_ascii=False)

    @classmethod
    def decode(cls, text: str) -> PromptParts:
        # Only used when the host explicitly selects this protocol. User text,
        # including text resembling this object or role tags, is never parsed.
        try:
            value = json.loads(text)
        except (ValueError, TypeError) as error:
            raise ContractError("prompt_invalid", "Invalid managed prompt envelope") from error
        if (not isinstance(value, dict) or set(value) != {"version", "fixed", "dynamic"}
                or type(value["version"]) is not int or value["version"] != 1):
            raise ContractError("prompt_invalid", "Unsupported managed prompt envelope")
        return cls(value["fixed"], value["dynamic"])
