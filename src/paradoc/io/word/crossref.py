"""Cross-reference conversion for Word documents."""

import re

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from paradoc.config import logger

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
    logger.debug(f"[DEBUG convert_figure_references] Found {len(bookmarks_in_order)} figure bookmarks: {bookmarks_in_order}")
    if not bookmarks_in_order:
        logger.debug("[DEBUG convert_figure_references] No bookmarks found, returning early")
        return  # No figures to process

    # Pattern to match figure references from pandoc-crossref
    # Matches: "Figure1.1", "Figure1-1", "Figure 1", "Figure 1-1", "fig. 1", "fig.\xa01"
    # Pandoc-crossref may output with or without space, and uses period or hyphen as separator
    # Use [\s\xa0]* to match optional space (zero or more)
    # Use [\d\.\-]+ to match numbers with period or hyphen separators
    fig_ref_pattern = re.compile(r"\b(?:Figure|fig\.)[\s\xa0]*([\d\.\-]+)", re.IGNORECASE)

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
    logger.debug(f"[DEBUG convert_table_references] Found {len(bookmarks_in_order)} table bookmarks: {bookmarks_in_order}")
    if not bookmarks_in_order:
        logger.debug("[DEBUG convert_table_references] No bookmarks found, returning early")
        return  # No tables to process

    # Pattern to match table references from pandoc-crossref
    # Matches: "Table1.1", "Table1-1", "Table 1", "Table 1-1", "tbl. 1", etc.
    # Pandoc-crossref may output with or without space, and uses period or hyphen as separator
    # Use [\s\xa0]* to match optional space (zero or more)
    # Use [\d\.\-]+ to match numbers with period or hyphen separators
    tbl_ref_pattern = re.compile(r"\b(?:Table|tbl\.)[\s\xa0]*([\d\.\-]+)", re.IGNORECASE)

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

    eq_ref_pattern = re.compile(r"\b((?:Eq(?:uation)?|eq\.)\s+([\d\-]+))\b", re.IGNORECASE)

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
        if hasattr(fig, "figure_ref") and fig.figure_ref.reference:
            if hasattr(fig, "actual_bookmark_name") and fig.actual_bookmark_name:
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
        if hasattr(tbl, "table_ref") and hasattr(tbl.table_ref, "link_name_override"):
            if hasattr(tbl, "actual_bookmark_name") and tbl.actual_bookmark_name:
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
        if hasattr(eq, "reference") and eq.reference:
            if hasattr(eq, "actual_bookmark_name") and eq.actual_bookmark_name:
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
    # First pass: Build a mapping of all reference numbers to their sequential order
    # IMPORTANT: At this point in the document composition, SEQ fields haven't been
    # evaluated by Word yet, so captions may all show placeholder values like "1-1".
    # Instead of parsing numbers, we'll just count captions in document order.
    reference_to_index = {}
    caption_count = 0

    # Pattern to identify caption paragraphs (matches both "Figure 1-1:" and "Figure 1.1:")
    caption_pattern = re.compile(rf"{label}\s+[\d\.\-]+:", re.IGNORECASE)

    # Also track the actual numbers we see for later mapping
    seen_numbers = []

    for block in iter_block_items(document):
        if not isinstance(block, Paragraph):
            continue

        text = block.text.strip()
        match = caption_pattern.search(text)
        if match:
            # Extract the full matched pattern to get the number
            full_match = match.group(0)
            # Extract just the number part (e.g., "1-1" or "1.1" from "Figure 1-1:" or "Figure 1.1:")
            num_match = re.search(r"([\d\.\-]+):", full_match)
            if num_match:
                ref_num = num_match.group(1)
                seen_numbers.append(ref_num)
                # Map this reference number to its sequential position
                reference_to_index[ref_num] = caption_count
                logger.debug(f"[DEBUG _convert_references]   Caption #{caption_count}: {label} {ref_num} (text: {text[:50]})")
                caption_count += 1

    # If all captions have the same number (e.g., all show "1-1" as placeholder),
    # we need to handle references by sequential order instead
    unique_numbers = set(seen_numbers)
    if len(unique_numbers) == 1 and len(seen_numbers) > 1:
        logger.debug(
            f"[DEBUG _convert_references]   WARNING: All captions show same number '{list(unique_numbers)[0]}' - likely unevaluated SEQ fields"
        )
        logger.debug("[DEBUG _convert_references]   Will use sequential matching for references")
        # In this case, we can't reliably map by number, so we'll need to match references
        # to captions in the order they appear in the document

    logger.debug(f"[DEBUG _convert_references] Built reference mapping for {label}: {reference_to_index}")
    logger.debug(f"[DEBUG _convert_references] Total {label} captions found: {caption_count}")

    # Second pass: Convert references to REF fields using the mapping
    processed_count = 0
    skipped_caption = 0
    no_match = 0

    # Track reference occurrences for sequential matching when all captions have same number
    reference_occurrence_count = {}

    for block in iter_block_items(document):
        if not isinstance(block, Paragraph):
            continue

        # Skip caption paragraphs
        if block.style.name in ("Image Caption", "Table Caption", "Captioned Figure"):
            skipped_caption += 1
            continue

        # Check if paragraph contains references
        if not re.search(pattern, block.text):
            no_match += 1
            continue

        # Process the paragraph
        logger.debug(f"[DEBUG _convert_references] Processing paragraph with {label}: {block.text[:80]}")
        _process_paragraph_references(
            block, pattern, bookmarks_in_order, label, num_group, reference_to_index, reference_occurrence_count
        )
        processed_count += 1

    logger.debug(
        f"[DEBUG _convert_references] {label} summary: processed={processed_count}, skipped_caption={skipped_caption}, no_match={no_match}"
    )


def _process_paragraph_references(
    paragraph: Paragraph,
    pattern: re.Pattern,
    bookmarks: list[str],
    label: str,
    num_group: int,
    reference_to_index: dict = None,
    reference_occurrence_count: dict = None,
):
    """Process a single paragraph to replace text references with REF fields.

    Args:
        paragraph: The paragraph to process
        pattern: Regex pattern to match references
        bookmarks: List of bookmark names in order
        label: The label for REF fields
        num_group: The regex group containing the number
        reference_to_index: Mapping of reference numbers (e.g., "2-1") to sequential indices
        reference_occurrence_count: Track how many times we've seen each reference number for sequential matching
    """
    original_text = paragraph.text
    matches = list(pattern.finditer(original_text))
    if not matches:
        return

    logger.debug(f"[DEBUG _process_paragraph_references] Found {len(matches)} matches in: {original_text[:80]}")

    # Store paragraph element before clearing
    p_element = paragraph._p

    # Clear all runs and hyperlinks
    for run in list(paragraph.runs):
        p_element.remove(run._element)
    for child in list(p_element):
        if child.tag == qn("w:hyperlink"):
            p_element.remove(child)

    # Rebuild the paragraph with text and REF fields
    last_pos = 0
    ref_fields_added = 0

    # Check if we have multiple captions with the same number (unevaluated SEQ fields)
    unique_refs = set(reference_to_index.keys()) if reference_to_index else set()
    all_same_number = len(unique_refs) == 1 and len(reference_to_index) > 1 if reference_to_index else False

    for match in matches:
        # Extract the number from the matched text
        if num_group == 2:
            # For equations: group 1 is full match, group 2 is number
            num_str = match.group(2)
        else:
            # For figures/tables: group 1 is number
            num_str = match.group(1).split()[-1] if " " in match.group(1) else match.group(1)

        # Map the reference number to the bookmark
        if all_same_number and reference_occurrence_count is not None:
            # All captions show the same number (e.g., "1-1") - use sequential matching
            # Track how many times we've seen this reference number
            if num_str not in reference_occurrence_count:
                reference_occurrence_count[num_str] = 0
            bookmark_idx = reference_occurrence_count[num_str]
            reference_occurrence_count[num_str] += 1
            logger.debug(
                f"[DEBUG _process_paragraph_references]   Sequential match: reference #{bookmark_idx} (number: {num_str})"
            )
        elif reference_to_index and num_str in reference_to_index:
            # Use the pre-built mapping
            bookmark_idx = reference_to_index[num_str]
        else:
            # Fallback to simple sequential mapping if no mapping available
            try:
                if num_str in ("-", "."):
                    bookmark_idx = 0
                elif "-" in num_str or "." in num_str:
                    # For chapter-based numbers (e.g., "1-1" or "1.1"), can't determine sequential position without mapping
                    # Fall back to using the section number - 1
                    separator = "-" if "-" in num_str else "."
                    bookmark_idx = int(num_str.split(separator)[0]) - 1
                else:
                    bookmark_idx = int(num_str) - 1
            except (ValueError, AttributeError):
                bookmark_idx = 0

        # Get the bookmark name
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
            before_text = original_text[last_pos : match.start()]
            create_text_run(p_element, before_text)

        # Add REF field
        create_ref_field_runs(p_element, bookmark_name, label=label)
        ref_fields_added += 1
        logger.debug(
            f"[DEBUG _process_paragraph_references]   Added REF field #{ref_fields_added}: {num_str} -> index {bookmark_idx} -> {bookmark_name}"
        )

        last_pos = match.end()

    # Add remaining text after the last reference
    if last_pos < len(original_text):
        after_text = original_text[last_pos:]
        create_text_run(p_element, after_text)

    logger.debug(f"[DEBUG _process_paragraph_references] Completed: added {ref_fields_added} REF fields")
