"""Bind a FilterRegistry's TaskHandles to a populated Runner.

Filters declared at module import time can't carry a runner reference
(no runner exists yet). The convention is to store
`TaskHandle.unbound(qualname)` on `Filter.task`; after `Runner.run()`
finishes, the controlling code calls `bind_filter_handles` to point
every handle at the runner that just produced its results.

After binding, `Filter.task.cells(**filter_coords)` resolves through
the runner's expanded cell DAG.

Strict-failure stance: a handle whose `qualname` doesn't appear in the
runner's registry raises. Silently rendering nothing for an unresolved
task is worse than a build-time error — the latter is fixable, the
former produces broken docs.
"""

from __future__ import annotations

from typing import Any

from .models import TaskHandle
from .runner import Runner


def bind_filter_handles(filter_registry: Any, runner: Runner) -> int:
    """Walk `filter_registry`, bind every TaskHandle to `runner`.

    Returns the number of handles bound. Filters with `task=None` or a
    non-TaskHandle `task` value (eg the legacy `Task` BaseModel) are
    skipped silently — the legacy shape was always declarative-only and
    has no runtime hook to wire.
    """
    bound = 0
    known = set(runner.registry.known_qualnames())
    for name in filter_registry.known_names():
        instance = filter_registry.get(name)
        handle = getattr(instance, "task", None)
        if not isinstance(handle, TaskHandle):
            continue
        if handle.qualname not in known and not _matches_bare_name(handle.qualname, runner):
            raise KeyError(
                f"filter {name!r} declares task={handle.qualname!r}, "
                f"but no such task is registered. "
                f"Known tasks: {sorted(known)!r}"
            )
        handle._runner = runner
        bound += 1
    return bound


def _matches_bare_name(qualname: str, runner: Runner) -> bool:
    """Allow filter authors to reference tasks by bare name when the
    full qualname would couple their filter to a specific module path."""
    return any(t.name == qualname for t in runner.registry.all_tasks())
