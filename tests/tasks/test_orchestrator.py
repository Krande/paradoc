"""End-to-end tests for `build_document` (the orchestrator behind
`paradoc build`). Validates that OneDoc + Runner + bind path
composes correctly.

Compile-path tests are gated on OneDoc being importable; if the test
env doesn't have pandoc/docx machinery the compile tests are skipped.
"""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

from paradoc.tasks import reset_default_registry
from paradoc.tasks.orchestrator import build_document

_ONE_DOC_AVAILABLE = importlib.util.find_spec("paradoc.document") is not None


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


def _scaffold(tmp_path: Path, tasks_body: str, toml_body: str = "", filters_body: str = "") -> Path:
    doc = tmp_path / "mydoc"
    doc.mkdir()
    (doc / "tasks.py").write_text(textwrap.dedent(tasks_body).lstrip())
    (doc / "paradoc.toml").write_text(textwrap.dedent(toml_body).lstrip())
    if filters_body:
        (doc / "filters.py").write_text(textwrap.dedent(filters_body).lstrip())
    return doc


_SIMPLE = """
    from paradoc.tasks import task

    @task
    def design():
        return {"v": 1}

    @task(parent=design, fanout={"geom_repr": ["shell", "solid"]})
    def mesh(a, *, geom_repr):
        return {**a, "geom_repr": geom_repr}
"""


# ---------------- orchestrator without compile ----------------


def test_build_document_no_compile_returns_runner(tmp_path: Path):
    doc = _scaffold(tmp_path, _SIMPLE)
    runner, one = build_document(doc, compile=False)

    assert one is None
    assert len(runner.cells_for("mesh")) == 2
    runner.shutdown()


def test_build_document_applies_profile_fanout(tmp_path: Path):
    doc = _scaffold(
        tmp_path,
        _SIMPLE,
        toml_body="""
            [build.smoke.fanout.mesh]
            geom_repr = ["shell"]
        """,
    )
    runner, _ = build_document(doc, profile="smoke", compile=False)
    assert len(runner.cells_for("mesh")) == 1
    runner.shutdown()


def test_build_document_missing_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        build_document(tmp_path / "nope")


def test_build_document_no_tasks(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "paradoc.toml").write_text("")
    with pytest.raises(RuntimeError, match="no tasks discovered"):
        build_document(empty)


# ---------------- runner_hooks ----------------


def test_build_document_after_expand_hook_called(tmp_path: Path):
    doc = _scaffold(tmp_path, _SIMPLE)
    observed: list = []

    def _after(runner):
        observed.append(runner)
        # The runner is fully expanded but hasn't executed yet.
        assert runner.cache_hits == 0
        assert runner.cache_misses == 0

    runner, _ = build_document(doc, compile=False, runner_hooks={"after_expand": _after})
    assert observed and observed[0] is runner
    runner.shutdown()


# ---------------- OneDoc compile path (skipped if missing) ----------------


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_build_document_compiles_with_filter_binding(tmp_path: Path):
    """The orchestrator should pass the runner to OneDoc, which then
    intrinsically binds TaskHandles during compile."""
    doc = _scaffold(
        tmp_path,
        _SIMPLE,
        filters_body="""
            from paradoc.filters import Filter, attr
            from paradoc.tasks import TaskHandle

            class _M(Filter):
                @attr
                def n(self) -> int:
                    return len(self.task.cells())

            mesh_filter = _M(name="mesh_filter", task=TaskHandle.unbound("mesh"))
        """,
    )
    # Markdown source so OneDoc.compile() has something to render.
    main = doc / "00-main"
    main.mkdir()
    (main / "01_intro.md").write_text("# Doc\n\nMesh cells: ${ mesh_filter.n }\n")

    work_dir = tmp_path / "work"
    runner, one = build_document(doc, work_dir=work_dir, compile=True, no_cache=True)

    assert one is not None
    # The filter resolver fired through the bound runner.
    assert one._filters_discovered is True
    bound_handle = one._filter_registry.get("mesh_filter").task
    assert bound_handle._runner is runner
    runner.shutdown()


# ---------------- multi-output ----------------


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_build_document_loops_outputs_from_toml(tmp_path: Path):
    """[build.x.outputs = ["docx", "pdf"]] should drive two compile passes."""

    doc = _scaffold(
        tmp_path,
        _SIMPLE,
        toml_body="""
            [build.default]
            outputs = ["docx"]
        """,
    )
    main = doc / "00-main"
    main.mkdir()
    (main / "01.md").write_text("# t\n")

    # Patch OneDoc.compile to record what got called.
    calls: list = []
    from paradoc.document import OneDoc

    real_compile = OneDoc.compile

    def _spy(self, name, **kwargs):
        calls.append((name, kwargs.get("export_format")))
        # Don't actually drive pandoc; just record the call.

    OneDoc.compile = _spy
    try:
        build_document(doc, work_dir=tmp_path / "work", no_cache=True)
    finally:
        OneDoc.compile = real_compile

    assert len(calls) == 1
    assert calls[0][0] == "mydoc"
    assert calls[0][1] == "docx"
