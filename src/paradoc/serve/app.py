"""FastAPI app factory for `paradoc serve`.

Endpoints mirror `paradoc.docstore.DocStore`. The binary endpoint
supports HTTP Range so chunked clients (and the browser viewer) stream
glbs efficiently from S3-backed deployments.

NOTE: `from __future__ import annotations` is intentionally absent —
FastAPI introspects function annotations at create_app() time and would
fail to resolve `Request` (imported inside the function body for the
optional-fastapi-dep contract) against module globals if annotations
were lazy strings, causing every `request: Request` route to 422 with
"missing query param 'request'".
"""

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from paradoc.docstore import DocStore

from .auth import AuthConfig, User
from .scope import Scope, scope_from_path

logger = logging.getLogger(__name__)


def _pkg_version(name: str) -> Optional[str]:
    """Best-effort package version lookup; returns None if not installed."""
    try:
        from importlib.metadata import PackageNotFoundError, version as _v

        try:
            return _v(name)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def _build_info() -> dict[str, Any]:
    """Snapshot the runtime + image identity. Computed once at app build.

    `image_sha` and `image_tag` come from env vars the Docker build bakes
    in (see Dockerfile `PARADOC_BUILD_SHA` / `PARADOC_BUILD_TAG`); fall
    back to "unknown" when running outside the container so local dev
    doesn't crash on missing values.
    """
    import paradoc as _paradoc

    return {
        "paradoc_version": getattr(_paradoc, "__version__", _pkg_version("paradoc")),
        "python_version": sys.version.split()[0],
        "python_full_version": sys.version,
        "platform": sys.platform,
        "fastapi_version": _pkg_version("fastapi"),
        "uvicorn_version": _pkg_version("uvicorn"),
        "obstore_version": _pkg_version("obstore"),
        "image_sha": os.environ.get("PARADOC_BUILD_SHA") or "unknown",
        "image_tag": os.environ.get("PARADOC_BUILD_TAG") or "unknown",
        "build_time": os.environ.get("PARADOC_BUILD_TIME") or "unknown",
    }


def create_app(
    *,
    doc_store: DocStore,
    static_dir: Optional[Path] = None,
    database_url: Optional[str] = None,
):
    """Build the FastAPI app. Imports FastAPI lazily so this module is
    importable without the `serve` extra installed.

    ``database_url`` (or env ``PARADOC_DATABASE_URL``) drives the
    optional Postgres control plane (users, projects, memberships).
    When empty, paradoc-serve runs in shared-only mode and the pool
    on ``app.state.db_pool`` stays ``None``.

    Auth is driven by env vars (``PARADOC_AUTH_ENABLED``,
    ``PARADOC_OIDC_PROVIDERS_JSON``, ``PARADOC_AUTH_ADMIN_GROUP``); see
    :mod:`paradoc.serve.auth`. When disabled, every request gets a
    synthetic local-dev admin user so dev paths stay untouched.
    """
    try:
        from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
        from fastapi.responses import JSONResponse, Response, StreamingResponse
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is required for `paradoc serve`. Install the `serve` extra "
            "(pip install paradoc[serve])."
        ) from exc

    db_url = database_url or os.environ.get("PARADOC_DATABASE_URL", "")

    @asynccontextmanager
    async def lifespan(app):
        from . import auth as auth_module
        from . import db as db_module
        try:
            app.state.db_pool = await db_module.init_pool(db_url)
        except Exception:
            logger.exception("db: pool init failed; running shared-only")
            app.state.db_pool = None
        yield
        try:
            await auth_module.aclose(app)
        except Exception:
            logger.exception("auth close failed")
        try:
            await db_module.close_pool(app.state.db_pool)
        except Exception:
            logger.exception("db close failed")

    app = FastAPI(
        title="paradoc",
        description="Read-only HTTP API over a compiled paradoc bundle.",
        version="1",
        lifespan=lifespan,
    )
    # Install OIDC verifier + config on app.state. Reads
    # PARADOC_AUTH_ENABLED / PARADOC_OIDC_PROVIDERS_JSON /
    # PARADOC_AUTH_ADMIN_GROUP from env. When disabled, current_user()
    # returns the synthetic local-dev principal so dev paths stay
    # untouched.
    from . import auth as auth_module
    auth_module.install(app)

    # Compute build info once at app create. Env vars don't change after
    # process start, so caching at the closure level is safe and saves a
    # few µs per /api/info call.
    _info_snapshot = _build_info()

    # ── Public discovery endpoints (no auth) ─────────────────────────

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "docs": doc_store.list_doc_ids()}

    @app.get("/api/info")
    async def info() -> dict[str, Any]:
        return _info_snapshot

    # Runtime config injected at the SPA's <script src="/config.js">. Same-host
    # serving (paradoc.<host>/ and /api/*), so apiBase is empty. When auth is
    # enabled, also emits the first trusted IdP's issuer + client_id so the
    # SPA can initiate the OIDC PKCE code flow without hard-coding values
    # into the bundle. Multi-provider UI is a later iteration; the SPA picks
    # the first entry for v0.
    @app.get("/config.js")
    async def config_js():
        cfg: AuthConfig = app.state.auth_config
        payload: dict[str, Any] = {"transport": "rest", "apiBase": ""}
        if cfg.enabled and cfg.providers:
            p = cfg.providers[0]
            payload["authEnabled"] = True
            payload["authIssuer"] = p.issuer
            payload["authClientId"] = p.client_id
            payload["authAudience"] = p.audience or p.client_id
        else:
            payload["authEnabled"] = False
        body = "window.__PARADOC_CONFIG__ = " + json.dumps(payload) + ";\n"
        return Response(content=body, media_type="application/javascript")

    # ── Authenticated endpoints ──────────────────────────────────────

    @app.get("/api/me")
    async def me(user: User = Depends(auth_module.current_user)) -> dict[str, Any]:
        return {
            "id": user.id,
            "iss": user.iss,
            "subject": user.subject,
            "email": user.email,
            "display_name": user.display_name,
            "groups": sorted(user.groups),
            "is_admin": user.is_admin,
        }

    # ── API tokens (paradoc publish CLI) ─────────────────────────────
    #
    # Long-lived bearer credentials owned by each user. The plaintext
    # token is shown exactly once on create; subsequent GETs only
    # return metadata. Hash is sha256 of plaintext, no salt — the
    # plaintext is 32 bytes of secrets.token_bytes (256 bits), so
    # brute-forcing the hash is not a realistic attack.

    @app.get("/api/me/tokens")
    async def list_my_tokens(
        request: Request, user: User = Depends(auth_module.current_user)
    ) -> dict[str, Any]:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=503,
                detail="api-token feature requires a Postgres-backed deployment",
            )
        from . import db as _db
        return {"tokens": await _db.list_api_tokens(pool, user.id)}

    @app.post("/api/me/tokens")
    async def create_my_token(
        request: Request,
        user: User = Depends(auth_module.current_user),
    ) -> dict[str, Any]:
        import hashlib
        import secrets

        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=503,
                detail="api-token feature requires a Postgres-backed deployment",
            )
        # Local-dev synthetic user is in the DB (auto-upserted) but we
        # don't issue tokens for it — it's already a no-auth shortcut.
        if user.id.startswith("00000000"):
            raise HTTPException(
                status_code=403,
                detail="cannot issue tokens for the local-dev user",
            )
        body = await request.json()
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        if len(name) > 200:
            raise HTTPException(status_code=400, detail="name too long")

        # Plaintext shape: `paradoc_` + base64url(32 bytes). The prefix
        # makes the token recognisable in logs / vault dumps and gates
        # the API-token path inside the verifier.
        raw = secrets.token_urlsafe(32)
        plaintext = f"paradoc_{raw}"
        digest = hashlib.sha256(plaintext.encode("utf-8")).digest()

        from . import db as _db
        row = await _db.create_api_token(
            pool, user_id=user.id, name=name, token_hash=digest
        )
        # Plaintext returned exactly once. The client is expected to
        # stash it immediately; subsequent GETs only see the metadata.
        return {**row, "token": plaintext}

    @app.delete("/api/me/tokens/{token_id}")
    async def revoke_my_token(
        token_id: str,
        request: Request,
        user: User = Depends(auth_module.current_user),
    ) -> dict[str, Any]:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=503,
                detail="api-token feature requires a Postgres-backed deployment",
            )
        import uuid as _uuid
        try:
            _uuid.UUID(token_id)
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(status_code=400, detail="invalid token id")
        from . import db as _db
        ok = await _db.revoke_api_token(pool, token_id=token_id, user_id=user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="token not found")
        return {"status": "revoked"}

    # ── Doc-content endpoints ────────────────────────────────────────
    #
    # Each operation has two URL forms:
    #   * Legacy:       /api/docs/{doc_id}/...
    #                   Implicitly scope=shared. Used by the existing
    #                   single-page frontend.
    #   * Scope-aware:  /api/scopes/{scope}/docs/{doc_id}/...
    #                   Explicit scope, gated by scope_from_path() which
    #                   verifies membership. Used by the (future) admin
    #                   UI and project-scoped views.
    #
    # Both URL forms call the same helper. The helper takes a Scope and
    # the doc identifier; route handlers wire either Scope.shared() or
    # the Depends(scope_from_path()) dep result.

    def _list_docs(scope: Scope) -> dict[str, Any]:
        groups = doc_store.list_doc_groups()
        return {
            "docs": doc_store.list_doc_ids(scope),
            "groups": [
                {"key": g.key, "label": g.label, "docs": list(g.doc_ids)}
                for g in groups
            ],
        }

    def _get_manifest(doc_id: str, scope: Scope):
        data = doc_store.get_static_manifest_bytes(doc_id, scope=scope)
        if data is None:
            raise HTTPException(status_code=404, detail="manifest not found")
        return Response(content=data, media_type="application/json")

    def _get_section(doc_id: str, idx: int, scope: Scope):
        data = doc_store.get_static_section_bytes(doc_id, idx, scope=scope)
        if data is None:
            raise HTTPException(status_code=404, detail=f"section {idx} not found")
        return Response(content=data, media_type="application/json")

    def _get_all_plots(doc_id: str, scope: Scope):
        data = doc_store.get_static_plots_bytes(doc_id, scope=scope)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    def _get_all_tables(doc_id: str, scope: Scope):
        data = doc_store.get_static_tables_bytes(doc_id, scope=scope)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    def _get_all_images(doc_id: str, scope: Scope):
        data = doc_store.get_static_images_bytes(doc_id, scope=scope)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    def _get_table(doc_id: str, key: str, scope: Scope):
        table = doc_store.get_table(doc_id, key, scope=scope)
        if table is None:
            raise HTTPException(status_code=404, detail=f"table {key!r} not found")
        return JSONResponse(content=json.loads(table.model_dump_json()))

    def _get_plot(doc_id: str, key: str, scope: Scope):
        plot = doc_store.get_plot(doc_id, key, scope=scope)
        if plot is None:
            raise HTTPException(status_code=404, detail=f"plot {key!r} not found")
        return JSONResponse(content=json.loads(plot.model_dump_json()))

    def _get_presets(doc_id: str, scope: Scope):
        data = doc_store.get_presets_bytes(doc_id, scope=scope)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    def _get_3d_meta(doc_id: str, key: str, scope: Scope):
        meta = doc_store.get_three_d_meta(doc_id, key, scope=scope)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"3D asset {key!r} not found")
        body = json.loads(meta.model_dump_json())
        # Promote `metadata.image_path` (set by the figure-source
        # filters when a poster PNG sibling was baked) to a top-level
        # field so the REST transport in the frontend can detect that
        # a poster is available and fetch it via /3d/{key}/poster.
        # Mirrors what the static-export pass writes into three_d.json.
        md = meta.metadata if isinstance(meta.metadata, dict) else {}
        if md.get("image_path"):
            body["image_path"] = md["image_path"]
        # FEA artefact bundle hints: when adapy's bake landed under
        # `assets/3d/<key>/`, surface the bundle directory + manifest
        # path so the frontend knows to dispatch to the artefact-aware
        # mount (load_fea_streaming-style) instead of plain mountViewer.
        if md.get("fea_bundle_dir"):
            body["fea_bundle_dir"] = md["fea_bundle_dir"]
        if md.get("fea_manifest_path"):
            body["fea_manifest_path"] = md["fea_manifest_path"]
        # Mode-view rows (`fea_artefact_bundle_mode_view`) share the
        # canonical bundle's files but ask the embed to render a
        # specific mode. `fea_bundle_key` is the key the bundle was
        # copied under (`<bundle>/assets/3d/<bundle_key>/...`), which
        # the frontend uses to build the manifest URL — distinct from
        # `key`, which is the mode-view row's own identifier (e.g.
        # `<case>_mode_3`).
        if md.get("fea_bundle_key"):
            body["fea_bundle_key"] = md["fea_bundle_key"]
        if isinstance(md.get("fea_mode_index"), int):
            body["fea_mode_index"] = md["fea_mode_index"]
        return JSONResponse(content=body)

    def _list_bundle_files(doc_id: str, scope: Scope):
        entries = doc_store.list_bundle_files(doc_id, scope=scope)
        return {
            "doc_id": doc_id,
            "files": [
                {
                    "rel_path": e.rel_path,
                    "size": e.size,
                    "content_type": e.content_type,
                }
                for e in entries
            ],
        }

    def _get_3d_fea_artefact(doc_id: str, key: str, filename: str, scope: Scope):
        data = doc_store.get_three_d_fea_artefact(doc_id, key, filename, scope=scope)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"FEA artefact {filename!r} not found for 3D key {key!r}",
            )
        import mimetypes

        media_type, _ = mimetypes.guess_type(filename)
        if media_type is None:
            # `.bin` field blobs aren't mime-typed by default; fall
            # back to octet-stream so browsers don't try to decode
            # them as text.
            media_type = "application/octet-stream"
        return Response(
            content=data,
            media_type=media_type,
            headers={
                # Artefacts are bundle-immutable per published_at; the
                # frontend revalidates via the bundle's manifest sha.
                "Cache-Control": "public, max-age=3600",
            },
        )

    def _get_3d_poster(doc_id: str, key: str, scope: Scope):
        data = doc_store.get_three_d_poster(doc_id, key, scope=scope)
        if data is None:
            raise HTTPException(
                status_code=404,
                detail=f"3D asset {key!r} has no poster (no metadata.image_path or file missing)",
            )
        return Response(
            content=data,
            media_type="image/png",
            headers={
                # Poster contents are bundle-immutable per published_at.
                # Long browser cache + revalidation on bundle rebuild.
                "Cache-Control": "public, max-age=3600",
            },
        )

    def _get_file(doc_id: str, rel_path: str, scope: Scope):
        data = doc_store.get_file_bytes(doc_id, rel_path, scope=scope)
        if data is None:
            raise HTTPException(status_code=404, detail=f"file not found: {rel_path!r}")
        import mimetypes

        media_type, _ = mimetypes.guess_type(rel_path)
        # Default to octet-stream; the browser still treats <img>-loaded
        # PNG bytes correctly because mimetypes guesses image/png from
        # the extension, but anything new (e.g. .glb) needs an explicit
        # add or it falls back here and downloads instead of inlines.
        if media_type is None:
            media_type = "application/octet-stream"
        return Response(
            content=data,
            media_type=media_type,
            headers={
                # Bundle files are immutable per published_at — long
                # cache + revalidation via the bundle's etag at the
                # browser-cache layer is safe.
                "Cache-Control": "public, max-age=3600",
            },
        )

    async def _get_3d_blob(doc_id: str, key: str, scope: Scope, request: Request):
        meta = doc_store.get_three_d_meta(doc_id, key, scope=scope)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"3D asset {key!r} not found")

        # Honor If-None-Match for strong-etag short-circuit (sha256 is the etag).
        inm = request.headers.get("if-none-match")
        if inm and inm.strip('"') == meta.sha256:
            return Response(status_code=304, headers={"ETag": f'"{meta.sha256}"'})

        async def gen():
            stream = await doc_store.open_binary(doc_id, key, scope=scope)
            async for chunk in stream:
                yield chunk

        return StreamingResponse(
            gen(),
            media_type="model/gltf-binary",
            headers={
                "Content-Length": str(meta.size),
                "ETag": f'"{meta.sha256}"',
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Paradoc-Sha256": meta.sha256,
                "X-Paradoc-Camera-Pos": meta.camera_pos,
            },
        )

    # ── Legacy /api/docs/... routes (always shared scope) ────────────

    _shared = Scope.shared()
    _scope_dep = scope_from_path()

    @app.get("/api/docs")
    async def list_docs(
        user: User = Depends(auth_module.current_user),
    ) -> dict[str, Any]:
        return _list_docs(_shared)

    @app.get("/api/docs/{doc_id}/manifest")
    async def get_manifest(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_manifest(doc_id, _shared)

    @app.get("/api/docs/{doc_id}/sections/{idx}")
    async def get_section(
        doc_id: str, idx: int, user: User = Depends(auth_module.current_user)
    ):
        return _get_section(doc_id, idx, _shared)

    @app.get("/api/docs/{doc_id}/plots")
    async def get_all_plots(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_all_plots(doc_id, _shared)

    @app.get("/api/docs/{doc_id}/tables")
    async def get_all_tables(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_all_tables(doc_id, _shared)

    @app.get("/api/docs/{doc_id}/images")
    async def get_all_images(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_all_images(doc_id, _shared)

    @app.get("/api/docs/{doc_id}/tables/{key}")
    async def get_table(
        doc_id: str, key: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_table(doc_id, key, _shared)

    @app.get("/api/docs/{doc_id}/plots/{key}")
    async def get_plot(
        doc_id: str, key: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_plot(doc_id, key, _shared)

    @app.get("/api/docs/{doc_id}/presets")
    async def get_presets(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_presets(doc_id, _shared)

    @app.get("/api/docs/{doc_id}/3d/{key}/meta")
    async def get_3d_meta(
        doc_id: str, key: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_3d_meta(doc_id, key, _shared)

    @app.get("/api/docs/{doc_id}/3d/{key}/blob")
    async def get_3d_blob(
        doc_id: str,
        key: str,
        request: Request,
        user: User = Depends(auth_module.current_user),
    ):
        return await _get_3d_blob(doc_id, key, _shared, request)

    @app.get("/api/docs/{doc_id}/3d/{key}/poster")
    async def get_3d_poster(
        doc_id: str, key: str, user: User = Depends(auth_module.current_user)
    ):
        return _get_3d_poster(doc_id, key, _shared)

    @app.get("/api/docs/{doc_id}/3d/{key}/fea/{filename:path}")
    async def get_3d_fea_artefact(
        doc_id: str,
        key: str,
        filename: str,
        user: User = Depends(auth_module.current_user),
    ):
        return _get_3d_fea_artefact(doc_id, key, filename, _shared)

    @app.get("/api/docs/{doc_id}/files/{rel_path:path}")
    async def get_doc_file(
        doc_id: str,
        rel_path: str,
        user: User = Depends(auth_module.current_user),
    ):
        return _get_file(doc_id, rel_path, _shared)

    @app.get("/api/docs/{doc_id}/manifest/files")
    async def list_doc_files(
        doc_id: str, user: User = Depends(auth_module.current_user)
    ):
        return _list_bundle_files(doc_id, _shared)

    # ── Scope-aware /api/scopes/{scope}/docs/... routes ──────────────

    @app.get("/api/scopes/{scope}/docs")
    async def s_list_docs(scope_obj: Scope = Depends(_scope_dep)) -> dict[str, Any]:
        return _list_docs(scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/manifest")
    async def s_get_manifest(doc_id: str, scope_obj: Scope = Depends(_scope_dep)):
        return _get_manifest(doc_id, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/sections/{idx}")
    async def s_get_section(
        doc_id: str, idx: int, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _get_section(doc_id, idx, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/plots")
    async def s_get_all_plots(doc_id: str, scope_obj: Scope = Depends(_scope_dep)):
        return _get_all_plots(doc_id, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/tables")
    async def s_get_all_tables(doc_id: str, scope_obj: Scope = Depends(_scope_dep)):
        return _get_all_tables(doc_id, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/images")
    async def s_get_all_images(doc_id: str, scope_obj: Scope = Depends(_scope_dep)):
        return _get_all_images(doc_id, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/tables/{key}")
    async def s_get_table(
        doc_id: str, key: str, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _get_table(doc_id, key, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/plots/{key}")
    async def s_get_plot(
        doc_id: str, key: str, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _get_plot(doc_id, key, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/presets")
    async def s_get_presets(doc_id: str, scope_obj: Scope = Depends(_scope_dep)):
        return _get_presets(doc_id, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/3d/{key}/meta")
    async def s_get_3d_meta(
        doc_id: str, key: str, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _get_3d_meta(doc_id, key, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/3d/{key}/blob")
    async def s_get_3d_blob(
        doc_id: str,
        key: str,
        request: Request,
        scope_obj: Scope = Depends(_scope_dep),
    ):
        return await _get_3d_blob(doc_id, key, scope_obj, request)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/3d/{key}/poster")
    async def s_get_3d_poster(
        doc_id: str, key: str, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _get_3d_poster(doc_id, key, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/3d/{key}/fea/{filename:path}")
    async def s_get_3d_fea_artefact(
        doc_id: str,
        key: str,
        filename: str,
        scope_obj: Scope = Depends(_scope_dep),
    ):
        return _get_3d_fea_artefact(doc_id, key, filename, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/files/{rel_path:path}")
    async def s_get_doc_file(
        doc_id: str,
        rel_path: str,
        scope_obj: Scope = Depends(_scope_dep),
    ):
        return _get_file(doc_id, rel_path, scope_obj)

    @app.get("/api/scopes/{scope}/docs/{doc_id}/manifest/files")
    async def s_list_doc_files(
        doc_id: str, scope_obj: Scope = Depends(_scope_dep)
    ):
        return _list_bundle_files(doc_id, scope_obj)

    # ── Bundle upload (paradoc publish CLI) ───────────────────────────
    #
    # One PUT per bundle file. The CLI walks the compiled bundle and
    # pushes each file under its bundle-relative path. The scope dep
    # gates access: shared = anyone with a valid bearer, user:me = the
    # token owner, project:<id> = a project member.

    @app.put("/api/scopes/{scope}/docs/{doc_id}/bundle/{rel_path:path}")
    async def s_put_doc_bundle_file(
        doc_id: str,
        rel_path: str,
        request: Request,
        scope_obj: Scope = Depends(_scope_dep),
    ):
        # 8 MB cap on a single file — large GLBs already chunk via the
        # bundle structure, the 3D viewer streams from the glb route.
        # Anything bigger is almost certainly a wrong-source-tree upload.
        MAX_SIZE = 8 * 1024 * 1024
        body = await request.body()
        if len(body) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="payload too large")
        try:
            doc_store.put_bundle_file(doc_id, rel_path, body, scope=scope_obj)
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except NotImplementedError:
            raise HTTPException(
                status_code=501,
                detail="this docstore does not support uploads",
            )
        return {"status": "ok", "size": len(body)}

    # ── Landing aggregator ───────────────────────────────────────────
    #
    # One round-trip backing the landing-page UI. Bundles the
    # shared / personal / per-project doc lists so the SPA doesn't
    # have to fan out N requests to draw the first screen. Each entry
    # is intentionally minimal (`id` + `scope`) — the SPA still calls
    # /api/docs/{id}/manifest for full metadata when the user opens
    # one. `recent` stays empty until we surface per-doc updated_at;
    # the frontend hides the section when it's empty.

    def _doc_entry(doc_id: str, scope: Scope, scope_label: str) -> dict[str, Any]:
        """Build a landing-card entry — id + scope + provenance.

        Reads each doc's bundle manifest so the SPA can show
        published_at + git info on the card. Missing manifest (pre-v2
        bundle, S3 fetch failed, etc.) gracefully degrades to id-only.
        """
        entry: dict[str, Any] = {"id": doc_id, "scope": scope_label}
        try:
            bm = doc_store.get_bundle_manifest(doc_id, scope=scope)
        except Exception:
            bm = None
        if bm is not None:
            entry["published_at"] = bm.published_at or bm.created_at
            entry["paradoc_version"] = bm.paradoc_version
            if bm.git is not None:
                entry["git"] = {
                    "short_commit": bm.git.short_commit,
                    "branch": bm.git.branch,
                    "is_dirty": bm.git.is_dirty,
                    "remote_url": bm.git.remote_url,
                }
        return entry

    @app.get("/api/landing")
    async def get_landing(
        request: Request,
        user: User = Depends(auth_module.current_user),
    ) -> dict[str, Any]:
        shared_scope = Scope.shared()
        shared_ids = doc_store.list_doc_ids(shared_scope)
        shared = [_doc_entry(d, shared_scope, "shared") for d in shared_ids]

        personal: list[dict[str, Any]] = []
        # Synthetic local-dev users keep the zero UUID; their bundles
        # never live under users/<id>/, so skip the listing.
        if user.id and not user.id.startswith("00000000"):
            try:
                user_scope = Scope.user(user.id)
                personal_ids = doc_store.list_doc_ids(user_scope)
                personal = [_doc_entry(d, user_scope, "personal") for d in personal_ids]
            except Exception:
                personal = []

        projects_out: list[dict[str, Any]] = []
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None and user.id and not user.id.startswith("00000000"):
            from . import db as _db
            user_projects = await _db.list_user_projects(pool, user.id)
            for p in user_projects:
                try:
                    project_scope = Scope.project(p.id)
                    doc_ids = doc_store.list_doc_ids(project_scope)
                    docs = [_doc_entry(d, project_scope, "project") for d in doc_ids]
                except Exception:
                    docs = []
                projects_out.append(
                    {
                        "slug": p.slug,
                        "name": p.name,
                        "docs": docs,
                    }
                )

        # Recent strip = all accessible docs sorted by published_at desc,
        # capped. We dedupe by (scope, id) so the same doc doesn't appear
        # twice if it's pushed to both shared + a project.
        all_entries = shared + personal + [d for g in projects_out for d in g["docs"]]
        with_ts = [e for e in all_entries if e.get("published_at")]
        with_ts.sort(key=lambda e: e["published_at"], reverse=True)
        recent = with_ts[:8]

        return {
            "recent": recent,
            "personal": personal,
            "shared": shared,
            "projects": projects_out,
        }

    # ── Admin API ────────────────────────────────────────────────────
    #
    # Project CRUD + member management + shelf_base_url config. All
    # routes are admin-gated via require_admin (composes with
    # current_user). Without a DB pool every endpoint 503s — there's
    # no in-memory fallback for project membership by design.

    admin = APIRouter(
        prefix="/api/admin",
        dependencies=[Depends(auth_module.require_admin)],
    )

    def _require_pool(request: Request):
        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(
                status_code=503,
                detail="admin endpoints require a Postgres-backed deployment "
                "(set PARADOC_DATABASE_URL)",
            )
        return pool

    def _validate_uuid(value: str, what: str = "id") -> str:
        import uuid as _uuid
        try:
            return str(_uuid.UUID(value))
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"invalid {what}") from exc

    from . import db as db_module

    @admin.get("/users")
    async def admin_users_list(request: Request) -> JSONResponse:
        """Known users. Powers the admin UI's add-member picker."""
        pool = _require_pool(request)
        return JSONResponse({"users": await db_module.list_users(pool)})

    @admin.get("/projects")
    async def admin_projects_list(request: Request) -> JSONResponse:
        pool = _require_pool(request)
        return JSONResponse({"projects": await db_module.list_all_projects(pool)})

    @admin.post("/projects")
    async def admin_projects_create(
        request: Request,
        user: User = Depends(auth_module.current_user),
    ) -> JSONResponse:
        pool = _require_pool(request)
        body = await request.json()
        slug = (body.get("slug") or "").strip()
        name = (body.get("name") or "").strip()
        if not slug or not name:
            raise HTTPException(status_code=400, detail="slug and name required")
        import re
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", slug):
            raise HTTPException(
                status_code=400,
                detail="slug must be lowercase alnum/hyphens (max 63)",
            )
        try:
            project = await db_module.create_project(pool, slug, name)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # Auto-add the creator as owner so the new project is immediately
        # navigable from their session; otherwise it's orphaned until an
        # admin adds someone manually.
        await db_module.add_project_member(pool, project["id"], user.id, role="owner")
        project["member_count"] = 1
        return JSONResponse(project, status_code=201)

    @admin.patch("/projects/{project_id}")
    async def admin_projects_update(
        project_id: str,
        request: Request,
    ) -> JSONResponse:
        """Partial update of name and/or shelf_base_url.

        Body keys:
          * ``name`` — new display name.
          * ``shelf_base_url`` — paste-only string (no shelf reachability
            check). Pass ``null`` to clear.
        """
        pool = _require_pool(request)
        pid = _validate_uuid(project_id, "project_id")
        body = await request.json()
        name = body.get("name")
        if name is not None:
            name = str(name).strip()
            if not name:
                raise HTTPException(status_code=400, detail="name cannot be empty")
        clear = "shelf_base_url" in body and body["shelf_base_url"] is None
        shelf_url = None
        if not clear and "shelf_base_url" in body:
            shelf_url = str(body["shelf_base_url"]).strip()
            if not shelf_url:
                clear = True
                shelf_url = None
        updated = await db_module.update_project(
            pool, pid,
            name=name,
            shelf_base_url=shelf_url,
            clear_shelf_base_url=clear,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="project not found")
        return JSONResponse(updated)

    @admin.delete("/projects/{project_id}")
    async def admin_projects_archive(
        project_id: str,
        request: Request,
    ) -> Response:
        pool = _require_pool(request)
        pid = _validate_uuid(project_id, "project_id")
        ok = await db_module.archive_project(pool, pid)
        if not ok:
            raise HTTPException(status_code=404, detail="project not found")
        return Response(status_code=204)

    @admin.get("/projects/{project_id}/members")
    async def admin_project_members_list(
        project_id: str,
        request: Request,
    ) -> JSONResponse:
        pool = _require_pool(request)
        pid = _validate_uuid(project_id, "project_id")
        if not await db_module.project_exists(pool, pid):
            raise HTTPException(status_code=404, detail="project not found")
        return JSONResponse(
            {"members": await db_module.list_project_members(pool, pid)}
        )

    @admin.post("/projects/{project_id}/members")
    async def admin_project_members_add(
        project_id: str,
        request: Request,
    ) -> JSONResponse:
        """Add a member by ``user_id`` (UUID).

        The user must already exist (have authenticated at least once);
        paradoc isn't an invite system. The admin UI's user picker pulls
        from ``GET /api/admin/users``.
        """
        pool = _require_pool(request)
        pid = _validate_uuid(project_id, "project_id")
        body = await request.json()
        user_id = (body.get("user_id") or "").strip()
        role = (body.get("role") or "member").strip() or "member"
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        uid = _validate_uuid(user_id, "user_id")
        if not await db_module.project_exists(pool, pid):
            raise HTTPException(status_code=404, detail="project not found")
        if not await db_module.user_exists(pool, uid):
            raise HTTPException(status_code=404, detail="user not found")
        added = await db_module.add_project_member(pool, pid, uid, role)
        return JSONResponse(
            {"user_id": uid, "role": role, "added": added},
            status_code=201 if added else 200,
        )

    @admin.delete("/projects/{project_id}/members/{user_id}")
    async def admin_project_members_remove(
        project_id: str,
        user_id: str,
        request: Request,
    ) -> Response:
        pool = _require_pool(request)
        pid = _validate_uuid(project_id, "project_id")
        uid = _validate_uuid(user_id, "user_id")
        ok = await db_module.remove_project_member(pool, pid, uid)
        if not ok:
            raise HTTPException(status_code=404, detail="not a member")
        return Response(status_code=204)

    app.include_router(admin)

    # SPA-fallback + static mount. Routes registered above (every
    # /api/*, /config.js) keep precedence over this mount. The fallback
    # is needed because the SPA uses react-router-dom client-side
    # routing: a direct GET to /admin (or any other client-side route)
    # must return index.html so the SPA can boot and resolve the route
    # itself. Without the fallback, StaticFiles would 404 because no
    # /admin file exists on disk.
    if static_dir is not None and static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        _index_path = (static_dir / "index.html").resolve()
        _static_dir = Path(static_dir).resolve()

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Try the literal file first (e.g. assets/foo.js); fall back
            # to index.html for any unknown path so client-side routes
            # resolve. The API routes above the mount win their paths
            # via FastAPI's route-resolution order.
            candidate = (static_dir / full_path).resolve()
            if (
                candidate.is_relative_to(_static_dir)
                and candidate.is_file()
            ):
                return Response(
                    content=candidate.read_bytes(),
                    media_type=_guess_media_type(candidate.name),
                )
            if _index_path.is_file():
                return Response(
                    content=_index_path.read_bytes(),
                    media_type="text/html; charset=utf-8",
                )
            raise HTTPException(status_code=404, detail="not found")

        # The catch-all above handles `/` too via empty `full_path`, so
        # the StaticFiles mount would shadow it. Skip the mount; rely on
        # the catch-all entirely.

    return app


def _guess_media_type(name: str) -> str:
    """Cheap content-type sniffer for the SPA fallback. Covers the
    Vite-emitted file types; everything else falls through to
    application/octet-stream."""
    import mimetypes

    guess, _ = mimetypes.guess_type(name)
    return guess or "application/octet-stream"
