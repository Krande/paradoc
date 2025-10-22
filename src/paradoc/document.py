from __future__ import annotations

import os
import pathlib
import shutil
from itertools import chain
from typing import Callable, Dict, Iterable

import pandas as pd

from .common import (
    MY_DEFAULT_HTML_CSS,
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
from .utils import get_list_of_files


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
        work_dir="temp",
        use_default_html_style=True,
        **kwargs,
    ):
        self.source_dir = pathlib.Path().resolve().absolute() if source_dir is None else pathlib.Path(source_dir)
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

        # Initialize database manager at source_dir/data.db
        db_path = self.source_dir / "data.db"
        self.db_manager = DbManager(db_path)

        # Initialize plot renderer with caching
        cache_dir = self.work_dir / ".paradoc_cache"
        self.plot_renderer = PlotRenderer(cache_dir=cache_dir)

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

    def send_to_frontend(self, metadata_file=None, embed_images=True, use_static_html=False, frontend_id=None):
        """
        Send document to Paradoc frontend reader via WebSocket.

        Args:
            metadata_file: Optional metadata file path
            embed_images: If True, embed images as base64 in WebSocket messages
            use_static_html: If True, extract frontend.zip and open in browser
            frontend_id: Optional frontend ID to target specific frontend instance. If None, sends to all connected frontends.
        """
        from paradoc.io.ast.exporter import ASTExporter

        shutil.rmtree(self.dist_dir, ignore_errors=True)
        self._prep_compilation(metadata_file=metadata_file)
        # Set frontend export flag before variable substitution
        self._perform_variable_substitution(False)
        html = ASTExporter(self)
        html.send_to_frontend(embed_images=embed_images, use_static_html=use_static_html, frontend_id=frontend_id)

    def _prep_compilation(self, metadata_file=None):
        self.build_dir.mkdir(exist_ok=True, parents=True)
        self.dist_dir.mkdir(exist_ok=True, parents=True)

        # Move/copy all non-markdown assets into build and dist so Pandoc and the HTTP server can resolve them
        src_root = pathlib.Path(self.source_dir)
        for fp in src_root.rglob("*"):
            fp = pathlib.Path(fp)
            if not fp.is_file():
                continue
            # Skip markdown/metadata and anything already under dist_dir
            if fp.suffix.lower() in (".md", ".yaml"):
                continue
            try:
                if self.dist_dir in fp.parents:
                    continue
            except Exception:
                pass
            rel_path = fp.relative_to(self.source_dir)
            # Preserve relative structure; if there is only one segment, keep it
            rel_without_first = pathlib.Path(*rel_path.parts[1:]) if len(rel_path.parts) > 1 else rel_path
            build_file = self.build_dir / rel_path
            dist_file = self.dist_dir / rel_without_first
            os.makedirs(build_file.parent, exist_ok=True)
            os.makedirs(dist_file.parent, exist_ok=True)
            shutil.copy(fp, build_file)
            shutil.copy(fp, dist_file)

        self.metadata_file = self.source_dir / "metadata.yaml" if metadata_file is None else pathlib.Path(metadata_file)

        if self.metadata_file.exists() is False:
            with open(self.metadata_file, "w") as f:
                f.write('linkReferences: true\nnameInLink: true\nfigPrefix: "Figure"\ntblPrefix: "Table"')
                if self.use_default_html_style is True:
                    f.write("\nstylesheet: style.css")
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
        **kwargs,
    ):
        if isinstance(export_format, str):
            export_format = ExportFormats(export_format)

        dest_file = (self.dist_dir / output_name).with_suffix(f".{export_format.value}").resolve().absolute()

        print(f'Compiling OneDoc report to "{dest_file}"')
        self._prep_compilation(metadata_file=metadata_file)

        if export_format == ExportFormats.DOCX:
            from paradoc.io.word.exporter import WordExporter

            use_custom_compile = kwargs.get("use_custom_docx_compile", True)
            if use_custom_compile is False:
                use_table_name_in_cell_as_index = False
            else:
                use_table_name_in_cell_as_index = True

            self._perform_variable_substitution(use_table_name_in_cell_as_index)
            check_open_docs = auto_open is True
            wordx = WordExporter(self, **kwargs)
            wordx.export(output_name, dest_file, check_open_docs=check_open_docs)
        elif export_format == ExportFormats.PDF:
            from paradoc.io.pdf.exporter import PdfExporter

            latex_path = shutil.which("latex")
            if latex_path is None:
                latex_url = "https://www.latex-project.org/get/"
                raise LatexNotInstalled(
                    "Latex was not installed on your system. "
                    f'Please install latex before exporting to pdf. See "{latex_url}" for installation packages'
                )
            self._perform_variable_substitution(False)
            pdf = PdfExporter(self)
            pdf.export(dest_file)
        elif export_format == ExportFormats.HTML:
            from paradoc.io.html.exporter import HTMLExporter

            self._perform_variable_substitution(False)
            html = HTMLExporter(self)
            html.export(dest_file, include_navbar=kwargs.get("include_navbar", True))
            if send_to_frontend:
                html.send_to_frontend()
        else:
            raise NotImplementedError(f'Export format "{export_format}" is not yet supported')

        if self.output_dir is not None:
            print(f'Copying outputted document from "{dest_file}" to "{self.output_dir}"')
            shutil.copy(dest_file, self.output_dir)

        if auto_open is True:
            os.startfile(dest_file)

    def add_table(self, name, df: pd.DataFrame, caption: str, tbl_format: TableFormat = TableFormat(), **kwargs):
        if '"' in caption:
            raise ValueError('Using characters such as " currently breaks the caption search in the docs compiler')
        self._uniqueness_check(name)
        self.tables[name] = Table(name, df, caption, tbl_format, **kwargs)

    def add_equation(self, name, func: Callable, custom_eq_str_compiler=None, **kwargs):
        self._uniqueness_check(name)
        self.equations[name] = Equation(name, func, custom_eq_str_compiler=custom_eq_str_compiler, **kwargs)

    def _get_table_markdown_from_db(self, full_reference: str, key_clean: str, use_table_var_substitution: bool):
        """
        Generate markdown table from database using annotations.

        Args:
            full_reference: Full markdown reference including annotations (e.g., {{__my_table__}}{tbl:index:no})
            key_clean: Clean table key (without __ markers)
            use_table_var_substitution: Whether to include table name in first cell

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

        # Handle table name in first cell for DOCX compatibility
        # IMPORTANT: The name in the cell must match the key in self.tables dictionary
        # For DOCX export, we use unique_key in the cell so each instance can be looked up
        if use_table_var_substitution:
            df = df.copy()
            if show_index:
                # When index is shown, put the table name as the first index value
                # Create a new index with the table name as the first element
                new_index = [unique_key] + list(df.index[1:])
                df.index = new_index
            else:
                # When index is hidden, put the table name in the first data cell
                col_name = df.columns[0]
                df[col_name] = df[col_name].astype(object)
                df.iat[0, 0] = unique_key

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
        table_obj = Table(
            name=unique_key,
            df=df,
            caption=table_data.caption,
            link_name_override=unique_key
        )
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

        # Cache directory for rendered plots
        cache_dir = self.work_dir / ".paradoc_cache" / "rendered_plots"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache files: PNG image + timestamp
        cache_png = cache_dir / f"{key_clean}.png"
        cache_timestamp = cache_dir / f"{key_clean}.timestamp"

        # Check if cache is valid
        cache_valid = False
        if cache_png.exists() and cache_timestamp.exists():
            try:
                cached_ts = float(cache_timestamp.read_text(encoding="utf-8").strip())
                if cached_ts >= db_timestamp:
                    cache_valid = True
                    logger.debug(f"Cache hit for plot {key_clean}")
            except Exception as e:
                logger.debug(f"Cache validation failed for {key_clean}: {e}")

        # Render plot if cache is invalid
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
                name=unique_key,
                caption=caption,
                reference=fig_id,
                file_path=file_path_str,
                md_instance=mdf
            )

        return img_markdown


    def _perform_variable_substitution(self, use_table_var_substitution):
        logger.info("Performing variable substitution")

        # Reset table and plot key usage counters for each compilation
        self._table_key_usage_count.clear()
        self._plot_key_usage_count.clear()

        for mdf in self.md_files_main + self.md_files_app:
            md_file = mdf.path
            os.makedirs(mdf.new_file.parent, exist_ok=True)
            md_str = mdf.read_original_file()
            md_str_original = md_str

            for m in mdf.get_variables():
                res = m.group(1)
                key = res.split("|")[0] if "|" in res else res
                list_of_flags = res.split("|")[1:] if "|" in res else None
                key_clean = key[2:-2] if key.startswith("__") and key.endswith("__") else key

                # Check database first for table/plot keys (keys with __ markers)
                if key.startswith("__") and key.endswith("__"):
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
                    db_table_markdown = self._get_table_markdown_from_db(
                        full_reference, key_clean, use_table_var_substitution
                    )
                    if db_table_markdown is not None:
                        logger.info(f'Substituting table "{key_clean}" from database')
                        new_str = db_table_markdown
                        # Replace both the variable and annotation if present
                        replacement_str = full_reference
                        md_str = md_str.replace(replacement_str, new_str, 1)
                        continue

                    # Try plot substitution
                    db_plot_markdown = self._get_plot_markdown_from_db(full_reference, key_clean, mdf)
                    if db_plot_markdown is not None:
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
                    new_str = tbl.to_markdown(use_table_var_substitution, list_of_flags)
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
