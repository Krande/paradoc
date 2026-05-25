"""Runner — walks a TaskRegistry, expands fanout, executes via Executor.

The Runner is the single piece of orchestration code in paradoc.tasks. It:

1. Topologically orders the registered tasks by parent reference.
2. Expands each task's fanout matrix into Cells (one per parent x fanout
   combination, with `skip_if` rejections dropped).
3. Submits each cell to the configured Executor and awaits the result,
   threading the parent cell's result into the child call.
4. Stores results keyed by Cell identity so downstream tasks +
   TaskHandle.cells() lookups can read them.

Scope kept narrow for the v0 cut: no cache (Q4), no subprocess isolation
(Q8 Option B is enabled by the executor swap, not the runner), no
version_probe folding (waits for the cache phase that needs it). What it
does ship is the seam every later feature plugs into.

Filter-side wiring (`Filter.task = TaskHandle(...)`) reads from the
runner via `runner.cells_for(task, **filter_coords)`. There's no
module-level singleton runner — multiple concurrent builds each
construct their own. The filter resolver will be passed the active
runner when the integration lands.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .cache import CacheKey, TaskCache, compute_cache_key
from .cells import Cell, expand_fanout
from .config import merge_fanout
from .executors import Executor, InProcessExecutor
from .models import TaskFn
from .registry import TaskRegistry

logger = logging.getLogger(__name__)


class Runner:
    """Walks a TaskRegistry, expands cells, drives the Executor."""

    def __init__(
        self,
        registry: TaskRegistry,
        executor: Optional[Executor] = None,
        cache: Optional[TaskCache] = None,
        fanout_overrides: Optional[dict[str, dict[str, list[Any]]]] = None,
    ) -> None:
        self.registry = registry
        self.executor = executor if executor is not None else InProcessExecutor()
        self.cache = cache
        # task qualname (or bare name) -> { axis: [values] }
        # Per-axis replacement, not merge — see config.merge_fanout.
        self.fanout_overrides: dict[str, dict[str, list[Any]]] = fanout_overrides or {}
        # qualname -> list[Cell]
        self._cells_by_task: dict[str, list[Cell]] = {}
        # id(Cell) -> result
        self._results: dict[int, Any] = {}
        # id(Cell) -> CacheKey (populated lazily, top-down, only if cache set)
        self._cache_keys: dict[int, CacheKey] = {}
        # id(TaskFn) -> bytes (ast hash memo, reused across all cells of a task)
        self._ast_hash_memo: dict[int, bytes] = {}
        self._expanded = False
        self._ran = False
        # Counters for observability of cache hit-rate.
        self.cache_hits = 0
        self.cache_misses = 0

    # ---------------- expansion ----------------

    def expand(self) -> None:
        """Build the cell DAG without running anything.

        Safe to call separately from `run()` for tooling that wants to
        introspect the matrix (eg `paradoc inspect-cells`). Idempotent.
        """
        if self._expanded:
            return
        self.registry.validate()
        for task in self._topo_sorted():
            if task.consumes is not None:
                upstream_task = self.registry.resolve_consumes(task)
                upstream_cells = list(self._cells_by_task.get(upstream_task.qualname, []))
                self._cells_by_task[task.qualname] = self._aggregator_cells_for_task(
                    task, upstream_cells
                )
            else:
                parent_task = self.registry.resolve_parent(task)
                parent_cells: list[Optional[Cell]]
                if parent_task is None:
                    parent_cells = []
                else:
                    parent_cells = list(self._cells_by_task.get(parent_task.qualname, []))
                self._cells_by_task[task.qualname] = self._cells_for_task(task, parent_cells)
        self._expanded = True

    def _cells_for_task(self, task: TaskFn, parent_cells: list[Optional[Cell]]) -> list[Cell]:
        """Inline cell-building with profile fanout overrides applied.

        We don't reuse `cells.cells_for(...)` here because the override
        layer is per-runner state; the module-level helper stays
        runner-agnostic for direct use.
        """
        if not parent_cells:
            parent_cells = [None]

        override = self.fanout_overrides.get(task.qualname) or self.fanout_overrides.get(task.name)
        resolved = merge_fanout(task.fanout, override)

        cells: list[Cell] = []
        for parent in parent_cells:
            for kwargs in expand_fanout(resolved):
                candidate = Cell(task=task, kwargs=kwargs, parent=parent)
                if task.skip_if is not None and task.skip_if(**candidate.full_kwargs):
                    continue
                cells.append(candidate)
        return cells

    def _aggregator_cells_for_task(self, task: TaskFn, upstream_cells: list[Cell]) -> list[Cell]:
        """Build the single cell for an aggregator task.

        `consumes` and `fanout` are mutually exclusive in v0 (validated at
        decoration time), so an aggregator always produces exactly one
        cell. skip_if is honored too — when the upstream task produced
        zero cells, the aggregator can opt out cleanly via
        `skip_if=lambda upstream: not upstream` if that's the right
        semantic for its body.
        """
        candidate = Cell(task=task, kwargs={}, upstream=list(upstream_cells))
        if task.skip_if is not None:
            # Aggregator skip predicates take the upstream list, not kwargs.
            try:
                should_skip = task.skip_if(upstream_cells)
            except TypeError:
                # Fall back to no-args predicate for symmetry with regular
                # tasks that use skip_if=lambda **kw: ...
                should_skip = task.skip_if(**candidate.full_kwargs)
            if should_skip:
                return []
        return [candidate]

    def cells_for(self, task: TaskFn | str, **filter_coords: Any) -> list[Cell]:
        """Return cells of `task` whose kwargs match all `filter_coords`.

        `task` accepts either the TaskFn itself, its qualname, or its
        bare name (decouples filters from specific module paths). Filter
        coords with no match yield an empty list; the filter resolver
        treats that as "no cell selected" and may either error or render
        a placeholder per author preference.
        """
        if not self._expanded:
            self.expand()
        if isinstance(task, TaskFn):
            qualname = task.qualname
        elif task in self._cells_by_task:
            qualname = task
        else:
            qualname = self._resolve_bare_name(task)
        cells = self._cells_by_task.get(qualname, [])
        if not filter_coords:
            return list(cells)
        return [c for c in cells if all(c.kwargs.get(k) == v for k, v in filter_coords.items())]

    def _resolve_bare_name(self, name: str) -> str:
        """Map a bare task name to its qualname. Returns `name` unchanged
        if no match — caller gets an empty cells list, which is the right
        shape for downstream filter rendering."""
        for t in self.registry.all_tasks():
            if t.name == name:
                return t.qualname
        return name

    # ---------------- execution ----------------

    def run(self) -> dict[str, list[Any]]:
        """Execute every cell in topological order. Returns qualname -> results.

        If a TaskCache is wired, each cell's result is keyed via
        `compute_cache_key` (Q4 Option C — AST source hash + call-graph
        walk + parent_key + version_probe). Cache hits short-circuit the
        executor entirely; misses run normally and write back.
        """
        self.expand()
        for task in self._topo_sorted():
            for cell in self._cells_by_task[task.qualname]:
                # Resolve the body's first-positional input:
                # - aggregator: list of upstream results, Nones filtered out
                # - regular task with a parent: single result (or None)
                # - root task: None
                if cell.upstream:
                    upstream_results = [
                        self._results[id(uc)]
                        for uc in cell.upstream
                        if id(uc) in self._results
                    ]
                    parent_result: Any = [r for r in upstream_results if r is not None]
                else:
                    parent_result = (
                        self._results.get(id(cell.parent)) if cell.parent is not None else None
                    )

                if self.cache is not None:
                    parent_key = (
                        self._cache_keys.get(id(cell.parent)) if cell.parent is not None else None
                    )
                    upstream_keys = (
                        [self._cache_keys[id(uc)] for uc in cell.upstream if id(uc) in self._cache_keys]
                        if cell.upstream
                        else None
                    )
                    key = compute_cache_key(
                        cell.task,
                        cell.kwargs,
                        parent_key=parent_key,
                        upstream_keys=upstream_keys,
                        ast_hash_memo=self._ast_hash_memo,
                    )
                    self._cache_keys[id(cell)] = key
                    serializer = cell.task.serializer  # None => cache default
                    if self.cache.has(key, serializer=serializer):
                        self._results[id(cell)] = self.cache.get(key, serializer=serializer)
                        self.cache_hits += 1
                        logger.debug(f"cache hit  {key!r}")
                        continue
                    self.cache_misses += 1
                    logger.debug(f"cache miss {key!r}")

                future = self.executor.submit(cell, parent_result)
                result = future.result()
                self._results[id(cell)] = result

                if self.cache is not None:
                    parent_key = (
                        self._cache_keys.get(id(cell.parent)) if cell.parent is not None else None
                    )
                    version_probe_val: Optional[str] = None
                    if cell.task.version_probe is not None:
                        try:
                            version_probe_val = str(cell.task.version_probe(cell.kwargs))
                        except Exception:  # noqa: BLE001
                            version_probe_val = None
                    self.cache.put(
                        self._cache_keys[id(cell)],
                        result,
                        kwargs=cell.kwargs,
                        parent_key=parent_key,
                        version_probe=version_probe_val,
                        serializer=cell.task.serializer,
                    )
        self._ran = True
        return {
            qn: [self._results[id(c)] for c in cells]
            for qn, cells in self._cells_by_task.items()
        }

    def result_for(self, cell: Cell) -> Any:
        """Look up a previously-computed result. Raises if cell wasn't run."""
        key = id(cell)
        if key not in self._results:
            raise KeyError(f"no result recorded for {cell!r}; did you call run()?")
        return self._results[key]

    def shutdown(self) -> None:
        """Release executor resources."""
        self.executor.shutdown()

    # ---------------- helpers ----------------

    def _topo_sorted(self) -> list[TaskFn]:
        """Tasks ordered so every upstream dep appears earlier in the list.

        Upstream = `parent` OR `consumes` (whichever the task declared;
        they're mutually exclusive).
        """
        tasks = self.registry.all_tasks()
        # Build adjacency: child -> upstream qualname (parent or consumes).
        parent_of: dict[str, Optional[str]] = {}
        for t in tasks:
            p = self.registry.resolve_dependency(t)
            parent_of[t.qualname] = p.qualname if p else None

        # Kahn's algorithm: roots first, then anyone whose parent is
        # already resolved.
        resolved: list[TaskFn] = []
        remaining = dict(parent_of)
        by_qn: dict[str, TaskFn] = {t.qualname: t for t in tasks}
        ready = [qn for qn, p in remaining.items() if p is None]
        # Stable order: sort the initial roots and each batch of newly-ready
        # tasks by qualname so the same registry produces the same plan.
        ready.sort()
        while ready:
            cur = ready.pop(0)
            resolved.append(by_qn[cur])
            del remaining[cur]
            newly_ready = sorted(qn for qn, p in remaining.items() if p == cur)
            ready.extend(newly_ready)
            for qn in newly_ready:
                remaining[qn] = None  # mark "no remaining parent dep" so we don't re-list it
        if remaining:
            # validate() catches cycles, so this should be unreachable; defensive.
            raise RuntimeError(f"topological sort stalled, unresolved: {sorted(remaining)!r}")
        return resolved
