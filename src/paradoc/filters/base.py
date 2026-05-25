"""`Filter` base class and the `@attr` decorator.

Filters are user-authored classes whose `@attr`-decorated methods are
callable from markdown via `${ instance.attr(kwargs) }`. Methods marked
with `@attr` are pure functions of (filter source, args, task output);
the resolver caches results to avoid repeat work within a build.

Tasks are not implemented yet — `task` is reserved for Phase 7. The
`@attr` cache key includes the filter source hash so changes to a method
implementation invalidate cached results.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, ClassVar, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from paradoc.tasks import Task, TaskHandle


_ATTR_MARKER = "__paradoc_attr__"


def attr(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a `Filter` method as a substitution-callable attribute.

    The decorator preserves the function and tags it for the registry.
    Call-time caching is handled by the resolver, not the decorator.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    setattr(wrapper, _ATTR_MARKER, True)
    return wrapper


def _is_attr(obj: Any) -> bool:
    return callable(obj) and getattr(obj, _ATTR_MARKER, False) is True


class Filter:
    """Base for user-authored filter classes.

    Subclass and decorate compute methods with `@attr`. Instances must be
    given a unique `name` used to look them up from markdown. Names
    follow the same identifier rules as Python identifiers (the parser
    enforces this).

    Attributes
    ----------
    name : str
        Unique registry name. By convention matches the variable that
        holds the instance in the project's `filters.py`.
    task : Task | TaskHandle | None
        Optional declarative reference to an upstream task. Two shapes
        are accepted:

        - `TaskHandle.unbound(qualname)` — the modern shape. The Runner
          binds the handle to itself after `run()` finishes (via
          `paradoc.tasks.bind_filter_handles`); the filter then calls
          `self.task.cells(**filter_coords)` to pull live cell results.
        - `Task(...)` — the legacy file-centric BaseModel. Pre-runner
          declarative-only shape kept for backwards compat.
    """

    name: str
    task: Optional[Any]

    # Subclasses may set this to `True` to opt out of strict-arg-validation,
    # e.g. for filters that pass through arbitrary kwargs to a downstream tool.
    relaxed_args: ClassVar[bool] = False

    def __init__(self, name: str, task: Optional[Any] = None) -> None:
        if not name.isidentifier():
            raise ValueError(f"Filter name {name!r} must be a valid Python identifier")
        self.name = name
        self.task = task

    def list_attrs(self) -> list[str]:
        """Return the names of all `@attr`-decorated methods on this instance."""
        return [
            name for name, member in inspect.getmembers(self, predicate=_is_attr)
        ]

    def get_attr_callable(self, attr_name: str) -> Callable[..., Any]:
        """Return the bound `@attr` callable, or raise KeyError."""
        member = getattr(self, attr_name, None)
        if member is None or not _is_attr(member):
            raise KeyError(f"{self.name!r} has no @attr {attr_name!r}")
        return member

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
