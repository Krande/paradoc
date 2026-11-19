"""Conditional text: `<!-- if name.attr -->` ... `<!-- else -->` ... `<!-- endif -->`.

A document written once for many objects (one report per analysed object, its values from a filter) often has
text that fits some of them only. A condition keeps the text of the branch its reference's truth says:

```markdown
<!-- if beam.is_slender -->
The member is slender: its buckling resistance governs.
<!-- else -->
The member is stocky.
<!-- endif -->
```

* the reference is a filter attribute (`name.attr`, called with no arguments) or a document variable (`name`);
  `not` before it negates it;
* each marker is an HTML comment on a line of its own; conditions nest;
* markers inside a fenced code block are text, not conditions (a page documenting the syntax shows it);
* a reference that resolves to nothing, an `else` or `endif` without its `if`, or an `if` without its `endif` is
  an error: a document that silently kept the wrong text would be worse than one that does not build.

The pass runs before every other: what a dropped branch holds (`${ ... }` substitutions, figure blocks) is never
resolved.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .errors import SubstitutionError

_IF_RE = re.compile(r"^\s*<!--\s*if\s+(?P<not>not\s+)?(?P<ref>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*-->\s*$")
_ELSE_RE = re.compile(r"^\s*<!--\s*else\s*-->\s*$")
_ENDIF_RE = re.compile(r"^\s*<!--\s*endif\s*-->\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


class ConditionError(SubstitutionError):
    """A condition that cannot be evaluated, or markers that do not pair up."""


def has_conditions(text: str) -> bool:
    """Whether ``text`` has any condition marker at all (a cheap check before :func:`apply_conditions`)."""
    return "<!--" in text and bool(re.search(r"<!--\s*(if|else|endif)\b", text))


def apply_conditions(text: str, evaluate: Callable[[str], Any], where: str = "") -> str:
    """``text`` with each condition replaced by the branch it keeps. ``evaluate(ref)`` gives the value of a
    reference (``name`` or ``name.attr``); its truth decides. ``where`` names the text in error messages."""
    out: list[str] = []
    # Per open condition: (its truth, whether the enclosing text is kept, an else seen).
    stack: list[tuple[bool, bool, bool]] = []
    keep = True
    fence: str | None = None
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        at = f"{where}:{n}" if where else f"line {n}"
        m = _FENCE_RE.match(line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and line.strip() == mark:
                fence = None
        elif fence is None:
            m = _IF_RE.match(line)
            if m:
                truth = False
                if keep:
                    try:
                        truth = bool(evaluate(m["ref"]))
                    except ConditionError:
                        raise
                    except Exception as exc:  # noqa: BLE001 - whatever the lookup says is the reason
                        raise ConditionError(f"{at}: condition {m['ref']!r} cannot be evaluated: {exc}") from exc
                if m["not"]:
                    truth = not truth
                stack.append((truth, keep, False))
                keep = keep and truth
                continue
            if _ELSE_RE.match(line):
                if not stack or stack[-1][2]:
                    raise ConditionError(f"{at}: <!-- else --> without its <!-- if -->")
                truth, outer, _ = stack[-1]
                stack[-1] = (truth, outer, True)
                keep = outer and not truth
                continue
            if _ENDIF_RE.match(line):
                if not stack:
                    raise ConditionError(f"{at}: <!-- endif --> without its <!-- if -->")
                _, keep, _ = stack.pop()
                continue
        if keep:
            out.append(line)
    if stack:
        raise ConditionError(f"{where or 'the text'}: {len(stack)} <!-- if --> without its <!-- endif -->")
    return "".join(out)


__all__ = ["ConditionError", "apply_conditions", "has_conditions"]
