"""FEA model geometry figure source — stub until task runner ships."""

from __future__ import annotations

from ..models import FEAModel
from .base import FigureSourceFilter, register_filter


@register_filter
class FEAModelFilter(FigureSourceFilter):
    figure_source = "fea_model"

    def render(self, spec, *, key):
        if not isinstance(spec, FEAModel):
            raise TypeError(f"FEAModelFilter received non-FEA spec: {type(spec).__name__}")
        raise NotImplementedError(
            "FEA model rendering requires the task runner (Phase 7+). "
            f"Would render {spec.source_inp} ({spec.fea_format}) at {spec.camera_pos}."
        )
