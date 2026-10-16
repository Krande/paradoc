"""The reader loads a large document lazily.

* Plot data: no bulk plot request at startup (neither the static `plots.json` nor REST
  `<doc>/plots`); a plot's data is fetched when its figure is switched to interactive.
* Sections: only the first sections are rendered at load; the rest are placeholders that render as
  the reader scrolls, or when a cross-reference points into them.

Covers both the static export (served over HTTP) and paradoc-serve's REST mode.
"""

from __future__ import annotations

import http.server
import socket
import socketserver
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from paradoc import OneDoc
from paradoc.db import dataframe_to_plot_data

N_SECTIONS = 8
FILLER = "Filler paragraph with enough words in it to wrap across a line or two of the page.\n\n" * 30


def _write_doc(test_dir: Path) -> None:
    main_dir = test_dir / "00-main"
    main_dir.mkdir(parents=True)
    parts = []
    for i in range(N_SECTIONS):
        parts.append(f"# Chapter {i + 1}\n\n")
        if i == 0:
            parts.append("The early plot is below; the late one is in [@fig:wave_late].\n\n")
            parts.append("{{__wave_early__}}\n\n")
        parts.append(FILLER)
        if i == N_SECTIONS - 1:
            parts.append("{{__wave_late__}}\n\nLast words of the document.\n")
    (main_dir / "doc.md").write_text("".join(parts), encoding="utf-8")


def _add_plots(one: OneDoc) -> None:
    x = np.linspace(0, 2 * np.pi, 50)
    for key, f in (("wave_early", np.sin), ("wave_late", np.cos)):
        df = pd.DataFrame({"x": x, key: f(x)})
        one.db_manager.add_plot(
            dataframe_to_plot_data(key=key, df=df, plot_type="line", caption=f"{key} plot", width=700, height=350)
        )


def _serve_dir(directory: Path):
    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _QuietHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="lazy-static-http")
    thread.start()
    return f"http://127.0.0.1:{httpd.server_address[1]}", thread, httpd


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def static_site(tmp_path):
    test_dir = tmp_path / "doc"
    _write_doc(test_dir)
    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    _add_plots(one)
    out_dir = tmp_path / "site"
    assert one.export_static(out_dir), "export_static failed"
    assert (out_dir / "plots_index.json").exists()
    base, thread, httpd = _serve_dir(out_dir)
    try:
        yield f"{base}/index.html"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2.0)


@pytest.fixture
def rest_site(tmp_path):
    pytest.importorskip("fastapi")
    uvicorn = pytest.importorskip("uvicorn")

    test_dir = tmp_path / "doc"
    _write_doc(test_dir)
    one = OneDoc(test_dir, work_dir=tmp_path / "work")
    _add_plots(one)
    one.compile("LazyDoc", export_format="html")
    bundle = tmp_path / "work" / "_build"
    assert (bundle / "static" / "plots_index.json").exists()

    from paradoc.docstore import LocalDocStore
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.serve.app import create_app

    fh = FrontendHandler(one, host="localhost", port=13579)
    assert fh.ensure_frontend_extracted()
    app = create_app(doc_store=LocalDocStore(bundle), static_dir=fh.resources_dir)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=_free_port(), log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=server.run, daemon=True, name="lazy-rest-serve")
    thread.start()
    deadline = time.time() + 10
    while not getattr(server, "started", False):
        if time.time() > deadline:
            pytest.fail("paradoc-serve did not start")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{server.config.port}/?doc=LazyDoc"
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


def _is_plot_data(url: str) -> bool:
    path = url.split("?", 1)[0]
    return path.endswith("/plots.json") or path.endswith("/plots") or "/_plots/" in path or path.endswith("/figure")


def _check_lazy_reader(page, url: str) -> None:
    requests: list[str] = []
    errors: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(url)
    page.locator("[data-search-root] h1").first.wait_for(timeout=30000)
    page.wait_for_timeout(1500)

    # No plot data at startup -- the index only.
    assert not [u for u in requests if _is_plot_data(u)], f"plot data fetched at startup: {requests}"
    assert any("plots_index.json" in u or "/plots-index" in u for u in requests), requests

    # Later chapters are placeholders, not rendered content.
    placeholders = page.locator("[data-section-placeholder]").count()
    assert 0 < placeholders < N_SECTIONS, placeholders
    assert page.locator("[id='fig:wave_late']").count() == 0

    # A cross-reference into an unrendered chapter renders it and scrolls there.
    page.locator("[data-search-root] a[href='#fig:wave_late']").first.click()
    # Park the pointer off the content: the scroll would otherwise bring the figure under it, and
    # hovering a figure starts fetching its data (the head start before a click on Interactive).
    page.mouse.move(1, 1)
    late = page.locator("[id='fig:wave_late']")
    late.wait_for(timeout=10000)
    page.wait_for_function(
        """() => { const r = document.getElementById('fig:wave_late').getBoundingClientRect();
                   return r.top >= 0 && r.top < window.innerHeight }""",
        timeout=15000,
    )

    # The figure's data is fetched only when the reader turns to it (hover, then Interactive).
    assert not [u for u in requests if _is_plot_data(u)]
    wrapper = late.locator("xpath=ancestor::div[contains(@class,'group')][1]")
    wrapper.hover()
    wrapper.locator("button:has-text('Interactive')").first.click()
    page.locator("svg.main-svg").first.wait_for(timeout=30000)
    fetched = [u for u in requests if _is_plot_data(u)]
    assert len(fetched) == 1 and "wave_late" in fetched[0], fetched

    # Scrolling to the end renders every chapter.
    for _ in range(400):
        done = page.evaluate(
            """() => { const r = document.querySelector('[data-search-root]'); r.scrollTop += r.clientHeight;
                       return document.querySelectorAll('[data-section-placeholder]').length === 0 }"""
        )
        if done:
            break
        page.wait_for_timeout(30)
    assert page.locator("[data-section-placeholder]").count() == 0
    assert not errors, errors


@pytest.mark.parametrize("page_view", ["1", "0"], ids=["page-view", "scroll-view"])
def test_static_export_loads_plots_and_sections_lazily(static_site, context, page_view):
    context.add_init_script(f"localStorage.setItem('paradoc-page-view', '{page_view}')")
    page = context.new_page()
    _check_lazy_reader(page, static_site)


def test_rest_mode_loads_plots_and_sections_lazily(rest_site, context):
    page = context.new_page()
    _check_lazy_reader(page, rest_site)
