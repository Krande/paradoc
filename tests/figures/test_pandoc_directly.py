import os
import shutil
import subprocess

import pypandoc


def test_run_pandoc_directly(files_dir):
    md_file = files_dir / "doc1/00-main/main.md"
    os.makedirs("temp", exist_ok=True)
    pandoc_exe = shutil.which("pandoc")
    subprocess.run(
        [
            pandoc_exe,
            md_file,
            "-o",
            "temp/test.docx",
            "--resource-path",
            str(md_file.parent.absolute()),
            "--filter",
            "pandoc-crossref",
        ]
    )


def test_run_pypandoc_directly(files_dir):
    md_file = files_dir / "doc1/00-main/main.md"
    os.makedirs("temp", exist_ok=True)
    pypandoc.convert_file(
        md_file,
        "docx",
        outputfile="temp/test.docx",
        format="markdown",
        extra_args=[f"--resource-path={md_file.parent.absolute()}"],
        filters=["pandoc-crossref"],
        encoding="utf8",
        sandbox=False,
    )
