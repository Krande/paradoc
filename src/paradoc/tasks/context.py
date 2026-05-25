"""BuildContext — a typed handle to the surrounding build's filesystem layout.

Tasks that need to know *where* the build is happening (doc_root,
cache_dir, work_dir, assets_dir) take a `ctx: BuildContext` parameter.
The runner inspects each task's signature; when it sees that annotation,
it passes the runner's current context object as a keyword argument at
call time. The context value is *not* mixed into `cell.kwargs`, so it
doesn't participate in cache-key computation — two builds of the same
doc in different paths still share cache entries.

Why a typed annotation rather than a registry lookup or a thread-local:
the dependency is visible at the call site, easy to test (`build(ctx=...)`
passes through), and survives pickle-marshaling to the subprocess
executor because BuildContext is a plain dataclass.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class BuildContext:
    """Filesystem layout of the build that's currently running.

    Constructed by the Runner and injected into any task body whose
    signature has a parameter annotated `BuildContext`. All fields are
    absolute paths when populated; `None` means "not configured" (eg
    cache_dir is None when the runner was started with `no_cache=True`).
    """

    doc_root: Path
    cache_dir: Optional[Path] = None
    work_dir: Optional[Path] = None
    assets_dir: Optional[Path] = None


def ctx_param_name(fn: Callable[..., Any]) -> Optional[str]:
    """Return the name of the parameter annotated `BuildContext`, or None.

    Walks `fn`'s signature; if any parameter's annotation resolves to the
    BuildContext class, returns its name. String forward references like
    `"BuildContext"` are matched by suffix so `from __future__ import
    annotations` modules also work without an eval.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    for name, p in sig.parameters.items():
        ann = p.annotation
        if ann is BuildContext:
            return name
        if isinstance(ann, str) and (ann == "BuildContext" or ann.endswith(".BuildContext")):
            return name
    return None
