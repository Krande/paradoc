"""Load `Filter` instances from a project's `filters.py` (or override module).

Discovery convention
--------------------
- If `paradoc.toml` has `[filters] modules = ["pkg.module", ...]` we
  import each in order.
- Otherwise, if `<doc_root>/filters.py` exists, we import it via a path
  loader (no requirement that it sit on `sys.path`).

After import, every module-level `Filter` instance is registered. We do
not auto-register `Filter` *classes* — only instances. This forces the
"named instance" pattern from the plan.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from .base import Filter
from .registry import FilterRegistry


def discover_filters(
    *,
    doc_root: Path,
    registry: FilterRegistry,
    explicit_modules: list[str] | None = None,
) -> None:
    """Load filter instances from the configured modules into `registry`."""
    if explicit_modules:
        for mod_name in explicit_modules:
            module = importlib.import_module(mod_name)
            _register_module_filters(module, registry)
        return

    filters_py = doc_root / "filters.py"
    if filters_py.exists():
        module = _load_path_module(filters_py, name=f"_paradoc_filters_{doc_root.name}")
        _register_module_filters(module, registry)


def _load_path_module(path: Path, *, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load filter module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _register_module_filters(module, registry: FilterRegistry) -> None:
    for attr_name, value in vars(module).items():
        if attr_name.startswith("_"):
            continue
        if isinstance(value, Filter):
            registry.register(value)
