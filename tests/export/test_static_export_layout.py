"""Static export layout: compact JSON, and plots split into an index plus one file per plot."""

import json

import numpy as np
import pandas as pd

from paradoc import OneDoc
from paradoc.db import dataframe_to_plot_data


def _doc(tmp_path):
    src = tmp_path / "doc"
    (src / "00-main").mkdir(parents=True)
    (src / "00-main" / "main.md").write_text(
        "# First\n\nIntro text.\n\n{{__wave__}}\n\n# Second\n\nSee [@fig:wave].\n", encoding="utf-8"
    )
    one = OneDoc(src, work_dir=tmp_path / "work")
    x = np.linspace(0, 1, 20)
    one.db_manager.add_plot(
        dataframe_to_plot_data(key="wave", df=pd.DataFrame({"x": x, "y": x**2}), plot_type="line", caption="Wave")
    )
    return one


def test_static_export_writes_compact_json_and_split_plots(tmp_path):
    one = _doc(tmp_path)
    out = tmp_path / "site"
    assert one.export_static(out, include_frontend=False)

    for rel in ["manifest.json", "sections/0.json", "sections/1.json", "plots.json", "plots_index.json"]:
        text = (out / rel).read_text(encoding="utf-8")
        assert "\n" not in text.strip(), f"{rel} is not compact"
        json.loads(text)

    index = json.loads((out / "plots_index.json").read_text(encoding="utf-8"))
    assert set(index) == {"wave"}
    entry = index["wave"]
    assert entry["file"] == "_plots/wave.json"
    assert entry["caption"] == "Wave"
    assert "figure" not in entry

    one_plot = json.loads((out / entry["file"]).read_text(encoding="utf-8"))
    bulk = json.loads((out / "plots.json").read_text(encoding="utf-8"))
    assert one_plot == bulk["wave"]
    assert one_plot["figure"]["data"], "per-plot file carries the Plotly figure"


def test_static_export_finds_an_image_written_relative_to_the_built_markdown(tmp_path):
    """Paths paradoc writes into the built markdown (3D figure posters) are relative to the built file,
    and a standalone image becomes a Figure, whose nested blocks carry no source annotation: the export
    must still find the file instead of dropping it as missing."""
    import os

    from PIL import Image

    assets = tmp_path / "elsewhere" / "case"
    assets.mkdir(parents=True)
    Image.new("RGB", (4, 4), "red").save(assets / "poster.png")
    src = tmp_path / "doc"
    (src / "00-main").mkdir(parents=True)
    one = OneDoc(src, work_dir=tmp_path / "work")
    rel = os.path.relpath(assets / "poster.png", one.build_dir / "00-main").replace(os.sep, "/")
    (src / "00-main" / "main.md").write_text(f"# First\n\n![A poster]({rel}){{#fig:poster}}\n", encoding="utf-8")
    one = OneDoc(src, work_dir=tmp_path / "work")

    out = tmp_path / "site"
    assert one.export_static(out, include_frontend=False)

    sections = "".join(p.read_text(encoding="utf-8") for p in (out / "sections").glob("*.json"))
    assert rel not in sections, "the image reference was not rewritten: the export did not find the file"
    copied = list((out / "_images").glob("*-poster.png"))
    assert len(copied) == 1 and copied[0].read_bytes() == (assets / "poster.png").read_bytes()
    assert f"_images/{copied[0].name}" in sections
    assert sorted(p.name for p in tmp_path.rglob("poster.png")) == ["poster.png"], "nothing copied outside the bundle"


def test_an_unresolved_image_is_not_swapped_for_another_file_with_the_same_name(tmp_path):
    """Every FEA case's poster is `fea.mesh.png`: a reference that does not resolve must not be
    served one of the others by a file-name search."""
    from PIL import Image

    src = tmp_path / "doc"
    (src / "00-main").mkdir(parents=True)
    for case in ("a", "b"):
        (src / "00-main" / case).mkdir()
        Image.new("RGB", (4, 4), "red").save(src / "00-main" / case / "fea.mesh.png")
    (src / "00-main" / "main.md").write_text("# First\n\n![Gone](gone/fea.mesh.png){#fig:gone}\n", encoding="utf-8")
    one = OneDoc(src, work_dir=tmp_path / "work")
    out = tmp_path / "site"
    assert one.export_static(out, include_frontend=False)
    assert not list(out.rglob("fea.mesh.png")) and not (out / "_images").exists()
