"""REST-mode 3D viewer regression tests.

Boots `paradoc.serve.create_app` against a compiled bundle and points
Playwright at the served URL. Targets the bugs we observed on
paradoc.krande.no:

  - `manifest.sections[].index` references sections that `/api/docs/
    <id>/sections/<idx>` then 404s ("section N fetch failed: HTTP
    404").
  - WebSocket reconnect loop to `ws://localhost:13579/` in production
    (runtime config not landing → frontend defaults to WS transport).
  - `/manifest.json` 404 (the SPA's `<link rel="manifest">` PWA fetch
    landing on a path the server doesn't expose — cosmetic but
    pollutes console).

Skipped when FastAPI/uvicorn aren't installed (the `serve` extra).
"""

from __future__ import annotations

import hashlib
import socket
import threading
import time
from pathlib import Path
from typing import Literal

import pytest

from paradoc import OneDoc
from paradoc.figure_sources import models as figmod
from paradoc.figure_sources.filters import register_filter
from paradoc.figure_sources.filters.base import FigureSourceFilter, RenderResult

_FIXTURE_GLB = Path(__file__).parent.parent.parent / "files" / "doc_figure_sources" / "files" / "cad.glb"

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
    b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9c"
    b"c\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@register_filter
class _RestGlbStubFilter(FigureSourceFilter):
    figure_source = "rest_glb_stub"

    def render(self, spec, *, key):
        out_dir = self.bundle_root / "assets" / "3d"
        out_dir.mkdir(parents=True, exist_ok=True)

        glb_bytes = _FIXTURE_GLB.read_bytes()
        (out_dir / f"{key}.glb").write_bytes(glb_bytes)
        (out_dir / f"{key}.png").write_bytes(_MIN_PNG)

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


class _RestGlbStubSpec(figmod.BaseFigureSource):
    figure_source: Literal["rest_glb_stub"] = "rest_glb_stub"
    figure_title: str
    camera_pos: str = "iso_3"


_original_create = figmod.create_figure_source


def _patched_create(data: dict):
    if data.get("figure_source") == "rest_glb_stub":
        return _RestGlbStubSpec(**data)
    return _original_create(data)


@pytest.fixture(autouse=True)
def _patch_create_figure_source(monkeypatch):
    from paradoc.figure_sources import preprocessor as preproc

    monkeypatch.setattr(preproc, "create_figure_source", _patched_create)


def _free_port() -> int:
    """Grab an unused TCP port on localhost. Race-y vs. another binder
    but good enough for a single test run."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def served_bundle(tmp_path):
    """Compile a tiny doc, then spin up `paradoc-serve` against the
    bundle in a background uvicorn thread. Yields the base URL.
    """
    pytest.importorskip("fastapi")
    pytest.importorskip("uvicorn")

    if not _FIXTURE_GLB.exists():
        pytest.skip(f"GLB fixture missing: {_FIXTURE_GLB}")

    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    md = (
        "# REST 3D Viewer Test\n"
        "\n"
        "Intro paragraph so the figure stands alone.\n"
        "\n"
        "<!-- paradoc:figure\n"
        "figure_source: rest_glb_stub\n"
        "figure_title: REST Test 3D Figure\n"
        "camera_pos: iso_3\n"
        "-->\n"
        "\n"
        "Body content.\n" + "\nFiller paragraph.\n" * 40
    )
    (main_dir / "test.md").write_text(md)

    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    one.compile("RestTestDoc", export_format="html")
    bundle = tmp_path / "work" / "_build"
    # `compile()` writes both the root-level `manifest.json` (for
    # `LocalDocStore.list_doc_ids()` discovery) and the REST-servable
    # `<bundle>/static/manifest.json` (read by `_read_static`).
    assert (bundle / "manifest.json").exists(), "compile didn't produce manifest.json"
    assert (bundle / "static" / "manifest.json").exists(), (
        "compile didn't populate <bundle>/static/manifest.json — REST mode " "will 404 on `/api/docs/<id>/manifest`."
    )

    # Ensure the bundled frontend is extracted; we point `static_dir`
    # at it so paradoc-serve also serves the SPA shell at /.
    from paradoc.frontend.frontend_handler import FrontendHandler

    fh = FrontendHandler(one, host="localhost", port=13579)
    assert fh.ensure_frontend_extracted(), "frontend.zip not extracted"
    frontend_dir = fh.resources_dir

    import uvicorn

    from paradoc.docstore import LocalDocStore
    from paradoc.serve.app import create_app

    app = create_app(doc_store=LocalDocStore(bundle), static_dir=frontend_dir)

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True, name="paradoc-serve-test")
    server_thread.start()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if getattr(server, "started", False):
            break
        time.sleep(0.05)
    else:
        pytest.fail("paradoc-serve test server did not start within 10s")

    base = f"http://127.0.0.1:{port}"
    try:
        yield base, "RestTestDoc"
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)


def _attach_recorders(page):
    console_messages: list[tuple[str, str]] = []
    failed_responses: list[tuple[str, int]] = []
    ws_attempts: list[str] = []

    page.on("console", lambda msg: console_messages.append((msg.type, msg.text)))
    page.on(
        "response",
        lambda res: failed_responses.append((res.url, res.status)) if res.status >= 400 else None,
    )
    page.on("websocket", lambda ws: ws_attempts.append(ws.url))

    return console_messages, failed_responses, ws_attempts


def test_rest_mode_no_section_404s(served_bundle, page, wait_for_frontend):
    """`loadRestData` iterates `manifest.sections[].index`. Every
    promised index must resolve via `/api/docs/<id>/sections/<idx>`.
    The paradoc.krande.no incident logged
    `[paradoc] section 5 fetch failed: HTTP 404` for indices 5-9 —
    the manifest claimed they existed but the section endpoint 404'd.
    """
    base, _doc_id = served_bundle
    _, failed_responses, _ = _attach_recorders(page)

    page.goto(f"{base}/")
    wait_for_frontend(page)
    page.wait_for_timeout(2000)

    section_404s = [(url, status) for url, status in failed_responses if "/sections/" in url and status == 404]
    assert not section_404s, f"manifest promised sections that the section endpoint can't " f"deliver: {section_404s}"


def test_rest_mode_does_not_attempt_websocket(served_bundle, page, wait_for_frontend):
    """When `transport: 'rest'` is in effect, the WS transport should
    never initialize. The prod log showed
    `WebSocket connection to 'ws://localhost:13579/' failed` in a
    reconnect loop — that means runtime config didn't reach the page
    (bundled `index.html` is missing `<script src="/config.js">`)
    and the frontend fell back to its WS default.
    """
    base, _doc_id = served_bundle
    _, _, ws_attempts = _attach_recorders(page)

    page.goto(f"{base}/")
    wait_for_frontend(page)
    page.wait_for_timeout(2000)

    ws_localhost = [u for u in ws_attempts if u.startswith("ws://localhost")]
    assert not ws_localhost, (
        f"REST-mode SPA attempted WebSocket connection(s) to "
        f"{ws_localhost}. Runtime config (`transport: 'rest'`) is not "
        "being delivered to the page — check that the bundled index.html "
        "references /config.js."
    )


def test_rest_mode_3d_viewer_mounts(served_bundle, page, wait_for_frontend):
    """End-to-end: page loads, 3D figure poster appears, clicking
    "Load interactive 3D viewer" mounts a canvas without console
    errors and without falling back to the hardcoded preset.

    `paradoc-serve` lands on a doc picker for multi-doc deployments;
    in single-doc mode the picker still appears with one entry. We
    click into the doc by name to reach the figure-bearing page.
    """
    base, doc_id = served_bundle
    console_messages, failed_responses, _ = _attach_recorders(page)

    page.goto(f"{base}/")
    wait_for_frontend(page)

    # Click the doc-picker entry to navigate into the doc itself.
    page.locator(f'button:has-text("{doc_id}")').first.click(timeout=10000)

    load_btn = page.locator('button:has-text("Load interactive 3D viewer")').first
    load_btn.wait_for(timeout=15000)
    load_btn.click()
    page.wait_for_selector("canvas", timeout=15000)
    page.wait_for_timeout(500)

    fallback_warnings = [
        text for kind, text in console_messages if kind == "warning" and "failed to load presets" in text
    ]
    assert not fallback_warnings, (
        f"ThreeDRenderer fell back to hardcoded preset on REST: "
        f"{fallback_warnings}. The /api/docs/<id>/presets endpoint may "
        "be broken or unreachable."
    )

    # The browser logs a generic "Failed to load resource" without
    # the URL for every 4xx response, so console.error counts include
    # noise unrelated to the viewer. Instead, assert on the URL-bearing
    # failed_responses list, ignoring the `/manifest.json` PWA 404
    # (covered by its own dedicated test).
    non_pwa_404s = [
        (url, status) for url, status in failed_responses if not (url.endswith("/manifest.json") and "/api/" not in url)
    ]
    assert not non_pwa_404s, (
        f"failed responses during REST 3D mount (excluding the PWA " f"manifest noise): {non_pwa_404s}"
    )


def test_rest_mode_no_root_manifest_json_404(served_bundle, page, wait_for_frontend):
    """The browser auto-fetches `/manifest.json` from
    `<link rel="manifest">`. paradoc-serve's StaticFiles mount doesn't
    ship one, so this 404s on every page load. Either the link should
    be removed from the bundled HTML, or the server should serve a
    minimal PWA manifest.
    """
    base, _doc_id = served_bundle
    _, failed_responses, _ = _attach_recorders(page)

    page.goto(f"{base}/")
    wait_for_frontend(page)
    page.wait_for_timeout(1500)

    root_manifest_404 = [
        (url, status)
        for url, status in failed_responses
        if url.endswith("/manifest.json") and status == 404 and "/api/" not in url
    ]
    assert not root_manifest_404, (
        f"`/manifest.json` 404'd: {root_manifest_404}. The bundled HTML "
        "still has a PWA manifest link the server doesn't satisfy."
    )
