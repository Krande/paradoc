"""PDF layout settings: ``[build.<profile>.pdf]`` in paradoc.toml.

Every field has a default, so a profile only lists what it changes::

    [build.pdf]
    outputs = ["pdf"]

    [build.pdf.pdf]
    fontsize = "11pt"
    figure_max_height = 0.5
    table_font_size = "small"

``engine = "chromium"`` prints the document's HTML with headless Chromium instead of LaTeX, with
a title page, table of contents and a page header and footer from ``[build.<profile>.pdf.document]``
(see ``paradoc.io.pdf.chromium``).

The defaults are tuned for a figure- and table-heavy engineering report (many captioned
result images, wide numeric comparison tables). A key the document's own metadata file sets
(``mainfont``, ``fontsize``, ``geometry``, ...) wins over the value here, so a document can
still pin its look without a paradoc.toml.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TableSize = Literal["tiny", "scriptsize", "footnotesize", "small", "normalsize"]


class RevisionEntry(BaseModel):
    """One row of the title page's revision history (``[[build.<profile>.pdf.document.revisions]]``)."""

    model_config = ConfigDict(extra="forbid")

    rev: str
    #: Issue date, as it should print (ISO ``YYYY-MM-DD`` recommended).
    date: str = ""
    description: str = ""
    #: Per-revision status ("Draft", "Issued for review", ...); empty = the document's status.
    status: str = ""
    prepared: str = ""
    checked: str = ""
    approved: str = ""


class DocumentInfo(BaseModel):
    """Document control data for the ``chromium`` engine's title page, page header and footer:
    ``[build.<profile>.pdf.document]``.

    Every field is optional; what is empty is left off the page. ``revision`` picks the current
    row of ``revisions``: the title page lists that row and the ones before it (a rebuild of an
    older revision does not show later ones), and an empty ``issue_date`` is taken from that row.
    """

    model_config = ConfigDict(extra="forbid")

    company: str = ""
    #: Logo image (SVG or PNG), relative to the document root. Shown in the page header (at
    #: header height) and, larger, on the title page.
    logo: Optional[str] = None
    #: Larger logo for the title page (eg a horizontal mark + wordmark lock-up); defaults to
    #: ``logo``. When set, the company name is not repeated beside it on the title page.
    title_page_logo: Optional[str] = None
    project: str = ""
    title: str = ""
    subtitle: str = ""
    client: str = ""
    document_number: str = ""
    revision: str = ""
    issue_date: str = ""
    #: Printed in the header next to the revision and stamped on the title page ("DRAFT").
    status: str = ""
    prepared_by: str = ""
    #: Free text printed on the title page under the document data (eg how a revision was made).
    note: str = ""
    revisions: list[RevisionEntry] = Field(default_factory=list)

    def current_revision(self) -> Optional[RevisionEntry]:
        for row in self.revisions:
            if row.rev == self.revision:
                return row
        return None

    def revision_history(self) -> list[RevisionEntry]:
        """The rows up to and including the current revision (all rows if it is not listed)."""
        out = []
        for row in self.revisions:
            out.append(row)
            if row.rev == self.revision:
                break
        return out

    def resolved_issue_date(self) -> str:
        if self.issue_date:
            return self.issue_date
        row = self.current_revision()
        return row.date if row is not None else ""


class PdfExportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: How the PDF is made:
    #: - "latex": the markdown through pandoc and a LaTeX engine (xelatex, tectonic, ...).
    #: - "chromium": the document's HTML printed by headless Chromium (Playwright), with a title
    #:   page, table of contents, and a page header and footer from ``document``. Figure and
    #:   table numbering match the HTML export. Needs the ``playwright`` Python package and a
    #:   Chromium build (``playwright install chromium``, or ``PARADOC_CHROMIUM`` / ``browser``
    #:   pointing at one).
    engine: Literal["latex", "chromium"] = "latex"

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

    # --- chromium engine -----------------------------------------------------------------------
    document: DocumentInfo = Field(default_factory=DocumentInfo)
    title_page: bool = True
    toc: bool = True
    #: Heading levels listed in the table of contents (1 = chapters only).
    toc_depth: int = Field(2, ge=1, le=4)
    #: Start every chapter (level-1 heading) on a new page.
    chapter_page_break: bool = True
    #: Page margins (CSS lengths); top and bottom hold the header and footer.
    margin_top: str = "27mm"
    margin_bottom: str = "22mm"
    margin_left: str = "18mm"
    margin_right: str = "18mm"
    font_family: str = '"Noto Sans", "Liberation Sans", "DejaVu Sans", Arial, sans-serif'
    #: Where the logo and company name go: "footer" puts them in the page footer (with the status
    #: mark) and project, document title, revision, issue date and "Page N of M" in the header;
    #: "header" puts logo, company, project and status/revision in the header and document
    #: number, issue date and page number in the footer.
    branding: Literal["footer", "header"] = "footer"
    #: Headings, rules and table headers.
    accent_color: str = "#1d3557"
    #: Extra print CSS (relative to the document root), applied after paradoc's own.
    stylesheet: Optional[str] = None
    #: Chromium executable; else ``PARADOC_CHROMIUM``, else Playwright's own, else one found on
    #: the system.
    browser: Optional[str] = None
    #: Keep the print-ready HTML next to the PDF (``<name>.print.html``) for inspection.
    keep_html: bool = True
