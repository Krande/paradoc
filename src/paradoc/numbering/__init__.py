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

In a PDF, pandoc-crossref hands figure, table and equation numbers to LaTeX, so the PDF export
adds :func:`latex_numbering_header` (``\\counterwithin``) for the same "6.3" / "A.2" numbers.

Headings follow one scheme in every format: "1", "1.1", "1.1.1" in the main body and "A", "A.1",
"A.1.1" in the appendices, a top-level appendix heading reading "Appendix A". The web reader
numbers them itself, Word through the template's heading list styles, LaTeX through
``--number-sections`` and ``\\appendix``; for ODT, whose writer cannot, the filter writes the
numbers into the heading text (:func:`number_headings`, switched on by
:data:`NUMBER_HEADINGS_ARGS`).
"""

from __future__ import annotations

import pathlib

from .filter import (
    APPENDIX_PREFIX,
    NUMBER_HEADINGS_KEY,
    appendix_letter,
    chapter_labels,
    heading_numbers,
    label_chapters,
    number_headings,
)

FILTER_PATH = pathlib.Path(__file__).resolve().parent / "filter.py"
"""Absolute path to the pandoc JSON filter. Must run *before* pandoc-crossref."""

#: pandoc ``-M`` arguments that switch pandoc-crossref to chapter-prefixed numbering.
CROSSREF_CHAPTER_ARGS = ("-M", "chapters=true", "-M", "chaptersDepth=1")

#: pandoc ``-M`` arguments that make the filter write heading numbers into the heading text.
NUMBER_HEADINGS_ARGS = ("-M", f"{NUMBER_HEADINGS_KEY}=true")


def crossref_filters(chapter_numbering: bool, number_headings: bool = False) -> list[str]:
    """The filter chain up to and including pandoc-crossref. ``number_headings``: the export
    also needs the filter for its heading numbers (with :data:`NUMBER_HEADINGS_ARGS`)."""
    if chapter_numbering or number_headings:
        return [str(FILTER_PATH), "pandoc-crossref"]
    return ["pandoc-crossref"]


def crossref_args(chapter_numbering: bool) -> list[str]:
    """Extra pandoc arguments for the chosen numbering scheme."""
    return list(CROSSREF_CHAPTER_ARGS) if chapter_numbering else []


def latex_numbering_header(chapter_numbering: bool) -> str:
    """LaTeX preamble lines that give the PDF the numbering of the other formats.

    pandoc-crossref leaves figure, table and equation numbers to LaTeX in a PDF, and LaTeX counts
    them through the whole document. ``\\counterwithin`` makes them "<section>.<n>", restarting at
    every top-level heading -- "Figure 3.2", and "Figure A.1" after ``\\appendix``, which letters
    the sections. A top-level appendix heading reads "Appendix A Title", as in the web reader
    and the Word template; references to it and its contents keep the bare letter.
    """
    # \paradoc@numbering: a document's own LaTeX can test for it (\@ifundefined) to stand down a
    # stop-gap for paradoc versions that did not number the PDF this way.
    lines = ["\\makeatletter", "\\def\\paradoc@numbering{}"]
    if chapter_numbering:
        lines += [
            "\\counterwithin{figure}{section}",
            "\\counterwithin{table}{section}",
            "\\counterwithin{equation}{section}",
        ]
    lines += [
        "\\def\\paradoc@secprefix@section{}",
        f"\\g@addto@macro\\appendix{{\\gdef\\paradoc@secprefix@section{{{APPENDIX_PREFIX}~}}}}",
        "\\renewcommand\\@seccntformat[1]{\\csname paradoc@secprefix@#1\\endcsname\\csname the#1\\endcsname\\quad}",
        "\\makeatother",
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "APPENDIX_PREFIX",
    "FILTER_PATH",
    "CROSSREF_CHAPTER_ARGS",
    "NUMBER_HEADINGS_ARGS",
    "NUMBER_HEADINGS_KEY",
    "appendix_letter",
    "chapter_labels",
    "crossref_args",
    "crossref_filters",
    "heading_numbers",
    "label_chapters",
    "latex_numbering_header",
    "number_headings",
]
