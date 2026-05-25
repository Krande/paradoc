"""Cell — a single fanout instance of a task.

The Runner expands each `TaskFn` into one or more cells (one per fanout
coordinate combination, minus skip_if-filtered ones). Cells are what the
executor receives; they carry the task to call, the bound kwargs, and a
back-reference to their parent cell so the runner can thread parent
results into the call.

Cells must be picklable: the future PixiSubprocessExecutor pickles
`(cell, parent_result)` across a subprocess boundary, and the future
NatsExecutor pickles the same payload onto a NATS message. The TaskFn
they hold is picklable because `@task` preserves `__module__` /
`__qualname__` via `functools.update_wrapper`, so the worker can
re-import the function by name. The kwargs dict holds whatever the
fanout matrix declared — typically primitives, all trivially picklable.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .models import TaskFn


@dataclass
class Cell:
    """One fanout instance of a task."""

    task: TaskFn
    kwargs: dict[str, Any] = field(default_factory=dict)
    parent: Optional["Cell"] = None

    @property
    def task_qualname(self) -> str:
        return self.task.qualname

    @property
    def full_kwargs(self) -> dict[str, Any]:
        """Merge this cell's kwargs with every ancestor's, in root-to-leaf order.

        Use case: skip rules that span multiple task levels. For the adapy
        verification matrix, `run_eig` cells need to inspect both their own
        `solver` kwarg AND the mesh's `geom_repr` / `elem_order` to decide
        validity (eg `calculix + line` is unsupported). The runner calls
        `skip_if(**cell.full_kwargs)` so a single predicate can see all
        relevant axes.

        Children override parents on key collision (which is the right
        semantic but should also be vanishingly rare — disjoint axes per
        task is the norm).
        """
        chain: list[Cell] = []
        cell: Optional[Cell] = self
        while cell is not None:
            chain.append(cell)
            cell = cell.parent
        out: dict[str, Any] = {}
        for c in reversed(chain):
            out.update(c.kwargs)
        return out

    @property
    def coords_key(self) -> str:
        """Canonical key for this cell's coordinates.

        Stable across runs as long as the kwargs are JSON-serializable.
        Used for logs and (in the future cache phase) as a hash input.
        Non-JSON values fall back to repr() with a sorted tuple wrapper
        — good enough for stable identifiers, not collision-resistant.
        """
        try:
            return json.dumps(self.kwargs, sort_keys=True, default=str)
        except TypeError:
            return repr(sorted(self.kwargs.items()))

    def __repr__(self) -> str:
        return f"Cell({self.task_qualname} {self.coords_key})"


def expand_fanout(fanout: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    """Yield every cartesian-product combination of fanout kwargs.

    Empty fanout yields a single empty-kwargs dict so tasks with no
    fanout still produce one cell per parent.
    """
    if not fanout:
        yield {}
        return
    keys = list(fanout)
    for combo in itertools.product(*(fanout[k] for k in keys)):
        yield dict(zip(keys, combo))


def cells_for(
    task: TaskFn,
    *,
    parent_cells: list[Optional[Cell]],
) -> list[Cell]:
    """Build the cells for `task`, given the upstream parent cells.

    One cell per (parent_cell, fanout_combo) pair, minus combos rejected
    by `task.skip_if`. If `parent_cells` is empty, the task is a root
    (no parent) — we still produce one cell per fanout combo with
    parent=None.
    """
    if not parent_cells:
        parent_cells = [None]

    cells: list[Cell] = []
    for parent in parent_cells:
        for kwargs in expand_fanout(task.fanout):
            candidate = Cell(task=task, kwargs=kwargs, parent=parent)
            if task.skip_if is not None and task.skip_if(**candidate.full_kwargs):
                continue
            cells.append(candidate)
    return cells
