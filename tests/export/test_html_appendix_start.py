"""The web reader letters the appendices from the first appendix heading: its text as the reader shows it."""

from __future__ import annotations

import re

from paradoc import OneDoc
from paradoc.filters import Filter, attr


class Part(Filter):
    @attr
    def title(self) -> str:
        return 'Beam "B1" & co'


def test_the_appendix_start_is_the_headings_shown_text(tmp_path):
    root = tmp_path / "doc"
    (root / "00-main").mkdir(parents=True)
    (root / "01-app").mkdir(parents=True)
    (root / "00-main" / "main.md").write_text("# Main {#sec:main}\n\nText.\n", encoding="utf-8")
    # A substitution and a label in the heading: the reader shows neither as written.
    (root / "01-app" / "app.md").write_text("# Part ${ part.title } {#sec:part}\n\nMore.\n", encoding="utf-8")
    one = OneDoc(root, work_dir=tmp_path / "work")
    one.add_filter(Part("part"))
    one.compile("Out", export_format="html")
    html = next((tmp_path / "work").rglob("Out.html")).read_text(encoding="utf-8")
    m = re.search(r'<meta name="data-appendix-start" content="([^"]*)">', html)
    assert m, "the appendix start is given"
    assert m.group(1) == "Part Beam &quot;B1&quot; &amp; co"
