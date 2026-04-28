"""Format-spec subset for `${expr:fmt}` substitutions.

We deliberately accept a small, safe subset of Python's mini-language
rather than passing arbitrary specs into `format()`. This keeps user-
authored format strings predictable and rejects exotic forms that would
make the substitution grammar harder to evolve later.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import SubstitutionError

_ALLOWED = re.compile(
    r"""
    ^(?:
        \.\d+[fFeEgG]      # .Nf, .Ne, .Ng (fixed/scientific/general w/ precision)
      | \d*[dD]            # integer
      | ,d                 # thousands-separated integer
      | ,\.\d+[fF]         # thousands-separated float w/ precision
      | %                  # percentage
      | \.\d+%             # percentage with precision
    )$
    """,
    re.VERBOSE,
)


def validate_fmtspec(fmtspec: str) -> None:
    """Raise SubstitutionError if `fmtspec` is outside the allowed subset."""
    if not _ALLOWED.match(fmtspec):
        raise SubstitutionError(
            f"unsupported format spec {fmtspec!r}; allowed: .Nf, .Ne, .Ng, d, ,d, ,.Nf, %, .N%"
        )


def apply_fmtspec(value: Any, fmtspec: str | None) -> str:
    """Format `value` according to `fmtspec`, or return `str(value)` if None.

    Raises SubstitutionError if `fmtspec` is outside the allowed subset, or
    if `format(value, fmtspec)` itself fails (e.g. spec/type mismatch).
    """
    if fmtspec is None:
        return str(value)
    validate_fmtspec(fmtspec)
    try:
        return format(value, fmtspec)
    except (TypeError, ValueError) as exc:
        raise SubstitutionError(f"failed to format {value!r} with spec {fmtspec!r}: {exc}") from exc
