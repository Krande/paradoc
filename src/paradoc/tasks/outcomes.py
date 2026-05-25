"""Typed outcomes that tasks return for automatic OneDoc registration.

A task whose body returns an `Outcome` (or a list of them) gets its
outcome auto-dispatched onto OneDoc by the orchestrator after
`runner.run()` finishes. The dispatch path is:

  TableOutcome    → one.db_manager.add_table(...)
  PlotOutcome     → one.db_manager.add_plot(...)
  ThreeDOutcome   → one.db_manager.add_three_d(...)
  FilterOutcome   → one._filter_registry.register(...)

Cells whose result is not an Outcome (or a list of them) are passed
through untouched — they remain available via `runner.result_for(...)`
for downstream tasks to consume.

The dispatch fires on every build, even on cache hits. The cached
*data* (the DataFrame, the plotly Figure, the ThreeDData row, the
Filter instance) round-trips through pickle; the side effect of
registering it on a fresh OneDoc replays every time. That's the
right model — OneDoc is a per-build object, the Outcome is the
durable thing.

Why typed wrappers vs. tagged dicts:

- Editor / mypy can guide authors at the call site
  (`TableOutcome(key=..., df=...)` flags missing args).
- Pickle round-trip is dataclass-trivial (no custom __reduce__).
- The orchestrator's `isinstance(result, Outcome)` check stays
  fast and unambiguous.

Author-side: returning an Outcome from a task body is exactly the
shape a comparison-table or plot task wants. Tasks that don't
register anything return their natural data (or None).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Outcome:
    """Marker base for task-produced things that get registered on OneDoc.

    Subclassed by the concrete outcome types; the orchestrator
    `isinstance`-checks against Outcome to decide whether to dispatch.
    """


@dataclass
class TableOutcome(Outcome):
    """A pandas DataFrame to register on `OneDoc.db_manager.add_table`.

    `default_sort` is a `(column_name, ascending)` tuple matching
    `dataframe_to_table_data`'s parameter.
    """

    key: str
    df: Any  # pd.DataFrame; typed as Any to keep this module pandas-free
    caption: str = ""
    show_index: bool = False
    default_sort: Optional[tuple] = None


@dataclass
class PlotOutcome(Outcome):
    """A plotly Figure to register on `OneDoc.db_manager.add_plot`."""

    key: str
    fig: Any  # plotly Figure; Any to avoid the plotly import here
    caption: str = ""
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ThreeDOutcome(Outcome):
    """A pre-built `ThreeDData` row to register on `OneDoc.db_manager.add_three_d`.

    Tasks that bake GLBs typically construct the ThreeDData themselves
    (via `to_paradoc_rows(...)` or similar) — this wrapper just routes
    it through the dispatcher.
    """

    row: Any  # paradoc.db.models.ThreeDData


@dataclass
class FilterOutcome(Outcome):
    """A `Filter` instance to register on `OneDoc._filter_registry`.

    Filters carrying runtime data that doesn't fit into a TaskHandle
    (eg env-probed solver versions, per-case FeaCaseFilter wrappers
    around already-baked bundles) come out of tasks via this shape.
    """

    filter: Any  # paradoc.filters.Filter


def iter_outcomes(result: Any):
    """Yield every Outcome inside `result` (one-level flatten of list/tuple)."""
    if result is None:
        return
    if isinstance(result, Outcome):
        yield result
        return
    if isinstance(result, (list, tuple)):
        for item in result:
            if isinstance(item, Outcome):
                yield item


def dispatch_outcomes(runner, one) -> int:
    """Walk every cell result; register Outcomes on OneDoc. Returns the count.

    Called by the orchestrator after `runner.run()` and after filter
    discovery, BEFORE `bind_filter_handles` — so any FilterOutcome
    that gets registered here also gets its TaskHandle bound by the
    subsequent binding step.

    Lazy imports for `paradoc.db` so `paradoc.tasks.outcomes` stays
    importable without dragging pandas / plotly into modules that only
    need the dataclass shapes.
    """
    from paradoc.db import dataframe_to_table_data, plotly_figure_to_plot_data

    count = 0
    for cell_id, result in runner._results.items():
        for outcome in iter_outcomes(result):
            _dispatch_one(outcome, one, dataframe_to_table_data, plotly_figure_to_plot_data)
            count += 1
    return count


def _dispatch_one(outcome, one, dataframe_to_table_data, plotly_figure_to_plot_data) -> None:
    if isinstance(outcome, TableOutcome):
        if outcome.df is None:
            return
        one.db_manager.add_table(
            dataframe_to_table_data(
                key=outcome.key,
                df=outcome.df,
                caption=outcome.caption,
                show_index=outcome.show_index,
                default_sort=outcome.default_sort,
            )
        )
    elif isinstance(outcome, PlotOutcome):
        if outcome.fig is None:
            return
        kwargs: dict = {"key": outcome.key, "fig": outcome.fig, "caption": outcome.caption}
        if outcome.width is not None:
            kwargs["width"] = outcome.width
        if outcome.height is not None:
            kwargs["height"] = outcome.height
        one.db_manager.add_plot(plotly_figure_to_plot_data(**kwargs))
    elif isinstance(outcome, ThreeDOutcome):
        if outcome.row is None:
            return
        one.db_manager.add_three_d(outcome.row)
    elif isinstance(outcome, FilterOutcome):
        if outcome.filter is None:
            return
        one._filter_registry.register(outcome.filter)
    else:  # pragma: no cover — exhaustive over the subclasses above
        raise TypeError(f"unrecognized outcome type: {type(outcome).__name__}")
