#!/usr/bin/env python3
"""Pandoc JSON-AST filter that wraps citations in `<a href>` links to shelf.

Invoked by pandoc as ``--filter`` with the contract: read JSON AST from
stdin, write transformed JSON AST to stdout. We walk every ``Cite`` node
and, for citations whose key matches an entry in the configured
bibliography, replace the node with a ``Link`` AST node whose href points
at the shelf attachment URL.

Env contract
~~~~~~~~~~~~

* ``PARADOC_BIBLIOGRAPHY`` — path to a YAML file with a top-level
  ``references:`` list of CSL-style entries (``id``, ``title``, ``URL``).
* ``PARADOC_SHELF_BASE_URL`` — value to substitute for the literal
  ``{shelf_base_url}`` placeholder in each entry's ``URL``.

If the bibliography file is missing or the env var is empty, the filter
is a no-op (every ``Cite`` passes through unchanged) so the same filter
chain works for bundles that opt out of the feature.

Locator parsing
~~~~~~~~~~~~~~~

Pandoc's citation suffix carries the locator (``p. 42``, ``sec. 3.2``,
``eq. (2.5)``, ``table 3.1``) as inline AST nodes. We flatten the
suffix to a plain string and parse with a small regex:

  * page (``p.`` / ``pp.``)            → ``?page=N``
  * everything else (sec/table/eq/fig) → ``?find=<urlencoded>``

The find-fallback is acceptable for v0 because shelf doesn't yet
expose stable anchors per sub-document element
(``[[shelf_subdoc_anchors]]`` in dap/plan/v1).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any, Optional
from urllib.parse import quote

_PAGE_RE = re.compile(r"^pp?\.\s*([0-9][0-9\-, ]*)$", re.IGNORECASE)


def _load_bibliography(path: Optional[str]) -> dict[str, dict[str, Any]]:
    """Load a YAML bibliography into a dict keyed by ``id``."""
    if not path:
        return {}
    p = pathlib.Path(path)
    if not p.is_file():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        # pyyaml is a transitive dep of pandoc/paradoc deployments
        # already; warn (to stderr — stdout is reserved for the AST)
        # and no-op when missing rather than crashing the compile.
        sys.stderr.write(
            "[shelf-citation] pyyaml not installed; skipping bibliography load\n"
        )
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        sys.stderr.write(f"[shelf-citation] failed to parse {path}: {exc}\n")
        return {}
    entries = data.get("references") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        eid = e.get("id")
        if isinstance(eid, str) and eid:
            out[eid] = e
    return out


def _inline_to_text(inlines: list[dict[str, Any]]) -> str:
    """Flatten a list of inline AST nodes to plain text."""
    parts: list[str] = []
    for node in inlines:
        t = node.get("t")
        if t == "Str":
            parts.append(node.get("c", ""))
        elif t == "Space" or t == "SoftBreak":
            parts.append(" ")
        elif t == "LineBreak":
            parts.append("\n")
        elif t in ("Emph", "Strong", "Strikeout", "Subscript", "Superscript",
                   "SmallCaps", "Span", "Quoted"):
            child = node.get("c")
            inner = child[1] if (t == "Span" or t == "Quoted") and isinstance(child, list) and len(child) >= 2 else child
            if isinstance(inner, list):
                parts.append(_inline_to_text(inner))
        elif t == "Code":
            c = node.get("c")
            if isinstance(c, list) and len(c) >= 2:
                parts.append(str(c[1]))
    return "".join(parts).strip()


def _parse_locator(suffix_text: str) -> tuple[Optional[int], Optional[str]]:
    """Return ``(page, raw_locator)`` from a flattened citation suffix.

    ``page`` is an int when the locator is a single page like
    ``p. 42``. Everything else (ranges, sections, tables, equations)
    becomes ``raw_locator`` so the caller can stuff it into ``?find=``.
    """
    if not suffix_text:
        return None, None
    # Strip a leading comma the suffix carries in pandoc's representation.
    s = suffix_text.lstrip(", ").strip()
    if not s:
        return None, None
    m = _PAGE_RE.match(s)
    if m:
        digits = m.group(1).strip()
        if digits.isdigit():
            return int(digits), s
        return None, s
    return None, s


def _build_url(base_url: str, locator_text: Optional[str], page: Optional[int]) -> str:
    """Append URL params for the locator. Page beats free-text find."""
    url = base_url
    if page is not None:
        return _append_query(url, "page", str(page))
    if locator_text:
        return _append_query(url, "find", locator_text)
    return url


def _append_query(url: str, key: str, value: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{key}={quote(value, safe='')}"


def _make_link(href: str, title: str, locator_text: Optional[str]) -> dict[str, Any]:
    """Build a pandoc Link AST node wrapping `[title, locator]` text."""
    text = f"[{title}, {locator_text}]" if locator_text else f"[{title}]"
    return {
        "t": "Link",
        "c": [
            ["", [], []],
            [{"t": "Str", "c": text}],
            [href, ""],
        ],
    }


def _transform_cite(
    cite_node: dict[str, Any],
    bibliography: dict[str, dict[str, Any]],
    shelf_base_url: str,
) -> Optional[dict[str, Any]]:
    """Return the Link replacement for a Cite, or None to leave it as-is."""
    c = cite_node.get("c")
    if not isinstance(c, list) or len(c) < 2:
        return None
    citations = c[0]
    if not citations:
        return None
    first = citations[0]
    cite_id = first.get("citationId")
    if not isinstance(cite_id, str):
        return None
    entry = bibliography.get(cite_id)
    if not entry:
        return None
    url_template = entry.get("URL")
    if not isinstance(url_template, str) or not url_template:
        return None
    url = url_template.replace("{shelf_base_url}", shelf_base_url) if shelf_base_url else url_template
    suffix_inlines = first.get("citationSuffix") or []
    suffix_text = _inline_to_text(suffix_inlines) if isinstance(suffix_inlines, list) else ""
    page, locator_text = _parse_locator(suffix_text)
    href = _build_url(url, locator_text, page)
    title = entry.get("title") or cite_id
    if isinstance(title, list):
        title = _inline_to_text(title)
    return _make_link(href, str(title), locator_text)


def _walk(node: Any, bibliography, shelf_base_url) -> Any:
    """Recursively walk the AST, replacing Cite nodes in place."""
    if isinstance(node, dict):
        if node.get("t") == "Cite":
            replacement = _transform_cite(node, bibliography, shelf_base_url)
            if replacement is not None:
                return replacement
        return {k: _walk(v, bibliography, shelf_base_url) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(item, bibliography, shelf_base_url) for item in node]
    return node


def main() -> int:
    bibliography_path = os.environ.get("PARADOC_BIBLIOGRAPHY", "").strip() or None
    shelf_base_url = os.environ.get("PARADOC_SHELF_BASE_URL", "").strip()

    bibliography = _load_bibliography(bibliography_path)

    try:
        ast = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[shelf-citation] bad input AST: {exc}\n")
        return 2

    if not bibliography:
        # No-op: pass the AST through. Done as a separate code path so
        # the noop case has zero risk of mangling something.
        json.dump(ast, sys.stdout)
        return 0

    transformed = _walk(ast, bibliography, shelf_base_url)
    json.dump(transformed, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
