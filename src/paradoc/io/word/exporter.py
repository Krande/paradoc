from __future__ import annotations

import logging
import re
from typing import List, Union

from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from docxcompose.composer import Composer

from paradoc.common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK, MarkDownFile, Table
from paradoc.document import OneDoc

from .common import DocXTableRef
from .formatting import (
    fix_headers_after_compose,
    format_image_captions,
    format_paragraphs_and_headings,
)
from .utils import close_word_docs_by_name, docx_update, iter_block_items


class WordExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def convert_to_docx(self, output_name, dest_file):
        one_doc = self.one_doc

        composer_main = add_to_composer(MY_DOCX_TMPL, one_doc.md_files_main)
        composer_app = add_to_composer(MY_DOCX_TMPL_BLANK, one_doc.md_files_app)

        for tbl in self.identify_tables(composer_main.doc):
            tbl.format_table(is_appendix=False)

        for tbl in self.identify_tables(composer_app.doc):
            tbl.format_table(is_appendix=True)

        format_image_captions(composer_main.doc, False)
        format_image_captions(composer_app.doc, True)

        format_paragraphs_and_headings(composer_app.doc, one_doc.appendix_heading_map)

        # Merge docs
        composer_main.doc.add_page_break()
        composer_main.append(composer_app.doc)

        # Format all paragraphs
        format_paragraphs_and_headings(composer_main.doc, one_doc.paragraph_style_map)

        # Apply last minute fixes
        fix_headers_after_compose(composer_main.doc)

        print("Close Existing Word documents")
        close_word_docs_by_name([output_name, f"{output_name}.docx"])

        print(f'Saving Composed Document to "{dest_file}"')
        composer_main.save(dest_file)

        docx_update(str(dest_file))

    def identify_tables(self, doc: Document):
        prev_table = False
        tables = []
        current_table = DocXTableRef()
        for block in iter_block_items(doc):
            if type(block) == DocxTable:
                current_table.docx_table = block
                prev_table = True
                continue

            if block.style.name == "Table Caption":
                current_table.docx_caption = block

            if type(block) == Paragraph and prev_table is True and len(block.runs) > 0:
                block.runs[0].text = "\n" + block.runs[0].text
                prev_table = False
                block.paragraph_format.space_before = None
                current_table.docx_following_pg = block

            if current_table.is_complete():
                source_table = self.get_related_table(current_table)
                if source_table is not None:
                    current_table.table_ref = source_table
                    tables.append(current_table)
                else:
                    logging.error(f'Unable to find table with caption "{current_table.docx_caption}"')
                current_table = DocXTableRef()

        return tables

    def get_related_table(self, current_table: DocXTableRef) -> Union[Table, None]:
        one = self.one_doc
        caption = current_table.docx_caption
        re_cap = re.compile("Table [0-9]{0,9}:(.*)")
        for key, tbl in one.tables.items():
            if "Table" in caption.text:
                m = re_cap.search(caption.text)
                caption_text = str(m.group(1).strip())
            else:
                caption_text = str(caption.text)
            caption_text = caption_text.replace("”", '"')
            if tbl.caption == caption_text:
                return tbl
        return None


def add_to_composer(source_doc, md_files: List[MarkDownFile]) -> Composer:
    composer_doc = Composer(Document(source_doc))
    if source_doc == MY_DOCX_TMPL:
        composer_doc.doc.add_page_break()
    for i, md in enumerate(md_files):
        doc_in = Document(str(md.new_file))
        doc_in.add_page_break()
        composer_doc.append(doc_in)
        logging.info(f"Added {md.new_file}")
    return composer_doc
