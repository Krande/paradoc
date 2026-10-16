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
