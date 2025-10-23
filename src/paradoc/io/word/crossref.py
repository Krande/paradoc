"""Cross-reference conversion for Word documents."""

import re

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .fields import create_ref_field_runs, create_text_run
from .utils import iter_block_items


def convert_figure_references_to_ref_fields(document, figures):
    """Convert plain text figure references to Word REF fields.

    This function finds paragraphs that contain figure references (like "Figure 1" or "fig. 1")
    and converts them to proper Word REF fields that point to the bookmarked captions.

    Args:
        document: The Word document
        figures: List of DocXFigureRef objects containing figure information
    """
    bookmarks_in_order = _extract_bookmarks_from_figures(figures)
    if not bookmarks_in_order:
        return  # No figures to process

    # Pattern to match figure references from pandoc-crossref
    fig_ref_pattern = re.compile(r'\b(?:Figure|fig\.)\s+([\d\-]+)\b', re.IGNORECASE)

    _convert_references(document, bookmarks_in_order, fig_ref_pattern, "Figure")


def convert_table_references_to_ref_fields(document, tables):
    """Convert plain text table references to Word REF fields.

    This function finds paragraphs that contain table references (like "Table 1" or "tbl. 1")
    and converts them to proper Word REF fields that point to the bookmarked captions.

    Args:
        document: The Word document
        tables: List of DocXTableRef objects containing table information
    """
    bookmarks_in_order = _extract_bookmarks_from_tables(tables)
    if not bookmarks_in_order:
        return  # No tables to process

    # Note: pandoc-crossref outputs "Table1" (no space) for tables
    tbl_ref_pattern = re.compile(r'\b((?:Table|tbl\.)\s*[\d\-]+)\b', re.IGNORECASE)

    _convert_references(document, bookmarks_in_order, tbl_ref_pattern, "Table")


def convert_equation_references_to_ref_fields(document, equations):
    """Convert plain text equation references to Word REF fields.

    This function finds paragraphs that contain equation references (like "Eq 1" or "eq. 1")
    and converts them to proper Word REF fields that point to the bookmarked captions.

    Args:
        document: The Word document
        equations: List of equation objects containing equation information
    """
    bookmarks_in_order = _extract_bookmarks_from_equations(equations)
    if not bookmarks_in_order:
        return  # No equations to process

    eq_ref_pattern = re.compile(r'\b((?:Eq(?:uation)?|eq\.)\s+([\d\-]+))\b', re.IGNORECASE)

    _convert_references(document, bookmarks_in_order, eq_ref_pattern, "Eq", num_group=2)


def _extract_bookmarks_from_figures(figures) -> list[str]:
    """Extract bookmark names from figure objects in order.

    Args:
        figures: List of DocXFigureRef objects

    Returns:
        List of bookmark names in order
    """
    bookmarks = []
    for fig in figures:
        if hasattr(fig, 'figure_ref') and fig.figure_ref.reference:
            if hasattr(fig, 'actual_bookmark_name') and fig.actual_bookmark_name:
                bookmarks.append(fig.actual_bookmark_name)
    return bookmarks


def _extract_bookmarks_from_tables(tables) -> list[str]:
    """Extract bookmark names from table objects in order.

    Args:
        tables: List of DocXTableRef objects

    Returns:
        List of bookmark names in order
    """
    bookmarks = []
    for tbl in tables:
        if hasattr(tbl, 'table_ref') and hasattr(tbl.table_ref, 'link_name_override'):
            if hasattr(tbl, 'actual_bookmark_name') and tbl.actual_bookmark_name:
                bookmarks.append(tbl.actual_bookmark_name)
    return bookmarks


def _extract_bookmarks_from_equations(equations) -> list[str]:
    """Extract bookmark names from equation objects in order.

    Args:
        equations: List of equation objects

    Returns:
        List of bookmark names in order
    """
    bookmarks = []
    for eq in equations:
        if hasattr(eq, 'reference') and eq.reference:
            if hasattr(eq, 'actual_bookmark_name') and eq.actual_bookmark_name:
                bookmarks.append(eq.actual_bookmark_name)
    return bookmarks


def _convert_references(document, bookmarks_in_order: list[str], pattern: re.Pattern, label: str, num_group: int = 1):
    """Generic function to convert text references to REF fields.

    Args:
        document: The Word document
        bookmarks_in_order: List of bookmark names in document order
        pattern: Regex pattern to match references
        label: The label to use in REF fields (e.g., "Figure", "Table", "Eq")
        num_group: The regex group number containing the number (default 1)
    """
    for block in iter_block_items(document):
        if not isinstance(block, Paragraph):
            continue

        # Skip caption paragraphs
        if block.style.name in ("Image Caption", "Table Caption", "Captioned Figure"):
            continue

        # Check if paragraph contains references
        if not re.search(pattern, block.text):
            continue

        # Process the paragraph
        _process_paragraph_references(block, pattern, bookmarks_in_order, label, num_group)


def _process_paragraph_references(paragraph: Paragraph, pattern: re.Pattern, bookmarks: list[str], label: str, num_group: int):
    """Process a single paragraph to replace text references with REF fields.

    Args:
        paragraph: The paragraph to process
        pattern: Regex pattern to match references
        bookmarks: List of bookmark names in order
        label: The label for REF fields
        num_group: The regex group containing the number
    """
    original_text = paragraph.text
    matches = list(pattern.finditer(original_text))
    if not matches:
        return

    # Store paragraph element before clearing
    p_element = paragraph._p

    # Clear all runs and hyperlinks
    for run in list(paragraph.runs):
        p_element.remove(run._element)
    for child in list(p_element):
        if child.tag == qn('w:hyperlink'):
            p_element.remove(child)

    # Rebuild the paragraph with text and REF fields
    last_pos = 0
    for match in matches:
        # Extract the number from the matched text
        if num_group == 2:
            # For equations: group 1 is full match, group 2 is number
            num_str = match.group(2)
        else:
            # For figures/tables: group 1 is number
            num_str = match.group(1).split()[-1] if ' ' in match.group(1) else match.group(1)

        # Parse the number
        try:
            if num_str == "-":
                item_num = 1
            else:
                # Extract just digits from strings like "1-1" or "1"
                item_num = int(re.search(r'\d+', num_str).group())
        except (ValueError, AttributeError):
            item_num = 1

        # Map number to bookmark (1-based indexing)
        bookmark_idx = item_num - 1
        if 0 <= bookmark_idx < len(bookmarks):
            bookmark_name = bookmarks[bookmark_idx]
        else:
            bookmark_name = bookmarks[-1] if bookmarks else None

        if bookmark_name is None:
            # No bookmark available, just add remaining text
            if last_pos < len(original_text):
                create_text_run(p_element, original_text[last_pos:])
            break

        # Add text before the reference
        if match.start() > last_pos:
            before_text = original_text[last_pos:match.start()]
            create_text_run(p_element, before_text)

        # Add REF field
        create_ref_field_runs(p_element, bookmark_name, label=label)

        last_pos = match.end()

    # Add remaining text after the last reference
    if last_pos < len(original_text):
        after_text = original_text[last_pos:]
        create_text_run(p_element, after_text)


def resolve_references(document):
    """Legacy function - kept for backward compatibility.

    Original function that parsed references but didn't convert them.
    """
    refs = dict()
    fig_re = re.compile(
        r"(?:Figure\s(?P<number>[0-9]{0,5})\s*)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    tbl_re = re.compile(r"(?:Table\s(?P<number>[0-9]{0,5})\s*)", re.MULTILINE | re.DOTALL | re.IGNORECASE)

    # Fix references
    for block in iter_block_items(document):
        if type(block) is Paragraph:
            if block.style.name in ("Image Caption", "Table Caption"):
                continue
            if "Figure" in block.text or "Table" in block.text:
                for m in fig_re.finditer(block.text):
                    d = m.groupdict()
                    n = d["number"]
                    figref = f"Figure {n}"
                    if figref in refs.keys():
                        fref = refs[figref]
                        pg_ref = fref[1]

                for m in tbl_re.finditer(block.text):
                    d = m.groupdict()
                    n = d["number"]
                    tblref = f"Table {n}"
                    if tblref in refs.keys():
                        tref = refs[tblref]
                        pg_ref = tref[1]
                        parent = pg_ref._p
                        print(parent)

