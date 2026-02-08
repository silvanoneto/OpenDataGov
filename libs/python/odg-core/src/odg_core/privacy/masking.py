"""PII masking strategies (ADR-070)."""

from __future__ import annotations

import hashlib
from typing import Protocol


class PIIMasker(Protocol):
    """Protocol for PII masking implementations."""

    def mask(self, value: str) -> str: ...


class HashMasker:
    """Mask by SHA-256 hashing (irreversible)."""

    def __init__(self, salt: str = "") -> None:
        self._salt = salt

    def mask(self, value: str) -> str:
        return hashlib.sha256(f"{self._salt}{value}".encode()).hexdigest()[:16]


class RedactMasker:
    """Mask by replacing with a fixed string."""

    def __init__(self, replacement: str = "[REDACTED]") -> None:
        self._replacement = replacement

    def mask(self, _value: str) -> str:
        return self._replacement


class PartialMasker:
    """Mask by showing only first/last N characters."""

    def __init__(self, show_first: int = 0, show_last: int = 4) -> None:
        self._show_first = show_first
        self._show_last = show_last

    def mask(self, value: str) -> str:
        if len(value) <= self._show_first + self._show_last:
            return "*" * len(value)
        prefix = value[: self._show_first]
        suffix = value[-self._show_last :] if self._show_last > 0 else ""
        middle = "*" * (len(value) - self._show_first - self._show_last)
        return f"{prefix}{middle}{suffix}"


# CPF masking: show only last 4 digits
CPF_MASKER = PartialMasker(show_first=0, show_last=4)


# Email masking: hash the local part, keep domain
class EmailMasker:
    """Mask email by hashing local part, keeping domain."""

    def mask(self, value: str) -> str:
        if "@" not in value:
            return HashMasker().mask(value)
        local, domain = value.rsplit("@", 1)
        hashed = hashlib.sha256(local.encode()).hexdigest()[:8]
        return f"{hashed}@{domain}"
