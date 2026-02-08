"""AI-driven metadata discovery (ADR-042).

Auto-classifies columns and suggests tags based on column names
and data patterns. Follows the B-Swarm pattern where suggestions
require RACI approval unless auto_approve=true.
"""

from __future__ import annotations

import re

# Common PII patterns
_PII_PATTERNS = [
    re.compile(r"(?i)(cpf|ssn|social.?security)"),
    re.compile(r"(?i)(e[-_.]?mail)"),
    re.compile(r"(?i)(phone|telefone|celular)"),
    re.compile(r"(?i)(address|endereco|cep|zip)"),
    re.compile(r"(?i)(birth.?date|nascimento|dob)"),
    re.compile(r"(?i)(passport|rg|identity)"),
    re.compile(r"(?i)(credit.?card|cartao)"),
]


def classify_columns(columns: list[str]) -> list[dict[str, str | bool]]:
    """Auto-classify columns for PII based on naming patterns.

    Returns a list of dicts with column name, is_pii, and suggested_tag.
    """
    results = []
    for col in columns:
        is_pii = any(p.search(col) for p in _PII_PATTERNS)
        result: dict[str, str | bool] = {
            "column": col,
            "is_pii": is_pii,
        }
        if is_pii:
            result["suggested_tag"] = "pii"
        results.append(result)
    return results
