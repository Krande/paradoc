"""Typed Outcomes + orchestrator auto-dispatch."""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from paradoc.tasks import (
    FilterOutcome,
    Outcome,
    PlotOutcome,
    Runner,
    TableOutcome,
    TaskRegistry,
    ThreeDOutcome,
    dispatch_outcomes,
    iter_outcomes,
    reset_default_registry,
    task,
)

_ONE_DOC_AVAILABLE = importlib.util.find_spec("paradoc.document") is not None


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- iter_outcomes ----------------


def test_iter_outcomes_single():
    o = TableOutcome("k", df=None)
    assert list(iter_outcomes(o)) == [o]


def test_iter_outcomes_list():
    a, b = TableOutcome("k1", df=None), PlotOutcome("k2", fig=None)
    assert list(iter_outcomes([a, b])) == [a, b]


def test_iter_outcomes_tuple():
    a, b = TableOutcome("k", df=None), ThreeDOutcome(row=None)
    assert list(iter_outcomes((a, b))) == [a, b]


def test_iter_outcomes_none():
    assert list(iter_outcomes(None)) == []


def test_iter_outcomes_regular_data():
    """Non-Outcome cell results yield nothing — they're just data."""
    assert list(iter_outcomes({"key": "value"})) == []
    assert list(iter_outcomes(42)) == []
    assert list(iter_outcomes("hello")) == []


def test_iter_outcomes_mixed_list_filters_non_outcomes():
    """A list mixing data + Outcomes yields only the Outcomes."""
    o = TableOutcome("k", df=None)
    assert list(iter_outcomes([o, "junk", 42])) == [o]


def test_iter_outcomes_only_one_level_deep():
    """Nested lists are NOT recursively walked — task authors return flat."""
    o = TableOutcome("k", df=None)
    nested = [[o]]
    # The inner list is not an Outcome instance; the outer iter sees it
    # but the implementation only goes one level deep.
    assert list(iter_outcomes(nested)) == []


# ---------------- dispatch_outcomes ----------------


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_dispatch_routes_each_outcome_kind(monkeypatch):
    """One TableOutcome, one PlotOutcome, one ThreeDOutcome, one FilterOutcome
    → matching add_* / register calls."""
    from paradoc.filters import Filter, attr
    import paradoc.tasks.outcomes as outcomes_mod

    # Mock paradoc.db boundaries so MagicMock figs/dfs don't trip JSON
    # serialization inside plotly_figure_to_plot_data /
    # dataframe_to_table_data — we're testing the dispatch routing, not
    # those converters.
    import paradoc.db as db_mod
    monkeypatch.setattr(db_mod, "dataframe_to_table_data", lambda **kw: ("table_data", kw))
    monkeypatch.setattr(db_mod, "plotly_figure_to_plot_data", lambda **kw: ("plot_data", kw))

    class _F(Filter):
        @attr
        def x(self) -> int:
            return 1

    @task
    def emit_table():
        return TableOutcome("k_table", df="fake_df", caption="c1")

    @task
    def emit_plot():
        return PlotOutcome("k_plot", fig="fake_fig", caption="c2")

    @task
    def emit_three_d():
        return ThreeDOutcome(row="fake_row")

    @task
    def emit_filter():
        return FilterOutcome(_F(name="f1"))

    reg = TaskRegistry()
    for t in (emit_table, emit_plot, emit_three_d, emit_filter):
        reg.register(t)
    reset_default_registry()

    runner = Runner(reg)
    runner.run()

    one = MagicMock()
    real_filters: list = []
    one._filter_registry.register.side_effect = real_filters.append

    n = dispatch_outcomes(runner, one)
    assert n == 4
    one.db_manager.add_table.assert_called_once()
    one.db_manager.add_plot.assert_called_once()
    one.db_manager.add_three_d.assert_called_once_with("fake_row")
    assert len(real_filters) == 1
    assert real_filters[0].name == "f1"


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_dispatch_flattens_lists(monkeypatch):
    """A single cell returning [TableOutcome, ThreeDOutcome] gets both
    routed."""
    import paradoc.db as db_mod
    monkeypatch.setattr(db_mod, "dataframe_to_table_data", lambda **kw: kw)

    @task
    def emit_pair():
        return [
            TableOutcome("k1", df="fake_df"),
            ThreeDOutcome(row="fake_row"),
        ]

    reg = TaskRegistry()
    reg.register(emit_pair)
    reset_default_registry()

    runner = Runner(reg)
    runner.run()

    one = MagicMock()
    n = dispatch_outcomes(runner, one)
    assert n == 2
    one.db_manager.add_table.assert_called_once()
    one.db_manager.add_three_d.assert_called_once_with("fake_row")


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_dispatch_skips_outcomes_with_none_payload():
    """TableOutcome(df=None) / PlotOutcome(fig=None) etc. are silent no-ops
    so tasks can return an Outcome shell with empty data without crashing."""

    @task
    def empty_emit():
        return [
            TableOutcome("k", df=None),
            PlotOutcome("k", fig=None),
            ThreeDOutcome(row=None),
            FilterOutcome(filter=None),
        ]

    reg = TaskRegistry()
    reg.register(empty_emit)
    reset_default_registry()

    runner = Runner(reg)
    runner.run()

    one = MagicMock()
    # iter_outcomes yields 4 entries; dispatch returns 4 (it counts
    # everything iter_outcomes produces, including the no-op skips).
    n = dispatch_outcomes(runner, one)
    assert n == 4
    one.db_manager.add_table.assert_not_called()
    one.db_manager.add_plot.assert_not_called()
    one.db_manager.add_three_d.assert_not_called()
    one._filter_registry.register.assert_not_called()


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_dispatch_ignores_non_outcome_cell_results():
    """Tasks returning regular data don't trigger any registration."""

    @task
    def returns_data():
        return {"name": "assembly", "v": 1}

    reg = TaskRegistry()
    reg.register(returns_data)
    reset_default_registry()

    runner = Runner(reg)
    runner.run()

    one = MagicMock()
    n = dispatch_outcomes(runner, one)
    assert n == 0
    one.db_manager.assert_not_called()


# ---------------- end-to-end through orchestrator ----------------


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_orchestrator_dispatches_outcomes_before_compile(tmp_path: Path, monkeypatch):
    """`build_document` walks task results post-run and registers Outcomes
    on OneDoc before compile.

    Probe: register an outcome, then in a patched compile() inspect the
    db_manager state to confirm the table is there.
    """
    from paradoc.document import OneDoc
    from paradoc.tasks.orchestrator import build_document

    doc = tmp_path / "mydoc"
    doc.mkdir()
    # Declare an output so the orchestrator's compile loop fires —
    # default (empty outputs) skips compile in the post-static-output-
    # type refactor.
    (doc / "paradoc.toml").write_text(
        textwrap.dedent(
            """
            [build.default]
            outputs = ["docx"]
            """
        ).lstrip()
    )
    (doc / "tasks.py").write_text(
        textwrap.dedent(
            """
            import pandas as pd
            from paradoc.tasks import task, TableOutcome

            @task
            def emit():
                return TableOutcome("my_table", df=pd.DataFrame({"x": [1, 2]}),
                                    caption="x")
            """
        ).lstrip()
    )
    (doc / "00-main").mkdir()
    (doc / "00-main" / "01.md").write_text("# t\n")

    keys_at_compile = []

    def _capture(self, name, **kw):
        # db_manager exposes registered tables via list_tables() / similar;
        # for the test we just probe via the attribute the dispatcher used.
        # Use try/except to keep this test stable if db_manager internals
        # shift.
        try:
            keys = self.db_manager.list_tables()
        except AttributeError:
            keys = list(getattr(self.db_manager, "_tables", {}).keys())
        keys_at_compile.append(keys)

    monkeypatch.setattr(OneDoc, "compile", _capture)

    build_document(doc, work_dir=tmp_path / "work", no_cache=True)

    # The Outcome dispatch fired before compile, so my_table should be
    # in db_manager by the time compile() is invoked.
    assert keys_at_compile, "compile never called"
    assert any("my_table" in keys for keys in keys_at_compile), keys_at_compile