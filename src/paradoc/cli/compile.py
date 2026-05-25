"""`paradoc paradoc <src_dir> <name>` — legacy single-shot compile.

Pre-task-runner entry point. Most callers should switch to
`paradoc build <doc_id>` instead. Kept here in its own module so the
heavy `from paradoc import OneDoc` cost is deferred until this
command is actually invoked — `paradoc --help` should cost <50 ms
cold and shouldn't load pandoc/plotly/docx for everyone.
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, help="Legacy compile command (pre-task-runner).")


@app.command("paradoc")
def main(
    source_dir: str,
    report_name: str,
    auto_open: bool = False,
    work_dir: str = "temp",
    export_format: str = "docx",
) -> None:
    """Compile a OneDoc bundle from a source directory.

    Most callers should use `paradoc build <doc_id>` instead, which
    routes through the paradoc.tasks DAG (cache, fanout, profiles).
    """
    # Lazy imports — OneDoc pulls pandoc + docx + plotly + pandas, and
    # ExportFormats lives in paradoc.common which transitively does too.
    from paradoc import OneDoc
    from paradoc.common import ExportFormats

    fmt = ExportFormats(export_format) if isinstance(export_format, str) else export_format
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile(report_name, auto_open=auto_open, export_format=fmt)
