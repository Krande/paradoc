"""Top-level `paradoc` CLI.

Kept deliberately lean at module level — every heavy import (pandoc,
docx, plotly, pandas via OneDoc; FastAPI via the publish/serve path)
is deferred inside the leaf command's submodule. `paradoc --help`
should cost <50 ms cold.

Each subcommand lives in its own `paradoc.cli.<name>` or
`paradoc.tasks.cli` module; this file only wires them onto the Typer
app. Adding a new subcommand: write the submodule, import its
function or sub-app here, register with `app.command(...)` or
`app.add_typer(...)`.
"""

from __future__ import annotations

import typer

from paradoc.cli.compile import app as legacy_compile_app
from paradoc.cli.publish import app as publish_app
from paradoc.tasks.cli import build as build_command
from paradoc.tasks.cli import dev as dev_command

app = typer.Typer()

# `paradoc publish <doc_dir>` — compile and upload a bundle to a
# running paradoc-serve. publish.py itself is lean (stdlib + typer);
# the heavy compile path stays deferred inside `paradoc.cli.compile`.
app.add_typer(publish_app, name="publish")

# `paradoc build <doc_id>` — run the document's task DAG. Flat
# command, not a Typer group, so the surface is `paradoc build <id>`
# rather than `paradoc build build <id>`.
app.command("build")(build_command)

# `paradoc dev <doc_id>` — build + serve + watch + live-reload.
# Local dev loop: HTTP server over the static bundle, WebSocket
# channel that fires `reload` on every successful rebuild.
app.command("dev")(dev_command)

# `paradoc paradoc <src_dir> <name>` — legacy pre-task-runner shape.
# Kept for backwards compat; new code should use `paradoc build`.
app.add_typer(legacy_compile_app, name="paradoc")


if __name__ == "__main__":
    app()
