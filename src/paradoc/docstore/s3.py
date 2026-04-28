"""S3-backed `DocStore` via `obstore`.

Layout in S3 mirrors the local layout::

    s3://<bucket>/<doc_id>/manifest.json
    s3://<bucket>/<doc_id>/paradoc.sqlite
    s3://<bucket>/<doc_id>/assets/3d/<key>.glb
    ...

The sqlite database is downloaded to a local cache on first access for
each doc; we never run sqlite over HTTP. Glb bytes stream directly from
S3 via obstore range reads.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

from paradoc.db import DbManager
from paradoc.db.models import PlotData, TableData, ThreeDData

from .base import DocStore


class S3DocStore(DocStore):
    """Read-only DocStore over an S3 (or S3-compatible) prefix.

    Requires `obstore` to be installed. The sqlite db is downloaded to
    a local cache directory once per process per doc.
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        endpoint: Optional[str] = None,
        region: Optional[str] = None,
        db_filename: str = "paradoc.sqlite",
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.endpoint = endpoint
        self.region = region
        self.db_filename = db_filename
        self.cache_dir = Path(cache_dir or Path(tempfile.gettempdir()) / "paradoc-s3-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._store = self._build_store()
        self._db_managers: dict[str, DbManager] = {}

    @classmethod
    def from_url(cls, url: str, *, db_filename: str = "paradoc.sqlite") -> "S3DocStore":
        """Build from an `s3://bucket/prefix` URL."""
        parsed = urlparse(url)
        if parsed.scheme != "s3":
            raise ValueError(f"expected s3:// URL, got {url!r}")
        return cls(bucket=parsed.netloc, prefix=parsed.path.lstrip("/"), db_filename=db_filename)

    def _build_store(self):
        try:
            from obstore.store import S3Store  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "obstore is required for S3DocStore. Install the `serve` extra "
                "(pip install paradoc[serve])."
            ) from exc

        kwargs: dict = {"bucket": self.bucket}
        if self.region:
            kwargs["region"] = self.region
        if self.endpoint:
            kwargs["endpoint"] = self.endpoint
        return S3Store(**kwargs)

    # ---------------- key helpers ----------------

    def _doc_prefix(self, doc_id: str) -> str:
        if "/" in doc_id or doc_id.startswith(".."):
            raise PermissionError(f"doc_id {doc_id!r} is not a single path segment")
        if self.prefix:
            return f"{self.prefix}/{doc_id}"
        return doc_id

    def _key(self, doc_id: str, *path: str) -> str:
        return "/".join([self._doc_prefix(doc_id), *path])

    # ---------------- DocStore interface ----------------

    def list_doc_ids(self) -> list[str]:
        try:
            iter_ = self._store.list(prefix=self.prefix or None)
            seen: set[str] = set()
            for entry in iter_:
                key = entry["path"] if isinstance(entry, dict) else getattr(entry, "path", "")
                rel = key[len(self.prefix) :].lstrip("/") if self.prefix else key
                first = rel.split("/", 1)[0]
                if first.endswith(".json") or first.endswith(".sqlite"):
                    continue
                if first:
                    seen.add(first)
            return sorted(seen)
        except Exception:
            return []

    def _db(self, doc_id: str) -> DbManager:
        cached = self._db_managers.get(doc_id)
        if cached is not None:
            return cached
        local_db_path = self.cache_dir / doc_id / self.db_filename
        local_db_path.parent.mkdir(parents=True, exist_ok=True)
        if not local_db_path.exists():
            payload = self._store.get(self._key(doc_id, self.db_filename)).bytes()
            local_db_path.write_bytes(bytes(payload))
        manager = DbManager(local_db_path)
        self._db_managers[doc_id] = manager
        return manager

    def get_table(self, doc_id: str, key: str) -> Optional[TableData]:
        return self._db(doc_id).get_table(key)

    def get_plot(self, doc_id: str, key: str) -> Optional[PlotData]:
        return self._db(doc_id).get_plot(key)

    def get_three_d_meta(self, doc_id: str, key: str) -> Optional[ThreeDData]:
        return self._db(doc_id).get_three_d(key)

    async def open_binary(
        self,
        doc_id: str,
        key: str,
        *,
        chunk_size: int = 256 * 1024,
    ) -> AsyncIterator[bytes]:
        meta = self.get_three_d_meta(doc_id, key)
        if meta is None:
            raise KeyError(f"3D asset not found: doc_id={doc_id!r} key={key!r}")

        s3_key = self._key(doc_id, *meta.glb_path.split("/"))
        store = self._store

        async def _gen() -> AsyncIterator[bytes]:
            offset = 0
            while offset < meta.size:
                end = min(offset + chunk_size, meta.size) - 1
                payload = store.get_range(s3_key, start=offset, end=end + 1).bytes()
                yield bytes(payload)
                offset = end + 1

        return _gen()
