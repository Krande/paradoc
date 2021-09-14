from __future__ import annotations

import logging
from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from docxcompose.composer import Composer

from paradoc.common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK
from paradoc.formatting.utils import (
    format_table,
    format_paragraph,
    format_captions,
    get_table_ref,
    fix_headers_after_compose,
)
from .utils import close_word_docs_by_name, docx_update, iter_block_items


class WordExporter:
    def __init__(self, one_doc):
        self.one_doc = one_doc

    def convert_to_docx(self, output_name, dest_file):
        one_doc = self.one_doc
        # Main Document - Format Style
        composer_main = Composer(Document(MY_DOCX_TMPL))
        composer_main.doc.add_page_break()

        for i, md in enumerate(one_doc.md_files_main):
            doc_in = Document(str(md.new_file))
            doc_in.add_page_break()
            composer_main.append(doc_in)
            logging.info(f"Added {md.new_file}")

        self.identify_tables(composer_main.doc)
        composer_main.doc.add_page_break()

        # Appendix - Format Style
        composer_app = Composer(Document(MY_DOCX_TMPL_BLANK))
        for i, md in enumerate(one_doc.md_files_app):
            doc_in = Document(str(md.new_file))
            doc_in.add_page_break()
            composer_app.append(doc_in)
            logging.info(f"Added {md.new_file}")

        app_paragraph_style = dict()
        app_paragraph_style.update(one_doc.appendix_heading_map)
        app_paragraph_style.update(one_doc.paragraph_style_map)

        self.identify_tables(composer_main.doc)

        composer_main.append(composer_app.doc)

        fix_headers_after_compose(composer_main.doc)

        print("Close Existing Word documents")
        close_word_docs_by_name([output_name, f"{output_name}.docx"])

        print(f'Saving Composed Document to "{dest_file}"')
        composer_main.save(dest_file)

        docx_update(str(dest_file))

    def identify_tables(self, doc: Document):
        prev_table = False
        current_table = []
        for block in iter_block_items(doc):
            if type(block) == DocxTable:
                current_table.append(block)
                prev_table = True
                continue

            if block.style.name == "Table Caption":
                current_table.append(block)

            if type(block) == Paragraph and prev_table is True and len(block.runs) > 0:
                block.runs[0].text = "\n" + block.runs[0].text
                prev_table = False
                block.paragraph_format.space_before = None
                current_table.append(block)

            if len(current_table) == 3:
                print('Do something with this information')



