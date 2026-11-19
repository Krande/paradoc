"""Conditional text: `<!-- if ref -->` ... `<!-- else -->` ... `<!-- endif -->`."""

from __future__ import annotations

import pytest

from paradoc import OneDoc
from paradoc.filters import Filter, attr
from paradoc.substitution.conditions import ConditionError, apply_conditions

VALUES = {"a.yes": True, "a.no": False, "a.empty": "", "a.items": "* x"}


def _apply(text: str) -> str:
    return apply_conditions(text, VALUES.__getitem__)


def test_a_condition_keeps_the_branch_its_truth_says():
    text = "<!-- if a.yes -->\nkept\n<!-- else -->\ndropped\n<!-- endif -->\n"
    assert _apply(text) == "kept\n"
    assert _apply(text.replace("a.yes", "a.no")) == "dropped\n"
    assert _apply("<!-- if not a.no -->\nkept\n<!-- endif -->\nafter\n") == "kept\nafter\n"
    # a value's truth: an empty text is false, a list of items true
    assert _apply("<!-- if a.empty -->\nx\n<!-- endif -->\n<!-- if a.items -->\ny\n<!-- endif -->\n") == "y\n"


def test_conditions_nest_and_a_dropped_branch_is_not_evaluated():
    text = (
        "<!-- if a.no -->\n<!-- if a.unknown -->\nnever\n<!-- endif -->\n<!-- else -->\n"
        "<!-- if a.yes -->\ninner\n<!-- else -->\nnot inner\n<!-- endif -->\n<!-- endif -->\n"
    )
    assert _apply(text) == "inner\n"


def test_markers_in_a_code_fence_are_text():
    text = "```markdown\n<!-- if a.no -->\nshown\n<!-- endif -->\n```\n"
    assert _apply(text) == text


def test_an_inline_comment_is_not_a_condition():
    assert _apply("text <!-- if a.no --> more\n") == "text <!-- if a.no --> more\n"


@pytest.mark.parametrize(
    "text, match",
    [
        ("<!-- if a.yes -->\nx\n", "without its <!-- endif -->"),
        ("x\n<!-- endif -->\n", "endif --> without"),
        ("<!-- else -->\n", "else --> without"),
        ("<!-- if a.yes -->\n<!-- else -->\n<!-- else -->\n<!-- endif -->\n", "else --> without"),
        ("<!-- if a.unknown -->\nx\n<!-- endif -->\n", "cannot be evaluated"),
    ],
)
def test_markers_that_do_not_pair_up_or_resolve_are_errors(text, match):
    with pytest.raises(ConditionError, match=match):
        _apply(text)


class Member(Filter):
    def __init__(self, name: str, slender: bool):
        super().__init__(name)
        self._slender = slender

    @attr
    def slender(self) -> bool:
        return self._slender

    @attr
    def length(self) -> float:
        return 3.0


def test_a_document_keeps_the_branches_of_its_filters_and_variables(tmp_path, caplog):
    main = tmp_path / "doc" / "00-main"
    main.mkdir(parents=True)
    (main / "test.md").write_text(
        "# Members\n\n"
        "<!-- if m1.slender -->\nM1 is slender (${ m1.length:.1f } m).\n<!-- else -->\nM1 is stocky.\n<!-- endif -->\n\n"
        "<!-- if not m2.slender -->\nM2 is stocky.\n<!-- endif -->\n"
        # a dropped branch's substitutions are never resolved: no error for the missing attr
        "<!-- if m2.slender -->\n${ m2.missing }\n<!-- endif -->\n" "<!-- if draft -->\nDRAFT\n<!-- endif -->\n",
        encoding="utf-8",
    )
    one = OneDoc(tmp_path / "doc", work_dir=tmp_path / "work")
    one.add_filter(Member("m1", True))
    one.add_filter(Member("m2", False))
    one.variables["draft"] = False
    one.compile("Out", export_format="html")
    built = (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text(encoding="utf-8")
    assert "M1 is slender (3.0 m)." in built and "M2 is stocky." in built
    assert "M1 is stocky" not in built and "DRAFT" not in built and "<!-- if" not in built
    assert "missing" not in built and not any("missing" in r.message for r in caplog.records)


def test_a_document_with_an_unknown_condition_does_not_build(tmp_path):
    main = tmp_path / "doc" / "00-main"
    main.mkdir(parents=True)
    (main / "test.md").write_text("<!-- if nobody.home -->\nx\n<!-- endif -->\n", encoding="utf-8")
    one = OneDoc(tmp_path / "doc", work_dir=tmp_path / "work")
    with pytest.raises(ConditionError, match="no filter registered as 'nobody'"):
        one.compile("Out", export_format="html")
