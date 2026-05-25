"""Runner + Executor + Cell tests.

Synthetic design->mesh->analyze pipeline mirrors the adapy verification
shape (Assembly = a tagged dict for the test). Validates fanout
expansion, skip_if filtering, parent-result threading, topological
order, and the Executor swap point that later phases (pixi subprocess /
NATS dispatch) plug into.
"""

from __future__ import annotations

from concurrent.futures import Future
from typing import Any

import pytest

from paradoc.tasks import (
    Cell,
    InProcessExecutor,
    Runner,
    TaskHandle,
    TaskRegistry,
    cells_for,
    expand_fanout,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- Cell + fanout primitives ----------------


def test_expand_fanout_empty_yields_one_empty():
    assert list(expand_fanout({})) == [{}]


def test_expand_fanout_cartesian_product():
    out = list(expand_fanout({"a": [1, 2], "b": ["x", "y"]}))
    assert {"a": 1, "b": "x"} in out
    assert {"a": 2, "b": "y"} in out
    assert len(out) == 4


def test_cells_for_no_parent_no_fanout():
    @task
    def root():
        return "r"

    cells = cells_for(root, parent_cells=[])
    assert len(cells) == 1
    assert cells[0].task is root
    assert cells[0].kwargs == {}
    assert cells[0].parent is None


def test_cells_for_skip_if_filters():
    @task
    def root():
        return None

    @task(parent=root, fanout={"x": [1, 2, 3]}, skip_if=lambda x: x == 2)
    def child(_p, *, x):
        return x

    cells = cells_for(child, parent_cells=[Cell(task=root)])
    xs = sorted(c.kwargs["x"] for c in cells)
    assert xs == [1, 3]


# ---------------- InProcessExecutor ----------------


def test_executor_propagates_result():
    @task
    def root():
        return 42

    ex = InProcessExecutor()
    cell = Cell(task=root)
    future = ex.submit(cell, parent_result=None)
    assert future.result() == 42


def test_executor_propagates_exception():
    @task
    def boom():
        raise ValueError("nope")

    ex = InProcessExecutor()
    cell = Cell(task=boom)
    future = ex.submit(cell, parent_result=None)
    assert isinstance(future, Future)
    with pytest.raises(ValueError, match="nope"):
        future.result()


def test_executor_threads_parent_result():
    @task
    def child(parent, *, scale):
        return parent * scale

    ex = InProcessExecutor()
    cell = Cell(task=child, kwargs={"scale": 3})
    future = ex.submit(cell, parent_result=10)
    assert future.result() == 30


# ---------------- Runner end-to-end ----------------


def _build_synthetic_registry() -> TaskRegistry:
    """design -> mesh (fanout geom_repr x elem_order, skip line+o2)
       -> analyze (fanout solver, all kept).

    Mirrors the adapy verification topology without depending on adapy.
    """
    reg = TaskRegistry()

    @task
    def design():
        return {"name": "assembly", "version": 1}

    @task(
        parent=design,
        fanout={"geom_repr": ["line", "shell", "solid"], "elem_order": [1, 2]},
        skip_if=lambda geom_repr, elem_order: geom_repr == "line" and elem_order == 2,
    )
    def mesh(a, *, geom_repr, elem_order):
        return {**a, "geom_repr": geom_repr, "elem_order": elem_order}

    @task(parent=mesh, fanout={"solver": ["abaqus", "calculix"]})
    def analyze(a, *, solver):
        return {**a, "solver": solver, "freqs": [1.0, 2.0, 3.0]}

    # Move all three onto the fresh registry (decoration put them on
    # the default registry; for isolation we copy and clear).
    for t in (design, mesh, analyze):
        reg.register(t)
    reset_default_registry()
    return reg


def test_runner_expand_topology_and_cell_counts():
    reg = _build_synthetic_registry()
    runner = Runner(reg)
    runner.expand()

    # design: 1 cell
    design_cells = runner.cells_for("tasks.test_runner.design")
    assert len(design_cells) == 1

    # mesh: 3 geom x 2 order = 6, minus 1 skip (line + o2) = 5
    mesh_cells = runner.cells_for("tasks.test_runner.mesh")
    assert len(mesh_cells) == 5

    # analyze: 5 mesh parents x 2 solvers = 10
    analyze_cells = runner.cells_for("tasks.test_runner.analyze")
    assert len(analyze_cells) == 10


def test_runner_cells_for_filter_coords():
    reg = _build_synthetic_registry()
    runner = Runner(reg)
    runner.expand()

    # Pick the solid-o2 cell of mesh.
    solid_o2 = runner.cells_for("tasks.test_runner.mesh", geom_repr="solid", elem_order=2)
    assert len(solid_o2) == 1
    assert solid_o2[0].kwargs == {"geom_repr": "solid", "elem_order": 2}


def test_runner_run_threads_results_through_dag():
    reg = _build_synthetic_registry()
    runner = Runner(reg)
    results = runner.run()

    # Every analyze result should carry its mesh's geom_repr + the design's name.
    for r in results["tasks.test_runner.analyze"]:
        assert r["name"] == "assembly"
        assert r["geom_repr"] in {"line", "shell", "solid"}
        assert r["solver"] in {"abaqus", "calculix"}
        # The skip rule means no analyze cell has line+o2.
        if r["geom_repr"] == "line":
            assert r["elem_order"] == 1


def test_runner_topological_order_is_stable():
    """Parents must execute before children, regardless of registry insert order."""
    reg = TaskRegistry()

    @task(parent="design", fanout={"x": [1, 2]})
    def child(a, *, x):
        return (a, x)

    @task
    def design():
        return "dgn"

    # Register child first, then design.
    reg.register(child)
    reg.register(design)

    runner = Runner(reg)
    results = runner.run()
    assert results["tasks.test_runner.design"] == ["dgn"]
    assert sorted(results["tasks.test_runner.child"]) == [("dgn", 1), ("dgn", 2)]


# ---------------- TaskHandle binding ----------------


def test_task_handle_bound_returns_runner_cells():
    reg = _build_synthetic_registry()
    runner = Runner(reg)
    runner.expand()

    # Simulate the filter resolver binding the handle to the runner.
    handle = TaskHandle(qualname="tasks.test_runner.analyze", _runner=runner)
    abaqus_cells = handle.cells(solver="abaqus")
    assert len(abaqus_cells) == 5
    assert all(c.kwargs["solver"] == "abaqus" for c in abaqus_cells)


def test_task_handle_unbound_still_raises():
    h = TaskHandle.unbound("tasks.test_runner.analyze")
    with pytest.raises(RuntimeError, match="unbound"):
        h.cells()


# ---------------- Executor swap-point (proves the seam) ----------------


class _RecordingExecutor:
    """Executor stub that captures submitted cells without running them."""

    def __init__(self) -> None:
        self.submitted: list[tuple[Cell, Any]] = []

    def submit(self, cell: Cell, parent_result: Any) -> Future:
        self.submitted.append((cell, parent_result))
        fut: Future = Future()
        # Return a deterministic synthetic result so downstream cells have
        # something to chain off of.
        fut.set_result({"recorded": True, "task": cell.task_qualname})
        return fut

    def shutdown(self) -> None:
        return None


def test_runner_uses_swapped_executor():
    """The Runner is oblivious to the executor implementation."""
    reg = _build_synthetic_registry()
    ex = _RecordingExecutor()
    runner = Runner(reg, executor=ex)
    runner.run()

    # 1 design + 5 mesh + 10 analyze = 16 cells submitted.
    assert len(ex.submitted) == 16
    # First submission must be design (no parent), so parent_result is None.
    first_cell, first_parent = ex.submitted[0]
    assert first_cell.task_qualname == "tasks.test_runner.design"
    assert first_parent is None


def test_executor_protocol_runtime_check():
    """`Executor` is a runtime_checkable Protocol — duck-typing works."""
    from paradoc.tasks import Executor

    ex = _RecordingExecutor()
    assert isinstance(ex, Executor)
    assert isinstance(InProcessExecutor(), Executor)
