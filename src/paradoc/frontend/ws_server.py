from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Set

import websockets
from typing import Any as _Any  # fallback for type hints; avoid hard dependency on internals

# Optional client utility depends on websocket-client (already in dependencies)
try:
    import websocket as ws_client  # type: ignore
except Exception:  # pragma: no cover - only used for ensure/ping
    ws_client = None  # type: ignore


ProtocolType = _Any
CLIENTS: Set[ProtocolType] = set()


async def _handle_client(ws: ProtocolType) -> None:
    CLIENTS.add(ws)
    try:
        async for message in ws:
            # Lightweight ping protocol
            try:
                if message == "__ping__":
                    await ws.send("__pong__")
                    continue
                # If JSON with kind=="ping"
                if isinstance(message, str):
                    obj = json.loads(message)
                    if isinstance(obj, dict) and obj.get("kind") == "ping":
                        await ws.send(json.dumps({"kind": "pong"}))
                        continue
            except Exception:
                # Not JSON or other error; just treat as broadcast content
                pass

            # Broadcast to all connected clients (including sender)
            await _broadcast(message)
    finally:
        CLIENTS.discard(ws)


async def _broadcast(message: str | bytes) -> None:
    if not CLIENTS:
        return
    # Create a snapshot to avoid mutation during iteration
    conns = list(CLIENTS)
    # Send concurrently; drop clients that error
    pending = []
    for c in conns:
        pending.append(_safe_send(c, message))
    await asyncio.gather(*pending, return_exceptions=True)


async def _safe_send(ws: ProtocolType, message: str | bytes) -> None:
    try:
        await ws.send(message)
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass
        CLIENTS.discard(ws)


async def _serve_forever(host: str, port: int) -> None:
    async with websockets.serve(_handle_client, host, port, ping_interval=20, ping_timeout=20):
        # Keep the server running forever
        await asyncio.Future()


def run_server(host: str = "localhost", port: int = 13579) -> None:
    """Run the websocket relay server (blocking)."""
    try:
        asyncio.run(_serve_forever(host, port))
    except KeyboardInterrupt:
        pass


def ping_ws_server(host: str = "localhost", port: int = 13579, timeout: float = 1.5) -> bool:
    """Ping the websocket server; return True if responsive."""
    if ws_client is None:
        # Best-effort: attempt a TCP handshake using websockets library
        try:
            import socket

            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    url = f"ws://{host}:{port}"
    try:
        ws = ws_client.create_connection(url, timeout=timeout)
    except Exception:
        return False
    try:
        ws.send("__ping__")
        ws.settimeout(timeout)
        resp = ws.recv()
        return resp == "__pong__"
    except Exception:
        return False
    finally:
        try:
            ws.close()
        except Exception:
            pass


def ensure_ws_server(host: str = "localhost", port: int = 13579, wait_seconds: float = 3.0) -> bool:
    """
    Ensure a single background websocket relay server is running.

    Returns True if a server is already running or was successfully started; False otherwise.
    """
    if ping_ws_server(host, port):
        return True

    # Spawn a detached background process: python -m paradoc.frontend.ws_server --host ... --port ...
    cmd = [sys.executable, "-m", "paradoc.frontend.ws_server", "--host", host, "--port", str(port)]

    # On Windows, detach the process
    creationflags = 0
    if os.name == "nt":
        # CREATE_NEW_PROCESS_GROUP (0x200) | DETACHED_PROCESS (0x8)
        creationflags = 0x00000200 | 0x00000008

    try:
        import subprocess

        with open(os.devnull, "wb") as devnull:
            subprocess.Popen(
                cmd,
                stdout=devnull,
                stderr=devnull,
                stdin=devnull,
                creationflags=creationflags,
            )
    except Exception:
        return False

    # Wait briefly for it to boot and become pingable
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if ping_ws_server(host, port):
            return True
        time.sleep(0.1)

    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paradoc WebSocket relay server")
    parser.add_argument("--host", default="localhost", help="Host to bind (default: localhost)")
    parser.add_argument("--port", type=int, default=13579, help="Port to bind (default: 13579)")
    args = parser.parse_args(argv)
    print(f"Paradoc WS server listening on ws://{args.host}:{args.port}")
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
