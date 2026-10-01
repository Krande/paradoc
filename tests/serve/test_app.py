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
from paradoc.serve import create_app  # noqa: E402


def _build_bundle(tmp_path, doc_id="my_doc", extra_three_d=()):
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
    for row in extra_three_d:
        db.add_three_d(row(glb))
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


def test_three_d_meta_carries_the_fea_view_hints(tmp_path):
    """An FEA mode-view row's metadata reaches the REST meta body: which mode to show, and whether the
    document wants beam elements drawn as solids. Absent, the viewer draws them as lines."""

    def mode_view(key, md):
        return lambda glb: ThreeDData(
            key=key,
            glb_path="assets/3d/fig1.glb",
            format="glb",
            camera_pos="iso_3",
            caption="mode",
            sha256=hashlib.sha256(glb).hexdigest(),
            size=len(glb),
            source_type="fea_artefact_bundle_mode_view",
            metadata=md,
        )

    bundle, doc_id, _ = _build_bundle(
        tmp_path,
        extra_three_d=(
            mode_view("mode_solid", {"fea_bundle_key": "case", "fea_mode_index": 2, "fea_beam_solids": True}),
            mode_view("mode_plain", {"fea_bundle_key": "case", "fea_mode_index": 2}),
        ),
    )

    # One app per request: LocalDocStore keeps the SQLite connection of the thread that first used
    # it, and TestClient serves a second request from another thread.
    def meta(key):
        client = TestClient(create_app(doc_store=LocalDocStore(bundle)))
        return client.get(f"/api/docs/{doc_id}/3d/{key}/meta").json()

    solid = meta("mode_solid")
    assert solid["fea_mode_index"] == 2
    assert solid["fea_beam_solids"] is True
    assert "fea_beam_solids" not in meta("mode_plain")


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


def test_scope_aware_route_shared(tmp_path):
    # New /api/scopes/{scope}/docs/... URL form. With auth disabled
    # the synthetic local-dev user can access shared scope; the route
    # resolves the scope predicate without a DB pool.
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/scopes/shared/docs/{doc_id}/tables/t")
    assert res.status_code == 200
    assert res.json()["key"] == "t"


def test_scope_aware_route_user_me_in_single_doc_mode_404s(tmp_path):
    # Single-doc layout only supports shared scope. user:me resolves
    # to a valid scope (local-dev's id), but the LocalDocStore raises
    # FileNotFoundError for non-shared scopes — surfaces as 500
    # (uncaught) or per FastAPI's default handling. Verify it's not 200.
    bundle, doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get(f"/api/scopes/user:me/docs/{doc_id}/tables/t")
    assert res.status_code != 200


def test_me_returns_local_dev_when_auth_disabled(tmp_path, monkeypatch):
    # Default (auth disabled) — /api/me returns the synthetic local-dev
    # admin user instead of 401ing. Keeps dev paths usable without IdP
    # config.
    monkeypatch.delenv("PARADOC_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("PARADOC_OIDC_PROVIDERS_JSON", raising=False)
    bundle, _doc_id, _ = _build_bundle(tmp_path)
    app = create_app(doc_store=LocalDocStore(bundle))
    client = TestClient(app)
    res = client.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["iss"] == "local-dev"
    assert body["is_admin"] is True
    assert body["subject"] == "local-dev"
