"""Parser for the unified `${...}` substitution syntax.

Grammar::

    substitution := '${' WS* name ('.' attr)? args? (':' fmtspec)? WS* '}'
    name         := identifier
    attr         := identifier
    args         := '(' ARGS_SRC ')'           # parsed via ast.parse
    argpair      := identifier '=' literal
    literal      := str | int | float | bool | None
    fmtspec      := /[\\d\\.,fFeEgGdD%]+/        # see fmtspec.py for the allowed subset

Design notes
------------
- The body is matched with a non-greedy regex that forbids `}` inside the
  body. String literals containing `}` are therefore not allowed in v1; this
  keeps the tokenizer trivial and avoids ambiguity with markdown attribute
  blocks. We can revisit if a real use case shows up.
- Argument values are parsed via `ast.parse` and validated to be `Constant`
  literals only — this gives us correct typed parsing for free while
  rejecting expressions, name lookups, and anything else that would let a
  doc author execute Python at build time.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from .errors import SubstitutionError

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Match `${...}` substitutions in markdown source. The body cannot contain
# raw `}` because that's our terminator. Escapes/strings-with-`}` are not
# supported in v1.
_SUBSTITUTION_RE = re.compile(r"\$\{([^}]*)\}")

# Quick header pattern: `name`, `name.attr`. Anything after this is args+fmt.
_HEADER_RE = re.compile(
    r"""
    ^\s*
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    (?:\.(?P<attr>[A-Za-z_][A-Za-z0-9_]*))?
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Substitution:
    """A parsed `${...}` substitution reference.

    `raw` is the original text including the `${` and `}` delimiters, so
    callers can do exact string replacement once the resolved value is known.
    """

    name: str
    attr: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)
    fmtspec: str | None = None
    raw: str = ""
    span: tuple[int, int] = (0, 0)

    @property
    def reference(self) -> str:
        """Human-readable form `name` or `name.attr` (no args, no fmt)."""
        return f"{self.name}.{self.attr}" if self.attr else self.name


def find_substitutions(text: str) -> Iterator[Substitution]:
    """Yield each `${...}` substitution found in `text`, in order."""
    for match in _SUBSTITUTION_RE.finditer(text):
        body = match.group(1)
        sub = parse_substitution_body(body, raw=match.group(0), span=match.span())
        yield sub


def parse_substitution_body(
    body: str,
    *,
    raw: str = "",
    span: tuple[int, int] = (0, 0),
) -> Substitution:
    """Parse the inside of a `${...}` block (without the delimiters).

    Raises SubstitutionError on any syntactic issue.
    """
    body = body.rstrip()
    header = _HEADER_RE.match(body)
    if header is None:
        raise SubstitutionError(f"could not parse substitution body {body!r}", source=raw)
    name = header.group("name")
    attr = header.group("attr")
    rest = body[header.end():]

    args_src: str | None = None
    fmtspec: str | None = None

    rest = rest.lstrip()
    if rest.startswith("("):
        depth = 0
        end_idx = -1
        in_str: str | None = None
        for i, ch in enumerate(rest):
            if in_str is not None:
                if ch == "\\":
                    continue
                if ch == in_str:
                    in_str = None
                continue
            if ch in ("'", '"'):
                in_str = ch
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        if end_idx == -1:
            raise SubstitutionError(f"unclosed args list in {body!r}", source=raw)
        args_src = rest[:end_idx]
        rest = rest[end_idx:].lstrip()

    if rest.startswith(":"):
        fmtspec = rest[1:].strip()
        if not fmtspec:
            raise SubstitutionError(f"empty format spec in {body!r}", source=raw)
        rest = ""

    if rest.strip():
        raise SubstitutionError(f"unexpected trailing text {rest!r} in {body!r}", source=raw)

    kwargs = _parse_kwargs(args_src, raw=raw) if args_src is not None else {}

    return Substitution(name=name, attr=attr, kwargs=kwargs, fmtspec=fmtspec, raw=raw, span=span)


def _parse_kwargs(args_src: str, *, raw: str) -> dict[str, Any]:
    """Parse `(k=lit, k2=lit2)` into a dict of literals.

    Uses `ast.parse` for correctness, then walks the AST to ensure
    nothing but `keyword(arg=str, value=Constant)` is present.
    """
    expr_src = f"_{args_src}"
    try:
        tree = ast.parse(expr_src, mode="eval")
    except SyntaxError as exc:
        raise SubstitutionError(f"could not parse args {args_src!r}: {exc.msg}", source=raw) from exc

    call = tree.body
    if not isinstance(call, ast.Call):
        raise SubstitutionError(f"expected kwargs in {args_src!r}", source=raw)

    if call.args:
        raise SubstitutionError("positional arguments are not allowed in substitutions", source=raw)

    out: dict[str, Any] = {}
    for kw in call.keywords:
        if kw.arg is None:
            raise SubstitutionError("**kwargs are not allowed in substitutions", source=raw)
        if not isinstance(kw.value, ast.Constant):
            raise SubstitutionError(
                f"value for {kw.arg!r} must be a literal (str, int, float, bool, or None)",
                source=raw,
            )
        val = kw.value.value
        if not isinstance(val, (str, int, float, bool)) and val is not None:
            raise SubstitutionError(
                f"value for {kw.arg!r} has unsupported type {type(val).__name__}",
                source=raw,
            )
        if kw.arg in out:
            raise SubstitutionError(f"duplicate kwarg {kw.arg!r}", source=raw)
        out[kw.arg] = val
    return out


def is_block_substitution(text: str, sub: Substitution) -> bool:
    """True iff `sub` occupies its enclosing paragraph by itself.

    A "paragraph" is the run of non-blank lines containing the substitution.
    A substitution that is alone on its line, with only whitespace on the
    line and blank lines (or text boundaries) above and below, is treated
    as a block-level replacement.
    """
    start, end = sub.span
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    if line.strip() != sub.raw:
        return False

    above = text[:line_start]
    if above and not above.rstrip(" \t").endswith("\n\n") and above.strip() != "":
        before_line_start = above.rfind("\n", 0, len(above) - 1) + 1
        if above[before_line_start:].strip() != "":
            return False

    below = text[line_end:]
    if below.startswith("\n"):
        below = below[1:]
    if below and below.lstrip(" \t").startswith("\n") is False and below.strip() != "":
        next_nl = below.find("\n")
        next_line = below[: next_nl if next_nl != -1 else len(below)]
        if next_line.strip() != "":
            return False

    return True
