"""Substitution-specific errors."""

from __future__ import annotations


class SubstitutionError(ValueError):
    """Raised when a `${...}` body fails to parse or resolve.

    The error message is intended to be shown directly to a doc author,
    so it should describe the offending substitution and what was wrong.
    """

    def __init__(self, message: str, source: str | None = None, position: int | None = None) -> None:
        self.source = source
        self.position = position
        if source is not None and position is not None:
            super().__init__(f"{message} (at offset {position} in {source!r})")
        elif source is not None:
            super().__init__(f"{message} (in {source!r})")
        else:
            super().__init__(message)
