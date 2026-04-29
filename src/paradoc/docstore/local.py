"""`LocalDocStore` — reads from a flat directory layout.

Layout::

    <root>/<doc_id>/{manifest.json, paradoc.sqlite, assets/3d/<key>.glb, ...}

For single-doc deployments, `<root>` *is* the bundle and `doc_id` is the
manifest's `doc_id`. The store still scopes lookups by `doc_id` so the
WS API and the future REST API have identical shapes.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator, Optional

from paradoc.db import DbManager
from paradoc.db.models import PlotData, TableData, ThreeDData

from .base import DocStore
from .manifest import read_manifest


class LocalDocStore(DocStore):
    """Filesystem-backed doc store for live-view dev mode."""

    def __init__(self, root: Path, *, db_filename: str = "paradoc.sqlite") -> None:
        self.root = Path(root).resolve()
        self.db_filename = db_filename
        self._managers: dict[str, DbManager] = {}

    # ---------------- doc layout helpers ----------------

    def _bundle_dir(self, doc_id: str) -> Path:
        """Resolve `doc_id` to a bundle directory, with traversal protection."""
        candidate = (self.root / doc_id).resolve()
        if not candidate.is_relative_to(self.root):
            raise PermissionError(f"doc_id {doc_id!r} escapes the doc root")

        # Single-doc deployment: root *is* the bundle. We accept either layout.
        if candidate == self.root or not candidate.exists():
            if (self.root / self.db_filename).exists():
                return self.root
        if not candidate.exists():
            raise FileNotFoundError(f"unknown doc_id: {doc_id!r}")
        return candidate

    def _db(self, doc_id: str) -> DbManager:
        bundle = self._bundle_dir(doc_id)
        cached = self._managers.get(str(bundle))
        if cached is not None:
            return cached
        manager = DbManager(bundle / self.db_filename)
        self._managers[str(bundle)] = manager
        return manager

    # ---------------- DocStore interface ----------------

    def list_doc_ids(self) -> list[str]:
        # Single-doc: list manifest.json's doc_id.
        if (self.root / self.db_filename).exists():
            try:
                return [read_manifest(self.root).doc_id]
            except FileNotFoundError:
                return [self.root.name]
        # Multi-doc: every immediate subdirectory with a manifest.json.
        out: list[str] = []
        for entry in sorted(self.root.iterdir()):
            if entry.is_dir() and (entry / "manifest.json").exists():
                try:
                    out.append(read_manifest(entry).doc_id)
                except FileNotFoundError:
                    continue
        return out

    def get_table(self, doc_id: str, key: str) -> Optional[TableData]:
        return self._db(doc_id).get_table(key)

    def get_plot(self, doc_id: str, key: str) -> Optional[PlotData]:
        return self._db(doc_id).get_plot(key)

    def get_three_d_meta(self, doc_id: str, key: str) -> Optional[ThreeDData]:
        return self._db(doc_id).get_three_d(key)

    def get_static_manifest_bytes(self, doc_id: str) -> Optional[bytes]:
        return self._read_static(doc_id, "manifest.json")

    def get_static_section_bytes(self, doc_id: str, idx: int) -> Optional[bytes]:
        if idx < 0:
            return None
        return self._read_static(doc_id, f"sections/{idx}.json")

    def _read_static(self, doc_id: str, rel: str) -> Optional[bytes]:
        bundle = self._bundle_dir(doc_id)
        path = (bundle / "static" / rel).resolve()
        if not path.is_relative_to(bundle):
            raise PermissionError(f"static path escapes bundle: {rel!r}")
        if not path.is_file():
            return None
        return path.read_bytes()

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

        bundle = self._bundle_dir(doc_id)
        # `glb_path` is bundle-relative — enforce that here too.
        full_path = (bundle / meta.glb_path).resolve()
        if not full_path.is_relative_to(bundle):
            raise PermissionError(f"3D asset path escapes bundle: {meta.glb_path!r}")
        if not full_path.exists():
            raise FileNotFoundError(f"3D asset file missing on disk: {full_path}")

        async def _gen() -> AsyncIterator[bytes]:
            with full_path.open("rb") as fh:
                while True:
                    chunk = fh.read(chunk_size)
                    if not chunk:
                        return
                    yield chunk

        return _gen()
