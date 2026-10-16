"""Lazy plot endpoints: ``<doc>/plots-index`` and ``<doc>/plots/{key}/figure``.

The reader fetches the small index at load and one plot's figure when it goes interactive. New
bundles carry ``static/plots_index.json`` + ``static/_plots/<key>.json``; bundles published
before that have only ``static/plots.json`` and are served out of it.
"""

import json

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from paradoc.docstore import LocalDocStore, write_manifest  # noqa: E402
from paradoc.docstore.static_plots import (  # noqa: E402
    PLOT_INDEX_FILE,
    compact_json,
    index_from_bulk,
    plot_file_name,
)
from paradoc.serve import create_app  # noqa: E402

PLOTS = {
    "sine": {"key": "sine", "plot_type": "line", "figure": {"data": [{"y": [0, 1, 0]}]}, "caption": "Sine"},
    "bars": {"key": "bars", "plot_type": "bar", "figure": {"data": [{"type": "bar"}]}, "caption": "Bars"},
}


def _single_doc_bundle(tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "static").mkdir(parents=True)
    write_manifest(bundle, doc_id="doc")
    (bundle / "paradoc.sqlite").touch()  # marks the root as a single-doc bundle
    return bundle


def _bundle(tmp_path, *, split: bool):
    bundle = _single_doc_bundle(tmp_path)
    static = bundle / "static"
    # A legacy bundle as it was published: pretty-printed bulk file only.
    (static / "plots.json").write_text(json.dumps(PLOTS, indent=2), encoding="utf-8")
    if split:
        for key, plot in PLOTS.items():
            p = static / plot_file_name(key)
            p.parent.mkdir(exist_ok=True)
            p.write_text(compact_json(plot), encoding="utf-8")
        (static / PLOT_INDEX_FILE).write_text(compact_json(index_from_bulk(PLOTS)), encoding="utf-8")
    return bundle


@pytest.mark.parametrize("split", [True, False], ids=["split", "legacy-bulk"])
def test_plot_index_lists_keys_without_figures(tmp_path, split):
    client = TestClient(create_app(doc_store=LocalDocStore(_bundle(tmp_path, split=split))))
    res = client.get("/api/docs/doc/plots-index")
    assert res.status_code == 200
    index = res.json()
    assert set(index) == {"sine", "bars"}
    assert index["sine"]["caption"] == "Sine"
    assert index["sine"]["file"] == "_plots/sine.json"
    assert "figure" not in index["sine"]


@pytest.mark.parametrize("split", [True, False], ids=["split", "legacy-bulk"])
def test_plot_figure_serves_one_plot(tmp_path, split):
    client = TestClient(create_app(doc_store=LocalDocStore(_bundle(tmp_path, split=split))))
    res = client.get("/api/docs/doc/plots/bars/figure")
    assert res.status_code == 200
    assert res.json() == PLOTS["bars"]
    assert client.get("/api/docs/doc/plots/nope/figure").status_code == 404


def test_plot_index_empty_without_plots(tmp_path):
    bundle = _single_doc_bundle(tmp_path)
    client = TestClient(create_app(doc_store=LocalDocStore(bundle)))
    assert client.get("/api/docs/doc/plots-index").json() == {}
    assert client.get("/api/docs/doc/plots/sine/figure").status_code == 404


def test_plot_figure_key_cannot_escape_static(tmp_path):
    bundle = _bundle(tmp_path, split=True)
    (bundle / "secret.json").write_text('{"x": 1}', encoding="utf-8")
    client = TestClient(create_app(doc_store=LocalDocStore(bundle)))
    # A key that is not a plain file name maps to a hashed file name, never a path.
    assert client.get("/api/docs/doc/plots/..%2F..%2Fsecret/figure").status_code == 404
    assert plot_file_name("../../secret").startswith("_plots/")
    assert "/" not in plot_file_name("a/b")[len("_plots/") :]


def test_local_store_static_file_bytes_stays_in_static(tmp_path):
    bundle = _bundle(tmp_path, split=True)
    (bundle / "outside.json").write_text("{}", encoding="utf-8")
    store = LocalDocStore(bundle)
    assert store.get_static_file_bytes("doc", PLOT_INDEX_FILE) is not None
    assert store.get_static_file_bytes("doc", "../outside.json") is None
