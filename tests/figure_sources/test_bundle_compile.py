"""End-to-end: comment block → glb + png + ThreeDData row + bundle manifest.

CAD rendering needs adapy (and OCC). The CAD-actually-renders path is
tested under tests/figures/ in real workflows; here we verify the
preprocessor + DB integration with a stub filter so the test runs
without optional 3D deps.
"""

from __future__ import annotations

import textwrap

import pytest

from paradoc import OneDoc
from paradoc.docstore import LocalDocStore, read_manifest
from paradoc.figure_sources.filters import register_filter
from paradoc.figure_sources.filters.base import (
    FigureSourceFilter,
    MarkdownChunk,
    RenderResult,
)


@register_filter
class _StubFilter(FigureSourceFilter):
    figure_source = "stub_test_source"

    def render(self, spec, *, key):
        out_dir = self.bundle_root / "assets" / "3d"
        out_dir.mkdir(parents=True, exist_ok=True)

        glb_bytes = b"stub-glb-bytes"
        (out_dir / f"{key}.glb").write_bytes(glb_bytes)

        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
            b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9c"
            b"c\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        (out_dir / f"{key}.png").write_bytes(png_bytes)

        import hashlib

        return RenderResult(
            png_path=f"assets/3d/{key}.png",
            glb_path=f"assets/3d/{key}.glb",
            glb_sha256=hashlib.sha256(glb_bytes).hexdigest(),
            glb_size=len(glb_bytes),
            caption=spec.figure_title,
            camera_pos=spec.camera_pos,
            source_type=self.figure_source,
            metadata={},
        )


# Register a matching pydantic spec for the stub source.
from typing import Literal  # noqa: E402

from paradoc.figure_sources import models as figmod  # noqa: E402


class _StubSpec(figmod.BaseFigureSource):
    figure_source: Literal["stub_test_source"] = "stub_test_source"
    figure_title: str
    camera_pos: str = "iso_3"


# Patch the dispatch factory so create_figure_source recognizes our stub type.
_original_create = figmod.create_figure_source


def _patched_create(data: dict):
    if data.get("figure_source") == "stub_test_source":
        return _StubSpec(**data)
    return _original_create(data)


@pytest.fixture(autouse=True)
def _patch_create_figure_source(monkeypatch):
    from paradoc.figure_sources import preprocessor as preproc

    monkeypatch.setattr(preproc, "create_figure_source", _patched_create)


def test_compile_writes_bundle_artifacts(tmp_path):
    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    (main_dir / "test.md").write_text(
        textwrap.dedent(
            """
            # Test

            <!-- paradoc:figure
            figure_source: stub_test_source
            figure_title: Stub Figure
            camera_pos: iso_3
            -->

            More content.
            """
        )
    )

    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    one.compile("MyDoc", export_format="html")

    bundle = tmp_path / "work" / "_build"

    manifest = read_manifest(bundle)
    assert manifest.doc_id == "MyDoc"
    assert (bundle / "assets" / "presets.json").exists()
    assert (bundle / "paradoc.sqlite").exists()

    glb = bundle / "assets" / "3d" / "stub_test_source_1.glb"
    png = bundle / "assets" / "3d" / "stub_test_source_1.png"
    assert glb.exists()
    assert png.exists()

    md_out = (bundle / "00-main" / "test.md").read_text()
    assert "stub_test_source_1.png" in md_out
    assert "data-3d-key=stub_test_source_1" in md_out
    assert "<!-- paradoc:figure" not in md_out


@register_filter
class _ChunkedStubFilter(FigureSourceFilter):
    """Stub that returns a mixed list of MarkdownChunk + RenderResult.

    Mimics the per-case grouping filter shape: heading chunk, figure,
    heading chunk, figure. The preprocessor must splice chunks as-is
    and register one ThreeDData row per RenderResult (not per chunk).
    """

    figure_source = "chunked_stub_source"

    def render(self, spec, *, key):
        out_dir = self.bundle_root / "assets" / "3d"
        out_dir.mkdir(parents=True, exist_ok=True)

        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
            b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9c"
            b"c\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        glb_bytes = b"chunked-glb-bytes"

        import hashlib

        def _result(sub_key: str, caption: str) -> RenderResult:
            (out_dir / f"{sub_key}.glb").write_bytes(glb_bytes)
            (out_dir / f"{sub_key}.png").write_bytes(png_bytes)
            return RenderResult(
                png_path=f"assets/3d/{sub_key}.png",
                glb_path=f"assets/3d/{sub_key}.glb",
                glb_sha256=hashlib.sha256(glb_bytes).hexdigest(),
                glb_size=len(glb_bytes),
                caption=caption,
                camera_pos=spec.camera_pos,
                source_type=self.figure_source,
                metadata={},
            )

        # Sub-keys derive from the allocated `key` the same way the
        # preprocessor would have keyed sequential figures: <key>,
        # <key>_2 — so they round-trip cleanly when the test asserts
        # ThreeDData rows.
        return [
            MarkdownChunk(text="#### Mode 1\n"),
            _result(key, caption="Mode 1"),
            MarkdownChunk(text="\n#### Mode 2\n"),
            _result(f"{key}_2", caption="Mode 2"),
        ]


class _ChunkedStubSpec(figmod.BaseFigureSource):
    figure_source: Literal["chunked_stub_source"] = "chunked_stub_source"
    figure_title: str
    camera_pos: str = "iso_3"


def _patched_create_with_chunked(data: dict):
    if data.get("figure_source") == "chunked_stub_source":
        return _ChunkedStubSpec(**data)
    return _patched_create(data)


@pytest.fixture
def _patch_create_chunked(monkeypatch):
    from paradoc.figure_sources import preprocessor as preproc

    monkeypatch.setattr(preproc, "create_figure_source", _patched_create_with_chunked)


def test_mixed_chunk_and_result_list_splices_headings_between_figures(
    tmp_path, _patch_create_chunked
):
    """A filter returning [chunk, result, chunk, result] should produce
    markdown where the chunk text appears verbatim between figure
    references, and one ThreeDData row gets registered per RenderResult
    (not per chunk)."""
    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    (main_dir / "test.md").write_text(
        textwrap.dedent(
            """
            # Test

            <!-- paradoc:figure
            figure_source: chunked_stub_source
            figure_title: Chunked
            camera_pos: iso_3
            -->

            After.
            """
        )
    )

    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    one.compile("MyDoc", export_format="html")

    bundle = tmp_path / "work" / "_build"
    md_out = (bundle / "00-main" / "test.md").read_text()

    # Chunk text appears verbatim.
    assert "#### Mode 1" in md_out
    assert "#### Mode 2" in md_out
    # Both figures rendered with the right derived sub-keys.
    assert "chunked_stub_source_1.png" in md_out
    assert "chunked_stub_source_1_2.png" in md_out
    assert "data-3d-key=chunked_stub_source_1" in md_out
    assert "data-3d-key=chunked_stub_source_1_2" in md_out
    # No leaked comment block.
    assert "<!-- paradoc:figure" not in md_out
    # Heading appears before its figure (basic ordering check).
    assert md_out.index("#### Mode 1") < md_out.index("chunked_stub_source_1.png")
    assert md_out.index("#### Mode 2") < md_out.index("chunked_stub_source_1_2.png")

    # Two ThreeDData rows, not four (chunks don't register rows). Read
    # the sqlite directly rather than via LocalDocStore so the test runs
    # without paradoc.serve's fastapi dependency.
    import sqlite3

    with sqlite3.connect(bundle / "paradoc.sqlite") as conn:
        keys = sorted(
            row[0]
            for row in conn.execute(
                "SELECT key FROM three_d WHERE source_type = ?",
                ("chunked_stub_source",),
            )
        )
    assert keys == ["chunked_stub_source_1", "chunked_stub_source_1_2"]


def test_docstore_serves_compiled_bundle(tmp_path):
    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    (main_dir / "test.md").write_text(
        textwrap.dedent(
            """
            <!-- paradoc:figure
            figure_source: stub_test_source
            figure_title: First
            camera_pos: iso_3
            -->
            """
        )
    )
    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    one.compile("MyDoc", export_format="html")

    bundle = tmp_path / "work" / "_build"
    store = LocalDocStore(bundle)
    meta = store.get_three_d_meta("MyDoc", "stub_test_source_1")
    assert meta is not None
    assert meta.format == "glb"
    assert meta.camera_pos == "iso_3"
    assert meta.size > 0
