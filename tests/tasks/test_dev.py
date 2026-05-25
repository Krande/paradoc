"""Tests for `paradoc dev` helpers.

The async serve+watch loop itself is integration-heavy (binds ports,
spawns watchdog Observer, talks WebSocket); covered indirectly by a
smoke pass in adapy's verification env. The pure helpers
(`_inject_reload_script`, `_is_ignored`, `_resolve_bundle_dir`,
`_watch_paths`) are unit-testable here.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from paradoc.tasks.dev import (
    _INJECTION_MARKER,
    _inject_reload_script,
    _is_ignored,
    _resolve_bundle_dir,
    _watch_paths,
)


# ---------------- reload script injection ----------------


def test_inject_reload_script_inserts_before_body(tmp_path: Path):
    html = tmp_path / "index.html"
    html.write_text("<html><body>hi</body></html>")
    _inject_reload_script(html, ws_port=12345)
    out = html.read_text()
    assert _INJECTION_MARKER in out
    assert "ws://" in out
    assert "12345" in out
    # script lands before </body>
    assert out.index("paradoc dev") < out.index("</body>")


def test_inject_reload_script_is_idempotent(tmp_path: Path):
    html = tmp_path / "index.html"
    html.write_text("<html><body>hi</body></html>")
    _inject_reload_script(html, ws_port=12345)
    first = html.read_text()
    _inject_reload_script(html, ws_port=12345)
    assert html.read_text() == first  # no duplicate inject


def test_inject_reload_script_no_body_tag_appends(tmp_path: Path):
    """Robust to malformed HTML — append at the end."""
    html = tmp_path / "index.html"
    html.write_text("<html>no body tag here</html>")
    _inject_reload_script(html, ws_port=9000)
    assert _INJECTION_MARKER in html.read_text()


def test_inject_reload_script_missing_file_is_warning_not_error(tmp_path: Path):
    """A missing index.html shouldn't raise — log + carry on."""
    _inject_reload_script(tmp_path / "absent.html", ws_port=8000)


# ---------------- ignored paths ----------------


def test_is_ignored_filters_cache(tmp_path: Path):
    assert _is_ignored(tmp_path / ".paradoc-cache" / "x.pkl", tmp_path) is True
    assert _is_ignored(tmp_path / "__pycache__" / "tasks.cpython-312.pyc", tmp_path) is True
    assert _is_ignored(tmp_path / "temp" / "x.txt", tmp_path) is True
    assert _is_ignored(tmp_path / ".cache" / "y.json", tmp_path) is True


def test_is_ignored_lets_real_sources_through(tmp_path: Path):
    assert _is_ignored(tmp_path / "tasks.py", tmp_path) is False
    assert _is_ignored(tmp_path / "report" / "00-main" / "intro.md", tmp_path) is False
    assert _is_ignored(tmp_path / "filters.py", tmp_path) is False


# ---------------- watch path resolution ----------------


def test_watch_paths_includes_report_when_present(tmp_path: Path):
    doc = tmp_path / "doc"
    doc.mkdir()
    (doc / "tasks.py").write_text("")
    (doc / "filters.py").write_text("")
    (doc / "paradoc.toml").write_text("")
    (doc / "report").mkdir()
    (doc / "report" / "intro.md").write_text("")

    paths = _watch_paths(doc)
    assert (doc / "tasks.py") in paths
    assert (doc / "filters.py") in paths
    assert (doc / "paradoc.toml") in paths
    assert (doc / "report") in paths


def test_watch_paths_falls_back_to_doc_root_without_report(tmp_path: Path):
    doc = tmp_path / "doc"
    doc.mkdir()
    (doc / "tasks.py").write_text("")
    paths = _watch_paths(doc)
    assert doc in paths


def test_watch_paths_skips_missing_files(tmp_path: Path):
    doc = tmp_path / "doc"
    doc.mkdir()
    # only tasks.py exists; filters.py + paradoc.toml don't
    (doc / "tasks.py").write_text("")
    paths = _watch_paths(doc)
    assert (doc / "tasks.py") in paths
    assert (doc / "filters.py") not in paths
    assert (doc / "paradoc.toml") not in paths


# ---------------- bundle dir resolution ----------------


def test_resolve_bundle_dir_finds_static_subdir(tmp_path: Path):
    work_dir = tmp_path / "work"
    static = work_dir / "_build" / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text("")
    one = SimpleNamespace(work_dir=str(work_dir))
    assert _resolve_bundle_dir(one) == static


def test_resolve_bundle_dir_falls_back_to_work_dir(tmp_path: Path):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    one = SimpleNamespace(work_dir=str(work_dir))
    # No index.html anywhere -> falls back to work_dir.
    assert _resolve_bundle_dir(one) == work_dir
