"""Backend-neutral interface for serving a doc bundle.

Phase 5 and Phase 10 both consume this. The two implementations
(`LocalDocStore` and the future `S3DocStore`) share a contract that's
small enough to be obvious but specific enough to support chunked
binary streaming.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from paradoc.db.models import PlotData, TableData, ThreeDData


@dataclass(frozen=True)
class DocGroup:
    """A named bucket of doc IDs surfaced to the doc-switcher UI.

    `key` is the stable identifier the API returns (e.g. ``"shared"``);
    `label` is what the UI shows. The `shared`/`user`/`project` split
    reflects the ownership model the deployment expects, but the backend
    is free to add or rename groups — the frontend renders whatever
    groups come back, in order.
    """

    key: str
    label: str
    doc_ids: tuple[str, ...]


class DocStore(ABC):
    """Read-only access to a built doc bundle, independent of storage."""

    @abstractmethod
    def list_doc_ids(self) -> list[str]:
        """All doc IDs the store can serve."""

    def list_doc_groups(self) -> list[DocGroup]:
        """Return docs partitioned into named groups for the UI dropdown.

        Default implementation lumps every doc into a single ``shared``
        group plus empty ``user`` / ``project`` placeholders so the UI
        always renders a consistent three-section dropdown. Backends can
        override to derive groups from path layout or manifest metadata.
        """
        all_ids = tuple(self.list_doc_ids())
        return [
            DocGroup(key="shared", label="Shared", doc_ids=all_ids),
            DocGroup(key="user", label="My docs", doc_ids=()),
            DocGroup(key="project", label="Project", doc_ids=()),
        ]

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
