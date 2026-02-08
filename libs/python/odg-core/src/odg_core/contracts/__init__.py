"""Data contract management (ADR-051)."""

from odg_core.contracts.loader import load_contract
from odg_core.contracts.validator import validate_data

__all__ = ["load_contract", "validate_data"]
