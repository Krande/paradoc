"""Data classes for Word document references."""

import random
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


@dataclass
class DocXEquationRef:
    """Reference to an equation in a Word document with associated metadata."""

    semantic_id: str = None  # e.g., "maxwell_equation" from "eq:maxwell_equation"
    docx_equation: Paragraph = None  # The paragraph containing the equation
    docx_caption: Paragraph = None  # The caption paragraph (not used for inline captions)
    is_appendix: bool = False
    document_index: int = None
    actual_bookmark_name: str = None  # Store the actual Word-style bookmark name

    def format_equation(self, is_appendix: bool, restart_caption_numbering: bool = False, reference_helper=None):
        """Format the equation with an inline caption (right-aligned on the same line).

        This method:
        1. Removes the old eq: bookmark from the math paragraph
        2. Adds a right-aligned caption with SEQ fields on the same line as the equation
        3. Wraps a new bookmark around just the caption portion (excluding whitespace)

        The result is an equation like:
        E = mc^2                                                (Eq. 1-1)
        where the caption is right-aligned and has a bookmark for cross-referencing.

        Args:
            is_appendix: Whether this equation is in the appendix
            restart_caption_numbering: Whether to restart caption numbering
            reference_helper: Optional ReferenceHelper instance for managing cross-references
        """
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        from .fields import add_seq_reference
        from .bookmarks import generate_word_bookmark_name

        if not self.docx_equation or not self.semantic_id:
            return

        # Get the equation paragraph
        eq_para = self.docx_equation
        p_element = eq_para._p

        # Remove the old eq: bookmark if it exists
        old_bookmark_name = f"eq:{self.semantic_id}"
        bookmark_starts = p_element.findall('.//w:bookmarkStart', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
        bookmark_ends = p_element.findall('.//w:bookmarkEnd', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})

        for bm_start in bookmark_starts:
            if bm_start.get(qn('w:name')) == old_bookmark_name:
                bm_id = bm_start.get(qn('w:id'))
                # Remove this bookmark start
                bm_start.getparent().remove(bm_start)
                # Remove matching bookmark end
                for bm_end in bookmark_ends:
                    if bm_end.get(qn('w:id')) == bm_id:
                        bm_end.getparent().remove(bm_end)
                        break
                break

        # Set up a right-aligned tab stop at the right margin (6 inches from left)
        # This positions the caption at the right edge of the page
        pPr = p_element.find('.//w:pPr', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
        if pPr is None:
            pPr = OxmlElement('w:pPr')
            p_element.insert(0, pPr)

        tabs = pPr.find('w:tabs', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})
        if tabs is None:
            tabs = OxmlElement('w:tabs')
            pPr.append(tabs)

        # Add right-aligned tab stop at 6 inches
        tab = OxmlElement('w:tab')
        tab.set(qn('w:val'), 'right')
        tab.set(qn('w:pos'), str(int(6 * 1440)))  # 1440 twips per inch
        tabs.append(tab)

        # Add a tab character to move to the right margin
        tab_run = eq_para.add_run('\t')

        # Build the caption with SEQ fields
        # Format: "(Eq. STYLEREF-SEQ)"
        # Start with opening parenthesis
        paren_run = eq_para.add_run('(Eq. ')

        heading_ref = '"Appendix"' if is_appendix else '"Heading 1"'

        # Add STYLEREF field for chapter number
        styleref_run_elem = p_element._new_r()
        add_seq_reference(styleref_run_elem, f"STYLEREF \\s {heading_ref} \\n", eq_para)
        # Insert before the last run (we'll keep adding runs)
        p_element.append(styleref_run_elem)

        # Add hyphen separator
        hyphen_run = eq_para.add_run('-')

        # Add SEQ field for equation number
        if restart_caption_numbering:
            seq_instruction = f"SEQ Equation \\* ARABIC \\r 1 \\s 1"
        else:
            seq_instruction = f"SEQ Equation \\* ARABIC \\s 1"

        seq_run_elem = p_element._new_r()
        add_seq_reference(seq_run_elem, seq_instruction, eq_para)
        p_element.append(seq_run_elem)

        # Add closing parenthesis
        close_paren_run = eq_para.add_run(')')

        # Now wrap a bookmark around the caption portion (from opening paren to closing paren)
        # Use ReferenceHelper if provided to get Word-style bookmark
        if reference_helper:
            bookmark_name = reference_helper.register_equation(self.semantic_id, eq_para)
            self.actual_bookmark_name = bookmark_name
        else:
            bookmark_name, bookmark_id = generate_word_bookmark_name()
            self.actual_bookmark_name = bookmark_name

        # Create bookmark start - insert right before the opening parenthesis run
        bookmark_start = OxmlElement('w:bookmarkStart')
        bookmark_id_str = str(random.randint(1, 999999))
        bookmark_start.set(qn('w:id'), bookmark_id_str)
        bookmark_start.set(qn('w:name'), bookmark_name)

        # Find the opening paren run in the XML
        paren_run_elem = paren_run._element
        paren_run_elem.addprevious(bookmark_start)

        # Create bookmark end - insert right after the closing parenthesis run
        bookmark_end = OxmlElement('w:bookmarkEnd')
        bookmark_end.set(qn('w:id'), bookmark_id_str)
        close_paren_run._element.addnext(bookmark_end)

