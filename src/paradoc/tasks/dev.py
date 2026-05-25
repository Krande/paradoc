"""`paradoc dev <doc_id>` — build + serve + watch + live-reload.

The local-development loop:

1. Run `build_document(doc_root, compile=True)` to populate the static
   bundle under `<work_dir>/_build/static` (or wherever OneDoc lands it).
2. Spin up a plain `http.server` over the bundle directory so the
   browser can fetch index.html + JSON + GLBs.
3. Spin up a `websockets` server on a sibling port that the injected
   reload script connects to.
4. Inject a tiny `<script>` into `index.html` that opens the WS and
   reloads the page on any message.
5. Use `watchdog` to observe source-side files (tasks.py, filters.py,
   paradoc.toml, every `.md` under report/). On change, rebuild and
   broadcast a reload message.

Rebuilds use paradoc.tasks' on-disk cache, so unchanged cells don't
re-execute. A pure markdown edit reruns the compile step without
touching the task DAG at all.

Failures during rebuild are logged and the browser keeps the previous
bundle — you don't get a half-broken page from a transient typo.

Dependencies:
- `watchdog` for filesystem events
- `websockets` for the reload channel
- `http.server` (stdlib) for the static server
"""

from __future__ import annotations

import asyncio
import http.server
import logging
import re
import socket
import socketserver
import threading
import time
from pathlib import Path
from typing import Optional

from .orchestrator import build_document

logger = logging.getLogger(__name__)


_RELOAD_SCRIPT_TEMPLATE = """
<!-- paradoc dev: auto-reload on rebuild -->
<script>
(function() {{
  let attempts = 0;
  function connect() {{
    const ws = new WebSocket('ws://' + window.location.hostname + ':{ws_port}');
    ws.onmessage = function(ev) {{
      try {{
        const msg = JSON.parse(ev.data);
        if (msg.event === 'reload') location.reload();
      }} catch (_) {{ location.reload(); }}
    }};
    ws.onclose = function() {{
      attempts++;
      // Backoff cap at ~5s; reconnect aggressively so a fresh build
      // brings the page back automatically.
      setTimeout(connect, Math.min(5000, 250 * attempts));
    }};
    ws.onerror = function() {{ ws.close(); }};
    ws.onopen = function() {{ attempts = 0; }};
  }}
  connect();
}})();
</script>
""".strip()

_INJECTION_MARKER = "paradoc dev: auto-reload"


def _inject_reload_script(index_html: Path, ws_port: int) -> None:
    """Insert the reload script into index.html if it isn't already there."""
    if not index_html.exists():
        logger.warning(f"no index.html at {index_html}; reload script not injected")
        return
    html = index_html.read_text()
    if _INJECTION_MARKER in html:
        return  # already injected from a previous run
    script = _RELOAD_SCRIPT_TEMPLATE.format(ws_port=ws_port)
    if "</body>" in html:
        html = html.replace("</body>", script + "\n</body>", 1)
    else:
        html = html + script
    index_html.write_text(html)


def _free_port(preferred: Optional[int] = None) -> int:
    """Return an OS-assigned free port, or `preferred` if available."""
    if preferred is not None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", preferred))
                return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _BundleServer(threading.Thread):
    """`http.server` running in a background thread over a directory."""

    def __init__(self, root: Path, port: int) -> None:
        super().__init__(daemon=True, name="paradoc-dev-http")
        self.root = root
        self.port = port
        self._httpd: Optional[socketserver.TCPServer] = None

    def run(self) -> None:
        # Use a SimpleHTTPRequestHandler bound to the bundle root.
        handler_cls = http.server.SimpleHTTPRequestHandler
        # `directory` kwarg landed in 3.7; supported via closure here.
        root_str = str(self.root)

        class _Handler(handler_cls):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=root_str, **kwargs)

            def log_message(self, fmt, *args):
                logger.debug("http: " + fmt % args)

        self._httpd = socketserver.TCPServer(("", self.port), _Handler)
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()


class _ReloadBus:
    """Async fan-out for reload events to every connected WS client."""

    def __init__(self) -> None:
        self._clients: set = set()
        self._lock = asyncio.Lock()

    async def register(self, ws) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            stale = []
            for ws in self._clients:
                try:
                    await ws.send(message)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._clients.discard(ws)


async def _ws_handler(ws, bus: _ReloadBus) -> None:
    await bus.register(ws)
    try:
        # Keep the connection open; we don't expect inbound traffic.
        async for _ in ws:
            pass
    finally:
        await bus.unregister(ws)


def _watch_paths(doc_root: Path) -> list[Path]:
    """Files/dirs the dev loop watches for rebuilds.

    Includes the doc root's tasks.py / filters.py / paradoc.toml plus
    the markdown source tree under report/ if present (the verification
    layout) or the doc_root itself otherwise. Excludes the
    `.paradoc-cache/` so the cache writes don't trigger spurious
    rebuilds.
    """
    candidates = [
        doc_root / "tasks.py",
        doc_root / "filters.py",
        doc_root / "paradoc.toml",
    ]
    report_dir = doc_root / "report"
    if report_dir.is_dir():
        candidates.append(report_dir)
    else:
        # Fall back to the doc_root itself for docs with markdown at top level.
        candidates.append(doc_root)
    return [p for p in candidates if p.exists()]


def _is_ignored(path: Path, doc_root: Path) -> bool:
    """True if a file event should be skipped (cache writes, temp,
    pycache, etc.)."""
    parts = path.relative_to(doc_root).parts if doc_root in path.parents or path == doc_root else path.parts
    ignored_segments = {".paradoc-cache", "__pycache__", "_build", "temp", ".cache"}
    return any(seg in ignored_segments for seg in parts)


async def serve_and_watch(
    doc_root: Path,
    *,
    port: int = 8765,
    ws_port: Optional[int] = None,
    profile: str = "default",
    no_cache: bool = False,
    work_dir: Optional[Path] = None,
    debounce_ms: int = 300,
) -> None:
    """Run the dev loop until interrupted.

    Args
    ----
    port : int
        HTTP port for the static bundle. Default 8765.
    ws_port : int | None
        WebSocket port for reload messages. Default: an OS-assigned
        free port.
    profile : str
        Build profile from paradoc.toml.
    no_cache : bool
        Skip the on-disk task cache (forces full re-execution every
        rebuild). Usually want False; the cache makes incremental
        rebuilds fast.
    work_dir : Path | None
        Override OneDoc's work directory.
    debounce_ms : int
        Coalesce filesystem events within this window so an editor's
        write+rename pattern doesn't trigger duplicate rebuilds.
    """
    try:
        import websockets
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "paradoc dev needs `watchdog` and `websockets` (already pinned in "
            "the prod env). Re-run with the env that has them."
        ) from exc

    doc_root = doc_root.resolve()
    if not doc_root.is_dir():
        raise FileNotFoundError(doc_root)

    http_port = _free_port(port)
    ws_port_resolved = _free_port(ws_port if ws_port is not None else port + 1)

    # Initial build.
    logger.info(f"initial build of {doc_root.name}...")
    _, one = build_document(doc_root, profile=profile, no_cache=no_cache, work_dir=work_dir)
    bundle_dir = _resolve_bundle_dir(one)
    logger.info(f"bundle at {bundle_dir}")

    _inject_reload_script(bundle_dir / "index.html", ws_port_resolved)

    # HTTP server thread.
    http_server = _BundleServer(bundle_dir, http_port)
    http_server.start()
    logger.info(f"serving http://localhost:{http_port}/  (ws :{ws_port_resolved})")

    # Reload bus + WS server.
    bus = _ReloadBus()
    async with websockets.serve(lambda ws: _ws_handler(ws, bus), "", ws_port_resolved):
        # Watchdog observer in a background thread; bridge into the
        # asyncio loop via run_coroutine_threadsafe.
        loop = asyncio.get_running_loop()
        last_event_at = 0.0
        pending_rebuild = asyncio.Event()

        def _on_any_event(_event):
            nonlocal last_event_at
            path = Path(getattr(_event, "src_path", ""))
            if _is_ignored(path, doc_root):
                return
            last_event_at = time.monotonic()
            loop.call_soon_threadsafe(pending_rebuild.set)

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                _on_any_event(event)

        observer = Observer()
        for p in _watch_paths(doc_root):
            observer.schedule(_Handler(), str(p), recursive=p.is_dir())
        observer.start()

        try:
            await _rebuild_loop(
                pending_rebuild,
                bus,
                doc_root,
                profile=profile,
                no_cache=no_cache,
                work_dir=work_dir,
                ws_port=ws_port_resolved,
                debounce_ms=debounce_ms,
                last_event_at_ref=lambda: last_event_at,
            )
        finally:
            observer.stop()
            observer.join(timeout=2.0)
            http_server.shutdown()


async def _rebuild_loop(
    pending: asyncio.Event,
    bus: _ReloadBus,
    doc_root: Path,
    *,
    profile: str,
    no_cache: bool,
    work_dir: Optional[Path],
    ws_port: int,
    debounce_ms: int,
    last_event_at_ref,
) -> None:
    """Wait for filesystem events, debounce, rebuild, broadcast reload."""
    while True:
        await pending.wait()
        # Debounce: wait until events stop arriving for `debounce_ms`.
        while True:
            await asyncio.sleep(debounce_ms / 1000.0)
            if time.monotonic() - last_event_at_ref() >= debounce_ms / 1000.0:
                break
        pending.clear()

        logger.info("rebuilding...")
        t0 = time.monotonic()
        try:
            _, one = build_document(
                doc_root, profile=profile, no_cache=no_cache, work_dir=work_dir
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"rebuild failed: {exc}", exc_info=True)
            continue

        bundle_dir = _resolve_bundle_dir(one)
        _inject_reload_script(bundle_dir / "index.html", ws_port)
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(f"rebuild done in {elapsed:.0f} ms — reloading clients")
        await bus.broadcast('{"event":"reload"}')


def _resolve_bundle_dir(one) -> Path:
    """Best-effort resolution of where OneDoc wrote the static bundle.

    OneDoc's compile() puts the static export under work_dir; the
    actual subdirectory layout has shifted over time. Probe a couple
    of known patterns and return the first that exists; fall back to
    work_dir itself.
    """
    work_dir = Path(one.work_dir)
    for candidate in (
        work_dir / "_build" / "static",
        work_dir / "static",
        work_dir,
    ):
        if (candidate / "index.html").exists():
            return candidate
    return work_dir
