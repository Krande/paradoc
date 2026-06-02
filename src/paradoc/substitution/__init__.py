"""Unified substitution syntax: `${ name(.attr)?(args)?(:fmt)? }`.

This package replaces the legacy `{{__key__}}` / `{{ variable }}` /
`{tbl:...}` / `{plt:...}` substitution forms. The legacy parser still
runs as a deprecated fallback (see `paradoc.document._perform_variable_substitution`).
"""

from .errors import SubstitutionError
from .fmtspec import apply_fmtspec, validate_fmtspec
from .parser import Substitution, find_substitutions, parse_substitution_body
from .resolver import Resolver, ResolverProtocol

__all__ = [
    "Substitution",
    "SubstitutionError",
    "find_substitutions",
    "parse_substitution_body",
    "apply_fmtspec",
    "validate_fmtspec",
    "Resolver",
    "ResolverProtocol",
]
