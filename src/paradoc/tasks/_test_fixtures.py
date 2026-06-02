"""Module-level @task functions used only by tests.

Pickle serializes callables by `__module__` + `__qualname__`; closure-
scoped functions can't round-trip across a process boundary. The
subprocess-executor tests need their fixture tasks at a stable,
importable module path that *any* pixi env with paradoc installed can
resolve. Co-locating them under `paradoc.tasks` is the path of least
surprise.

The leading underscore signals "not part of the public API". Production
code must not import from this module.
"""

from __future__ import annotations

from .decorator import task


@task
def simple_design():
    return {"version": 1, "name": "design"}


@task(parent=simple_design)
def child_double(parent):
    return {**parent, "doubled": True}


@task(fanout={"x": [1, 2, 3]}, env="default")
def with_kwargs(*, x):
    return x * 10


@task(env="meshing")
def design_in_meshing_env():
    return "meshing-env-output"


@task(env=lambda kw: kw["solver"], fanout={"solver": ["calculix", "abaqus"]})
def per_cell_env(*, solver):
    return f"ran-under-{solver}"


@task
def errprone():
    raise ValueError("boom from worker")
