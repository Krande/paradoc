from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from typing import (
    Any as _Any,  # fallback for type hints; avoid hard dependency on internals
)
from typing import Set, Dict

import websockets

# Optional client utility depends on websocket-client (already in dependencies)
try:
    import websocket as ws_client  # type: ignore
except Exception:  # pragma: no cover - only used for ensure/ping
    ws_client = None  # type: ignore


ProtocolType = _Any
CLIENTS: Set[ProtocolType] = set()

# Track connected frontends with their metadata
# Structure: {frontend_id: {"ws": websocket, "last_heartbeat": timestamp}}
CONNECTED_FRONTENDS: Dict[str, Dict[str, _Any]] = {}

# Heartbeat timeout in seconds - remove frontend if no heartbeat received in this time
HEARTBEAT_TIMEOUT = 30.0

# Global flag to trigger shutdown
SHUTDOWN_REQUESTED = False


async def _cleanup_stale_frontends() -> None:
    """Periodically remove frontends that haven't sent a heartbeat recently."""
    while not SHUTDOWN_REQUESTED:
        await asyncio.sleep(5.0)  # Check every 5 seconds
        current_time = time.time()
        stale_frontends = []

        for frontend_id, info in CONNECTED_FRONTENDS.items():
            if current_time - info["last_heartbeat"] > HEARTBEAT_TIMEOUT:
                stale_frontends.append(frontend_id)

        for frontend_id in stale_frontends:
            CONNECTED_FRONTENDS.pop(frontend_id, None)
            print(f"Removed stale frontend: {frontend_id}")


async def _handle_client(ws: ProtocolType) -> None:
    CLIENTS.add(ws)
    client_frontend_id = None  # Track this client's frontend_id for cleanup

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
                    if isinstance(obj, dict):
                        kind = obj.get("kind")

                        # Handle ping
                        if kind == "ping":
                            await ws.send(json.dumps({"kind": "pong"}))
                            continue

                        # Handle frontend heartbeat registration
                        if kind == "frontend_heartbeat":
                            frontend_id = obj.get("frontend_id")
                            if frontend_id:
                                client_frontend_id = frontend_id
                                CONNECTED_FRONTENDS[frontend_id] = {
                                    "ws": ws,
                                    "last_heartbeat": time.time(),
                                    "frontend_id": frontend_id
                                }
                                await ws.send(json.dumps({"kind": "heartbeat_ack", "frontend_id": frontend_id}))
                            continue

                        # Handle get_connected_frontends request
                        if kind == "get_connected_frontends":
                            frontend_ids = list(CONNECTED_FRONTENDS.keys())
                            response = {
                                "kind": "connected_frontends",
                                "frontend_ids": frontend_ids,
                                "count": len(frontend_ids)
                            }
                            await ws.send(json.dumps(response))
                            continue

                        # Handle process info request
                        if kind == "get_process_info":
                            process_info = {
                                "kind": "process_info",
                                "pid": os.getpid(),
                                "thread_id": threading.get_ident(),
                            }
                            await ws.send(json.dumps(process_info))
                            continue

                        # Handle shutdown request
                        if kind == "shutdown":
                            global SHUTDOWN_REQUESTED
                            SHUTDOWN_REQUESTED = True
                            await ws.send(json.dumps({"kind": "shutdown_ack"}))
                            # Close all client connections
                            for client in list(CLIENTS):
                                try:
                                    await client.close()
                                except Exception:
                                    pass
                            return
            except Exception:
                # Not JSON or other error; just treat as broadcast content
                pass

            # Broadcast to all connected clients (including sender)
            await _broadcast(message)
    finally:
        CLIENTS.discard(ws)
        # Remove frontend from tracking when connection closes
        if client_frontend_id:
            CONNECTED_FRONTENDS.pop(client_frontend_id, None)


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
    # Start the cleanup task
    cleanup_task = asyncio.create_task(_cleanup_stale_frontends())

    async with websockets.serve(_handle_client, host, port, ping_interval=20, ping_timeout=20):
        # Keep the server running until shutdown is requested
        try:
            while not SHUTDOWN_REQUESTED:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass


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


def get_connected_frontends(host: str = "localhost", port: int = 13579, timeout: float = 1.5) -> list[str]:
    """
    Query the websocket server for a list of connected frontend IDs.

    Returns:
        List of frontend IDs currently connected to the server.
    """
    if ws_client is None:
        return []

    url = f"ws://{host}:{port}"
    try:
        ws = ws_client.create_connection(url, timeout=timeout)
    except Exception:
        return []

    try:
        ws.send(json.dumps({"kind": "get_connected_frontends"}))
        ws.settimeout(timeout)
        resp = ws.recv()
        data = json.loads(resp)
        if data.get("kind") == "connected_frontends":
            return data.get("frontend_ids", [])
        return []
    except Exception:
        return []
    finally:
        try:
            ws.close()
        except Exception:
            pass


def has_active_frontends(host: str = "localhost", port: int = 13579, timeout: float = 1.5) -> bool:
    """
    Check if there are any active frontends connected to the websocket server.

    Returns:
        True if at least one frontend is connected, False otherwise.
    """
    frontends = get_connected_frontends(host, port, timeout)
    return len(frontends) > 0


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
