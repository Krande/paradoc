"""`paradoc build` CLI tests.

Drive via Typer's CliRunner against a synthetic doc layout:

    <tmp>/mydoc/
      paradoc.toml
      tasks.py

That's the convention `paradoc build mydoc` resolves. Tests cover:
inspection without execution, full run with on-disk cache, profile
selection + fanout override, missing doc / missing tasks failure,
in-process fallback when no [paradoc] section is present.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paradoc.tasks import reset_default_registry
from paradoc.tasks.cli import app as build_app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


def _scaffold_doc(
    tmp_path: Path,
    tasks_body: str,
    toml_body: str = "",
    name: str = "mydoc",
) -> Path:
    doc_root = tmp_path / name
    doc_root.mkdir()
    (doc_root / "tasks.py").write_text(textwrap.dedent(tasks_body).lstrip())
    (doc_root / "paradoc.toml").write_text(textwrap.dedent(toml_body).lstrip())
    return doc_root


_SIMPLE_TASKS_PY = """
    from paradoc.tasks import task

    @task
    def design():
        return {"name": "assembly"}

    @task(parent=design, fanout={"geom_repr": ["shell", "solid"], "elem_order": [1, 2]})
    def mesh(a, *, geom_repr, elem_order):
        return {**a, "geom_repr": geom_repr, "elem_order": elem_order}

    @task(parent=mesh, fanout={"solver": ["calculix"]})
    def analyze(a, *, solver):
        return {**a, "solver": solver}
"""


# ---------------- happy paths ----------------


def test_build_full_run(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    result = runner.invoke(build_app, [str(doc_root), "--no-compile"])

    assert result.exit_code == 0, result.output
    # 1 design + 4 mesh + 4 analyze = 9 cells
    assert "ran 9 cells" in result.output
    assert "design" in result.output
    assert "mesh" in result.output
    assert "analyze" in result.output


def test_build_inspect_skips_execution(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    result = runner.invoke(build_app, [str(doc_root), "--inspect"])

    assert result.exit_code == 0, result.output
    assert "skipping execution" in result.output
    assert "ran 9 cells" not in result.output  # never executed


def test_build_dag_output_shows_cell_counts(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    result = runner.invoke(build_app, [str(doc_root), "--inspect"])

    assert "(1 cell)" in result.output  # design
    assert "(4 cells)" in result.output  # mesh and analyze


def test_build_cache_hits_on_second_run(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    first = runner.invoke(build_app, [str(doc_root), "--no-compile"])
    assert first.exit_code == 0
    assert "9 misses" in first.output
    assert "0 hits" in first.output

    second = runner.invoke(build_app, [str(doc_root), "--no-compile"])
    assert second.exit_code == 0
    assert "9 hits" in second.output
    assert "0 misses" in second.output


def test_build_no_cache_flag(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    result = runner.invoke(build_app, [str(doc_root), "--no-cache", "--no-compile"])

    assert result.exit_code == 0
    # No cache line printed.
    assert "cache:" not in result.output


def test_build_profile_applies_fanout_overrides(tmp_path: Path):
    toml = """
        [paradoc]

        [build.smoke.fanout.mesh]
        geom_repr = ["shell"]
        elem_order = [1]
    """
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY, toml_body=toml)

    result = runner.invoke(build_app, [str(doc_root), "--profile", "smoke", "--inspect"])

    assert result.exit_code == 0, result.output
    # mesh: 1 geom x 1 order = 1 cell instead of 4
    # analyze: 1 mesh x 1 solver = 1 cell
    assert "(1 cell)" in result.output  # design AND the overridden mesh
    # Two "(1 cell)" lines expected: design + the now-singleton mesh + the
    # now-singleton analyze. Loosely assert there's no longer any (4 cells).
    assert "(4 cells)" not in result.output


# ---------------- failure paths ----------------


def test_build_missing_doc_dir(tmp_path: Path):
    result = runner.invoke(build_app, [str(tmp_path / "nope")])
    assert result.exit_code == 2
    assert "document directory not found" in result.output


def test_build_no_tasks_discovered(tmp_path: Path):
    doc_root = tmp_path / "empty"
    doc_root.mkdir()
    (doc_root / "paradoc.toml").write_text("")

    result = runner.invoke(build_app, [str(doc_root), "--no-compile"])
    assert result.exit_code == 1
    assert "no tasks discovered" in result.output


def test_build_unknown_profile_raises(tmp_path: Path):
    toml = """
        [build.smoke]
    """
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY, toml_body=toml)

    result = runner.invoke(build_app, [str(doc_root), "--profile", "full"])
    # KeyError from load_task_config -> Typer wraps as an uncaught exception
    # (exit 1) unless we wrap it; for now we just assert non-zero exit.
    assert result.exit_code != 0


def test_build_in_process_only_when_no_pixi_toml(tmp_path: Path):
    """A doc with no [paradoc] section should still build — defaults to
    InProcessExecutor for everything."""
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)  # toml is empty
    result = runner.invoke(build_app, [str(doc_root), "--no-compile"])

    assert result.exit_code == 0
    assert "(none — in-process only)" in result.output


def test_build_wired_into_parent_cli_app(tmp_path: Path):
    """`paradoc build <doc_id>` resolves through the top-level
    paradoc.cli_app — guards against regressions in how the build
    command is registered onto the parent."""
    from paradoc.cli_app import app as parent_app

    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)
    result = runner.invoke(parent_app, ["build", str(doc_root), "--inspect"])

    assert result.exit_code == 0, result.output
    assert "task DAG" in result.output


def test_build_bind_filters_no_filters_py(tmp_path: Path):
    """--bind-filters is fine when no filters.py exists; just warns."""
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)

    result = runner.invoke(build_app, [str(doc_root), "--bind-filters", "--no-compile"])

    assert result.exit_code == 0, result.output
    assert "no filters discovered" in result.output


def test_build_bind_filters_binds_taskhandle(tmp_path: Path):
    """End-to-end: tasks.py + filters.py with TaskHandle bound to runner."""
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)
    (doc_root / "filters.py").write_text(
        textwrap.dedent(
            """
            from paradoc.filters import Filter, attr
            from paradoc.tasks import TaskHandle

            class _M(Filter):
                @attr
                def n(self) -> int:
                    return len(self.task.cells())

            mesh_filter = _M(name="mesh_filter", task=TaskHandle.unbound("mesh"))
            """
        ).lstrip()
    )

    result = runner.invoke(build_app, [str(doc_root), "--bind-filters", "--no-compile"])

    assert result.exit_code == 0, result.output
    assert "bound 1 TaskHandle" in result.output


def test_build_custom_cache_dir(tmp_path: Path):
    doc_root = _scaffold_doc(tmp_path, _SIMPLE_TASKS_PY)
    custom_cache = tmp_path / "elsewhere"

    result = runner.invoke(
        build_app, [str(doc_root), "--cache-dir", str(custom_cache), "--no-compile"]
    )

    assert result.exit_code == 0, result.output
    assert custom_cache.exists()
    assert any(custom_cache.iterdir())  # cache populated
