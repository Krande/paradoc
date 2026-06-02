"""Filter registry: maps name → Filter instance and resolves attr calls.

Two ways instances enter the registry:

1. **Manual** — a doc author instantiates a `Filter` subclass in their
   `filters.py` (e.g. `eig_main = EigenResults(name="eig_main")`) and
   the discovery loader registers them.
2. **Auto** — when an OneDoc-managed table or plot lands in the DB, the
   registry mirrors it as an anonymous `TableFilter` / `PlotFilter` so
   `${ my_table }` resolves through the same machinery as user filters.

Auto-registered filters use the same key as the underlying DB row.
Conflicts (a user-defined filter with the same name as a DB key) raise
at registration time, since silent shadowing would be confusing.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional

from .base import Filter
from .cache import AttrCache


class FilterRegistry:
    """Registry of named filter instances."""

    def __init__(self) -> None:
        self._filters: dict[str, Filter] = {}
        self._cache = AttrCache()

    # ---------------- registration ----------------

    def register(self, instance: Filter) -> None:
        """Register a named filter instance. Raises on duplicate names."""
        if instance.name in self._filters:
            existing = self._filters[instance.name]
            if existing is instance:
                return
            raise ValueError(
                f"Filter name {instance.name!r} is already registered " f"(existing: {existing!r}, new: {instance!r})"
            )
        self._filters[instance.name] = instance

    def unregister(self, name: str) -> None:
        self._filters.pop(name, None)

    def clear(self) -> None:
        self._filters.clear()
        self._cache.clear()

    # ---------------- lookup ----------------

    def get(self, name: str) -> Optional[Filter]:
        return self._filters.get(name)

    def known_names(self) -> list[str]:
        return sorted(self._filters)

    # ---------------- resolution ----------------

    def call_attr(self, name: str, attr_name: str, kwargs: dict[str, Any]) -> Any:
        """Look up a filter and invoke its attribute, with caching."""
        instance = self._filters.get(name)
        if instance is None:
            raise KeyError(f"no filter registered as {name!r}")
        callable_ = instance.get_attr_callable(attr_name)
        _validate_args(callable_, kwargs, instance)

        def compute() -> Any:
            return callable_(**kwargs)

        return self._cache.get_or_compute(
            filter_name=name,
            attr_name=attr_name,
            args=kwargs,
            filter_cls=type(instance),
            compute=compute,
        )


def _validate_args(callable_: Callable, kwargs: dict[str, Any], instance: Filter) -> None:
    """Reject unexpected kwargs unless the filter is `relaxed_args`."""
    if instance.relaxed_args:
        return
    sig = inspect.signature(callable_)
    accepted = set(sig.parameters.keys())
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    if has_var_keyword:
        return
    extra = set(kwargs) - accepted
    if extra:
        raise TypeError(
            f"unexpected keyword argument(s) {sorted(extra)!r} for "
            f"{instance.name}.{callable_.__name__} "
            f"(accepts: {sorted(accepted - {'self'})!r})"
        )
