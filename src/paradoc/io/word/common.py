import logging
from dataclasses import dataclass

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from paradoc.common import Table

from .references import add_seq_reference


@dataclass
class DocXTableRef:
    table_ref: Table = None
    docx_table: DocxTable = None
    docx_caption: Paragraph = None
    docx_following_pg: Paragraph = None
    is_appendix = False

    def is_complete(self):
        docx_attr = [self.docx_caption, self.docx_table, self.docx_following_pg]
        return all([x is not None for x in docx_attr])

    def format_table(self, is_appendix):
        tbl = self.docx_table
        tbl_format = self.table_ref.format

        # Format content of table
        tbl.style = tbl_format.style
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        logging.info(f'Changed Table style from "{tbl.style}" to "{tbl_format.style}"')
        for i, row in enumerate(tbl.rows):
            for cell in row.cells:
                paragraphs = cell.paragraphs
                for paragraph in paragraphs:
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
        caption = self.docx_caption
        caption.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        rebuild_caption(caption, self.table_ref.caption, is_appendix)

        for run in caption.runs:
            run.font.name = tbl_format.font_style

        # Fix formatting after Table

        self.docx_following_pg.paragraph_format.space_before = Pt(12)
        # follower_pg = self.docx_following_pg
        #
        # i = par_index(follower_pg)
        #
        # follower_pg.runs[0].text = "\n" + follower_pg.runs[0].text
        # follower_pg.paragraph_format.space_before = None


def rebuild_caption(caption: Paragraph, caption_str, is_appendix):
    caption.clear()
    caption.runs.clear()

    run = caption.add_run()

    heading_ref = "Appendix" if is_appendix is True else '"Heading 1"'

    seq1 = caption._element._new_r()
    seq1.text = "Table "

    add_seq_reference(seq1, f"STYLEREF \\s {heading_ref} \\n", run._parent)
    run._element.addprevious(seq1)

    stroke = caption._element._new_r()
    new_run = Run(stroke, run._parent)
    new_run.text = "-"
    run._element.addprevious(stroke)
    seq2 = caption._element._new_r()
    add_seq_reference(seq2, "SEQ Table \\* ARABIC \\s 1", run._parent)
    run._element.addprevious(seq2)
    fin = caption._element._new_r()
    fin_run = Run(fin, run._parent)
    fin_run.text = ": " + caption_str
    run._element.addprevious(fin)
