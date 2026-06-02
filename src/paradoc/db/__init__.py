"""Database module for paradoc table and plot data storage.

The `utils` re-exports below import pandas at module load. They're lazy via
PEP 562 so the serve path (paradoc.docstore → paradoc.db.DbManager) doesn't
drag pandas into containers built without it.
"""

from typing import TYPE_CHECKING

from .manager import DbManager
from .models import (
    PlotAnnotation,
    PlotData,
    TableAnnotation,
    TableCell,
    TableColumn,
    TableData,
    TableFilterConfig,
    TableSortConfig,
    ThreeDData,
)

if TYPE_CHECKING:
    from .utils import (
        apply_table_annotation,
        custom_function_to_plot_data,
        dataframe_to_plot_data,
        dataframe_to_table_data,
        parse_plot_reference,
        parse_table_reference,
        plotly_figure_to_plot_data,
        table_data_to_dataframe,
    )

_LAZY_UTILS = {
    "apply_table_annotation",
    "custom_function_to_plot_data",
    "dataframe_to_plot_data",
    "dataframe_to_table_data",
    "parse_plot_reference",
    "parse_table_reference",
    "plotly_figure_to_plot_data",
    "table_data_to_dataframe",
}

__all__ = [
    "DbManager",
    "TableData",
    "TableColumn",
    "TableCell",
    "TableSortConfig",
    "TableFilterConfig",
    "TableAnnotation",
    "PlotData",
    "PlotAnnotation",
    "ThreeDData",
    *sorted(_LAZY_UTILS),
]


def __getattr__(name):
    if name in _LAZY_UTILS:
        from importlib import import_module

        value = getattr(import_module(".utils", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | _LAZY_UTILS)
