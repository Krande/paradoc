"""Phase 7 Task placeholder tests.

The runner is not implemented yet — these tests just lock the data shape
so future work doesn't accidentally break field names that filter
authors will already be using.
"""

from pathlib import Path

from paradoc.filters import Filter, attr
from paradoc.tasks import Task


def test_task_minimal_construction():
    t = Task(name="simulate_main")
    assert t.name == "simulate_main"
    assert t.inputs == []
    assert t.outputs == []
    assert t.depends_on == []
    assert t.env_lock is None
    assert t.solver_version is None


def test_task_full_construction():
    t = Task(
        name="simulate_eig",
        inputs=["files/model.inp"],
        outputs=["results/eig.rmed"],
        env_lock=Path("env.lock"),
        solver_version="codeaster-15.4",
        depends_on=["preprocess_mesh"],
    )
    assert t.name == "simulate_eig"
    assert t.solver_version == "codeaster-15.4"
    assert t.depends_on == ["preprocess_mesh"]


def test_filter_accepts_task_reference():
    class _ResultsFilter(Filter):
        @attr
        def first_freq(self) -> float:
            return 0.0

    t = Task(name="upstream")
    f = _ResultsFilter(name="results", task=t)
    assert f.task is t


def test_fea_model_results_has_task_id_field():
    """Forward-compat: FEAModelResults reserves a task_id slot."""
    from paradoc.figure_sources import FEAFormat, FEAModelResults

    spec = FEAModelResults(
        figure_title="x",
        fea_format=FEAFormat.ABAQUS,
        source_inp="model.inp",
        output_file="model.odb",
        field="S",
        task_id="simulate_main",
    )
    assert spec.task_id == "simulate_main"

    # Default is None
    spec2 = FEAModelResults(
        figure_title="x",
        fea_format=FEAFormat.ABAQUS,
        source_inp="model.inp",
        output_file="model.odb",
        field="S",
    )
    assert spec2.task_id is None
