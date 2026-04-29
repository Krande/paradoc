"""Backend-neutral interface for serving a doc bundle.

Phase 5 and Phase 10 both consume this. The two implementations
(`LocalDocStore` and the future `S3DocStore`) share a contract that's
small enough to be obvious but specific enough to support chunked
binary streaming.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from paradoc.db.models import PlotData, TableData, ThreeDData


class DocStore(ABC):
    """Read-only access to a built doc bundle, independent of storage."""

    @abstractmethod
    def list_doc_ids(self) -> list[str]:
        """All doc IDs the store can serve."""

    @abstractmethod
    def get_table(self, doc_id: str, key: str) -> Optional[TableData]:
        ...

    @abstractmethod
    def get_plot(self, doc_id: str, key: str) -> Optional[PlotData]:
        ...

    @abstractmethod
    def get_three_d_meta(self, doc_id: str, key: str) -> Optional[ThreeDData]:
        ...

    @abstractmethod
    async def open_binary(
        self,
        doc_id: str,
        key: str,
        *,
        chunk_size: int = 256 * 1024,
    ) -> AsyncIterator[bytes]:
        """Yield binary payload (currently glb) in `chunk_size` chunks."""

    def get_static_manifest_bytes(self, doc_id: str) -> Optional[bytes]:
        """Return the raw bytes of the doc's static manifest.json.

        That's the DocManifest the frontend's static-mode loader expects
        (sections list, doc metadata) — distinct from the BundleManifest
        at the bundle root, which is paradoc-serve discovery metadata.
        Default implementation returns None; backends override.
        """
        return None

    def get_static_section_bytes(self, doc_id: str, idx: int) -> Optional[bytes]:
        """Return the raw bytes of a section JSON (export_static layout)."""
        return None
