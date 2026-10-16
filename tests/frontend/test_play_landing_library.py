"""Landing page + Library view against a live paradoc-serve (REST mode).

* The landing page shows a search field and "Recent"; typing filters, Enter opens the top hit.
* The Library lists every accessible doc grouped by scope (personal, shared, member projects).
* Delete is offered only where the server allows it (not on shared docs for a non-admin) and
  asks for confirmation before removing the bundle.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from paradoc.docstore import LocalDocStore, write_manifest

ME = "11111111-2222-3333-4444-555555555555"
PROJECT = "aaaaaaaa-0000-0000-0000-000000000001"

DOCS = {
    "shared": ["load-case-summary", "structural-design-basis"],
    f"users/{ME}": ["draft-notes"],
    f"projects/{PROJECT}": ["quay-foundation-loads", "beam-strength-check"],
}


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _write_store(root):
    import json

    for prefix, ids in DOCS.items():
        for doc_id in ids:
            b = root / prefix / doc_id
            (b / "static" / "sections").mkdir(parents=True)
            write_manifest(b, doc_id=doc_id)
            (b / "static" / "manifest.json").write_text(
                json.dumps({"docId": doc_id, "sections": [{"id": "s1", "title": "First", "index": 0, "level": 1}]})
            )
            blocks = [
                {"t": "Header", "c": [1, ["s1", [], []], [{"t": "Str", "c": "First"}]]},
                {"t": "Para", "c": [{"t": "Str", "c": f"Body of {doc_id}"}]},
            ]
            (b / "static" / "sections" / "0.json").write_text(
                json.dumps(
                    {"section": {"id": "s1", "title": "First", "index": 0, "level": 1}, "doc": {"blocks": blocks}}
                )
            )


@pytest.fixture
def library_site(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    uvicorn = pytest.importorskip("uvicorn")

    from paradoc import OneDoc
    from paradoc.frontend.frontend_handler import FrontendHandler
    from paradoc.serve import auth as auth_module
    from paradoc.serve import create_app
    from paradoc.serve import db as db_module

    root = tmp_path / "store"
    _write_store(root)

    async def list_user_projects(pool, user_id):
        return [db_module.Project(id=PROJECT, slug="quay", name="Quay Wall", shelf_base_url=None, role="member")]

    async def project_id_from_slug(pool, slug):
        return PROJECT if slug == "quay" else None

    async def is_project_member(pool, *, project_id, user_id):
        return project_id == PROJECT and user_id == ME

    async def init_pool(url):
        return object()

    async def close_pool(pool):
        return None

    for name, fn in (
        ("list_user_projects", list_user_projects),
        ("project_id_from_slug", project_id_from_slug),
        ("is_project_member", is_project_member),
        ("init_pool", init_pool),
        ("close_pool", close_pool),
    ):
        monkeypatch.setattr(db_module, name, fn)

    user = auth_module.User(
        id=ME,
        iss="test",
        subject="demo",
        email="demo@example.com",
        display_name="Demo User",
        groups=frozenset(),
        is_admin=False,
    )
    src = tmp_path / "src"
    (src / "00-main").mkdir(parents=True)
    (src / "00-main" / "doc.md").write_text("# x\n")
    fh = FrontendHandler(OneDoc(src, work_dir=tmp_path / "work"), host="localhost", port=13579)
    assert fh.ensure_frontend_extracted()
    app = create_app(doc_store=LocalDocStore(root), static_dir=fh.resources_dir)
    app.dependency_overrides[auth_module.current_user] = lambda: user
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=_free_port(), log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=server.run, daemon=True, name="library-serve")
    thread.start()
    deadline = time.time() + 10
    while not getattr(server, "started", False):
        if time.time() > deadline:
            pytest.fail("paradoc-serve did not start")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{server.config.port}", root
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


def test_landing_search_and_recents(page, library_site):
    base, _ = library_site
    page.goto(base + "/")
    search = page.locator("#landing-search")
    search.wait_for(timeout=15000)
    rows = page.locator('[data-testid="landing-row"]')
    rows.first.wait_for(timeout=10000)
    # Recent lists every published doc (all have publish times), newest first.
    assert rows.count() == 5
    assert page.get_by_role("heading", name="Recent").is_visible()
    assert page.locator('[data-testid="open-library"]').is_visible()

    search.click()
    page.keyboard.type("quay")
    page.wait_for_function("document.querySelectorAll('[data-testid=landing-row]').length === 2")
    first = rows.first.inner_text()
    assert "Quay foundation loads" in first

    page.keyboard.press("Enter")
    page.wait_for_url("**doc=quay-foundation-loads**", timeout=10000)
    assert "scope=project%3Aquay" in page.url or "scope=project:quay" in page.url
    page.get_by_text("Body of quay-foundation-loads").wait_for(timeout=15000)

    # Opening it recorded local history: back on the landing page it leads Recent as "opened".
    page.locator('[data-testid="brand-home"]').click()
    rows.first.wait_for(timeout=10000)
    assert "opened" in rows.first.inner_text()
    assert "Quay foundation loads" in rows.first.inner_text()


def test_library_groups_by_scope_and_gates_delete(page, library_site):
    base, root = library_site
    page.goto(base + "/")
    page.locator('[data-testid="open-library"]').click()
    page.wait_for_url("**view=library**")
    page.locator('[data-testid="library-doc"]').first.wait_for(timeout=10000)

    groups = {
        "user:me": ["Draft notes"],
        "shared": ["Load case summary", "Structural design basis"],
        "project:quay": ["Beam strength check", "Quay foundation loads"],
    }
    for ref, titles in groups.items():
        g = page.locator(f'[data-testid="library-group-{ref}"]')
        text = g.inner_text()
        for t in titles:
            assert t in text, (ref, t, text)
        assert g.locator('[data-testid="library-doc"]').count() == len(titles)

    # Shared doc, non-admin: the actions menu has no Delete.
    page.get_by_role("button", name="Actions for Load case summary").click()
    menu = page.get_by_role("menu", name="Actions for Load case summary")
    menu.wait_for()
    assert menu.get_by_role("menuitem", name="Copy link").is_visible()
    assert menu.get_by_role("menuitem", name="Delete…").count() == 0
    page.keyboard.press("Escape")

    # Personal doc: Delete asks first; Cancel keeps it, Delete removes it.
    page.get_by_role("button", name="Actions for Draft notes").click()
    page.get_by_role("menuitem", name="Delete…").click()
    dialog = page.get_by_role("dialog", name="Delete document?")
    dialog.wait_for()
    dialog.get_by_role("button", name="Cancel").click()
    assert (root / "users" / ME / "draft-notes").exists()

    page.get_by_role("button", name="Actions for Draft notes").click()
    page.get_by_role("menuitem", name="Delete…").click()
    page.get_by_role("dialog", name="Delete document?").get_by_role("button", name="Delete").click()
    page.locator('[data-testid="library-group-user:me"]').wait_for(state="detached", timeout=10000)
    assert not (root / "users" / ME / "draft-notes").exists()

    # Filter by scope from the scope rail; an empty filter result shows the empty state.
    page.locator('nav[aria-label="Scopes"] button', has_text="Quay Wall").click()
    assert page.locator('[data-testid="library-doc"]').count() == 2
    page.get_by_label("Filter documents").fill("zzz")
    page.get_by_text("No documents match the filter").wait_for()


def test_reader_shell_breadcrumb_switcher_and_menu(page, library_site):
    base, _ = library_site
    page.goto(base + "/?doc=beam-strength-check&scope=project:quay")
    page.get_by_text("Body of beam-strength-check").wait_for(timeout=15000)

    # Breadcrumb: scope crumb + doc title; the title opens the switcher.
    crumb = page.get_by_role("navigation", name="Breadcrumb")
    assert "Quay Wall" in crumb.inner_text()
    page.locator('[data-testid="doc-switcher"]').click()
    page.get_by_label("Find a document").fill("foundation")
    page.keyboard.press("Enter")
    page.get_by_text("Body of quay-foundation-loads").wait_for(timeout=15000)

    # Options menu: document toggles, theme, account; no admin entry for a non-admin.
    page.locator('[data-testid="app-menu-button"]').click()
    menu = page.locator('[data-testid="app-menu"]')
    menu.wait_for()
    for name in ("Page view (A4 sheets)", "Source view", "3D viewer controls"):
        assert menu.get_by_role("menuitemcheckbox", name=name).count() == 1
    for name in ("Find in document", "Bundle files & downloads…", "Account & API tokens…", "About paradoc…"):
        assert menu.get_by_role("menuitem", name=name).count() == 1, name
    assert menu.get_by_role("menuitemradio", name="Dark").count() == 1
    assert menu.get_by_role("menuitem", name="Admin panel").count() == 0
    source = menu.get_by_role("menuitemcheckbox", name="Source view")
    before = source.get_attribute("aria-checked")
    source.click()
    assert source.get_attribute("aria-checked") != before
    page.keyboard.press("Escape")
    menu.wait_for(state="detached")

    # The brand mark goes home; the outline toggle is reader-only.
    page.locator('[data-testid="brand-home"]').click()
    page.locator("#landing-search").wait_for()
    assert page.get_by_role("button", name="Toggle outline").count() == 0
    # Back returns to the doc.
    page.go_back()
    page.get_by_text("Body of quay-foundation-loads").wait_for(timeout=15000)
