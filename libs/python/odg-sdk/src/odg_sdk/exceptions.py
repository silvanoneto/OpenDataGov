"""OpenDataGov SDK exceptions."""

from __future__ import annotations


class ODGError(Exception):
    """Base exception for all OpenDataGov SDK errors."""


class ODGAPIError(ODGError):
    """API request failed."""

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ODGAuthenticationError(ODGAPIError):
    """Authentication failed (401)."""


class ODGNotFoundError(ODGAPIError):
    """Resource not found (404)."""


class ODGValidationError(ODGAPIError):
    """Request validation failed (422)."""


class ODGConnectionError(ODGError):
    """Failed to connect to OpenDataGov API."""
