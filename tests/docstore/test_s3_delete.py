"""S3DocStore.delete_doc against an in-memory object store (no network)."""

from __future__ import annotations

import obstore
import pytest
from obstore.store import MemoryStore

from paradoc.docstore.s3 import S3DocStore
from paradoc.serve.scope import Scope


@pytest.fixture
def store(tmp_path):
    s = S3DocStore(
        bucket="demo-bucket", endpoint="http://localhost:1", region="us-east-1", cache_dir=tmp_path / "cache"
    )
    s._store = MemoryStore()
    return s


def _put(store, key: str):
    obstore.put(store._store, key, b"x")


def _keys(store) -> list[str]:
    return sorted(o["path"] for batch in obstore.list(store._store) for o in batch)


def test_delete_doc_removes_only_that_bundle(store):
    for key in (
        "shared/demo-doc/manifest.json",
        "shared/demo-doc/static/sections/0.json",
        "shared/demo-doc2/manifest.json",  # same prefix text, different doc
        "users/u1/demo-doc/manifest.json",  # same id, other scope
    ):
        _put(store, key)
    cached = store.cache_dir / "shared" / "demo-doc"
    cached.mkdir(parents=True)
    (cached / "paradoc.sqlite").write_bytes(b"")

    assert store.delete_doc("demo-doc", scope=Scope.shared()) == 2
    assert _keys(store) == ["shared/demo-doc2/manifest.json", "users/u1/demo-doc/manifest.json"]
    assert not cached.exists()
    assert store.delete_doc("demo-doc", scope=Scope.shared()) == 0


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b"])
def test_delete_doc_refuses_path_tricks(store, bad):
    _put(store, "shared/demo-doc/manifest.json")
    with pytest.raises(PermissionError):
        store.delete_doc(bad, scope=Scope.shared())
    assert _keys(store) == ["shared/demo-doc/manifest.json"]
