"""Custom exceptions for the Flowerhub client."""

from __future__ import annotations

from typing import Any, Optional


class AuthenticationError(Exception):
    """Raised when authentication token expires and refresh fails."""


class ApiError(Exception):
    """Raised for non-auth HTTP errors and payload validation issues."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.payload = payload


__all__ = ["ApiError", "AuthenticationError"]
