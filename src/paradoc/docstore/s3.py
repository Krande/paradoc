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
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

from paradoc.db import DbManager
from paradoc.db.models import PlotData, TableData, ThreeDData

from .base import DocStore


def _env_first(*names: str) -> Optional[str]:
    """Return the first non-empty value among the given env var names, else None."""
    for name in names:
        val = os.environ.get(name, "")
        if val and val.strip():
            return val.strip()
    return None


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
        # Resolve endpoint/region from env so the helm chart's
        # AWS_ENDPOINT_URL / AWS_REGION env vars actually flow through to
        # the obstore client config — otherwise `_build_store` couldn't
        # tell whether to apply the path-style + plain-HTTP defaults that
        # non-AWS S3 (Garage, MinIO) require. Empty strings are treated as
        # missing because Forgejo expands unset secrets that way.
        self.endpoint = endpoint or _env_first("AWS_ENDPOINT_URL", "AWS_ENDPOINT")
        self.region = region or _env_first("AWS_REGION", "AWS_DEFAULT_REGION")
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
            # Match upload_examples.py: a custom endpoint nearly always
            # means a non-AWS S3 (Garage, MinIO, LocalStack) which only
            # supports path-style and frequently runs over plain HTTP
            # inside a cluster. Without these the obstore client either
            # rejects the http:// scheme outright (BadScheme) or builds a
            # virtual-hosted URL the backend can't route, and every
            # list/get silently fails.
            kwargs["allow_http"] = True
            kwargs["virtual_hosted_style_request"] = False
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
        # Prefer `list_with_delimiter` so we get the per-doc subdirectories
        # back as `common_prefixes` directly, instead of paginating every
        # object in the bucket and reducing to first-segments. Trailing
        # slash matters: obstore evaluates prefixes on a path-segment
        # basis, so `examples/` matches `examples/foo` but not
        # `examples-other/foo` (and without the slash, listing is
        # technically still correct but less obviously scoped).
        try:
            import obstore as _obstore
        except ImportError:
            return []

        list_prefix = (self.prefix.rstrip("/") + "/") if self.prefix else None
        try:
            result = _obstore.list_with_delimiter(self._store, prefix=list_prefix)
            common = result["common_prefixes"] if isinstance(result, dict) else getattr(result, "common_prefixes", [])
        except Exception as exc:
            # Surface the error in logs rather than returning [] silently —
            # an empty doc list looked identical to "everything's fine but
            # nothing's published" and made this hard to diagnose.
            import logging

            logging.getLogger(__name__).warning(
                "S3DocStore.list_doc_ids via list_with_delimiter failed: %r", exc
            )
            return self._list_doc_ids_via_flat_listing(list_prefix)

        strip_len = len(list_prefix) if list_prefix else 0
        seen: set[str] = set()
        for cp in common:
            cp_str = str(cp).rstrip("/")
            seg = cp_str[strip_len:] if list_prefix and cp_str.startswith(list_prefix) else cp_str
            seg = seg.split("/", 1)[0]
            if seg:
                seen.add(seg)
        return sorted(seen)

    def _list_doc_ids_via_flat_listing(self, list_prefix: Optional[str]) -> list[str]:
        """Fallback for backends that don't support `list_with_delimiter` —
        paginate every object and reduce to first-segment-after-prefix.
        """
        try:
            stream = self._store.list(prefix=list_prefix)
        except Exception:
            return []
        seen: set[str] = set()
        strip_len = len(list_prefix) if list_prefix else 0
        try:
            for batch in stream:
                # `batch` is a Sequence[ObjectMeta]; ObjectMeta is a dict.
                for entry in batch:
                    key = entry["path"] if isinstance(entry, dict) else getattr(entry, "path", "")
                    rel = key[strip_len:] if strip_len and key.startswith(list_prefix or "") else key
                    first = rel.split("/", 1)[0]
                    if first and "." not in first:
                        seen.add(first)
        except Exception:
            return sorted(seen)
        return sorted(seen)

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

    def get_static_manifest_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._fetch_object(self._key(doc_id, "static", "manifest.json"))

    def get_static_section_bytes(self, doc_id: str, idx: int) -> Optional[bytes]:
        if idx < 0:
            return None
        return self._fetch_object(self._key(doc_id, "static", "sections", f"{idx}.json"))

    def get_static_plots_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._fetch_object(self._key(doc_id, "static", "plots.json"))

    def get_static_tables_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._fetch_object(self._key(doc_id, "static", "tables.json"))

    def get_static_images_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._fetch_object(self._key(doc_id, "static", "images.json"))

    def get_presets_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._fetch_object(self._key(doc_id, "assets", "presets.json"))

    def _fetch_object(self, key: str) -> Optional[bytes]:
        try:
            payload = self._store.get(key).bytes()
        except Exception:
            # obstore raises a generic error on missing key; return None
            # rather than swallowing real I/O errors silently — but we
            # don't have per-error-type granularity here, so any failure
            # surfaces as a 404 to the API client. Acceptable: missing
            # static/ output is the only realistic failure mode.
            return None
        return bytes(payload)

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
                # `get_range` returns an obstore `Bytes` object directly
                # (unlike `get`, which wraps a `GetResult` you'd then call
                # `.bytes()` on). Calling `.bytes()` here raises
                # AttributeError and the whole HTTP/2 stream resets with
                # INTERNAL_ERROR before any bytes hit the client.
                payload = store.get_range(s3_key, start=offset, end=end + 1)
                yield bytes(payload)
                offset = end + 1

        return _gen()
