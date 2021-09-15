import logging
import os
import pathlib
import re

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
    from .io.word.utils import convert_markdown_dir_to_docx

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
    from .common import Equation, Table

    def sub_table(tbl: Table, flags) -> str:
        return tbl.to_markdown(False, flags=flags)

    def sub_equation(eq: Equation, flags) -> str:
        return eq.to_latex(flags=flags)

    def convert_variable(value, flags) -> str:
        if type(value) is Table:
            value_str = sub_table(value, flags)
        elif type(value) is Equation:
            value_str = sub_equation(value, flags)
        else:
            value_str = str(value)
        return value_str

    key_re = re.compile("{{(.*)}}")
    for m in key_re.finditer(md_doc_str):
        res = m.group(1)
        key = res.split("|")[0] if "|" in res else res
        list_of_flags = res.split("|")[1:] if "|" in res else None
        key_clean = key[2:-2]
        variable = variable_dict.get(key_clean, None)
        if variable is None:
            continue
        value_result_str = convert_variable(variable, list_of_flags)
        md_doc_str = md_doc_str.replace(m.group(0), value_result_str)

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
