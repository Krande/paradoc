"""Binary asset fetch protocol on top of the existing WS relay.

Wire format (one in-flight binary fetch per client at a time)::

    C -> S  text   {"kind":"binary_fetch_request",
                    "request_id":"...", "doc_id":"...", "key":"...",
                    "sha256":"...?", "chunk_size":262144}

    S -> C  text   {"kind":"binary_fetch_meta",
                    "request_id":"...", "sha256":"...",
                    "total_size":N, "n_chunks":M,
                    "format":"glb", "camera_pos":"iso_3", "caption":"..."}
            (or)   {"kind":"binary_fetch_cached", "request_id":"..."}
            (or)   {"kind":"binary_fetch_error", "request_id":"...", "error":"..."}

    S -> C  binary <chunk_0>
    ...
    S -> C  binary <chunk_M-1>
    S -> C  text   {"kind":"binary_fetch_done", "request_id":"..."}

Why binary frames instead of base64-in-JSON
-------------------------------------------
WebSocket frames are typed (text vs binary). Sending the chunks as binary
avoids the 33% base64 tax and keeps memory / CPU low. The client knows it
is in a fetch (after `binary_fetch_meta`) and accumulates binary frames
until `binary_fetch_done`.

Why we cap at one in-flight per client
--------------------------------------
Multiplexing multiple in-flight transfers over a single WS would force
us to add framing to every binary frame just to disambiguate. We don't
have a real use case for parallel transfers from the same UI tab in v1
(it'd make the network busy without making any single transfer faster),
so we keep the protocol simple.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from paradoc.docstore import DocStore

logger = logging.getLogger("paradoc.binary_relay")

DEFAULT_CHUNK_SIZE = 256 * 1024
MAX_CHUNK_SIZE = 4 * 1024 * 1024


# Per-client locks so we strictly serialize binary fetches per WS.
_FETCH_LOCKS: dict[int, asyncio.Lock] = {}


def _client_lock(ws: Any) -> asyncio.Lock:
    key = id(ws)
    lock = _FETCH_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _FETCH_LOCKS[key] = lock
    return lock


def release_client_lock(ws: Any) -> None:
    """Drop the lock when a client disconnects."""
    _FETCH_LOCKS.pop(id(ws), None)


async def handle_binary_fetch_request(
    *,
    ws: Any,
    msg: dict,
    doc_store: DocStore | None,
) -> None:
    """Serve a `binary_fetch_request` from a client.

    Errors land back at the requester (never broadcast). Path-traversal
    and unknown-key handling lives in the underlying `DocStore`.
    """
    request_id = msg.get("request_id") or "?"
    doc_id = msg.get("doc_id")
    key = msg.get("key")
    client_sha = msg.get("sha256")
    requested_chunk = int(msg.get("chunk_size") or DEFAULT_CHUNK_SIZE)
    chunk_size = min(max(requested_chunk, 1024), MAX_CHUNK_SIZE)

    if doc_store is None:
        await _send_error(ws, request_id, "no DocStore configured on this server")
        return

    if not isinstance(doc_id, str) or not isinstance(key, str):
        await _send_error(ws, request_id, "doc_id and key are required")
        return

    lock = _client_lock(ws)
    if lock.locked():
        await _send_error(
            ws, request_id, "another binary fetch is already in flight on this connection"
        )
        return

    async with lock:
        try:
            meta = doc_store.get_three_d_meta(doc_id, key)
        except (PermissionError, FileNotFoundError) as exc:
            await _send_error(ws, request_id, str(exc))
            return
        except Exception as exc:
            logger.error(f"DocStore.get_three_d_meta crashed: {exc}", exc_info=True)
            await _send_error(ws, request_id, "internal error")
            return

        if meta is None:
            await _send_error(ws, request_id, f"unknown 3D key {key!r} in doc {doc_id!r}")
            return

        if client_sha and client_sha == meta.sha256:
            await _send_text(ws, {"kind": "binary_fetch_cached", "request_id": request_id})
            return

        n_chunks = max(1, (meta.size + chunk_size - 1) // chunk_size) if meta.size else 0

        await _send_text(
            ws,
            {
                "kind": "binary_fetch_meta",
                "request_id": request_id,
                "sha256": meta.sha256,
                "total_size": meta.size,
                "n_chunks": n_chunks,
                "format": meta.format,
                "camera_pos": meta.camera_pos,
                "caption": meta.caption,
            },
        )

        try:
            stream = await doc_store.open_binary(doc_id, key, chunk_size=chunk_size)
        except (PermissionError, KeyError, FileNotFoundError) as exc:
            await _send_error(ws, request_id, str(exc))
            return
        except Exception as exc:
            logger.error(f"DocStore.open_binary crashed: {exc}", exc_info=True)
            await _send_error(ws, request_id, "internal error")
            return

        sent = 0
        try:
            async for chunk in stream:
                if not chunk:
                    continue
                await ws.send(chunk)
                sent += 1
        except Exception as exc:
            logger.error(f"binary stream send failed: {exc}", exc_info=True)
            await _send_error(ws, request_id, "stream interrupted")
            return

        await _send_text(
            ws,
            {"kind": "binary_fetch_done", "request_id": request_id, "chunks_sent": sent},
        )


async def _send_text(ws: Any, payload: dict) -> None:
    try:
        await ws.send(json.dumps(payload))
    except Exception:
        # Caller's loop will pick up the disconnect; nothing actionable here.
        pass


async def _send_error(ws: Any, request_id: str, error: str) -> None:
    await _send_text(
        ws,
        {"kind": "binary_fetch_error", "request_id": request_id, "error": error},
    )
