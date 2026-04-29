"""Compile a curated set of example docs into bundle dirs.

Output layout::

    dist/examples/<doc_id>/_build/manifest.json
    dist/examples/<doc_id>/_build/...

Run via ``pixi run compile-examples [doc1 doc2 ...]``. With no args, falls
back to ``DEFAULT_DOCS`` below — a small set chosen because they don't
need pre-generated images / external DB inputs that would only exist
locally.

Used by ``upload-examples`` (to push to the configured object store) and
by developers who want to inspect a freshly-compiled bundle without
deploying anything.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import paradoc as pa

REPO_ROOT = Path(__file__).resolve().parent.parent
FILES_DIR = REPO_ROOT / "files"
OUT_ROOT = REPO_ROOT / "dist" / "examples"

# Curated "always-buildable" set. Skipped docs that depend on assets the
# build pipeline doesn't provide (e.g. pre-rendered PNGs, an external DB).
DEFAULT_DOCS = [
    "doc_math",
    "doc_bullet_points",
    "doc_regular_table",
    "doc_table",
]


def compile_doc(doc_id: str, *, clean: bool) -> Path:
    src = FILES_DIR / doc_id
    if not src.is_dir():
        raise FileNotFoundError(f"example not found: {src}")
    work = OUT_ROOT / doc_id
    if clean and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    od = pa.OneDoc(src, work_dir=work)
    od.compile(doc_id, export_format="html")

    bundle = work / "_build"
    if not (bundle / "manifest.json").exists():
        raise RuntimeError(f"compile produced no manifest at {bundle}")
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "docs",
        nargs="*",
        default=None,
        help="Doc dir names under files/. Defaults to a curated set.",
    )
    parser.add_argument(
        "--no-clean",
        dest="clean",
        action="store_false",
        help="Don't wipe the per-doc work dir before compiling (keeps incremental state).",
    )
    args = parser.parse_args(argv)

    docs = args.docs or DEFAULT_DOCS
    failed: list[tuple[str, str]] = []
    for doc_id in docs:
        try:
            bundle = compile_doc(doc_id, clean=args.clean)
            n_files = sum(1 for _ in bundle.rglob("*") if _.is_file())
            print(f"[ok]   {doc_id}: {n_files} files in {bundle.relative_to(REPO_ROOT)}")
        except Exception as exc:
            failed.append((doc_id, repr(exc)))
            print(f"[fail] {doc_id}: {exc!r}", file=sys.stderr)

    if failed:
        print(f"\n{len(failed)} doc(s) failed to compile.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
