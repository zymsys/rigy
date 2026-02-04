"""Tests for warning policy controls."""

from __future__ import annotations

import warnings

import pytest

from rigy.errors import ValidationError
from rigy.warning_policy import (
    KNOWN_CODES,
    RigyWarning,
    WarningPolicy,
    emit_warning,
    parse_code_list,
)


class TestParseCodeList:
    def test_single_code(self):
        assert parse_code_list("W01") == frozenset({"W01"})

    def test_multiple_codes(self):
        assert parse_code_list("W01,W02") == frozenset({"W01", "W02"})

    def test_whitespace_stripped(self):
        assert parse_code_list("W01 , W03") == frozenset({"W01", "W03"})

    def test_empty_string(self):
        assert parse_code_list("") == frozenset()

    def test_unknown_code_rejected(self):
        with pytest.raises(ValueError, match="Unknown warning code.*W99"):
            parse_code_list("W99")

    def test_mixed_valid_invalid_rejected(self):
        with pytest.raises(ValueError, match="Unknown warning code"):
            parse_code_list("W01,W99")


class TestEmitWarning:
    def test_default_emits_rigy_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            emit_warning("W01", "test message")
        assert len(w) == 1
        assert issubclass(w[0].category, RigyWarning)
        assert "[W01]" in str(w[0].message)

    def test_suppressed(self):
        policy = WarningPolicy(suppress=frozenset({"W01"}))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            emit_warning("W01", "test message", policy=policy)
        assert len(w) == 0

    def test_warn_as_error(self):
        policy = WarningPolicy(warn_as_error=frozenset({"W01"}))
        with pytest.raises(ValidationError, match=r"\[W01\]"):
            emit_warning("W01", "test message", policy=policy)

    def test_unaffected_code_still_warns(self):
        policy = WarningPolicy(suppress=frozenset({"W02"}))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            emit_warning("W01", "test message", policy=policy)
        assert len(w) == 1

    def test_none_policy_emits_warning(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            emit_warning("W03", "test", policy=None)
        assert len(w) == 1


class TestKnownCodes:
    def test_contains_expected_codes(self):
        assert KNOWN_CODES == {"W01", "W02", "W03"}
