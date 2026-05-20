"""Upload compiled example bundles to the configured object store.

Reads ``dist/examples/<doc_id>/_build/`` (the output of ``compile-examples``)
and pushes each file to ``<S3_PREFIX>/shared/<doc_id>/<rel-path>`` in the
bucket identified by env. The ``shared/`` segment is the scope prefix
that paradoc-serve's scope-aware DocStore expects — examples are
deployment-wide shared content, never per-user or per-project, so they
live under ``shared/``. Everything that pinpoints a specific cluster
lives in env vars, never in this source tree.

Required env vars:

* ``S3_ENDPOINT_URL``     — full URL of the S3-compatible service
* ``S3_BUCKET``           — target bucket name
* ``AWS_ACCESS_KEY_ID``
* ``AWS_SECRET_ACCESS_KEY``

Optional:

* ``S3_PREFIX``           — extra prefix inside the bucket (default empty)
* ``AWS_REGION``          — defaults to ``us-east-1`` (S3-compatible servers
                            usually ignore region but obstore wants one)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "dist" / "examples"


def env_required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.stderr.write(f"missing env var: {name}\n")
        sys.exit(2)
    return val


def main(argv: list[str] | None = None) -> int:
    from obstore.store import S3Store
    import obstore

    if not EXAMPLES_DIR.is_dir():
        sys.stderr.write(
            f"no compiled examples at {EXAMPLES_DIR.relative_to(REPO_ROOT)}; "
            f"run `pixi run compile-examples` first.\n"
        )
        return 2

    bucket = env_required("S3_BUCKET")
    endpoint = env_required("S3_ENDPOINT_URL")
    env_required("AWS_ACCESS_KEY_ID")  # consumed by obstore via env
    env_required("AWS_SECRET_ACCESS_KEY")
    # `.get(name, default)` only falls back when the key is missing — an
    # empty value (e.g. an unset Forgejo secret expanded to "") still
    # returns "". Treat empty as missing so the SigV4 scope doesn't end
    # up as `<date>//s3/aws4_request`, which Garage rejects with
    # AuthorizationHeaderMalformed. Also write the resolved value back
    # to the env so any obstore-internal env reads see the same string
    # as our explicit `region=` kwarg.
    region = os.environ.get("AWS_REGION", "").strip() or "us-east-1"
    os.environ["AWS_REGION"] = region
    os.environ["AWS_DEFAULT_REGION"] = region
    prefix = os.environ.get("S3_PREFIX", "").strip("/")

    # `allow_http=True` so plain-HTTP endpoints (e.g. cluster-internal
    # Garage at http://...:3900) aren't rejected by reqwest with
    # BadScheme. `virtual_hosted_style_request=False` because Garage and
    # most non-AWS S3 servers only support path-style addressing.
    store = S3Store(
        bucket=bucket,
        endpoint=endpoint,
        region=region,
        allow_http=True,
        virtual_hosted_style_request=False,
    )

    bundles = sorted(p for p in EXAMPLES_DIR.iterdir() if (p / "_build" / "manifest.json").is_file())
    if not bundles:
        sys.stderr.write(f"no bundles with manifest.json under {EXAMPLES_DIR}\n")
        return 2

    failed: list[str] = []
    for doc_dir in bundles:
        doc_id = doc_dir.name
        bundle = doc_dir / "_build"
        n = 0
        try:
            for fp in sorted(bundle.rglob("*")):
                if not fp.is_file():
                    continue
                rel = fp.relative_to(bundle).as_posix()
                # Examples are deployment-wide shared content; upload
                # under the `shared/` scope prefix that paradoc-serve's
                # DocStore expects.
                key = "/".join(p for p in [prefix, "shared", doc_id, rel] if p)
                with open(fp, "rb") as fh:
                    obstore.put(store, key, fh)
                n += 1
            print(f"[ok] {doc_id}: {n} files uploaded under {prefix or '(root)'}/shared/{doc_id}")
        except Exception as exc:
            failed.append(doc_id)
            sys.stderr.write(f"[fail] {doc_id}: {exc!r}\n")

    if failed:
        sys.stderr.write(f"\n{len(failed)} doc(s) failed to upload.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
