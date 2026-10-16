"""Shelf-citation pandoc filter.

Hosts the JSON-AST filter (:mod:`paradoc.citation.filter`) that
wraps `[@key, locator]` citations in `<a href>` links to a shelf
document. Loaded by HTMLExporter and the AST exporter via pandoc's
``--filter`` flag.

The contract: a citation resolves to a stable anchor in the cited
document, falling back to a text find when no anchor is available.
"""

import pathlib

FILTER_PATH = pathlib.Path(__file__).resolve().parent / "filter.py"
"""Absolute path to the filter script. Passed to pandoc via --filter."""
