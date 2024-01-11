from docx import Document
from docx.text.paragraph import Paragraph

from paradoc.config import create_logger

from .references import insert_caption_into_runs
from .utils import iter_block_items

logger = create_logger()


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

    for i, block in enumerate(iter_block_items(doc)):
        if not isinstance(block, Paragraph):
            continue

        if block.style.name in ("Image Caption", "Table Caption"):
            continue
        else:
            format_paragraph(block, document, paragraph_style_map, i)


def format_paragraph(pg, document: Document, paragraph_style_map: dict, index):
    from docx.shared import Mm, Pt

    style_name = pg.style.name
    new_style_name = paragraph_style_map.get(style_name, None)
    if "No table of contents entries found." in pg.text:
        logger.info(f'Skipping Table of Contents at index "{index}"')
        return

    logger.debug(style_name)
    if style_name == "Compact":  # Is a bullet point list
        bullet_list_style_name = "Bulleted list"
        # https://github.com/python-openxml/python-docx/issues/217
        # https://stackoverflow.com/questions/77226712/how-to-extract-bullet-points-from-the-docs-using-python
        indent_level = pg._p.xpath("./w:pPr/w:numPr/w:ilvl/@w:val")[0]

        # Find previous and next paragraphs
        prev_pg = pg._p.getprevious()
        next_pg = pg._p.getnext()

        pg._p.style = bullet_list_style_name
        if prev_pg.style != bullet_list_style_name:
            pg.paragraph_format.space_before = Pt(12)
        if next_pg is not None and hasattr(next_pg, "style") and next_pg.style != "Compact":
            pg.paragraph_format.space_after = Pt(12)

        if indent_level == "0":
            pg.paragraph_format.left_indent = Mm(29)
        elif indent_level == "1":
            pg.paragraph_format.left_indent = Mm(34)

    elif style_name == "Source Code":
        pg.paragraph_format.left_indent = Mm(15)
        pg.paragraph_format.space_before = Pt(12)
        pg.paragraph_format.space_after = Pt(12)

    elif style_name == "Body Text":
        pg._p.style = new_style_name
        pg.paragraph_format.space_before = Pt(12)
        pg.paragraph_format.left_indent = Mm(15)

        logger.debug(f'Changed paragraph style "{pg.style}" to "{new_style_name}"')
    elif style_name is not None and new_style_name is not None and pg.text.strip() != "":
        if new_style_name not in document.styles:
            styles = "".join([x.name + "\n" for x in document.styles])
            raise ValueError(
                f'The requested style "{pg.style.name}" does not exist in style_doc.\n'
                "Note! Style names are CAPS sensitive.\n"
                f"Available styles are:\n{styles}"
            )
        pg._p.style = new_style_name
        if pg.style.name != new_style_name:
            forced_style = document.styles[new_style_name]
            pg.style = forced_style
        pg.paragraph_format.space_before = Pt(2)
        pg.paragraph_format.left_indent = Mm(15)

        logger.debug(f'Changed paragraph style "{pg.style}" to "{new_style_name}"')
    else:
        if style_name not in document.styles:
            logger.info(f'StyleDoc missing style "{style_name}"')


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
