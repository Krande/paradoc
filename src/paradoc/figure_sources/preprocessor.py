"""Parse and rewrite `<!-- paradoc:figure ... -->` blocks.

Behavior
--------
Each block is matched, its key/value body parsed into a `dict`, validated
into a typed spec, and routed to the matching filter. The filter writes
the assets and returns a `ThreeDView`. The original comment block is
replaced with the markdown rendering of that view (typically an image
reference with `data-3d-key=...`).

Why this is preprocessing-as-comments
-------------------------------------
Pandoc strips HTML comments by default, so any block we miss leaks into
Word/PDF as nothing visible (rather than as garbled text). The
`paradoc:figure` prefix makes the comment's role unambiguous and
disjoint from author comments.
"""

from __future__ import annotations

import re
from typing import Callable

from .models import FigureSourceSpec, create_figure_source

FIGURE_SOURCE_RE = re.compile(
    r"<!--\s*paradoc:figure\s*\n(?P<body>.*?)\n\s*-->",
    re.DOTALL,
)


def _fenced_code_ranges(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` offsets for every fenced-code block.

    Pandoc-flavoured fences: a line of 3+ backticks or 3+ tildes opens,
    and a closing line of *at least* as many of the same character on
    its own (optionally trailing whitespace) closes. We walk line by
    line and track open/close so a doc that documents paradoc's own
    syntax can put a literal ``<!-- paradoc:figure ... -->`` inside a
    code fence without the preprocessor trying to render it.
    """
    ranges: list[tuple[int, int]] = []
    open_char: str | None = None
    open_len: int = 0
    open_offset: int = 0
    cursor = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" ")
        if open_char is None:
            # Look for an opening fence: 3+ of `~` or 3+ of `` ` ``.
            for ch in ("`", "~"):
                if stripped.startswith(ch * 3):
                    n = len(stripped) - len(stripped.lstrip(ch))
                    open_char = ch
                    open_len = n
                    open_offset = cursor
                    break
        else:
            # Inside a fence — look for a matching close (same char,
            # at least as long, nothing but the fence char + optional
            # trailing whitespace on the line).
            line_no_ws = stripped.rstrip()
            if line_no_ws and line_no_ws == open_char * len(line_no_ws) and len(line_no_ws) >= open_len:
                ranges.append((open_offset, cursor + len(line)))
                open_char = None
                open_len = 0
                open_offset = 0
        cursor += len(line)
    # Unclosed fence: treat the rest of the document as inside the
    # fence — same way pandoc handles "missing close" (rendered as one
    # big code block reaching EOF).
    if open_char is not None:
        ranges.append((open_offset, len(text)))
    return ranges


def _is_in_ranges(pos: int, ranges: list[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start <= pos < end:
            return True
    return False


def extract_figure_source_blocks(text: str) -> list[tuple[int, int, str]]:
    """Yield ``(start, end, body)`` tuples for every figure block in ``text``.

    Skips matches that fall inside a fenced code block so documentation
    pages can show literal ``<!-- paradoc:figure ... -->`` examples
    without triggering rendering.
    """
    code_ranges = _fenced_code_ranges(text)
    out: list[tuple[int, int, str]] = []
    for m in FIGURE_SOURCE_RE.finditer(text):
        if _is_in_ranges(m.start(), code_ranges):
            continue
        out.append((m.start(), m.end(), m.group("body").strip()))
    return out


def parse_spec_dict(body: str) -> dict:
    """Parse `key: value` pairs (one per line) from a figure-source block."""
    data: dict = {}
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"figure-source line missing ':': {raw!r}")
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def preprocess_markdown(
    text: str,
    *,
    render_block: Callable[[FigureSourceSpec], str],
) -> str:
    """Rewrite each figure-source block by calling `render_block(spec)`.

    `render_block` is what wires the preprocessor into the rest of the
    pipeline: paradoc passes a callable that runs the appropriate filter
    and returns the markdown to splice in.
    """
    out: list[str] = []
    last = 0
    for start, end, body in extract_figure_source_blocks(text):
        out.append(text[last:start])
        try:
            data = parse_spec_dict(body)
            spec = create_figure_source(data)
            replacement = render_block(spec)
        except Exception as exc:
            replacement = f"<!-- paradoc:figure ERROR: {exc} -->\n" f"`figure-source error: {exc}`"
        out.append(replacement)
        last = end
    out.append(text[last:])
    return "".join(out)
