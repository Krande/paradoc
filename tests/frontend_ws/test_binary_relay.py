"""Binary asset fetch over the WS protocol — fake-ws, no real network."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

import pandas as pd
import pytest

from paradoc.db import DbManager, ThreeDData, dataframe_to_table_data
from paradoc.docstore import LocalDocStore, write_manifest
from paradoc.frontend.binary_relay import handle_binary_fetch_request


class FakeWebSocket:
    """Records every send. Yields on send to model real network IO."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, Any]] = []

    async def send(self, message: Any) -> None:
        # Yield so the event loop can schedule other tasks (mirrors real socket).
        await asyncio.sleep(0)
        kind = "bytes" if isinstance(message, (bytes, bytearray, memoryview)) else "text"
        self.sent.append((kind, bytes(message) if kind == "bytes" else message))


def _build_bundle(tmp_path, glb_bytes: bytes, key: str = "fig1", doc_id: str = "doc"):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle, doc_id=doc_id)
    db = DbManager(bundle / "paradoc.sqlite")
    df = pd.DataFrame({"a": [1]})
    db.add_table(dataframe_to_table_data(key="t", df=df, caption="x", show_index=False))

    glb_dir = bundle / "assets" / "3d"
    glb_dir.mkdir(parents=True)
    (glb_dir / f"{key}.glb").write_bytes(glb_bytes)
    db.add_three_d(
        ThreeDData(
            key=key,
            glb_path=f"assets/3d/{key}.glb",
            format="glb",
            camera_pos="iso_3",
            caption="cap",
            sha256=hashlib.sha256(glb_bytes).hexdigest(),
            size=len(glb_bytes),
            source_type="cad_model_file",
        )
    )
    db.close()
    return bundle, doc_id


def _run(coro):
    return asyncio.run(coro)


def test_meta_then_binary_chunks_then_done(tmp_path):
    glb = b"\x00\x01\x02" * 1500  # 4500 bytes
    bundle, doc_id = _build_bundle(tmp_path, glb)
    store = LocalDocStore(bundle)

    chunk_size = 2048
    ws = FakeWebSocket()
    msg = {
        "kind": "binary_fetch_request",
        "request_id": "r1",
        "doc_id": doc_id,
        "key": "fig1",
        "chunk_size": chunk_size,
    }
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=store))

    # First message must be meta (text JSON).
    assert ws.sent[0][0] == "text"
    meta = json.loads(ws.sent[0][1])
    assert meta["kind"] == "binary_fetch_meta"
    assert meta["request_id"] == "r1"
    assert meta["sha256"] == hashlib.sha256(glb).hexdigest()
    assert meta["total_size"] == len(glb)
    expected_chunks = (len(glb) + chunk_size - 1) // chunk_size
    assert meta["n_chunks"] == expected_chunks

    # Then `expected_chunks` binary frames.
    binary_frames = [m for m in ws.sent[1:-1] if m[0] == "bytes"]
    assert len(binary_frames) == expected_chunks
    assembled = b"".join(b for _, b in binary_frames)
    assert assembled == glb

    # Last message is `done`.
    assert ws.sent[-1][0] == "text"
    done = json.loads(ws.sent[-1][1])
    assert done["kind"] == "binary_fetch_done"
    assert done["chunks_sent"] == expected_chunks


def test_cached_short_circuit(tmp_path):
    glb = b"\xff" * 100
    bundle, doc_id = _build_bundle(tmp_path, glb)
    store = LocalDocStore(bundle)
    sha = hashlib.sha256(glb).hexdigest()

    ws = FakeWebSocket()
    msg = {
        "kind": "binary_fetch_request",
        "request_id": "r2",
        "doc_id": doc_id,
        "key": "fig1",
        "sha256": sha,
        "chunk_size": 256,
    }
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=store))

    # Single text reply, no chunks.
    assert len(ws.sent) == 1
    cached = json.loads(ws.sent[0][1])
    assert cached["kind"] == "binary_fetch_cached"
    assert cached["request_id"] == "r2"


def test_unknown_key_yields_error(tmp_path):
    bundle, doc_id = _build_bundle(tmp_path, b"data")
    store = LocalDocStore(bundle)

    ws = FakeWebSocket()
    msg = {
        "kind": "binary_fetch_request",
        "request_id": "r3",
        "doc_id": doc_id,
        "key": "nope",
    }
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=store))

    assert len(ws.sent) == 1
    err = json.loads(ws.sent[0][1])
    assert err["kind"] == "binary_fetch_error"
    assert "nope" in err["error"]


def test_no_doc_store_configured_yields_error(tmp_path):
    ws = FakeWebSocket()
    msg = {"kind": "binary_fetch_request", "request_id": "r4", "doc_id": "d", "key": "k"}
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=None))
    err = json.loads(ws.sent[0][1])
    assert err["kind"] == "binary_fetch_error"


def test_chunk_size_clamped_to_min(tmp_path):
    glb = b"x" * 2048
    bundle, doc_id = _build_bundle(tmp_path, glb)
    store = LocalDocStore(bundle)

    ws = FakeWebSocket()
    # chunk_size=10 should be clamped up to >=1024.
    msg = {
        "kind": "binary_fetch_request",
        "request_id": "r5",
        "doc_id": doc_id,
        "key": "fig1",
        "chunk_size": 10,
    }
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=store))

    meta = json.loads(ws.sent[0][1])
    assert meta["n_chunks"] == 2  # 2048 / 1024


def test_traversal_safe(tmp_path):
    bundle, doc_id = _build_bundle(tmp_path, b"x")
    store = LocalDocStore(bundle)
    ws = FakeWebSocket()
    msg = {
        "kind": "binary_fetch_request",
        "request_id": "r6",
        "doc_id": "../escape",
        "key": "anything",
    }
    _run(handle_binary_fetch_request(ws=ws, msg=msg, doc_store=store))
    err = json.loads(ws.sent[0][1])
    assert err["kind"] == "binary_fetch_error"


@pytest.mark.skipif(False, reason="protocol contract test")
def test_concurrent_fetch_locked_out(tmp_path):
    """A second request while one is in-flight on the same WS yields an error."""
    glb = b"x" * 4096
    bundle, doc_id = _build_bundle(tmp_path, glb)
    store = LocalDocStore(bundle)

    ws = FakeWebSocket()

    async def both():
        # Schedule both at once; the second one should see the lock held.
        t1 = asyncio.create_task(
            handle_binary_fetch_request(
                ws=ws,
                msg={
                    "kind": "binary_fetch_request",
                    "request_id": "first",
                    "doc_id": doc_id,
                    "key": "fig1",
                    "chunk_size": 1024,
                },
                doc_store=store,
            )
        )
        # Yield to let t1 acquire the lock.
        await asyncio.sleep(0)
        await handle_binary_fetch_request(
            ws=ws,
            msg={
                "kind": "binary_fetch_request",
                "request_id": "second",
                "doc_id": doc_id,
                "key": "fig1",
            },
            doc_store=store,
        )
        await t1

    _run(both())

    # At least one error referencing the "second" request.
    error_msgs = [
        json.loads(m[1])
        for m in ws.sent
        if m[0] == "text" and json.loads(m[1]).get("kind") == "binary_fetch_error"
    ]
    assert any(e["request_id"] == "second" for e in error_msgs)
