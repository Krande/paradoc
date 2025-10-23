"""Caption formatting and rebuilding for Word documents."""

from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .fields import add_seq_reference


def rebuild_caption(caption: Paragraph, caption_prefix: str, caption_str: str, is_appendix: bool, should_restart: bool = False):
    """Rebuild a caption paragraph with proper SEQ and STYLEREF fields.

    Creates a caption like "Figure 2-1: Caption text" where:
    - "Figure " is plain text
    - "2" comes from STYLEREF field (chapter/heading number)
    - "-" is plain text
    - "1" comes from SEQ field (figure/table counter)
    - ": Caption text" is plain text

    Args:
        caption: The caption paragraph to rebuild
        caption_prefix: The caption type ("Figure", "Table", etc.)
        caption_str: The caption text to display after the number
        is_appendix: Whether this is in the appendix section
        should_restart: Whether to restart numbering at this caption
    """
    caption.clear()
    caption.runs.clear()

    run = caption.add_run()

    heading_ref = '"Appendix"' if is_appendix else '"Heading 1"'

    # Build the SEQ field instruction
    # Format: SEQ Figure \* ARABIC \s 1
    # where Figure/Table is the identifier, \* ARABIC is the format, \s 1 restarts numbering
    seq_instruction = f"SEQ {caption_prefix} \\* ARABIC"

    if should_restart:
        # \r switch restarts numbering at heading level
        if is_appendix:
            seq_instruction += ' \\r "Appendix X.1"'
        else:
            seq_instruction += ' \\r "Heading 1"'
    else:
        # \s switch continues numbering from heading level
        seq_instruction += ' \\s 1'

    # Add caption prefix text (e.g., "Figure ")
    seq1 = caption._element._new_r()
    seq1.text = caption_prefix + " "

    # Add STYLEREF field for chapter/heading number
    add_seq_reference(seq1, f"STYLEREF \\s {heading_ref} \\n", run._parent)
    run._element.addprevious(seq1)

    # Add hyphen separator
    stroke = caption._element._new_r()
    new_run = Run(stroke, run._parent)
    new_run.text = "-"
    run._element.addprevious(stroke)

    # Add SEQ field for figure/table number
    seq2 = caption._element._new_r()
    add_seq_reference(seq2, seq_instruction, run._parent)
    run._element.addprevious(seq2)

    # Add caption text
    fin = caption._element._new_r()
    fin_run = Run(fin, run._parent)
    fin_run.text = ": " + caption_str
    run._element.addprevious(fin)


def insert_caption(pg: Paragraph, prefix: str, run, text: str, is_appendix: bool):
    """Insert caption fields into a paragraph before a given run.

    Legacy function that inserts STYLEREF, hyphen, SEQ, and text before a specific run.

    Args:
        pg: The paragraph to modify
        prefix: The caption prefix ("Figure", "Table", etc.)
        run: The run to insert fields before
        text: The caption text
        is_appendix: Whether this is in the appendix
    """
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
    """Insert caption fields into an existing paragraph's runs.

    Legacy function that parses existing caption text and inserts fields.

    Args:
        pg: The paragraph containing the caption
        prefix: The caption prefix ("Figure", "Table", etc.)
        is_appendix: Whether this is in the appendix

    Returns:
        Tuple of (start_run, paragraph, old_prefix)
    """
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

