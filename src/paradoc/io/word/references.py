import re

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .utils import iter_block_items


def _normalize_bookmark_name(name: str) -> str:
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


def resolve_references(document):
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
                        # ref_id = parent.id
                        print(parent)


def add_bookmarkStart(paragraph: Paragraph, _id):
    name = "_Ref_id_num_" + _id
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:name"), name)
    start.set(qn("w:id"), str(_id))
    paragraph._p.append(start)
    return name


def append_ref_to_paragraph(paragraph: Paragraph, ref_name, text=""):
    # run 1
    run = paragraph.add_run(text)
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    # run 2
    run = paragraph.add_run()
    r = run._r
    instrText = OxmlElement("w:instrText")
    instrText.text = "REF " + ref_name + " \\h"
    r.append(instrText)
    # run 3
    run = paragraph.add_run()
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)


def add_bookmark(paragraph: Paragraph, bookmark_text, bookmark_name):
    run = paragraph.add_run()
    tag = run._r  # for reference the following also works: tag =  document.element.xpath('//w:r')[-1]
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "0")
    start.set(qn("w:name"), bookmark_name)
    tag.append(start)

    text = OxmlElement("w:r")
    text.text = bookmark_text
    tag.append(text)

    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "0")
    end.set(qn("w:name"), bookmark_name)
    tag.append(end)


def add_bookmark_around_seq_field(paragraph: Paragraph, bookmark_name: str):
    """Add a bookmark around the caption number SEQ field.

    This is the proper way to create Word cross-references - the bookmark
    wraps around the SEQ field that generates the caption number, not the
    entire caption paragraph.

    Args:
        paragraph: The caption paragraph containing SEQ fields
        bookmark_name: The name of the bookmark (will be normalized to Word format)
    """
    # Normalize bookmark name to Word-compatible format
    normalized_name = _normalize_bookmark_name(bookmark_name)

    # Generate a unique ID for the bookmark
    import random
    bookmark_id = str(random.randint(1, 999999))

    # Find the SEQ field runs in the caption
    # Caption structure: [prefix run] [STYLEREF field] [separator run] [SEQ field] [caption text run]
    # We want to wrap the bookmark around the SEQ field

    p_element = paragraph._p
    runs = list(p_element.findall(qn('w:r')))

    if len(runs) < 4:
        # Not enough runs to identify SEQ field, fall back to paragraph bookmark
        add_bookmark_to_caption(paragraph, bookmark_name)
        return

    # Find the SEQ field (usually the 4th run, index 3)
    # Look for the run containing fldChar with fldCharType="end" for the SEQ field
    seq_field_end_idx = None
    for idx, run in enumerate(runs):
        # Check if this run contains a field end
        fld_chars = run.findall(qn('w:fldChar'))
        for fld_char in fld_chars:
            fld_type = fld_char.get(qn('w:fldCharType'))
            if fld_type == 'end':
                # This might be the SEQ field end - check previous runs for SEQ instruction
                if idx >= 2:
                    # Check if previous runs contain SEQ instruction
                    for check_idx in range(max(0, idx - 3), idx):
                        instr_texts = runs[check_idx].findall(qn('w:instrText'))
                        for instr in instr_texts:
                            if instr.text and 'SEQ' in instr.text and 'STYLEREF' not in instr.text:
                                seq_field_end_idx = idx
                                break
                if seq_field_end_idx:
                    break

    if seq_field_end_idx is None:
        # Couldn't find SEQ field, fall back to paragraph bookmark
        add_bookmark_to_caption(paragraph, bookmark_name)
        return

    # Place bookmark start before the SEQ field begin (a few runs before the end)
    bookmark_start_idx = max(0, seq_field_end_idx - 3)

    # Add bookmark start before the SEQ field
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), normalized_name)

    # Insert bookmark start before the identified run
    runs[bookmark_start_idx].addprevious(start)

    # Add bookmark end after the SEQ field end
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)

    # Insert bookmark end after the SEQ field end run
    runs[seq_field_end_idx].addnext(end)


def add_bookmark_to_caption(paragraph: Paragraph, bookmark_name):
    """Add a bookmark to a caption paragraph for cross-referencing.

    The bookmark wraps around the entire caption paragraph so that
    Word's cross-reference feature can reference it properly.

    Args:
        paragraph: The caption paragraph to add the bookmark to
        bookmark_name: The name of the bookmark (e.g., "fig:test_figure")
    """
    # Normalize bookmark name to Word-compatible format
    # Convert "fig:test_figure" to "_Reffig_test_figure"
    normalized_name = _normalize_bookmark_name(bookmark_name)

    # Generate a unique ID for the bookmark
    import random
    bookmark_id = str(random.randint(1, 999999))

    # Add bookmark start at the beginning of the paragraph
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), bookmark_id)
    start.set(qn("w:name"), normalized_name)
    paragraph._p.insert(0, start)

    # Add bookmark end at the end of the paragraph
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), bookmark_id)
    paragraph._p.append(end)


def insert_caption(pg: Paragraph, prefix, run, text, is_appendix: bool):
    heading_ref = "Appendix" if is_appendix is True else '"Heading 1"'

    seq1 = pg._element._new_r()
    add_seq_reference(seq1, f"STYLEREF \\s {heading_ref} \\n", run._parent)
    run._element.addprevious(seq1)
    stroke = pg._element._new_r()
    new_run = Run(stroke, run._parent)
    new_run.text = "-"
    run._element.addprevious(stroke)
    seq2 = pg._element._new_r()
    add_seq_reference(seq2, f"SEQ {prefix} \\* ARABIC \\s 1", run._parent)
    run._element.addprevious(seq2)
    fin = pg._element._new_r()
    fin_run = Run(fin, run._parent)
    fin_run.text = ": " + text
    run._element.addprevious(fin)


def insert_caption_into_runs(pg: Paragraph, prefix: str, is_appendix: bool):
    tmp_split = pg.text.split(":")
    prefix_old = tmp_split[0].strip()
    text = tmp_split[-1].strip()
    srun = pg.runs[0]
    if len(pg.runs) > 1:
        run = pg.runs[1]
        tmp_str = pg.runs[0].text
        pg.runs[0].text = f"{prefix} "
        insert_caption(pg, prefix, run, tmp_str.split(":")[-1].strip(), is_appendix)
    else:
        srun.text = f"{prefix} "
        run = pg.add_run()
        insert_caption(pg, prefix, run, text, is_appendix)

    return srun, pg, prefix_old


def add_seq_reference(run_in, seq, parent):
    from docx.text.run import Run

    new_run = Run(run_in, parent)
    r = new_run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    instrText = OxmlElement("w:instrText")
    instrText.text = seq
    r.append(instrText)
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)
    return new_run


def add_table_reference(paragraph, seq=" SEQ Table \\* ARABIC \\s 1"):
    run = paragraph.add_run()
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    instrText = OxmlElement("w:instrText")
    instrText.text = seq
    r.append(instrText)
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)

    return run


def convert_figure_references_to_ref_fields(document, figures):
    """Convert plain text figure references to Word REF fields.

    This function finds paragraphs that contain figure references (like "Figure 1" or "fig. 1")
    and converts them to proper Word REF fields that point to the bookmarked captions.

    Args:
        document: The Word document
        figures: List of DocXFigureRef objects containing figure information
    """
    # Build a list of bookmark names in order
    bookmarks_in_order = []

    for fig in figures:
        if hasattr(fig, 'figure_ref') and fig.figure_ref.reference:
            ref_id = fig.figure_ref.reference
            bookmark_name = f"fig:{ref_id}"
            # Normalize to Word-compatible format
            normalized_name = _normalize_bookmark_name(bookmark_name)
            bookmarks_in_order.append(normalized_name)

    if not bookmarks_in_order:
        return  # No figures to process

    # Pattern to match figure references from pandoc-crossref
    # Match: "Figure X", "fig. X", "Figure X-Y" etc.
    # Note: SEQ fields show as "-" before evaluation, so we match any number pattern
    fig_ref_pattern = re.compile(r'\b((?:Figure|fig\.)\s+([\d\-]+))\b', re.IGNORECASE)

    # Track figure numbers to bookmark mapping
    # Extract figure numbers from bookmarks for mapping
    figure_num_to_bookmark = {}
    for idx, bookmark in enumerate(bookmarks_in_order):
        # Map figure index (1-based) to bookmark
        figure_num_to_bookmark[idx + 1] = bookmark

    # Iterate through all paragraphs
    for block in iter_block_items(document):
        if not isinstance(block, Paragraph):
            continue

        # Skip caption paragraphs
        if block.style.name in ("Image Caption", "Table Caption", "Captioned Figure"):
            continue

        # Check if paragraph contains figure references
        if not re.search(fig_ref_pattern, block.text):
            continue

        # Process the paragraph to replace text with REF fields
        original_text = block.text

        # Find all matches in the paragraph text
        matches = list(fig_ref_pattern.finditer(original_text))
        if not matches:
            continue

        # Store paragraph element before clearing
        p_element = block._p

        # Clear all runs in the paragraph by removing them from the XML
        for run in list(block.runs):  # Use list() to avoid modification during iteration
            p_element.remove(run._element)

        # Also remove hyperlink elements (pandoc-crossref creates these)
        for child in list(p_element):
            if child.tag == qn('w:hyperlink'):
                p_element.remove(child)

        # Rebuild the paragraph with text and REF fields
        # We manually create and append run elements to ensure correct order
        last_pos = 0
        for match in matches:
            # Extract the figure number from the match
            figure_num_str = match.group(2)  # The number part (e.g., "1" from "Figure 1")

            # Try to parse the figure number
            # If it's "-" (unevaluated SEQ field), assume it's the first figure
            try:
                if figure_num_str == "-":
                    figure_num = 1  # Default to first figure
                else:
                    figure_num = int(figure_num_str)
            except ValueError:
                figure_num = 1  # Fallback to first figure

            # Map figure number to bookmark (1-based indexing)
            # Figure 1 -> bookmarks_in_order[0], Figure 2 -> bookmarks_in_order[1], etc.
            bookmark_idx = figure_num - 1

            if 0 <= bookmark_idx < len(bookmarks_in_order):
                bookmark_name = bookmarks_in_order[bookmark_idx]
            else:
                # If figure number is out of range, use the last bookmark
                bookmark_name = bookmarks_in_order[-1] if bookmarks_in_order else None

            if bookmark_name is None:
                # No bookmark available, just add remaining text and break
                if last_pos < len(original_text):
                    _add_text_run(p_element, original_text[last_pos:])
                break


            # Add text before the reference
            if match.start() > last_pos:
                before_text = original_text[last_pos:match.start()]
                _add_text_run(p_element, before_text)

            # Add REF field
            _add_ref_field_runs(p_element, bookmark_name)

            last_pos = match.end()

        # Add remaining text after the last reference
        if last_pos < len(original_text):
            after_text = original_text[last_pos:]
            _add_text_run(p_element, after_text)




def _add_text_run(p_element, text):
    """Add a text run to a paragraph element by appending to XML.

    Args:
        p_element: The paragraph XML element (w:p)
        text: The text content for the run
    """
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)

    # Simply append to the paragraph - runs should come after pPr
    p_element.append(r)


def _add_ref_field_runs(p_element, bookmark_name):
    """Add REF field runs to a paragraph element by appending to XML.

    This creates the complete REF field structure with begin, instruction, separator, result, and end.

    Args:
        p_element: The paragraph XML element (w:p)
        bookmark_name: The name of the bookmark to reference
    """
    # Run 1: Field begin
    r1 = OxmlElement("w:r")
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    r1.append(fldChar1)
    p_element.append(r1)

    # Run 2: Field instruction
    r2 = OxmlElement("w:r")
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    # Use Word's cross-reference format: REF bookmark \h \* MERGEFORMAT
    # \h creates a hyperlink, \* MERGEFORMAT preserves formatting
    instrText.text = f" REF {bookmark_name} \\h "
    r2.append(instrText)
    p_element.append(r2)

    # Run 3: Field separator
    r3 = OxmlElement("w:r")
    fldChar3 = OxmlElement("w:fldChar")
    fldChar3.set(qn("w:fldCharType"), "separate")
    r3.append(fldChar3)
    p_element.append(r3)

    # Run 4: Field result (placeholder text that will be replaced when field is updated)
    r4 = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "Figure 1"  # Placeholder - will be updated by Word
    r4.append(t)
    p_element.append(r4)

    # Run 5: Field end
    r5 = OxmlElement("w:r")
    fldChar5 = OxmlElement("w:fldChar")
    fldChar5.set(qn("w:fldCharType"), "end")
    r5.append(fldChar5)
    p_element.append(r5)


def add_ref_field_to_paragraph(paragraph: Paragraph, bookmark_name: str):
    """Add a REF field to a paragraph.

    Args:
        paragraph: The paragraph to add the REF field to
        bookmark_name: The name of the bookmark to reference
    """
    # Create field begin
    run1 = paragraph.add_run()
    r1 = run1._r
    fldChar1 = OxmlElement("w:fldChar")
    fldChar1.set(qn("w:fldCharType"), "begin")
    r1.append(fldChar1)

    # Create field instruction
    run2 = paragraph.add_run()
    r2 = run2._r
    instrText = OxmlElement("w:instrText")
    instrText.set(qn("xml:space"), "preserve")
    instrText.text = f" REF {bookmark_name} \\h "
    r2.append(instrText)

    # Create field separator
    run3 = paragraph.add_run()
    r3 = run3._r
    fldChar3 = OxmlElement("w:fldChar")
    fldChar3.set(qn("w:fldCharType"), "separate")
    r3.append(fldChar3)

    # Create field result (placeholder)
    run4 = paragraph.add_run("Figure 1")

    # Create field end
    run5 = paragraph.add_run()
    r5 = run5._r
    fldChar5 = OxmlElement("w:fldChar")
    fldChar5.set(qn("w:fldCharType"), "end")
    r5.append(fldChar5)


