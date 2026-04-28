"""Idempotent rewriter from legacy `{{__key__}}` / `{{ var }}` syntax to `${...}`.

Mapping (audited from `paradoc.db.models.TableAnnotation` /
`PlotAnnotation.from_annotation_string`)::

    {{__k__}}                              -> ${ k }
    {{__k__}}{tbl:index:no}                -> ${ k(show_index=False) }
    {{__k__}}{tbl:sortby:c}                -> ${ k(sort_by="c") }
    {{__k__}}{tbl:sortby:c:desc}           -> ${ k(sort_by="c", sort_ascending=False) }
    {{__k__}}{tbl:filter:p}                -> ${ k(filter_pattern="p") }
    {{__k__}}{tbl:filter:p:c}              -> ${ k(filter_pattern="p", filter_column="c") }
    {{__k__}}{tbl:nocaption}               -> ${ k(no_caption=True) }
    {{__k__}}{plt:width:N}                 -> ${ k(width=N) }
    {{__k__}}{plt:height:N}                -> ${ k(height=N) }
    {{__k__}}{plt:nocaption}               -> ${ k(no_caption=True) }
    {{__k__}}{plt:format:f}                -> ${ k(format="f") }
    {{ var }}                              -> ${ var }

The migrator never touches `${...}` content, so running it twice is a no-op.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_LEGACY_KEY_RE = re.compile(r"\{\{__(\w+)__\}\}")
_LEGACY_VAR_RE = re.compile(r"\{\{(?!__)([^{}]+?)\}\}")
_TBL_ANNO_PREFIX = "{tbl:"
_PLT_ANNO_PREFIX = "{plt:"


@dataclass
class MigrationResult:
    """Summary of a single-file migration."""

    path: Path
    changed: bool
    new_content: str
    replacements: int = 0
    warnings: list[str] = field(default_factory=list)


def migrate_text(text: str, *, source: str | None = None) -> tuple[str, int, list[str]]:
    """Return (new_text, n_replacements, warnings) without touching disk.

    `source` is used in warning messages only. Idempotent: text already in
    `${...}` form passes through unchanged.
    """
    warnings: list[str] = []
    out: list[str] = []
    pos = 0
    count = 0

    while pos < len(text):
        m = _LEGACY_KEY_RE.search(text, pos)
        if m is None:
            break
        out.append(text[pos:m.start()])
        key = m.group(1)
        end = m.end()

        kwargs: dict[str, str] = {}
        if text.startswith(_TBL_ANNO_PREFIX, end) or text.startswith(_PLT_ANNO_PREFIX, end):
            anno_close = _find_matching_brace(text, end)
            if anno_close == -1:
                warnings.append(
                    f"unclosed annotation after {{{{__{key}__}}}} at offset {m.start()}"
                    + (f" in {source}" if source else "")
                )
                out.append(text[m.start():end])
                pos = end
                continue
            anno = text[end:anno_close + 1]
            kwargs = _annotation_to_kwargs(anno, warnings=warnings, source=source)
            end = anno_close + 1

        out.append(_render_substitution(key, kwargs))
        pos = end
        count += 1

    out.append(text[pos:])
    rewritten = "".join(out)

    rewritten, var_count = _rewrite_legacy_vars(rewritten)
    count += var_count

    return rewritten, count, warnings


def migrate_file(path: Path, *, dry_run: bool = False) -> MigrationResult:
    """Migrate a single file. With dry_run=True, computes but does not write."""
    text = path.read_text(encoding="utf-8")
    new_text, n, warnings = migrate_text(text, source=str(path))
    changed = new_text != text
    if changed and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return MigrationResult(
        path=path,
        changed=changed,
        new_content=new_text,
        replacements=n,
        warnings=warnings,
    )


def migrate_tree(root: Path, *, dry_run: bool = False) -> list[MigrationResult]:
    """Migrate every `.md` file under `root` (recursive)."""
    results: list[MigrationResult] = []
    for md_path in sorted(root.rglob("*.md")):
        results.append(migrate_file(md_path, dry_run=dry_run))
    return results


def _find_matching_brace(text: str, start: int) -> int:
    """Return index of the `}` closing the `{` at `text[start]`, or -1."""
    if start >= len(text) or text[start] != "{":
        return -1
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _annotation_to_kwargs(
    anno: str, *, warnings: list[str], source: str | None
) -> dict[str, str]:
    """Map a `{tbl:...}` or `{plt:...}` annotation to kwargs for the new syntax."""
    body = anno
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    if body.startswith("tbl:"):
        body = body[4:]
        return _table_flags_to_kwargs(body, warnings=warnings, source=source)
    if body.startswith("plt:"):
        body = body[4:]
        return _plot_flags_to_kwargs(body, warnings=warnings, source=source)
    warnings.append(f"unknown annotation prefix in {anno!r}")
    return {}


def _table_flags_to_kwargs(
    body: str, *, warnings: list[str], source: str | None
) -> dict[str, str]:
    kwargs: dict[str, str] = {}
    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = [t.strip() for t in part.split(":")]
        flag = tokens[0]
        if flag == "index":
            if len(tokens) > 1 and tokens[1].lower() == "no":
                kwargs["show_index"] = "False"
            elif len(tokens) > 1 and tokens[1].lower() == "yes":
                kwargs["show_index"] = "True"
        elif flag == "sortby":
            if len(tokens) > 1:
                kwargs["sort_by"] = _quote(tokens[1])
                if len(tokens) > 2 and tokens[2].lower() == "desc":
                    kwargs["sort_ascending"] = "False"
        elif flag == "filter":
            if len(tokens) > 1:
                kwargs["filter_pattern"] = _quote(tokens[1])
                if len(tokens) > 2:
                    kwargs["filter_column"] = _quote(tokens[2])
        elif flag == "nocaption":
            kwargs["no_caption"] = "True"
        else:
            warnings.append(
                f"unknown table flag {flag!r}" + (f" in {source}" if source else "")
            )
    return kwargs


def _plot_flags_to_kwargs(
    body: str, *, warnings: list[str], source: str | None
) -> dict[str, str]:
    kwargs: dict[str, str] = {}
    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = [t.strip() for t in part.split(":")]
        flag = tokens[0]
        if flag in ("width", "height"):
            if len(tokens) > 1:
                try:
                    int(tokens[1])
                    kwargs[flag] = tokens[1]
                except ValueError:
                    warnings.append(
                        f"non-integer value for {flag} flag: {tokens[1]!r}"
                        + (f" in {source}" if source else "")
                    )
        elif flag == "nocaption":
            kwargs["no_caption"] = "True"
        elif flag == "format":
            if len(tokens) > 1:
                kwargs["format"] = _quote(tokens[1])
        else:
            warnings.append(
                f"unknown plot flag {flag!r}" + (f" in {source}" if source else "")
            )
    return kwargs


def _quote(s: str) -> str:
    """Render `s` as a quoted string literal for the new syntax."""
    if '"' not in s:
        return f'"{s}"'
    if "'" not in s:
        return f"'{s}'"
    escaped = s.replace('"', '\\"')
    return f'"{escaped}"'


def _render_substitution(name: str, kwargs: dict[str, str]) -> str:
    if not kwargs:
        return f"${{ {name} }}"
    args = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    return f"${{ {name}({args}) }}"


def _rewrite_legacy_vars(text: str) -> tuple[str, int]:
    """Translate `{{ name }}` (no `__`) into `${ name }`.

    Bails out for content that contains `|` (pipe-style flags from the
    legacy generic substitutor) — there's no general mapping for those, so
    we leave them alone and let the doc author resolve manually.
    """
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        body = match.group(1).strip()
        if "|" in body:
            return match.group(0)
        if not body.replace("_", "").replace(".", "").replace("(", "").replace(")", "").isalnum():
            return match.group(0)
        count += 1
        return f"${{ {body} }}"

    new_text = _LEGACY_VAR_RE.sub(repl, text)
    return new_text, count
