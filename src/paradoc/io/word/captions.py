"""Caption formatting and rebuilding for Word documents."""

from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .fields import add_seq_reference

#: Separator between the chapter part and the counter: "Figure 6.3", "Figure A.2".
CHAPTER_SEPARATOR = "."


def chapter_styleref(is_appendix: bool) -> str:
    """STYLEREF instruction yielding the current chapter's number ("6") or appendix letter ("A").

    ``\\n`` inserts the heading's list number. The template's appendix headings are numbered
    "Appendix %1", whose list text would come along with it ("Figure Appendix A.1"); ``\\t``
    suppresses the non-delimiter, non-numeric text and leaves only the letter.
    """
    heading_ref = '"Appendix"' if is_appendix else '"Heading 1"'
    return f"STYLEREF \\s {heading_ref} \\n \\t"


def seq_instruction(seq_name: str, should_restart: bool, chapter_numbering: bool = True) -> str:
    """SEQ instruction for a caption counter.

    Chapter numbering: ``\\s 1`` restarts the counter at every heading of outline level 1 -- both
    "Heading 1" and the "Appendix" style that is based on it -- so each chapter and each appendix
    counts from 1. Without it, one running count through the document.
    """
    parts = [f"SEQ {seq_name} \\* ARABIC"]
    if should_restart:
        parts.append("\\r 1")
    if chapter_numbering:
        parts.append("\\s 1")
    return " ".join(parts)


def rebuild_caption(
    caption: Paragraph,
    caption_prefix: str,
    caption_str: str,
    is_appendix: bool,
    should_restart: bool = False,
    chapter_numbering: bool = True,
):
    """Rebuild a caption paragraph with proper SEQ and STYLEREF fields.

    With chapter numbering, creates a caption like "Figure 2.1: Caption text" ("Figure A.1: ..."
    in an appendix) where:
    - "Figure " is plain text
    - "2" comes from a STYLEREF field (chapter number, or appendix letter)
    - "." is plain text
    - "1" comes from a SEQ field (figure/table counter, restarted per chapter)
    - ": Caption text" is plain text

    Without chapter numbering the STYLEREF field and separator are left out: "Figure 7: ...".

    Args:
        caption: The caption paragraph to rebuild
        caption_prefix: The caption type ("Figure", "Table", etc.)
        caption_str: The caption text to display after the number
        is_appendix: Whether this is in the appendix section
        should_restart: Whether to restart numbering at this caption
        chapter_numbering: Prefix the number with the chapter number / appendix letter
    """
    caption.clear()
    caption.runs.clear()

    run = caption.add_run()

    # Add caption prefix text (e.g., "Figure ")
    seq1 = caption._element._new_r()
    seq1.text = caption_prefix + " "

    if chapter_numbering:
        # STYLEREF field for the chapter number / appendix letter
        add_seq_reference(seq1, chapter_styleref(is_appendix), run._parent, placeholder="A" if is_appendix else "1")
        run._element.addprevious(seq1)

        # Separator
        stroke = caption._element._new_r()
        new_run = Run(stroke, run._parent)
        new_run.text = CHAPTER_SEPARATOR
        run._element.addprevious(stroke)
    else:
        run._element.addprevious(seq1)

    # Add SEQ field for figure/table number
    seq2 = caption._element._new_r()
    add_seq_reference(seq2, seq_instruction(caption_prefix, should_restart, chapter_numbering), run._parent)
    run._element.addprevious(seq2)

    # Add caption text
    fin = caption._element._new_r()
    fin_run = Run(fin, run._parent)
    fin_run.text = ": " + caption_str
    run._element.addprevious(fin)
