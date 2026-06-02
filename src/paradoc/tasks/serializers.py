"""Per-task result serializers — the dispatch boundary for cache I/O.

Pickle is fine until your task returns hundreds of MB of object graph
(adapy's `mesh` over a million-node structural FEM, for example). At
that point the right shape is a domain-specific binary format —
parquet for tabular node/element data, npz for connectivity, a small
pickle for the rest. The `Serializer` Protocol is the seam that lets a
task author swap pickle for that shape without touching the cache or
runner code.

Usage:

    from paradoc.tasks import task, Serializer, PickleSerializer

    class NumpyFEMSerializer:
        # Implements Serializer Protocol; see PickleSerializer for the
        # shape. Splits an Assembly into parquet (nodes) + npz
        # (connectivity) + pickle (the rest). Implementation lives in
        # an adapy-side module that imports paradoc.tasks.
        extension = "fem"
        def dump(self, obj, path): ...
        def load(self, path): ...

    @task(serializer=NumpyFEMSerializer())
    def mesh(a, *, geom_repr):
        ...

The TaskFn carries the serializer through to the Runner, which threads
it into TaskCache.has / get / put. Tasks without an explicit serializer
inherit the cache's default (PickleSerializer).

Stored file naming: `<hex_key>.<serializer.extension>`. A task that
switches serializers gets a fresh cache miss (the old extension's file
remains as orphaned data until manually cleared) — this avoids
silently loading a wrong-format payload after a serializer change.
"""

from __future__ import annotations

import contextlib
import pickle
import sys
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Serializer(Protocol):
    """Serialize / deserialize a single cell's result to / from disk."""

    extension: str
    """File extension (no leading dot) for the on-disk payload. Used by
    `TaskCache` to compose the per-cell file name. Two serializers with
    the same extension on the same task would race; pick distinct
    extensions if you ship more than one."""

    def dump(self, obj: Any, path: Path) -> None:
        """Write `obj` to `path`. Caller ensures the parent dir exists.
        Implementations should be atomic (write-then-rename pattern)
        when the format permits — partial files on a crash break
        future reads."""

    def load(self, path: Path) -> Any:
        """Read and return the object at `path`. Raises whatever the
        format raises on truncation / format mismatch — callers treat
        any exception here as a cache miss + re-execute."""


class PickleSerializer:
    """The v0 default: pickle.HIGHEST_PROTOCOL with a recursion bump.

    Large object graphs (eg adapy meshes with cyclic Node/Elem refs)
    blow past Python's default 1000-frame recursion limit during the
    recursive __reduce__ traversal. We bump `sys.recursionlimit` for
    the duration of the dump/load round-trip and restore on exit;
    nothing else in the process sees the elevated limit.

    50_000 is well above any plausible FEM mesh today, and the limit
    is restored on exit so it's not a global mutation. If a future
    graph blows past 50k, switch to a domain-specific serializer
    rather than bumping further — that's the cliff this Protocol
    exists to climb.
    """

    extension: str = "pkl"

    def __init__(self, recursion_limit: int = 50_000) -> None:
        self.recursion_limit = recursion_limit

    def dump(self, obj: Any, path: Path) -> None:
        # Atomic publish via write-then-rename so a crash mid-write
        # doesn't leave a half-pickled file at the destination key.
        tmp = path.with_suffix(path.suffix + ".tmp")
        with _bumped_recursion_limit(self.recursion_limit):
            with tmp.open("wb") as fh:
                pickle.dump(obj, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)

    def load(self, path: Path) -> Any:
        with _bumped_recursion_limit(self.recursion_limit):
            with path.open("rb") as fh:
                return pickle.load(fh)


@contextlib.contextmanager
def _bumped_recursion_limit(target: int):
    """Bump sys.recursionlimit for the duration of a pickle round-trip.

    Confined to the with-block so nothing else in the process sees
    the elevated limit. Used by PickleSerializer; available as a
    helper for custom serializers built on pickle.
    """
    old = sys.getrecursionlimit()
    if target > old:
        sys.setrecursionlimit(target)
    try:
        yield
    finally:
        sys.setrecursionlimit(old)
