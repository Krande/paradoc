"""`paradoc-serve` console entrypoint.

Usage::

    paradoc-serve <bundle_root> [--host 0.0.0.0] [--port 8000]

For S3-backed serving::

    paradoc-serve s3://bucket/prefix --port 8000

S3 URLs require `obstore` (install the `serve` extra).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False, help="Run a paradoc REST server over a bundle.")


@app.command()
def serve(
    bundle: str = typer.Argument(
        ...,
        help="Local bundle directory or s3://bucket/prefix URL.",
    ),
    host: str = typer.Option("0.0.0.0", help="Listen address."),
    port: int = typer.Option(8000, help="Listen port."),
    db_filename: str = typer.Option("paradoc.sqlite", help="Bundle DB filename."),
    require_auth: bool = typer.Option(
        False,
        "--require-auth",
        help="Reject requests without an authenticated principal header.",
    ),
    static_dir: Optional[Path] = typer.Option(
        None,
        "--static-dir",
        envvar="PARADOC_STATIC_DIR",
        help="Directory containing the SPA bundle to mount at /. Skipped when unset.",
    ),
) -> None:
    """Start the REST server."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter(
            "uvicorn is required for `paradoc-serve`. Install the `serve` extra."
        ) from exc

    from paradoc.serve import IngressTrustPolicy, create_app

    if bundle.startswith("s3://"):
        from paradoc.docstore.s3 import S3DocStore

        store = S3DocStore.from_url(bundle, db_filename=db_filename)
    else:
        from paradoc.docstore import LocalDocStore

        store = LocalDocStore(Path(bundle), db_filename=db_filename)

    policy = IngressTrustPolicy(require_principal=require_auth)
    fastapi_app = create_app(doc_store=store, auth_policy=policy, static_dir=static_dir)
    uvicorn.run(fastapi_app, host=host, port=port)


if __name__ == "__main__":
    app()
