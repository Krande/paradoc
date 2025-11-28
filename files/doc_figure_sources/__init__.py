"""Figure sources package for parsing and generating figures from specifications."""

from .source_models import (
    FigureSourceSpec,
    CADModelFile,
    FEAModel,
    FEAModelResults,
    CameraPosition,
    FEAFormat,
    create_figure_source,
)

from .source_handler import (
    extract_figure_sources,
    parse_spec_content,
    parse_figure_sources_from_markdown,
    parse_figure_sources_from_file,
    generate_figure,
    generate_cad_model_figure,
    generate_fea_model_figure,
    generate_fea_results_figure,
    process_markdown_file,
)

__all__ = [
    # Models
    "FigureSourceSpec",
    "CADModelFile",
    "FEAModel",
    "FEAModelResults",
    "CameraPosition",
    "FEAFormat",
    "create_figure_source",
    # Handler functions
    "extract_figure_sources",
    "parse_spec_content",
    "parse_figure_sources_from_markdown",
    "parse_figure_sources_from_file",
    "generate_figure",
    "generate_cad_model_figure",
    "generate_fea_model_figure",
    "generate_fea_results_figure",
    "process_markdown_file",
]

