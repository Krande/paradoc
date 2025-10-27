"""Data classes for Word document references."""

from dataclasses import dataclass

from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from paradoc.common import Figure, Table
from paradoc.config import create_logger

logger = create_logger()


@dataclass
class DocXTableRef:
    """Reference to a table in a Word document with associated metadata."""

    table_ref: Table = None
    docx_table: DocxTable = None
    docx_caption: Paragraph = None
    docx_following_pg: Paragraph = None
    is_appendix: bool = False
    document_index: int = None
    actual_bookmark_name: str = None  # Store the actual Word-style bookmark name

    def is_complete(self) -> bool:
        """Check if all required document elements are present."""
        docx_attr = [self.docx_caption, self.docx_table, self.docx_following_pg]
        return all([x is not None for x in docx_attr])

    def get_content_cell0_pg(self) -> Paragraph:
        """Get the first paragraph of the first content cell (row 1, col 0)."""
        tbl = self.docx_table
        return tbl.rows[1].cells[0].paragraphs[0]

    def format_table(self, is_appendix: bool, restart_caption_numbering: bool = False, reference_helper=None):
        """Format the table and its caption with proper styling and numbering.

        Args:
            is_appendix: Whether this table is in the appendix
            restart_caption_numbering: Whether to restart caption numbering
            reference_helper: Optional ReferenceHelper instance for managing cross-references
        """
        from .bookmarks import add_bookmark_around_seq_field
        from .captions import rebuild_caption

        tbl = self.docx_table
        tbl_format = self.table_ref.format

        # Format content of table
        tbl.style = tbl_format.style
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

        logger.info(f'Changed Table style from "{tbl.style}" to "{tbl_format.style}"')
        for i, row in enumerate(tbl.rows):
            for cell in row.cells:
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                paragraphs = cell.paragraphs
                for paragraph in paragraphs:
                    paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                    for run in paragraph.runs:
                        font = run.font
                        font.name = tbl_format.font_style
                        font.size = Pt(tbl_format.font_size)
                        if i == 0:
                            font.bold = True
                        else:
                            font.bold = False
        tbl.autofit = True

        # Format table Caption
        self.docx_caption.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        rebuild_caption(self.docx_caption, "Table", self.table_ref.caption, is_appendix, restart_caption_numbering)

        # Add bookmark around the caption number for Word cross-references
        if self.table_ref.link_name_override or self.table_ref.name:
            table_id = self.table_ref.link_name_override or self.table_ref.name

            # Use ReferenceHelper if provided
            if reference_helper:
                # Register the table and get Word-style bookmark
                bookmark_name = reference_helper.register_table(table_id, self.docx_caption)
                self.actual_bookmark_name = bookmark_name
                # Apply the bookmark to the caption paragraph
                add_bookmark_around_seq_field(self.docx_caption, bookmark_name)
            else:
                # Fallback to old method
                bookmark_name = f"tbl:{table_id}"
                # Capture the actual bookmark name that was created
                self.actual_bookmark_name = add_bookmark_around_seq_field(self.docx_caption, bookmark_name)

        for run in self.docx_caption.runs:
            run.font.name = tbl_format.font_style

        # Fix formatting before Table
        self.docx_caption.paragraph_format.space_before = Pt(18)

        # Fix formatting after Table
        self.docx_following_pg.paragraph_format.space_before = Pt(22)

    def substitute_back_temp_var(self):
        """Substitute temporary variable back with actual data value."""
        pg_0 = self.get_content_cell0_pg()

        df = self.table_ref.df
        col_name = df.columns[0]
        res = df.iloc[0, df.columns.get_loc(col_name)]
        fmt = self.table_ref.format.float_fmt

        use_decimals = True
        if len(self.docx_table.rows) > 1:
            try:
                row2 = self.docx_table.rows[2].cells[0].paragraphs[0]
            except IndexError as e:
                logger.error(f"Second row not used by table. Using first error: '{e}'")
                row2 = self.docx_table.rows[1].cells[0].paragraphs[0]

            if "." not in row2.text:
                use_decimals = False
        if fmt is None or use_decimals is False:
            pg_0.text = f"{res}"
        else:
            pg_0.text = f"{res:{fmt}}"


@dataclass
class DocXFigureRef:
    """Reference to a figure in a Word document with associated metadata."""

    figure_ref: Figure = None
    docx_figure: Paragraph = None
    docx_caption: Paragraph = None
    docx_following_pg: Paragraph = None
    is_appendix: bool = False
    document_index: int = None
    actual_bookmark_name: str = None  # Store the actual Word-style bookmark name

    def format_figure(self, is_appendix: bool, restart_caption_numbering: bool, reference_helper=None):
        """Format the figure caption with proper styling and numbering.

        Args:
            is_appendix: Whether this figure is in the appendix
            restart_caption_numbering: Whether to restart caption numbering
            reference_helper: Optional ReferenceHelper instance for managing cross-references
        """
        from .bookmarks import add_bookmark_around_seq_field
        from .captions import rebuild_caption

        figure_format = self.figure_ref.format
        self.docx_caption.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        # Rebuild caption without bookmark
        rebuild_caption(self.docx_caption, "Figure", self.figure_ref.caption, is_appendix, restart_caption_numbering)

        # Add bookmark around the caption number (SEQ field) for Word cross-references
        if self.figure_ref.reference:
            # Use ReferenceHelper if provided
            if reference_helper:
                # Register the figure and get Word-style bookmark
                bookmark_name = reference_helper.register_figure(self.figure_ref.reference, self.docx_caption)
                self.actual_bookmark_name = bookmark_name
                # Apply the bookmark to the caption paragraph
                add_bookmark_around_seq_field(self.docx_caption, bookmark_name)
            else:
                # Fallback to old method
                bookmark_name = f"fig:{self.figure_ref.reference}"
                # Capture the actual bookmark name that was created
                self.actual_bookmark_name = add_bookmark_around_seq_field(self.docx_caption, bookmark_name)

        for run in self.docx_caption.runs:
            run.font.name = figure_format.font_style

