from __future__ import annotations

from typing import Any


class DocGateError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def error_body(error: DocGateError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.details:
        payload["details"] = error.details
    return {"error": payload}

