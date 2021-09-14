import logging
import os
import pathlib
import re
import traceback

import pypandoc


def func_to_eq(func):
    """
    Converts a function with doc strings containing :eq: and :param: keywords.

    :param func:
    :return:
    """
    params_re = re.compile(r":param (?P<var>.*?):(?P<res>.*?)$", re.MULTILINE | re.DOTALL | re.IGNORECASE)
    equation_re = re.compile(r":eq:(.*?):\/eq:", re.MULTILINE | re.DOTALL | re.IGNORECASE)

    params = {x.groupdict()["var"].strip(): x.groupdict()["res"].strip() for x in params_re.finditer(func.__doc__)}
    equation = [x.group(1).strip() for x in equation_re.finditer(func.__doc__)]
    return equation, params


def close_word_docs_by_name(names):
    """

    :param names: List of word document basenames (basenames e.g. "something.docx").
    :type names: list
    :return:
    """

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
    from docx.document import Document
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table, _Cell
    from docx.text.paragraph import Paragraph

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
            logging.info(f"Unrecognized child element type {type(child)}")


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


def convert_markdown(
    source,
    dest,
    dest_format="docx",
    metadata_file=None,
    pdf_engine="xelatex",
    style_doc=None,
):
    """

    :param source:
    :param dest:
    :param dest_format:
    :param metadata_file:
    :param pdf_engine:
    :return:
    """

    source = pathlib.Path(source)
    dest = pathlib.Path(dest).with_suffix(f".{dest_format}")
    extra_args = ["-M2GB", "+RTS", "-K64m", "-RTS"]
    if metadata_file is not None:
        extra_args += [f"--metadata-file={metadata_file}"]
    if dest_format == "pdf":
        extra_args += [f"--pdf-engine={pdf_engine}"]
    if style_doc is not None:
        extra_args += [f"--reference-doc={style_doc}"]

    extra_args += [f"--resource-path={source.parent}"]
    print(f"Converting {source}")
    if source.is_dir():
        convert_markdown_dir_to_docx(source, dest, dest_format, extra_args, style_doc=style_doc)
    else:
        output = pypandoc.convert_file(
            str(source),
            dest_format,
            format="markdown",
            outputfile=str(dest),
            extra_args=extra_args,
            filters=["pandoc-crossref"],
            encoding="utf8",
        )
        logging.info(output)


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
    """

    :param docx_file:
    :return:
    """
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


def get_list_of_files(dir_path, file_ext=None, strict=False):
    """
    Get a list of file and sub directories for a given directory

    :param dir_path: Parent directory in which the recursive search for files will take place
    :param file_ext: File extension
    :param strict: If True the function raiser errors when no files are found.
    :return: list of all found files
    """
    all_files = []
    list_of_file = os.listdir(dir_path)

    # Iterate over all the entries
    for entry in list_of_file:
        # Create full path
        full_path = os.path.join(dir_path, entry)
        # If entry is a directory then get the list of files in this directory
        if os.path.isdir(full_path):
            all_files = all_files + get_list_of_files(full_path, file_ext, strict)
        else:
            all_files.append(full_path)

    if file_ext is not None:
        all_files = [f for f in all_files if f.endswith(file_ext)]

    if len(all_files) == 0:
        msg = f'Files with "{file_ext}"-extension is not found in "{dir_path}" or any sub-folder.'
        if strict:
            raise FileNotFoundError(msg)
        else:
            logging.info(msg)

    return all_files


def basic_equation_compiler(f, print_latex=False, print_formula=False):
    from inspect import getsourcelines

    import pytexit

    lines = getsourcelines(f)
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

    return eq_latex


def variable_sub(md_doc_str, variable_dict):
    from .concepts import Table

    def sub_table(tbl: Table) -> str:
        return tbl.to_markdown(True)

    for key, value in variable_dict.items():
        key_str = f"{{{{__{key}__}}}}"
        if key_str in md_doc_str:
            if type(value) is Table:
                value_str = sub_table(value)
            else:
                value_str = str(value)
            md_doc_str = md_doc_str.replace(key_str, value_str)
    return md_doc_str


def make_df(inputs, header, func):
    import pandas as pd

    res_matrix = [header]
    for var in inputs:
        res_matrix.append((*var, func(*var)))
    df = pd.DataFrame(res_matrix)
    df.columns = df.iloc[0]
    df = df.drop(df.index[0])
    return df
