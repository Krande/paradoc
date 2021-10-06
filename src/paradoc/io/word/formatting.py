import logging

from docx import Document
from docx.text.paragraph import Paragraph

from .references import insert_caption_into_runs
from .utils import iter_block_items


def add_indented_normal(doc: Document):
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


def format_paragraphs_and_headings(doc: Document, paragraph_style_map, style_doc=None):
    from paradoc import MY_DOCX_TMPL

    document = style_doc if style_doc is not None else Document(MY_DOCX_TMPL)

    for block in iter_block_items(doc):
        if type(block) == Paragraph:
            if block.style.name in ("Image Caption", "Table Caption"):
                continue
            else:
                format_paragraph(block, document, paragraph_style_map)


def format_paragraph(pg, document, paragraph_style_map: dict):
    from docx.shared import Mm, Pt

    style_name = pg.style.name
    logging.debug(style_name)
    if style_name == "Compact":  # Is a bullet point list
        new_style_name = paragraph_style_map[pg.style.name]
        new_style = document.styles[new_style_name]
        pg.style = new_style
        pg.paragraph_format.left_indent = Mm(25)
    elif style_name == "Source Code":
        pg.paragraph_format.left_indent = Mm(15)
        pg.paragraph_format.space_before = Pt(12)
        pg.paragraph_format.space_after = Pt(12)
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


def fix_headers_after_compose(doc: Document):
    from paradoc import OneDoc
    from paradoc.io.word.utils import delete_paragraph, iter_block_items

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


def format_image_captions(doc: Document, is_appendix):
    for block in iter_block_items(doc):
        if type(block) == Paragraph:
            if block.style.name in ("Image Caption",):
                insert_caption_into_runs(block, "Figure", is_appendix)
