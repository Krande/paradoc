import logging
import os
import pathlib
import traceback

import pypandoc
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from paradoc.utils import get_list_of_files


def delete_paragraph(paragraph):
    p = paragraph._element
    p.getparent().remove(p)
    paragraph._p = paragraph._element = None


def open_word_win32():
    import sys

    if sys.platform != "win32":
        return

    try:
        import win32com.client

        word = win32com.client.DispatchEx("Word.Application")
    except (ModuleNotFoundError, ImportError):
        logging.error(
            "Ensure you have you have win32com installed. "
            'Use "conda install -c conda-forge pywin32" to install. '
            f"{traceback.format_exc()}"
        )
        return None
    except BaseException as e:
        logging.error(
            "Probably unable to find COM connection to Word application. "
            f"Is Word installed? {traceback.format_exc()}, {e}"
        )
        return None
    return word


def docx_update(docx_file):
    word = open_word_win32()
    if word is None:
        return

    doc = word.Documents.Open(docx_file)

    # update all figure / table numbers
    word.ActiveDocument.Fields.Update()

    # update Table of content / figure / table
    word.ActiveDocument.TablesOfContents(1).Update()
    # word.ActiveDocument.TablesOfFigures(1).Update()
    # word.ActiveDocument.TablesOfFigures(2).Update()

    doc.Close(SaveChanges=True)

    word.Quit()


def close_word_docs_by_name(names: list) -> None:
    word = open_word_win32()
    if word is None:
        return

    if len(word.Documents) > 0:
        for doc in word.Documents:
            doc_name = doc.Name
            if doc_name in names:
                print(f'Closing "{doc}"')
                doc.Close()
    else:
        print(f"No Word docs named {names} found to be open. Ending Word Application COM session")

    word.Quit()


def iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    Each returned value is an instance of either Table or Paragraph. *parent*
    would most commonly be a reference to a main Document object, but
    also works for a _Cell object, which itself can contain paragraphs and tables.
    """
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)
        else:
            logging.debug(f"Unrecognized child element type {type(child)}")


def convert_markdown_dir_to_docx(source, dest, dest_format, extra_args, style_doc=None):
    """

    :param source:
    :param dest:
    :param dest_format:
    :param extra_args:
    :param style_doc:
    :return:
    """
    from docx import Document
    from docxcompose.composer import Composer

    build_dir = source / "_build"
    if style_doc is not None:
        document = Document(str(style_doc))
        document.add_page_break()
        composer = Composer(document)
    else:
        composer = None
    files = []
    for md_file in get_list_of_files(source, ".md"):
        if "_build" in md_file or "_dist" in md_file:
            continue
        md_file = pathlib.Path(md_file)
        new_file = build_dir / md_file.parent.name / md_file.with_suffix(".docx").name
        os.makedirs(new_file.parent, exist_ok=True)

        output = pypandoc.convert_file(
            str(md_file),
            dest_format,
            format="markdown",
            outputfile=str(new_file),
            extra_args=extra_args,
            filters=["pandoc-crossref"],
            encoding="utf8",
        )
        logging.info(output)
        files.append(str(new_file))

    # for i in range(0, len(files)):
    #     doc = Document(files[i])
    #     doc.add_page_break()
    #     if composer is None:
    #         composer = Composer(doc)
    #     else:
    #         composer.append(doc)
    #
    #     logging.info(f"Added {files[i]}")

    composer.save(str(dest))
