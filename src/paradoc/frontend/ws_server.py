from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
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


# Setup logging
LOG_DIR = Path.home() / ".paradoc" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "ws_server.log"

# Configure logger
logger = logging.getLogger("paradoc.ws_server")
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler (optional, for when run directly)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

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
            logger.warning(f"Removed stale frontend: {frontend_id}")


async def _handle_client(ws: ProtocolType) -> None:
    CLIENTS.add(ws)
    client_frontend_id = None  # Track this client's frontend_id for cleanup
    client_addr = ws.remote_address if hasattr(ws, "remote_address") else "unknown"

    logger.info(f"New client connected from {client_addr}. Total clients: {len(CLIENTS)}")

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
                        logger.debug(f"Received message kind: {kind} from {client_addr}")

                        # Handle ping
                        if kind == "ping":
                            await ws.send(json.dumps({"kind": "pong"}))
                            continue

                        # Handle frontend heartbeat registration
                        if kind == "frontend_heartbeat":
                            frontend_id = obj.get("frontend_id")
                            if frontend_id:
                                was_new = frontend_id not in CONNECTED_FRONTENDS
                                client_frontend_id = frontend_id
                                CONNECTED_FRONTENDS[frontend_id] = {
                                    "ws": ws,
                                    "last_heartbeat": time.time(),
                                    "frontend_id": frontend_id,
                                }
                                if was_new:
                                    logger.info(
                                        f"Frontend registered: {frontend_id}. Total frontends: {len(CONNECTED_FRONTENDS)}"
                                    )
                                else:
                                    logger.debug(f"Frontend heartbeat updated: {frontend_id}")
                                await ws.send(json.dumps({"kind": "heartbeat_ack", "frontend_id": frontend_id}))
                            continue

                        # Handle get_connected_frontends request
                        if kind == "get_connected_frontends":
                            frontend_ids = list(CONNECTED_FRONTENDS.keys())
                            logger.debug(
                                f"Connected frontends requested. Count: {len(frontend_ids)}, IDs: {frontend_ids}"
                            )
                            response = {
                                "kind": "connected_frontends",
                                "frontend_ids": frontend_ids,
                                "count": len(frontend_ids),
                            }
                            await ws.send(json.dumps(response))
                            continue

                        # Handle log file path request
                        if kind == "get_log_file_path":
                            log_path = str(LOG_FILE.absolute())
                            logger.debug(f"Log file path requested: {log_path}")
                            response = {"kind": "log_file_path", "path": log_path}
                            await ws.send(json.dumps(response))
                            continue

                        # Handle process info request
                        if kind == "get_process_info":
                            logger.debug(f"Process info requested from {client_addr}")
                            process_info = {
                                "kind": "process_info",
                                "pid": os.getpid(),
                                "thread_id": threading.get_ident(),
                            }
                            await ws.send(json.dumps(process_info))
                            continue

                        # Handle shutdown request
                        if kind == "shutdown":
                            logger.warning(f"Shutdown requested from {client_addr}")
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
            except Exception as e:
                # Not JSON or other error; just treat as broadcast content
                logger.debug(f"Non-JSON message or parse error: {e}")
                pass

            # Broadcast to all connected clients (including sender)
            logger.debug(f"Broadcasting message from {client_addr} to {len(CLIENTS)} clients")
            await _broadcast(message)
    except Exception as e:
        logger.error(f"Error handling client {client_addr}: {e}", exc_info=True)
    finally:
        CLIENTS.discard(ws)
        # Remove frontend from tracking when connection closes
        if client_frontend_id:
            CONNECTED_FRONTENDS.pop(client_frontend_id, None)
            logger.info(f"Frontend disconnected: {client_frontend_id}. Remaining frontends: {len(CONNECTED_FRONTENDS)}")
        else:
            logger.info(f"Client disconnected from {client_addr}. Remaining clients: {len(CLIENTS)}")


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
    logger.info(f"Starting WebSocket server on ws://{host}:{port}")
    logger.info(f"Log file location: {LOG_FILE.absolute()}")

    # Start the cleanup task
    cleanup_task = asyncio.create_task(_cleanup_stale_frontends())

    async with websockets.serve(_handle_client, host, port, ping_interval=20, ping_timeout=20):
        logger.info(f"WebSocket server is now listening on ws://{host}:{port}")
        # Keep the server running until shutdown is requested
        try:
            while not SHUTDOWN_REQUESTED:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("Server received cancellation request")
            pass
        finally:
            logger.info("Shutting down WebSocket server")
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("WebSocket server shutdown complete")


def run_server(host: str = "localhost", port: int = 13579) -> None:
    """Run the websocket relay server (blocking)."""
    logger.info(f"Initializing WebSocket server on {host}:{port}")
    try:
        asyncio.run(_serve_forever(host, port))
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        pass
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


def ping_ws_server(host: str = "localhost", port: int = 13579, timeout: float = 1.5) -> bool:
    """Ping the websocket server; return True if responsive."""
    if ws_client is None:
        # Best-effort: attempt a TCP handshake using websockets library
        try:
            import socket

            with socket.create_connection((host, port), timeout=timeout):
                logger.debug(f"Successfully connected to WebSocket server via TCP on {host}:{port}")
                return True
        except Exception as e:
            logger.debug(f"Failed to connect via TCP to {host}:{port}: {e}")
            return False

    url = f"ws://{host}:{port}"
    try:
        ws = ws_client.create_connection(url, timeout=timeout)
    except Exception as e:
        logger.debug(f"Failed to create WebSocket connection to {url}: {e}")
        return False
    try:
        ws.send("__ping__")
        ws.settimeout(timeout)
        resp = ws.recv()
        success = resp == "__pong__"
        if success:
            logger.debug(f"Successfully pinged WebSocket server at {url}")
        else:
            logger.debug(f"Unexpected response from WebSocket server at {url}: {resp}")
        return success
    except Exception as e:
        logger.debug(f"Failed to ping WebSocket server at {url}: {e}")
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
        logger.debug(f"WebSocket server already running on {host}:{port}")
        return True

    # Spawn a detached background process: python -m paradoc.frontend.ws_server --host ... --port ...
    cmd = [sys.executable, "-m", "paradoc.frontend.ws_server", "--host", host, "--port", str(port)]
    logger.info(f"Starting WebSocket server with command: {' '.join(cmd)}")

    # On Windows, detach the process using creationflags
    # On Unix, use start_new_session to properly detach
    creationflags = 0
    start_new_session = False

    if os.name == "nt":
        # CREATE_NEW_PROCESS_GROUP (0x200) | DETACHED_PROCESS (0x8)
        creationflags = 0x00000200 | 0x00000008
    else:
        # On Unix systems, start a new session to detach from parent
        start_new_session = True

    try:
        import subprocess

        with open(os.devnull, "wb") as devnull:
            proc = subprocess.Popen(
                cmd,
                stdout=devnull,
                stderr=devnull,
                stdin=devnull,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
            logger.info(f"WebSocket server process started with PID: {proc.pid}")
    except Exception as e:
        logger.error(f"Failed to start WebSocket server: {e}", exc_info=True)
        return False

    # Wait briefly for it to boot and become pingable
    deadline = time.time() + wait_seconds
    attempts = 0
    while time.time() < deadline:
        if ping_ws_server(host, port):
            logger.info(f"WebSocket server successfully started and responding on {host}:{port}")
            return True
        attempts += 1
        time.sleep(0.1)

    logger.error(f"WebSocket server failed to start after {wait_seconds}s and {attempts} ping attempts")
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
