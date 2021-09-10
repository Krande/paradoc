import logging
from dataclasses import dataclass

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


@dataclass
class Formatting:
    is_appendix: bool
    paragraph_style_map: dict
    table_format: str


def add_indented_normal(doc):
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Mm, Pt

    styles = doc.styles
    style = styles.add_style("Normal indent", WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = styles["Normal"]

    paragraph_format = style.paragraph_format
    paragraph_format.left_indent = Mm(0.25)
    paragraph_format.space_before = Pt(12)
    paragraph_format.widow_control = True

    return style


def format_paragraph(pg, document, paragraph_formatting):
    """

    :param pg:
    :param document:
    :param paragraph_formatting:
    :type paragraph_formatting: paradoc.Formatting
    :return:
    """
    from docx.shared import Mm

    paragraph_style_map = paragraph_formatting.paragraph_style_map
    style_name = pg.style.name
    logging.debug(style_name)
    if style_name == "Compact":  # Is a bullet point list
        new_style_name = paragraph_style_map[pg.style.name]
        new_style = document.styles[new_style_name]
        pg.style = new_style
        pg.paragraph_format.left_indent = Mm(25)

    elif style_name in paragraph_style_map.keys():
        new_style_name = paragraph_style_map[pg.style.name]

        if new_style_name not in document.styles:
            styles = "".join([x.name + "\n" for x in document.styles])
            raise ValueError(
                f'The requested style "{new_style_name}" does not exist in style_doc.\n'
                "Note! Style names are CAPS sensitive.\n"
                f"Available styles are:\n{styles}"
            )

        new_style = document.styles[new_style_name]
        pg.style = new_style

        logging.debug(f'Changed paragraph style "{pg.style}" to "{new_style_name}"')
    else:
        if style_name not in document.styles:
            logging.info(f'StyleDoc missing style "{style_name}"')


def apply_custom_styles_to_docx(doc, doc_format=None, style_doc=None):
    """

    :param doc:
    :param doc_format:
    :type doc_format: paradoc.Formatting
    :param style_doc:
    :return:
    """

    from paradoc import MY_DOCX_TMPL

    from .references import format_captions
    from .tables import format_table
    from .utils import iter_block_items

    document = style_doc if style_doc is not None else Document(MY_DOCX_TMPL)
    prev_table = False
    refs = dict()

    for block in iter_block_items(doc):
        if type(block) == Paragraph:
            if prev_table and len(block.runs) > 0:
                block.runs[0].text = "\n" + block.runs[0].text
                prev_table = False
                block.paragraph_format.space_before = None
            if block.style.name in ("Image Caption", "Table Caption"):
                ref_ = format_captions(block, doc_format)
                refs.update(ref_)
            else:
                format_paragraph(block, document, doc_format)

        elif type(block) == Table:
            if doc_format.table_format:
                format_table(block, document, doc_format.table_format)
            prev_table = True

    return refs


def fix_headers_after_compose(doc: Document):
    from paradoc import OneDoc

    from .utils import delete_paragraph, iter_block_items

    pg_rem = []
    for pg in iter_block_items(doc):
        if type(pg) == Paragraph:
            if pg.style.name in ("Image Caption", "Table Caption"):
                continue
            else:
                if pg.style.name in list(OneDoc.default_app_map.values())[1:]:
                    pg.insert_paragraph_before(pg.text, style=pg.style.name)
                    pg_rem.append(pg)

    for pg in pg_rem:
        delete_paragraph(pg)
