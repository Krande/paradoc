"""OpenDocument Text (.odt) export, straight from pandoc.

The same route as the PDF export -- the built markdown joined into one document, figure and table
captions numbered by pandoc-crossref -- written with pandoc's own ODT writer. No office suite is
needed to produce it, and LibreOffice, Word and Google Docs all open it.
"""

import pathlib

import pypandoc

from paradoc import OneDoc
from paradoc.io.pdf.exporter import prepare_images
from paradoc.utils import copy_figures_to_dist


class OdtExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file: pathlib.Path):
        one = self.one_doc
        out_dir = dest_file.parent

        copy_figures_to_dist(one, out_dir)

        def built(md) -> str:
            return prepare_images(md.read_built_file(), md.build_file.parent, out_dir)

        # No appendix marker: the PDF's is a raw LaTeX \appendix, which the ODT writer drops.
        combined_str = "\n\n".join(built(md) for md in [*one.md_files_main, *one.md_files_app])

        pypandoc.convert_text(
            combined_str,
            one.FORMATS.ODT,
            outputfile=str(dest_file),
            format="markdown",
            extra_args=[
                "-M2GB",
                "+RTS",
                "-K64m",
                "-RTS",
                f"--resource-path={out_dir}",
                f"--metadata-file={one.metadata_file}",
            ],
            filters=["pandoc-crossref"],
        )
        print(f'Successfully exported ODT to "{dest_file}"')
