import os

import pytest

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled

auto_open = os.getenv("AUTO_OPEN", False)


@pytest.mark.parametrize("export_format", ["html", "docx", "pdf"])
def test_doc1_export_to_html(files_dir, tmp_path, export_format):
    source = files_dir / "doc1"
    dest = tmp_path / f"{source.name}/{source.name}.{export_format}"

    try:
        one = OneDoc(source, work_dir=dest.parent)
        one.compile(source.name, auto_open=auto_open, export_format=export_format)
    except LatexNotInstalled as e:
        print(e)


@pytest.mark.parametrize("export_format", ["html", "docx", "pdf"])
def test_doc2_export_to_html(files_dir, tmp_path, export_format):
    source = files_dir / "doc2"
    dest = tmp_path / f"{source.name}/{source.name}.{export_format}"

    try:
        one = OneDoc(source, work_dir=dest.parent)
        one.compile(source.name, auto_open=auto_open, export_format=export_format)
    except LatexNotInstalled as e:
        print(e)
