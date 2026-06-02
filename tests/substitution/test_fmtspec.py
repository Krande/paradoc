"""Unit tests for the format-spec subset."""

import pytest

from paradoc.substitution import SubstitutionError, apply_fmtspec, validate_fmtspec


class TestValidate:
    @pytest.mark.parametrize(
        "spec",
        [".2f", ".4f", ".2e", ".3E", ".2g", "d", "5d", ",d", ",.2f", "%", ".2%"],
    )
    def test_allowed(self, spec):
        validate_fmtspec(spec)

    @pytest.mark.parametrize(
        "spec",
        ["", ".2x", "?", ".2", "{:.2f}", " .2f", ".2f "],
    )
    def test_rejected(self, spec):
        with pytest.raises(SubstitutionError):
            validate_fmtspec(spec)


class TestApply:
    def test_no_spec_returns_str(self):
        assert apply_fmtspec(3.14, None) == "3.14"
        assert apply_fmtspec("hi", None) == "hi"

    def test_float(self):
        assert apply_fmtspec(3.14159, ".2f") == "3.14"
        assert apply_fmtspec(1234.5, ",.2f") == "1,234.50"

    def test_int(self):
        assert apply_fmtspec(1234567, ",d") == "1,234,567"

    def test_percent(self):
        assert apply_fmtspec(0.1234, ".1%") == "12.3%"

    def test_type_mismatch_raises(self):
        with pytest.raises(SubstitutionError, match="failed to format"):
            apply_fmtspec("not a number", ".2f")
