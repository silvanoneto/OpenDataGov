"""OpenDataGov Python SDK.

Official Python client for OpenDataGov REST and GraphQL APIs.
"""

from __future__ import annotations

from odg_sdk.client import OpenDataGovClient
from odg_sdk.exceptions import (
    ODGAPIError,
    ODGAuthenticationError,
    ODGError,
    ODGNotFoundError,
    ODGValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "OpenDataGovClient",
    "ODGError",
    "ODGAPIError",
    "ODGAuthenticationError",
    "ODGNotFoundError",
    "ODGValidationError",
]
