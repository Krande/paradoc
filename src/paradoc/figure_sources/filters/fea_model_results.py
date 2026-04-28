"""FEA results figure source — stub until task runner ships."""

from __future__ import annotations

from ..models import FEAModelResults
from .base import FigureSourceFilter, register_filter


@register_filter
class FEAModelResultsFilter(FigureSourceFilter):
    figure_source = "fea_model_results"

    def render(self, spec, *, key):
        if not isinstance(spec, FEAModelResults):
            raise TypeError(
                f"FEAModelResultsFilter received non-FEA-results spec: {type(spec).__name__}"
            )
        raise NotImplementedError(
            "FEA results rendering requires the task runner (Phase 7+). "
            f"Would render {spec.output_file} field {spec.field!r} at {spec.camera_pos}."
        )
