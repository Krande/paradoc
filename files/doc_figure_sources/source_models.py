"""Pydantic models for figure source specifications.

This module defines the data models for different types of figure sources
that can be specified in markdown documents using <-- --> markers.
"""

from enum import Enum
from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, Field

# This should ideally be gathered from sqlite
class CameraPosition(str, Enum):
    """Standard camera position presets."""

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
    """Supported FEA software formats."""

    ABAQUS = "abaqus"
    SESAM = "sesam"
    ANSYS = "ansys"
    NASTRAN = "nastran"


class BaseFigureSource(BaseModel):
    """Base model for all figure source specifications."""

    figure_source: str
    figure_title: str
    camera_pos: CameraPosition = CameraPosition.ISO_3


class CADModelFile(BaseFigureSource):
    """Specification for CAD model figures (STEP, IFC, etc.)."""

    figure_source: Literal["cad_model_file"] = "cad_model_file"
    source_inp: Path = Field(..., description="Path to the CAD model file (STEP, IFC, etc.)")


class FEAModel(BaseFigureSource):
    """Specification for FEA model geometry visualization."""

    figure_source: Literal["fea_model"] = "fea_model"
    fea_format: FEAFormat = Field(..., description="FEA software format")
    source_inp: Path = Field(..., description="Path to the FEA model input file")


class FEAModelResults(BaseFigureSource):
    """Specification for FEA model results visualization."""

    figure_source: Literal["fea_model_results"] = "fea_model_results"
    fea_format: FEAFormat = Field(..., description="FEA software format")
    source_inp: Path = Field(..., description="Path to the FEA model input file")
    output_file: Path = Field(..., description="Path to the results file (ODB, SIN, etc.)")
    field: str = Field(..., description="Field variable to visualize (e.g., 'S' for stress)")


# Union type for all figure source types
FigureSourceSpec = Union[CADModelFile, FEAModel, FEAModelResults]


def create_figure_source(data: dict) -> FigureSourceSpec:
    """Factory function to create the appropriate figure source model.

    Args:
        data: Dictionary containing the parsed figure source specification

    Returns:
        An instance of the appropriate FigureSourceSpec subclass

    Raises:
        ValueError: If the figure_source type is not recognized
    """
    figure_source_type = data.get("figure_source")

    if figure_source_type == "cad_model_file":
        return CADModelFile(**data)
    elif figure_source_type == "fea_model":
        return FEAModel(**data)
    elif figure_source_type == "fea_model_results":
        return FEAModelResults(**data)
    else:
        raise ValueError(f"Unknown figure_source type: {figure_source_type}")

