"""ODT export fits images wider than the text block to its width, and leaves the others alone.

The ODT writer sizes an image from its pixels and DPI; a PNG with no DPI metadata counts as 72 dpi,
so a 640 px render came out 8.9 in wide on a 6.5 in text block.
"""

import re
import zipfile

import pypandoc
import pytest

from paradoc.io.odt.exporter import TEXT_WIDTH_IN, image_width_filter

PIL = pytest.importorskip("PIL.Image")


def _frame_widths(odt) -> list[str]:
    with zipfile.ZipFile(odt) as z:
        content = z.read("content.xml").decode("utf-8")
    return re.findall(r'<draw:frame[^>]*svg:width="([^"]+)"', content)


def test_wide_image_fits_text_width(tmp_path):
    PIL.new("RGB", (640, 480), "white").save(tmp_path / "wide.png")
    PIL.new("RGB", (100, 50), "white").save(tmp_path / "small.png")
    md = "![wide](wide.png)\n\n![small](small.png)\n\n![sized](wide.png){width=2in}\n"
    odt = tmp_path / "out.odt"

    pypandoc.convert_text(
        md,
        "odt",
        format="markdown",
        outputfile=str(odt),
        extra_args=[f"--resource-path={tmp_path}"],
        filters=[str(image_width_filter(tmp_path))],
    )

    wide, small, sized = _frame_widths(odt)
    assert wide == f"{TEXT_WIDTH_IN}in"
    assert small != wide  # left at its natural size
    assert sized == "2in"  # an explicit width is the author's
