"""Shelf-citation pandoc filter.

Hosts the JSON-AST filter (:mod:`paradoc.citation.filter`) that
wraps `[@key, locator]` citations in `<a href>` links to a shelf
document. Loaded by HTMLExporter and the AST exporter via pandoc's
``--filter`` flag.

See ``dap/plan/v1/notes_phase_1b_design.md`` for the contract and
decisions.
"""

import pathlib

FILTER_PATH = pathlib.Path(__file__).resolve().parent / "filter.py"
"""Absolute path to the filter script. Passed to pandoc via --filter."""
