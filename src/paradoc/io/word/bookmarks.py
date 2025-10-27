"""Bookmark creation and management for Word documents."""

import random

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def generate_word_bookmark_name() -> tuple[str, str]:
    """Generate a Word-style bookmark name and ID.

    Returns:
        Tuple of (bookmark_name, bookmark_id) where bookmark_name is like "_Ref306075071"
    """
    random_id = random.randint(100000000, 999999999)
    word_style_name = f"_Ref{random_id}"
    bookmark_id = str(random.randint(1, 999999))
    return word_style_name, bookmark_id


def normalize_bookmark_name(name: str) -> str:
    """Convert a bookmark name to Word-compatible format.

    Word doesn't like colons in bookmark names for REF fields.
    Convert 'fig:test_figure' to '_Reffig_test_figure'.

    Args:
        name: The bookmark name (e.g., "fig:test_figure")

    Returns:
        Word-compatible bookmark name (e.g., "_Reffig_test_figure")
    """
    # Replace colons with underscores
    normalized = name.replace(':', '_')

    # Add _Ref prefix if not already present (Word's convention)
    if not normalized.startswith('_Ref'):
        normalized = '_Ref' + normalized

    return normalized


def add_bookmark_to_paragraph(paragraph: Paragraph, bookmark_name: str = None) -> str:
    """Add a bookmark wrapping the entire paragraph.

    Args:
        paragraph: The paragraph to add the bookmark to
        bookmark_name: Optional bookmark name; if None, generates a Word-style name
                      If the name already starts with '_Ref', it's used as-is (Word-style)
                      Otherwise, it's normalized (semantic name like 'fig:test')

    Returns:
        The actual bookmark name that was created
    """
    if bookmark_name:
        # Check if this is already a Word-style bookmark (starts with _Ref and is all digits after)
        if bookmark_name.startswith('_Ref') and bookmark_name[4:].isdigit():
            # Already Word-style, use as-is
            word_style_name = bookmark_name
        else:
            # Semantic name, normalize it
            word_style_name = normalize_bookmark_name(bookmark_name)
        bookmark_id = str(random.randint(1, 999999))
    else:
        word_style_name, bookmark_id = generate_word_bookmark_name()

    # Add bookmark start at the beginning of the paragraph
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), word_style_name)
    paragraph._p.insert(0, start)

    # Add bookmark end at the end of the paragraph
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)
    paragraph._p.append(end)

    return word_style_name


def add_bookmark_around_seq_field(paragraph: Paragraph, bookmark_name: str) -> str:
    """Add a bookmark around only the label and number portion of a caption.

    For Word cross-references with "Only label and number" behavior, the bookmark
    should only wrap the label and number (e.g., "Figure 1-1"), NOT the caption text.
    This matches Word's native Insert Caption cross-reference behavior.

    Caption structure (as created by rebuild_caption):
    - Run 0: "Figure " or "Table " text
    - Runs 1-5: STYLEREF field (chapter number: "2")
    - Run 6: hyphen text "-"
    - Runs 7-11: SEQ field (figure/table number: "1")
    - Run 12+: ": caption text" <- This should NOT be included in the bookmark

    Args:
        paragraph: The caption paragraph containing the numbering fields
        bookmark_name: The semantic bookmark name (e.g., "fig:test_figure")

    Returns:
        The actual Word-style bookmark name that was created (e.g., "_Ref306075071")
    """
    # Generate Word-style bookmark name
    if bookmark_name.startswith('_Ref') and bookmark_name[4:].isdigit():
        word_style_name = bookmark_name
    else:
        word_style_name = normalize_bookmark_name(bookmark_name)
    bookmark_id = str(random.randint(1, 999999))

    # Get all runs in the paragraph
    runs = list(paragraph._p)

    # Debug: print paragraph structure
    print(f"[DEBUG add_bookmark_around_seq_field] Processing bookmark '{bookmark_name}'")
    print(f"[DEBUG] Paragraph text: {paragraph.text}")
    print(f"[DEBUG] Total runs: {len(runs)}")

    # Find the run that contains the caption text (starts with ": ")
    caption_text_start_idx = None
    for i, run in enumerate(runs):
        # Check if this is a text run (w:r element)
        if run.tag != qn("w:r"):
            continue

        # Check text content
        text_elements = run.findall(qn('w:t'))
        for t_elem in text_elements:
            text_content = t_elem.text if t_elem.text else ""
            print(f"[DEBUG]   Run {i}: '{text_content[:50]}'")
            if t_elem.text and t_elem.text.startswith(": "):
                caption_text_start_idx = i
                print(f"[DEBUG]   Found caption text separator at run {i}")
                break
        if caption_text_start_idx is not None:
            break

    # If we found where caption text starts, bookmark everything before it
    # Otherwise, fall back to bookmarking the entire paragraph
    if caption_text_start_idx is not None and caption_text_start_idx > 0:
        # Bookmark from the first run up to (but not including) the caption text run
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), bookmark_id)
        start.set(qn("w:name"), word_style_name)
        # Insert at the beginning of the paragraph
        paragraph._p.insert(0, start)

        # Insert bookmark end just before the caption text run
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), bookmark_id)
        runs[caption_text_start_idx].addprevious(end)
    else:
        # Fallback: wrap entire paragraph if we can't find the caption text separator
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), bookmark_id)
        start.set(qn("w:name"), word_style_name)
        paragraph._p.insert(0, start)

        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), bookmark_id)
        paragraph._p.append(end)

    return word_style_name


def _find_field_indices(runs) -> tuple[int | None, int | None]:
    """Find the indices of STYLEREF begin and SEQ end in runs list.

    Args:
        runs: List of run elements from paragraph

    Returns:
        Tuple of (styleref_begin_idx, seq_end_idx)
    """
    styleref_begin_idx = None
    seq_end_idx = None
    field_begins = []  # List of (run_idx, field_type)

    # First pass: identify all field begin positions and their types
    for i, run in enumerate(runs):
        instr_texts = run.findall(qn('w:instrText'))
        for instr in instr_texts:
            if instr.text:
                # Look back to find the corresponding field begin
                for j in range(max(0, i - 3), i + 1):
                    fld_chars = runs[j].findall(qn('w:fldChar'))
                    for fld_char in fld_chars:
                        if fld_char.get(qn('w:fldCharType')) == 'begin':
                            if 'STYLEREF' in instr.text:
                                field_begins.append((j, 'STYLEREF'))
                                if styleref_begin_idx is None:
                                    styleref_begin_idx = j
                            elif 'SEQ' in instr.text and 'STYLEREF' not in instr.text:
                                field_begins.append((j, 'SEQ'))
                            break

    # Second pass: find field ends and match them to their begins
    begin_stack = []  # Stack to track which field begins we've seen

    for i, run in enumerate(runs):
        fld_chars = run.findall(qn('w:fldChar'))
        for fld_char in fld_chars:
            fld_type = fld_char.get(qn('w:fldCharType'))

            if fld_type == 'begin':
                # Check if this is one of our tracked field begins
                for begin_idx, begin_field_type in field_begins:
                    if begin_idx == i:
                        begin_stack.append((i, begin_field_type))
                        break

            elif fld_type == 'end':
                # This end corresponds to the most recent unmatched begin
                if begin_stack:
                    begin_idx, begin_field_type = begin_stack.pop()

                    # Record the SEQ field end (but only after we've found STYLEREF)
                    if begin_field_type == 'SEQ' and styleref_begin_idx is not None and seq_end_idx is None:
                        seq_end_idx = i

    return styleref_begin_idx, seq_end_idx


def _find_seq_field_only(runs) -> tuple[int | None, int | None]:
    """Find just the SEQ field begin and end indices.

    Args:
        runs: List of run elements from paragraph

    Returns:
        Tuple of (seq_begin_idx, seq_end_idx)
    """
    seq_begin_idx = None
    seq_end_idx = None

    for i, run in enumerate(runs):
        fld_chars = run.findall(qn('w:fldChar'))
        for fld_char in fld_chars:
            fld_type = fld_char.get(qn('w:fldCharType'))

            if fld_type == 'begin':
                # Check if this is SEQ field
                for j in range(i, min(i + 5, len(runs))):
                    check_instr = runs[j].findall(qn('w:instrText'))
                    for instr in check_instr:
                        if instr.text and 'SEQ' in instr.text and 'STYLEREF' not in instr.text:
                            seq_begin_idx = i
                            break
                    if seq_begin_idx == i:
                        break

            elif fld_type == 'end' and seq_begin_idx is not None and seq_end_idx is None:
                seq_end_idx = i
                break

        if seq_begin_idx is not None and seq_end_idx is not None:
            break

    return seq_begin_idx, seq_end_idx


def _add_bookmark_around_runs(runs, start_idx: int, end_idx: int, bookmark_name: str, bookmark_id: str) -> str:
    """Add bookmark elements around a range of runs.

    Args:
        runs: List of run elements
        start_idx: Index of first run to wrap
        end_idx: Index of last run to wrap
        bookmark_name: The bookmark name
        bookmark_id: The bookmark ID

    Returns:
        The bookmark name that was added
    """
    # Insert bookmark start BEFORE the first run
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), bookmark_name)
    runs[start_idx].addprevious(start)

    # Insert bookmark end AFTER the last run
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)
    runs[end_idx].addnext(end)

    return bookmark_name