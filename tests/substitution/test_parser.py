"""Unit tests for the `${...}` parser."""

import pytest

from paradoc.substitution import (
    SubstitutionError,
    find_substitutions,
    parse_substitution_body,
)


class TestParseBody:
    def test_bare_name(self):
        sub = parse_substitution_body("my_table")
        assert sub.name == "my_table"
        assert sub.attr is None
        assert sub.kwargs == {}
        assert sub.fmtspec is None

    def test_name_with_attr(self):
        sub = parse_substitution_body("eig_main.first_freq")
        assert sub.name == "eig_main"
        assert sub.attr == "first_freq"

    def test_kwargs_only(self):
        sub = parse_substitution_body("my_table(sort_by=\"col_a\", show_index=False)")
        assert sub.name == "my_table"
        assert sub.kwargs == {"sort_by": "col_a", "show_index": False}

    def test_kwargs_with_attr(self):
        sub = parse_substitution_body("eig_main.mode_shape(mode=3)")
        assert sub.name == "eig_main"
        assert sub.attr == "mode_shape"
        assert sub.kwargs == {"mode": 3}

    def test_fmtspec(self):
        sub = parse_substitution_body("eig_main.first_freq:.2f")
        assert sub.fmtspec == ".2f"

    def test_fmtspec_with_kwargs(self):
        sub = parse_substitution_body("x.y(k=1):.3e")
        assert sub.kwargs == {"k": 1}
        assert sub.fmtspec == ".3e"

    def test_whitespace_tolerant(self):
        sub = parse_substitution_body("  my_table  ")
        assert sub.name == "my_table"

    @pytest.mark.parametrize(
        "literal,expected",
        [
            ("k=1", 1),
            ("k=1.5", 1.5),
            ("k=True", True),
            ("k=False", False),
            ("k=None", None),
            ("k=\"hello\"", "hello"),
            ("k='single'", "single"),
        ],
    )
    def test_literal_types(self, literal, expected):
        sub = parse_substitution_body(f"x({literal})")
        assert sub.kwargs == {"k": expected}


class TestParseRejects:
    def test_positional_args(self):
        with pytest.raises(SubstitutionError, match="positional"):
            parse_substitution_body("x(1, 2)")

    def test_expression_value(self):
        with pytest.raises(SubstitutionError, match="literal"):
            parse_substitution_body("x(k=1+2)")

    def test_name_lookup_value(self):
        with pytest.raises(SubstitutionError, match="literal"):
            parse_substitution_body("x(k=other_var)")

    def test_call_value(self):
        with pytest.raises(SubstitutionError, match="literal"):
            parse_substitution_body("x(k=foo())")

    def test_starargs(self):
        with pytest.raises(SubstitutionError):
            parse_substitution_body("x(*[1])")

    def test_kwargs_double_splat(self):
        with pytest.raises(SubstitutionError, match=r"\*\*kwargs"):
            parse_substitution_body("x(**d)")

    def test_unclosed_args(self):
        with pytest.raises(SubstitutionError, match="unclosed"):
            parse_substitution_body("x(k=1")

    def test_duplicate_kwarg(self):
        with pytest.raises(SubstitutionError, match="duplicate"):
            parse_substitution_body("x(k=1, k=2)")

    def test_empty_fmtspec(self):
        with pytest.raises(SubstitutionError, match="empty format"):
            parse_substitution_body("x:")

    def test_garbage_trailing(self):
        with pytest.raises(SubstitutionError, match="trailing"):
            parse_substitution_body("x.y(k=1) garbage")

    def test_unparseable(self):
        with pytest.raises(SubstitutionError):
            parse_substitution_body("123_starts_with_digit")


class TestFindSubstitutions:
    def test_finds_inline(self):
        text = "Mean is ${mean.value:.2f} units"
        subs = list(find_substitutions(text))
        assert len(subs) == 1
        assert subs[0].name == "mean"
        assert subs[0].attr == "value"
        assert subs[0].fmtspec == ".2f"

    def test_finds_multiple(self):
        text = "${a} and ${b.c} and ${d(k=1)}"
        subs = list(find_substitutions(text))
        assert [s.name for s in subs] == ["a", "b", "d"]

    def test_ignores_inline_math(self):
        text = "The formula $x^2 + y^2 = z^2$ but ${a} matches"
        subs = list(find_substitutions(text))
        assert [s.name for s in subs] == ["a"]

    def test_span_is_exact(self):
        text = "before ${x.y} after"
        sub = next(find_substitutions(text))
        assert text[sub.span[0]:sub.span[1]] == "${x.y}"
