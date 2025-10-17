from __future__ import annotations

import argparse
import http.server
import os
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    # Suppress logging to stdout
    def log_message(self, format: str, *args):  # noqa: A003 (shadow builtins)
        pass


def _serve(directory: str, host: str, port: int) -> None:
    # Change working dir for the handler to serve from the desired root
    os.chdir(directory)

    Handler = QuietHTTPRequestHandler
    # Use ThreadingTCPServer for concurrency
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    httpd = ThreadingHTTPServer((host, port), Handler)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except Exception:
        pass
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def ensure_http_server(host: str = "localhost", port: int = 13580, directory: str | os.PathLike[str] | None = None) -> bool:
    """
    Ensure a lightweight HTTP static file server is running on host:port serving the given directory.

    Returns True if server is running or was started successfully.
    """
    if directory is None:
        directory = os.getcwd()
    directory = str(Path(directory).resolve())

    if _port_open(host, port):
        return True

    # Start in a background thread within current process; this is sufficient for dev usage
    try:
        t = threading.Thread(target=_serve, args=(directory, host, port), daemon=True)
        t.start()
    except Exception:
        return False

    # Wait briefly for it to accept connections
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.05)
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Paradoc static HTTP server")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=13580)
    p.add_argument("--dir", dest="directory", default=os.getcwd())
    args = p.parse_args(argv)

    ok = ensure_http_server(args.host, args.port, args.directory)
    if not ok:
        print(f"Failed to start HTTP server on http://{args.host}:{args.port} serving {args.directory}")
        return 1
    print(f"Paradoc HTTP server on http://{args.host}:{args.port} serving {args.directory}")
    try:
        # Block forever
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
