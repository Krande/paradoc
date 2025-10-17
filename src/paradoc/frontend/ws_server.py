from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple

# Lightweight WebSocket broadcast server that runs on a dedicated background thread.
# It stores the last message and sends it to any client that connects later.
# Implemented with the "websockets" package (asyncio-based).


@dataclass
class _ServerState:
    host: str
    port: int
    thread: threading.Thread | None = None
    loop: asyncio.AbstractEventLoop | None = None
    clients: Set["websockets.WebSocketServerProtocol"] = field(default_factory=set)
    last_message: str | None = None
    started: bool = False


_states: Dict[Tuple[str, int], _ServerState] = {}


async def _handler(websocket, state: _ServerState):
    # Register client
    state.clients.add(websocket)
    try:
        # Send last content to newly connected client, if available
        if state.last_message:
            try:
                await websocket.send(state.last_message)
            except Exception:
                pass

        # Echo/broadcast any messages to all clients and remember last
        async for message in websocket:
            # Ignore keep-alive empty messages to avoid wiping the last document
            try:
                if not message or (isinstance(message, str) and message.strip() == ""):
                    continue
            except Exception:
                # If we can't inspect it, proceed
                pass
            state.last_message = message
            # Broadcast to all
            send_tasks = []
            for client in list(state.clients):
                try:
                    send_tasks.append(client.send(message))
                except Exception:
                    pass
            if send_tasks:
                try:
                    await asyncio.gather(*send_tasks, return_exceptions=True)
                except Exception:
                    pass
    finally:
        # Unregister client
        try:
            state.clients.discard(websocket)
        except Exception:
            pass


def _run_server(state: _ServerState):
    # Dedicated event loop in this background thread
    try:
        import websockets  # type: ignore
    except Exception:
        # If dependency missing, give up starting server in this thread
        # Surface a clear hint to the user
        print(
            "Paradoc: Missing optional dependency 'websockets'.\n"
            "Install it to enable the live preview server: pip install websockets\n"
            "Alternatively, add it to your environment via pixi (see pyproject)."
        )
        state.started = False
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    state.loop = loop

    async def _start():
        # Bind to all interfaces when host is unspecified or localhost-like to support both IPv4 and IPv6 loopbacks.
        listen_host = None if state.host in ("", "localhost", "127.0.0.1", "::1") else state.host
        server = await websockets.serve(
            lambda ws: _handler(ws, state), listen_host, state.port
        )
        return server

    try:
        server = loop.run_until_complete(_start())
        state.started = True
        print(f"Paradoc: WebSocket server listening on ws://{state.host}:{state.port}")
        loop.run_forever()
    finally:
        try:
            state.started = False
            # Close server and all client connections
            for client in list(state.clients):
                try:
                    loop.run_until_complete(client.close())
                except Exception:
                    pass
            state.clients.clear()
        except Exception:
            pass
        try:
            pending = asyncio.all_tasks(loop)
            for t in pending:
                t.cancel()
        except Exception:
            pass
        try:
            loop.stop()
            loop.close()
        except Exception:
            pass


def ensure_ws_server(host: str = "localhost", port: int = 13579) -> bool:
    """
    Ensure a WebSocket broadcast server is running in a background thread.

    Returns True if the server is (or becomes) running, False otherwise.
    """
    key = (host, port)
    state = _states.get(key)
    if state and state.started:
        return True

    if state is None:
        state = _ServerState(host=host, port=port)
        _states[key] = state

    # If a thread exists but not started, we'll still wait for readiness below
    if not (state.thread and state.thread.is_alive()):
        # Spawn background daemon thread
        th = threading.Thread(target=_run_server, args=(state,), daemon=True, name=f"frontend-ws@{host}:{port}")
        state.thread = th
        try:
            th.start()
        except Exception:
            return False

    # Wait briefly for the server to report started
    try:
        import time
        deadline = time.time() + 1.0  # up to 1s
        while time.time() < deadline:
            if state.started:
                return True
            time.sleep(0.05)
    except Exception:
        # best-effort; fall back to optimistic
        pass

    # Not started within the timeout
    return False
