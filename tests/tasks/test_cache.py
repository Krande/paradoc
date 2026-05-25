"""Cache layer tests — Q4 Option C.

Covers:
- AST source hashing with call-graph walk (helper-fn change busts hash)
- Module fingerprint fallback for C-extension callables
- Cache key construction (kwargs + parent + version_probe)
- On-disk cache get/put with atomic rename
- Runner integration: hit short-circuits executor, miss runs + writes
"""

from __future__ import annotations

import pickle
import textwrap
from pathlib import Path

import pytest

from paradoc.tasks import (
    CacheKey,
    Cell,
    InProcessExecutor,
    Runner,
    TaskCache,
    TaskFn,
    TaskRegistry,
    ast_source_hash,
    compute_cache_key,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- AST source hash ----------------


def test_ast_hash_stable_across_calls():
    @task
    def design():
        return "a"

    a = ast_source_hash(design)
    b = ast_source_hash(design)
    assert a == b
    assert isinstance(a, bytes) and len(a) == 32


def test_ast_hash_changes_when_body_changes():
    def v1():
        return 1

    def v2():
        return 2  # change

    assert ast_source_hash(v1) != ast_source_hash(v2)


def test_ast_hash_walks_helper_fn():
    """If a helper fn changes, the parent's hash must change too —
    that's the whole point of the call-graph walk."""

    def helper_v1(x):
        return x + 1

    def design_v1(x):
        return helper_v1(x)

    design_v1.__globals__["helper_v1"] = helper_v1
    h1 = ast_source_hash(design_v1)

    def helper_v2(x):
        return x + 100  # behavior change

    def design_v2(x):
        return helper_v1(x)  # same source as v1, but the helper changed

    design_v2.__globals__["helper_v1"] = helper_v2
    h2 = ast_source_hash(design_v2)

    assert h1 != h2


def test_ast_hash_module_fingerprint_fallback_for_c_extension():
    """C extensions have no source; fingerprint is module name (+ version if any)."""
    import json

    # json.dumps is a Python function in stdlib, but io.BytesIO is a class
    # backed by C — pick one that's reliably non-Python-source.
    import io

    fingerprint = ast_source_hash(io.BytesIO)
    # Just confirming it doesn't crash and produces a deterministic digest.
    assert isinstance(fingerprint, bytes) and len(fingerprint) == 32

    # Plain json (the module) is also picklable; check json.dumps explicitly.
    h1 = ast_source_hash(json.dumps)
    h2 = ast_source_hash(json.dumps)
    assert h1 == h2


def test_ast_hash_cycle_guard():
    """A function that references itself shouldn't recurse infinitely."""

    def recursive(n):
        if n <= 0:
            return 0
        return recursive(n - 1)

    recursive.__globals__["recursive"] = recursive
    # If the cycle guard fails this hangs / RecursionErrors.
    h = ast_source_hash(recursive)
    assert isinstance(h, bytes)


# ---------------- compute_cache_key ----------------


def test_cache_key_includes_kwargs():
    @task
    def t(*, x):
        return x

    k1 = compute_cache_key(t, {"x": 1})
    k2 = compute_cache_key(t, {"x": 2})
    assert k1.digest != k2.digest


def test_cache_key_kwarg_order_independent():
    @task
    def t(*, a, b):
        return (a, b)

    k1 = compute_cache_key(t, {"a": 1, "b": 2})
    k2 = compute_cache_key(t, {"b": 2, "a": 1})
    assert k1.digest == k2.digest


def test_cache_key_parent_propagation():
    @task
    def root():
        return None

    @task(parent=root)
    def child():
        return None

    parent_key_v1 = CacheKey(qualname="root", digest=b"\x01" * 32)
    parent_key_v2 = CacheKey(qualname="root", digest=b"\x02" * 32)

    k1 = compute_cache_key(child, {}, parent_key=parent_key_v1)
    k2 = compute_cache_key(child, {}, parent_key=parent_key_v2)
    assert k1.digest != k2.digest


def test_cache_key_version_probe_folded():
    @task(version_probe=lambda kw: f"solver={kw['solver']}-1.0")
    def t(*, solver):
        return solver

    k1 = compute_cache_key(t, {"solver": "calculix"})
    k2 = compute_cache_key(t, {"solver": "abaqus"})
    assert k1.digest != k2.digest  # solver differs in kwargs AND probe


def test_cache_key_memo_reused_across_cells():
    """The memo dict should avoid re-hashing the same task per cell."""

    @task
    def t(*, x):
        return x

    memo: dict[int, bytes] = {}
    compute_cache_key(t, {"x": 1}, ast_hash_memo=memo)
    assert id(t) in memo
    # Second call must reuse the cached digest.
    digest_before = memo[id(t)]
    compute_cache_key(t, {"x": 99}, ast_hash_memo=memo)
    assert memo[id(t)] is digest_before


# ---------------- TaskCache on-disk ----------------


def test_cache_round_trip(tmp_path: Path):
    cache = TaskCache(tmp_path)
    key = CacheKey(qualname="my.task", digest=b"\xaa" * 32)
    assert cache.has(key) is False

    cache.put(key, {"freqs": [1.0, 2.0]}, kwargs={"solver": "calculix"})
    assert cache.has(key) is True
    assert cache.get(key) == {"freqs": [1.0, 2.0]}


def test_cache_meta_sidecar(tmp_path: Path):
    import json

    cache = TaskCache(tmp_path)
    key = CacheKey(qualname="my.task", digest=b"\xbb" * 32)
    parent = CacheKey(qualname="parent", digest=b"\xcc" * 32)
    cache.put(
        key,
        "result",
        kwargs={"solver": "ccx"},
        parent_key=parent,
        version_probe="calculix-2.21",
    )

    meta_path = tmp_path / "my.task" / f"{key.hex}.meta"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["kwargs"] == {"solver": "ccx"}
    assert meta["parent_hex"] == parent.hex
    assert meta["version_probe"] == "calculix-2.21"


def test_cache_atomic_publish_no_partial_pkl(tmp_path: Path):
    """The .pkl file shouldn't exist mid-write — atomic rename."""
    cache = TaskCache(tmp_path)
    key = CacheKey(qualname="task", digest=b"\xdd" * 32)
    cache.put(key, "ok")
    # After put completes, no .tmp files should remain.
    leftovers = list(tmp_path.rglob("*.tmp"))
    assert leftovers == [], leftovers


# ---------------- Runner integration ----------------


def _build_synthetic_registry() -> tuple[TaskRegistry, TaskFn, TaskFn, TaskFn]:
    reg = TaskRegistry()

    @task
    def design():
        return {"value": 10}

    @task(parent=design, fanout={"scale": [1, 2]})
    def mesh(a, *, scale):
        return {**a, "scale": scale}

    @task(parent=mesh, fanout={"solver": ["calculix", "abaqus"]})
    def analyze(a, *, solver):
        return {**a, "solver": solver}

    for t in (design, mesh, analyze):
        reg.register(t)
    reset_default_registry()
    return reg, design, mesh, analyze


def test_runner_with_cache_writes_results(tmp_path: Path):
    reg, *_ = _build_synthetic_registry()
    cache = TaskCache(tmp_path)
    runner = Runner(reg, cache=cache)
    runner.run()

    # 1 design + 2 mesh + 4 analyze = 7 cells, all newly cached.
    assert runner.cache_misses == 7
    assert runner.cache_hits == 0

    # On-disk files exist.
    pkls = list(tmp_path.rglob("*.pkl"))
    assert len(pkls) == 7


def test_runner_with_cache_hits_on_second_run(tmp_path: Path):
    reg, *_ = _build_synthetic_registry()
    cache = TaskCache(tmp_path)

    runner1 = Runner(reg, cache=cache)
    runner1.run()
    assert runner1.cache_misses == 7

    runner2 = Runner(reg, cache=cache)
    runner2.run()
    # Second run: every cell hits.
    assert runner2.cache_hits == 7
    assert runner2.cache_misses == 0


def test_runner_cache_invalidates_when_task_body_changes(tmp_path: Path):
    """Hash a registry, run, then mutate a function body. The cache key
    must differ on the second run."""
    reg = TaskRegistry()

    def design_body():
        return {"version": "v1"}

    fn = TaskFn(fn=design_body, name="design")
    reg.register(fn)

    runner = Runner(reg, cache=TaskCache(tmp_path))
    runner.run()
    first_keys = set(runner._cache_keys.values())
    assert len(first_keys) == 1
    [first_key] = first_keys

    # Swap the function body — same name, different code.
    def design_body_v2():
        return {"version": "v2"}

    reg.clear()
    fn2 = TaskFn(fn=design_body_v2, name="design")
    reg.register(fn2)

    runner2 = Runner(reg, cache=TaskCache(tmp_path))
    runner2.run()
    [second_key] = set(runner2._cache_keys.values())

    assert first_key.digest != second_key.digest


def test_cached_result_short_circuits_executor(tmp_path: Path):
    """A cache hit must not invoke the executor."""
    from concurrent.futures import Future

    class _ExplodingExecutor:
        def submit(self, cell, parent_result):
            raise RuntimeError("executor must not be called on a cache hit")

        def shutdown(self):
            return None

    reg, *_ = _build_synthetic_registry()
    cache = TaskCache(tmp_path)

    # Prime the cache with a normal run.
    Runner(reg, cache=cache).run()

    # Second run with an exploding executor: every cell hits, so submit
    # should never be called.
    Runner(reg, executor=_ExplodingExecutor(), cache=cache).run()


def test_runner_without_cache_skips_key_construction(tmp_path: Path):
    """No cache wired -> Runner must not compute keys (which would call
    inspect.getsource on every task)."""
    reg, *_ = _build_synthetic_registry()
    runner = Runner(reg)  # no cache=
    runner.run()
    assert runner._cache_keys == {}
    assert runner.cache_hits == 0
    assert runner.cache_misses == 0
