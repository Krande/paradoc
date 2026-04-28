"""Base class and registry for figure-source filters.

The plan calls for "drop a file in `filters/<source_type>.py`, gets
auto-discovered". The implementation is a small registry keyed by the
`figure_source` literal each subclass declares.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ..models import FigureSourceSpec


@dataclass
class RenderResult:
    """Output of running a figure-source filter at build time.

    All paths are relative to the bundle root (`<doc_build>/`) so the
    bundle stays portable for the REST/S3 follow-up.
    """

    png_path: str
    glb_path: str
    glb_sha256: str
    glb_size: int
    caption: str
    camera_pos: str
    source_type: str
    metadata: dict


_REGISTRY: dict[str, type["FigureSourceFilter"]] = {}


def register_filter(cls: type["FigureSourceFilter"]) -> type["FigureSourceFilter"]:
    """Decorator: register `cls` under its `figure_source` literal."""
    if cls.figure_source in _REGISTRY:
        raise ValueError(
            f"figure_source filter for {cls.figure_source!r} already registered"
        )
    _REGISTRY[cls.figure_source] = cls
    return cls


def get_filter_for(figure_source: str) -> type["FigureSourceFilter"]:
    """Look up a filter class by `figure_source` literal."""
    if figure_source not in _REGISTRY:
        raise KeyError(f"no figure_source filter registered for {figure_source!r}")
    return _REGISTRY[figure_source]


class FigureSourceFilter:
    """Base for figure-source filter implementations.

    Subclasses set the class variable `figure_source` to match the spec
    discriminator and implement `render`.

    `bundle_root` is the directory the build artifact is staged in (i.e.
    `<doc_build>/`). Filters write everything under it.
    """

    figure_source: ClassVar[str] = ""

    def __init__(self, *, bundle_root: Path) -> None:
        self.bundle_root = bundle_root

    def render(self, spec: FigureSourceSpec, *, key: str) -> RenderResult:
        """Run the filter for `spec`, producing PNG + glb + metadata.

        Implementations write outputs under `self.bundle_root/assets/...`
        and return paths relative to `self.bundle_root`.
        """
        raise NotImplementedError(
            f"{type(self).__name__} did not implement render()"
        )
