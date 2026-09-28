import shutil
import subprocess

import pypandoc


def test_run_pandoc_directly(files_dir, tmp_path):
    md_file = files_dir / "doc1/00-main/main.md"
    pandoc_exe = shutil.which("pandoc")
    subprocess.run(
        [
            pandoc_exe,
            md_file,
            "-o",
            (tmp_path / "test.docx").as_posix(),
            "--resource-path",
            str(md_file.parent.absolute()),
            "--filter",
            "pandoc-crossref",
        ]
    )


def test_run_pypandoc_directly(files_dir, tmp_path):
    md_file = files_dir / "doc1/00-main/main.md"
    pypandoc.convert_file(
        md_file,
        "docx",
        outputfile=tmp_path / "test.docx",
        format="markdown",
        extra_args=[f"--resource-path={md_file.parent.absolute()}"],
        filters=["pandoc-crossref"],
        sandbox=False,
    )
