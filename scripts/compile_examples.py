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
from typing import Callable

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
    # Auto-discovered data.db (already populated, checked into the repo).
    "doc_lorum",
    "doc_table_db",
    # NB: doc_figure_sources is intentionally NOT in this list — it
    # needs ada-py at compile time for STEP→GLB rendering, which would
    # bloat the lightweight `examples` env. It's compiled separately
    # via the `examples-figs` env (see pixi.toml). The CI workflow
    # invokes both passes and they share dist/examples/ so the uploader
    # picks them up together.
]


def _setup_doc_table(od: "pa.OneDoc") -> None:
    """`files/doc_table/` references {{__my_table__}} … {{__my_table_5__}};
    register sample tables so the substitution actually fires. Mirrors the
    pytest fixture in tests/tables/test_tables.py."""
    import pandas as pd

    from paradoc.common import TableFormat

    df = pd.DataFrame([(0, 0), (1, 2)], columns=["a", "b"])
    od.add_table("my_table", df, "A basic table")
    od.add_table("my_table_2", df, "A slightly smaller table", TableFormat(font_size=8))
    od.add_table("my_table_3", df, "No Space 1")
    od.add_table("my_table_4", df, "No Space 2")
    od.add_table("my_table_5", df, "No Space 3")


def _setup_doc_table_db(od: "pa.OneDoc") -> None:
    """`files/doc_table_db/data.db` ships my_table + my_table_3, but the
    appendix markdown references my_table_2/4/5 which were never baked.
    Register the missing three in-memory so the example renders end-to-
    end. The db-backed pair still exercises the auto-discovery path."""
    import pandas as pd

    df = pd.DataFrame([(0, 0), (1, 2)], columns=["a", "b"])
    od.add_table("my_table_2", df, "Appendix table 2")
    od.add_table("my_table_4", df, "Appendix table 4")
    od.add_table("my_table_5", df, "Appendix table 5")


def _setup_doc_figure_sources(od: "pa.OneDoc") -> None:
    """`files/doc_figure_sources/` references:

    * ``${ demo_table }`` and the legacy ``{{__demo_table__}}`` alias —
      the same db-backed table seen via both syntaxes.
    * ``${ eig_main.frequency_table }`` — a filter attribute that returns
      ``TableView(table_key="eigen_freqs")``, so we need an
      ``eigen_freqs`` row to exist when the legacy substituter runs.

    Plus a STEP file (already in the repo at ``files/doc_figure_sources/
    files/cad.stp``) which adapy renders to glb + PNG at compile time.
    """
    import pandas as pd

    from paradoc.db import dataframe_to_table_data

    # demo_table — referenced from source_table.md (both new & legacy).
    od.db_manager.add_table(
        dataframe_to_table_data(
            "demo_table",
            pd.DataFrame(
                [(i, i**2, f"row_{i}") for i in range(5)],
                columns=["index", "squared", "label"],
            ),
            "Demonstration table",
        )
    )

    # eigen_freqs — referenced indirectly via the EigenResultsDemo filter.
    od.db_manager.add_table(
        dataframe_to_table_data(
            "eigen_freqs",
            pd.DataFrame(
                [
                    (1, 12.345, 0.012),
                    (2, 17.890, 0.014),
                    (3, 23.117, 0.011),
                ],
                columns=["mode", "freq_hz", "damping"],
            ),
            "First three eigenmodes",
        )
    )


def _setup_doc_math(od: "pa.OneDoc") -> None:
    """`files/doc_math/` references {{__my_equation_1__}}, {{__my_equation_2__}},
    {{__results__}}, {{__results_2__}}; register equations + result tables.
    Mirrors tests/equations/test_doc_math.py."""
    from paradoc.utils import make_df

    def my_calc_example_1(a, b):
        """A calculation with doc stub"""
        V_x = a + 1 * (0.3 + a * b) ** 2
        return V_x

    def my_calc_example_2(a, b):
        """A calculation with a longer doc stub"""
        V_n = a + 1 * (0.16 + a * b) ** 2
        V_x = V_n * 0.98
        return V_x

    inputs = [(0, 0), (1, 1), (2, 1), (2, 2)]
    df1 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_1)
    df2 = make_df(inputs, ("a", "b", "V_x"), my_calc_example_2)

    od.add_equation("my_equation_1", my_calc_example_1, include_python_code=True)
    od.add_equation("my_equation_2", my_calc_example_2)
    od.add_table("results", df1, "Results from Equation my_equation")
    od.add_table("results_2", df2, "Results from Equation my_equation_2")


# Per-doc setup hooks. Examples that need build-time inputs (tables,
# plots, equations) register a callback here. Examples whose markdown is
# self-contained — doc_regular_table, doc_bullet_points — are omitted
# and compile straight through.
SETUP_HOOKS: dict[str, Callable[["pa.OneDoc"], None]] = {
    "doc_table": _setup_doc_table,
    "doc_table_db": _setup_doc_table_db,
    "doc_math": _setup_doc_math,
    "doc_figure_sources": _setup_doc_figure_sources,
}


def compile_doc(doc_id: str, *, clean: bool) -> Path:
    src = FILES_DIR / doc_id
    if not src.is_dir():
        raise FileNotFoundError(f"example not found: {src}")
    work = OUT_ROOT / doc_id
    if clean and work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    od = pa.OneDoc(src, work_dir=work)
    setup = SETUP_HOOKS.get(doc_id)
    if setup is not None:
        setup(od)
    od.compile(doc_id, export_format="html")

    bundle = work / "_build"
    if not (bundle / "manifest.json").exists():
        raise RuntimeError(f"compile produced no manifest at {bundle}")

    # Also emit the export_static layout (DocManifest + sections JSON) into
    # bundle/static/, so paradoc-serve can hand it back to the frontend's
    # REST loader. include_frontend=False — the SPA HTML+JS lives in the
    # paradoc-serve container (/app/static), not per-doc.
    static_dir = bundle / "static"
    od_static = pa.OneDoc(src, work_dir=work / "_static-work")
    if setup is not None:
        # `export_static` re-runs prep + variable substitution from a
        # fresh OneDoc, so re-register the inputs here too — otherwise
        # the static-served sections would still contain the literal
        # `{{__my_table__}}` markers.
        setup(od_static)
    od_static.export_static(static_dir, embed_images=True, include_frontend=False)
    if not (static_dir / "manifest.json").exists():
        raise RuntimeError(f"export_static produced no manifest at {static_dir}")
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
