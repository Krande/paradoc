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
    except Exception as e:
        # If dependency missing, give up starting server in this thread
        # Note: The caller can still attempt to send; the client will fail
        # with a helpful message from the exporter.
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    state.loop = loop

    async def _start():
        server = await websockets.serve(
            lambda ws: _handler(ws, state), state.host, state.port
        )
        return server

    try:
        server = loop.run_until_complete(_start())
        state.started = True
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

    if state.thread and state.thread.is_alive():
        # Thread alive but not marked started yet; give it a moment
        return True

    # Spawn background daemon thread
    th = threading.Thread(target=_run_server, args=(state,), daemon=True, name=f"frontend-ws@{host}:{port}")
    state.thread = th

    try:
        th.start()
        return True
    except Exception:
        return False
