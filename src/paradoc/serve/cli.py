"""`paradoc-serve` console entrypoint.

Usage::

    paradoc-serve <bundle_root> [--host 0.0.0.0] [--port 8000]

For S3-backed serving::

    paradoc-serve s3://bucket/prefix --port 8000

S3 URLs require `obstore` (install the `serve` extra).

Auth is driven by env vars, not CLI flags — see
``paradoc.serve.auth`` for ``PARADOC_AUTH_ENABLED`` /
``PARADOC_OIDC_PROVIDERS_JSON`` / ``PARADOC_AUTH_ADMIN_GROUP``.
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
    static_dir: Optional[Path] = typer.Option(
        None,
        "--static-dir",
        envvar="PARADOC_STATIC_DIR",
        help="Directory containing the SPA bundle to mount at /. Skipped when unset.",
    ),
    database_url: Optional[str] = typer.Option(
        None,
        "--database-url",
        envvar="PARADOC_DATABASE_URL",
        help=(
            "Postgres DSN for the optional control plane (users, projects, "
            "memberships). When unset, paradoc-serve runs in shared-only mode."
        ),
    ),
) -> None:
    """Start the REST server."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter(
            "uvicorn is required for `paradoc-serve`. Install the `serve` extra."
        ) from exc

    from paradoc.serve import create_app

    if bundle.startswith("s3://"):
        from paradoc.docstore.s3 import S3DocStore

        store = S3DocStore.from_url(bundle, db_filename=db_filename)
    else:
        from paradoc.docstore import LocalDocStore

        store = LocalDocStore(Path(bundle), db_filename=db_filename)

    fastapi_app = create_app(
        doc_store=store,
        static_dir=static_dir,
        database_url=database_url,
    )
    uvicorn.run(fastapi_app, host=host, port=port)


if __name__ == "__main__":
    app()
