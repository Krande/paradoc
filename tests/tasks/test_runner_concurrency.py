"""`@task(concurrency=...)`: a task's cells may run side by side, held to per-value limits.

What it is for: a solver matrix, where each cell is a licensed run and the licences, not the
cores, say how many may overlap -- e.g. at most two Abaqus jobs, whatever the open-source solvers
do meanwhile.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

import pytest

from paradoc.tasks import Runner, TaskRegistry, reset_default_registry, task
from paradoc.tasks.cache import TaskCache


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


class _Tracker:
    """Counts how many cells run at once, overall and per solver."""

    def __init__(self):
        self.lock = threading.Lock()
        self.now = defaultdict(int)
        self.peak = defaultdict(int)
        self.calls = []

    def run(self, solver, seconds=0.15):
        with self.lock:
            self.now[solver] += 1
            self.now["*"] += 1
            self.peak[solver] = max(self.peak[solver], self.now[solver])
            self.peak["*"] = max(self.peak["*"], self.now["*"])
            self.calls.append(solver)
        time.sleep(seconds)
        with self.lock:
            self.now[solver] -= 1
            self.now["*"] -= 1


def _registry(tracker, concurrency, *, fail_on=None, seeds=(1, 2, 3)):
    reg = TaskRegistry()

    @task
    def design():
        return "model"

    @task(parent=design, fanout={"seed": list(seeds)})
    def mesh(a, *, seed):
        return f"{a}/{seed}"

    @task(parent=mesh, fanout={"solver": ["abaqus", "calculix", "sesam"]}, concurrency=concurrency)
    def run(a, *, solver):
        tracker.run(solver)
        if fail_on is not None and (a, solver) == fail_on:
            raise RuntimeError(f"{solver} failed on {a}")
        return f"{a}:{solver}"

    for t in (design, mesh, run):
        reg.register(t)
    reset_default_registry()
    return reg


LIMITS = {"key": "solver", "limits": {"abaqus": 2, "sesam": 1}, "default": 3}


def test_cells_overlap_within_their_limits():
    tracker = _Tracker()
    results = Runner(_registry(tracker, LIMITS)).run()

    assert tracker.peak["abaqus"] == 2  # three abaqus cells, two at a time
    assert tracker.peak["sesam"] == 1
    assert tracker.peak["calculix"] == 3
    assert tracker.peak["*"] > 3  # solvers overlapped one another
    # Results come back in cell order, exactly as a sequential run gives them.
    assert results["tasks.test_runner_concurrency.run"] == [
        f"model/{seed}:{solver}" for seed in (1, 2, 3) for solver in ("abaqus", "calculix", "sesam")
    ]


def test_a_task_without_concurrency_runs_one_cell_at_a_time():
    tracker = _Tracker()
    Runner(_registry(tracker, None)).run()
    assert tracker.peak["*"] == 1


def test_paradoc_max_parallel_one_turns_it_off(monkeypatch):
    monkeypatch.setenv("PARADOC_MAX_PARALLEL", "1")
    tracker = _Tracker()
    Runner(_registry(tracker, LIMITS)).run()
    assert tracker.peak["*"] == 1


def test_paradoc_max_parallel_caps_the_whole_task(monkeypatch):
    monkeypatch.setenv("PARADOC_MAX_PARALLEL", "2")
    tracker = _Tracker()
    Runner(_registry(tracker, LIMITS)).run()
    assert tracker.peak["*"] == 2


def test_a_failure_lets_the_others_finish_and_keeps_their_results(tmp_path):
    """The first failure is raised -- after every other cell has run, and with their results cached,
    so the next build reruns only what failed."""
    tracker = _Tracker()
    cache = TaskCache(tmp_path / "cache")
    reg = _registry(tracker, LIMITS, fail_on=("model/2", "sesam"))
    with pytest.raises(RuntimeError, match="sesam failed on model/2"):
        Runner(reg, cache=cache).run()
    assert len(tracker.calls) == 9  # all nine cells ran

    tracker2 = _Tracker()
    reg2 = _registry(tracker2, LIMITS, fail_on=("model/2", "sesam"))
    runner = Runner(reg2, cache=cache)
    with pytest.raises(RuntimeError):
        runner.run()
    assert tracker2.calls == ["sesam"]  # only the failed cell ran again


@pytest.mark.parametrize(
    "bad",
    [
        "solver",
        {"keys": "solver"},
        {"key": 3},
        {"limits": {"abaqus": 0}},
        {"default": -1},
        {"default": True},
    ],
)
def test_a_malformed_concurrency_is_refused(bad):
    with pytest.raises((TypeError, ValueError)):

        @task(fanout={"solver": ["a"]}, concurrency=bad)
        def run(*, solver):
            return solver
