"""Upload compiled example bundles to the configured object store.

Reads ``dist/examples/<doc_id>/_build/`` (the output of ``compile-examples``)
and pushes each file to ``<S3_PREFIX>/<doc_id>/<rel-path>`` in the bucket
identified by env. Everything that pinpoints a specific cluster lives in
env vars, never in this source tree.

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
    region = os.environ.get("AWS_REGION", "us-east-1")
    prefix = os.environ.get("S3_PREFIX", "").strip("/")

    store = S3Store(bucket=bucket, endpoint=endpoint, region=region)

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
                key = "/".join(p for p in [prefix, doc_id, rel] if p)
                with open(fp, "rb") as fh:
                    obstore.put(store, key, fh)
                n += 1
            print(f"[ok] {doc_id}: {n} files uploaded under {prefix or '(root)'}/{doc_id}")
        except Exception as exc:
            failed.append(doc_id)
            sys.stderr.write(f"[fail] {doc_id}: {exc!r}\n")

    if failed:
        sys.stderr.write(f"\n{len(failed)} doc(s) failed to upload.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
