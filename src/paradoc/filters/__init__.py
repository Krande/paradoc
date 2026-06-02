"""Filter classes — the bridge between tasks and the doc.

A `Filter` is a named, instantiable object that exposes computed values
through `@attr`-decorated methods. Markdown references like
`${ eig_main.first_freq }` resolve to a filter attribute call.

The supported attribute return types are:

- `ScalarValue` (or any value `apply_fmtspec` can format) → inline substitution
- `TableView` → block-level table substitution
- `FigureView` → block-level static figure substitution
- `ThreeDView` → block-level 3D figure substitution (Phase 4)
"""

from .base import Filter, attr
from .cache import AttrCache
from .discovery import discover_filters
from .linter import lint_unresolved_substitutions
from .registry import FilterRegistry
from .views import FigureView, ScalarValue, TableView, ThreeDView, ViewBase

__all__ = [
    "Filter",
    "attr",
    "AttrCache",
    "FilterRegistry",
    "discover_filters",
    "lint_unresolved_substitutions",
    "FigureView",
    "ScalarValue",
    "TableView",
    "ThreeDView",
    "ViewBase",
]
