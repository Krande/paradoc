"""`/api/library`: every doc the caller can read, across scopes, without leaking other users' docs."""

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from paradoc.docstore import LocalDocStore, write_manifest  # noqa: E402
from paradoc.serve import auth as auth_module  # noqa: E402
from paradoc.serve import create_app  # noqa: E402
from paradoc.serve import db as db_module  # noqa: E402

ME = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-8888-7777-6666-555555555555"
PROJ_IN = "aaaaaaaa-0000-0000-0000-000000000001"
PROJ_OUT = "aaaaaaaa-0000-0000-0000-000000000002"


def _user(uid=ME, is_admin=False):
    return auth_module.User(
        id=uid,
        iss="test",
        subject=uid,
        email="someone@example.com",
        display_name="Someone",
        groups=frozenset(),
        is_admin=is_admin,
    )


def _bundle(root, prefix, doc_id, payload=b"x" * 100):
    b = root / prefix / doc_id
    b.mkdir(parents=True)
    write_manifest(b, doc_id=doc_id)
    (b / "files").mkdir()
    (b / "files" / "data.bin").write_bytes(payload)
    return b


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "store"
    _bundle(root, "shared", "shared-doc")
    _bundle(root, f"users/{ME}", "my-doc", b"y" * 1000)
    _bundle(root, f"users/{OTHER}", "their-doc")
    _bundle(root, f"projects/{PROJ_IN}", "project-doc")
    _bundle(root, f"projects/{PROJ_OUT}", "secret-project-doc")
    return root


@pytest.fixture
def member_of_one_project(monkeypatch):
    async def list_user_projects(pool, user_id):
        if user_id != ME:
            return []
        return [db_module.Project(id=PROJ_IN, slug="quay", name="Quay Upgrade", shelf_base_url=None, role="member")]

    monkeypatch.setattr(db_module, "list_user_projects", list_user_projects)


def _client(root, user, pool=None):
    app = create_app(doc_store=LocalDocStore(root))
    app.dependency_overrides[auth_module.current_user] = lambda: user
    # No lifespan (TestClient not used as a context manager), so the pool is whatever we set.
    app.state.db_pool = pool
    return TestClient(app)


def test_library_lists_personal_shared_and_member_projects_only(store, member_of_one_project):
    client = _client(store, _user(), pool=object())
    body = client.get("/api/library").json()

    assert [(s["ref"], s["kind"], s["name"]) for s in body["scopes"]] == [
        ("user:me", "personal", "Personal"),
        ("shared", "shared", "Shared"),
        ("project:quay", "project", "Quay Upgrade"),
    ]
    got = {(d["id"], d["scope"], d["scope_ref"], d["scope_name"]) for d in body["docs"]}
    assert got == {
        ("my-doc", "personal", "user:me", "Personal"),
        ("shared-doc", "shared", "shared", "Shared"),
        ("project-doc", "project", "project:quay", "Quay Upgrade"),
    }
    ids = {d["id"] for d in body["docs"]}
    # Another user's personal docs and a project the caller is not a member of never show up.
    assert "their-doc" not in ids and "secret-project-doc" not in ids
    for d in body["docs"]:
        assert d["published_at"]
        assert "size" not in d  # sizes are opt-in


def test_library_other_user_sees_only_their_own_personal_docs(store, member_of_one_project):
    body = _client(store, _user(OTHER), pool=object()).get("/api/library").json()
    assert {d["id"] for d in body["docs"]} == {"their-doc", "shared-doc"}


def test_library_sizes_opt_in(store, member_of_one_project):
    body = _client(store, _user(), pool=object()).get("/api/library?sizes=1").json()
    by_id = {d["id"]: d for d in body["docs"]}
    mine = by_id["my-doc"]
    # data.bin (1000 B) + manifest.json
    assert mine["size"] > 1000 and mine["file_count"] == 2


def test_library_can_delete_mirrors_delete_route(store, member_of_one_project):
    body = _client(store, _user(is_admin=False), pool=object()).get("/api/library").json()
    assert {s["ref"]: s["can_delete"] for s in body["scopes"]} == {
        "user:me": True,
        "shared": False,
        "project:quay": True,
    }
    assert body["is_admin"] is False
    body = _client(store, _user(is_admin=True), pool=object()).get("/api/library").json()
    assert {s["ref"]: s["can_delete"] for s in body["scopes"]}["shared"] is True


def test_library_without_db_has_no_projects(store, member_of_one_project):
    body = _client(store, _user(), pool=None).get("/api/library").json()
    assert [s["ref"] for s in body["scopes"]] == ["user:me", "shared"]


def test_library_local_dev_user_is_shared_only(store):
    # Auth disabled -> synthetic zero-UUID user: no personal scope.
    app = create_app(doc_store=LocalDocStore(store))
    body = TestClient(app).get("/api/library").json()
    assert [s["ref"] for s in body["scopes"]] == ["shared"]
    assert [d["id"] for d in body["docs"]] == ["shared-doc"]


def test_landing_shape_unchanged_with_projects(store, member_of_one_project):
    body = _client(store, _user(), pool=object()).get("/api/landing").json()
    assert [d["id"] for d in body["personal"]] == ["my-doc"]
    assert [d["id"] for d in body["shared"]] == ["shared-doc"]
    assert [(p["slug"], p["name"], [d["id"] for d in p["docs"]]) for p in body["projects"]] == [
        ("quay", "Quay Upgrade", ["project-doc"])
    ]
    assert {d["id"] for d in body["recent"]} == {"my-doc", "shared-doc", "project-doc"}
