"""`@task(outputs=...)` — declarative file outputs with cache pre-flight."""

from __future__ import annotations

from pathlib import Path

import pytest

from paradoc.tasks import (
    Runner,
    TaskCache,
    TaskRegistry,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- static outputs ----------------


def test_static_outputs_present_cache_hits(tmp_path: Path):
    """Cache hit when the declared output file exists on disk."""
    out_path = tmp_path / "out.txt"

    @task(outputs=[out_path])
    def emit_file():
        out_path.write_text("hello")
        return "result"

    reg = TaskRegistry()
    reg.register(emit_file)
    reset_default_registry()

    cache = TaskCache(tmp_path / "cache")

    # First run: cache miss, file written.
    runner1 = Runner(reg, cache=cache)
    runner1.run()
    assert runner1.cache_misses == 1
    assert runner1.cache_hits == 0
    assert out_path.exists()

    # Second run: cache hit (file present).
    runner2 = Runner(reg, cache=cache)
    runner2.run()
    assert runner2.cache_hits == 1
    assert runner2.cache_misses == 0


def test_missing_output_forces_re_execution(tmp_path: Path):
    """If the declared output file is deleted between builds, the next
    build re-executes (the cache pre-flight catches the gap)."""
    out_path = tmp_path / "out.txt"
    execution_count = 0

    @task(outputs=[out_path])
    def emit_file():
        nonlocal execution_count
        execution_count += 1
        out_path.write_text("hello")
        return "result"

    reg = TaskRegistry()
    reg.register(emit_file)
    reset_default_registry()

    cache = TaskCache(tmp_path / "cache")

    Runner(reg, cache=cache).run()
    assert execution_count == 1
    assert out_path.exists()

    # Simulate user deletion / staleness.
    out_path.unlink()

    Runner(reg, cache=cache).run()
    assert execution_count == 2  # re-executed because file was gone
    assert out_path.exists()


# ---------------- callable outputs ----------------


def test_callable_outputs_receives_parent_result(tmp_path: Path):
    """For parent-based tasks, outputs callable receives the parent result."""
    captured: list = []

    @task
    def design():
        return {"name": "alpha"}

    @task(parent=design, outputs=lambda parent: [tmp_path / parent["name"] / "marker.txt"])
    def write_marker(parent):
        captured.append(parent)
        (tmp_path / parent["name"]).mkdir(parents=True, exist_ok=True)
        (tmp_path / parent["name"] / "marker.txt").write_text("x")
        return "ok"

    reg = TaskRegistry()
    reg.register(design)
    reg.register(write_marker)
    reset_default_registry()

    Runner(reg, cache=TaskCache(tmp_path / "cache")).run()
    assert (tmp_path / "alpha" / "marker.txt").exists()
    assert captured == [{"name": "alpha"}]


def test_callable_outputs_receives_kwargs(tmp_path: Path):
    """Fanned-out task with kwargs-derived output paths."""

    @task(
        fanout={"i": [1, 2, 3]},
        outputs=lambda i: [tmp_path / f"out_{i}.txt"],
    )
    def emit(*, i):
        path = tmp_path / f"out_{i}.txt"
        path.write_text(str(i))
        return i

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    Runner(reg, cache=TaskCache(tmp_path / "cache")).run()
    assert (tmp_path / "out_1.txt").read_text() == "1"
    assert (tmp_path / "out_2.txt").read_text() == "2"
    assert (tmp_path / "out_3.txt").read_text() == "3"


def test_callable_outputs_for_aggregator(tmp_path: Path):
    """Aggregator (`consumes`) outputs callable receives the upstream list."""

    @task(fanout={"i": [1, 2]})
    def upstream(*, i):
        return i

    @task(
        consumes=upstream,
        outputs=lambda results: [tmp_path / f"agg_{len(results)}.txt"],
    )
    def aggregate(results):
        path = tmp_path / f"agg_{len(results)}.txt"
        path.write_text(",".join(str(r) for r in results))
        return sum(results)

    reg = TaskRegistry()
    reg.register(upstream)
    reg.register(aggregate)
    reset_default_registry()

    Runner(reg, cache=TaskCache(tmp_path / "cache")).run()
    assert (tmp_path / "agg_2.txt").read_text() == "1,2"


# ---------------- doc_root resolution ----------------


def test_relative_outputs_anchor_at_doc_root(tmp_path: Path):
    """Relative output paths resolve against the Runner's doc_root."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()

    @task(outputs=["assets/marker.txt"])
    def emit():
        (doc_root / "assets").mkdir(parents=True, exist_ok=True)
        (doc_root / "assets" / "marker.txt").write_text("x")
        return None

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    runner = Runner(reg, cache=TaskCache(tmp_path / "cache"), doc_root=doc_root)
    runner.run()
    assert (doc_root / "assets" / "marker.txt").exists()
    assert runner.cache_misses == 1

    # Second run picks up the file under doc_root and cache-hits.
    runner2 = Runner(reg, cache=TaskCache(tmp_path / "cache"), doc_root=doc_root)
    runner2.run()
    assert runner2.cache_hits == 1


def test_absolute_outputs_ignore_doc_root(tmp_path: Path):
    """Absolute paths are used as-is regardless of doc_root."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    abs_target = tmp_path / "elsewhere" / "marker.txt"

    @task(outputs=[abs_target])
    def emit():
        abs_target.parent.mkdir(parents=True, exist_ok=True)
        abs_target.write_text("x")

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    Runner(reg, cache=TaskCache(tmp_path / "cache"), doc_root=doc_root).run()
    assert abs_target.exists()


# ---------------- no outputs declared ----------------


def test_no_outputs_declared_caches_purely_on_return_value(tmp_path: Path):
    """A task without outputs= behaves exactly like the v0 cache layer —
    no file pre-flight, no extra invalidation surface."""

    @task
    def pure():
        return 42

    reg = TaskRegistry()
    reg.register(pure)
    reset_default_registry()

    cache = TaskCache(tmp_path / "cache")
    Runner(reg, cache=cache).run()
    runner2 = Runner(reg, cache=cache)
    runner2.run()
    assert runner2.cache_hits == 1


# ---------------- mismatched output declaration ----------------


def test_outputs_invalid_type_raises_at_decoration_time():
    """outputs=<something-not-list-or-callable> raises immediately,
    not on the first cache hit. Surface bad declarations early."""
    with pytest.raises(TypeError, match="must be a list of paths or a callable"):

        @task(outputs="not_a_list_or_callable")  # type: ignore[arg-type]
        def bad():
            return None
