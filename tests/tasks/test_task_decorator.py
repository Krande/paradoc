"""Decorator + registry + discovery for the @task-based primitive.

Scope: declarative surface only. The runner that actually executes tasks
lives in the next phase; these tests lock the API shape and the
registration semantics so that work can be additive.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from paradoc.tasks import (
    TaskFn,
    TaskHandle,
    TaskRegistry,
    discover_tasks,
    get_default_registry,
    is_task,
    reset_default_registry,
    task,
)


@pytest.fixture(autouse=True)
def _isolate_default_registry():
    """Each test gets a clean default registry so decoration side effects
    from one test don't leak into the next."""
    reset_default_registry()
    yield
    reset_default_registry()


def test_bare_task_decoration():
    @task
    def design():
        return "assembly"

    assert is_task(design)
    assert isinstance(design, TaskFn)
    assert design.name == "design"
    assert design.fanout == {}
    assert design.parent is None
    assert design() == "assembly"  # callable as-is


def test_task_with_metadata():
    @task
    def design():
        return "a"

    @task(
        parent=design,
        fanout={"geom_repr": ["line", "shell"], "elem_order": [1, 2]},
        env="meshing",
        skip_if=lambda kw: kw["geom_repr"] == "line" and kw["elem_order"] == 2,
    )
    def mesh(a, *, geom_repr, elem_order):
        return (a, geom_repr, elem_order)

    assert mesh.parent is design
    assert mesh.fanout == {"geom_repr": ["line", "shell"], "elem_order": [1, 2]}
    assert mesh.env == "meshing"
    assert mesh.skip_if({"geom_repr": "line", "elem_order": 2}) is True
    assert mesh.skip_if({"geom_repr": "line", "elem_order": 1}) is False
    assert mesh("aa", geom_repr="solid", elem_order=2) == ("aa", "solid", 2)


def test_name_override():
    @task(name="custom_name")
    def design():
        return None

    assert design.name == "custom_name"


def test_registry_collects_decorations():
    @task
    def alpha():
        return None

    @task(parent=alpha)
    def beta():
        return None

    reg = get_default_registry()
    qnames = reg.known_qualnames()
    assert any(q.endswith(".alpha") for q in qnames)
    assert any(q.endswith(".beta") for q in qnames)


def test_duplicate_registration_raises():
    @task
    def design():
        return None

    # A second @task on a function with the same qualname should raise.
    # Simulate by constructing a TaskFn manually and registering it.
    other = TaskFn(fn=lambda: None, name="design")
    # Force the same qualname as the first by patching __module__.
    other.fn.__module__ = design.fn.__module__
    with pytest.raises(ValueError, match="already registered"):
        get_default_registry().register(other)


def test_parent_string_resolves_after_definition_order():
    """Forward string references resolve at validate() time."""
    reg = TaskRegistry()

    @task(parent="alpha")
    def beta():
        return None

    @task
    def alpha():
        return None

    # alpha came in after beta on the default registry; copy both into a
    # fresh registry to test resolve_parent across the gap.
    reg.register(alpha)
    reg.register(beta)
    resolved = reg.resolve_parent(beta)
    assert resolved is alpha


def test_parent_string_unknown_raises_keyerror():
    @task(parent="nonexistent")
    def orphan():
        return None

    with pytest.raises(KeyError, match="declares parent='nonexistent'"):
        get_default_registry().validate()


def test_cycle_detection():
    reg = TaskRegistry()
    # Two TaskFns referencing each other by string.
    a = TaskFn(fn=lambda: None, name="a", parent="b")
    a.fn.__module__ = "test_cycle"
    b = TaskFn(fn=lambda: None, name="b", parent="a")
    b.fn.__module__ = "test_cycle"
    reg.register(a)
    reg.register(b)
    with pytest.raises(ValueError, match="cycle detected"):
        reg.validate()


def test_task_handle_cells_not_yet_implemented():
    h = TaskHandle(qualname="some.task")
    with pytest.raises(NotImplementedError, match="requires the task runner"):
        h.cells(geom_repr="solid")


def test_discovery_from_doc_root(tmp_path: Path):
    tasks_py = tmp_path / "tasks.py"
    tasks_py.write_text(
        textwrap.dedent(
            """
            from paradoc.tasks import task

            @task
            def design():
                return "a"

            @task(parent=design, fanout={"x": [1, 2]})
            def mesh(a, *, x):
                return (a, x)
            """
        ).lstrip()
    )

    reg = TaskRegistry()
    discover_tasks(doc_root=tmp_path, registry=reg)
    qnames = reg.known_qualnames()
    assert any(q.endswith(".design") for q in qnames)
    assert any(q.endswith(".mesh") for q in qnames)


def test_discovery_no_tasks_py_is_noop(tmp_path: Path):
    """An empty doc_root just yields an empty registry, not an error."""
    reg = TaskRegistry()
    discover_tasks(doc_root=tmp_path, registry=reg)
    assert reg.known_qualnames() == []


def test_discovery_validates_parent_refs(tmp_path: Path):
    tasks_py = tmp_path / "tasks.py"
    tasks_py.write_text(
        textwrap.dedent(
            """
            from paradoc.tasks import task

            @task(parent="ghost")
            def orphan():
                return None
            """
        ).lstrip()
    )

    reg = TaskRegistry()
    with pytest.raises(KeyError, match="ghost"):
        discover_tasks(doc_root=tmp_path, registry=reg)
