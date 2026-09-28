import os
import pathlib
import shutil

import pypandoc

from paradoc import OneDoc
from paradoc.exceptions import LatexNotInstalled
from paradoc.utils import copy_figures_to_dist

#: PDF engines pandoc can drive, in the order they are tried. xelatex first because it is what
#: paradoc has always used; tectonic next because it is one self-contained binary on conda-forge for
#: every platform (TeX Live is not packaged for win-64) that fetches the TeX packages it needs.
PDF_ENGINES = ("xelatex", "tectonic", "lualatex", "pdflatex")


def resolve_pdf_engine() -> str:
    """The PDF engine to hand pandoc: ``PARADOC_PDF_ENGINE`` if set, else the first found on PATH.

    ``PARADOC_PDF_ENGINE`` takes a name on PATH or a path to the executable.
    """
    override = os.environ.get("PARADOC_PDF_ENGINE", "").strip()
    if override:
        found = shutil.which(override)
        if found is None:
            raise LatexNotInstalled(f'PARADOC_PDF_ENGINE is "{override}", which is not an executable found here.')
        return found
    for name in PDF_ENGINES:
        found = shutil.which(name)
        if found is not None:
            return found
    raise LatexNotInstalled(
        f"No PDF engine found (looked for {', '.join(PDF_ENGINES)}). Install one -- e.g. "
        '"conda install -c conda-forge tectonic" -- or point PARADOC_PDF_ENGINE at one.'
    )


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
                f"--pdf-engine={resolve_pdf_engine()}",
                f"--resource-path={dest_file.parent}",
                f"--metadata-file={one.metadata_file}",
            ],
            filters=["pandoc-crossref"],
        )
        print(f'Successfully exported PDF to "{dest_file}"')
