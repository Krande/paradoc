"""Figure-source spec language: `<!-- paradoc:figure ... -->` blocks.

Pipeline at compile time
------------------------
1. The preprocessor scans markdown for `<!-- paradoc:figure ... -->` blocks.
2. Each block is parsed into a typed spec (CADModelFile, FEAModel, ...).
3. A figure-source filter (one per `figure_source` value) is invoked:
   - Renders a static PNG (for Word/PDF/static HTML).
   - Writes a glb to `<doc_build>/assets/3d/<key>.glb` with sha256 recorded.
   - Inserts a `ThreeDData` row in the doc DB.
4. The block in the markdown is replaced with `![cap](png){#fig:id data-3d-key=...}`.
"""

from ._plugins import Dispatcher, ensure_plugins_loaded
from .models import (
    BaseFigureSource,
    CADModelFile,
    CameraPosition,
    FEAFormat,
    FEAModel,
    FEAModelResults,
    FigureSourceSpec,
    create_figure_source,
    register_spec,
)
from .preprocessor import (
    FIGURE_SOURCE_RE,
    extract_figure_source_blocks,
    parse_spec_dict,
    preprocess_markdown,
)

__all__ = [
    "BaseFigureSource",
    "CADModelFile",
    "FEAModel",
    "FEAModelResults",
    "FigureSourceSpec",
    "CameraPosition",
    "FEAFormat",
    "create_figure_source",
    "register_spec",
    "Dispatcher",
    "ensure_plugins_loaded",
    "FIGURE_SOURCE_RE",
    "extract_figure_source_blocks",
    "parse_spec_dict",
    "preprocess_markdown",
]
