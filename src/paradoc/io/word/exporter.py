from __future__ import annotations

import logging
import re
from typing import List, Union

import numpy as np
import pypandoc
from docx import Document
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from docxcompose.composer import Composer

from paradoc.common import (
    MY_DOCX_TMPL,
    MY_DOCX_TMPL_BLANK,
    ExportFormats,
    MarkDownFile,
    Table,
)
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

    def _compile_individual_md_files_to_docx(self):
        one = self.one_doc
        for mdf in one.md_files_main + one.md_files_app:
            md_file = mdf.path
            pypandoc.convert_file(
                str(mdf.build_file),
                ExportFormats.DOCX,
                outputfile=str(mdf.new_file),
                format="markdown",
                extra_args=[
                    "-M2GB",
                    "+RTS",
                    "-K64m",
                    "-RTS",
                    f"--resource-path={md_file.parent}",
                    f"--metadata-file={one.metadata_file}"
                    # f"--reference-doc={MY_DOCX_TMPL}",
                ],
                filters=["pandoc-crossref"],
                encoding="utf8",
            )

    def export(self, output_name, dest_file):
        one_doc = self.one_doc
        self._compile_individual_md_files_to_docx()

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

            if type(block) == Paragraph and prev_table is True:
                prev_table = False
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

    def get_related_table(self, current_table: DocXTableRef, frac=1e-2) -> Union[Table, None]:
        one = self.one_doc

        # Search using Caption string
        caption = current_table.docx_caption
        re_cap = re.compile(r"Table\s*[0-9]{0,9}:(.*)")
        for key, tbl in one.tables.items():
            if "Table" in caption.text:
                m = re_cap.search(caption.text)
                if m is None:
                    raise ValueError()
                caption_text = str(m.group(1).strip())
            else:
                caption_text = str(caption.text)
            caption_text = caption_text.replace("”", '"')
            if tbl.caption == caption_text:
                return tbl

        # If no match using caption string, then use contents of table
        content = get_first_row_from_table(current_table.docx_table)
        is_content_numeric = False
        try:
            content_numeric = np.array(content, dtype=float)
            is_content_numeric = True
        except ValueError:
            content_numeric = None

        for key, tbl in one.tables.items():
            row_1 = tbl.df.iloc[0].values
            if is_content_numeric and len(content) == len(row_1):
                tot = sum(row_1)
                diff = sum(row_1 - content_numeric)
                if abs(diff) < abs(tot) * frac:
                    return tbl
            print("")
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


def get_first_row_from_table(docx_table: DocxTable, num_row=1):
    content = []
    for i, row in enumerate(docx_table.rows):
        if i == 0:
            continue
        for cell in row.cells:
            paragraphs = cell.paragraphs
            for paragraph in paragraphs:
                content.append(paragraph.text.strip())
        return content
