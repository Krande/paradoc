"""End-to-end: a filter's @attr called from markdown."""

from __future__ import annotations

import textwrap

import pandas as pd

from paradoc import OneDoc
from paradoc.db import dataframe_to_table_data


def _make_doc(tmp_path, body, filters_code=None):
    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    (main_dir / "test.md").write_text(body)
    if filters_code is not None:
        (test_dir / "filters.py").write_text(textwrap.dedent(filters_code))
    return OneDoc(test_dir, work_dir=tmp_path / "work")


def test_scalar_attr_with_fmtspec(tmp_path):
    one = _make_doc(
        tmp_path,
        "First freq: ${ eig.first_freq:.2f } Hz\n",
        """
        from paradoc.filters import Filter, attr

        class Results(Filter):
            @attr
            def first_freq(self) -> float:
                return 12.34567

        eig = Results(name="eig")
        """,
    )
    one.compile("Out", export_format="html")
    text = (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text()
    assert "First freq: 12.35 Hz" in text


def test_filter_returning_table_view(tmp_path):
    one = _make_doc(
        tmp_path,
        "Here's the table:\n\n${ src.table }\n",
        """
        from paradoc.filters import Filter, TableView, attr

        class Source(Filter):
            @attr
            def table(self) -> TableView:
                return TableView(table_key="my_table", display_kwargs={"no_caption": True})

        src = Source(name="src")
        """,
    )
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    one.db_manager.add_table(dataframe_to_table_data(key="my_table", df=df, caption="hidden", show_index=False))
    one.compile("Out", export_format="html")
    text = (tmp_path / "work" / "_build" / "00-main" / "test.md").read_text()
    assert "${" not in text
    # nocaption flag should suppress the table caption
    assert "hidden" not in text
    # but the table data should be present in markdown form
    assert "A" in text and "B" in text


def test_unknown_attr_logs_error(tmp_path, caplog):
    import logging

    one = _make_doc(
        tmp_path,
        "${ src.missing }\n",
        """
        from paradoc.filters import Filter, attr

        class Source(Filter):
            @attr
            def value(self) -> int:
                return 1

        src = Source(name="src")
        """,
    )
    with caplog.at_level(logging.ERROR):
        one.compile("Out", export_format="html")
    assert any("missing" in r.message for r in caplog.records)


def test_unexpected_kwarg_logs_error(tmp_path, caplog):
    import logging

    one = _make_doc(
        tmp_path,
        "${ src.value(unknown_kwarg=1) }\n",
        """
        from paradoc.filters import Filter, attr

        class Source(Filter):
            @attr
            def value(self) -> int:
                return 1

        src = Source(name="src")
        """,
    )
    with caplog.at_level(logging.ERROR):
        one.compile("Out", export_format="html")
    assert any("unexpected keyword" in r.message for r in caplog.records)
