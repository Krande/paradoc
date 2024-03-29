from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Union

import pandas as pd

RESOURCE_DIR = pathlib.Path(__file__).resolve().absolute().parent / "resources"
MY_DOCX_TMPL = RESOURCE_DIR / "template.docx"
MY_DOCX_TMPL_BLANK = RESOURCE_DIR / "template_blank.docx"
MY_DEFAULT_HTML_CSS = RESOURCE_DIR / "default_style.css"


@dataclass
class TableFormat:
    style: str = "Grid Table 1 Light"
    font_size: float = 11
    font_style: str = "Arial"
    float_fmt: Union[str, tuple] = None


@dataclass
class FigureFormat:
    font_style: str = "Arial"
    font_size: float = 11


class TableFlags:
    NO_CAPTION = "nocaption"


@dataclass
class Table:
    name: str
    df: pd.DataFrame
    caption: str
    format: TableFormat = field(default_factory=TableFormat)
    add_link: bool = True
    md_instances: List[MarkDownFile] = field(default_factory=list)
    docx_instances: List[object] = field(default_factory=list)
    link_name_override: str = None

    def __post_init__(self):
        if self.df is None:
            raise ValueError('Passed in dataframe "df" cannot be None')

    def to_markdown(self, include_name_in_cell=False, flags=None):
        df = self.df.copy()
        if include_name_in_cell:
            col_name = df.columns[0]
            col_index = df.columns.get_loc(col_name)
            df.iloc[0, col_index] = self.name

        props = dict(index=False, tablefmt="grid")
        if self.format.float_fmt is not None:
            props["floatfmt"] = self.format.float_fmt
        tbl_str = df.to_markdown(**props)
        if flags is not None and TableFlags.NO_CAPTION in flags:
            return tbl_str
        tbl_str += f"\n\nTable: {self.caption}"
        if self.add_link:
            if self.link_name_override is None:
                link_name = self.name
            else:
                link_name = self.link_name_override

            tbl_str += f" {{#tbl:{link_name}}}"
        return tbl_str

    @staticmethod
    def from_markdown_str(table_str: str) -> Table:
        """Parse a markdown table string and return a Table instance"""
        lines = table_str.splitlines()
        header = [x.strip() for x in lines[0].split("|")[1:-1]]
        data = []
        table_caption_str = None
        for line in lines[2:]:
            if line == "":
                continue
            if line.strip().startswith("Table:"):
                table_caption_str = line.strip()
                break
            data.append([x.strip() for x in line.split("|")[1:-1]])

        caption = table_caption_str.split("Table:")[1].strip()
        caption = caption.split("{")[0].strip()
        # Create a pandas DataFrame using the extracted header and data rows
        df = pd.DataFrame(data, columns=header)
        name = str(df.values[0][0])
        tbl_ref = re.search(r"{#tbl:(.*?)}", table_str)
        link_override = None
        if tbl_ref is not None:
            link_override = tbl_ref.group(1)
        return Table(name=name, df=df, caption=caption, link_name_override=link_override)


@dataclass
class Figure:
    name: str
    caption: str
    reference: str
    file_path: str
    format: FigureFormat = field(default_factory=FigureFormat)
    md_instance: MarkDownFile = field(default_factory=list)
    docx_instances: List[object] = field(default_factory=list)


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

    def read_original_file(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def read_built_file(self):
        """Read the Markdown file after performed variable substitution"""
        with open(self.build_file, "r", encoding="utf-8") as f:
            return f.read()

    def get_variables(self):
        key_re = re.compile(r"{{(.*)}}")
        return key_re.finditer(self.read_original_file())

    def get_figures(self):
        regx = re.compile(r"(?:!\[(?P<caption>.*?)\]\((?P<file_path>.*?)\)(?:{#fig:(?P<reference>.*?)}|))")
        yield from regx.finditer(self.read_original_file())

        # scan for html image refs also <img src="fig_path" alt="Subtitle" width="300"/>
        regx = re.compile(r'<img src="(?P<file_path>.*?)" alt="(?P<caption>.*?)"\s*(?:width="(?P<width>.*?)"|)\/>')
        yield from regx.finditer(self.read_original_file())

    def get_tables(self):
        regx = re.compile(r"(\|.*?\nTable:.*?$)", re.MULTILINE | re.DOTALL)
        yield from regx.finditer(self.read_original_file())


class ExportFormats(str, Enum):
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
