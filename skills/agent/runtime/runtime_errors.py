"""Shared machine-readable runtime contract failures."""


class ContractError(Exception):
    """Represent a stable machine-readable refusal or runtime failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
