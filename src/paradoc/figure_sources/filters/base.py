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
from typing import ClassVar, Optional, Union

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


@dataclass
class MarkdownChunk:
    """Raw markdown text spliced into the rendered block output.

    Filters that want to interleave structural prose (section headings,
    captions, gallery wrappers) between figures return a mixed list of
    :class:`RenderResult` and ``MarkdownChunk`` entries. The preprocessor
    walks the list in order: each :class:`RenderResult` registers a
    ``ThreeDData`` row and emits an image reference; each chunk is
    spliced as-is with no further processing.

    Chunks do NOT recursively resolve ``${ }`` substitutions — the
    text is emitted verbatim. Filters that need substitutions inside
    chunks must compute the substituted text themselves.
    """

    text: str


# A filter's ``render()`` may return a single :class:`RenderResult` (one
# figure per block), a list of them (multi-figure expansion, used by the
# FEA artefact-bundle source where one block emits one figure per mode),
# or a mixed list of :class:`RenderResult` and :class:`MarkdownChunk`
# entries (interleaved figures + headings, used by per-case grouping
# filters). The preprocessor normalises to a list and walks entries in
# order: RenderResults register ThreeDData rows + emit image tags,
# MarkdownChunks splice their text as-is.
RenderEntry = Union[RenderResult, MarkdownChunk]
RenderOutput = Union[RenderEntry, list[RenderEntry]]


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

    Parameters
    ----------
    bundle_root :
        Directory the build artifact is staged in (i.e. ``<doc_build>/``).
        Filters that bake outputs write them under this dir and return
        paths relative to it.
    doc_root :
        The dir containing the report's ``paradoc.toml`` (and conventionally
        ``tasks.py`` / ``filters.py`` / ``_assets/``). When the report
        configures ``source_dir = "subdir"`` in paradoc.toml the markdown
        lives one level down, but the doc-root layout (including any
        baked-asset trees produced by the task DAG) stays at this path.
        Filters that need to read pre-baked artefacts from the source
        tree pull them from here. Falls back to ``bundle_root.parent``
        (the legacy convention) when the caller doesn't supply one,
        which keeps existing single-flat-dir reports working.
    """

    figure_source: ClassVar[str] = ""

    def __init__(
        self,
        *,
        bundle_root: Path,
        doc_root: Optional[Path] = None,
    ) -> None:
        self.bundle_root = bundle_root
        self.doc_root = doc_root if doc_root is not None else bundle_root.parent

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
