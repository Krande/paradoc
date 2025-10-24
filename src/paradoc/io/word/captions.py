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
    # For chapter-based numbering (Figure 1-1, 1-2, 2-1, etc.), we need:
    # - First figure/table: SEQ Figure \* ARABIC \r 1 \s 1
    #   (\r 1 initializes to 1, \s 1 enables chapter tracking)
    # - Subsequent figures/tables: SEQ Figure \* ARABIC \s 1
    #   (\s 1 continues chapter tracking and increments within chapter)
    if should_restart:
        # Initialize the sequence with \r 1 and enable chapter tracking with \s 1
        seq_instruction = f"SEQ {caption_prefix} \\* ARABIC \\r 1 \\s 1"
    else:
        # Continue the sequence within the chapter
        seq_instruction = f"SEQ {caption_prefix} \\* ARABIC \\s 1"


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


