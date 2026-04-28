"""LocalDocStore: read paths & path-traversal protection."""

import asyncio
import hashlib

import pandas as pd
import pytest

from paradoc.db import DbManager, ThreeDData, dataframe_to_table_data
from paradoc.docstore import LocalDocStore, write_manifest


def _build_single_doc_bundle(tmp_path, doc_id="my_doc"):
    """Create a minimal bundle with a sqlite + a glb asset."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle, doc_id=doc_id)

    db = DbManager(bundle / "paradoc.sqlite")
    df = pd.DataFrame({"a": [1, 2]})
    db.add_table(dataframe_to_table_data(key="t1", df=df, caption="x", show_index=False))

    glb_dir = bundle / "assets" / "3d"
    glb_dir.mkdir(parents=True)
    glb_bytes = b"GLBfake_content_bytes_xyz" * 200  # ~5KB
    glb_file = glb_dir / "fig1.glb"
    glb_file.write_bytes(glb_bytes)

    db.add_three_d(
        ThreeDData(
            key="fig1",
            glb_path="assets/3d/fig1.glb",
            format="glb",
            camera_pos="iso_3",
            caption="Caption",
            sha256=hashlib.sha256(glb_bytes).hexdigest(),
            size=len(glb_bytes),
            source_type="cad_model_file",
        )
    )
    db.close()
    return bundle, doc_id, glb_bytes


def test_get_table_round_trip(tmp_path):
    bundle, doc_id, _ = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)
    table = store.get_table(doc_id, "t1")
    assert table is not None
    assert table.key == "t1"


def test_get_three_d_meta_round_trip(tmp_path):
    bundle, doc_id, glb_bytes = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)
    meta = store.get_three_d_meta(doc_id, "fig1")
    assert meta is not None
    assert meta.size == len(glb_bytes)
    assert meta.sha256 == hashlib.sha256(glb_bytes).hexdigest()


def test_open_binary_streams_chunks(tmp_path):
    bundle, doc_id, glb_bytes = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)

    async def read_all():
        gen = await store.open_binary(doc_id, "fig1", chunk_size=1024)
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
        return b"".join(chunks)

    out = asyncio.run(read_all())
    assert out == glb_bytes


def test_open_binary_unknown_key(tmp_path):
    bundle, doc_id, _ = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)

    async def go():
        await store.open_binary(doc_id, "nope")

    with pytest.raises(KeyError):
        asyncio.run(go())


def test_traversal_attempt_rejected(tmp_path):
    bundle, _, _ = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)
    with pytest.raises((PermissionError, FileNotFoundError)):
        store._bundle_dir("../escape")


def test_list_doc_ids_single(tmp_path):
    bundle, doc_id, _ = _build_single_doc_bundle(tmp_path)
    store = LocalDocStore(bundle)
    assert store.list_doc_ids() == [doc_id]
