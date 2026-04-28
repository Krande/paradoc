"""Migrator tests: legacy syntax → unified `${...}`."""

import pytest

from paradoc.substitution.migrator import migrate_text


@pytest.mark.parametrize(
    "legacy,expected",
    [
        ("{{__my_table__}}", "${ my_table }"),
        ("{{__my_table__}}{tbl:index:no}", "${ my_table(show_index=False) }"),
        ("{{__t__}}{tbl:sortby:col}", '${ t(sort_by="col") }'),
        (
            "{{__t__}}{tbl:sortby:col:desc}",
            '${ t(sort_by="col", sort_ascending=False) }',
        ),
        ("{{__t__}}{tbl:filter:pat}", '${ t(filter_pattern="pat") }'),
        (
            "{{__t__}}{tbl:filter:pat:c}",
            '${ t(filter_pattern="pat", filter_column="c") }',
        ),
        ("{{__t__}}{tbl:nocaption}", "${ t(no_caption=True) }"),
        ("{{__p__}}{plt:width:800}", "${ p(width=800) }"),
        ("{{__p__}}{plt:height:600}", "${ p(height=600) }"),
        ("{{__p__}}{plt:nocaption}", "${ p(no_caption=True) }"),
        ("{{__p__}}{plt:format:svg}", '${ p(format="svg") }'),
        ("{{ my_var }}", "${ my_var }"),
    ],
)
def test_basic_rewrites(legacy, expected):
    out, n, warnings = migrate_text(legacy)
    assert out == expected
    assert n == 1
    assert warnings == []


def test_idempotent():
    text = '${ my_table } and ${ p(width=800) } and ${ x.y(k=1):.2f }'
    out, n, warnings = migrate_text(text)
    assert out == text
    assert n == 0
    assert warnings == []


def test_mixed_content():
    text = "Lead-in {{__a__}}{tbl:index:no} middle {{ var }} trailing {{__b__}}"
    out, n, _ = migrate_text(text)
    assert out == "Lead-in ${ a(show_index=False) } middle ${ var } trailing ${ b }"
    assert n == 3


def test_unknown_flag_warns_but_continues():
    text = "{{__t__}}{tbl:bogus:val}"
    out, _, warnings = migrate_text(text)
    assert out == "${ t }"
    assert any("bogus" in w for w in warnings)


def test_pipe_style_legacy_var_left_alone():
    text = "{{ var|fmt|extra }}"
    out, n, _ = migrate_text(text)
    assert out == text
    assert n == 0


def test_unclosed_annotation_left_alone():
    text = "{{__t__}}{tbl:index:no"
    out, _, warnings = migrate_text(text)
    assert "{{__t__}}" in out
    assert any("unclosed" in w for w in warnings)
