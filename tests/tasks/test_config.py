"""paradoc.toml schema + HybridExecutor routing + fanout overrides."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from paradoc.tasks import (
    BuildProfile,
    Cell,
    HybridExecutor,
    InProcessExecutor,
    PixiSubprocessExecutor,
    Runner,
    TaskConfig,
    TaskRegistry,
)
from paradoc.tasks import _test_fixtures as fx
from paradoc.tasks import (
    build_executor_from_config,
    load_task_config,
    merge_fanout,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- TOML loading ----------------


def _write_toml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "paradoc.toml"
    p.write_text(textwrap.dedent(body).lstrip())
    return p


def test_load_missing_file_returns_empty(tmp_path: Path):
    config = load_task_config(tmp_path / "absent.toml")
    assert config.pixi_toml is None
    assert config.envs == {}
    assert config.fanout_overrides == {}


def test_load_paradoc_section_resolves_pixi_toml_relative(tmp_path: Path):
    # Create the referenced pixi.toml so the resolve point exists on disk
    # (the loader resolves but doesn't require existence — verified
    # separately).
    (tmp_path / "subdir").mkdir()
    pixi_toml = tmp_path / "subdir" / "pixi.toml"
    pixi_toml.write_text("# fake")
    toml = _write_toml(
        tmp_path,
        """
        [paradoc]
        pixi_toml = "subdir/pixi.toml"
        """,
    )
    config = load_task_config(toml)
    assert config.pixi_toml == pixi_toml.resolve()


def test_load_envs_global_and_profile_overrides(tmp_path: Path):
    toml = _write_toml(
        tmp_path,
        """
        [paradoc]
        pixi_toml = "p.toml"

        [paradoc.envs]
        default  = "tests"
        meshing  = "fem-deps"
        calculix = "calculix-deps"

        [build.smoke]
        [build.smoke.envs]
        calculix = "tests"
        """,
    )
    config = load_task_config(toml, profile="smoke")
    assert config.envs == {
        "default": "tests",
        "meshing": "fem-deps",
        "calculix": "tests",  # overridden by profile
    }


def test_load_profile_fanout_overrides(tmp_path: Path):
    toml = _write_toml(
        tmp_path,
        """
        [paradoc]
        [build.verification.fanout.mesh]
        geom_repr  = ["shell"]
        elem_order = [1]
        [build.verification.fanout.run_eig]
        solver = ["calculix"]
        """,
    )
    config = load_task_config(toml, profile="verification")
    assert config.fanout_overrides == {
        "mesh": {"geom_repr": ["shell"], "elem_order": [1]},
        "run_eig": {"solver": ["calculix"]},
    }


def test_load_unknown_profile_raises(tmp_path: Path):
    toml = _write_toml(
        tmp_path,
        """
        [build.smoke]
        """,
    )
    with pytest.raises(KeyError, match=r"\[build\.full\]"):
        load_task_config(toml, profile="full")


def test_load_no_build_section_allows_any_profile_name(tmp_path: Path):
    """If the toml has no profiles, the default-profile request returns
    an empty override map — used by docs that don't need profile config."""
    toml = _write_toml(tmp_path, "[paradoc]\n")
    config = load_task_config(toml, profile="anything")
    assert config.fanout_overrides == {}


def test_load_rejects_unknown_keys(tmp_path: Path):
    """Typos in paradoc.toml should fail loudly, not be silently dropped."""
    toml = _write_toml(
        tmp_path,
        """
        [paradoc]
        pixi-toml = "p.toml"
        """,
    )
    with pytest.raises(ValueError, match="pixi-toml"):
        load_task_config(toml)


# ---------------- merge_fanout ----------------


def test_merge_fanout_per_axis_replacement():
    task_fanout = {"a": [1, 2], "b": [10, 20]}
    override = {"a": [9]}
    assert merge_fanout(task_fanout, override) == {"a": [9], "b": [10, 20]}


def test_merge_fanout_no_override():
    task_fanout = {"x": [1]}
    assert merge_fanout(task_fanout, None) == {"x": [1]}
    assert merge_fanout(task_fanout, {}) == {"x": [1]}


def test_merge_fanout_returns_fresh_dict():
    task_fanout = {"x": [1]}
    out = merge_fanout(task_fanout, {"y": [2]})
    out["x"] = [9]
    assert task_fanout == {"x": [1]}  # unchanged


# ---------------- HybridExecutor routing ----------------


def test_hybrid_routes_envless_task_in_process():
    """A task without env= must NOT spawn a subprocess."""
    in_proc_calls = []
    pixi_calls = []

    class _Stub:
        def __init__(self, sink):
            self.sink = sink

        def submit(self, cell, parent_result, extra_kwargs=None):
            from concurrent.futures import Future

            self.sink.append(cell)
            f = Future()
            f.set_result(None)
            return f

        def shutdown(self):
            return None

    hybrid = HybridExecutor(_Stub(in_proc_calls), _Stub(pixi_calls))
    hybrid.submit(Cell(task=fx.simple_design), None).result()  # env=None
    hybrid.submit(Cell(task=fx.design_in_meshing_env), None).result()  # env="meshing"

    assert [c.task.qualname for c in in_proc_calls] == [fx.simple_design.qualname]
    assert [c.task.qualname for c in pixi_calls] == [fx.design_in_meshing_env.qualname]


def test_hybrid_shutdown_propagates():
    shut = []

    class _Stub:
        def __init__(self, name):
            self.name = name

        def submit(self, cell, parent_result, extra_kwargs=None):
            from concurrent.futures import Future

            f = Future()
            f.set_result(None)
            return f

        def shutdown(self):
            shut.append(self.name)

    HybridExecutor(_Stub("ip"), _Stub("pixi")).shutdown()
    assert shut == ["ip", "pixi"]


# ---------------- build_executor_from_config ----------------


def test_build_executor_no_pixi_falls_back_to_in_process(tmp_path: Path):
    config = TaskConfig(pixi_toml=None, envs={}, fanout_overrides={})
    ex = build_executor_from_config(config)
    assert isinstance(ex, InProcessExecutor)


def test_build_executor_with_pixi_returns_hybrid(tmp_path: Path):
    config = TaskConfig(
        pixi_toml=tmp_path / "pixi.toml",
        envs={"default": "tests", "meshing": "fem-deps"},
        fanout_overrides={},
    )
    ex = build_executor_from_config(config)
    assert isinstance(ex, HybridExecutor)
    assert isinstance(ex.in_process, InProcessExecutor)
    assert isinstance(ex.pixi, PixiSubprocessExecutor)
    assert ex.pixi.env_map == {"default": "tests", "meshing": "fem-deps"}
    ex.shutdown()


# ---------------- Runner with fanout_overrides ----------------


def _build_synth_registry():
    reg = TaskRegistry()

    @task
    def design():
        return {"v": 1}

    @task(parent=design, fanout={"geom_repr": ["line", "shell", "solid"], "elem_order": [1, 2]})
    def mesh(a, *, geom_repr, elem_order):
        return {**a, "geom_repr": geom_repr, "elem_order": elem_order}

    @task(parent=mesh, fanout={"solver": ["abaqus", "calculix", "code_aster"]})
    def analyze(a, *, solver):
        return {**a, "solver": solver}

    for t in (design, mesh, analyze):
        reg.register(t)
    reset_default_registry()
    return reg


def test_runner_applies_fanout_overrides_per_axis():
    reg = _build_synth_registry()
    # Override only solver, leave geom_repr / elem_order alone.
    overrides = {
        "tasks.test_config.analyze": {"solver": ["calculix"]},
    }
    runner = Runner(reg, fanout_overrides=overrides)
    runner.expand()

    # mesh: 3x2 = 6 (unchanged)
    assert len(runner.cells_for("tasks.test_config.mesh")) == 6
    # analyze: 6 mesh parents x 1 solver = 6 (was 18)
    analyze = runner.cells_for("tasks.test_config.analyze")
    assert len(analyze) == 6
    assert all(c.kwargs["solver"] == "calculix" for c in analyze)


def test_runner_overrides_by_bare_name():
    """Override lookup falls back to task.name if qualname doesn't match.
    Lets users write `[build.x.fanout.analyze]` without the full
    `tasks.test_config.analyze` qualname in paradoc.toml."""
    reg = _build_synth_registry()
    overrides = {"mesh": {"geom_repr": ["shell"], "elem_order": [1]}}
    runner = Runner(reg, fanout_overrides=overrides)
    runner.expand()
    # mesh: 1 cell
    assert len(runner.cells_for("tasks.test_config.mesh")) == 1


def test_runner_overrides_empty_list_yields_no_cells():
    """A profile that sets an axis to [] eliminates the entire task."""
    reg = _build_synth_registry()
    runner = Runner(reg, fanout_overrides={"analyze": {"solver": []}})
    runner.expand()
    assert runner.cells_for("tasks.test_config.analyze") == []


def test_runner_no_overrides_preserves_decorator_fanout():
    reg = _build_synth_registry()
    runner = Runner(reg)
    runner.expand()
    assert len(runner.cells_for("tasks.test_config.mesh")) == 6
    assert len(runner.cells_for("tasks.test_config.analyze")) == 18


# ---------------- Strict-key rejection scope ----------------


def test_build_profile_strict():
    """Mistyped profile keys must raise — typos in paradoc.toml should
    fail at load time, not produce silently-wrong builds."""
    with pytest.raises(ValueError, match="extra"):
        BuildProfile(unknown_field=True)
