"""Typed return wrappers that the resolver maps to markdown forms.

Each filter `@attr` returns one of these (or a plain scalar). The resolver
then picks the right substitution strategy based on the view type.

Keeping these as pydantic v2 models gives us free validation and lets
callers serialize a view for caching or diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class ViewBase(BaseModel):
    """Common base so the resolver can do `isinstance(value, ViewBase)`."""

    model_config = {"frozen": False, "arbitrary_types_allowed": True}


class TableView(ViewBase):
    """A reference to a DB-backed table, optionally with display kwargs.

    Phase 2 wires this to the existing `_get_table_markdown_from_db` path so
    we get caching, usage-count tracking, and DOCX figure registration for
    free.
    """

    table_key: str = Field(..., description="DB key of the underlying table.")
    display_kwargs: dict = Field(default_factory=dict)


class FigureView(ViewBase):
    """A 2D static figure (plot or pre-rendered image)."""

    plot_key: Optional[str] = Field(default=None, description="DB plot key, if backed by a plot.")
    image_path: Optional[Path] = Field(default=None, description="Pre-rendered image path.")
    caption: str = ""
    figure_id: Optional[str] = None
    display_kwargs: dict = Field(default_factory=dict)


class ThreeDView(ViewBase):
    """A 3D figure: a static PNG plus a key into the 3D asset store.

    Phase 4 fills in `glb_key` and the camera/preset linkage. Phase 6's
    frontend uses `glb_key` to fetch the binary from the asset transport.
    """

    image_path: Optional[Path] = Field(default=None, description="Pre-rendered PNG path.")
    glb_key: str = Field(..., description="3D asset store key (matches ThreeDData.key).")
    caption: str = ""
    figure_id: Optional[str] = None
    camera_preset: Optional[str] = None


class ScalarValue(ViewBase):
    """An explicit scalar wrapper for filter attrs that prefer typed returns.

    Filter attrs may return raw `int`/`float`/`str`/`bool` directly; the
    resolver handles those without requiring this wrapper. `ScalarValue`
    exists for filters that want to attach metadata (e.g. units) later.
    """

    value: Any
    units: Optional[str] = None
