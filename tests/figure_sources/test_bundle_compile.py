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
from paradoc.figure_sources.filters.base import FigureSourceFilter, RenderResult


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
