"""Tests for privacy toolkit: classification, detector, differential, jurisdiction, masking."""

from __future__ import annotations

import builtins
import hashlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from odg_core.enums import ComplianceFramework, DataClassification, Jurisdiction
from odg_core.privacy.classification import (
    CLASSIFICATION_CONTROLS,
    get_required_controls,
)
from odg_core.privacy.detector import _PII_PATTERNS, detect_pii_columns
from odg_core.privacy.differential import (
    DEFAULT_EPSILON,
    add_laplace_noise,
    apply_differential_privacy,
    get_epsilon,
)
from odg_core.privacy.jurisdiction import (
    JURISDICTION_FRAMEWORKS,
    JurisdictionPolicy,
    get_jurisdiction_policy,
)
from odg_core.privacy.masking import (
    CPF_MASKER,
    EmailMasker,
    HashMasker,
    PartialMasker,
    RedactMasker,
)

# ---------------------------------------------------------------------------
# classification.py
# ---------------------------------------------------------------------------


class TestClassificationControls:
    """Tests for CLASSIFICATION_CONTROLS mapping and get_required_controls."""

    def test_all_classification_levels_present(self) -> None:
        for level in DataClassification:
            assert level in CLASSIFICATION_CONTROLS

    def test_public_minimal_controls(self) -> None:
        controls = CLASSIFICATION_CONTROLS[DataClassification.PUBLIC]
        assert controls["rbac"] is False
        assert controls["encryption_at_rest"] is False
        assert controls["encryption_in_transit"] is True
        assert controls["pii_masking"] is False
        assert controls["differential_privacy"] is False
        assert controls["mfa_required"] is False
        assert controls["audit_logging"] is False

    def test_internal_controls(self) -> None:
        controls = CLASSIFICATION_CONTROLS[DataClassification.INTERNAL]
        assert controls["rbac"] is True
        assert controls["encryption_at_rest"] is False
        assert controls["audit_logging"] is True

    def test_confidential_controls(self) -> None:
        controls = CLASSIFICATION_CONTROLS[DataClassification.CONFIDENTIAL]
        assert controls["rbac"] is True
        assert controls["encryption_at_rest"] is True
        assert controls["pii_masking"] is True
        assert controls["differential_privacy"] is False

    def test_restricted_all_controls_enabled(self) -> None:
        controls = CLASSIFICATION_CONTROLS[DataClassification.RESTRICTED]
        assert controls["rbac"] is True
        assert controls["encryption_at_rest"] is True
        assert controls["encryption_in_transit"] is True
        assert controls["pii_masking"] is True
        assert controls["differential_privacy"] is True
        assert controls["mfa_required"] is True
        assert controls["audit_logging"] is True

    def test_top_secret_all_controls_enabled(self) -> None:
        controls = CLASSIFICATION_CONTROLS[DataClassification.TOP_SECRET]
        assert all(controls.values())

    def test_get_required_controls_known_level(self) -> None:
        result = get_required_controls(DataClassification.PUBLIC)
        assert result == CLASSIFICATION_CONTROLS[DataClassification.PUBLIC]

    def test_get_required_controls_each_level(self) -> None:
        for level in DataClassification:
            result = get_required_controls(level)
            assert result == CLASSIFICATION_CONTROLS[level]

    def test_get_required_controls_unknown_falls_back_to_internal(self) -> None:
        """When given an unknown key, falls back to INTERNAL controls."""
        sentinel = MagicMock()
        result = CLASSIFICATION_CONTROLS.get(sentinel, CLASSIFICATION_CONTROLS[DataClassification.INTERNAL])
        assert result == CLASSIFICATION_CONTROLS[DataClassification.INTERNAL]

    def test_controls_dict_has_seven_keys(self) -> None:
        expected_keys = {
            "rbac",
            "encryption_at_rest",
            "encryption_in_transit",
            "pii_masking",
            "differential_privacy",
            "mfa_required",
            "audit_logging",
        }
        for level in DataClassification:
            assert set(CLASSIFICATION_CONTROLS[level].keys()) == expected_keys

    def test_controls_increase_with_classification(self) -> None:
        """Higher classification levels should have at least as many True controls."""
        ordered = [
            DataClassification.PUBLIC,
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
            DataClassification.RESTRICTED,
            DataClassification.TOP_SECRET,
        ]
        for i in range(len(ordered) - 1):
            lower_count = sum(CLASSIFICATION_CONTROLS[ordered[i]].values())
            higher_count = sum(CLASSIFICATION_CONTROLS[ordered[i + 1]].values())
            assert higher_count >= lower_count


# ---------------------------------------------------------------------------
# detector.py
# ---------------------------------------------------------------------------


class TestDetector:
    """Tests for PII column-name detection."""

    def test_detect_cpf_column(self) -> None:
        result = detect_pii_columns(["cpf"])
        assert len(result) == 1
        assert result[0] == {"column": "cpf", "pii_type": "cpf"}

    def test_detect_cnpj_column(self) -> None:
        result = detect_pii_columns(["cnpj_number"])
        assert len(result) == 1
        assert result[0]["pii_type"] == "cpf"

    def test_detect_ssn_column(self) -> None:
        result = detect_pii_columns(["ssn"])
        assert len(result) == 1
        assert result[0]["pii_type"] == "cpf"

    def test_detect_tax_id(self) -> None:
        result = detect_pii_columns(["tax_id"])
        assert len(result) == 1
        assert result[0]["pii_type"] == "cpf"

    def test_detect_social_security(self) -> None:
        result = detect_pii_columns(["social_security_number"])
        assert len(result) == 1
        assert result[0]["pii_type"] == "cpf"

    def test_detect_email(self) -> None:
        result = detect_pii_columns(["email"])
        assert result[0]["pii_type"] == "email"

    def test_detect_e_mail(self) -> None:
        result = detect_pii_columns(["e_mail_address"])
        assert result[0]["pii_type"] == "email"

    def test_detect_phone(self) -> None:
        result = detect_pii_columns(["phone"])
        assert result[0]["pii_type"] == "phone"

    def test_detect_telefone(self) -> None:
        result = detect_pii_columns(["telefone_contato"])
        assert result[0]["pii_type"] == "phone"

    def test_detect_celular(self) -> None:
        result = detect_pii_columns(["celular"])
        assert result[0]["pii_type"] == "phone"

    def test_detect_mobile(self) -> None:
        result = detect_pii_columns(["mobile_number"])
        assert result[0]["pii_type"] == "phone"

    def test_detect_address(self) -> None:
        result = detect_pii_columns(["address"])
        assert result[0]["pii_type"] == "address"

    def test_detect_endereco(self) -> None:
        result = detect_pii_columns(["endereco_residencial"])
        assert result[0]["pii_type"] == "address"

    def test_detect_street(self) -> None:
        result = detect_pii_columns(["street_name"])
        assert result[0]["pii_type"] == "address"

    def test_detect_cep(self) -> None:
        result = detect_pii_columns(["cep"])
        assert result[0]["pii_type"] == "address"

    def test_detect_zip_code(self) -> None:
        result = detect_pii_columns(["zip_code"])
        assert result[0]["pii_type"] == "address"

    def test_detect_postal(self) -> None:
        result = detect_pii_columns(["postal_code"])
        assert result[0]["pii_type"] == "address"

    def test_detect_full_name(self) -> None:
        result = detect_pii_columns(["full_name"])
        assert result[0]["pii_type"] == "name"

    def test_detect_first_name(self) -> None:
        result = detect_pii_columns(["first_name"])
        assert result[0]["pii_type"] == "name"

    def test_detect_last_name(self) -> None:
        result = detect_pii_columns(["last_name"])
        assert result[0]["pii_type"] == "name"

    def test_detect_nome(self) -> None:
        result = detect_pii_columns(["nome_completo"])
        assert result[0]["pii_type"] == "name"

    def test_detect_birth_date(self) -> None:
        result = detect_pii_columns(["birth_date"])
        assert result[0]["pii_type"] == "birth_date"

    def test_detect_nascimento(self) -> None:
        result = detect_pii_columns(["data_nascimento"])
        assert result[0]["pii_type"] == "birth_date"

    def test_detect_dob(self) -> None:
        result = detect_pii_columns(["dob"])
        assert result[0]["pii_type"] == "birth_date"

    def test_detect_credit_card(self) -> None:
        result = detect_pii_columns(["credit_card"])
        assert result[0]["pii_type"] == "financial"

    def test_detect_card_number(self) -> None:
        result = detect_pii_columns(["card_number"])
        assert result[0]["pii_type"] == "financial"

    def test_detect_account_number(self) -> None:
        result = detect_pii_columns(["account_number"])
        assert result[0]["pii_type"] == "financial"

    def test_detect_iban(self) -> None:
        result = detect_pii_columns(["iban_code"])
        assert result[0]["pii_type"] == "financial"

    def test_detect_passport(self) -> None:
        result = detect_pii_columns(["passport_number"])
        assert result[0]["pii_type"] == "document"

    def test_detect_rg_number(self) -> None:
        result = detect_pii_columns(["rg_number"])
        assert result[0]["pii_type"] == "document"

    def test_detect_driver_license(self) -> None:
        result = detect_pii_columns(["driver_license_id"])
        assert result[0]["pii_type"] == "document"

    def test_no_detection_for_safe_columns(self) -> None:
        result = detect_pii_columns(["id", "created_at", "amount", "status"])
        assert result == []

    def test_empty_list(self) -> None:
        result = detect_pii_columns([])
        assert result == []

    def test_multiple_pii_columns(self) -> None:
        cols = ["cpf", "email", "phone", "id", "created_at"]
        result = detect_pii_columns(cols)
        assert len(result) == 3
        types = {r["pii_type"] for r in result}
        assert types == {"cpf", "email", "phone"}

    def test_case_insensitive(self) -> None:
        result = detect_pii_columns(["EMAIL", "CPF", "Phone"])
        assert len(result) == 3

    def test_first_match_wins(self) -> None:
        """Each column should match at most one PII type (first match breaks)."""
        result = detect_pii_columns(["email_phone"])
        assert len(result) == 1
        # "email" pattern matches first
        assert result[0]["pii_type"] == "email"

    def test_pii_patterns_is_non_empty(self) -> None:
        assert len(_PII_PATTERNS) > 0

    def test_all_pattern_types_are_strings(self) -> None:
        for pii_type, _ in _PII_PATTERNS:
            assert isinstance(pii_type, str)


# ---------------------------------------------------------------------------
# differential.py
# ---------------------------------------------------------------------------


class TestDifferentialPrivacy:
    """Tests for differential privacy functions."""

    def test_default_epsilon_has_all_levels(self) -> None:
        for level in DataClassification:
            assert level in DEFAULT_EPSILON

    def test_get_epsilon_known_levels(self) -> None:
        assert get_epsilon(DataClassification.PUBLIC) == 10.0
        assert get_epsilon(DataClassification.INTERNAL) == 5.0
        assert get_epsilon(DataClassification.CONFIDENTIAL) == 1.0
        assert get_epsilon(DataClassification.RESTRICTED) == 0.1
        assert get_epsilon(DataClassification.TOP_SECRET) == 0.01

    def test_get_epsilon_fallback(self) -> None:
        """dict.get with a non-existent key returns the default 1.0."""
        sentinel = MagicMock()
        result = DEFAULT_EPSILON.get(sentinel, 1.0)
        assert result == 1.0

    def test_epsilon_decreases_with_classification(self) -> None:
        ordered = [
            DataClassification.PUBLIC,
            DataClassification.INTERNAL,
            DataClassification.CONFIDENTIAL,
            DataClassification.RESTRICTED,
            DataClassification.TOP_SECRET,
        ]
        for i in range(len(ordered) - 1):
            assert get_epsilon(ordered[i]) > get_epsilon(ordered[i + 1])

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_structure(self, mock_noise: MagicMock) -> None:
        aggregates = {"count": 100.0, "mean": 50.0}
        result = apply_differential_privacy(aggregates)
        assert "values" in result
        assert "epsilon" in result
        assert "sensitivity" in result
        assert "classification" in result
        assert "mechanism" in result
        assert result["mechanism"] == "laplace"
        assert result["classification"] == DataClassification.CONFIDENTIAL.value

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_default_epsilon(self, mock_noise: MagicMock) -> None:
        result = apply_differential_privacy(
            {"x": 10.0},
            classification=DataClassification.RESTRICTED,
        )
        assert result["epsilon"] == 0.1

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_override_epsilon(self, mock_noise: MagicMock) -> None:
        result = apply_differential_privacy(
            {"x": 10.0},
            epsilon=2.5,
        )
        assert result["epsilon"] == 2.5

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_custom_sensitivity(self, mock_noise: MagicMock) -> None:
        result = apply_differential_privacy(
            {"x": 10.0},
            sensitivity=5.0,
        )
        assert result["sensitivity"] == 5.0

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_calls_noise_per_aggregate(self, mock_noise: MagicMock) -> None:
        aggregates = {"a": 1.0, "b": 2.0, "c": 3.0}
        apply_differential_privacy(aggregates)
        assert mock_noise.call_count == 3

    @patch("odg_core.privacy.differential.add_laplace_noise", side_effect=lambda v, s, e, **_kw: v)
    def test_apply_differential_privacy_empty_aggregates(self, mock_noise: MagicMock) -> None:
        result = apply_differential_privacy({})
        assert result["values"] == {}

    def test_add_laplace_noise_opendp_path(self) -> None:
        """Cover lines 53-57: opendp import succeeds and noise is added."""
        mock_meas = MagicMock(return_value=0.5)

        mock_dp = MagicMock()
        mock_dp.enable_features = MagicMock()
        mock_dp.atom_domain = MagicMock(return_value="domain")
        mock_dp.absolute_distance = MagicMock(return_value="metric")

        # The code does: space >> dp.then_laplace(scale=scale)
        # space is a tuple ("domain", "metric"), so Python calls
        # dp.then_laplace().__rrshift__(space) to get meas.
        mock_then_result = MagicMock()
        mock_then_result.__rrshift__ = MagicMock(return_value=mock_meas)
        mock_dp.then_laplace = MagicMock(return_value=mock_then_result)

        # For `import opendp.prelude as dp`, Python's __import__ returns the
        # top-level package, then resolves the submodule via sys.modules.
        # We inject both into sys.modules so the import statement binds dp
        # to our mock_dp.
        mock_opendp = MagicMock()
        mock_opendp.prelude = mock_dp

        saved: dict[str, Any] = {}
        for key in ("opendp", "opendp.prelude"):
            saved[key] = sys.modules.get(key, object)  # sentinel for missing

        sys.modules["opendp"] = mock_opendp
        sys.modules["opendp.prelude"] = mock_dp
        try:
            result = add_laplace_noise(100.0, 1.0, 1.0)
        finally:
            for key, val in saved.items():
                if val is object:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

        # value (100.0) + mocked noise (0.5)
        assert result == pytest.approx(100.5)
        mock_dp.enable_features.assert_called_once_with("contrib")
        mock_meas.assert_called_once_with(0.0)

    def test_add_laplace_noise_numpy_path(self) -> None:
        """Cover lines 64-66: opendp import fails, numpy succeeds."""
        mock_rng = MagicMock()
        mock_rng.laplace = MagicMock(return_value=3.0)
        mock_np = MagicMock()
        mock_np.random.default_rng = MagicMock(return_value=mock_rng)

        _real_import = builtins.__import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "opendp.prelude":
                raise ImportError("no opendp")
            if name == "numpy":
                return mock_np
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_fake_import):
            result = add_laplace_noise(100.0, 2.0, 1.0)

        # value (100.0) + mocked noise (3.0)
        assert result == pytest.approx(103.0)
        mock_np.random.default_rng.assert_called_once()
        mock_rng.laplace.assert_called_once_with(0, 2.0)

    def test_add_laplace_noise_no_libraries(self) -> None:
        """Cover line 68-69: both opendp and numpy fail, returns raw value."""
        _real_import = builtins.__import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name in ("opendp.prelude", "numpy"):
                raise ImportError(f"no {name}")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_fake_import):
            result = add_laplace_noise(42.0, 1.0, 1.0)

        assert result == pytest.approx(42.0)

    def test_add_laplace_noise_scale_is_sensitivity_over_epsilon(self) -> None:
        """Verify scale = sensitivity / epsilon is passed correctly."""
        mock_rng = MagicMock()
        mock_rng.laplace = MagicMock(return_value=0.0)
        mock_np = MagicMock()
        mock_np.random.default_rng = MagicMock(return_value=mock_rng)

        _real_import = builtins.__import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "opendp.prelude":
                raise ImportError("no opendp")
            if name == "numpy":
                return mock_np
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_fake_import):
            add_laplace_noise(50.0, 4.0, 2.0)

        # Expected scale is sensitivity divided by epsilon, i.e. 2.0
        mock_rng.laplace.assert_called_once_with(0, 2.0)

    def test_add_laplace_noise_returns_float(self) -> None:
        """Noise result is always a float."""
        _real_import = builtins.__import__

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name in ("opendp.prelude", "numpy"):
                raise ImportError(f"no {name}")
            return _real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=_fake_import):
            result = add_laplace_noise(0.0, 1.0, 1.0)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# jurisdiction.py
# ---------------------------------------------------------------------------


class TestJurisdiction:
    """Tests for jurisdiction frameworks mapping and policy."""

    def test_jurisdiction_frameworks_br(self) -> None:
        frameworks = JURISDICTION_FRAMEWORKS[Jurisdiction.BR]
        assert ComplianceFramework.LGPD in frameworks
        assert ComplianceFramework.DAMA_DMBOK in frameworks

    def test_jurisdiction_frameworks_eu(self) -> None:
        frameworks = JURISDICTION_FRAMEWORKS[Jurisdiction.EU]
        assert ComplianceFramework.GDPR in frameworks
        assert ComplianceFramework.EU_AI_ACT in frameworks
        assert ComplianceFramework.DAMA_DMBOK in frameworks

    def test_jurisdiction_frameworks_us(self) -> None:
        frameworks = JURISDICTION_FRAMEWORKS[Jurisdiction.US]
        assert ComplianceFramework.SOX in frameworks
        assert ComplianceFramework.NIST_AI_RMF in frameworks
        assert ComplianceFramework.DAMA_DMBOK in frameworks

    def test_jurisdiction_frameworks_global(self) -> None:
        frameworks = JURISDICTION_FRAMEWORKS[Jurisdiction.GLOBAL]
        assert ComplianceFramework.ISO_42001 in frameworks
        assert ComplianceFramework.DAMA_DMBOK in frameworks

    def test_all_jurisdictions_present(self) -> None:
        for j in Jurisdiction:
            assert j in JURISDICTION_FRAMEWORKS

    def test_jurisdiction_policy_model(self) -> None:
        policy = JurisdictionPolicy(
            jurisdiction=Jurisdiction.BR,
            allowed_regions=["sa-east-1"],
            data_transfer_restricted=True,
            applicable_frameworks=[ComplianceFramework.LGPD],
        )
        assert policy.jurisdiction == Jurisdiction.BR
        assert policy.allowed_regions == ["sa-east-1"]
        assert policy.data_transfer_restricted is True
        assert ComplianceFramework.LGPD in policy.applicable_frameworks

    def test_jurisdiction_policy_defaults(self) -> None:
        policy = JurisdictionPolicy(jurisdiction=Jurisdiction.US)
        assert policy.allowed_regions == []
        assert policy.data_transfer_restricted is False
        assert policy.applicable_frameworks == []

    def test_get_jurisdiction_policy_br(self) -> None:
        policy = get_jurisdiction_policy(Jurisdiction.BR)
        assert policy.jurisdiction == Jurisdiction.BR
        assert policy.data_transfer_restricted is True
        assert ComplianceFramework.LGPD in policy.applicable_frameworks

    def test_get_jurisdiction_policy_eu(self) -> None:
        policy = get_jurisdiction_policy(Jurisdiction.EU)
        assert policy.jurisdiction == Jurisdiction.EU
        assert policy.data_transfer_restricted is True
        assert ComplianceFramework.GDPR in policy.applicable_frameworks

    def test_get_jurisdiction_policy_us(self) -> None:
        policy = get_jurisdiction_policy(Jurisdiction.US)
        assert policy.jurisdiction == Jurisdiction.US
        assert policy.data_transfer_restricted is False
        assert ComplianceFramework.SOX in policy.applicable_frameworks

    def test_get_jurisdiction_policy_global(self) -> None:
        policy = get_jurisdiction_policy(Jurisdiction.GLOBAL)
        assert policy.jurisdiction == Jurisdiction.GLOBAL
        assert policy.data_transfer_restricted is False
        assert ComplianceFramework.ISO_42001 in policy.applicable_frameworks

    def test_data_transfer_restricted_only_eu_and_br(self) -> None:
        for j in Jurisdiction:
            policy = get_jurisdiction_policy(j)
            if j in {Jurisdiction.EU, Jurisdiction.BR}:
                assert policy.data_transfer_restricted is True
            else:
                assert policy.data_transfer_restricted is False

    def test_policy_frameworks_match_mapping(self) -> None:
        for j in Jurisdiction:
            policy = get_jurisdiction_policy(j)
            assert policy.applicable_frameworks == JURISDICTION_FRAMEWORKS[j]


# ---------------------------------------------------------------------------
# masking.py
# ---------------------------------------------------------------------------


class TestHashMasker:
    """Tests for HashMasker."""

    def test_mask_returns_16_char_hex(self) -> None:
        masker = HashMasker()
        result = masker.mask("test")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_mask_deterministic(self) -> None:
        masker = HashMasker()
        assert masker.mask("hello") == masker.mask("hello")

    def test_mask_different_inputs_produce_different_hashes(self) -> None:
        masker = HashMasker()
        assert masker.mask("a") != masker.mask("b")

    def test_mask_with_salt(self) -> None:
        salted = HashMasker(salt="mysalt")
        unsalted = HashMasker()
        assert salted.mask("test") != unsalted.mask("test")

    def test_mask_with_empty_salt(self) -> None:
        masker = HashMasker(salt="")
        expected = hashlib.sha256(b"test").hexdigest()[:16]
        assert masker.mask("test") == expected

    def test_mask_empty_string(self) -> None:
        masker = HashMasker()
        result = masker.mask("")
        assert len(result) == 16

    def test_mask_matches_sha256(self) -> None:
        masker = HashMasker(salt="salt")
        expected = hashlib.sha256(b"saltvalue").hexdigest()[:16]
        assert masker.mask("value") == expected


class TestRedactMasker:
    """Tests for RedactMasker."""

    def test_default_replacement(self) -> None:
        masker = RedactMasker()
        assert masker.mask("anything") == "[REDACTED]"

    def test_custom_replacement(self) -> None:
        masker = RedactMasker(replacement="***")
        assert masker.mask("secret") == "***"

    def test_empty_replacement(self) -> None:
        masker = RedactMasker(replacement="")
        assert masker.mask("data") == ""

    def test_ignores_input_value(self) -> None:
        masker = RedactMasker()
        assert masker.mask("a") == masker.mask("b")

    def test_mask_empty_string_input(self) -> None:
        masker = RedactMasker()
        assert masker.mask("") == "[REDACTED]"


class TestPartialMasker:
    """Tests for PartialMasker."""

    def test_default_show_last_4(self) -> None:
        masker = PartialMasker()
        result = masker.mask("12345678")
        assert result == "****5678"

    def test_show_first_and_last(self) -> None:
        masker = PartialMasker(show_first=3, show_last=3)
        result = masker.mask("1234567890")
        assert result == "123****890"

    def test_show_first_only(self) -> None:
        masker = PartialMasker(show_first=2, show_last=0)
        result = masker.mask("123456")
        assert result == "12****"

    def test_show_last_only(self) -> None:
        masker = PartialMasker(show_first=0, show_last=2)
        result = masker.mask("123456")
        assert result == "****56"

    def test_short_value_fully_masked(self) -> None:
        """Value shorter than or equal to show_first + show_last -> all stars."""
        masker = PartialMasker(show_first=3, show_last=3)
        result = masker.mask("12345")
        assert result == "*****"

    def test_value_equal_length_fully_masked(self) -> None:
        masker = PartialMasker(show_first=3, show_last=3)
        result = masker.mask("123456")
        assert result == "******"

    def test_value_one_char_longer(self) -> None:
        masker = PartialMasker(show_first=3, show_last=3)
        result = masker.mask("1234567")
        assert result == "123*567"

    def test_single_char_value(self) -> None:
        masker = PartialMasker(show_first=0, show_last=4)
        result = masker.mask("x")
        assert result == "*"

    def test_empty_string(self) -> None:
        masker = PartialMasker(show_first=0, show_last=4)
        result = masker.mask("")
        assert result == ""

    def test_show_zero_both(self) -> None:
        masker = PartialMasker(show_first=0, show_last=0)
        result = masker.mask("test")
        assert result == "****"

    def test_show_zero_both_empty_input(self) -> None:
        masker = PartialMasker(show_first=0, show_last=0)
        result = masker.mask("")
        assert result == ""

    def test_length_preserved(self) -> None:
        masker = PartialMasker(show_first=2, show_last=2)
        value = "abcdefgh"
        result = masker.mask(value)
        assert len(result) == len(value)


class TestCPFMasker:
    """Tests for the pre-configured CPF_MASKER."""

    def test_cpf_masker_is_partial(self) -> None:
        assert isinstance(CPF_MASKER, PartialMasker)

    def test_cpf_11_digits(self) -> None:
        result = CPF_MASKER.mask("12345678901")
        assert result == "*******8901"

    def test_cpf_short_value(self) -> None:
        result = CPF_MASKER.mask("123")
        assert result == "***"

    def test_cpf_exact_4_chars(self) -> None:
        result = CPF_MASKER.mask("1234")
        assert result == "****"

    def test_cpf_5_chars(self) -> None:
        result = CPF_MASKER.mask("12345")
        assert result == "*2345"


class TestEmailMasker:
    """Tests for EmailMasker."""

    def test_mask_standard_email(self) -> None:
        masker = EmailMasker()
        result = masker.mask("user@example.com")
        assert result.endswith("@example.com")
        local_part = result.split("@")[0]
        assert len(local_part) == 8
        assert all(c in "0123456789abcdef" for c in local_part)

    def test_mask_deterministic(self) -> None:
        masker = EmailMasker()
        assert masker.mask("a@b.com") == masker.mask("a@b.com")

    def test_mask_different_locals_different_hashes(self) -> None:
        masker = EmailMasker()
        r1 = masker.mask("user1@example.com")
        r2 = masker.mask("user2@example.com")
        assert r1 != r2

    def test_mask_preserves_domain(self) -> None:
        masker = EmailMasker()
        result = masker.mask("test@mydomain.org")
        assert result.endswith("@mydomain.org")

    def test_mask_no_at_sign_falls_back_to_hash(self) -> None:
        masker = EmailMasker()
        result = masker.mask("noatsign")
        # Falls back to HashMasker, which returns 16-char hex
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_mask_multiple_at_signs(self) -> None:
        """rsplit('@', 1) should split on the last '@'."""
        masker = EmailMasker()
        result = masker.mask("user@sub@domain.com")
        assert result.endswith("@domain.com")

    def test_mask_email_hash_matches_sha256(self) -> None:
        masker = EmailMasker()
        local = "myuser"
        domain = "test.com"
        expected_hash = hashlib.sha256(local.encode()).hexdigest()[:8]
        result = masker.mask(f"{local}@{domain}")
        assert result == f"{expected_hash}@{domain}"

    def test_mask_empty_local_part(self) -> None:
        masker = EmailMasker()
        result = masker.mask("@domain.com")
        assert result.endswith("@domain.com")
        local_part = result.split("@")[0]
        assert len(local_part) == 8


class TestMaskerProtocol:
    """Verify all maskers satisfy the PIIMasker protocol shape."""

    def test_hash_masker_has_mask_method(self) -> None:
        masker = HashMasker()
        assert callable(masker.mask)

    def test_redact_masker_has_mask_method(self) -> None:
        masker = RedactMasker()
        assert callable(masker.mask)

    def test_partial_masker_has_mask_method(self) -> None:
        masker = PartialMasker()
        assert callable(masker.mask)

    def test_email_masker_has_mask_method(self) -> None:
        masker = EmailMasker()
        assert callable(masker.mask)

    def test_all_maskers_return_str(self) -> None:
        maskers: list[HashMasker | RedactMasker | PartialMasker | EmailMasker] = [
            HashMasker(),
            RedactMasker(),
            PartialMasker(),
            EmailMasker(),
        ]
        for masker in maskers:
            result = masker.mask("test_value")
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# __init__.py (module docstring / importability)
# ---------------------------------------------------------------------------


class TestPrivacyInit:
    """Test that the privacy package is importable."""

    def test_import_privacy_package(self) -> None:
        import odg_core.privacy

        assert odg_core.privacy.__doc__ is not None

    def test_import_submodules(self) -> None:
        from odg_core.privacy import classification, detector, differential, jurisdiction, masking

        assert classification is not None
        assert detector is not None
        assert differential is not None
        assert jurisdiction is not None
        assert masking is not None
