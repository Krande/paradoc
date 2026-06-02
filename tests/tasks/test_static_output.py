"""`outputs = ["static"]` dispatches to OneDoc.export_static with
the `[build.<profile>.static]` configuration."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from paradoc.tasks import StaticExportConfig, load_task_config, reset_default_registry


@pytest.fixture(autouse=True)
def _isolate():
    reset_default_registry()
    yield
    reset_default_registry()


# ---------------- config parsing ----------------


def _write_toml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "paradoc.toml"
    p.write_text(textwrap.dedent(body).lstrip())
    return p


def test_static_config_defaults_when_absent(tmp_path: Path):
    """A profile that lists `outputs = ["static"]` but no
    `[build.<profile>.static]` table loads cleanly with config.static = None;
    the orchestrator falls back to defaults at dispatch time."""
    toml = _write_toml(
        tmp_path,
        """
        [build.default]
        outputs = ["static"]
        """,
    )
    cfg = load_task_config(toml, profile="default")
    assert cfg.outputs == ["static"]
    assert cfg.static is None


def test_static_config_parses_full_subtable(tmp_path: Path):
    toml = _write_toml(
        tmp_path,
        """
        [build.default]
        outputs = ["static"]

        [build.default.static]
        target = "docs/_static/report"
        embed_images = false
        include_frontend = true
        header_links = [
            { label = "Back to docs", href = "../../index.html" },
            { label = "Source", href = "https://example.com" },
        ]
        """,
    )
    cfg = load_task_config(toml, profile="default")
    assert cfg.static is not None
    assert cfg.static.target == "docs/_static/report"
    assert cfg.static.embed_images is False
    assert cfg.static.include_frontend is True
    assert cfg.static.header_links == [
        {"label": "Back to docs", "href": "../../index.html"},
        {"label": "Source", "href": "https://example.com"},
    ]


def test_static_config_target_relative_anchors_at_doc_root():
    """Static is the only place where 'target' becomes an actual
    filesystem path — the orchestrator does the doc_root resolve, not
    the loader. This test pins the default; full dispatch is covered
    below."""
    cfg = StaticExportConfig()
    assert cfg.target == "static_output"
    assert cfg.embed_images is True
    assert cfg.include_frontend is True
    assert cfg.header_links is None


def test_static_config_rejects_unknown_keys(tmp_path: Path):
    """Mistyped keys must fail loud — silent typos are a class of bugs
    the strict schema is meant to catch."""
    toml = _write_toml(
        tmp_path,
        """
        [build.default]
        outputs = ["static"]

        [build.default.static]
        targat = "oops"
        """,
    )
    with pytest.raises(Exception):  # pydantic ValidationError
        load_task_config(toml, profile="default")


# ---------------- orchestrator dispatch ----------------


def test_orchestrator_dispatches_static_to_export_static(tmp_path: Path):
    """`outputs = ["static"]` triggers `OneDoc.export_static`, not
    `OneDoc.compile` — pandoc/docx must not be invoked."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    (doc_root / "tasks.py").write_text(
        "from paradoc.tasks import task\n\n" "@task\n" "def placeholder():\n" "    return None\n"
    )
    (doc_root / "00-main").mkdir()
    (doc_root / "00-main" / "01-intro.md").write_text("# heading\n")
    (doc_root / "metadata.yaml").write_text("title: t\n")
    _write_toml(
        doc_root,
        """
        [build.default]
        outputs = ["static"]

        [build.default.static]
        target = "bundle"
        header_links = [{ label = "Home", href = "/" }]
        """,
    )

    from paradoc.tasks import build_document

    with (
        patch("paradoc.document.OneDoc.compile") as mock_compile,
        patch("paradoc.document.OneDoc.export_static") as mock_static,
    ):
        mock_static.return_value = True
        build_document(doc_root, profile="default", auto_open=False)

    mock_compile.assert_not_called()
    mock_static.assert_called_once()
    args, kwargs = mock_static.call_args
    target = Path(args[0]) if args else Path(kwargs["output_dir"])
    assert target == doc_root / "bundle"
    assert kwargs["header_links"] == [{"label": "Home", "href": "/"}]


def test_orchestrator_static_uses_defaults_when_subtable_absent(tmp_path: Path):
    """No `[build.<profile>.static]` → export_static still runs, with
    the default target/header_links."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    (doc_root / "tasks.py").write_text(
        "from paradoc.tasks import task\n\n" "@task\n" "def placeholder():\n" "    return None\n"
    )
    (doc_root / "00-main").mkdir()
    (doc_root / "00-main" / "01-intro.md").write_text("# heading\n")
    (doc_root / "metadata.yaml").write_text("title: t\n")
    _write_toml(
        doc_root,
        """
        [build.default]
        outputs = ["static"]
        """,
    )

    from paradoc.tasks import build_document

    with (
        patch("paradoc.document.OneDoc.compile") as mock_compile,
        patch("paradoc.document.OneDoc.export_static") as mock_static,
    ):
        mock_static.return_value = True
        build_document(doc_root, profile="default", auto_open=False)

    mock_compile.assert_not_called()
    mock_static.assert_called_once()
    args, kwargs = mock_static.call_args
    target = Path(args[0]) if args else Path(kwargs["output_dir"])
    assert target == doc_root / "static_output"
    assert kwargs["header_links"] is None
    assert kwargs["embed_images"] is True
    assert kwargs["include_frontend"] is True


def test_orchestrator_static_can_coexist_with_docx(tmp_path: Path):
    """A profile listing both formats invokes both code paths."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    (doc_root / "tasks.py").write_text(
        "from paradoc.tasks import task\n\n" "@task\n" "def placeholder():\n" "    return None\n"
    )
    (doc_root / "00-main").mkdir()
    (doc_root / "00-main" / "01-intro.md").write_text("# heading\n")
    (doc_root / "metadata.yaml").write_text("title: t\n")
    _write_toml(
        doc_root,
        """
        [build.default]
        outputs = ["docx", "static"]
        """,
    )

    from paradoc.tasks import build_document

    with (
        patch("paradoc.document.OneDoc.compile") as mock_compile,
        patch("paradoc.document.OneDoc.export_static") as mock_static,
    ):
        mock_static.return_value = True
        build_document(doc_root, profile="default", auto_open=False)

    mock_compile.assert_called_once()
    mock_static.assert_called_once()


def test_orchestrator_static_target_absolute_passes_through(tmp_path: Path):
    """An absolute static `target` is used as-is — no doc_root anchoring."""
    doc_root = tmp_path / "doc"
    doc_root.mkdir()
    abs_target = tmp_path / "elsewhere" / "bundle"
    (doc_root / "tasks.py").write_text(
        "from paradoc.tasks import task\n\n" "@task\n" "def placeholder():\n" "    return None\n"
    )
    (doc_root / "00-main").mkdir()
    (doc_root / "00-main" / "01-intro.md").write_text("# heading\n")
    (doc_root / "metadata.yaml").write_text("title: t\n")
    _write_toml(
        doc_root,
        f"""
        [build.default]
        outputs = ["static"]

        [build.default.static]
        target = "{abs_target}"
        """,
    )

    from paradoc.tasks import build_document

    with patch("paradoc.document.OneDoc.compile"), patch("paradoc.document.OneDoc.export_static") as mock_static:
        mock_static.return_value = True
        build_document(doc_root, profile="default", auto_open=False)

    args, kwargs = mock_static.call_args
    target = Path(args[0]) if args else Path(kwargs["output_dir"])
    assert target == abs_target
