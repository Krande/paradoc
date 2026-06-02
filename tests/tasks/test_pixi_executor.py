"""PixiSubprocessExecutor tests.

Three layers of coverage:

1. **Unit tests with mocked subprocess.run** — validate env resolution,
   command-line construction, tmp-dir lifecycle, error-path handling.
   No real subprocess involved.

2. **Worker module tests** — invoke `paradoc.tasks.run_cell` directly
   (via the current Python interpreter, no pixi) with handcrafted
   input.pkl. Validates the marshaling protocol end-to-end.

3. **Real-pixi integration (opt-in)** — skipped unless pixi is on PATH
   and `PARADOC_TEST_PIXI=1`. CI envs typically lack pixi.

Fixture tasks live in `paradoc.tasks._test_fixtures` (inside the
package) so pickle's import-by-qualname machinery resolves them from
any pixi env that has paradoc installed.
"""

from __future__ import annotations

import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paradoc.tasks import Cell, PixiSubprocessError, PixiSubprocessExecutor
from paradoc.tasks import _test_fixtures as fx
from paradoc.tasks import reset_default_registry


@pytest.fixture(autouse=True)
def _isolate():
    # The fixture-module's @task decorations registered themselves on
    # import. We don't touch the registry from these tests (Cells are
    # constructed directly), but other tests in the suite expect a
    # clean registry — leave it pristine on both sides.
    reset_default_registry()
    yield
    reset_default_registry()


def _make_executor(env_map: dict[str, str] | None = None) -> PixiSubprocessExecutor:
    return PixiSubprocessExecutor(
        pixi_toml=Path("/nonexistent/pixi.toml"),
        env_map=env_map or {"default": "tests", "meshing": "fem-deps"},
    )


# ---------------- env resolution ----------------


def test_env_resolution_static_alias():
    ex = _make_executor()
    cell = Cell(task=fx.design_in_meshing_env)
    assert ex._resolve_env(cell) == "fem-deps"


def test_env_resolution_none_falls_back_to_default():
    ex = _make_executor()
    cell = Cell(task=fx.simple_design)
    assert ex._resolve_env(cell) == "tests"


def test_env_resolution_callable():
    ex = _make_executor(env_map={"default": "d", "calculix": "ccx-env", "abaqus": "aba-env"})
    cell = Cell(task=fx.per_cell_env, kwargs={"solver": "calculix"})
    assert ex._resolve_env(cell) == "ccx-env"


def test_env_resolution_unknown_alias_raises():
    ex = _make_executor(env_map={"default": "d"})
    cell = Cell(task=fx.design_in_meshing_env)
    with pytest.raises(KeyError, match="meshing"):
        ex._resolve_env(cell)


# ---------------- subprocess.run mock: cmd construction + error path ----------------


def test_subprocess_cmd_construction():
    """Verify the executor builds the right `pixi run ...` invocation."""
    ex = _make_executor()
    cell = Cell(task=fx.simple_design)
    captured: list[list[str]] = []

    def _fake(cmd, **kwargs):
        captured.append(cmd)
        # Fake a successful run by writing the output pickle.
        tmpdir = Path(cmd[-1])
        with (tmpdir / "output.pkl").open("wb") as fh:
            pickle.dump("synthetic", fh, protocol=pickle.HIGHEST_PROTOCOL)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake):
        result = ex.submit(cell, parent_result=None).result()

    assert result == "synthetic"
    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[0] == "pixi"
    assert cmd[1] == "run"
    assert cmd[2:4] == ["--manifest-path", str(Path("/nonexistent/pixi.toml"))]
    assert cmd[4:6] == ["-e", "tests"]
    # python -m paradoc.tasks.run_cell <tmpdir>
    assert "python" in cmd
    assert "paradoc.tasks.run_cell" in cmd


def test_subprocess_extra_pixi_args_injected():
    ex = PixiSubprocessExecutor(
        pixi_toml=Path("/tmp/x.toml"),
        env_map={"default": "tests"},
        extra_pixi_args=["--frozen"],
    )
    captured: list[list[str]] = []

    def _fake(cmd, **kwargs):
        captured.append(cmd)
        tmpdir = Path(cmd[-1])
        with (tmpdir / "output.pkl").open("wb") as fh:
            pickle.dump(None, fh, protocol=pickle.HIGHEST_PROTOCOL)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake):
        ex.submit(Cell(task=fx.simple_design), parent_result=None).result()

    assert "--frozen" in captured[0]


def test_subprocess_failure_with_no_error_pkl_raises_pixi_error():
    ex = _make_executor()
    cell = Cell(task=fx.simple_design)

    def _fake_pixi_fails(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=2, stdout="", stderr="pixi: env 'tests' not found")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake_pixi_fails):
        future = ex.submit(cell, parent_result=None)
        with pytest.raises(PixiSubprocessError, match="env 'tests' not found"):
            future.result()


def test_subprocess_error_pkl_reraises_worker_exception():
    """Worker exit-1 with error.pkl carrying an exception."""
    ex = _make_executor()
    cell = Cell(task=fx.simple_design)

    def _fake_worker_raises(cmd, **kwargs):
        tmpdir = Path(cmd[-1])
        with (tmpdir / "error.pkl").open("wb") as fh:
            pickle.dump(ValueError("worker-level boom"), fh, protocol=pickle.HIGHEST_PROTOCOL)
        return subprocess.CompletedProcess(cmd, 1, "", "")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake_worker_raises):
        future = ex.submit(cell, parent_result=None)
        with pytest.raises(ValueError, match="worker-level boom"):
            future.result()


def test_subprocess_cleans_up_tmpdir():
    ex = _make_executor()
    cell = Cell(task=fx.simple_design)
    captured_tmpdirs: list[Path] = []

    def _fake(cmd, **kwargs):
        tmpdir = Path(cmd[-1])
        captured_tmpdirs.append(tmpdir)
        with (tmpdir / "output.pkl").open("wb") as fh:
            pickle.dump("ok", fh, protocol=pickle.HIGHEST_PROTOCOL)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake):
        ex.submit(cell, parent_result=None).result()

    assert captured_tmpdirs
    for d in captured_tmpdirs:
        assert not d.exists(), f"tmpdir {d} leaked"


def test_subprocess_tmpdir_cleaned_on_error_path():
    """tmpdir must be removed even when the worker raises."""
    ex = _make_executor()
    captured_tmpdirs: list[Path] = []

    def _fake(cmd, **kwargs):
        tmpdir = Path(cmd[-1])
        captured_tmpdirs.append(tmpdir)
        with (tmpdir / "error.pkl").open("wb") as fh:
            pickle.dump(RuntimeError("nope"), fh, protocol=pickle.HIGHEST_PROTOCOL)
        return subprocess.CompletedProcess(cmd, 1, "", "")

    with patch("paradoc.tasks.executors.subprocess.run", side_effect=_fake):
        with pytest.raises(RuntimeError, match="nope"):
            ex.submit(Cell(task=fx.simple_design), parent_result=None).result()

    for d in captured_tmpdirs:
        assert not d.exists()


def test_executor_shutdown_releases_pool():
    ex = _make_executor()
    ex.shutdown()
    with pytest.raises(RuntimeError):
        ex.submit(Cell(task=fx.simple_design), None)


# ---------------- worker module: direct invocation ----------------


def _invoke_worker(payload: dict) -> tuple[int, Path]:
    """Write input.pkl, invoke paradoc.tasks.run_cell, return (rc, tmpdir).

    Pytest puts `src/` on sys.path via pyproject's `pythonpath = ["src"]`,
    but a subprocess doesn't inherit that — we pass PYTHONPATH=src in
    the env so the worker can import paradoc.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"

    tmpdir = Path(tempfile.mkdtemp(prefix="paradoc-worker-test-"))
    with (tmpdir / "input.pkl").open("wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    env = {**os.environ, "PYTHONPATH": str(src_dir)}
    proc = subprocess.run(
        [sys.executable, "-m", "paradoc.tasks.run_cell", str(tmpdir)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode not in (0, 1):
        # Surface unexpected failures (e.g. import errors) instead of
        # leaving the assertion in the test producing a confusing diff.
        raise RuntimeError(f"worker rc={proc.returncode}\nstderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")
    return proc.returncode, tmpdir


def test_worker_round_trip_success():
    cell = Cell(task=fx.simple_design)
    rc, tmpdir = _invoke_worker({"cell": cell, "parent_result": None})
    try:
        assert rc == 0
        with (tmpdir / "output.pkl").open("rb") as fh:
            result = pickle.load(fh)
        assert result == {"version": 1, "name": "design"}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_worker_threads_parent_result():
    cell = Cell(task=fx.child_double)
    rc, tmpdir = _invoke_worker({"cell": cell, "parent_result": {"version": 1, "name": "x"}})
    try:
        assert rc == 0
        with (tmpdir / "output.pkl").open("rb") as fh:
            result = pickle.load(fh)
        assert result == {"version": 1, "name": "x", "doubled": True}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_worker_passes_kwargs():
    cell = Cell(task=fx.with_kwargs, kwargs={"x": 7})
    rc, tmpdir = _invoke_worker({"cell": cell, "parent_result": None})
    try:
        assert rc == 0
        with (tmpdir / "output.pkl").open("rb") as fh:
            result = pickle.load(fh)
        assert result == 70
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_worker_writes_error_pkl_on_exception():
    cell = Cell(task=fx.errprone)
    rc, tmpdir = _invoke_worker({"cell": cell, "parent_result": None})
    try:
        assert rc == 1
        assert (tmpdir / "error.pkl").exists()
        assert not (tmpdir / "output.pkl").exists()
        with (tmpdir / "error.pkl").open("rb") as fh:
            exc = pickle.load(fh)
        assert isinstance(exc, ValueError)
        assert "boom from worker" in str(exc)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------- real-pixi integration (opt-in) ----------------


@pytest.mark.skipif(
    not (shutil.which("pixi") and os.environ.get("PARADOC_TEST_PIXI") == "1"),
    reason="requires pixi on PATH + PARADOC_TEST_PIXI=1",
)
def test_real_pixi_round_trip():
    repo_root = Path(__file__).resolve().parents[2]
    pixi_toml = repo_root / "pixi.toml"
    assert pixi_toml.exists(), pixi_toml

    ex = PixiSubprocessExecutor(
        pixi_toml=pixi_toml,
        env_map={"default": "test"},
    )
    try:
        result = ex.submit(Cell(task=fx.simple_design), parent_result=None).result()
        assert result == {"version": 1, "name": "design"}
    finally:
        ex.shutdown()
