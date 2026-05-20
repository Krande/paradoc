"""Backend-neutral interface for serving a doc bundle.

Phase 5 and Phase 10 both consume this. The two implementations
(`LocalDocStore` and the future `S3DocStore`) share a contract that's
small enough to be obvious but specific enough to support chunked
binary streaming.

Each read method takes a :class:`paradoc.serve.scope.Scope` so the
DocStore can resolve to ``<root>/<scope.prefix()>/<doc_id>/...``.
``Scope.shared()`` is the default for backwards-compat with single-doc
deployments; ``user`` and ``project`` scopes only make sense for
multi-doc S3-backed deployments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, AsyncIterator, Optional

from paradoc.db.models import PlotData, TableData, ThreeDData

if TYPE_CHECKING:
    from paradoc.serve.scope import Scope

    from .manifest import BundleManifest


def _default_shared_scope() -> "Scope":
    """Local helper avoiding a top-level import of paradoc.serve.scope.

    ``paradoc.serve`` depends on ``paradoc.docstore``, so importing
    ``Scope`` at module top would create a cycle. Each method that wants
    a default reaches for this — cheap and obvious.
    """
    from paradoc.serve.scope import Scope as _Scope

    return _Scope.shared()


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
    """Read-only access to a built doc bundle, independent of storage.

    Path-style methods take a :class:`Scope` and resolve to
    ``<root>/<scope.prefix()>/<doc_id>/...``. When no scope is passed,
    they default to ``Scope.shared()`` for backwards-compat.
    """

    @abstractmethod
    def list_doc_ids(self, scope: Optional["Scope"] = None) -> list[str]:
        """All doc IDs the store can serve within ``scope``."""

    def put_bundle_file(
        self,
        doc_id: str,
        rel_path: str,
        data: bytes,
        *,
        scope: Optional["Scope"] = None,
    ) -> None:
        """Write ``data`` to ``<bundle>/<rel_path>`` within the doc.

        Used by the upload route the ``paradoc publish`` CLI hits.
        Implementations must reject path-traversal and overwrite-safe
        the destination atomically when possible. Read-only stores
        raise ``NotImplementedError``.
        """
        raise NotImplementedError

    def get_file_bytes(
        self,
        doc_id: str,
        rel_path: str,
        *,
        scope: Optional["Scope"] = None,
    ) -> Optional[bytes]:
        """Return raw bytes of ``<bundle>/files/<rel_path>``.

        Backs the ``/api/docs/{doc_id}/files/{path}`` route so plain
        markdown image refs (``![](files/cad.png)``) work without going
        through the IndexedDB-embedding round-trip the static-mode SPA
        relies on. Implementations must reject any ``rel_path`` that
        escapes the bundle root (``..``, absolute paths, etc.).
        Returns ``None`` when the file is missing.
        """
        return None

    def get_bundle_manifest(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional["BundleManifest"]:
        """Return the parsed ``<bundle>/manifest.json`` for ``doc_id``.

        Used by aggregation endpoints (``/api/landing``) that want
        published_at + git provenance per doc without paying for the
        full static-bundle read. ``None`` if the manifest is missing or
        unparseable; callers fall back to id-only display.
        """
        return None

    def list_doc_groups(self) -> list[DocGroup]:
        """Return docs partitioned into named groups for the UI dropdown.

        Default implementation lists shared-scope docs and emits empty
        ``user`` / ``project`` placeholders. A future user-aware version
        will accept a :class:`paradoc.serve.auth.User` and surface the
        user's accessible projects.
        """
        all_ids = tuple(self.list_doc_ids(_default_shared_scope()))
        return [
            DocGroup(key="shared", label="Shared", doc_ids=all_ids),
            DocGroup(key="user", label="My docs", doc_ids=()),
            DocGroup(key="project", label="Project", doc_ids=()),
        ]

    @abstractmethod
    def get_table(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[TableData]:
        ...

    @abstractmethod
    def get_plot(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[PlotData]:
        ...

    @abstractmethod
    def get_three_d_meta(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[ThreeDData]:
        ...

    @abstractmethod
    async def open_binary(
        self,
        doc_id: str,
        key: str,
        *,
        scope: Optional["Scope"] = None,
        chunk_size: int = 256 * 1024,
    ) -> AsyncIterator[bytes]:
        """Yield binary payload (currently glb) in `chunk_size` chunks."""

    def get_static_manifest_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of the doc's static manifest.json.

        That's the DocManifest the frontend's static-mode loader expects
        (sections list, doc metadata) — distinct from the BundleManifest
        at the bundle root, which is paradoc-serve discovery metadata.
        Default implementation returns None; backends override.
        """
        return None

    def get_static_section_bytes(
        self, doc_id: str, idx: int, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of a section JSON (export_static layout)."""
        return None

    def get_static_plots_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of `static/plots.json` (pre-rendered Plotly
        figures keyed by plot key) — what the static-mode loader fetches as
        `plots.json` and the REST loader now consumes via the bulk endpoint.
        """
        return None

    def get_static_tables_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of `static/tables.json`."""
        return None

    def get_static_images_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of `static/images.json` (embedded base64 image
        payloads keyed by image path)."""
        return None

    def get_presets_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        """Return the raw bytes of `assets/presets.json` — the camera
        preset map adapy emits at compile time. The 3D viewer needs this
        to mirror the static PNG's camera framing (preset names alone
        aren't enough; the viewer needs `distance`, `target`, etc.).
        """
        return None
