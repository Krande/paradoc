from __future__ import annotations

import os
import pathlib
import shutil
from itertools import chain
from typing import TYPE_CHECKING, Callable, Dict, Iterable, Optional

import pandas as pd

from .common import (
    MY_DEFAULT_HTML_CSS,
    MY_DOCX_TMPL,
    MY_DOCX_TMPL_BLANK,
    DocXFormat,
    ExportFormats,
    Figure,
    MarkDownFile,
    Table,
    TableFormat,
)
from .config import logger
from .db import (
    DbManager,
    apply_table_annotation,
    parse_plot_reference,
    parse_table_reference,
    table_data_to_dataframe,
)
from .db.plot_renderer import PlotRenderer
from .equations import Equation
from .exceptions import LatexNotInstalled
from .io.ast.exporter import ASTExporter
from .pandoc_helper import ensure_pandoc_path
from .utils import get_list_of_files

# Used to be called from paradoc/__init__.py at import time. Moved here so the
# serve path (which imports paradoc.serve.cli) doesn't trigger it. Importers
# of OneDoc still get pandoc on PYPANDOC_PANDOC the same as before.
ensure_pandoc_path()

if TYPE_CHECKING:
    from .io.pdf.exporter import PdfExporter
    from .io.word.exporter import WordExporter


def _kwargs_to_table_anno_str(kwargs: dict) -> str:
    """Inverse of `TableAnnotation.from_annotation_string`.

    Converts the parsed-substitution kwargs back into a `{tbl:...}` annotation
    so the legacy `_get_table_markdown_from_db` path can pick them up.
    """
    parts: list[str] = []
    if kwargs.get("show_index") is False:
        parts.append("index:no")
    elif kwargs.get("show_index") is True:
        parts.append("index:yes")
    if "sort_by" in kwargs:
        spec = f"sortby:{kwargs['sort_by']}"
        if kwargs.get("sort_ascending") is False:
            spec += ":desc"
        parts.append(spec)
    if "filter_pattern" in kwargs:
        spec = f"filter:{kwargs['filter_pattern']}"
        if "filter_column" in kwargs:
            spec += f":{kwargs['filter_column']}"
        parts.append(spec)
    if kwargs.get("no_caption") is True:
        parts.append("nocaption")
    if not parts:
        return ""
    return "{tbl:" + ";".join(parts) + "}"


def _kwargs_to_plot_anno_str(kwargs: dict) -> str:
    """Inverse of `PlotAnnotation.from_annotation_string`."""
    parts: list[str] = []
    if "width" in kwargs:
        parts.append(f"width:{kwargs['width']}")
    if "height" in kwargs:
        parts.append(f"height:{kwargs['height']}")
    if kwargs.get("no_caption") is True:
        parts.append("nocaption")
    if "format" in kwargs:
        parts.append(f"format:{kwargs['format']}")
    if not parts:
        return ""
    return "{plt:" + ";".join(parts) + "}"


def _find_matching_brace(text: str, start: int) -> int:
    """Index of the `}` that closes the `{` at `text[start]`, or -1."""
    if start >= len(text) or text[start] != "{":
        return -1
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


class OneDoc:
    """

    Work dir should be structured with 2 directories '00-main' and '01-app' representing the Main and Appendix part
    of your report.


    :param source_dir:
    :param export_format:
    :param clean_build_dir:
    :param create_dirs: If not exists create default main and app dirs.
    :param variable_map:
    :param table_format: Optional override table format
    :param paragraph_style_map: Optional override paragraph format
    :param appendix_heading_map: Optional override appendix formats
    """

    default_paragraph_map = {
        "Normal": "Normal Indent",
        "First Paragraph": "Normal Indent",
        "Body Text": "Normal Indent",
        "Compact": "Normal Indent",
    }

    default_app_map = {
        **default_paragraph_map,
        "Heading 1": "Appendix",
        "Heading 2": "Appendix X.1",
        "Heading 3": "Appendix X.2",
        "Heading 4": "Appendix X.3",
    }

    FORMATS = ExportFormats

    def __init__(
        self,
        source_dir=None,
        main_prefix="00-main",
        app_prefix="01-app",
        clean_build_dir=True,
        create_dirs=False,
        output_dir=None,
        work_dir=None,
        use_default_html_style=True,
        bibliography_file=None,
        shelf_base_url=None,
        **kwargs,
    ):
        self.source_dir = pathlib.Path().resolve().absolute() if source_dir is None else pathlib.Path(source_dir)
        if work_dir is None:
            work_dir = pathlib.Path("temp") / self.source_dir.name
        self.work_dir = pathlib.Path(work_dir).resolve().absolute()
        self.work_dir = self.work_dir.resolve().absolute()
        # check if work_dir is a subdirectory of source_dir, then raise an error
        if self.source_dir in self.work_dir.parents:
            raise ValueError(f"work_dir '{self.work_dir}' cannot be a subdirectory of source_dir '{self.source_dir}'")

        self._main_prefix = main_prefix
        self._app_prefix = app_prefix
        self._output_dir = output_dir
        self.variables = dict()
        self.tables: Dict[str, Table] = dict()
        self.equations: Dict[str, Equation] = dict()
        self.figures: Dict[str, Figure] = dict()
        self.doc_format = DocXFormat()

        # Style info: https://python-docx.readthedocs.io/en/latest/user/styles-using.html
        self.paragraph_style_map = kwargs.get("paragraph_style_map", OneDoc.default_paragraph_map)
        self.appendix_heading_map = kwargs.get("appendix_heading_map", OneDoc.default_app_map)
        self.md_files_main = []
        self.md_files_app = []
        self.metadata_file = None
        self.use_default_html_style = use_default_html_style

        # Shelf citation deep-link config. ``bibliography_file`` points
        # to a YAML file with CSL-style `references:` entries; the
        # citation filter (paradoc.citation.filter) loads it via env at
        # compile time. Defaults to ``<source_dir>/references.yaml``
        # when that file exists. ``shelf_base_url`` is substituted into
        # the ``{shelf_base_url}`` placeholder in each entry's ``URL``;
        # falls back to env ``PARADOC_SHELF_BASE_URL`` then empty.
        if bibliography_file is not None:
            self.bibliography_file = pathlib.Path(bibliography_file)
        else:
            default_bib = self.source_dir / "references.yaml"
            self.bibliography_file = default_bib if default_bib.is_file() else None
        if shelf_base_url is not None:
            self.shelf_base_url = str(shelf_base_url)
        else:
            self.shelf_base_url = os.environ.get("PARADOC_SHELF_BASE_URL", "").strip()

        # Initialize database manager at source_dir/data.db
        db_path = self.source_dir / "data.db"
        self.db_manager = DbManager(db_path)

        # Initialize plot renderer with caching
        cache_dir = self.work_dir / ".paradoc_cache"
        self.plot_renderer = PlotRenderer(cache_dir=cache_dir)

        # Filter registry — discovers `<source_dir>/filters.py` lazily during compile.
        from paradoc.filters import FilterRegistry
        self._filter_registry = FilterRegistry()
        self._filters_discovered = False

        # Track table key usage to ensure unique keys when tables are reused with different filters/sorts
        self._table_key_usage_count: Dict[str, int] = {}
        self._plot_key_usage_count: Dict[str, int] = {}

        self._setup(create_dirs, clean_build_dir)

    def _iter_md_files(self) -> Iterable[pathlib.Path]:
        content_iters = [get_list_of_files(self.main_dir, ".md")]
        if self.app_dir.exists():
            content_iters.append(get_list_of_files(self.app_dir, ".md"))

        # chain to single iterable
        md_file_iter = chain(*content_iters)
        for md_file_path in md_file_iter:
            yield pathlib.Path(md_file_path)

    def _setup(self, create_dirs, clean_build_dir):
        if create_dirs is True:
            os.makedirs(self.main_dir, exist_ok=True)
            os.makedirs(self.app_dir, exist_ok=True)

        for md_file_path in self._iter_md_files():
            logger.info(f'Adding markdown file "{md_file_path}"')
            is_appendix = self.app_dir in md_file_path.parents
            md_file_path = pathlib.Path(md_file_path)
            rel_path = md_file_path.relative_to(self.source_dir)
            if self.dist_dir in md_file_path.parents:
                logger.info(f"file {md_file_path} located in `dist_dir` dir is skipped")
                continue

            new_file = self.build_dir / rel_path.with_suffix(".docx")
            build_file = self.build_dir / rel_path

            md_file = MarkDownFile(
                path=md_file_path,
                is_appendix=is_appendix,
                new_file=new_file,
                build_file=build_file,
            )
            if is_appendix:
                self.md_files_app.append(md_file)
            else:
                self.md_files_main.append(md_file)

            for fig in md_file.get_figures():
                d = fig.groupdict()

                # Check if the figure is commented out
                # Get first newline right before regex search found start and till the end (capture entire line)
                start = fig.string[: fig.start()].rfind("\n") + 1
                end = fig.string[fig.start() :].find("\n") + fig.start()
                line = fig.string[start:end]
                if line.startswith("[//]: #"):
                    continue
                ref = d.get("reference", None)
                caption = str(d["caption"])
                file_path = d["file_path"]
                if ' "' in file_path:
                    file_path = file_path.split(' "')[0]
                name = ref if ref is not None else caption
                if caption in self.figures.keys():
                    raise ValueError(
                        f'Failed uniqueness check for Caption "{caption}". '
                        f"Uniqueness is required for OneDoc to index the figures"
                    )
                self.figures[caption] = Figure(name, caption, ref, file_path, md_instance=md_file)

            for re_table in md_file.get_tables():
                table = Table.from_markdown_str(re_table.group(1))
                self.tables[table.name] = table

        if clean_build_dir is True:
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def get_ast(self, metadata_file=None) -> ASTExporter:
        self._prep_compilation(metadata_file=metadata_file)
        self._perform_variable_substitution()
        return ASTExporter(self)

    def get_document_structure(self, metadata_file=None):
        """Get the complete document structure with section hierarchy.

        This method extracts a comprehensive hierarchical structure of the document,
        including sections, paragraphs, figures, tables, equations, and cross-references.

        Args:
            metadata_file: Optional metadata file path

        Returns:
            DocumentStructure object containing the complete document hierarchy

        Example:
            >>> one = OneDoc(source_dir)
            >>> structure = one.get_document_structure()
            >>> stats = structure.validate()
            >>> print(f"Document has {stats['total_sections']} sections")
            >>>
            >>> # Navigate sections
            >>> for root_section in structure.root_sections:
            >>>     print(f"{root_section.number}: {root_section.title}")
            >>>     for child in root_section.children:
            >>>         print(f"  {child.number}: {child.title}")
        """
        from paradoc.io.ast.document_structure import DocumentStructureExtractor

        # Build the AST
        exporter = self.get_ast(metadata_file=metadata_file)
        ast = exporter.build_ast()

        # Extract document structure
        extractor = DocumentStructureExtractor(ast)
        structure = extractor.extract()

        return structure

    def get_docx(
        self,
        main_tmpl=MY_DOCX_TMPL,
        app_tmpl=MY_DOCX_TMPL_BLANK,
        use_hyperlink_references=True,
        enable_word_com_automation=False,
        use_custom_docx_compile=True,
    ):
        from paradoc.io.word.exporter import WordExporter

        return WordExporter(
            self,
            main_tmpl=main_tmpl,
            app_tmpl=app_tmpl,
            use_hyperlink_references=use_hyperlink_references,
            enable_word_com_automation=enable_word_com_automation,
            use_custom_docx_compile=use_custom_docx_compile,
        )

    def send_to_frontend(self, metadata_file=None, embed_images=True, use_static_html=False, frontend_id=None):
        """
        Send document to Paradoc frontend reader via WebSocket.

        Args:
            metadata_file: Optional metadata file path
            embed_images: If True, embed images as base64 in WebSocket messages
            use_static_html: If True, extract frontend.zip and open in browser
            frontend_id: Optional frontend ID to target specific frontend instance. If None, sends to all connected frontends.
        """
        shutil.rmtree(self.dist_dir, ignore_errors=True)

        html = self.get_ast(metadata_file=metadata_file)
        html.send_to_frontend(embed_images=embed_images, use_static_html=use_static_html, frontend_id=frontend_id)

    def export_static(
        self,
        output_dir: pathlib.Path | str,
        metadata_file=None,
        embed_images: bool = True,
        include_frontend: bool = True,
        header_links: Optional[Iterable[dict]] = None,
    ) -> bool:
        """
        Export document to static files for web hosting without a WebSocket server.

        This method generates all the data files (JSON) needed to render the document
        in a static web environment. The output can be served by any static file server.

        Args:
            output_dir: Directory to write the static files to
            metadata_file: Optional metadata file path
            embed_images: If True, embed images as base64 in the data files
            include_frontend: If True, copy the frontend HTML/JS files to output_dir
            header_links: Optional iterable of link dicts (``{"label": str, "href": str,
                "target": str?, "rel": str?}``) rendered into the Topbar. Hosts that embed
                or link to the bundle (Sphinx, MkDocs, ...) can use this for a
                "Back to docs" affordance without rebuilding the frontend.

        Returns:
            True if successful, False otherwise

        Example:
            >>> one = OneDoc("my_report")
            >>> one.add_table("results", df, "Results Table")
            >>> one.export_static("./static_output")
            # Output: ./static_output/index.html, manifest.json, sections/, etc.
        """
        output_dir = pathlib.Path(output_dir)

        # Prepare compilation (variable substitution, etc.)
        self._prep_compilation(metadata_file=metadata_file)
        self._perform_variable_substitution()

        # Get AST exporter and export to static files
        ast_exporter = self.get_ast(metadata_file=metadata_file)
        return ast_exporter.export_to_static_files(
            output_dir=output_dir,
            embed_images=embed_images,
            include_frontend=include_frontend,
            header_links=list(header_links) if header_links is not None else None,
        )

    def _prep_compilation(self, metadata_file=None):
        self.build_dir.mkdir(exist_ok=True, parents=True)
        self.dist_dir.mkdir(exist_ok=True, parents=True)

        # Move/copy all non-markdown assets into build and dist so Pandoc and the HTTP server can resolve them
        src_root = pathlib.Path(self.source_dir)
        for fp in src_root.rglob("*"):
            fp = pathlib.Path(fp)
            if not fp.is_file():
                continue

            # Skip metadata.yaml files for both build and dist directories
            if fp.suffix.lower() in (".yaml", ".py", ".db"):
                continue

            # Python bytecode caches: ``__pycache__/*.pyc`` and stray
            # ``.pyo`` files from local ``populate_*.py`` runs. ``.py``
            # is filtered above; ``.pyc`` slipped through because the
            # suffix doesn't match. Same idea for OS-level junk
            # (``.DS_Store`` on macOS, ``Thumbs.db`` on Windows) and
            # any dotfile. None of these belong in the published bundle.
            rel = fp.relative_to(self.source_dir)
            if any(part == "__pycache__" or part.startswith(".") for part in rel.parts):
                continue
            if fp.suffix.lower() in (".pyc", ".pyo"):
                continue
            if fp.name in ("Thumbs.db",):
                continue

            rel_path = fp.relative_to(self.source_dir)
            # Preserve relative structure; if there is only one segment, keep it
            rel_without_first = pathlib.Path(*rel_path.parts[1:]) if len(rel_path.parts) > 1 else rel_path
            build_file = self.build_dir / rel_path
            os.makedirs(build_file.parent, exist_ok=True)
            shutil.copy(fp, build_file)

            # Skip markdown and already under dist_dir
            if fp.suffix.lower() in (".md",):
                continue
            try:
                if self.dist_dir in fp.parents:
                    continue
            except Exception:
                pass

            dist_file = self.dist_dir / rel_without_first
            os.makedirs(dist_file.parent, exist_ok=True)
            shutil.copy(fp, dist_file)

        self.metadata_file = self.source_dir / "metadata.yaml" if metadata_file is None else pathlib.Path(metadata_file)

        if not self.metadata_file.exists():
            with open(self.metadata_file, "w") as f:
                # Use correct pandoc-crossref metadata format
                # figureTitle and tableTitle are the proper settings for pandoc-crossref
                f.write("linkReferences: true\n")
                f.write("nameInLink: true\n")
                f.write('figureTitle: "Figure"\n')
                f.write('tableTitle: "Table"\n')
                f.write('figPrefix: "Figure"\n')  # Keep for backwards compatibility
                f.write('tblPrefix: "Table"\n')  # Keep for backwards compatibility
                if self.use_default_html_style is True:
                    f.write("stylesheet: style.css\n")
            css_style = self.source_dir / "style.css"
            if css_style.exists() is False:
                shutil.copy(MY_DEFAULT_HTML_CSS, css_style)

    def compile(
        self,
        output_name,
        auto_open=False,
        metadata_file=None,
        export_format: ExportFormats | str = ExportFormats.DOCX,
        send_to_frontend=False,
        update_docx_with_com=True,
        **kwargs,
    ) -> WordExporter | PdfExporter | None:
        """
        Compiles a report into the specified format and handles the resultant exported
        file accordingly. Depending on the export format, different specialized exporters
        are used, and variable substitutions are performed where necessary. The resulting
        file can then be optionally opened, sent to a frontend, or copied to a specific
        output directory.

        :param output_name: Name of the output file without the file extension.
        :type output_name: str
        :param auto_open: Whether to automatically open the compiled document after export.
        :type auto_open: bool, optional
        :param metadata_file: Path to an optional metadata file to be used for compilation.
        :type metadata_file: str, optional
        :param export_format: The format in which to export the report.
        :type export_format: ExportFormats | str
        :param send_to_frontend: Whether to send the exported HTML document to a frontend service.
            Applicable only when export_format is HTML.
        :type send_to_frontend: bool, optional
        :param update_docx_with_com: Specifies whether to perform certain DOCX updates using COM.
            Applicable only for DOCX export.
        :type update_docx_with_com: bool, optional
        :param kwargs: Additional keyword arguments used specifically by certain exporters
            or configurations such as custom DOCX compilation or navbar inclusion in HTML.
        :type kwargs: dict, optional
        :return: None
        :rtype: NoneType
        """

        if isinstance(export_format, str):
            export_format = ExportFormats(export_format)

        dest_file = (self.dist_dir / output_name).with_suffix(f".{export_format.value}").resolve().absolute()

        logger.info(f'Compiling OneDoc report to "{dest_file}"')
        self._prep_compilation(metadata_file=metadata_file)
        self._perform_variable_substitution()
        self._write_bundle_artifacts(doc_id=output_name)
        converter = None
        if export_format == ExportFormats.DOCX:
            import platform

            # No longer need to inject table names into cells - using bookmark-based identification
            wordx = self.get_docx(**kwargs)
            wordx.export(output_name, dest_file, check_open_docs=auto_open)

            if update_docx_with_com and platform.system() == "Windows":
                from paradoc.io.word.com_api.com_utils import docx_update

                docx_update(dest_file)
            converter = wordx
        elif export_format == ExportFormats.PDF:
            from paradoc.io.pdf.exporter import PdfExporter

            latex_path = shutil.which("latex")
            if latex_path is None:
                latex_url = "https://www.latex-project.org/get/"
                raise LatexNotInstalled(
                    "Latex was not installed on your system. "
                    f'Please install latex before exporting to pdf. See "{latex_url}" for installation packages'
                )
            pdf = PdfExporter(self)
            pdf.export(dest_file)
            converter = pdf
        elif export_format == ExportFormats.HTML:
            from paradoc.io.html.exporter import HTMLExporter

            html = HTMLExporter(self)
            html.export(dest_file, include_navbar=kwargs.get("include_navbar", True))
        else:
            raise NotImplementedError(f'Export format "{export_format}" is not yet supported')

        if self.output_dir is not None:
            logger.info(f'Copying outputted document from "{dest_file}" to "{self.output_dir}"')
            shutil.copy(dest_file, self.output_dir)

        if auto_open is True:
            os.startfile(dest_file)

        return converter

    def add_table(self, name, df: pd.DataFrame, caption: str, tbl_format: TableFormat = TableFormat(), **kwargs):
        if '"' in caption:
            raise ValueError('Using characters such as " currently breaks the caption search in the docs compiler')
        self._uniqueness_check(name)
        self.tables[name] = Table(name, df, caption, tbl_format, **kwargs)

    def add_equation(self, name, func: Callable, custom_eq_str_compiler=None, **kwargs):
        self._uniqueness_check(name)
        self.equations[name] = Equation(name, func, custom_eq_str_compiler=custom_eq_str_compiler, **kwargs)

    def _get_table_markdown_from_db(self, full_reference: str, key_clean: str):
        """
        Generate markdown table from database using annotations.

        Args:
            full_reference: Full markdown reference including annotations (e.g., {{__my_table__}}{tbl:index:no})
            key_clean: Clean table key (without __ markers)

        Returns:
            Markdown table string or None if not found in database
        """
        # Check if table exists in database
        table_data = self.db_manager.get_table(key_clean)
        if table_data is None:
            return None

        # Parse annotation from full reference if present
        annotation = None
        try:
            _, annotation = parse_table_reference(full_reference)
        except (ValueError, AttributeError):
            pass

        # Convert to DataFrame
        df = table_data_to_dataframe(table_data)

        # Apply annotation transformations (sorting, filtering)
        show_index = table_data.show_index_default
        if annotation:
            df, show_index = apply_table_annotation(df, annotation, table_data.show_index_default)

        # Generate unique key for this table instance
        # Track usage count and append numeric suffix for reused tables
        if key_clean not in self._table_key_usage_count:
            self._table_key_usage_count[key_clean] = 0
            unique_key = key_clean
        else:
            self._table_key_usage_count[key_clean] += 1
            unique_key = f"{key_clean}_{self._table_key_usage_count[key_clean]}"

        # NOTE: We no longer need to inject the table name into the first cell
        # Table identification now uses the bookmark/hyperlink anchor system from pandoc-crossref
        # This eliminates data corruption and makes the system more robust

        # Convert to markdown
        props = dict(index=show_index, tablefmt="grid")
        tbl_str = df.to_markdown(**props)

        # Add caption unless nocaption flag is set
        # NOTE: Do NOT include the annotation in the caption - it's only for transformation
        if not (annotation and annotation.no_caption):
            tbl_str += f"\n\nTable: {table_data.caption}"
            tbl_str += f" {{#tbl:{unique_key}}}"

        # Create and store Table object for DOCX export compatibility
        # Store with unique_key (including usage count suffix) to handle multiple instances
        table_obj = Table(name=unique_key, df=df, caption=table_data.caption, link_name_override=unique_key)
        self.tables[unique_key] = table_obj

        return tbl_str

    def _get_plot_markdown_from_db(self, full_reference: str, key_clean: str, mdf) -> str:
        """
        Generate markdown image from database plot using annotations.
        Uses timestamp-based caching to avoid re-rendering unchanged plots.

        Args:
            full_reference: Full markdown reference including annotations (e.g., {{__my_plot__}}{plt:width:800})
            key_clean: Clean plot key (without __ markers)
            mdf: MarkDownFile instance for path context

        Returns:
            Markdown image string or empty string if not found in database
        """

        # Get plot data with timestamp for cache validation
        result = self.db_manager.get_plot_with_timestamp(key_clean)
        if result is None:
            return ""

        plot_data, db_timestamp = result

        # Parse annotation from full reference if present
        annotation = None
        try:
            _, annotation = parse_plot_reference(full_reference)
            if annotation:
                logger.debug(
                    f"Parsed plot annotation for {key_clean}: width={annotation.width}, height={annotation.height}"
                )
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse plot annotation: {e}")

        # Generate unique key for this plot instance
        if key_clean not in self._plot_key_usage_count:
            self._plot_key_usage_count[key_clean] = 0
            unique_key = key_clean
        else:
            self._plot_key_usage_count[key_clean] += 1
            unique_key = f"{key_clean}_{self._plot_key_usage_count[key_clean]}"

        # Determine size for cache key
        width = annotation.width if annotation and annotation.width else plot_data.width or 800
        height = annotation.height if annotation and annotation.height else plot_data.height or 600

        # Cache directory for rendered plots
        cache_dir = self.work_dir / ".paradoc_cache" / "rendered_plots"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache files: PNG image + timestamp (using dimensions in key to handle different sizes)
        cache_key = f"{key_clean}_{width}x{height}"
        cache_png = cache_dir / f"{cache_key}.png"
        cache_timestamp = cache_dir / f"{cache_key}.timestamp"

        # Check if cache is valid
        cache_valid = False
        if cache_png.exists() and cache_timestamp.exists():
            try:
                cached_ts = float(cache_timestamp.read_text(encoding="utf-8").strip())
                if cached_ts >= db_timestamp:
                    cache_valid = True
                    logger.debug(f"Cache hit for plot {key_clean} ({width}x{height})")
            except Exception as e:
                logger.debug(f"Cache validation failed for {key_clean}: {e}")

        # Render plot if cache is invalid (shouldn't happen after parallel rendering)
        if not cache_valid:
            logger.debug(f"Rendering plot {key_clean} (cache miss or stale)")
            try:
                # Create Plotly figure
                fig = self.plot_renderer._create_figure(plot_data)

                # Apply size overrides from annotation or plot_data
                width = annotation.width if annotation and annotation.width else plot_data.width or 800
                height = annotation.height if annotation and annotation.height else plot_data.height or 600
                fig.update_layout(width=width, height=height)

                # Write to cache
                try:
                    fig.write_image(str(cache_png), format="png")
                except Exception:
                    from plotly.io._kaleido import get_chrome

                    get_chrome()
                    fig.write_image(str(cache_png), format="png")
                cache_timestamp.write_text(str(db_timestamp), encoding="utf-8")
                logger.info(f'Rendered and cached plot "{key_clean}"')
            except Exception as e:

                logger.error(f'Failed to render plot "{key_clean}": {e}')
                return f"[Error rendering plot: {key_clean}]"

        # Now copy cached PNG to output locations
        plot_filename = f"{unique_key}.png"

        # Get the relative path from markdown file to images subdirectory
        md_rel_path = mdf.build_file.relative_to(self.build_dir)
        md_parent_dir = self.build_dir / md_rel_path.parent

        # Create images directory next to the markdown file
        images_dir_build = md_parent_dir / "images"
        images_dir_build.mkdir(parents=True, exist_ok=True)
        plot_path = images_dir_build / plot_filename

        # Also save to dist dir for final output
        dist_md_parent = self.dist_dir / md_rel_path.parent
        images_dir_dist = dist_md_parent / "images"
        images_dir_dist.mkdir(parents=True, exist_ok=True)
        dist_plot_path = images_dir_dist / plot_filename

        # Copy from cache to output directories
        shutil.copy(cache_png, plot_path)
        shutil.copy(cache_png, dist_plot_path)

        # Build markdown reference with proper pandoc-crossref syntax
        caption = "" if (annotation and annotation.no_caption) else plot_data.caption
        fig_id = f"fig:{unique_key}"

        if caption and not (annotation and annotation.no_caption):
            img_markdown = f"![{caption}](images/{plot_filename}){{#{fig_id}}}"
        else:
            img_markdown = f"![](images/{plot_filename}){{#{fig_id}}}"

        # Add plot-based figure to figures dictionary for DOCX export
        # This ensures format_figures() can find database-generated plots
        if caption:
            from paradoc.common import Figure

            file_path_str = f"images/{plot_filename}"
            self.figures[caption] = Figure(
                name=unique_key, caption=caption, reference=fig_id, file_path=file_path_str, md_instance=mdf
            )

        return img_markdown

    def _collect_and_render_plots_parallel(self, max_workers: Optional[int] = None):
        """
        Collect all plots that need rendering and render them using batch write_images.

        This pre-renders plots before variable substitution using plotly.io.write_images
        which batches the processing and is much faster than rendering one at a time.

        Args:
            max_workers: Unused parameter kept for API compatibility
        """
        logger.info("Collecting plots for batch rendering")

        # Lists to collect plot data for batch rendering
        plots_to_render = (
            []
        )  # List of (cache_key, plot_data, width, height, cache_png, cache_timestamp, db_timestamp, key_clean)

        # Cache directory for rendered plots
        cache_dir = self.work_dir / ".paradoc_cache" / "rendered_plots"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Scan all markdown files to find plot references. Use the desugared
        # cache when available so `${...}` plot refs are picked up too.
        cache = getattr(self, "_desugared_md_cache", {})
        for mdf in self.md_files_main + self.md_files_app:
            md_str = cache.get(mdf.path) or mdf.read_original_file()

            for m in mdf.get_variables():
                res = m.group(1)
                key = res.split("|")[0] if "|" in res else res
                key_clean = key[2:-2] if key.startswith("__") and key.endswith("__") else key

                # Only process database plot keys (keys with __ markers)
                if not (key.startswith("__") and key.endswith("__")):
                    continue

                # Get full reference including any annotation that follows
                full_reference = m.group(0)
                match_end = m.end()
                remaining_str = md_str[match_end:]

                # Check if there's a {plt:...} annotation following
                if remaining_str.startswith("{plt:"):
                    brace_depth = 0
                    annotation_end = 0
                    for i, char in enumerate(remaining_str):
                        if char == "{":
                            brace_depth += 1
                        elif char == "}":
                            brace_depth -= 1
                            if brace_depth == 0:
                                annotation_end = i + 1
                                break
                    if annotation_end > 0:
                        full_reference += remaining_str[:annotation_end]

                # Try to get plot data
                result = self.db_manager.get_plot_with_timestamp(key_clean)
                if result is None:
                    continue

                plot_data, db_timestamp = result

                # Parse annotation
                annotation = None
                try:
                    _, annotation = parse_plot_reference(full_reference)
                except (ValueError, AttributeError):
                    pass

                # Determine size
                width = annotation.width if annotation and annotation.width else plot_data.width or 800
                height = annotation.height if annotation and annotation.height else plot_data.height or 600

                # Use cache key that includes dimensions to handle different sizes
                cache_key = f"{key_clean}_{width}x{height}"
                cache_png = cache_dir / f"{cache_key}.png"
                cache_timestamp = cache_dir / f"{cache_key}.timestamp"

                cache_valid = False
                if cache_png.exists() and cache_timestamp.exists():
                    try:
                        cached_ts = float(cache_timestamp.read_text(encoding="utf-8").strip())
                        if cached_ts >= db_timestamp:
                            cache_valid = True
                    except Exception:
                        pass

                # Only render if cache is invalid and not already in list
                if not cache_valid and not any(p[0] == cache_key for p in plots_to_render):
                    plots_to_render.append(
                        (cache_key, plot_data, width, height, cache_png, cache_timestamp, db_timestamp, key_clean)
                    )

        if not plots_to_render:
            logger.info("No plots need rendering (all cached)")
            return

        logger.info(f"Rendering {len(plots_to_render)} plots using batch write_images")

        # Prepare lists for batch rendering
        figures = []
        file_paths = []
        cache_keys = []
        timestamps_to_write = []

        for cache_key, plot_data, width, height, cache_png, cache_timestamp, db_timestamp, key_clean in plots_to_render:
            try:
                # Create figure
                fig = self.plot_renderer._create_figure(plot_data)

                # Apply size
                fig.update_layout(width=width, height=height)

                # Add to batch lists
                figures.append(fig)
                file_paths.append(str(cache_png))
                cache_keys.append(cache_key)
                timestamps_to_write.append((cache_timestamp, db_timestamp))

            except Exception as e:
                logger.error(f'Failed to create figure for plot "{key_clean}": {e}')
                continue

        if not figures:
            logger.warning("No figures could be created for batch rendering")
            return

        # Batch render all plots using write_images
        try:
            import plotly.io as pio

            # Initialize kaleido once before batch processing
            try:
                pio.write_images(fig=figures, file=file_paths, format="png")
            except Exception:
                # Fallback to ensure chrome is initialized
                from plotly.io._kaleido import get_chrome

                get_chrome()
                pio.write_images(fig=figures, file=file_paths, format="png")

            # Write timestamp files after successful batch rendering
            for i, (cache_timestamp, db_timestamp) in enumerate(timestamps_to_write):
                try:
                    cache_timestamp.write_text(str(db_timestamp), encoding="utf-8")
                    logger.info(f'Rendered and cached plot "{cache_keys[i]}"')
                except Exception as e:
                    logger.error(f'Failed to write timestamp for "{cache_keys[i]}": {e}')

        except Exception as e:
            logger.error(f"Batch rendering failed: {e}")
            # Fall back to individual rendering if batch fails
            logger.info("Falling back to individual plot rendering")
            for i, fig in enumerate(figures):
                try:
                    fig.write_image(file_paths[i], format="png")
                    cache_timestamp, db_timestamp = timestamps_to_write[i]
                    cache_timestamp.write_text(str(db_timestamp), encoding="utf-8")
                    logger.info(f'Rendered and cached plot "{cache_keys[i]}"')
                except Exception as e_individual:
                    logger.error(f'Failed to render plot "{cache_keys[i]}": {e_individual}')

    def _perform_variable_substitution(self):
        """Perform variable substitution in markdown files.

        Runs in two passes:
          1) Desugar `${...}` references to the legacy `{{__key__}}{plt|tbl:...}`
             form (or substitute scalars directly). The result is cached per
             markdown file so the plot-prerender scan and the main substitution
             loop see the same desugared content.
          2) Run the legacy `{{...}}` parser (table/plot/equation/variable),
             emitting a deprecation warning whenever a legacy `{{__key__}}`
             match is encountered.
        """
        logger.info("Performing variable substitution")

        # Reset table and plot key usage counters for each compilation
        self._table_key_usage_count.clear()
        self._plot_key_usage_count.clear()

        # Discover filter instances from <source_dir>/filters.py once per build.
        self._discover_filters_once()

        # Reset per-build figure-source key counters.
        self._fig_source_key_counter: Dict[str, int] = {}

        # Phase 1: desugar ${...} → legacy form (in-memory, never written to disk).
        # Keep the original (pre-desugar, pre-figure-source) text per file too;
        # the legacy `{{__key__}}` deprecation warning checks against the
        # original so paradoc's own desugar output doesn't trigger false
        # positives.
        self._desugared_md_cache = {}
        self._pre_desugar_md_cache = {}
        for mdf in self.md_files_main + self.md_files_app:
            original = mdf.read_original_file()
            self._pre_desugar_md_cache[mdf.path] = original
            after_figsrc = self._preprocess_figure_sources(original, mdf)
            self._desugared_md_cache[mdf.path] = self._desugar_new_syntax(after_figsrc, mdf)

        # Pre-render all plots in parallel before substitution
        self._collect_and_render_plots_parallel()

        for mdf in self.md_files_main + self.md_files_app:
            md_file = mdf.path
            os.makedirs(mdf.new_file.parent, exist_ok=True)
            md_str = self._desugared_md_cache[mdf.path]
            md_str_original = md_str

            import re as _re
            _legacy_re = _re.compile(r"{{(.*)}}")
            # Same code-span guard as paradoc.substitution.parser: a
            # `{{__key__}}` inside backticks is doc-of-the-syntax, not a
            # reference to substitute.
            from paradoc.substitution.parser import _CODE_FENCE_RE, _CODE_SPAN_RE
            _masked = [m.span() for m in _CODE_FENCE_RE.finditer(md_str_original)]
            _masked += [m.span() for m in _CODE_SPAN_RE.finditer(md_str_original)]

            def _in_code(start: int, end: int) -> bool:
                return any(s <= start and end <= e for s, e in _masked)

            for m in _legacy_re.finditer(md_str_original):
                if _in_code(*m.span()):
                    continue
                res = m.group(1)
                key = res.split("|")[0] if "|" in res else res
                list_of_flags = res.split("|")[1:] if "|" in res else None
                key_clean = key[2:-2] if key.startswith("__") and key.endswith("__") else key

                # Check database first for table/plot keys (keys with __ markers)
                if key.startswith("__") and key.endswith("__"):
                    # Skip the deprecation warning when the legacy match was
                    # produced by our own ${...} → {{__key__}} desugar pass
                    # rather than the user's source. We test by substring
                    # against the pre-desugar text.
                    raw_match = m.group(0)
                    pre = self._pre_desugar_md_cache.get(mdf.path, "")
                    if raw_match in pre:
                        self._warn_legacy_syntax(raw_match, md_str_original, mdf)
                    # Get full reference including any annotation that follows
                    full_reference = m.group(0)

                    # Look ahead in the string to find annotation pattern
                    match_end = m.end()
                    remaining_str = md_str_original[match_end:]

                    # Check if there's a {tbl:...} or {plt:...} annotation following
                    if remaining_str.startswith("{tbl:") or remaining_str.startswith("{plt:"):
                        # Find the matching closing brace by counting brace depth
                        brace_depth = 0
                        annotation_end = 0
                        for i, char in enumerate(remaining_str):
                            if char == "{":
                                brace_depth += 1
                            elif char == "}":
                                brace_depth -= 1
                                if brace_depth == 0:
                                    annotation_end = i + 1
                                    break

                        if annotation_end > 0:
                            full_reference += remaining_str[:annotation_end]

                    # Try table substitution first
                    db_table_markdown = self._get_table_markdown_from_db(full_reference, key_clean)
                    if db_table_markdown is not None:
                        logger.info(f'Substituting table "{key_clean}" from database')
                        new_str = db_table_markdown
                        # Replace both the variable and annotation if present
                        replacement_str = full_reference
                        md_str = md_str.replace(replacement_str, new_str, 1)
                        continue

                    # Try plot substitution
                    db_plot_markdown = self._get_plot_markdown_from_db(full_reference, key_clean, mdf)
                    if db_plot_markdown != "":
                        logger.info(f'Substituting plot "{key_clean}" from database')
                        new_str = db_plot_markdown
                        # Replace both the variable and annotation if present
                        replacement_str = full_reference
                        md_str = md_str.replace(replacement_str, new_str, 1)
                        continue

                # Fall back to in-memory dictionaries
                tbl = self.tables.get(key_clean, None)
                eq = self.equations.get(key_clean, None)
                variables = self.variables.get(key_clean, None)

                if tbl is not None:
                    tbl.md_instances.append(mdf)
                    # No longer need to pass use_table_var_substitution - using bookmark-based identification
                    new_str = tbl.to_markdown(include_name_in_cell=False, flags=list_of_flags)
                elif eq is not None:
                    eq.md_instances.append(mdf)
                    new_str = eq.to_latex()
                elif variables is not None:
                    new_str = str(variables)
                else:
                    logger.error(f'key "{key_clean}" located in {md_file} has not been substituted')
                    new_str = m.group(0)

                md_str = md_str.replace(m.group(0), new_str)

            with open(mdf.build_file, "w", encoding="utf-8") as f:
                f.write(md_str)

    def _desugar_new_syntax(self, md_str: str, mdf: MarkDownFile) -> str:
        """Translate `${...}` substitutions to legacy `{{...}}` form.

        Probes db tables, db plots, in-memory tables, equations, and variables
        in that order. Scalar variables with a `:fmt` spec are substituted
        directly (with format applied). Substitutions whose name resolves to
        nothing are left as-is so the legacy linter can surface them.

        This is a Phase 1 bridge: Phase 2 replaces it with a filter-aware
        resolver that handles `name.attr(args)` natively.
        """
        from paradoc.substitution import find_substitutions

        out: list[str] = []
        last = 0
        for sub in find_substitutions(md_str):
            out.append(md_str[last:sub.span[0]])
            replacement = self._desugar_one_substitution(sub, mdf)
            if replacement is None:
                logger.warning(
                    f'Unresolved substitution ${{ {sub.reference} }} in {mdf.path}'
                )
                out.append(sub.raw)
            else:
                out.append(replacement)
            last = sub.span[1]
        out.append(md_str[last:])
        return "".join(out)

    def _desugar_one_substitution(self, sub, mdf: MarkDownFile) -> Optional[str]:
        from paradoc.substitution import SubstitutionError, apply_fmtspec

        # Filter-attribute call: ${ name.attr(args) }
        if sub.attr is not None:
            return self._resolve_filter_call(sub, mdf)

        name = sub.name

        if self.db_manager.get_table(name) is not None:
            anno = _kwargs_to_table_anno_str(sub.kwargs)
            return f"{{{{__{name}__}}}}{anno}"

        if self.db_manager.get_plot(name) is not None:
            anno = _kwargs_to_plot_anno_str(sub.kwargs)
            return f"{{{{__{name}__}}}}{anno}"

        if name in self.tables:
            return f"{{{{__{name}__}}}}"

        if name in self.equations:
            return f"{{{{__{name}__}}}}"

        if name in self.variables:
            value = self.variables[name]
            try:
                return apply_fmtspec(value, sub.fmtspec)
            except SubstitutionError as exc:
                logger.error(f'{exc} for ${{ {name} }} in {mdf.path}')
                return None

        return None

    def _preprocess_figure_sources(self, md_text: str, mdf: MarkDownFile) -> str:
        """Replace `<!-- paradoc:figure ... -->` blocks with image references.

        Each block runs its registered filter, which writes a glb + PNG to
        the bundle and returns the metadata. We register a `ThreeDData` row
        and rewrite the block as `![title](png){#fig:KEY data-3d-key=KEY}`.
        """
        from paradoc.db.models import ThreeDData
        from paradoc.figure_sources.filters import get_filter_for
        from paradoc.figure_sources.filters.base import RenderResult
        from paradoc.figure_sources.preprocessor import preprocess_markdown

        bundle_root = self.build_dir
        md_dir = mdf.build_file.parent

        def _render_block(spec) -> str:
            key = self._allocate_figure_source_key(spec.figure_source)
            try:
                filter_cls = get_filter_for(spec.figure_source)
                filter_inst = filter_cls(bundle_root=bundle_root)
                raw = filter_inst.render(spec, key=key)
            except Exception as exc:
                logger.error(f'figure-source filter failed for key {key!r}: {exc}')
                return f"<!-- paradoc:figure ERROR: {exc} -->"

            # Multi-figure filters (FEA artefact-bundle's `per_mode`
            # layout, future history-output series) return a list of
            # RenderResults. Normalise to a list so single-figure
            # filters keep working through the same code path. One
            # markdown image tag + one ThreeDData row per result;
            # derived keys preserve uniqueness in the asset store.
            if isinstance(raw, RenderResult):
                results = [raw]
            else:
                results = list(raw)
            if not results:
                logger.warning(
                    f'figure-source filter for key {key!r} returned no results'
                )
                return f"<!-- paradoc:figure {key} produced no results -->"

            markdown_parts: list[str] = []
            for i, result in enumerate(results):
                # First row keeps the allocated key (back-compat with
                # single-figure flows + matches the key the static
                # export uses for the canonical figure); subsequent
                # rows get the `_2`, `_3` suffix the FEA bake convention
                # already produces for mode-view ThreeDData rows.
                sub_key = key if i == 0 else f"{key}_{i + 1}"
                self.db_manager.add_three_d(
                    ThreeDData(
                        key=sub_key,
                        glb_path=result.glb_path,
                        format="glb",
                        camera_pos=result.camera_pos,
                        caption=result.caption,
                        sha256=result.glb_sha256,
                        size=result.glb_size,
                        source_type=result.source_type,
                        metadata=result.metadata,
                    )
                )

                # Compute the relative path from the markdown file to
                # the PNG so pandoc resolves it correctly for both
                # Word/PDF and HTML.
                png_full = bundle_root / result.png_path
                try:
                    rel_png = os.path.relpath(png_full, md_dir)
                except ValueError:
                    rel_png = result.png_path
                # Forward slashes for portability (pandoc + S3).
                rel_png = rel_png.replace(os.sep, "/")
                fig_id = f"fig:{sub_key}"
                markdown_parts.append(
                    f"![{result.caption}]({rel_png})"
                    f"{{#{fig_id} data-3d-key={sub_key}}}"
                )

            return "\n\n".join(markdown_parts)

        return preprocess_markdown(md_text, render_block=_render_block)

    def _allocate_figure_source_key(self, source_type: str) -> str:
        """Assign a unique key per (source_type, occurrence) within a build."""
        idx = self._fig_source_key_counter.get(source_type, 0) + 1
        self._fig_source_key_counter[source_type] = idx
        return f"{source_type}_{idx}"

    def _write_bundle_artifacts(self, *, doc_id: str) -> None:
        """Write `manifest.json`, `presets.json`, and `paradoc.sqlite` into the bundle.

        Together with the figure-source assets already written under
        `assets/3d/`, this leaves `<build_dir>/` as a portable, S3-uploadable
        directory tree that the future REST DocStore can serve as-is.

        Also populates `<build_dir>/static/` with the REST-servable
        JSON form (manifest, sections, plots, tables, images). Without
        this, `paradoc-serve`'s `LocalDocStore._read_static` 404s every
        section request because it reads from `<bundle>/static/` —
        the same layout `S3DocStore` expects in object storage.
        """
        from paradoc.camera.presets import export_presets_json, load_camera_presets
        from paradoc.docstore import write_manifest

        bundle_root = self.build_dir
        bundle_root.mkdir(parents=True, exist_ok=True)

        try:
            # source_dir is the project repo's source root — git provenance
            # extracted from there reflects the project that produced the
            # doc, not paradoc itself.
            write_manifest(bundle_root, doc_id=doc_id, repo_root=self.source_dir)
        except Exception as exc:
            logger.error(f"failed to write manifest.json: {exc}")

        try:
            paradoc_toml = self.source_dir / "paradoc.toml"
            presets = load_camera_presets(paradoc_toml if paradoc_toml.exists() else None)
            export_presets_json(presets, bundle_root / "assets" / "presets.json")
        except Exception as exc:
            logger.error(f"failed to write presets.json: {exc}")

        try:
            db_src = self.db_manager.db_path
            db_dst = bundle_root / "paradoc.sqlite"
            if db_src.exists():
                shutil.copy(db_src, db_dst)
        except Exception as exc:
            logger.error(f"failed to copy paradoc.sqlite into bundle: {exc}")

        # REST-servable JSON layout. `include_frontend=False` because
        # the SPA shell is served by the host (paradoc-serve's
        # StaticFiles, nginx, ...), not from `<bundle>/static/`.
        try:
            ast_exporter = self.get_ast()
            ast_exporter.export_to_static_files(
                bundle_root / "static",
                include_frontend=False,
            )
        except Exception as exc:
            logger.error(f"failed to populate <bundle>/static/: {exc}")

        # Drop the static export's binary mirror of ``assets/`` —
        # ``_export_three_d_assets_for_static`` copies every GLB +
        # poster + FEA artefact under ``<output>/assets/3d/`` because
        # standalone static bundles (no server) need them right there.
        # In the REST layout the binaries already live at
        # ``<bundle>/assets/3d/`` and the REST docstore resolves them
        # from there (``DbManager.glb_path`` is bundle-relative).
        # Keeping the mirror would 2x the S3 footprint and clutter
        # ``/api/docs/{id}/manifest/files`` with phantom duplicates.
        # The JSON manifests under ``static/`` (sections / plots /
        # tables / images / manifest.json) are kept — those ARE what
        # the REST server reads.
        try:
            static_assets = bundle_root / "static" / "assets"
            if static_assets.exists():
                shutil.rmtree(static_assets)
        except Exception as exc:
            logger.warning(f"failed to scrub <bundle>/static/assets/: {exc}")

    def _discover_filters_once(self) -> None:
        if self._filters_discovered:
            return
        from paradoc.filters import discover_filters

        try:
            discover_filters(doc_root=self.source_dir, registry=self._filter_registry)
        except Exception as exc:  # discovery failure should not crash the build
            logger.error(f"filter discovery failed: {exc}")
        self._filters_discovered = True

    def _resolve_filter_call(self, sub, mdf: MarkDownFile) -> Optional[str]:
        """Run a `${ name.attr(args) }` reference through the filter registry."""
        instance = self._filter_registry.get(sub.name)
        if instance is None:
            return None  # unresolved → linter

        try:
            result = self._filter_registry.call_attr(sub.name, sub.attr, sub.kwargs)
        except (KeyError, TypeError) as exc:
            logger.error(
                f'Failed to resolve ${{ {sub.reference} }} in {mdf.path}: {exc}'
            )
            return None

        return self._render_view(result, sub, mdf)

    def _render_view(self, result, sub, mdf: MarkDownFile) -> Optional[str]:
        """Translate a filter `@attr` return value into markdown.

        TableView / FigureView / ThreeDView desugar to legacy markdown forms;
        scalars are formatted with the substitution's fmtspec.
        """
        from paradoc.filters import FigureView, ScalarValue, TableView, ThreeDView
        from paradoc.substitution import SubstitutionError, apply_fmtspec

        if isinstance(result, TableView):
            anno = _kwargs_to_table_anno_str(result.display_kwargs)
            return f"{{{{__{result.table_key}__}}}}{anno}"

        if isinstance(result, FigureView):
            if result.plot_key is not None:
                anno = _kwargs_to_plot_anno_str(result.display_kwargs)
                return f"{{{{__{result.plot_key}__}}}}{anno}"
            if result.image_path is not None:
                fig_id = result.figure_id or f"fig:{sub.name}_{sub.attr}"
                cap = result.caption
                return f"![{cap}]({result.image_path}){{#{fig_id}}}"
            logger.error(
                f'FigureView from ${{ {sub.reference} }} has neither plot_key nor image_path'
            )
            return None

        if isinstance(result, ThreeDView):
            # Phase 4 wires the 3D pipeline; for Phase 2 we emit a static-figure
            # markdown line with a `data-3d-key` attribute that the frontend
            # will pick up once Phase 6 lands.
            fig_id = result.figure_id or f"fig:{sub.name}_{sub.attr}"
            cap = result.caption
            img_path = result.image_path or "MISSING_3D_IMAGE.png"
            return f"![{cap}]({img_path}){{#{fig_id} data-3d-key={result.glb_key}}}"

        if isinstance(result, ScalarValue):
            try:
                return apply_fmtspec(result.value, sub.fmtspec)
            except SubstitutionError as exc:
                logger.error(f'{exc} for ${{ {sub.reference} }} in {mdf.path}')
                return None

        # Plain scalar return
        try:
            return apply_fmtspec(result, sub.fmtspec)
        except SubstitutionError as exc:
            logger.error(f'{exc} for ${{ {sub.reference} }} in {mdf.path}')
            return None

    def _warn_legacy_syntax(self, raw_match: str, full_md: str, mdf: MarkDownFile) -> None:
        """Emit a deprecation warning for legacy `{{__key__}}` references.

        We only warn once per unique legacy match per file, to keep the build
        log readable on docs with hundreds of references.
        """
        if not hasattr(self, "_warned_legacy"):
            self._warned_legacy = set()
        warn_key = (mdf.path, raw_match)
        if warn_key in self._warned_legacy:
            return
        self._warned_legacy.add(warn_key)

        # Determine if there's a trailing annotation so we can suggest a precise replacement
        idx = full_md.find(raw_match)
        suggestion = raw_match
        if idx >= 0:
            after = full_md[idx + len(raw_match):]
            if after.startswith("{tbl:") or after.startswith("{plt:"):
                close = _find_matching_brace(after, 0)
                if close != -1:
                    suggestion = raw_match + after[: close + 1]

        from paradoc.substitution.migrator import migrate_text

        new_form, _, _ = migrate_text(suggestion)
        logger.warning(
            f'Deprecated legacy substitution {suggestion!r} in {mdf.path}; '
            f'replace with {new_form!r}. Run `paradoc-migrate-syntax` to '
            f'rewrite all legacy syntax in this doc tree.'
        )

    def _uniqueness_check(self, name):
        error_msg = 'Table name "{name}" must be unique. This name is already used by {cont_type}="{container}"'

        tbl = self.tables.get(name, None)
        if tbl is not None:
            raise ValueError(error_msg.format(name=name, cont_type="Table", container=tbl))
        eq = self.equations.get(name, None)
        if eq is not None:
            raise ValueError(error_msg.format(name=name, cont_type="Equation", container=eq))
        v = self.variables.get(name, None)
        if v is not None:
            raise ValueError(error_msg.format(name=name, cont_type="Variable", container=v))

    @property
    def main_dir(self):
        return self.source_dir / self._main_prefix

    @property
    def app_dir(self):
        return self.source_dir / self._app_prefix

    @property
    def build_dir(self):
        return self.work_dir / "_build"

    @property
    def dist_dir(self):
        return self.work_dir / "_dist"

    @property
    def output_dir(self):
        return self._output_dir
