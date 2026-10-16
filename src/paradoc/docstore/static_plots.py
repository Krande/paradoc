"""Layout of the per-plot files in a static export.

A static export (and the ``static/`` directory of a published bundle) used to carry every
Plotly figure in one ``plots.json``. The reader fetched and parsed all of it before the first
figure could go interactive, although every plot first shows as its static image. The export now
also writes:

* ``plots_index.json`` -- ``{key: {file, caption, width, height, plot_type}}``, small enough to
  fetch at load, so the reader knows which figures can switch to interactive;
* ``_plots/<file>.json`` -- one figure each, fetched when a reader asks for it.

``plots.json`` is still written, so readers and tools that know only the bulk file keep working.
Bundles published before the split have only ``plots.json``; the server derives the index and the
per-plot payloads from it (see :func:`index_from_bulk`).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

PLOT_INDEX_FILE = "plots_index.json"
PLOT_DIR = "_plots"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")


def plot_file_name(key: str) -> str:
    """Bundle-relative path of one plot's JSON file.

    Keys that are not plain file names (path separators, spaces, very long keys, a leading dot)
    are hashed, so a key can never escape ``_plots/`` or collide with another file.
    """
    name = key if _SAFE_NAME.match(key) and not key.startswith(".") else hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"{PLOT_DIR}/{name}.json"


def index_entry(key: str, plot: Mapping[str, Any]) -> dict[str, Any]:
    """The index row for one plot: everything but the (large) figure itself."""
    return {
        "file": plot_file_name(key),
        "caption": plot.get("caption", ""),
        "width": plot.get("width"),
        "height": plot.get("height"),
        "plot_type": plot.get("plot_type"),
    }


def index_from_bulk(plots: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build the plot index from a monolithic ``plots.json`` dict."""
    return {key: index_entry(key, plot) for key, plot in plots.items()}


def compact_json(obj: Any) -> str:
    """JSON for the reader: no indentation, no spaces after separators.

    Pretty-printed section and plot files were ~4.5x the size of the compact form; nothing reads
    them by eye, and the reader parses either.
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
