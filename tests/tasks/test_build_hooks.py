"""Tests for `build_hooks.py` discovery + orchestrator integration."""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

from paradoc.tasks import (
    BuildHooks,
    load_build_hooks,
    reset_default_registry,
)
from paradoc.tasks.orchestrator import build_document

_ONE_DOC_AVAILABLE = importlib.util.find_spec("paradoc.document") is not None


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- load_build_hooks ----------------


def test_load_missing_file_returns_empty(tmp_path: Path):
    hooks = load_build_hooks(tmp_path)
    assert hooks.empty
    assert hooks.setup is None
    assert hooks.postcompile is None


def test_load_with_both_hooks(tmp_path: Path):
    (tmp_path / "build_hooks.py").write_text(
        textwrap.dedent(
            """
            def setup(one, runner):
                one.metadata['setup_called'] = True

            def postcompile(one):
                one.metadata['postcompile_called'] = True
            """
        ).lstrip()
    )
    hooks = load_build_hooks(tmp_path)
    assert not hooks.empty
    assert callable(hooks.setup)
    assert callable(hooks.postcompile)


def test_load_with_only_setup(tmp_path: Path):
    (tmp_path / "build_hooks.py").write_text("def setup(one, runner): pass\n")
    hooks = load_build_hooks(tmp_path)
    assert callable(hooks.setup)
    assert hooks.postcompile is None


def test_load_with_only_postcompile(tmp_path: Path):
    (tmp_path / "build_hooks.py").write_text("def postcompile(one): pass\n")
    hooks = load_build_hooks(tmp_path)
    assert hooks.setup is None
    assert callable(hooks.postcompile)


def test_load_with_no_functions(tmp_path: Path):
    """A build_hooks.py with no setup/postcompile is treated as empty."""
    (tmp_path / "build_hooks.py").write_text("X = 1\n")
    hooks = load_build_hooks(tmp_path)
    assert hooks.empty


# ---------------- orchestrator integration ----------------


_SIMPLE_TASKS = """
    from paradoc.tasks import task

    @task
    def design():
        return {"v": 1}
"""


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_orchestrator_invokes_setup_and_postcompile(tmp_path: Path):
    doc = tmp_path / "mydoc"
    doc.mkdir()
    (doc / "tasks.py").write_text(textwrap.dedent(_SIMPLE_TASKS).lstrip())
    (doc / "paradoc.toml").write_text("")
    log_path = tmp_path / "hook_calls.log"
    # Append to an out-of-band log file so the test sees the calls
    # even if the hook module gets re-imported (which resets module
    # globals).
    (doc / "build_hooks.py").write_text(
        textwrap.dedent(
            f"""
            from pathlib import Path

            def setup(one, runner):
                assert runner is not None
                assert one is not None
                Path(r'{log_path}').open('a').write('setup\\n')

            def postcompile(one):
                Path(r'{log_path}').open('a').write('postcompile\\n')
            """
        ).lstrip()
    )
    (doc / "00-main").mkdir()
    (doc / "00-main" / "01.md").write_text("# t\n")

    from paradoc.document import OneDoc

    real_compile = OneDoc.compile
    OneDoc.compile = lambda self, name, **kw: None
    try:
        build_document(doc, work_dir=tmp_path / "work", no_cache=True)
    finally:
        OneDoc.compile = real_compile

    assert log_path.read_text().splitlines() == ["setup", "postcompile"]


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_orchestrator_works_without_build_hooks(tmp_path: Path):
    doc = tmp_path / "mydoc"
    doc.mkdir()
    (doc / "tasks.py").write_text(textwrap.dedent(_SIMPLE_TASKS).lstrip())
    (doc / "paradoc.toml").write_text("")
    (doc / "00-main").mkdir()
    (doc / "00-main" / "01.md").write_text("# t\n")

    from paradoc.document import OneDoc

    real_compile = OneDoc.compile
    OneDoc.compile = lambda self, name, **kw: None
    try:
        # Should complete without error even though build_hooks.py
        # doesn't exist.
        build_document(doc, work_dir=tmp_path / "work", no_cache=True)
    finally:
        OneDoc.compile = real_compile


# ---------------- source_dir override ----------------


@pytest.mark.skipif(not _ONE_DOC_AVAILABLE, reason="paradoc.document not importable")
def test_orchestrator_honors_paradoc_source_dir(tmp_path: Path):
    """`[paradoc] source_dir = "report"` makes OneDoc use a subdir for markdown."""
    doc = tmp_path / "mydoc"
    doc.mkdir()
    (doc / "tasks.py").write_text(textwrap.dedent(_SIMPLE_TASKS).lstrip())
    (doc / "paradoc.toml").write_text(
        textwrap.dedent(
            """
            [paradoc]
            source_dir = "report"
            """
        ).lstrip()
    )
    report = doc / "report"
    report.mkdir()
    (report / "00-main").mkdir()
    (report / "00-main" / "01.md").write_text("# t\n")

    observed_source_dirs: list = []
    from paradoc.document import OneDoc

    real_init = OneDoc.__init__

    def _spy_init(self, source_dir=None, **kw):
        observed_source_dirs.append(Path(source_dir).resolve() if source_dir else None)
        real_init(self, source_dir=source_dir, **kw)

    real_compile = OneDoc.compile
    OneDoc.__init__ = _spy_init
    OneDoc.compile = lambda self, name, **kw: None
    try:
        build_document(doc, work_dir=tmp_path / "work", no_cache=True)
    finally:
        OneDoc.__init__ = real_init
        OneDoc.compile = real_compile

    assert observed_source_dirs == [report.resolve()]
