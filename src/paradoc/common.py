from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Callable

import pandas as pd

MY_DOCX_TMPL = pathlib.Path(__file__).resolve().absolute().parent / "resources" / "template.docx"
MY_DOCX_TMPL_BLANK = pathlib.Path(__file__).resolve().absolute().parent / "resources" / "template_blank.docx"


@dataclass
class TableFormat:
    style: str = "Grid Table 1 Light"
    font_size: float = 11
    font_style: str = "Arial"


class TableFlags:
    NO_CAPTION = "nocaption"


@dataclass
class Table:
    name: str
    df: pd.DataFrame
    caption: str
    format: TableFormat = TableFormat()
    add_link: bool = False

    def to_markdown(self, include_name_in_cell=False, flags=None):
        df = self.df.copy()
        if include_name_in_cell:
            col_name = df.columns[0]
            df.iloc[0, df.columns.get_loc(col_name)] = self.name
        tbl_str = df.to_markdown(index=False, tablefmt="grid")
        if flags is not None and TableFlags.NO_CAPTION in flags:
            return tbl_str
        tbl_str += f"\n\nTable: {self.caption}"
        if self.add_link:
            tbl_str += f"{{#tbl:{self.name}}}"
        return tbl_str


@dataclass
class Equation:
    name: str
    func: Callable
    custom_eq_str_compiler: Callable = None

    def to_latex(self, print_latex=False, print_formula=False, flags=None):
        if self.custom_eq_str_compiler is not None:
            return self.custom_eq_str_compiler(self.func)

        from inspect import getsourcelines

        import pytexit

        lines = getsourcelines(self.func)
        eq_latex = ""
        matches = ("def", "return", '"')
        dots = 0
        for line in lines[0]:
            if any(x in line for x in matches):
                dots += line.count('"')
                dots += line.count("'")
                continue
            if dots >= 6 or dots == 0:
                eq_latex += pytexit.py2tex(line, print_latex=print_latex, print_formula=print_formula) + "\n"

        return eq_latex + f"{{#eq:{self.name}}}"


@dataclass
class DocXFormat:
    pg_font: str = "Arial"
    pg_size: int = 11


@dataclass
class MarkDownFile:
    path: pathlib.Path
    is_appendix: bool
    new_file: pathlib.Path
    build_file: pathlib.Path


class ExportFormats:
    DOCX = "docx"
    PDF = "pdf"
