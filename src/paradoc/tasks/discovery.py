"""Load `@task`-decorated callables from a project's `tasks.py` (or override).

Discovery convention (Q6 of the design discussion):

- If `paradoc.toml` has `[tasks] modules = ["pkg.module", ...]` we import
  each in order.
- Otherwise, if `<doc_root>/tasks.py` exists, we import it via a path
  loader (no requirement that it sit on `sys.path`).

After import, every module-level `TaskFn` instance is collected. `@task`
decoration already registers tasks on the default registry as a side
effect of import; this loader just ensures the import happens and then
validates parent references + cycles.

The shape mirrors `paradoc.filters.discovery.discover_filters` so authors
who already know the filter conventions can transfer the pattern.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from .models import TaskFn
from .registry import TaskRegistry, get_default_registry


def discover_tasks(
    *,
    doc_root: Path,
    registry: TaskRegistry | None = None,
    explicit_modules: list[str] | None = None,
) -> TaskRegistry:
    """Load task modules into a registry and validate the resulting DAG.

    If `registry` is None, the default module-level registry is used. The
    return value is the registry that was populated, for caller
    convenience.
    """
    target = registry if registry is not None else get_default_registry()

    if explicit_modules:
        for mod_name in explicit_modules:
            module = importlib.import_module(mod_name)
            _collect_module_tasks(module, target)
    else:
        tasks_py = doc_root / "tasks.py"
        if tasks_py.exists():
            module = _load_path_module(tasks_py, name=f"_paradoc_tasks_{doc_root.name}")
            _collect_module_tasks(module, target)

    target.validate()
    return target


def _load_path_module(path: Path, *, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load task module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _collect_module_tasks(module, registry: TaskRegistry) -> None:
    """Idempotent: tasks already register themselves via @task; this is
    defensive against modules that build TaskFn instances by hand.

    Module-level names starting with `_` are skipped to match the filter
    discovery convention.
    """
    for attr_name, value in vars(module).items():
        if attr_name.startswith("_"):
            continue
        if isinstance(value, TaskFn):
            # Already-registered tasks are a no-op via TaskRegistry.register's
            # identity check; tasks built outside @task get folded in here.
            try:
                registry.register(value)
            except ValueError:
                # Duplicate of an existing entry — fine; @task decoration
                # registered it first.
                pass
