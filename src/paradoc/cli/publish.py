"""`paradoc publish` — compile a doc and PUT every bundle file to a
running paradoc-serve.

Mirrors the ergonomics of `ada-build run` + `ada-build upload`: one
command, one HTTPS round-trip per file, bearer-token auth via
``PARADOC_VIEWER_URL`` + ``PARADOC_VIEWER_TOKEN`` env vars.

Token shape is the same opaque ``paradoc_<base64url>`` string the
``POST /api/me/tokens`` route hands out; the server's verifier looks
it up in ``api_tokens`` and resolves to the issuing user.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="Compile and publish a paradoc bundle.")


def _env_required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.stderr.write(f"missing env var: {name}\n")
        raise typer.Exit(2)
    return val


def _put(url: str, token: str, body: bytes) -> None:
    """One-shot PUT with the bearer token attached.

    Uses stdlib urllib so the CLI doesn't pull a runtime requests/httpx
    dependency just for publishing. 4xx/5xx raises via urllib's HTTPError.
    """
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"upload failed: HTTP {resp.status}")


@app.command()
def publish(
    source_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Doc source directory passed to OneDoc().compile().",
    ),
    doc_id: str = typer.Option(
        None,
        "--doc-id",
        help="Doc id to publish under. Defaults to the source dir name.",
    ),
    scope: str = typer.Option(
        "user:me",
        "--scope",
        help="Target scope: 'user:me' (default), 'shared', or 'project:<slug>'.",
    ),
    work_dir: Path = typer.Option(
        Path("temp"),
        "--work-dir",
        help="Local compile scratch dir.",
    ),
) -> None:
    """Compile ``source_dir`` and upload the resulting bundle.

    Required env: ``PARADOC_VIEWER_URL`` (e.g. ``https://paradoc.krande.no``)
    and ``PARADOC_VIEWER_TOKEN`` (a token from ``POST /api/me/tokens``).
    """
    base = _env_required("PARADOC_VIEWER_URL").rstrip("/")
    token = _env_required("PARADOC_VIEWER_TOKEN")
    if not token.startswith("paradoc_"):
        sys.stderr.write(
            "PARADOC_VIEWER_TOKEN should start with 'paradoc_' — "
            "use a token from POST /api/me/tokens, not the OIDC bearer.\n"
        )
        raise typer.Exit(2)

    # Local import keeps `paradoc publish --help` snappy and avoids
    # pulling pandoc/pypandoc into the CLI module-load path.
    from paradoc import OneDoc

    resolved_doc_id = doc_id or source_dir.name
    typer.echo(f"compiling {source_dir} -> doc_id={resolved_doc_id}")
    one = OneDoc(str(source_dir), work_dir=str(work_dir))
    one.compile(resolved_doc_id, auto_open=False)

    # OneDoc writes the bundle to build_dir; we pick that up and walk
    # every file. The export_static layout already mirrors what
    # paradoc-serve expects under each scope/<doc_id>/.
    bundle_root = Path(one.build_dir)
    if not (bundle_root / "manifest.json").is_file():
        sys.stderr.write(f"compiled bundle missing manifest.json at {bundle_root}\n")
        raise typer.Exit(2)

    scope_segment = urllib.parse.quote(scope, safe=":")
    uploaded = 0
    for fp in sorted(bundle_root.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(bundle_root).as_posix()
        encoded = "/".join(urllib.parse.quote(seg) for seg in rel.split("/"))
        url = f"{base}/api/scopes/{scope_segment}/docs/" f"{urllib.parse.quote(resolved_doc_id)}/bundle/{encoded}"
        _put(url, token, fp.read_bytes())
        uploaded += 1
        typer.echo(f"  PUT {rel}")
    typer.echo(f"published {uploaded} file(s) to {scope}/{resolved_doc_id}")


if __name__ == "__main__":
    app()
