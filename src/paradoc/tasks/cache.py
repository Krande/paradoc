"""On-disk cache + cache key construction for paradoc.tasks.

Layout:

    <cache_dir>/
      <task_qualname>/
        <hex_key>.pkl     # pickled cell result
        <hex_key>.meta    # JSON sidecar (kwargs, version_probe, parent_key)

The hex_key is sha256(qualname + ast_source_hash + canonical_kwargs +
version_probe + parent_key + depends_on_hashes).

Why parent_key recursively: a cell's identity isn't just "this task with
these kwargs"; it's "this task with these kwargs, fed the result of *that
specific* upstream cell." If `design` changes, every downstream `mesh`
and `analyze` cell must invalidate. Folding the parent's cache key into
the child's hash propagates invalidation through the DAG for free.

What's deliberately deferred (per Q4 hard cuts):

- Eviction. Users run `rm -rf .paradoc-cache` to reset.
- Cross-machine cache sharing. Local only; the directory is .gitignore'd.
- Result-schema versioning. If a result class drops a field, the
  pickled object may deserialize wrong. Mitigation is a follow-up.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import TaskFn
from .source_hash import ast_source_hash

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheKey:
    """Hashable record of everything that contributes to a cell's identity.

    Frozen so callers can stick keys in sets / use as dict keys when
    inspecting the cache state.
    """

    qualname: str
    digest: bytes

    @property
    def hex(self) -> str:
        return self.digest.hex()

    def __repr__(self) -> str:
        return f"CacheKey({self.qualname} {self.hex[:12]}...)"


def compute_cache_key(
    task: TaskFn,
    kwargs: dict[str, Any],
    *,
    parent_key: Optional[CacheKey] = None,
    ast_hash_memo: Optional[dict[int, bytes]] = None,
) -> CacheKey:
    """Construct a stable cache key for a single cell.

    `ast_hash_memo` is an optional dict the runner passes in to avoid
    re-hashing the same TaskFn across many fanout cells. The per-task
    cost dominates total cache-key construction.
    """
    h = hashlib.sha256()
    h.update(task.qualname.encode())

    if ast_hash_memo is not None and id(task) in ast_hash_memo:
        h.update(ast_hash_memo[id(task)])
    else:
        ast_h = ast_source_hash(task)
        if ast_hash_memo is not None:
            ast_hash_memo[id(task)] = ast_h
        h.update(ast_h)

    h.update(_canonical_kwargs(kwargs))

    if task.version_probe is not None:
        try:
            v = task.version_probe(kwargs)
        except Exception as exc:  # noqa: BLE001 — version probes shouldn't kill the build
            logger.warning(f"version_probe for {task.qualname} raised {exc!r}; folding exc class instead")
            v = type(exc).__name__
        h.update(str(v).encode())

    for dep in task.depends_on:
        h.update(ast_source_hash(dep))

    if parent_key is not None:
        h.update(parent_key.digest)

    return CacheKey(qualname=task.qualname, digest=h.digest())


def _canonical_kwargs(kwargs: dict[str, Any]) -> bytes:
    """Stable byte encoding of fanout kwargs.

    JSON with sort_keys=True for the common case of primitives + lists.
    Non-JSON values (callables, custom objects) fall back to repr() with
    a sorted-tuple wrapper. Not collision-resistant, but stable across
    runs of the same Python interpreter.
    """
    try:
        return json.dumps(kwargs, sort_keys=True, default=str).encode()
    except TypeError:
        return repr(sorted(kwargs.items())).encode()


@dataclass
class CacheEntry:
    """In-memory representation of one cached cell result."""

    key: CacheKey
    result: Any
    meta: dict[str, Any] = field(default_factory=dict)


class TaskCache:
    """On-disk pickle cache, keyed by `<qualname>/<hex_digest>`."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _pkl_path(self, key: CacheKey) -> Path:
        return self.cache_dir / key.qualname / f"{key.hex}.pkl"

    def _meta_path(self, key: CacheKey) -> Path:
        return self.cache_dir / key.qualname / f"{key.hex}.meta"

    def has(self, key: CacheKey) -> bool:
        return self._pkl_path(key).exists()

    def get(self, key: CacheKey) -> Any:
        """Load a cached result. Raises FileNotFoundError on miss."""
        path = self._pkl_path(key)
        with path.open("rb") as fh:
            return pickle.load(fh)

    def put(
        self,
        key: CacheKey,
        result: Any,
        *,
        kwargs: Optional[dict[str, Any]] = None,
        parent_key: Optional[CacheKey] = None,
        version_probe: Optional[str] = None,
    ) -> None:
        """Write a result + sidecar metadata atomically (write-then-rename)."""
        task_dir = self.cache_dir / key.qualname
        task_dir.mkdir(parents=True, exist_ok=True)

        pkl = self._pkl_path(key)
        meta = self._meta_path(key)

        tmp_pkl = pkl.with_suffix(".pkl.tmp")
        tmp_meta = meta.with_suffix(".meta.tmp")

        with tmp_pkl.open("wb") as fh:
            pickle.dump(result, fh, protocol=pickle.HIGHEST_PROTOCOL)
        meta_doc = {
            "qualname": key.qualname,
            "hex": key.hex,
            "kwargs": _meta_safe(kwargs or {}),
            "parent_hex": parent_key.hex if parent_key else None,
            "version_probe": version_probe,
            "timestamp": time.time(),
        }
        with tmp_meta.open("w") as fh:
            json.dump(meta_doc, fh, indent=2, default=str)

        # Atomic publish — readers never see a half-written .pkl.
        tmp_pkl.replace(pkl)
        tmp_meta.replace(meta)

    def clear(self) -> None:
        """Wipe the entire cache directory. Mostly for tests."""
        if not self.cache_dir.exists():
            return
        for child in self.cache_dir.rglob("*"):
            if child.is_file():
                child.unlink()
        for child in sorted(self.cache_dir.rglob("*"), reverse=True):
            if child.is_dir():
                child.rmdir()


def _meta_safe(d: dict[str, Any]) -> dict[str, Any]:
    """Coerce metadata to JSON-serializable form for the .meta sidecar."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        try:
            json.dumps(v)
            out[k] = v
        except TypeError:
            out[k] = repr(v)
    return out
