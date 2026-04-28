"""Typed specs for figure-source comment blocks.

Each `figure_source: <type>` value maps to one of these subclasses. The
`figure_source` literal acts as the discriminator.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class CameraPosition(str, Enum):
    """Camera preset names. Mirrors `paradoc.camera.presets.BUILTIN_PRESETS`.

    Custom presets defined in `paradoc.toml [cameras.custom.<name>]` are
    accepted at runtime (we don't enum-restrict them); this enum just lists
    the always-available builtins for IDE completion.
    """

    ISO_1 = "iso_1"
    ISO_2 = "iso_2"
    ISO_3 = "iso_3"
    ISO_4 = "iso_4"
    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class FEAFormat(str, Enum):
    ABAQUS = "abaqus"
    SESAM = "sesam"
    ANSYS = "ansys"
    NASTRAN = "nastran"


class BaseFigureSource(BaseModel):
    """Common fields across all figure-source specs."""

    figure_source: str
    figure_title: str
    camera_pos: str = Field("iso_3", description="Camera preset name (built-in or custom).")

    model_config = {"frozen": False}


class CADModelFile(BaseFigureSource):
    figure_source: Literal["cad_model_file"] = "cad_model_file"
    source_inp: Path = Field(..., description="Path to the CAD model file (STEP, IFC, etc.).")


class FEAModel(BaseFigureSource):
    figure_source: Literal["fea_model"] = "fea_model"
    fea_format: FEAFormat
    source_inp: Path = Field(..., description="Path to the FEA model input file.")


class FEAModelResults(BaseFigureSource):
    figure_source: Literal["fea_model_results"] = "fea_model_results"
    fea_format: FEAFormat
    source_inp: Path = Field(..., description="Path to the FEA model input file.")
    output_file: Path = Field(..., description="Path to the results file (ODB, SIN, RMED).")
    field: str = Field(..., description="Field variable to visualize (e.g. 'S' for stress).")
    task_id: Optional[str] = Field(
        default=None,
        description=(
            "Reserved (Phase 7): task identifier producing `output_file`. "
            "Used by the future task runner to ensure the result is up-to-date."
        ),
    )


FigureSourceSpec = Union[CADModelFile, FEAModel, FEAModelResults]


def create_figure_source(data: dict) -> FigureSourceSpec:
    """Dispatch on `figure_source` to the right subclass."""
    figure_source_type = data.get("figure_source")
    if figure_source_type == "cad_model_file":
        return CADModelFile(**data)
    if figure_source_type == "fea_model":
        return FEAModel(**data)
    if figure_source_type == "fea_model_results":
        return FEAModelResults(**data)
    raise ValueError(
        f"Unknown figure_source type: {figure_source_type!r}. "
        f"Supported: cad_model_file, fea_model, fea_model_results."
    )
