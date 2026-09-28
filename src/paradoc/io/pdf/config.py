"""PDF layout settings: ``[build.<profile>.pdf]`` in paradoc.toml.

Every field has a default, so a profile only lists what it changes::

    [build.pdf]
    outputs = ["pdf"]

    [build.pdf.pdf]
    fontsize = "11pt"
    figure_max_height = 0.5
    table_font_size = "small"

The defaults are tuned for a figure- and table-heavy engineering report (many captioned
result images, wide numeric comparison tables). A key the document's own metadata file sets
(``mainfont``, ``fontsize``, ``geometry``, ...) wins over the value here, so a document can
still pin its look without a paradoc.toml.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TableSize = Literal["tiny", "scriptsize", "footnotesize", "small", "normalsize"]


class PdfExportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # --- page --------------------------------------------------------------------------------
    papersize: str = "a4"
    fontsize: str = "10pt"
    #: Passed to the LaTeX geometry package. pandoc's own default leaves a ~12 cm text block on
    #: A4, too narrow for a ten-column comparison table.
    geometry: str = "margin=2cm"
    #: None = a font the operating system ships with Greek and super/subscript glyphs
    #: (pandoc's Latin Modern has neither).
    mainfont: Optional[str] = None
    monofont: Optional[str] = None

    # --- figures -----------------------------------------------------------------------------
    #: Largest figure height, as a fraction of the text height; 0.42 fits two captioned
    #: figures on a page.
    figure_max_height: float = Field(0.42, gt=0, le=1)
    #: Largest figure width, as a fraction of the line width.
    figure_max_width: float = Field(0.85, gt=0, le=1)
    #: LaTeX float placement for figures. "H" keeps each figure where the markdown puts it --
    #: under its heading -- instead of letting LaTeX move it pages away.
    figure_placement: str = "H"
    #: Crop uniform background margins off raster images (with a small padding) before
    #: typesetting. Rendered 3D posters are mostly empty background; cropped, the model fills
    #: the space the figure is given.
    figure_trim_whitespace: bool = True
    #: Padding kept around the cropped content, as a fraction of the content's larger side.
    figure_trim_padding: float = Field(0.04, ge=0, le=0.5)

    # --- headings ----------------------------------------------------------------------------
    #: Make ``####``/``#####`` headings (LaTeX \\paragraph/\\subparagraph) stand alone rather than
    #: run in with the next line of text -- under a heading followed only by figures there is
    #: none, and the heading would print after its figures.
    block_headings: bool = True

    # --- tables ------------------------------------------------------------------------------
    table_font_size: TableSize = "footnotesize"
    #: Horizontal padding each side of a table cell (LaTeX \\tabcolsep; its default is 6pt).
    table_col_sep: str = "3pt"
    #: How column widths are decided:
    #: - "relative": pandoc's widths, proportional to the source table's column widths. A
    #:   number wider than its share overruns into the next column.
    #: - "auto": every column as wide as its content (no wrapping).
    #: - "content": "auto" for tables whose cells are all short (numbers, labels), "relative"
    #:   for tables with longer text, which then still wraps.
    table_col_widths: Literal["relative", "auto", "content"] = "content"
    #: "content" mode: the longest cell text, in characters, that still counts as short.
    table_short_cell_chars: int = Field(24, ge=1)
