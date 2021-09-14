import pathlib
from dataclasses import dataclass

MY_DOCX_TMPL = pathlib.Path(__file__).resolve().absolute().parent / "resources" / "template.docx"
MY_DOCX_TMPL_BLANK = pathlib.Path(__file__).resolve().absolute().parent / "resources" / "template_blank.docx"


@dataclass
class MarkDownFile:
    path: pathlib.Path
    is_appendix: bool
    new_file: pathlib.Path
    build_file: pathlib.Path


class ExportFormats:
    DOCX = "docx"
    PDF = "pdf"
