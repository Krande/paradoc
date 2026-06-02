"""`@task` decorator — declarative entry point for paradoc.tasks.

Usage:

    from paradoc.tasks import task

    @task
    def design() -> ada.Assembly:
        ...

    @task(
        parent=design,
        fanout={"geom_repr": ["line", "shell", "solid"], "elem_order": [1, 2]},
        env="meshing",
        skip_if=lambda kw: kw["geom_repr"] == "line" and kw["elem_order"] == 2,
    )
    def mesh(a, *, geom_repr, elem_order) -> ada.Assembly:
        ...

The decorator wraps the function in a `TaskFn`, marks it with a sentinel
attribute so discovery can find it, and registers it on the default
registry. The returned object is still directly callable — `design()` and
`mesh(a, geom_repr="solid", elem_order=2)` work unchanged for testing.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional, Union, overload

from .models import TaskFn
from .registry import get_default_registry

_TASK_MARKER = "__paradoc_task__"


@overload
def task(fn: Callable[..., Any], /) -> TaskFn: ...  # bare @task


@overload
def task(  # @task(...)
    *,
    name: Optional[str] = None,
    parent: Union[Callable[..., Any], str, None] = None,
    consumes: Union[Callable[..., Any], str, None] = None,
    fanout: Optional[dict[str, list[Any]]] = None,
    env: Union[str, Callable[[dict[str, Any]], str], None] = None,
    skip_if: Optional[Callable[..., bool]] = None,
    version_probe: Optional[Callable[[dict[str, Any]], str]] = None,
    depends_on: Optional[list[Callable[..., Any]]] = None,
    serializer: Optional[Any] = None,
    outputs: Optional[Any] = None,
) -> Callable[[Callable[..., Any]], TaskFn]: ...


def task(  # type: ignore[misc]
    fn: Optional[Callable[..., Any]] = None,
    /,
    *,
    name: Optional[str] = None,
    parent: Union[Callable[..., Any], str, None] = None,
    consumes: Union[Callable[..., Any], str, None] = None,
    fanout: Optional[dict[str, list[Any]]] = None,
    env: Union[str, Callable[[dict[str, Any]], str], None] = None,
    skip_if: Optional[Callable[..., bool]] = None,
    version_probe: Optional[Callable[[dict[str, Any]], str]] = None,
    depends_on: Optional[list[Callable[..., Any]]] = None,
    serializer: Optional[Any] = None,
    outputs: Optional[Any] = None,
):
    """Mark a callable as a paradoc task. See module docstring for usage."""

    def decorate(target: Callable[..., Any]) -> TaskFn:
        if consumes is not None and parent is not None:
            raise ValueError(
                f"@task on {target.__name__}: `parent=` and `consumes=` are "
                "mutually exclusive (a task depends on a single parent OR "
                "aggregates over an upstream task, not both)."
            )
        if consumes is not None and fanout:
            raise ValueError(
                f"@task on {target.__name__}: `consumes=` and `fanout=` are "
                "mutually exclusive in v0 (an aggregator task has one cell). "
                "If you need per-axis aggregation, declare multiple "
                "aggregator tasks each filtering the upstream list."
            )
        if outputs is not None and not (callable(outputs) or isinstance(outputs, (list, tuple))):
            raise TypeError(
                f"@task on {target.__name__}: `outputs=` must be a list of "
                f"paths or a callable returning a list, got "
                f"{type(outputs).__name__}."
            )

        task_fn = TaskFn(
            fn=target,
            name=name or target.__name__,
            parent=parent,
            consumes=consumes,
            fanout=fanout or {},
            env=env,
            skip_if=skip_if,
            version_probe=version_probe,
            depends_on=depends_on or [],
            serializer=serializer,
            outputs=outputs,
        )
        # functools.wraps copies __name__, __doc__, __module__, etc. onto
        # the TaskFn so introspection (and the qualname property) behaves
        # like the underlying function.
        functools.update_wrapper(task_fn, target, updated=())
        setattr(task_fn, _TASK_MARKER, True)
        get_default_registry().register(task_fn)
        return task_fn

    if fn is not None:
        # Bare `@task` form: `task` was applied to the function directly.
        return decorate(fn)
    return decorate


def is_task(obj: Any) -> bool:
    """True if `obj` came out of `@task`."""
    return getattr(obj, _TASK_MARKER, False) is True
