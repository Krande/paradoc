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
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .models import TaskFn
from .serializers import PickleSerializer, Serializer
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
    upstream_keys: Optional[list[CacheKey]] = None,
    ast_hash_memo: Optional[dict[int, bytes]] = None,
) -> CacheKey:
    """Construct a stable cache key for a single cell.

    `parent_key` applies to regular (1:1 / 1:N) tasks: the parent cell's
    own cache key folds in so a parent change invalidates the child.

    `upstream_keys` applies to aggregator (`consumes=`) tasks: the list
    of every upstream cell's cache key folds in *sorted* so the order
    in which the runner iterated cells doesn't affect the digest. Any
    change to any upstream cell invalidates the aggregator.

    A cell has either `parent_key` or `upstream_keys`, never both —
    these are the two shapes of "upstream dependency" and `@task`
    validates that they're mutually exclusive at decoration time.

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

    if upstream_keys:
        # Sort by digest so cell-iteration order doesn't affect the hash.
        for uk in sorted(upstream_keys, key=lambda k: k.digest):
            h.update(uk.digest)

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
    """On-disk cache, keyed by `<qualname>/<hex_digest>.<serializer.ext>`.

    Per-cell I/O is delegated to a `Serializer` — by default a
    `PickleSerializer`. Tasks declaring `@task(serializer=...)` override
    per cell; the runner threads their serializer through `has` / `get`
    / `put` so each cell uses the right format.

    File-layout consequence: a task that switches serializers gets a
    fresh cache miss because the old extension's file doesn't match
    the new serializer's `.extension`. The orphaned old file remains
    on disk until manually cleared.
    """

    def __init__(self, cache_dir: Path, *, default_serializer: Optional[Serializer] = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_serializer: Serializer = default_serializer or PickleSerializer()

    def _payload_path(self, key: CacheKey, serializer: Serializer) -> Path:
        return self.cache_dir / key.qualname / f"{key.hex}.{serializer.extension}"

    def _meta_path(self, key: CacheKey) -> Path:
        return self.cache_dir / key.qualname / f"{key.hex}.meta"

    def has(self, key: CacheKey, *, serializer: Optional[Serializer] = None) -> bool:
        s = serializer or self.default_serializer
        return self._payload_path(key, s).exists()

    def get(self, key: CacheKey, *, serializer: Optional[Serializer] = None) -> Any:
        """Load a cached result. Raises FileNotFoundError on miss."""
        s = serializer or self.default_serializer
        return s.load(self._payload_path(key, s))

    def put(
        self,
        key: CacheKey,
        result: Any,
        *,
        kwargs: Optional[dict[str, Any]] = None,
        parent_key: Optional[CacheKey] = None,
        version_probe: Optional[str] = None,
        serializer: Optional[Serializer] = None,
    ) -> None:
        """Write a result + sidecar metadata. Serializer handles atomicity."""
        s = serializer or self.default_serializer
        task_dir = self.cache_dir / key.qualname
        task_dir.mkdir(parents=True, exist_ok=True)

        s.dump(result, self._payload_path(key, s))

        meta_doc = {
            "qualname": key.qualname,
            "hex": key.hex,
            "kwargs": _meta_safe(kwargs or {}),
            "parent_hex": parent_key.hex if parent_key else None,
            "version_probe": version_probe,
            "serializer": type(s).__name__,
            "extension": s.extension,
            "timestamp": time.time(),
        }
        meta = self._meta_path(key)
        tmp_meta = meta.with_suffix(".meta.tmp")
        with tmp_meta.open("w") as fh:
            json.dump(meta_doc, fh, indent=2, default=str)
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
