"""`paradoc build <doc_id>` — run a document's task DAG.

Wires phases 1-5 together (decorator, registry, runner, cache, pixi
executor, paradoc.toml schema) behind a single CLI command. The full
`OneDoc.compile()` pipeline plugs in later via the filter integration
phase — for now `paradoc build` exercises the task tree and reports
what ran; the markdown resolver still uses the legacy compile path.

Usage:

    paradoc build verification
    paradoc build verification --profile smoke
    paradoc build verification --inspect          # list cells, don't run
    paradoc build verification --no-cache
    paradoc build verification --cache-dir /tmp/cache

Convention: `<doc_id>` resolves to `./<doc_id>/` containing
`paradoc.toml` and `tasks.py`. Pass an absolute or relative path
instead of a bare id for non-conventional layouts.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from .cache import TaskCache
from .config import build_executor_from_config, load_task_config
from .discovery import discover_tasks
from .filter_binding import bind_filter_handles
from .registry import TaskRegistry, reset_default_registry
from .runner import Runner

app = typer.Typer(add_completion=False, help="Run a document's task DAG.")

logger = logging.getLogger(__name__)


@app.command()
def build(
    doc_id: str = typer.Argument(..., help="Document directory or id (eg 'verification')."),
    profile: str = typer.Option("default", "--profile", "-p", help="Build profile from paradoc.toml."),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable the on-disk cache for this run."),
    cache_dir: Optional[Path] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory (default: <doc_dir>/.paradoc-cache).",
    ),
    inspect: bool = typer.Option(
        False,
        "--inspect",
        help="Print task DAG + cell counts without executing.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    bind_filters: bool = typer.Option(
        False,
        "--bind-filters",
        help="After the DAG runs, discover filters.py and bind any TaskHandles.",
    ),
) -> None:
    """Execute the task DAG for `<doc_id>`."""
    _configure_logging(verbose)

    doc_root = _resolve_doc_root(doc_id)
    config = load_task_config(doc_root / "paradoc.toml", profile=profile)
    typer.echo(f"doc_root: {doc_root}")
    typer.echo(f"profile:  {profile}")
    if config.pixi_toml is not None:
        typer.echo(f"pixi:     {config.pixi_toml}")
    typer.echo(f"envs:     {config.envs or '(none — in-process only)'}")

    # @task decoration writes to the module-level default registry as a
    # side effect. A second `paradoc build` invocation (eg the test
    # suite, or a long-running paradoc-serve process) would re-import
    # the doc's tasks.py and collide with stale entries. Clearing first
    # makes the CLI invocation idempotent.
    reset_default_registry()

    registry = TaskRegistry()
    discover_tasks(doc_root=doc_root, registry=registry)
    if not registry.all_tasks():
        typer.secho(
            f"no tasks discovered. expected `{doc_root / 'tasks.py'}` or "
            f"`[tasks] modules = [...]` in paradoc.toml.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    cache: Optional[TaskCache] = None
    if not no_cache:
        cache_dir_resolved = cache_dir or (doc_root / ".paradoc-cache")
        cache = TaskCache(cache_dir_resolved)
        typer.echo(f"cache:    {cache_dir_resolved}")

    executor = build_executor_from_config(config)
    runner = Runner(
        registry,
        executor=executor,
        cache=cache,
        fanout_overrides=config.fanout_overrides,
    )

    try:
        runner.expand()
        _print_dag(runner)

        if inspect:
            typer.secho("(--inspect: skipping execution)", fg=typer.colors.CYAN)
            return

        results = runner.run()
        _print_run_summary(runner, results)

        if bind_filters:
            _bind_filters(doc_root, runner)
    finally:
        runner.shutdown()


def _bind_filters(doc_root: Path, runner: Runner) -> None:
    """Discover this doc's filters.py and bind TaskHandles to the runner.

    Imported lazily so the build command stays usable when paradoc.filters
    pulls in heavy dependencies that aren't needed for a pure task run.
    """
    from paradoc.filters import FilterRegistry, discover_filters

    filter_registry = FilterRegistry()
    discover_filters(doc_root=doc_root, registry=filter_registry)
    if not filter_registry.known_names():
        typer.secho("no filters discovered; nothing to bind.", fg=typer.colors.YELLOW)
        return

    bound = bind_filter_handles(filter_registry, runner)
    typer.echo(f"bound {bound} TaskHandle{'s' if bound != 1 else ''} to runner")


def _resolve_doc_root(doc_id: str) -> Path:
    candidate = Path(doc_id)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()
    if not candidate.is_dir():
        typer.secho(f"document directory not found: {candidate}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    return candidate


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)


def _print_dag(runner: Runner) -> None:
    """One line per task with cell count. Indented by depth."""
    by_parent: dict[Optional[str], list[str]] = {}
    for task in runner.registry.all_tasks():
        parent = runner.registry.resolve_parent(task)
        by_parent.setdefault(parent.qualname if parent else None, []).append(task.qualname)

    typer.echo("\ntask DAG:")
    _print_dag_recurse(runner, by_parent, None, depth=0)


def _print_dag_recurse(
    runner: Runner,
    by_parent: dict[Optional[str], list[str]],
    parent_qn: Optional[str],
    *,
    depth: int,
) -> None:
    for qn in sorted(by_parent.get(parent_qn, [])):
        cell_count = len(runner.cells_for(qn))
        prefix = "  " * depth + ("└─ " if depth > 0 else "")
        typer.echo(f"  {prefix}{qn}  ({cell_count} cell{'s' if cell_count != 1 else ''})")
        _print_dag_recurse(runner, by_parent, qn, depth=depth + 1)


def _print_run_summary(runner: Runner, results: dict) -> None:
    total_cells = sum(len(v) for v in results.values())
    typer.echo("")
    typer.secho(
        f"ran {total_cells} cell{'s' if total_cells != 1 else ''} across "
        f"{len(results)} task{'s' if len(results) != 1 else ''}",
        fg=typer.colors.GREEN,
    )
    if runner.cache is not None:
        typer.echo(
            f"cache: {runner.cache_hits} hit{'s' if runner.cache_hits != 1 else ''}, "
            f"{runner.cache_misses} miss{'es' if runner.cache_misses != 1 else ''}"
        )


if __name__ == "__main__":  # pragma: no cover
    app()
