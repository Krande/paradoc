"""Auto-discovered hooks at `<doc_root>/build_hooks.py`.

The orchestrator (`build_document`) calls `setup(one, runner)` between
OneDoc construction and `one.compile()`, and `postcompile(one)` after
compile finishes. Both are optional; a missing function (or missing
file) is a no-op.

Use cases:

- **setup**: bake derived assets (DataFrames -> `one.db_manager.add_table`,
  plotly figures -> `add_plot`, GLBs -> `add_three_d`) so the markdown
  resolver finds them when filter `@attr` returns a `TableView` /
  `FigureView` / `ThreeDView` referencing the corresponding key. Without
  this, filters whose attrs return `TableView(table_key=...)` resolve
  against an empty db_manager.
- **postcompile**: export the bundle to a custom directory, push to a
  remote, mint a Sphinx landing-page wrapper, etc. The legacy verification
  driver does this via `one.export_static(...)`.

Discovery convention (mirrors `tasks.py` / `filters.py` from Q6 of the
design discussion):

    <doc_root>/build_hooks.py
        def setup(one, runner) -> None: ...
        def postcompile(one) -> None: ...

Both functions are optional; the orchestrator no-ops on absence.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Public type aliases for clarity in type annotations downstream.
SetupHook = Callable[[Any, Any], None]  # (OneDoc, Runner) -> None
PostcompileHook = Callable[[Any], None]  # (OneDoc,) -> None


@dataclass
class BuildHooks:
    """Container for the two optional hook callables."""

    setup: Optional[SetupHook] = None
    postcompile: Optional[PostcompileHook] = None

    @property
    def empty(self) -> bool:
        return self.setup is None and self.postcompile is None


def load_build_hooks(doc_root: Path) -> BuildHooks:
    """Load `<doc_root>/build_hooks.py` if present; return its hook callables.

    Either function may be omitted; the returned BuildHooks has None for
    missing ones. A missing file returns an empty BuildHooks.
    """
    hooks_py = doc_root / "build_hooks.py"
    if not hooks_py.exists():
        return BuildHooks()

    name = f"_paradoc_build_hooks_{doc_root.name}"
    spec = importlib.util.spec_from_file_location(name, hooks_py)
    if spec is None or spec.loader is None:
        logger.warning(f"could not load build hooks from {hooks_py}")
        return BuildHooks()

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    return BuildHooks(
        setup=getattr(module, "setup", None),
        postcompile=getattr(module, "postcompile", None),
    )
