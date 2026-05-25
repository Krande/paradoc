"""BuildContext injection via `ctx: BuildContext` annotation."""

from __future__ import annotations

from pathlib import Path

import pytest

from paradoc.tasks import (
    BuildContext,
    Runner,
    TaskCache,
    TaskRegistry,
    ctx_param_name,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- ctx_param_name introspection ----------------


def test_ctx_param_name_finds_annotated_parameter():
    def fn(ctx: BuildContext):
        return ctx

    assert ctx_param_name(fn) == "ctx"


def test_ctx_param_name_finds_renamed_parameter():
    def fn(parent_result, *, build: BuildContext):
        return build

    assert ctx_param_name(fn) == "build"


def test_ctx_param_name_none_when_unannotated():
    def fn(parent_result):
        return parent_result

    assert ctx_param_name(fn) is None


def test_ctx_param_name_none_when_unrelated_annotation():
    def fn(parent_result: int):
        return parent_result

    assert ctx_param_name(fn) is None


def test_ctx_param_name_handles_future_annotations_strings():
    """`from __future__ import annotations` is in effect for this module;
    the annotation reaches inspect.signature as the literal string
    `'BuildContext'`. The matcher must accept that."""
    import inspect

    def fn(ctx: BuildContext):
        return ctx

    raw = inspect.signature(fn).parameters["ctx"].annotation
    assert raw == "BuildContext", "PEP 563 should have stringified the annotation"
    assert ctx_param_name(fn) == "ctx"


# ---------------- runner injection ----------------


def test_ctx_injected_into_solo_task(tmp_path: Path):
    captured: list[BuildContext] = []

    @task
    def emit(ctx: BuildContext):
        captured.append(ctx)
        return ctx.doc_root

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    runner = Runner(reg, doc_root=tmp_path)
    runner.run()

    assert len(captured) == 1
    assert captured[0].doc_root == tmp_path.resolve()


def test_ctx_injected_alongside_parent_result(tmp_path: Path):
    captured: list[tuple] = []

    @task
    def root():
        return {"design": "alpha"}

    @task(parent=root)
    def child(parent, ctx: BuildContext):
        captured.append((parent, ctx))
        return ctx.doc_root / "out"

    reg = TaskRegistry()
    reg.register(root)
    reg.register(child)
    reset_default_registry()

    Runner(reg, doc_root=tmp_path).run()
    assert len(captured) == 1
    parent, ctx = captured[0]
    assert parent == {"design": "alpha"}
    assert ctx.doc_root == tmp_path.resolve()


def test_ctx_injected_alongside_kwargs(tmp_path: Path):
    captured: list[tuple] = []

    @task(fanout={"i": [1, 2]})
    def emit(ctx: BuildContext, *, i):
        captured.append((i, ctx.doc_root))
        return i

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    Runner(reg, doc_root=tmp_path).run()
    assert sorted(captured) == [
        (1, tmp_path.resolve()),
        (2, tmp_path.resolve()),
    ]


def test_ctx_injected_into_aggregator(tmp_path: Path):
    captured: list[tuple] = []

    @task(fanout={"i": [1, 2, 3]})
    def upstream(*, i):
        return i

    @task(consumes=upstream)
    def aggregate(results, ctx: BuildContext):
        captured.append((tuple(results), ctx.doc_root))
        return sum(results)

    reg = TaskRegistry()
    reg.register(upstream)
    reg.register(aggregate)
    reset_default_registry()

    Runner(reg, doc_root=tmp_path).run()
    assert len(captured) == 1
    results, doc_root = captured[0]
    assert sorted(results) == [1, 2, 3]
    assert doc_root == tmp_path.resolve()


def test_unannotated_task_is_unaffected(tmp_path: Path):
    """A task without a ctx parameter still works — no injection happens."""

    @task
    def plain():
        return "ok"

    reg = TaskRegistry()
    reg.register(plain)
    reset_default_registry()

    runner = Runner(reg, doc_root=tmp_path)
    runner.run()
    # No errors, no surprise kwargs.


def test_ctx_not_in_cache_key(tmp_path: Path):
    """BuildContext is *not* part of cell.kwargs, so caching is stable
    across builds that share data but live in different directories."""
    execution_count = 0

    @task
    def emit(ctx: BuildContext):
        nonlocal execution_count
        execution_count += 1
        return "result"

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    cache = TaskCache(tmp_path / "cache")

    # First build: under doc_root_a.
    doc_root_a = tmp_path / "a"
    doc_root_a.mkdir()
    Runner(reg, cache=cache, doc_root=doc_root_a).run()
    assert execution_count == 1

    # Second build: same registry, same cache, *different* doc_root.
    # If BuildContext were leaking into the cache key, we'd get a miss.
    doc_root_b = tmp_path / "b"
    doc_root_b.mkdir()
    runner_b = Runner(reg, cache=cache, doc_root=doc_root_b)
    runner_b.run()
    assert execution_count == 1  # cache hit despite different doc_root
    assert runner_b.cache_hits == 1


def test_ctx_passes_cache_dir_and_work_dir(tmp_path: Path):
    """When the runner is given an explicit context, those fields flow
    through to the task body."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    cache_dir = tmp_path / "cache"
    captured: list[BuildContext] = []

    @task
    def emit(ctx: BuildContext):
        captured.append(ctx)
        return None

    reg = TaskRegistry()
    reg.register(emit)
    reset_default_registry()

    explicit = BuildContext(
        doc_root=tmp_path,
        cache_dir=cache_dir,
        work_dir=work_dir,
        assets_dir=tmp_path / "assets",
    )
    Runner(reg, cache=TaskCache(cache_dir), context=explicit).run()
    assert captured[0].work_dir == work_dir
    assert captured[0].cache_dir == cache_dir
    assert captured[0].assets_dir == tmp_path / "assets"
