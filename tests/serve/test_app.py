"""REST app endpoint tests.

Requires fastapi + httpx (the `serve` extras). Skipped when not installed.
"""

import hashlib

import pandas as pd
import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from paradoc.db import DbManager, ThreeDData, dataframe_to_table_data  # noqa: E402
from paradoc.docstore import LocalDocStore, write_manifest  # noqa: E402
from paradoc.serve import IngressTrustPolicy, create_app  # noqa: E402


def _build_bundle(tmp_path, doc_id="my_doc"):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_manifest(bundle, doc_id=doc_id)

    db = DbManager(bundle / "paradoc.sqlite")
    df = pd.DataFrame({"a": [1, 2, 3]})
    db.add_table(dataframe_to_table_data(key="t", df=df, caption="cap", show_index=False))

    glb = b"\x01\x02\x03" * 1000
    glb_dir = bundle / "assets" / "3d"
    glb_dir.mkdir(parents=True)
    (glb_dir / "fig1.glb").write_bytes(glb)
    db.add_three_d(
        ThreeDData(
            key="fig1",
            glb_path="assets/3d/fig1.glb",
            format="glb",
            camera_pos="iso_3",
            caption="3D cap",
            sha256=hashlib.sha256(glb).hexdigest(),
            size=len(glb),
            source_type="cad_model_file",
        )
    )
    db.close()
    return bundle, doc_id, glb


def test_health_endpoint(tmp_path):
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "ok" in res.json()["status"]


def test_table_endpoint(tmp_path):
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/docs/{doc_id}/tables/t")
    assert res.status_code == 200
    body = res.json()
    assert body["key"] == "t"


def test_table_404(tmp_path):
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/docs/{doc_id}/tables/nope")
    assert res.status_code == 404


def test_three_d_meta_endpoint(tmp_path):
    bundle, doc_id, glb = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/docs/{doc_id}/3d/fig1/meta")
    assert res.status_code == 200
    body = res.json()
    assert body["key"] == "fig1"
    assert body["sha256"] == hashlib.sha256(glb).hexdigest()


def test_three_d_blob_endpoint(tmp_path):
    bundle, doc_id, glb = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/docs/{doc_id}/3d/fig1/blob")
    assert res.status_code == 200
    assert res.content == glb
    assert res.headers["etag"] == f'"{hashlib.sha256(glb).hexdigest()}"'
    assert res.headers["x-paradoc-camera-pos"] == "iso_3"


def test_three_d_blob_etag_cache(tmp_path):
    bundle, doc_id, glb = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)

    sha = hashlib.sha256(glb).hexdigest()
    res = client.get(
        f"/api/docs/{doc_id}/3d/fig1/blob",
        headers={"If-None-Match": f'"{sha}"'},
    )
    assert res.status_code == 304


def test_auth_required(tmp_path):
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(
        doc_store=LocalDocStore(bundle),
        auth_policy=IngressTrustPolicy(require_principal=True),
    )
    client = TestClient(app)
    res = client.get(f"/api/docs/{doc_id}/tables/t")
    assert res.status_code == 401

    res2 = client.get(
        f"/api/docs/{doc_id}/tables/t",
        headers={"X-Auth-Request-User": "alice"},
    )
    assert res2.status_code == 200
