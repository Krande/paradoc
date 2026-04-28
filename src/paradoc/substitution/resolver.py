"""Resolve parsed substitutions against a registry.

The resolver is intentionally small: it knows about parse → registry lookup
→ format. The registry interface is `ResolverProtocol`, which Phase 2's
filter registry will satisfy. For Phase 1 we use a `DictResolver` shim that
dispatches `${name}` to in-memory tables, equations, and variables (the
same backing data that the legacy `{{__key__}}` path uses).
"""

from __future__ import annotations

from typing import Any, Protocol

from .errors import SubstitutionError
from .fmtspec import apply_fmtspec
from .parser import Substitution


class ResolverProtocol(Protocol):
    """A registry-like object that can resolve substitutions to strings."""

    def resolve(self, sub: Substitution, *, block: bool = False) -> str:
        """Return the markdown replacement for `sub`."""
        ...

    def known_names(self) -> list[str]:
        """Return all names registered so far (for linter/error suggestions)."""
        ...


class Resolver:
    """A composable resolver that delegates to a chain of named handlers.

    Phase 1 registers tables/plots/variables/equations as handlers; Phase 2
    swaps in the filter registry as the primary handler with this one as
    fallback.
    """

    def __init__(self) -> None:
        self._handlers: list[ResolverProtocol] = []

    def add_handler(self, handler: ResolverProtocol) -> None:
        self._handlers.append(handler)

    def resolve(self, sub: Substitution, *, block: bool = False) -> str:
        last_error: SubstitutionError | None = None
        for handler in self._handlers:
            try:
                return handler.resolve(sub, block=block)
            except KeyError:
                continue
            except SubstitutionError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error

        suggestions = _suggest(sub.name, self.known_names())
        hint = f" (did you mean: {', '.join(suggestions)}?)" if suggestions else ""
        raise SubstitutionError(
            f"no resolver matched ${{ {sub.reference} }}{hint}",
            source=sub.raw,
        )

    def known_names(self) -> list[str]:
        out: list[str] = []
        for handler in self._handlers:
            out.extend(handler.known_names())
        return sorted(set(out))


def format_scalar(value: Any, sub: Substitution) -> str:
    """Apply the substitution's format spec to a scalar value."""
    return apply_fmtspec(value, sub.fmtspec)


def _suggest(name: str, known: list[str], *, max_distance: int = 3, max_count: int = 3) -> list[str]:
    """Return up to `max_count` names within Levenshtein distance `max_distance`."""
    scored: list[tuple[int, str]] = []
    for n in known:
        d = _levenshtein(name, n)
        if d <= max_distance:
            scored.append((d, n))
    scored.sort()
    return [n for _, n in scored[:max_count]]


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1)))
        prev = cur
    return prev[-1]
