"""Build-time linter for `${...}` references.

Surfaces unresolved references with close-match suggestions so doc
authors notice typos before the build finishes silently with a literal
`${ name }` left in the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paradoc.substitution import Substitution, find_substitutions
from paradoc.substitution.resolver import _suggest

from .registry import FilterRegistry


@dataclass
class LintIssue:
    """One unresolved substitution found by the linter."""

    path: Path
    sub: Substitution
    suggestions: list[str]


def lint_unresolved_substitutions(
    *,
    md_files: list[Path],
    registry: FilterRegistry,
    extra_known_names: list[str] | None = None,
) -> list[LintIssue]:
    """Return all `${ name(.attr)? }` substitutions that don't resolve."""
    extras = extra_known_names or []
    known = registry.known_names() + list(extras)

    issues: list[LintIssue] = []
    for path in md_files:
        text = path.read_text(encoding="utf-8")
        for sub in find_substitutions(text):
            if sub.name in registry._filters:  # noqa: SLF001
                # Verify attr exists if specified
                if sub.attr is not None:
                    instance = registry._filters[sub.name]  # noqa: SLF001
                    if sub.attr not in instance.list_attrs():
                        issues.append(LintIssue(
                            path=path,
                            sub=sub,
                            suggestions=_suggest(sub.attr, instance.list_attrs()),
                        ))
                continue
            if sub.name in extras:
                continue
            issues.append(LintIssue(
                path=path,
                sub=sub,
                suggestions=_suggest(sub.name, known),
            ))
    return issues
