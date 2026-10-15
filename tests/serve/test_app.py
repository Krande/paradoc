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


def _build_scoped_store(tmp_path, user_id, doc_id="demo-doc"):
    """Multi-doc store with one doc in shared scope and one in
    ``users/<user_id>`` (personal scope)."""
    root = tmp_path / "store"
    shared_bundle, _, _ = _build_bundle(tmp_path / "shared_src", doc_id="shared-doc")
    personal_src = tmp_path / "personal_src"
    personal_src.mkdir()
    personal_bundle, _, _ = _build_bundle(personal_src, doc_id=doc_id)
    for bundle in (shared_bundle, personal_bundle):
        static = bundle / "static"
        static.mkdir()
        (static / "manifest.json").write_text('{"sections": []}')
    (root / "shared").mkdir(parents=True)
    shared_bundle.rename(root / "shared" / "shared-doc")
    (root / "users" / user_id).mkdir(parents=True)
    personal_bundle.rename(root / "users" / user_id / doc_id)
    return root


def test_personal_doc_served_via_scoped_routes_and_landing_scope_ref(tmp_path):
    # A doc published to the personal scope is listed on /api/landing
    # but only reachable via /api/scopes/user:me/docs/... — the SPA uses
    # the entry's `scope_ref` to build those URLs.
    (tmp_path / "shared_src").mkdir()
    from paradoc.serve import auth as auth_module

    user = auth_module.User(
        id="11111111-2222-3333-4444-555555555555",
        iss="test",
        subject="demo-user",
        email="demo@example.com",
        display_name="Demo User",
        groups=frozenset(),
        is_admin=False,
    )
    root = _build_scoped_store(tmp_path, user.id)
    app = create_app(doc_store=LocalDocStore(root))
    app.dependency_overrides[auth_module.current_user] = lambda: user
    client = TestClient(app)

    landing = client.get("/api/landing").json()
    assert [(d["id"], d["scope"], d["scope_ref"]) for d in landing["personal"]] == [("demo-doc", "personal", "user:me")]
    assert [(d["id"], d["scope_ref"]) for d in landing["shared"]] == [("shared-doc", "shared")]

    # Unscoped legacy routes only see the shared scope.
    assert client.get("/api/docs/demo-doc/manifest").status_code == 404
    assert client.get("/api/docs/shared-doc/manifest").status_code == 200

    base = "/api/scopes/user:me/docs/demo-doc"
    assert client.get(f"{base}/manifest").status_code == 200
    assert client.get(f"{base}/tables/t").json()["key"] == "t"
    assert client.get(f"{base}/3d/fig1/meta").json()["key"] == "fig1"
    assert client.get(f"{base}/3d/fig1/blob").status_code == 200
    assert client.get(f"{base}/presets").json() == {}
    files = client.get(f"{base}/manifest/files")
    assert files.status_code == 200
    assert files.json()["doc_id"] == "demo-doc"
    # URL-encoded scope segment (what the SPA sends) resolves the same.
    assert client.get("/api/scopes/user%3Ame/docs/demo-doc/manifest").status_code == 200
