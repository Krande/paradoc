"""Task-tree models.

Two unrelated shapes live here:

- `TaskFn` / `TaskHandle` — the new declarative task primitive built around
  `@task`-decorated callables. This is what `paradoc.tasks` is being grown
  into now.
- `LegacyTaskSpec` (formerly `Task`) — the original file-centric placeholder
  from the early plan. Kept for backwards compat with `Filter.task` and the
  `FEAModelResults.task_id` reference; will be removed once the new shape is
  the canonical reference.

Neither is executed by the runtime yet. Decoration collects metadata; the
runner that turns metadata into a DAG execution lives in the next phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field


# Sentinel for "no value supplied" so callers can pass None explicitly.
_UNSET: Any = object()


@dataclass
class TaskFn:
    """Runtime representation of a `@task`-decorated callable.

    Holds the original function plus everything the runner needs to plan
    a DAG execution: parent reference, fanout matrix, env alias, skip
    predicate, version-probe callable, explicit depends_on.

    Created by `@task(...)`; collected by the registry as the module is
    imported. The runner (next phase) walks the registry, expands fanout,
    evaluates skip_if, and constructs the DAG.
    """

    fn: Callable[..., Any]
    name: str
    parent: Union[Callable[..., Any], str, None] = None
    fanout: dict[str, list[Any]] = field(default_factory=dict)
    env: Union[str, Callable[[dict[str, Any]], str], None] = None
    skip_if: Optional[Callable[..., bool]] = None
    version_probe: Optional[Callable[[dict[str, Any]], str]] = None
    depends_on: list[Callable[..., Any]] = field(default_factory=list)

    @property
    def qualname(self) -> str:
        """Stable identifier for cache keys / DAG nodes."""
        mod = getattr(self.fn, "__module__", "?")
        return f"{mod}.{self.name}"

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Direct invocation runs the original function unchanged.

        The runner uses this same path; @task does not interpose execution
        logic at call time. Cache + fanout + subprocess handling happen
        upstream of the function call, not inside it.
        """
        return self.fn(*args, **kwargs)


@dataclass
class TaskHandle:
    """Lightweight reference to a TaskFn, bound to a Runner.

    What filters store in `Filter.task`. Created by the Runner during
    build setup once the cell DAG is expanded; filters then call
    `.cells(**filter_coords)` to pull the cells that match their
    pin/override coords (Q1 hybrid).

    The `_runner` back-reference is set by the Runner factory; if
    `cells()` is called before binding, raises with a clear message.
    Filters that need a TaskHandle at module import time can use
    `TaskHandle.unbound(qualname)` and the resolver will bind it later.
    """

    qualname: str
    _runner: Optional[Any] = None  # Runner — Any to avoid circular import

    def cells(self, **filter_coords: Any) -> "list[Any]":
        """Return cells matching the filter coords. Runner-backed."""
        if self._runner is None:
            raise RuntimeError(
                f"TaskHandle({self.qualname!r}) is unbound; "
                f"the Runner must bind it before cells() is callable. "
                f"This happens automatically during a paradoc build."
            )
        return self._runner.cells_for(self.qualname, **filter_coords)

    @classmethod
    def unbound(cls, qualname: str) -> "TaskHandle":
        """Create a handle without a runner; the resolver binds it later."""
        return cls(qualname=qualname, _runner=None)


# ---------------------------------------------------------------------------
# Legacy file-centric Task — retained for the in-tree test that locks its
# shape and for Filter.task's type annotation. Slated for removal once the
# new TaskHandle is the canonical Filter.task reference.
# ---------------------------------------------------------------------------


class LegacyTaskSpec(BaseModel):
    """Original file-centric task placeholder (renamed from `Task`).

    Predates the decorator-based primitive. Authors should migrate to
    `@task` + `TaskHandle`; this class will be removed in a future cut.
    """

    name: str = Field(..., description="Unique identifier (used for caching and logs).")
    inputs: list[str] = Field(default_factory=list, description="Input files / globs.")
    outputs: list[str] = Field(default_factory=list, description="Expected output files / globs.")
    env_lock: Optional[Path] = Field(
        default=None,
        description="Lockfile pinning the script execution environment.",
    )
    solver_version: Optional[str] = Field(
        default=None,
        description="Version pin for the simulation solver, if any.",
    )
    depends_on: list[str] = Field(default_factory=list, description="Upstream task names.")

    model_config = {"frozen": False}


# Public name for the legacy spec until consumers migrate.
Task = LegacyTaskSpec
