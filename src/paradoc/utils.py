import logging
import os
import pathlib
import re
from decimal import ROUND_HALF_EVEN, Decimal

import pypandoc
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


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


def func_eq_params(func):
    """
    Returns the string defined after the :equation: marker

    :param func:
    :return:
    """
    eq_str = "".join([l.replace(":equation:", "") for l in func.__doc__.splitlines() if ":equation:" in l]).strip()

    var_map = {}
    params = [":param ", ":eq_param "]
    for l in func.__doc__.splitlines():
        for par in params:
            if par in l:
                l_1 = l.replace(par, "")
                l_s = l_1.split(":")
                var = l_s[0].strip()
                desc = l_s[1].strip()
                if var.lower() in eq_str.lower():
                    start = eq_str.lower().index(var.lower())
                    new_str = eq_str[start : start + len(var)]
                    var_map[new_str] = desc
                else:
                    if par == ":eq_param ":
                        var_map[var] = desc
    return var_map


def roundoff(x, precision=6):
    """

    :param x: Number
    :param precision: Number precision
    :return:
    """
    xout = float(Decimal(float(x)).quantize(Decimal("." + precision * "0" + "1"), rounding=ROUND_HALF_EVEN))
    return xout if abs(xout) != 0.0 else 0.0


def extract_ref(document):
    """
    Extract all references from report.

    TO-DO: Should use this on more example

    :param document:
    :return: Reference Dictionary
    """
    ref_dict = {"regulations": {}, "company": {}, "project": {}}
    table = document.tables[6]
    num = 1
    for row in table.rows[1:]:
        ref_dict["regulations"][row.cells[0].text] = {
            "title": row.cells[1].text,
            "rev": row.cells[2].text,
            "ref": "/{}/".format(num),
        }
        num += 1
    table = document.tables[7]
    for row in table.rows[1:]:
        ref_dict["company"][row.cells[0].text] = {
            "title": row.cells[1].text,
            "rev": row.cells[2].text,
            "ref": "/{}/".format(num),
        }
        num += 1
    table = document.tables[8]
    for row in table.rows[1:]:
        ref_dict["project"][row.cells[0].text] = {
            "title": row.cells[1].text,
            "rev": row.cells[2].text,
            "ref": "/{}/".format(num),
        }
        num += 1
    return ref_dict


def extract_head(document):
    doc_contents = []
    for par in document.paragraphs:
        if "heading" in par.style.name.lower():
            if par.style.name == "Heading 1":
                doc_contents.append({"level": 1, "heading": par.text})
            elif par.style.name == "Heading 2":
                doc_contents.append({"level": 2, "heading": par.text})
            elif par.style.name == "Heading 3":
                doc_contents.append({"level": 3, "heading": par.text})
            elif par.style.name == "Heading 4":
                doc_contents.append({"level": 4, "heading": par.text})
    return doc_contents


def extract_ref_from_par(document):
    """

    :param document:
    :return:
    """
    curr_head = ""
    for par in document.paragraphs:
        if "heading" in par.style.name.lower():
            curr_head = par.text
        else:
            for i in range(1, 30):
                if "/{}/".format(i) in par.text:
                    print(40 * "-")
                    print("{} contains ref to /{}/".format(curr_head, i))
                    print("\n")
                    print(par.text)
                    print(40 * "-")
                    print("\n")


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


def process_latex(e):
    """

    :param e:
    :return:

    Copied function from https://github.com/javiljoen/tex2mathml
    """

    while e.startswith("$"):
        e = e[1:]

    while e.endswith("$"):
        e = e[:-1]

    e = e.replace(r"\operatorname", "")
    e = e.replace(r"\displaystyle", "")
    e = e.replace(r"\nonumber", "")
    e = e.replace("&", "")
    e = e.replace(r"\!", "")
    e = re.sub(r"([^\\])\$", "\\1", e)
    e = re.sub(r"\\mbox{([^}]*)}", '"\\1"', e)
    e = re.sub(r"\\mathrm{([^}]*)}", '"\\1"', e)
    e = re.sub(r"\\begin{.*}", "", e)
    e = re.sub(r"\\end{.*}", "", e)
    return e


def add_table_reference(paragraph, seq=" SEQ Table \\* ARABIC \\s 1"):
    """

    :param paragraph:
    :param seq
    """
    run = paragraph.add_run()
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    instrText = OxmlElement("w:instrText")
    instrText.text = seq
    r.append(instrText)
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)

    return run


def add_seq_reference(run_in, seq, parent):
    """

    :param run_in:
    :param seq:
    :param parent:
    :return:
    """
    from docx.text.run import Run

    new_run = Run(run_in, parent)
    r = new_run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    instrText = OxmlElement("w:instrText")
    instrText.text = seq
    r.append(instrText)
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)
    return new_run


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


def format_table(tbl, document, table_format):
    """

    :param tbl:
    :param document:
    :param table_format:
    :return:
    """
    from docx.shared import Pt

    new_tbl_style = document.styles[table_format]
    tbl.style = new_tbl_style
    logging.info(f'Changed Table style from "{tbl.style}" to "{new_tbl_style}"')
    # tbl.paragraph_format.space_after = Pt(12)
    for i, row in enumerate(tbl.rows):
        for cell in row.cells:
            paragraphs = cell.paragraphs
            for paragraph in paragraphs:
                for run in paragraph.runs:
                    font = run.font
                    # run.style = document.styles["Normal"]
                    font.name = "Arial"
                    font.size = Pt(12)
                    if i == 0:
                        font.bold = True
                    else:
                        font.bold = False


def add_bookmark(paragraph, bookmark_text, bookmark_name):
    """

    :param paragraph:
    :param bookmark_text:
    :param bookmark_name:
    :return:
    """
    from docx.oxml.ns import qn
    from docx.oxml.shared import OxmlElement

    run = paragraph.add_run()
    tag = run._r  # for reference the following also works: tag =  document.element.xpath('//w:r')[-1]
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "0")
    start.set(qn("w:name"), bookmark_name)
    tag.append(start)

    text = OxmlElement("w:r")
    text.text = bookmark_text
    tag.append(text)

    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "0")
    end.set(qn("w:name"), bookmark_name)
    tag.append(end)


def insert_caption(pg, prefix, run, text, doc_format):
    """

    :param pg:
    :param prefix:
    :param run:
    :param text:
    :param doc_format:
    :type doc_format: paradoc.Formatting
    :return:
    """
    from docx.text.run import Run

    heading_ref = "Appendix" if doc_format.is_appendix is True else '"Heading 1"'

    seq1 = pg._element._new_r()
    add_seq_reference(seq1, f"STYLEREF \\s {heading_ref} \\n", run._parent)
    run._element.addprevious(seq1)
    stroke = pg._element._new_r()
    new_run = Run(stroke, run._parent)
    new_run.text = "-"
    run._element.addprevious(stroke)
    seq2 = pg._element._new_r()
    add_seq_reference(seq2, f"SEQ {prefix} \\* ARABIC \\s 1", run._parent)
    run._element.addprevious(seq2)
    fin = pg._element._new_r()
    fin_run = Run(fin, run._parent)
    fin_run.text = ": " + text
    run._element.addprevious(fin)


def insert_caption_into_runs(pg, prefix, doc_format):
    """

    :param pg:
    :param prefix:
    :param doc_format:
    :type doc_format: paradoc.Formatting
    :return:
    """

    tmp_split = pg.text.split(":")
    prefix_old = tmp_split[0].strip()
    text = tmp_split[-1].strip()
    srun = pg.runs[0]
    if len(pg.runs) > 1:
        run = pg.runs[1]
        tmp_str = pg.runs[0].text
        pg.runs[0].text = f"{prefix} "
        insert_caption(pg, prefix, run, tmp_str.split(":")[-1].strip(), doc_format)
    else:
        srun.text = f"{prefix} "
        run = pg.add_run()
        insert_caption(pg, prefix, run, text, doc_format)

    return srun, pg, prefix_old


def format_captions(pg, doc_format):
    """

    :param pg:
    :param doc_format:
    :type doc_format: paradoc.Formatting
    :return:
    """
    ref_dict = dict()
    style_name = pg.style.name
    logging.debug(style_name)
    tmp_split = pg.text.split(":")
    prefix = tmp_split[0].strip()
    if style_name == "Image Caption":
        ref_dict[prefix] = insert_caption_into_runs(pg, "Figure", doc_format)
    elif style_name == "Table Caption":
        ref_dict[prefix] = insert_caption_into_runs(pg, "Table", doc_format)
    else:
        raise ValueError("Not possible")

    return ref_dict


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


def add_bookmarkStart(paragraph, _id):
    name = "_Ref_id_num_" + _id
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:name"), name)
    start.set(qn("w:id"), str(_id))
    paragraph._p.append(start)
    return name


def append_ref_to_paragraph(paragraph, refName, text=""):
    """

    :param paragraph:
    :param refName:
    :param text:
    :return:
    """
    # run 1
    run = paragraph.add_run(text)
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "begin")
    r.append(fldChar)
    # run 2
    run = paragraph.add_run()
    r = run._r
    instrText = OxmlElement("w:instrText")
    instrText.text = "REF " + refName + " \\h"
    r.append(instrText)
    # run 3
    run = paragraph.add_run()
    r = run._r
    fldChar = OxmlElement("w:fldChar")
    fldChar.set(qn("w:fldCharType"), "end")
    r.append(fldChar)


def apply_custom_styles_to_docx(doc, doc_format=None, style_doc=None):
    """

    :param doc:
    :param doc_format:
    :type doc_format: paradoc.Formatting
    :param style_doc:
    :return:
    """

    from paradoc import MY_DOCX_TMPL

    document = style_doc if style_doc is not None else Document(MY_DOCX_TMPL)
    prev_table = False
    refs = dict()

    for block in iter_block_items(doc):
        if type(block) == Paragraph:
            if prev_table:
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


def resolve_references(document):
    import re

    from docx.text.paragraph import Paragraph

    refs = dict()
    fig_re = re.compile(
        r"(?:Figure\s(?P<number>[0-9]{0,5})\s*)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    tbl_re = re.compile(r"(?:Table\s(?P<number>[0-9]{0,5})\s*)", re.MULTILINE | re.DOTALL | re.IGNORECASE)

    # Fix references
    for block in iter_block_items(document):
        if type(block) == Paragraph:
            if block.style.name in ("Image Caption", "Table Caption"):
                continue
            if "Figure" in block.text or "Table" in block.text:
                for m in fig_re.finditer(block.text):
                    d = m.groupdict()
                    n = d["number"]
                    figref = f"Figure {n}"
                    if figref in refs.keys():
                        fref = refs[figref]
                        pg_ref = fref[1]

                for m in tbl_re.finditer(block.text):
                    d = m.groupdict()
                    n = d["number"]
                    tblref = f"Table {n}"
                    if tblref in refs.keys():
                        tref = refs[tblref]
                        pg_ref = tref[1]
                        parent = pg_ref._p
                        # ref_id = parent.id
                        print(parent)


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


def fix_headers_after_compose(doc):
    """

    :param doc:
    :type doc: docx.document.Document
    :return:
    """
    from paradoc import OneDoc

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


def open_word_win32():
    try:
        import win32com.client

        word = win32com.client.DispatchEx("Word.Application")
    except BaseException as e:
        logging.error(f"Unable to find COM connection to Word application. Is Word installed? {e}")
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
