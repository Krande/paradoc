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


#: Fonts the operating system itself provides that cover Greek and super/subscripts. pandoc's
#: LaTeX default, Latin Modern, has neither: a report writing "ρ = 7850 kg/m³" or "L⁴" loses
#: those characters. Other TeX fonts are no answer -- conda-forge's MiKTeX ships only Latin
#: Modern and fetches anything else from the network -- whereas xelatex and tectonic both load
#: system fonts, and these are present on a stock install of each platform.
_SYSTEM_FONTS = {
    "win32": ("Cambria", "Consolas"),
    "darwin": ("Times New Roman", "Menlo"),
}
_SYSTEM_FONTS_OTHER = ("DejaVu Serif", "DejaVu Sans Mono")


def default_font_args(metadata_file=None) -> list[str]:
    """``-V mainfont=… -V monofont=…`` for this platform, unless the document sets its own.

    A ``mainfont`` / ``monofont`` in the document's metadata file wins, key by key. (Read as a
    top-level ``key:`` line rather than parsed: pyyaml is not a paradoc dependency.)
    """
    import re
    import sys

    text = ""
    if metadata_file and pathlib.Path(metadata_file).is_file():
        text = pathlib.Path(metadata_file).read_text(encoding="utf-8")

    def is_set(key: str) -> bool:
        return re.search(rf"^{key}\s*:\s*\S", text, re.MULTILINE) is not None

    main, mono = _SYSTEM_FONTS.get(sys.platform, _SYSTEM_FONTS_OTHER)
    args = []
    if not is_set("mainfont"):
        args.append(f"--variable=mainfont={main}")
    if not is_set("monofont"):
        args.append(f"--variable=monofont={mono}")
    return args


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
                *default_font_args(one.metadata_file),
            ],
            filters=["pandoc-crossref"],
        )
        print(f'Successfully exported PDF to "{dest_file}"')
