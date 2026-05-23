"""Base class and registry for figure-source filters.

The plan calls for "drop a file in `filters/<source_type>.py`, gets
auto-discovered". The implementation is a small registry keyed by the
`figure_source` literal each subclass declares. Out-of-tree plugins
register via the ``paradoc.figure_sources`` entry-point group — see
``paradoc.figure_sources._plugins``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Union

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


# A filter's ``render()`` may return a single :class:`RenderResult` (one
# figure per block) or a list of them (multi-figure expansion, used by
# the FEA artefact-bundle source where one block emits one figure per
# mode). The caller normalises to a list and emits one markdown image
# tag + one ``ThreeDData`` row per entry.
RenderOutput = Union[RenderResult, list[RenderResult]]


_REGISTRY: dict[str, type["FigureSourceFilter"]] = {}


def register_filter(cls: type["FigureSourceFilter"]) -> type["FigureSourceFilter"]:
    """Decorator: register `cls` under its `figure_source` literal.

    Plugin handlers also call this (indirectly, via
    :class:`paradoc.figure_sources._plugins.Dispatcher.register_filter`)
    to register out-of-tree filters. Re-registration with the same
    discriminator overwrites silently — matches ``register_spec``'s
    dev-loop ergonomics.
    """
    _REGISTRY[cls.figure_source] = cls
    return cls


def get_filter_for(figure_source: str) -> type["FigureSourceFilter"]:
    """Look up a filter class by `figure_source` literal.

    Fires plugin discovery on first call so a filter registered via
    entry point resolves the same way the in-tree ones do. Mirrors
    :func:`paradoc.figure_sources.models.create_figure_source`'s
    lazy discovery.
    """
    from .._plugins import ensure_plugins_loaded

    ensure_plugins_loaded()

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

    def render(self, spec: FigureSourceSpec, *, key: str) -> RenderOutput:
        """Run the filter for `spec`, producing PNG + glb + metadata.

        Implementations write outputs under `self.bundle_root/assets/...`
        and return paths relative to `self.bundle_root`.

        Single-figure filters return one :class:`RenderResult`.
        Multi-figure filters (FEA bundle's ``per_mode`` layout, future
        history-output series) return a list — paradoc emits one
        markdown image tag + one ``ThreeDData`` row per entry, with
        derived keys ``<key>``, ``<key>_2``, ``<key>_3``, …
        """
        raise NotImplementedError(
            f"{type(self).__name__} did not implement render()"
        )
