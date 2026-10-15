#!/usr/bin/env python3
"""Pandoc JSON filter: give every top-level heading its chapter label.

Runs in front of pandoc-crossref (with ``chapters: true``, ``chaptersDepth: 1``). Each
top-level heading gets a ``label`` attribute -- "1", "2", ... in the main body, then "A",
"B", ... after the ``\\appendix`` marker -- which pandoc-crossref uses as the chapter prefix of
every figure, table and equation number below it ("Figure 6.3", "Table A.1").

The counting matches the heading numbers the web reader shows: every top-level heading counts,
and the appendix lettering starts at "A" at the marker. A heading that already carries a
``label`` keeps it (and still counts).

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


def main() -> int:
    try:
        ast = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[paradoc-chapters] bad input AST: {exc}\n")
        return 2
    json.dump(label_chapters(ast), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
