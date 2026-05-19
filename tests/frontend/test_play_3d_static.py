"""Static-export 3D viewer regression tests.

Targets the bug class we hit in production three times running:
  - `assets/presets.json` 404 → fallback preset that can't frame the
    model (the "FEA viewer goes black after growing past the screen"
    incident).
  - viewer hijacks page scroll (cursor-over-canvas wheel events
    `preventDefault`ed everywhere, not just over the GL surface).
  - canvas grows beyond its container.

Pattern mirrors `tests/figure_sources/test_bundle_compile.py` (stub
filter so the test runs in the cheap `test` pixi env without adapy /
OCC), but the stub here writes a real 4.5KB GLB so the embed's
`setupModelLoaderAsync` actually succeeds and the canvas mounts.

If the GLB fixture is missing the tests skip rather than fail; the
file ships with the `doc_figure_sources` example, so a fresh checkout
will have it.
"""

from __future__ import annotations

import hashlib
import http.server
import socketserver
import threading
from pathlib import Path
from typing import Literal

import pytest

from paradoc import OneDoc
from paradoc.figure_sources import models as figmod
from paradoc.figure_sources.filters import register_filter
from paradoc.figure_sources.filters.base import FigureSourceFilter, RenderResult


# Real 1-triangle CAD-shaped GLB so adapy's GLTFLoader + prepareLoadedModel
# accept it. 4.5KB; checked in under `files/doc_figure_sources/files/`.
_FIXTURE_GLB = (
    Path(__file__).parent.parent.parent
    / "files"
    / "doc_figure_sources"
    / "files"
    / "cad.glb"
)

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00"
    b"\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9c"
    b"c\x00\x01\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@register_filter
class _RealGlbStubFilter(FigureSourceFilter):
    """Stub filter that copies a real GLB into the bundle.

    Matches the `_StubFilter` pattern from `tests/figure_sources/
    test_bundle_compile.py`, but the GLB it emits is a real
    glTF-binary (4.5KB) so the frontend viewer's adapy ingest pipeline
    succeeds instead of erroring on garbage bytes.
    """

    figure_source = "real_glb_stub"

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


class _RealGlbStubSpec(figmod.BaseFigureSource):
    figure_source: Literal["real_glb_stub"] = "real_glb_stub"
    figure_title: str
    camera_pos: str = "iso_3"


_original_create = figmod.create_figure_source


def _patched_create(data: dict):
    if data.get("figure_source") == "real_glb_stub":
        return _RealGlbStubSpec(**data)
    return _original_create(data)


@pytest.fixture(autouse=True)
def _patch_create_figure_source(monkeypatch):
    from paradoc.figure_sources import preprocessor as preproc

    monkeypatch.setattr(preproc, "create_figure_source", _patched_create)


def _serve_dir(directory: Path) -> tuple[str, threading.Thread, socketserver.TCPServer]:
    """Spin up a threading HTTP server rooted at `directory`. Chromium
    blocks `fetch()` over `file://` (security restriction), so the
    static bundle must be served over HTTP — matches how the bundle
    is hosted in production (nginx, GitHub Pages, etc.).
    """
    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    # Port 0 → let the OS pick a free port.
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _QuietHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="static-bundle-http")
    thread.start()
    return f"http://127.0.0.1:{port}", thread, httpd


@pytest.fixture
def static_bundle(tmp_path):
    """Build a tiny doc with one 3D figure, static-export it, and
    serve it over HTTP. Yields the base URL.

    Bundle is the full static-web output (manifest.json, sections/,
    assets/3d/, assets/presets.json, the bundled frontend).
    """
    if not _FIXTURE_GLB.exists():
        pytest.skip(f"GLB fixture missing: {_FIXTURE_GLB}")

    test_dir = tmp_path / "doc"
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    # Indentation matters: the figure block must land at column 0 so
    # Pandoc treats it as a directive (and the resulting `![...]`
    # expansion as a paragraph that becomes an implicit Figure block),
    # not as an indented code block.
    md = (
        "# Static 3D Viewer Test\n"
        "\n"
        "Intro paragraph so the figure stands alone in its own paragraph.\n"
        "\n"
        "<!-- paradoc:figure\n"
        "figure_source: real_glb_stub\n"
        "figure_title: Test 3D Figure\n"
        "camera_pos: iso_3\n"
        "-->\n"
        "\n"
        "Trailing content so the page is scrollable past the viewer.\n"
        # Need enough content below the 4:3 viewer (which at 1280-wide
        # viewport is ~960px tall) so the page is unambiguously
        # scrollable past it.
        + "\nFiller paragraph with enough words to break across lines.\n" * 100
    )
    (main_dir / "test.md").write_text(md)

    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    out_dir = tmp_path / "static_out"
    assert one.export_static(out_dir), "export_static failed"
    assert (out_dir / "index.html").exists(), "static export missing index.html"

    base_url, thread, httpd = _serve_dir(out_dir)
    try:
        yield base_url
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2.0)


def _attach_recorders(page):
    """Capture console messages + failed network requests for assertions."""
    console_messages: list[tuple[str, str]] = []
    failed_requests: list[tuple[str, str]] = []
    ws_attempts: list[str] = []

    page.on("console", lambda msg: console_messages.append((msg.type, msg.text)))
    page.on(
        "requestfailed",
        lambda req: failed_requests.append((req.url, req.failure or "")),
    )
    page.on(
        "response",
        lambda res: failed_requests.append((res.url, f"HTTP {res.status}"))
        if res.status >= 400
        else None,
    )
    page.on("websocket", lambda ws: ws_attempts.append(ws.url))

    return console_messages, failed_requests, ws_attempts


def test_static_export_3d_viewer_mounts_without_presets_404(
    static_bundle, page, wait_for_frontend
):
    """The original ada-docs incident: `presets.json` is 404, the
    fallback preset only ships `iso_3`, and the canvas can't frame a
    model whose registered `camera_pos` isn't in the fallback set.

    Asserting:
      - `assets/presets.json` returns 200 (not 404).
      - No "[ThreeDRenderer] failed to load presets; using fallback"
        console warning.
      - The viewer mounts (a `<canvas>` is in the DOM).
    """
    console_messages, failed_requests, _ = _attach_recorders(page)

    page.goto(f"{static_bundle}/")
    wait_for_frontend(page)

    # The figure starts as a poster placeholder. Mount the live viewer.
    load_btn = page.locator('button:has-text("Load interactive 3D viewer")').first
    load_btn.wait_for(timeout=10000)
    load_btn.click()

    # Canvas should appear once the GLB downloads + adapy ingests it.
    page.wait_for_selector("canvas", timeout=15000)

    # Give the lazy ThreeDRenderer time to fire its presets fetch.
    page.wait_for_timeout(500)

    presets_404s = [
        url for url, reason in failed_requests if "presets.json" in url and "404" in reason
    ]
    assert not presets_404s, f"presets.json 404'd: {presets_404s}"

    fallback_warnings = [
        text for kind, text in console_messages
        if kind == "warning" and "failed to load presets" in text
    ]
    assert not fallback_warnings, (
        f"ThreeDRenderer fell back to hardcoded preset: {fallback_warnings}"
    )


def test_static_export_3d_viewer_does_not_hijack_page_scroll(
    static_bundle, page, wait_for_frontend
):
    """The bug from paradoc.krande.no: enabling the viewer makes the
    surrounding paradoc page un-scrollable.

    The SPA puts `html` / `body` in `overflow: hidden` and scrolls
    inside `[data-search-root]` (VirtualReader's container). The
    assertion targets that container, not window.scrollY which is
    structurally always 0 in this layout.
    """
    page.goto(f"{static_bundle}/")
    wait_for_frontend(page)

    load_btn = page.locator('button:has-text("Load interactive 3D viewer")').first
    load_btn.wait_for(timeout=10000)
    load_btn.click()
    page.wait_for_selector("canvas", timeout=15000)
    page.wait_for_timeout(500)

    # The inner reader is the scroll target.
    scroller_info = page.evaluate(
        "() => { const el = document.querySelector('[data-search-root]'); "
        "if (!el) return null; "
        "return { scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, "
        "scrollTop: el.scrollTop }; }"
    )
    assert scroller_info is not None, "VirtualReader scroll container not found"
    assert scroller_info["scrollHeight"] > scroller_info["clientHeight"], (
        f"reader container is not scrollable: scrollHeight "
        f"{scroller_info['scrollHeight']}px ≤ clientHeight "
        f"{scroller_info['clientHeight']}px (viewer may have collapsed the layout)"
    )

    # Reset to top, then wheel inside the reader container outside the
    # canvas (below it, since the viewer is near the top and filler is
    # below). The desktop sidebar occupies the left ~288px on desktop
    # viewports — wheel from the reader's own bounding rect so the test
    # is layout-independent.
    reader_rect = page.evaluate(
        "() => document.querySelector('[data-search-root]').getBoundingClientRect().toJSON()"
    )
    page.evaluate("document.querySelector('[data-search-root]').scrollTop = 0")
    initial = page.evaluate("document.querySelector('[data-search-root]').scrollTop")
    # Bottom-right area of the reader, well past the canvas region.
    wheel_x = int(reader_rect["x"] + reader_rect["width"] - 20)
    wheel_y = int(reader_rect["y"] + reader_rect["height"] - 20)
    page.mouse.move(wheel_x, wheel_y)
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(200)
    after = page.evaluate("document.querySelector('[data-search-root]').scrollTop")
    assert after > initial, (
        f"reader scrollTop did not advance on wheel outside canvas "
        f"(initial={initial}, after={after}). The viewer is hijacking wheel events."
    )


def test_static_export_3d_viewer_canvas_stays_within_container(
    static_bundle, page, wait_for_frontend
):
    """Canvas height should match the 4:3 container, not blow up to
    window.innerHeight × something. The "FEA viewer black screen"
    bug had the canvas growing past 5000px tall.
    """
    page.goto(f"{static_bundle}/")
    wait_for_frontend(page)

    load_btn = page.locator('button:has-text("Load interactive 3D viewer")').first
    load_btn.wait_for(timeout=10000)
    load_btn.click()
    page.wait_for_selector("canvas", timeout=15000)
    page.wait_for_timeout(500)

    # The ThreeDRenderer mounts the canvas inside a div with
    # `aspect-ratio: 4/3` and `max-w-full`. The canvas itself should
    # fit inside that wrapper — assert its bounding rect height stays
    # well under the viewport (a 1000px-wide viewer at 4:3 is 750px;
    # we allow up to 2× viewport just to keep the assertion stable
    # across browsers / pixel ratios).
    rect = page.evaluate(
        "() => { const c = document.querySelector('canvas'); "
        "if (!c) return null; const r = c.getBoundingClientRect(); "
        "return { width: r.width, height: r.height }; }"
    )
    assert rect is not None, "no canvas in DOM after mount"
    vh = page.evaluate("window.innerHeight")
    assert rect["height"] < vh * 2, (
        f"canvas exceeds 2× viewport height: {rect['height']}px vs vp {vh}px"
    )


def test_static_export_scroll_survives_showControls_toggle(
    static_bundle, page, wait_for_frontend
):
    """The 3D-viewer-controls toggle disposes and re-mounts the
    viewer with `showControls` flipped. Either state can have its own
    scroll bug:

      * `showControls: true` (default) mounts adapy's `EmbedUI` overlay
        on top of the canvas — `absolute inset-0` over the figure
        container, plus a pointer-handler bound to canvasHost.
      * `showControls: false` is the canvas-only path.

    Toggling between them shouldn't leave wheel events captured. This
    test flips the toggle, waits for the re-mount, and asserts the
    reader still scrolls on wheel events outside the canvas. Default
    state (controls-on) is already covered by
    `test_static_export_3d_viewer_does_not_hijack_page_scroll`; this
    test specifically guards the *toggled* state.
    """
    page.goto(f"{static_bundle}/")
    wait_for_frontend(page)

    page.locator('button:has-text("Load interactive 3D viewer")').first.click(timeout=10000)
    page.wait_for_selector("canvas", timeout=15000)
    page.wait_for_timeout(500)

    # Snapshot a button title only present when EmbedUI is mounted
    # (showControls=true). It disappears when we toggle off — we use
    # that as our "re-mounted in the new state" signal.
    embed_tree_btn = 'button[title="Show selection tree"]'
    initial_has_embed = page.locator(embed_tree_btn).count() > 0
    assert initial_has_embed, (
        "expected EmbedUI to be mounted by default (showControls=true). "
        "If the default flipped, this test needs to be inverted."
    )

    # Open the kebab menu + flip the toggle.
    page.locator('button[aria-label="More options"]').first.click()
    page.locator('button[role="menuitem"]:has-text("3D viewer controls")').first.click()

    # ThreeDRenderer re-mounts on toggle change. Wait for the EmbedUI
    # button to disappear (now in canvas-only mode) and a fresh canvas
    # to appear.
    page.wait_for_function(
        "() => document.querySelectorAll('button[title=\"Show selection tree\"]').length === 0",
        timeout=15000,
    )
    page.wait_for_selector("canvas", timeout=15000)
    page.wait_for_timeout(500)

    # Scroll test in the toggled state. Wheel from the reader's own
    # rect to stay layout-independent of the (now visible) desktop
    # sidebar.
    reader_rect = page.evaluate(
        "() => document.querySelector('[data-search-root]').getBoundingClientRect().toJSON()"
    )
    page.evaluate("document.querySelector('[data-search-root]').scrollTop = 0")
    initial = page.evaluate("document.querySelector('[data-search-root]').scrollTop")
    wheel_x = int(reader_rect["x"] + reader_rect["width"] - 20)
    wheel_y = int(reader_rect["y"] + reader_rect["height"] - 20)
    page.mouse.move(wheel_x, wheel_y)
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(200)
    after = page.evaluate("document.querySelector('[data-search-root]').scrollTop")
    assert after > initial, (
        f"reader scrollTop did not advance after toggling showControls "
        f"(initial={initial}, after={after}). Toggling the viewer "
        "controls left wheel-event capture in a bad state."
    )


def test_static_export_does_not_attempt_websocket(
    static_bundle, page, wait_for_frontend
):
    """Static-export mode injects `transport: 'static'` in
    `window.__PARADOC_CONFIG__`. Verify the WS path is genuinely
    inert — no `ws://...` connection attempts.
    """
    _, _, ws_attempts = _attach_recorders(page)

    page.goto(f"{static_bundle}/")
    wait_for_frontend(page)
    page.wait_for_timeout(2000)  # give any deferred boot work time

    ws_localhost = [u for u in ws_attempts if u.startswith("ws://localhost")]
    assert not ws_localhost, (
        f"static export attempted WebSocket connection(s): {ws_localhost}. "
        "Runtime config (transport: 'static') is not being honored."
    )
