"""In-memory cache for `@attr` results within a single build.

The cache key is `(filter_name, attr, args_hash, source_hash)`:

- `filter_name` and `attr` identify the call site.
- `args_hash` covers the kwargs (literals only — see `parser._parse_kwargs`).
- `source_hash` covers the AST of the specific filter class definition so
  edits to a method invalidate any stale cached value.

Persistent caching (across builds, in sqlite) is a Phase 9 polish; the
resolver doesn't depend on it for correctness.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import textwrap
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttrCache:
    """A small per-build cache for `@attr` call results."""

    _store: dict[tuple[str, str, str, str], Any] = field(default_factory=dict)
    _source_hash_cache: dict[type, str] = field(default_factory=dict)

    def get_or_compute(
        self,
        *,
        filter_name: str,
        attr_name: str,
        args: dict[str, Any],
        filter_cls: type,
        compute: Any,
    ) -> Any:
        """Return cached value or run `compute()` and store the result."""
        args_hash = _hash_args(args)
        source_hash = self._source_hash(filter_cls, attr_name)
        key = (filter_name, attr_name, args_hash, source_hash)
        if key in self._store:
            return self._store[key]
        value = compute()
        self._store[key] = value
        return value

    def clear(self) -> None:
        self._store.clear()
        self._source_hash_cache.clear()

    def _source_hash(self, filter_cls: type, attr_name: str) -> str:
        """Hash the AST of `filter_cls.<attr_name>` (not the whole class)."""
        cache_key = (filter_cls, attr_name)
        # We deliberately key on (cls, attr) so unrelated edits to other
        # methods on the same class don't invalidate this attr's cache.
        cached = self._source_hash_cache.get(cache_key)  # type: ignore[arg-type]
        if cached is not None:
            return cached
        try:
            source = inspect.getsource(getattr(filter_cls, attr_name))
        except (OSError, TypeError, AttributeError):
            # Builtins / dynamically generated / class-level missing
            # (subclasses can expose @attr-marked methods only on the
            # instance via __getattr__) → fall back to an unstable hash
            # that still varies with the qualname so different classes
            # don't share entries.
            digest = hashlib.sha256(f"{filter_cls.__qualname__}.{attr_name}".encode()).hexdigest()
            self._source_hash_cache[cache_key] = digest  # type: ignore[index]
            return digest
        try:
            tree = ast.parse(textwrap.dedent(source))
            normalized = ast.dump(tree, annotate_fields=False, include_attributes=False)
        except SyntaxError:
            normalized = source
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        self._source_hash_cache[cache_key] = digest  # type: ignore[index]
        return digest


def _hash_args(args: dict[str, Any]) -> str:
    """Stable hash of literal-only kwargs."""
    canonical = json.dumps(args, sort_keys=True, default=repr)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
