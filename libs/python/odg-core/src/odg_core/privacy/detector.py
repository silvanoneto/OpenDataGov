"""PII detection by column name patterns (ADR-070)."""

from __future__ import annotations

import re

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cpf", re.compile(r"(?i)^(cpf|cnpj|tax_id|ssn|social_security)")),
    ("email", re.compile(r"(?i)(email|e_mail)")),
    ("phone", re.compile(r"(?i)(phone|telefone|celular|mobile)")),
    ("address", re.compile(r"(?i)(address|endereco|street|cep|zip_code|postal)")),
    ("name", re.compile(r"(?i)^(full_name|first_name|last_name|nome)")),
    ("birth_date", re.compile(r"(?i)(birth|nascimento|dob)")),
    ("financial", re.compile(r"(?i)(credit_card|card_number|account_number|iban)")),
    ("document", re.compile(r"(?i)(passport|rg_number|driver_license)")),
]


def detect_pii_columns(column_names: list[str]) -> list[dict[str, str]]:
    """Detect potential PII columns by name pattern matching.

    Returns a list of dicts with 'column' and 'pii_type' keys.
    """
    detections = []
    for col in column_names:
        for pii_type, pattern in _PII_PATTERNS:
            if pattern.search(col):
                detections.append({"column": col, "pii_type": pii_type})
                break
    return detections
