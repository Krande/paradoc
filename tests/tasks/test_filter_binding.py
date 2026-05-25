"""bind_filter_handles + end-to-end Filter -> TaskHandle -> Runner.

Exercises the path that gets used when `paradoc build <doc> --bind-filters`
hands a populated Runner to the markdown resolver:

  Filter(task=TaskHandle.unbound("qualname"))
      ^ declared at module import (no runner exists yet)
  ...runner.run() finishes...
  bind_filter_handles(filter_registry, runner)
      ^ now self.task.cells(...) is callable
  filter.some_attr()
      ^ pulls live cells through the runner

Also covers the strict failure mode (unresolved qualname raises).
"""

from __future__ import annotations

import pytest

from paradoc.filters import Filter, FilterRegistry, attr
from paradoc.tasks import (
    Runner,
    TaskHandle,
    TaskRegistry,
    bind_filter_handles,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


def _build_registry():
    reg = TaskRegistry()

    @task
    def design():
        return {"v": 1}

    @task(parent=design, fanout={"geom_repr": ["shell", "solid"], "elem_order": [1, 2]})
    def mesh(a, *, geom_repr, elem_order):
        return {**a, "geom_repr": geom_repr, "elem_order": elem_order}

    @task(parent=mesh, fanout={"solver": ["calculix", "abaqus"]})
    def analyze(a, *, solver):
        return {**a, "solver": solver}

    for t in (design, mesh, analyze):
        reg.register(t)
    reset_default_registry()
    return reg, design, mesh, analyze


class _MeshFilter(Filter):
    @attr
    def cell_count(self) -> int:
        return len(self.task.cells())

    @attr
    def first_for(self, geom_repr: str, elem_order: int) -> dict:
        cells = self.task.cells(geom_repr=geom_repr, elem_order=elem_order)
        # In the v0 runner, the result is whatever the task returned.
        return self.task._runner.result_for(cells[0])


# ---------------- bind_filter_handles ----------------


def test_bind_returns_count():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()

    freg = FilterRegistry()
    freg.register(_MeshFilter(name="m1", task=TaskHandle.unbound("tasks.test_filter_binding.mesh")))
    freg.register(_MeshFilter(name="m2", task=TaskHandle.unbound("mesh")))  # bare name

    bound = bind_filter_handles(freg, runner)
    assert bound == 2


def test_bind_resolves_bare_name():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()

    freg = FilterRegistry()
    freg.register(_MeshFilter(name="m", task=TaskHandle.unbound("mesh")))

    bind_filter_handles(freg, runner)
    f = freg.get("m")
    # cells() returns through the runner — bare name resolves to qualname.
    assert len(f.task.cells()) == 4


def test_bind_unknown_qualname_raises():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()

    freg = FilterRegistry()
    freg.register(_MeshFilter(name="orphan", task=TaskHandle.unbound("does.not.exist")))

    with pytest.raises(KeyError, match="does.not.exist"):
        bind_filter_handles(freg, runner)


def test_bind_skips_non_taskhandle_task():
    """Filters with task=None or task=<LegacyTaskSpec> aren't bound."""
    from paradoc.tasks import Task as LegacyTask

    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()

    freg = FilterRegistry()

    class _F(Filter):
        @attr
        def x(self) -> int:
            return 1

    freg.register(_F(name="no_task"))  # task=None
    freg.register(_F(name="legacy", task=LegacyTask(name="legacy_task")))

    # No raise, no bindings.
    bound = bind_filter_handles(freg, runner)
    assert bound == 0


def test_bind_is_idempotent():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()

    freg = FilterRegistry()
    handle = TaskHandle.unbound("mesh")
    freg.register(_MeshFilter(name="m", task=handle))

    bind_filter_handles(freg, runner)
    first = handle._runner
    bind_filter_handles(freg, runner)
    assert handle._runner is first  # same runner, no error


# ---------------- end-to-end: bind -> run -> resolve ----------------


def test_bound_filter_pulls_cells_via_runner():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.run()

    freg = FilterRegistry()
    freg.register(_MeshFilter(name="m", task=TaskHandle.unbound("mesh")))
    bind_filter_handles(freg, runner)

    # call_attr drives the @attr resolution as the markdown layer would.
    n = freg.call_attr("m", "cell_count", {})
    assert n == 4


def test_bound_filter_filter_coords():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.run()

    freg = FilterRegistry()
    freg.register(_MeshFilter(name="m", task=TaskHandle.unbound("mesh")))
    bind_filter_handles(freg, runner)

    result = freg.call_attr("m", "first_for", {"geom_repr": "solid", "elem_order": 2})
    assert result == {"v": 1, "geom_repr": "solid", "elem_order": 2}


# ---------------- Runner.cells_for tolerates bare names ----------------


def test_runner_cells_for_accepts_bare_name():
    reg, *_ = _build_registry()
    runner = Runner(reg)
    runner.expand()
    # cells_for accepts the bare task name even though the dict is
    # keyed by qualname.
    cells_by_qualname = runner.cells_for("tasks.test_filter_binding.mesh")
    cells_by_name = runner.cells_for("mesh")
    assert len(cells_by_name) == len(cells_by_qualname) == 4
