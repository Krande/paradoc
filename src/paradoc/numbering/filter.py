#!/usr/bin/env python3
"""Pandoc JSON filter: give every top-level heading its chapter label.

Runs in front of pandoc-crossref (with ``chapters: true``, ``chaptersDepth: 1``). Each
top-level heading gets a ``label`` attribute -- "1", "2", ... in the main body, then "A",
"B", ... after the ``\\appendix`` marker -- which pandoc-crossref uses as the chapter prefix of
every figure, table and equation number below it ("Figure 6.3", "Table A.1").

The counting matches the heading numbers the web reader shows: every top-level heading counts,
and the appendix lettering starts at "A" at the marker. A heading that already carries a
``label`` keeps it (and still counts).

With the metadata flag ``paradoc-number-headings: true`` it also writes every heading's number
into its text ("1.2 Title", "Appendix A Title"), for writers that cannot number headings (ODT).

Self-contained on purpose: pandoc runs it as a separate process, so it imports nothing from
paradoc.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Iterable, Iterator


def appendix_letter(n: int) -> str:
    """1 -> "A", 26 -> "Z", 27 -> "AA" (spreadsheet-column style)."""
    if n < 1:
        raise ValueError(f"appendix number must be >= 1, got {n}")
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _is_appendix_marker(block: Any) -> bool:
    if not isinstance(block, dict) or block.get("t") != "RawBlock":
        return False
    c = block.get("c")
    return isinstance(c, list) and len(c) >= 2 and isinstance(c[1], str) and "\\appendix" in c[1]


def _h1_attrs(block: Any) -> list | None:
    """The Attr of a level-1 Header block, else None."""
    if isinstance(block, dict) and block.get("t") == "Header":
        c = block.get("c")
        if isinstance(c, list) and len(c) >= 3 and c[0] == 1 and isinstance(c[1], list):
            return c[1]
    return None


def chapter_labels(blocks: Iterable[Any]) -> Iterator[tuple[list, str, bool]]:
    """Yield ``(attr, label, is_appendix)`` for each top-level heading, in document order."""
    main = 0
    app = 0
    in_appendix = False
    for block in blocks:
        if _is_appendix_marker(block):
            in_appendix = True
            continue
        attr = _h1_attrs(block)
        if attr is None:
            continue
        if in_appendix:
            app += 1
            yield attr, appendix_letter(app), True
        else:
            main += 1
            yield attr, str(main), False


def label_chapters(ast: dict) -> dict:
    """Stamp a ``label`` attribute on each top-level heading of a pandoc JSON AST (in place)."""
    for attr, label, _ in chapter_labels(ast.get("blocks") or []):
        # Attr = [id, [classes], [[key, value], ...]]
        if len(attr) < 3 or not isinstance(attr[2], list):
            continue
        if any(isinstance(kv, list) and kv and kv[0] == "label" for kv in attr[2]):
            continue
        attr[2].append(["label", label])
    return ast


#: Metadata key that switches on :func:`number_headings` in the filter script. Formats that
#: number headings themselves (the web reader, Word's heading styles, LaTeX) leave it off.
NUMBER_HEADINGS_KEY = "paradoc-number-headings"

#: Text before a top-level appendix heading's letter, as the web reader and the Word template
#: ("Appendix %1") show it.
APPENDIX_PREFIX = "Appendix"


def _is_unnumbered(attr: list) -> bool:
    return isinstance(attr[1], list) and "unnumbered" in attr[1]


def heading_numbers(blocks: Iterable[Any]) -> Iterator[tuple[dict, str, bool]]:
    """Yield ``(header_block, number, is_appendix)`` for each numbered heading, in document order.

    The scheme of the web reader and the Word template: "1", "1.1", "1.1.1" in the main body;
    "A", "A.1", "A.1.1" after the ``\\appendix`` marker, each appendix restarting the sub-counts.
    A heading with the ``unnumbered`` class (``{-}``) gets no number and does not count, as in
    LaTeX. A level-1 heading that carries a ``label`` attribute uses it as its number.
    """
    main = [0] * 6
    app = [0] * 6
    in_appendix = False
    for block in blocks:
        if _is_appendix_marker(block):
            in_appendix = True
            continue
        if not (isinstance(block, dict) and block.get("t") == "Header"):
            continue
        level, attr = block["c"][0], block["c"][1]
        if not isinstance(level, int) or not 1 <= level <= 6 or _is_unnumbered(attr):
            continue
        counters = app if in_appendix else main
        counters[level - 1] += 1
        for i in range(level, 6):
            counters[i] = 0
        first = appendix_letter(counters[0]) if in_appendix and counters[0] else str(counters[0])
        if level == 1:
            label = next((kv[1] for kv in attr[2] if isinstance(kv, list) and kv and kv[0] == "label"), None)
            if label:
                first = label
        yield block, ".".join([first, *(str(n) for n in counters[1:level])]), in_appendix


def number_headings(ast: dict) -> dict:
    """Write each heading's number in front of its text (in place): "1.2 Title", "A.1 Title",
    and "Appendix A Title" for a top-level appendix heading.

    For writers that cannot number headings themselves (ODT: pandoc's writer has no section
    numbering, and an appendix letter is beyond any outline numbering). The number is a ``Span``
    of class ``header-section-number``, as pandoc's own ``--number-sections`` makes in HTML.
    """
    for block, number, is_appendix in heading_numbers(ast.get("blocks") or []):
        text = f"{APPENDIX_PREFIX} {number}" if is_appendix and block["c"][0] == 1 else number
        words = text.split(" ")
        inlines: list = []
        for i, word in enumerate(words):
            if i:
                inlines.append({"t": "Space"})
            inlines.append({"t": "Str", "c": word})
        span = {"t": "Span", "c": [["", ["header-section-number"], []], inlines]}
        block["c"][2] = [span, {"t": "Space"}, *block["c"][2]]
    return ast


def _meta_true(meta: dict, key: str) -> bool:
    value = meta.get(key)
    if not isinstance(value, dict):
        return False
    if value.get("t") == "MetaBool":
        return bool(value.get("c"))
    if value.get("t") == "MetaInlines":  # `-M key=true` on older pandocs
        return "".join(i.get("c", "") for i in value.get("c", []) if i.get("t") == "Str").lower() in ("true", "yes")
    if value.get("t") == "MetaString":
        return str(value.get("c")).lower() in ("true", "yes")
    return False


def _read_ast() -> Any:
    # pandoc pipes UTF-8 JSON; text-mode stdio would decode it with the locale codec (cp1252 on Windows).
    return json.loads(sys.stdin.buffer.read().decode("utf-8"))


def _write_ast(ast: Any) -> None:
    sys.stdout.buffer.write(json.dumps(ast, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.flush()


def main() -> int:
    try:
        ast = _read_ast()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"[paradoc-chapters] bad input AST: {exc}\n")
        return 2
    label_chapters(ast)
    if _meta_true(ast.get("meta") or {}, NUMBER_HEADINGS_KEY):
        number_headings(ast)
    _write_ast(ast)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
