import logging
from dataclasses import dataclass

from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from paradoc.common import Table

from .references import insert_caption_into_runs


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

        # Format table Caption
        caption = self.docx_caption
        caption.paragraph_format.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        insert_caption_into_runs(caption, "Table", is_appendix)
        for run in caption.runs:
            run.font.name = tbl_format.font_style

        # Fix formatting after Table
        follower_pg = self.docx_following_pg
        follower_pg.runs[0].text = "\n" + follower_pg.runs[0].text
        follower_pg.paragraph_format.space_before = None
