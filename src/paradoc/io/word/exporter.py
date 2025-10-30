from __future__ import annotations

import pypandoc
from docx import Document
from docx.table import Table as DocxTable

from paradoc.common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK, ExportFormats
from paradoc.config import logger
from paradoc.document import OneDoc
from paradoc.io.word.com_api.com_utils import docx_update, close_word_docs_by_name
from .formatting import fix_headers_after_compose, format_paragraphs_and_headings
from .models import DocXFigureRef, DocXTableRef
from .reference_helper import ReferenceHelper
from .utils import (
    add_to_composer,
    fix_bookmark_ids,
    get_from_doc_by_index,
    iter_block_items,
)


class WordExporter:
    def __init__(
        self,
        one_doc: OneDoc,
        main_tmpl=MY_DOCX_TMPL,
        app_tmpl=MY_DOCX_TMPL_BLANK,
        use_hyperlink_references=True,
        enable_word_com_automation=False,
        use_custom_docx_compile=True,
    ):
        self.one_doc = one_doc
        self.main_tmpl = main_tmpl
        self.app_tmpl = app_tmpl
        self.use_custom_docx_compile = use_custom_docx_compile
        self.enable_word_com_automation = enable_word_com_automation
        self.use_hyperlink_references = use_hyperlink_references

    def export(self, output_name, dest_file, check_open_docs=False):
        if self.use_custom_docx_compile:
            self._compile_individual_md_files_to_docx(output_name, dest_file, check_open_docs)
        else:
            self._compile_docx_from_str(dest_file)

    def _compile_individual_md_files_to_docx(self, output_name, dest_file, check_open_docs=False):
        one = self.one_doc

        # Initialize the reference helper to manage all cross-references
        ref_helper = ReferenceHelper()
        logger.info("[WordExporter] Initialized ReferenceHelper for cross-reference management")

        for mdf in one.md_files_main + one.md_files_app:
            # Use build_file parent as resource path since images are stored relative to build location
            resource_paths = f"--resource-path={mdf.build_file.parent.absolute()}"
            pypandoc.convert_file(
                str(mdf.build_file),
                ExportFormats.DOCX,
                outputfile=str(mdf.new_file),
                format="markdown",
                extra_args=["-M2GB", "+RTS", "-K64m", "-RTS", resource_paths, f"--metadata-file={one.metadata_file}"],
                filters=["pandoc-crossref"],
                sandbox=False,
            )

        composer_main = add_to_composer(self.main_tmpl, one.md_files_main)
        composer_app = add_to_composer(self.app_tmpl, one.md_files_app)


        # Format tables and register them with the reference helper
        self.format_tables(composer_main.doc, False, ref_helper)
        self.format_tables(composer_app.doc, True, ref_helper)

        # Format figures and register them with the reference helper
        self.format_figures(composer_main.doc, False, ref_helper)
        self.format_figures(composer_app.doc, True, ref_helper)

        format_paragraphs_and_headings(composer_app.doc, one.appendix_heading_map)

        # Merge docs
        composer_main.doc.add_page_break()
        composer_main.append(composer_app.doc)
        logger.info("[WordExporter] Merged main document and appendix")

        # Update display numbers in the reference helper
        logger.info("[WordExporter] Updating display numbers in ReferenceHelper")
        ref_helper.update_display_numbers()

        # Print registry for debugging
        ref_helper.print_registry()

        # Convert references using the configured method
        if self.use_hyperlink_references:
            # New method: Extract hyperlink references and convert them
            logger.info("[WordExporter] Converting hyperlink-based cross-references to REF fields")
            hyperlink_refs = ref_helper.extract_hyperlink_references(composer_main.doc)
            logger.info(f"[WordExporter] Found {len(hyperlink_refs)} hyperlink references")
            ref_helper.convert_hyperlink_references(hyperlink_refs)
        else:
            # Old method: Use pattern-based conversion
            logger.info("[WordExporter] Converting text references to REF fields using pattern matching")
            ref_helper.convert_all_references(composer_main.doc)

        # Format all paragraphs
        format_paragraphs_and_headings(composer_main.doc, one.paragraph_style_map)

        # Apply last minute fixes
        fix_headers_after_compose(composer_main.doc)

        # Fix bookmark ID mismatches caused by docxcompose
        # This is critical for cross-references to work correctly
        fix_bookmark_ids(composer_main.doc)

        logger.info("Close Existing Word documents")
        if check_open_docs and self.enable_word_com_automation:
            close_word_docs_by_name([output_name, f"{output_name}.docx"])

        print(f'Saving Composed Document to "{dest_file}"')
        composer_main.save(dest_file)

        # Only attempt Word COM automation if explicitly enabled
        # This is disabled by default to avoid fatal COM errors in test/CI environments
        if self.enable_word_com_automation:
            docx_update(str(dest_file))

    def format_tables(self, composer_doc: Document, is_appendix, reference_helper=None):
        tables = []
        for i, docx_tbl in enumerate(self.get_all_tables(composer_doc)):
            try:
                cell0 = docx_tbl.get_content_cell0_pg()
            except IndexError:
                continue
            tbl_name = cell0.text
            tbl = self.one_doc.tables.get(tbl_name, None)
            if tbl is None:
                raise ValueError(f"Unable to retrieve originally parsed table '{tbl_name}'")

            docx_tbl.table_ref = tbl
            docx_tbl.substitute_back_temp_var()
            # Restart numbering for:
            # 1. The very first table in the main document (i == 0 and not is_appendix)
            # 2. The first table in the appendix (i == 0 and is_appendix)
            # This initializes the SEQ field with \r 1 \s 1
            if i == 0:
                restart_caption_num = True
            else:
                restart_caption_num = False
            docx_tbl.format_table(
                is_appendix, restart_caption_numbering=restart_caption_num, reference_helper=reference_helper
            )
            tables.append(docx_tbl)
        return tables

    def format_figures(self, composer_doc: Document, is_appendix, reference_helper=None):
        figures = self.get_all_figures(composer_doc)
        for i, docx_fig in enumerate(figures):
            # Restart numbering for:
            # 1. The very first figure in the main document (i == 0 and not is_appendix)
            # 2. The first figure in the appendix (i == 0 and is_appendix)
            # This initializes the SEQ field with \r 1 \s 1
            if i == 0:
                restart_caption_num = True
            else:
                restart_caption_num = False
            docx_fig.format_figure(is_appendix, restart_caption_num, reference_helper=reference_helper)
        return figures

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
                f"--metadata-file={one.metadata_file}",
                # f"--reference-doc={MY_DOCX_TMPL}",
            ],
            filters=["pandoc-crossref"],
        )
