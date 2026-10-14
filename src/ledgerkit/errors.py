from typing import Any


class DomainError(Exception):
    """A business-rule failure. The message is shown to the caller (human or model),
    so it should say what went wrong and what to do about it."""

    def __init__(self, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
