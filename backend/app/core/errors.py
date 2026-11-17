from typing import Any


class AppError(Exception):
    """An error with an HTTP status, rendered as the standard envelope:
    `{"error": {"code", "message", **extra}}`. Raise from services; the handler
    in main.py turns it into a response."""

    def __init__(self, status_code: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra
