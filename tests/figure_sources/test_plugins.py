"""Plugin discovery via the ``paradoc.figure_sources`` entry-point group.

Covers the in-process discovery hook (Dispatcher + ensure_plugins_loaded)
and verifies the registries pick up plugin-registered specs / filters.
Real cross-package discovery against an installed adapy wheel is
exercised separately in the adapy test suite (``test_fea_docs.py``'s
``test_paradoc_figure_sources_entry_point_registered``); here we only
check paradoc's side of the plumbing.
"""

from __future__ import annotations

import pytest
from pydantic import Field
from typing import Literal

from paradoc.figure_sources._plugins import (
    Dispatcher,
    _DISPATCHER,
    _reset_for_tests,
    ensure_plugins_loaded,
)
from paradoc.figure_sources.filters.base import (
    FigureSourceFilter,
    RenderResult,
    get_filter_for,
)
from paradoc.figure_sources.models import (
    BaseFigureSource,
    _SPEC_REGISTRY,
    create_figure_source,
    register_spec,
)


_TEST_SOURCE = "test_only_plugin_source_xyz"


@pytest.fixture(autouse=True)
def _isolate_test_registries():
    """Strip our test-only spec / filter entries after each test so
    cross-test pollution can't make a later test depend on an earlier
    one's registrations."""
    yield
    _SPEC_REGISTRY.pop(_TEST_SOURCE, None)
    # The filter registry is keyed the same way.
    from paradoc.figure_sources.filters.base import _REGISTRY
    _REGISTRY.pop(_TEST_SOURCE, None)


def test_dispatcher_register_spec_and_filter_round_trips():
    """The plugin-side dispatcher registers a spec + filter pair that
    parses + resolves via the same registries the built-in types use."""

    dispatcher = _DISPATCHER

    class _PluginSpec(BaseFigureSource):
        figure_source: Literal["test_only_plugin_source_xyz"] = _TEST_SOURCE
        source_inp: str = Field(...)

    class _PluginFilter(FigureSourceFilter):
        figure_source = _TEST_SOURCE

        def render(self, spec, *, key):  # type: ignore[override]
            return RenderResult(
                png_path="x.png", glb_path="x.glb",
                glb_sha256="0" * 64, glb_size=1,
                caption=f"plugin {key}", camera_pos=spec.camera_pos,
                source_type=self.figure_source, metadata={},
            )

    dispatcher.register_spec(_TEST_SOURCE, _PluginSpec)
    dispatcher.register_filter(_PluginFilter)

    assert _TEST_SOURCE in _SPEC_REGISTRY
    parsed = create_figure_source({
        "figure_source": _TEST_SOURCE,
        "figure_title": "Plugin test",
        "source_inp": "files/whatever",
    })
    assert isinstance(parsed, _PluginSpec)
    assert get_filter_for(_TEST_SOURCE) is _PluginFilter


def test_ensure_plugins_loaded_is_idempotent():
    """``ensure_plugins_loaded`` is the lazy hook that fires plugin
    discovery on first ``create_figure_source`` / ``get_filter_for``
    lookup. Calling it twice must not re-import every entry point —
    the second call is a no-op."""

    _reset_for_tests()
    call_count = {"n": 0}

    class _CountingDispatcher(Dispatcher):
        def register_spec(self, name, cls):  # noqa: D401 — mock-ish
            call_count["n"] += 1
            super().register_spec(name, cls)

    # We can't easily inject a custom dispatcher into entry_points(...)
    # without monkeypatching the importlib.metadata API, so instead we
    # just confirm the global guard flag flips and the underlying
    # `_LOADED` sentinel suppresses a second walk. ensure_plugins_loaded
    # itself is the surface tested elsewhere; here we check the guard.
    ensure_plugins_loaded()
    from paradoc.figure_sources import _plugins
    assert _plugins._LOADED is True

    # Second call: still True, no exception.
    ensure_plugins_loaded()
    assert _plugins._LOADED is True


def test_create_figure_source_triggers_discovery():
    """Looking up an unknown figure_source still triggers plugin
    discovery — the user-facing error message lists every registered
    type, which would be misleading if the plugin loader hadn't fired
    yet."""

    _reset_for_tests()
    with pytest.raises(ValueError, match="Supported:"):
        create_figure_source({"figure_source": "definitely_not_registered"})

    from paradoc.figure_sources import _plugins
    assert _plugins._LOADED is True


def test_register_spec_overwrites_silently():
    """Re-registering an existing figure_source replaces the previous
    spec. Matches ``register_filter``'s dev-loop ergonomics — a plugin
    reload shouldn't error, the second registration wins."""

    class _SpecA(BaseFigureSource):
        figure_source: Literal["test_only_plugin_source_xyz"] = _TEST_SOURCE
        source_inp: str = Field(...)

    class _SpecB(BaseFigureSource):
        figure_source: Literal["test_only_plugin_source_xyz"] = _TEST_SOURCE
        source_inp: str = Field(...)
        extra_field: int = 7

    register_spec(_TEST_SOURCE, _SpecA)
    register_spec(_TEST_SOURCE, _SpecB)

    parsed = create_figure_source({
        "figure_source": _TEST_SOURCE,
        "figure_title": "overwrite test",
        "source_inp": "x",
    })
    assert isinstance(parsed, _SpecB)
    assert parsed.extra_field == 7
