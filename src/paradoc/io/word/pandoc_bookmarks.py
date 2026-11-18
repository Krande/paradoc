"""Give pandoc's DOCX bookmarks and internal links back the identifiers they were made from.

Since pandoc 3.12 the DOCX writer no longer uses an element's identifier as its bookmark name.
Every name starts with ``_`` (hidden from screen readers), and an identifier that is not a valid
Word bookmark name -- anything with a ``:`` or ``-`` in it, so every pandoc-crossref id such as
``fig:trends``, ``tbl:metrics`` or ``eq:basic`` -- is replaced by ``_`` plus the last 39 hex
digits of its SHA-1. Internal links (``w:hyperlink/@w:anchor``) are rewritten the same way.

The DOCX post-processing finds equations by their ``eq:`` bookmarks and converts pandoc-crossref's
links to ``fig:``/``tbl:``/``eq:`` anchors into REF fields, so with pandoc >= 3.12 it found no
equations and no links. Pandoc's rule is deterministic, so the original names can be recovered
for every identifier the source declares or references; this maps them back right after pandoc
writes each file, which makes the output look the way it did with earlier pandoc versions.
Names that match no known identifier are left alone, and output from older pandoc is unchanged.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from paradoc.config import logger

#: An identifier given in an attribute block: ``{#fig:trends}``, ``{#tbl:x .class key=value}``.
_ATTR_ID = re.compile(r"\{[^{}\n]*?#([^\s{}]+)")
#: A citation-style reference: ``@fig:trends``, ``[@eq:basic; @eq:derived]``. The key must end
#: in a word character, as pandoc drops trailing punctuation from a key.
_CITE_ID = re.compile(r"(?<![\w@])@(\w(?:[\w:.#$%&+?<>~/-]*\w)?)")

_BOOKMARK_NAME = re.compile(r'(<w:bookmarkStart\b[^>]*?\bw:name=")([^"]*)(")')
_LINK_ANCHOR = re.compile(r'(<w:hyperlink\b[^>]*?\bw:anchor=")([^"]*)(")')


def pandoc_bookmark_name(identifier: str) -> str:
    """The bookmark name pandoc >= 3.12 writes for ``identifier`` (its ``toBookmarkName``)."""
    if len(identifier) < 40 and all(c.isalnum() or c == "_" for c in identifier):
        return "_" + identifier
    # A SHA-1 is 40 hex digits; pandoc drops the first to make room for the "_".
    return "_" + hashlib.sha1(identifier.encode("utf-8")).hexdigest()[1:]


def identifiers_in_markdown(text: str) -> set[str]:
    """Every identifier ``text`` declares (``{#id}``) or references (``@id``)."""
    return set(_ATTR_ID.findall(text)) | set(_CITE_ID.findall(text))


def restore_pandoc_bookmark_names(docx_path: str | os.PathLike, identifiers: Iterable[str]) -> int:
    """Rename bookmarks and link anchors in ``docx_path`` that pandoc derived from ``identifiers``
    back to the identifiers themselves. Returns the number of names restored."""
    aliases = {pandoc_bookmark_name(i): i for i in identifiers if i}
    # A name that already is its identifier (older pandoc) needs nothing.
    aliases = {alias: ident for alias, ident in aliases.items() if alias != ident}
    if not aliases:
        return 0

    restored = 0

    def _sub(m: re.Match) -> str:
        nonlocal restored
        ident = aliases.get(m.group(2))
        if ident is None:
            return m.group(0)
        restored += 1
        return m.group(1) + escape(ident, {'"': "&quot;"}) + m.group(3)

    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path) as zin:
        entries = []
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                before = restored
                text = _LINK_ANCHOR.sub(_sub, _BOOKMARK_NAME.sub(_sub, data.decode("utf-8")))
                if restored != before:
                    data = text.encode("utf-8")
            entries.append((info, data))

    if restored:
        fd, tmp = tempfile.mkstemp(suffix=".docx", dir=docx_path.parent)
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for info, data in entries:
                    zout.writestr(info, data)
            os.replace(tmp, docx_path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        logger.debug(f"[WordExporter] Restored {restored} pandoc bookmark names in {docx_path.name}")

    return restored
