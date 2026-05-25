"""High-level `build_document` — the single entry point for `paradoc build`.

Ties phases 1-7 together:

  load paradoc.toml ->
  discover tasks ->
  run the DAG (with cache + executor per config) ->
  hand the runner to OneDoc ->
  OneDoc.compile() — discovers filters.py, binds TaskHandles to the
    runner, renders markdown.

Users typically don't call this directly; `paradoc build <doc_id>`
delegates here. But it's importable for programmatic use (notebooks,
custom CI scripts) so the OneDoc layer is never strictly required at
the call site.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from .build_hooks import load_build_hooks
from .cache import TaskCache
from .config import build_executor_from_config, load_task_config
from .discovery import discover_tasks
from .filter_binding import bind_filter_handles
from .registry import TaskRegistry, reset_default_registry
from .runner import Runner

logger = logging.getLogger(__name__)


def build_document(
    doc_root: Path,
    *,
    profile: str = "default",
    output_name: Optional[str] = None,
    no_cache: bool = False,
    cache_dir: Optional[Path] = None,
    work_dir: Optional[Path] = None,
    auto_open: bool = False,
    export_format: Any = None,
    compile: bool = True,
    runner_hooks: Optional[dict] = None,
):
    """Run the task DAG and compile the document.

    Args
    ----
    doc_root : Path
        Directory containing `paradoc.toml`, `tasks.py`, `filters.py`,
        and the document's markdown.
    profile : str
        Build profile from `[build.<profile>]` in paradoc.toml.
    output_name : str | None
        Output file stem. Defaults to `doc_root.name`.
    no_cache : bool
        Skip the on-disk task cache entirely.
    cache_dir : Path | None
        Override the default cache location (`<doc_root>/.paradoc-cache`).
    work_dir : Path | None
        OneDoc work dir. Defaults to `temp/<doc_root.name>` per OneDoc.
    auto_open : bool
        Open the rendered document after compile.
    export_format : ExportFormats | str | None
        DOCX / PDF / etc. None defaults to OneDoc's default.
    compile : bool
        When False, skip OneDoc.compile() — just run + bind. Useful when
        the caller wants the Runner result for further processing.
    runner_hooks : dict | None
        Optional callbacks for testing or instrumentation. Currently
        only `"after_expand"`: `Callable[[Runner], None]`, called before
        execution starts.

    Returns
    -------
    tuple[Runner, OneDoc | None]
        The Runner (so callers can `runner.cells_for(...)` after the
        fact) and the OneDoc (None if `compile=False`).
    """
    doc_root = Path(doc_root).resolve()
    if not doc_root.is_dir():
        raise FileNotFoundError(f"document directory not found: {doc_root}")

    reset_default_registry()  # idempotent across repeated invocations

    config = load_task_config(doc_root / "paradoc.toml", profile=profile)

    registry = TaskRegistry()
    discover_tasks(doc_root=doc_root, registry=registry)
    if not registry.all_tasks():
        raise RuntimeError(
            f"no tasks discovered under {doc_root}; expected `tasks.py` "
            f"or `[tasks] modules = [...]` in paradoc.toml."
        )

    cache: Optional[TaskCache] = None
    if not no_cache:
        cache = TaskCache(cache_dir or (doc_root / ".paradoc-cache"))

    executor = build_executor_from_config(config)
    runner = Runner(
        registry,
        executor=executor,
        cache=cache,
        fanout_overrides=config.fanout_overrides,
    )

    try:
        runner.expand()
        if runner_hooks and "after_expand" in runner_hooks:
            runner_hooks["after_expand"](runner)

        runner.run()

        if not compile:
            return runner, None

        # Lazy import — keep paradoc.tasks importable without pulling in
        # the heavy OneDoc compile path (pandoc, docx, db, ...).
        from paradoc.document import OneDoc
        from paradoc.filters import discover_filters

        # source_dir defaults to doc_root, but paradoc.toml can override
        # for layouts where markdown lives in a subdir (eg
        # `verification/report/`) while tasks.py / filters.py /
        # build_hooks.py stay at the doc root.
        source_dir = config.source_dir or doc_root

        one = OneDoc(source_dir=source_dir, work_dir=work_dir, runner=runner)

        # Pre-register filters from doc_root (not source_dir) so the
        # convention `<doc_root>/filters.py` works even when markdown
        # lives elsewhere. Setting `_filters_discovered=True` short-
        # circuits OneDoc's lazy lookup against `source_dir/filters.py`
        # which would otherwise re-fire and either find nothing or
        # collide on duplicate names.
        discover_filters(doc_root=doc_root, registry=one._filter_registry)
        bind_filter_handles(one._filter_registry, runner)
        one._filters_discovered = True

        # Load optional build hooks at `<doc_root>/build_hooks.py`.
        # `setup(one, runner)` runs before compile (asset baking,
        # db_manager registration); `postcompile(one)` runs after.
        hooks = load_build_hooks(doc_root)
        if hooks.setup is not None:
            hooks.setup(one, runner)

        name = output_name or doc_root.name

        # Resolve output formats:
        # 1. Explicit `export_format=` from the caller wins.
        # 2. Else use `[build.<profile>] outputs = [...]` from paradoc.toml.
        # 3. Else fall through to OneDoc.compile()'s default (DOCX).
        if export_format is not None:
            formats: list[Any] = [export_format]
        elif config.outputs:
            formats = list(config.outputs)
        else:
            formats = [None]

        for fmt in formats:
            compile_kwargs: dict[str, Any] = {"auto_open": auto_open}
            if fmt is not None:
                compile_kwargs["export_format"] = fmt
            one.compile(name, **compile_kwargs)

        if hooks.postcompile is not None:
            hooks.postcompile(one)

        return runner, one
    finally:
        # Caller may want to inspect runner.cells_for(...) post-build,
        # so we don't shut down the executor here. The CLI does it in
        # its `finally`.
        pass
