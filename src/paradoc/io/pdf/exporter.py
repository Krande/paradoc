import pathlib

import pypandoc

from paradoc import OneDoc
from paradoc.utils import copy_figures_to_dist


class PdfExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file: pathlib.Path):
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])

        copy_figures_to_dist(one, dest_file.parent)

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

        pypandoc.convert_text(
            combined_str,
            one.FORMATS.PDF,
            outputfile=str(dest_file),
            format="markdown",
            extra_args=[
                "-M2GB",
                "+RTS",
                "-K64m",
                "-RTS",
                "--pdf-engine=xelatex",
                f"--resource-path={dest_file.parent}",
                f"--metadata-file={one.metadata_file}",
            ],
            filters=["pandoc-crossref"],
        )
        print(f'Successfully exported PDF to "{dest_file}"')
