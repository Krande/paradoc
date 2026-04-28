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


def extract_figure_source_blocks(text: str) -> list[tuple[int, int, str]]:
    """Yield `(start, end, body)` tuples for every figure block in `text`."""
    out: list[tuple[int, int, str]] = []
    for m in FIGURE_SOURCE_RE.finditer(text):
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
            replacement = (
                f"<!-- paradoc:figure ERROR: {exc} -->\n"
                f"`figure-source error: {exc}`"
            )
        out.append(replacement)
        last = end
    out.append(text[last:])
    return "".join(out)
