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
from pathlib import Path
from typing import Any, Optional

from paradoc.docstore import DocStore

from .auth import AuthPolicy, IngressTrustPolicy


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

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "docs": doc_store.list_doc_ids()}

    @app.get("/api/docs")
    async def list_docs() -> dict[str, Any]:
        return {"docs": doc_store.list_doc_ids()}

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
