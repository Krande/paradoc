"""Static plot images come out at the requested size, not kaleido's 700x500 default."""

import struct

import pandas as pd

from paradoc import OneDoc
from paradoc.db import DbManager, PlotData, dataframe_to_plot_data
from paradoc.db.plot_renderer import PlotRenderer


def _png_size(path) -> tuple[int, int]:
    """Width and height from the PNG IHDR chunk."""
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", head[16:24])


def test_render_to_image_uses_plot_size(tmp_path):
    df = pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})
    plot = dataframe_to_plot_data(df=df, key="sized", plot_type="line", caption="Sized", x_column="x", y_columns=["y"])
    plot = PlotData(**{**plot.model_dump(), "width": 1100, "height": 780})
    out = tmp_path / "sized.png"
    PlotRenderer(cache_dir=tmp_path / "cache").render_to_image(plot, output_path=out)
    assert _png_size(out) == (1100, 780)


def test_batch_render_uses_plot_size(tmp_path):
    source_dir = tmp_path / "doc"
    main_dir = source_dir / "00-main"
    main_dir.mkdir(parents=True)

    db = DbManager(source_dir / "data.db")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2]})
    plot = dataframe_to_plot_data(df=df, key="wide", plot_type="line", caption="Wide", x_column="x", y_columns=["y"])
    plot.width, plot.height = 1100, 780
    db.add_plot(plot)
    if db.connection:
        db.connection.close()

    (main_dir / "content.md").write_text("# Plots\n\n{{__wide__}}\n", encoding="utf-8")

    one = OneDoc(source_dir=source_dir, work_dir=tmp_path / "work")
    one.get_ast()
    if one.db_manager.connection:
        one.db_manager.connection.close()

    png = one.work_dir / ".paradoc_cache" / "rendered_plots" / "wide_1100x780.png"
    assert png.exists()
    assert _png_size(png) == (1100, 780)
