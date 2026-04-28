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


def test_duplicate_registration_raises():
    @register_filter
    class _Custom(FigureSourceFilter):
        figure_source = "test_only_filter_unique_xyz"

    with pytest.raises(ValueError, match="already registered"):
        @register_filter  # noqa
        class _Duplicate(FigureSourceFilter):  # noqa: F811
            figure_source = "test_only_filter_unique_xyz"
