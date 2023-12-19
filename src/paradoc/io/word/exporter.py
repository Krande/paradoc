from __future__ import annotations

import pypandoc
from docx import Document
from docx.table import Table as DocxTable

from paradoc.common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK, ExportFormats
from paradoc.document import OneDoc

from .common import DocXFigureRef, DocXTableRef
from .formatting import fix_headers_after_compose, format_paragraphs_and_headings
from .utils import (
    add_to_composer,
    close_word_docs_by_name,
    docx_update,
    get_from_doc_by_index,
    iter_block_items,
)


class WordExporter:
    def __init__(self, one_doc: OneDoc, main_tmpl=MY_DOCX_TMPL, app_tmpl=MY_DOCX_TMPL_BLANK, **kwargs):
        self.one_doc = one_doc
        self.main_tmpl = main_tmpl
        self.app_tmpl = app_tmpl
        self.use_custom_docx_compile = kwargs.get("use_custom_docx_compile", True)

    def export(self, output_name, dest_file):
        if self.use_custom_docx_compile:
            self._compile_individual_md_files_to_docx(output_name, dest_file)
        else:
            self._compile_docx_from_str(dest_file)

    def _compile_individual_md_files_to_docx(self, output_name, dest_file):
        one = self.one_doc

        for mdf in one.md_files_main + one.md_files_app:
            resource_paths = f"--resource-path={mdf.path.parent.absolute()}"
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
                    # "--file-scope",
                    resource_paths,
                    f"--metadata-file={one.metadata_file}"
                    # f"--reference-doc={MY_DOCX_TMPL}",
                ],
                filters=["pandoc-crossref"],
                sandbox=False,
            )

        composer_main = add_to_composer(self.main_tmpl, one.md_files_main)
        composer_app = add_to_composer(self.app_tmpl, one.md_files_app)

        self.format_tables(composer_main.doc, False)
        self.format_tables(composer_app.doc, True)

        self.format_figures(composer_main.doc, False)
        self.format_figures(composer_app.doc, True)

        format_paragraphs_and_headings(composer_app.doc, one.appendix_heading_map)

        # Merge docs
        composer_main.doc.add_page_break()
        composer_main.append(composer_app.doc)

        # Format all paragraphs
        format_paragraphs_and_headings(composer_main.doc, one.paragraph_style_map)

        # Apply last minute fixes
        fix_headers_after_compose(composer_main.doc)

        print("Close Existing Word documents")
        close_word_docs_by_name([output_name, f"{output_name}.docx"])

        print(f'Saving Composed Document to "{dest_file}"')
        composer_main.save(dest_file)

        docx_update(str(dest_file))

    def format_tables(self, composer_doc: Document, is_appendix):
        for i, docx_tbl in enumerate(self.get_all_tables(composer_doc)):
            cell0 = docx_tbl.get_content_cell0_pg()
            tbl_name = cell0.text
            tbl = self.one_doc.tables.get(tbl_name, None)
            if tbl is None:
                raise ValueError("Unable to retrieve originally parsed table")

            docx_tbl.table_ref = tbl
            docx_tbl.substitute_back_temp_var()
            if is_appendix and i == 0:
                restart_caption_num = True
            else:
                restart_caption_num = False
            docx_tbl.format_table(is_appendix, restart_caption_numbering=restart_caption_num)

    def format_figures(self, composer_doc: Document, is_appendix):
        for i, docx_fig in enumerate(self.get_all_figures(composer_doc)):
            if is_appendix and i == 0:
                restart_caption_num = True
            else:
                restart_caption_num = False
            docx_fig.format_figure(is_appendix, restart_caption_num)

    def get_all_tables(self, doc: Document):
        tables = []

        for i, block in enumerate(iter_block_items(doc)):
            if type(block) is DocxTable:
                current_table = DocXTableRef()
                current_table.docx_table = block
                current_table.docx_caption = get_from_doc_by_index(i - 1, doc)
                current_table.docx_following_pg = get_from_doc_by_index(i + 1, doc)
                current_table.document_index = i
                tables.append(current_table)

        return tables

    def get_all_figures(self, doc: Document):
        figures = []
        for i, block in enumerate(iter_block_items(doc)):
            if block.style.name == "Captioned Figure":
                caption = get_from_doc_by_index(i + 1, doc)
                caption_str = caption.text.split(":")[-1].strip().replace("“", '"').replace("”", '"')
                figure = self.one_doc.figures.get(caption_str, None)
                if figure is None:
                    raise ValueError(f'Figure with caption "{caption_str}" not retrieved')
                current_fig = DocXFigureRef(figure, doc)
                current_fig.docx_figure = block
                current_fig.docx_caption = caption
                current_fig.docx_following_pg = get_from_doc_by_index(i + 2, doc)
                current_fig.document_index = i
                figures.append(current_fig)

        return figures

    def _compile_docx_from_str(self, dest_file):
        one = self.one_doc
        md_main_str = "\n".join([md.read_built_file() for md in one.md_files_main])

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str
        pypandoc.convert_text(
            combined_str,
            one.FORMATS.DOCX,
            outputfile=str(dest_file),
            format="markdown",
            extra_args=[
                "-M2GB",
                "+RTS",
                "-K64m",
                "-RTS",
                f"--metadata-file={one.metadata_file}"
                # f"--reference-doc={MY_DOCX_TMPL}",
            ],
            filters=["pandoc-crossref"],
            encoding="utf8",
        )
