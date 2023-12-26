from __future__ import annotations

import os
import pathlib
import shutil
from typing import Callable, Dict

import pandas as pd

from paradoc.config import create_logger

from .common import (
    MY_DEFAULT_HTML_CSS,
    DocXFormat,
    ExportFormats,
    Figure,
    MarkDownFile,
    Table,
    TableFormat,
)
from .equations import Equation
from .exceptions import LatexNotInstalled
from .utils import get_list_of_files

logger = create_logger()


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
        **kwargs,
    ):
        self.source_dir = pathlib.Path().resolve().absolute() if source_dir is None else pathlib.Path(source_dir)
        self.work_dir = pathlib.Path(work_dir) if work_dir is not None else pathlib.Path("")
        self.work_dir = self.work_dir.resolve().absolute()

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
        self._use_default_html_style = use_default_html_style
        self._setup(create_dirs, app_prefix, clean_build_dir)

    def _setup(self, create_dirs, app_prefix, clean_build_dir):
        if create_dirs is True:
            os.makedirs(self.main_dir, exist_ok=True)
            os.makedirs(self.app_dir, exist_ok=True)

        for md_file_path in get_list_of_files(self.source_dir, ".md"):
            logger.info(f'Adding markdown file "{md_file_path}"')
            is_appendix = True if app_prefix in md_file_path else False
            md_file_path = pathlib.Path(md_file_path)
            rel_path = md_file_path.relative_to(self.source_dir)
            parents = list(rel_path.parents)
            top = str(parents[-2])
            if top == "temp":
                logger.info(f"file {md_file_path} located in `temp` dir is skipped")
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

        if clean_build_dir is True:
            shutil.rmtree(self.build_dir, ignore_errors=True)

    def compile(self, output_name, auto_open=False, metadata_file=None, export_format=ExportFormats.DOCX, **kwargs):
        dest_file = (self.dist_dir / output_name).with_suffix(f".{export_format.value}").resolve().absolute()

        print(f'Compiling OneDoc report to "{dest_file}"')
        os.makedirs(self.build_dir, exist_ok=True)
        os.makedirs(self.dist_dir, exist_ok=True)

        # Move all non-md files to temp dir because pandoc (tested on 2.19.2) struggles with external resource paths
        for f in get_list_of_files(self.source_dir):
            fp = pathlib.Path(f)
            rel_path = fp.relative_to(self.source_dir)
            if fp.suffix in (".md", ".yaml"):
                continue
            build_file = self.build_dir / rel_path
            dist_file = self.dist_dir / "/".join(rel_path.parts[1:])
            os.makedirs(build_file.parent, exist_ok=True)
            os.makedirs(dist_file.parent, exist_ok=True)
            shutil.copy(fp, build_file)
            shutil.copy(fp, dist_file)

        self.metadata_file = self.source_dir / "metadata.yaml" if metadata_file is None else pathlib.Path(metadata_file)

        if self.metadata_file.exists() is False:
            with open(self.metadata_file, "w") as f:
                f.write('linkReferences: true\nnameInLink: true\nfigPrefix: "Figure"\ntblPrefix: "Table"')
                if self._use_default_html_style is True:
                    f.write("\nstylesheet: style.css")
            css_style = self.source_dir / "style.css"
            if css_style.exists() is False:
                shutil.copy(MY_DEFAULT_HTML_CSS, css_style)

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
            html.export(dest_file)
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

    def _perform_variable_substitution(self, use_table_var_substitution):
        logger.info("Performing variable substitution")
        for mdf in self.md_files_main + self.md_files_app:
            md_file = mdf.path
            os.makedirs(mdf.new_file.parent, exist_ok=True)
            md_str = mdf.read_original_file()

            for m in mdf.get_variables():
                res = m.group(1)
                key = res.split("|")[0] if "|" in res else res
                list_of_flags = res.split("|")[1:] if "|" in res else None
                key_clean = key[2:-2]

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
        return self.work_dir / "temp" / "_build"

    @property
    def dist_dir(self):
        return self.work_dir / "temp" / "_dist"

    @property
    def output_dir(self):
        return self._output_dir
