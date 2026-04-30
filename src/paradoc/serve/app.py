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
import os
import sys
from pathlib import Path
from typing import Any, Optional

from paradoc.docstore import DocStore

from .auth import AuthPolicy, IngressTrustPolicy


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
    auth_policy: Optional[AuthPolicy] = None,
    static_dir: Optional[Path] = None,
):
    """Build the FastAPI app. Imports FastAPI lazily so this module is
    importable without the `serve` extra installed.
    """
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import JSONResponse, Response, StreamingResponse
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is required for `paradoc serve`. Install the `serve` extra "
            "(pip install paradoc[serve])."
        ) from exc

    policy = auth_policy or IngressTrustPolicy()

    app = FastAPI(
        title="paradoc",
        description="Read-only HTTP API over a compiled paradoc bundle.",
        version="1",
    )

    def _authorize(doc_id: str, request: Request) -> None:
        decision = policy.authorize(doc_id=doc_id, request=request)
        if not decision.allowed:
            raise HTTPException(status_code=decision.status_code, detail=decision.reason)

    # Compute build info once at app create. Env vars don't change after
    # process start, so caching at the closure level is safe and saves a
    # few µs per /api/info call.
    _info_snapshot = _build_info()

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "docs": doc_store.list_doc_ids()}

    @app.get("/api/info")
    async def info() -> dict[str, Any]:
        return _info_snapshot

    @app.get("/api/me")
    async def me(request: "Request") -> dict[str, Any]:  # noqa: F821
        # Surface what the auth policy can see. We don't gate this on a
        # principal — anonymous callers get `principal: null` so the
        # frontend's User Info panel can render an explicit "not signed
        # in" state instead of a 401.
        decision = policy.authorize(doc_id="__me__", request=request)
        headers = getattr(request, "headers", {}) or {}
        return {
            "principal": decision.principal,
            "allowed": decision.allowed,
            # Echo back the auth-related ingress headers we trust, so the
            # UI can show what the upstream proxy sent. Limited list to
            # avoid leaking unrelated headers.
            "ingress_headers": {
                "x-auth-request-user": headers.get("x-auth-request-user"),
                "x-auth-request-email": headers.get("x-auth-request-email"),
                "x-auth-request-groups": headers.get("x-auth-request-groups"),
                "x-user-id": headers.get("x-user-id"),
            },
        }

    @app.get("/api/docs")
    async def list_docs() -> dict[str, Any]:
        # `docs` is the flat backwards-compat list. `groups` is the
        # partition the doc-switcher renders as <optgroup>s; older
        # frontends ignore the extra field.
        groups = doc_store.list_doc_groups()
        return {
            "docs": doc_store.list_doc_ids(),
            "groups": [
                {"key": g.key, "label": g.label, "docs": list(g.doc_ids)}
                for g in groups
            ],
        }

    @app.get("/api/docs/{doc_id}/manifest")
    async def get_manifest(doc_id: str, request: Request):
        _authorize(doc_id, request)
        data = doc_store.get_static_manifest_bytes(doc_id)
        if data is None:
            raise HTTPException(status_code=404, detail="manifest not found")
        return Response(content=data, media_type="application/json")

    @app.get("/api/docs/{doc_id}/sections/{idx}")
    async def get_section(doc_id: str, idx: int, request: Request):
        _authorize(doc_id, request)
        data = doc_store.get_static_section_bytes(doc_id, idx)
        if data is None:
            raise HTTPException(status_code=404, detail=f"section {idx} not found")
        return Response(content=data, media_type="application/json")

    # Runtime config injected at the SPA's <script src="/config.js">. Same-host
    # serving (paradoc.<host>/ and /api/*), so apiBase is empty.
    @app.get("/config.js")
    async def config_js():
        body = (
            "window.__PARADOC_CONFIG__ = "
            "{\"transport\": \"rest\", \"apiBase\": \"\"};\n"
        )
        return Response(content=body, media_type="application/javascript")

    @app.get("/api/docs/{doc_id}/plots")
    async def get_all_plots(doc_id: str, request: Request):
        # Bulk endpoint that mirrors static-mode's `plots.json`: a dict of
        # `{key: <pre-rendered Plotly figure payload>}`. The frontend's
        # `loadRestData` seeds IndexedDB from this so InteractiveFigure can
        # detect that data exists and offer the static/interactive toggle.
        # Returns `{}` rather than 404 when the doc has no plots so the
        # frontend can treat the response uniformly.
        _authorize(doc_id, request)
        data = doc_store.get_static_plots_bytes(doc_id)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    @app.get("/api/docs/{doc_id}/tables")
    async def get_all_tables(doc_id: str, request: Request):
        _authorize(doc_id, request)
        data = doc_store.get_static_tables_bytes(doc_id)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    @app.get("/api/docs/{doc_id}/images")
    async def get_all_images(doc_id: str, request: Request):
        _authorize(doc_id, request)
        data = doc_store.get_static_images_bytes(doc_id)
        if data is None:
            return JSONResponse(content={})
        return Response(content=data, media_type="application/json")

    @app.get("/api/docs/{doc_id}/tables/{key}")
    async def get_table(doc_id: str, key: str, request: Request):
        _authorize(doc_id, request)
        table = doc_store.get_table(doc_id, key)
        if table is None:
            raise HTTPException(status_code=404, detail=f"table {key!r} not found")
        return JSONResponse(content=json.loads(table.model_dump_json()))

    @app.get("/api/docs/{doc_id}/plots/{key}")
    async def get_plot(doc_id: str, key: str, request: Request):
        _authorize(doc_id, request)
        plot = doc_store.get_plot(doc_id, key)
        if plot is None:
            raise HTTPException(status_code=404, detail=f"plot {key!r} not found")
        return JSONResponse(content=json.loads(plot.model_dump_json()))

    @app.get("/api/docs/{doc_id}/3d/{key}/meta")
    async def get_3d_meta(doc_id: str, key: str, request: Request):
        _authorize(doc_id, request)
        meta = doc_store.get_three_d_meta(doc_id, key)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"3D asset {key!r} not found")
        return JSONResponse(content=json.loads(meta.model_dump_json()))

    @app.get("/api/docs/{doc_id}/3d/{key}/blob")
    async def get_3d_blob(doc_id: str, key: str, request: Request):
        _authorize(doc_id, request)
        meta = doc_store.get_three_d_meta(doc_id, key)
        if meta is None:
            raise HTTPException(status_code=404, detail=f"3D asset {key!r} not found")

        # Honor If-None-Match for strong-etag short-circuit (sha256 is the etag).
        inm = request.headers.get("if-none-match")
        if inm and inm.strip('"') == meta.sha256:
            return Response(status_code=304, headers={"ETag": f'"{meta.sha256}"'})

        async def gen():
            stream = await doc_store.open_binary(doc_id, key)
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

    # Mount the SPA last so the API routes above keep precedence. With
    # html=True a bare GET / returns index.html (the build:standalone
    # output is a single file, so deep-link fallback isn't needed).
    if static_dir is not None and static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
