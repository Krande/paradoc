from __future__ import annotations

import pypandoc
from docx import Document
from docx.table import Table as DocxTable

from paradoc.common import MY_DOCX_TMPL, MY_DOCX_TMPL_BLANK, ExportFormats
from paradoc.config import logger
from paradoc.document import OneDoc
from paradoc.io.word.com_api.com_utils import docx_update, close_word_docs_by_name
from .formatting import fix_headers_after_compose, format_paragraphs_and_headings
from .models import DocXFigureRef, DocXTableRef, DocXEquationRef
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

        # Step 1: Convert individual markdown files to DOCX
        self._convert_markdown_files_to_docx(one)

        # Step 2: Compose main and appendix documents
        composer_main = add_to_composer(self.main_tmpl, one.md_files_main)
        composer_app = add_to_composer(self.app_tmpl, one.md_files_app)

        # Step 3: Extract and format all caption elements (tables, figures, equations)
        # This replaces the previous approach of calling format_tables/format_figures twice
        self._extract_and_format_captions(composer_main.doc, composer_app.doc, ref_helper)

        # Step 4: Format appendix headings
        format_paragraphs_and_headings(composer_app.doc, one.appendix_heading_map)

        # Step 5: Merge documents
        composer_main.doc.add_page_break()
        composer_main.append(composer_app.doc)
        logger.info("[WordExporter] Merged main document and appendix")

        # Step 6: Update display numbers and convert cross-references
        self._update_and_convert_references(composer_main.doc, ref_helper)

        # Step 7: Format all paragraphs
        format_paragraphs_and_headings(composer_main.doc, one.paragraph_style_map)

        # Step 8: Apply final fixes
        fix_headers_after_compose(composer_main.doc)
        fix_bookmark_ids(composer_main.doc)

        # Step 9: Save and optionally update with COM automation
        self._save_document(composer_main, output_name, dest_file, check_open_docs)

    def _convert_markdown_files_to_docx(self, one_doc):
        """Convert all markdown files to individual DOCX files using pandoc.

        Args:
            one_doc: The OneDoc instance containing markdown files
        """
        logger.info("[WordExporter] Converting markdown files to DOCX")

        for mdf in one_doc.md_files_main + one_doc.md_files_app:
            # Use build_file parent as resource path since images are stored relative to build location
            resource_paths = f"--resource-path={mdf.build_file.parent.absolute()}"
            pypandoc.convert_file(
                str(mdf.build_file),
                ExportFormats.DOCX,
                outputfile=str(mdf.new_file),
                format="markdown",
                extra_args=["-M2GB", "+RTS", "-K64m", "-RTS", resource_paths, f"--metadata-file={one_doc.metadata_file}"],
                filters=["pandoc-crossref"],
                sandbox=False,
            )

        logger.info(f"[WordExporter] Converted {len(one_doc.md_files_main) + len(one_doc.md_files_app)} markdown files")

    def _extract_and_format_captions(self, main_doc, app_doc, ref_helper):
        """Extract and format all caption elements (tables, figures, equations) from both documents.

        This method replaces the previous approach of calling format_tables and format_figures
        separately for main and appendix. It extracts all caption elements using the
        ReferenceHelper and formats them in a single pass.

        Args:
            main_doc: The main document
            app_doc: The appendix document
            ref_helper: The ReferenceHelper instance
        """
        logger.info("[WordExporter] Extracting and formatting caption elements")

        # Extract all tables, figures, and equations from both documents
        main_tables = ref_helper.extract_all_tables(main_doc, self.one_doc, is_appendix=False)
        app_tables = ref_helper.extract_all_tables(app_doc, self.one_doc, is_appendix=True)

        main_figures = ref_helper.extract_all_figures(main_doc, self.one_doc, is_appendix=False)
        app_figures = ref_helper.extract_all_figures(app_doc, self.one_doc, is_appendix=True)

        main_equations = ref_helper.extract_all_equations(main_doc, is_appendix=False)
        app_equations = ref_helper.extract_all_equations(app_doc, is_appendix=True)

        # Format tables
        logger.info("[WordExporter] Formatting tables")
        for i, docx_tbl in enumerate(main_tables):
            docx_tbl.substitute_back_temp_var()
            restart_caption_num = (i == 0)  # Restart numbering for first table
            docx_tbl.format_table(False, restart_caption_numbering=restart_caption_num, reference_helper=ref_helper)

        for i, docx_tbl in enumerate(app_tables):
            docx_tbl.substitute_back_temp_var()
            restart_caption_num = (i == 0)  # Restart numbering for first appendix table
            docx_tbl.format_table(True, restart_caption_numbering=restart_caption_num, reference_helper=ref_helper)

        # Format figures
        logger.info("[WordExporter] Formatting figures")
        for i, docx_fig in enumerate(main_figures):
            restart_caption_num = (i == 0)  # Restart numbering for first figure
            docx_fig.format_figure(False, restart_caption_num, reference_helper=ref_helper)

        for i, docx_fig in enumerate(app_figures):
            restart_caption_num = (i == 0)  # Restart numbering for first appendix figure
            docx_fig.format_figure(True, restart_caption_num, reference_helper=ref_helper)

        # Format equations
        logger.info("[WordExporter] Formatting equations")
        for i, docx_eq in enumerate(main_equations):
            restart_caption_num = (i == 0)  # Restart numbering for first equation
            docx_eq.format_equation(False, restart_caption_numbering=restart_caption_num, reference_helper=ref_helper)

        for i, docx_eq in enumerate(app_equations):
            restart_caption_num = (i == 0)  # Restart numbering for first appendix equation
            docx_eq.format_equation(True, restart_caption_numbering=restart_caption_num, reference_helper=ref_helper)

        logger.info(
            f"[WordExporter] Formatted {len(main_tables) + len(app_tables)} tables, "
            f"{len(main_figures) + len(app_figures)} figures, "
            f"{len(main_equations) + len(app_equations)} equations"
        )

    def _update_and_convert_references(self, document, ref_helper):
        """Update display numbers and convert cross-references to REF fields.

        Args:
            document: The merged Word document
            ref_helper: The ReferenceHelper instance
        """
        logger.info("[WordExporter] Updating display numbers in ReferenceHelper")
        ref_helper.update_display_numbers()

        # Print registry for debugging
        ref_helper.print_registry()

        # Convert references using the configured method
        if self.use_hyperlink_references:
            # New method: Extract hyperlink references and convert them
            logger.info("[WordExporter] Converting hyperlink-based cross-references to REF fields")
            hyperlink_refs = ref_helper.extract_hyperlink_references(document)
            logger.info(f"[WordExporter] Found {len(hyperlink_refs)} hyperlink references")
            ref_helper.convert_hyperlink_references(hyperlink_refs)
        else:
            # Old method: Use pattern-based conversion
            logger.info("[WordExporter] Converting text references to REF fields using pattern matching")
            ref_helper.convert_all_references(document)

    def _save_document(self, composer, output_name, dest_file, check_open_docs):
        """Save the document and optionally update with COM automation.

        Args:
            composer: The Composer instance with the final document
            output_name: Name of the output file
            dest_file: Destination file path
            check_open_docs: Whether to check and close open Word documents
        """
        logger.info("Close Existing Word documents")
        if check_open_docs and self.enable_word_com_automation:
            close_word_docs_by_name([output_name, f"{output_name}.docx"])

        print(f'Saving Composed Document to "{dest_file}"')
        composer.save(dest_file)

        # Only attempt Word COM automation if explicitly enabled
        # This is disabled by default to avoid fatal COM errors in test/CI environments
        if self.enable_word_com_automation:
            docx_update(str(dest_file))

    def format_tables(self, composer_doc: Document, is_appendix, reference_helper=None):
        """DEPRECATED: Use _extract_and_format_captions instead.

        Format tables and register them with the reference helper.
        This method is kept for backward compatibility but should not be used in new code.
        """
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
