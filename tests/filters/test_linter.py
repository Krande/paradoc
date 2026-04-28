"""Linter surfaces unresolved substitutions with suggestions."""

import textwrap

from paradoc.filters import (
    Filter,
    FilterRegistry,
    attr,
    lint_unresolved_substitutions,
)


class _Demo(Filter):
    @attr
    def value(self) -> int:
        return 1

    @attr
    def value_two(self) -> int:
        return 2


def test_linter_flags_unknown_name(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("Some text ${ unknown_thing } more")

    reg = FilterRegistry()
    issues = lint_unresolved_substitutions(md_files=[md], registry=reg)
    assert len(issues) == 1
    assert issues[0].sub.name == "unknown_thing"


def test_linter_suggests_close_match(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("${ deemo.value }")

    reg = FilterRegistry()
    reg.register(_Demo(name="demo"))
    issues = lint_unresolved_substitutions(md_files=[md], registry=reg)
    assert len(issues) == 1
    assert "demo" in issues[0].suggestions


def test_linter_flags_unknown_attr(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("${ demo.valu }")  # typo close to 'value' (distance 1)

    reg = FilterRegistry()
    reg.register(_Demo(name="demo"))
    issues = lint_unresolved_substitutions(md_files=[md], registry=reg)
    assert len(issues) == 1
    assert issues[0].sub.attr == "valu"
    assert "value" in issues[0].suggestions


def test_extra_known_names_skip_linter(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("${ db_table_key }")

    reg = FilterRegistry()
    issues = lint_unresolved_substitutions(
        md_files=[md], registry=reg, extra_known_names=["db_table_key"]
    )
    assert issues == []


def test_resolved_attr_clean(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("${ demo.value }")

    reg = FilterRegistry()
    reg.register(_Demo(name="demo"))
    issues = lint_unresolved_substitutions(md_files=[md], registry=reg)
    assert issues == []
