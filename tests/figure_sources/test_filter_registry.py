"""Figure-source filter registry."""

import pytest

from paradoc.figure_sources.filters import (
    CADModelFileFilter,
    get_filter_for,
    register_filter,
)
from paradoc.figure_sources.filters.base import FigureSourceFilter


def test_builtins_registered():
    assert get_filter_for("cad_model_file") is CADModelFileFilter
    assert get_filter_for("fea_model").figure_source == "fea_model"
    assert get_filter_for("fea_model_results").figure_source == "fea_model_results"


def test_unknown_raises():
    with pytest.raises(KeyError):
        get_filter_for("never_registered")


def test_duplicate_registration_overwrites():
    """Re-registration replaces the previous handler. Matches
    :func:`paradoc.figure_sources.models.register_spec`'s dev-loop
    ergonomics — reloading a plugin module shouldn't error, the
    second registration just wins. Cross-package collisions (two
    different packages claiming the same ``figure_source`` literal)
    are caught at the plugin-discovery layer instead.
    """

    @register_filter
    class _Custom(FigureSourceFilter):
        figure_source = "test_only_filter_unique_xyz"

    @register_filter
    class _Replacement(FigureSourceFilter):  # noqa: F811
        figure_source = "test_only_filter_unique_xyz"

    assert get_filter_for("test_only_filter_unique_xyz") is _Replacement
