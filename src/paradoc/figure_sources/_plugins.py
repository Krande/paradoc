"""Plugin discovery for the ``paradoc.figure_sources`` entry-point group.

Third-party packages register figure-source spec + filter classes by
declaring a callable under ``paradoc.figure_sources`` in their
``pyproject.toml``::

    [project.entry-points."paradoc.figure_sources"]
    fea_artefact_bundle = "ada.fem.results.docs:register_paradoc_block_sugar"

paradoc imports the callable on first use, invokes it with the
:class:`Dispatcher` below, and the callable registers whatever spec /
filter combos it wants. Idempotent: discovery fires at most once per
process, gated by ``_LOADED``.

Lazy-on-demand rather than eager-at-import: ``paradoc.figure_sources``
imports the registry-driven ``create_figure_source`` and the filter
registry at module load. If we discovered plugins at import time
we'd risk circular imports — a plugin's ``register_paradoc_block_sugar``
typically imports ``paradoc.figure_sources.models`` to subclass
``BaseFigureSource``. Deferring discovery until the first
``create_figure_source`` / ``get_filter_for`` call breaks that cycle.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .filters.base import FigureSourceFilter
    from .models import BaseFigureSource

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "paradoc.figure_sources"
_LOADED = False


class Dispatcher:
    """Plugin-side handle for registering spec + filter pairs.

    Passed to each entry-point callable as its single argument. Plugins
    don't import paradoc's internals directly — they call the
    ``register_spec`` / ``register_filter`` methods on whatever
    Dispatcher we hand them, which keeps the contract stable as the
    paradoc internals move around.
    """

    def register_spec(
        self,
        figure_source: str,
        spec_cls: "type[BaseFigureSource]",
    ) -> None:
        """Register a ``BaseFigureSource`` subclass for the given
        ``figure_source`` literal. After registration, a markdown block
        carrying ``figure_source: <name>`` parses into ``spec_cls``.
        """
        from .models import register_spec

        register_spec(figure_source, spec_cls)

    def register_filter(
        self,
        filter_cls: "type[FigureSourceFilter]",
    ) -> None:
        """Register a ``FigureSourceFilter`` subclass. The filter's
        ``figure_source`` class attribute determines which spec
        discriminator it handles.
        """
        from .filters.base import register_filter

        register_filter(filter_cls)


_DISPATCHER = Dispatcher()


def ensure_plugins_loaded() -> None:
    """Idempotently discover and invoke every ``paradoc.figure_sources``
    entry point. Called by :func:`create_figure_source` and
    :func:`get_filter_for` on first lookup so an unused build doesn't
    pay the plugin-import cost.
    """
    global _LOADED
    if _LOADED:
        return
    # Flip before iterating so a plugin that triggers a recursive
    # `create_figure_source` call (e.g. registering one spec by
    # delegating to another) doesn't re-enter discovery.
    _LOADED = True

    try:
        eps = entry_points(group=_ENTRY_POINT_GROUP)
    except Exception as exc:  # pragma: no cover - importlib quirks
        logger.warning(
            "paradoc.figure_sources entry-point discovery failed: %s",
            exc,
            exc_info=True,
        )
        return

    for ep in eps:
        try:
            handler = ep.load()
        except Exception as exc:
            logger.warning(
                "paradoc.figure_sources plugin %s: load failed: %s",
                ep.name,
                exc,
                exc_info=True,
            )
            continue
        if not callable(handler):
            logger.warning(
                "paradoc.figure_sources plugin %s: target %r is not callable",
                ep.name,
                handler,
            )
            continue
        try:
            handler(_DISPATCHER)
        except Exception as exc:
            logger.warning(
                "paradoc.figure_sources plugin %s: handler raised: %s",
                ep.name,
                exc,
                exc_info=True,
            )


def _reset_for_tests() -> None:
    """Test-only: rewind so a re-import of a plugin module gets picked
    up by the next ``ensure_plugins_loaded()`` call. Production builds
    never need this — discovery is one-shot per process by design."""
    global _LOADED
    _LOADED = False
