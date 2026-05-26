"""Figure-source filters — one file per `figure_source` value.

Filters are auto-discovered: drop a module here that defines a class
inheriting from `FigureSourceFilter`, and it registers itself for the
`figure_source` value declared on its spec.
"""

from .base import (
    FigureSourceFilter,
    MarkdownChunk,
    RenderResult,
    get_filter_for,
    register_filter,
)
from .cad_model_file import CADModelFileFilter
from .fea_model import FEAModelFilter
from .fea_model_results import FEAModelResultsFilter

__all__ = [
    "FigureSourceFilter",
    "MarkdownChunk",
    "RenderResult",
    "register_filter",
    "get_filter_for",
    "CADModelFileFilter",
    "FEAModelFilter",
    "FEAModelResultsFilter",
]
