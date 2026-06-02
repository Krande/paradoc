"""Aggregator tasks (`@task(consumes=...)`).

N:1 dependency: one aggregator cell sees every upstream cell's result.
Used for comparison tables / plots / anything that folds over a fanout
matrix. The body's first arg is the list of upstream results, Nones
filtered out by the runner.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paradoc.tasks import (
    Runner,
    TaskCache,
    TaskRegistry,
    compute_cache_key,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


def _build_registry() -> TaskRegistry:
    """design -> fanout {geom_repr: [...], elem_order: [1, 2]} mesh
    -> aggregator that consumes mesh"""
    reg = TaskRegistry()

    @task
    def design():
        return {"v": 1}

    @task(parent=design, fanout={"geom_repr": ["line", "shell", "solid"], "elem_order": [1, 2]})
    def mesh(a, *, geom_repr, elem_order):
        return {**a, "geom_repr": geom_repr, "elem_order": elem_order}

    @task(consumes=mesh)
    def all_mesh_results(results):
        return {"count": len(results), "first": results[0] if results else None}

    for t in (design, mesh, all_mesh_results):
        reg.register(t)
    reset_default_registry()
    return reg


# ---------------- decorator validation ----------------


def test_decorator_rejects_parent_and_consumes_combined():
    @task
    def upstream():
        return None

    with pytest.raises(ValueError, match="mutually exclusive"):

        @task(parent=upstream, consumes=upstream)
        def bad(_):
            pass


def test_decorator_rejects_consumes_and_fanout_combined():
    @task
    def upstream():
        return None

    with pytest.raises(ValueError, match="mutually exclusive in v0"):

        @task(consumes=upstream, fanout={"x": [1, 2]})
        def bad(results, *, x):
            pass


# ---------------- expansion ----------------


def test_aggregator_produces_one_cell():
    reg = _build_registry()
    runner = Runner(reg)
    runner.expand()

    agg_cells = runner.cells_for("all_mesh_results")
    assert len(agg_cells) == 1
    assert agg_cells[0].kwargs == {}
    assert agg_cells[0].parent is None
    # upstream points at all 6 mesh cells (3 geoms x 2 orders)
    assert len(agg_cells[0].upstream) == 6


def test_aggregator_with_empty_upstream_still_one_cell():
    """Aggregator on a task that produces zero cells still gets one cell —
    its body sees an empty list. skip_if can opt out."""
    reg = TaskRegistry()

    @task(fanout={"x": []})  # empty fanout = zero cells
    def empty(*, x):
        return x

    @task(consumes=empty)
    def agg(results):
        return len(results)

    reg.register(empty)
    reg.register(agg)
    reset_default_registry()

    runner = Runner(reg)
    runner.expand()
    cells = runner.cells_for("agg")
    assert len(cells) == 1
    assert cells[0].upstream == []


def test_aggregator_skip_if_takes_upstream_list():
    """skip_if for an aggregator receives the upstream list, not kwargs."""
    reg = TaskRegistry()

    @task(fanout={"x": [1, 2]})
    def upstream(*, x):
        return x

    @task(consumes=upstream, skip_if=lambda upstream_cells: len(upstream_cells) < 5)
    def agg(results):
        return len(results)

    reg.register(upstream)
    reg.register(agg)
    reset_default_registry()

    runner = Runner(reg)
    runner.expand()
    # skip_if says "skip if fewer than 5 upstream"; we have 2, so cell dropped.
    assert runner.cells_for("agg") == []


# ---------------- execution ----------------


def test_aggregator_receives_filtered_upstream_results():
    """Nones from upstream are filtered before reaching the aggregator body."""
    reg = TaskRegistry()

    @task(fanout={"x": [1, 2, 3]})
    def upstream(*, x):
        # Return None for x=2; the runner should drop it from the agg input.
        return None if x == 2 else x * 10

    @task(consumes=upstream)
    def agg(results):
        return sorted(results)

    reg.register(upstream)
    reg.register(agg)
    reset_default_registry()

    runner = Runner(reg)
    runner.run()
    [agg_cell] = runner.cells_for("agg")
    assert runner.result_for(agg_cell) == [10, 30]


def test_aggregator_end_to_end():
    reg = _build_registry()
    runner = Runner(reg)
    runner.run()
    [agg_cell] = runner.cells_for("all_mesh_results")
    result = runner.result_for(agg_cell)
    assert result["count"] == 6
    assert result["first"]["v"] == 1


# ---------------- caching ----------------


def test_aggregator_cache_key_folds_in_upstream_keys(tmp_path: Path):
    """Changing any upstream cell's content should invalidate the aggregator."""
    reg = _build_registry()
    cache = TaskCache(tmp_path)

    runner1 = Runner(reg, cache=cache)
    runner1.run()
    [first_agg] = runner1.cells_for("all_mesh_results")
    first_key = runner1._cache_keys[id(first_agg)]

    # Second run with the same registry: aggregator hits cache.
    runner2 = Runner(reg, cache=cache)
    runner2.run()
    [second_agg] = runner2.cells_for("all_mesh_results")
    second_key = runner2._cache_keys[id(second_agg)]
    assert second_key.digest == first_key.digest
    assert runner2.cache_hits >= 1  # aggregator hit


def test_aggregator_cache_key_responds_to_upstream_keys():
    """Same task body + same fanout but DIFFERENT upstream cache keys
    must produce a different aggregator cache key. Tests the
    upstream_keys parameter of compute_cache_key directly."""
    from paradoc.tasks import CacheKey

    @task(consumes="upstream")
    def agg(results):
        return len(results)

    upstream_keys_v1 = [
        CacheKey(qualname="upstream", digest=b"\x01" * 32),
        CacheKey(qualname="upstream", digest=b"\x02" * 32),
    ]
    upstream_keys_v2 = [
        CacheKey(qualname="upstream", digest=b"\x01" * 32),
        CacheKey(qualname="upstream", digest=b"\x99" * 32),  # one upstream changed
    ]
    k1 = compute_cache_key(agg, {}, upstream_keys=upstream_keys_v1)
    k2 = compute_cache_key(agg, {}, upstream_keys=upstream_keys_v2)
    assert k1.digest != k2.digest


def test_aggregator_cache_key_order_independent():
    """Two upstream lists with the same digests in different order
    must produce the SAME aggregator cache key."""
    from paradoc.tasks import CacheKey

    @task(consumes="upstream")
    def agg(results):
        return len(results)

    keys_a = [
        CacheKey(qualname="upstream", digest=b"\x01" * 32),
        CacheKey(qualname="upstream", digest=b"\x02" * 32),
    ]
    keys_b = list(reversed(keys_a))  # same content, reversed order
    k1 = compute_cache_key(agg, {}, upstream_keys=keys_a)
    k2 = compute_cache_key(agg, {}, upstream_keys=keys_b)
    assert k1.digest == k2.digest


def test_aggregator_topo_order_after_consumes():
    """Aggregators come after their consumed upstream in topo order."""
    reg = _build_registry()
    runner = Runner(reg)
    sorted_tasks = runner._topo_sorted()
    qualnames = [t.qualname for t in sorted_tasks]
    assert qualnames.index("tasks.test_aggregator.design") < qualnames.index("tasks.test_aggregator.mesh")
    assert qualnames.index("tasks.test_aggregator.mesh") < qualnames.index("tasks.test_aggregator.all_mesh_results")
