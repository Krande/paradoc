"""Chapter-scoped numbering of figures, tables and equations.

With chapter numbering on (the default), every caption and every reference to it carries the
number of the top-level heading it sits under, and the counter restarts at each new top-level
heading: "Figure 6.3", "Table 2.1". After the ``\\appendix`` marker the chapter part is the
appendix letter instead: "Figure A.2", "Table B.1".

The numbers are produced once, for the whole document, by pandoc-crossref (``chapters: true``,
``chaptersDepth: 1``). The one thing pandoc-crossref does not know is the appendix lettering, so
:mod:`paradoc.numbering.filter` runs in front of it and stamps every top-level heading with an
explicit ``label`` attribute ("1", "2", ..., then "A", "B", ...). pandoc-crossref uses that label
as the chapter prefix. Captions and references in the pandoc output -- the static HTML, the PDF,
and the JSON AST the web reader renders -- therefore all agree, and nothing downstream has to
count figures (the web reader only ever sees part of the document at once).

The DOCX export numbers its captions with Word fields instead (``STYLEREF`` of the heading +
``SEQ ... \\s 1``), which gives the same "6.3" / "A.2" result once Word updates the fields.
"""

from __future__ import annotations

import pathlib

from .filter import appendix_letter, chapter_labels, label_chapters

FILTER_PATH = pathlib.Path(__file__).resolve().parent / "filter.py"
"""Absolute path to the pandoc JSON filter. Must run *before* pandoc-crossref."""

#: pandoc ``-M`` arguments that switch pandoc-crossref to chapter-prefixed numbering.
CROSSREF_CHAPTER_ARGS = ("-M", "chapters=true", "-M", "chaptersDepth=1")


def crossref_filters(chapter_numbering: bool) -> list[str]:
    """The filter chain up to and including pandoc-crossref."""
    if chapter_numbering:
        return [str(FILTER_PATH), "pandoc-crossref"]
    return ["pandoc-crossref"]


def crossref_args(chapter_numbering: bool) -> list[str]:
    """Extra pandoc arguments for the chosen numbering scheme."""
    return list(CROSSREF_CHAPTER_ARGS) if chapter_numbering else []


__all__ = [
    "FILTER_PATH",
    "CROSSREF_CHAPTER_ARGS",
    "appendix_letter",
    "chapter_labels",
    "crossref_args",
    "crossref_filters",
    "label_chapters",
]
