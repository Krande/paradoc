"""`LocalDocStore` — reads from a scope-aware directory layout.

Multi-doc layout (scope-aware)::

    <root>/<scope_kind>/<scope_id?>/<doc_id>/{manifest.json, paradoc.sqlite, ...}

Where ``<scope_kind>/<scope_id?>`` comes from :meth:`Scope.prefix`:

  * ``shared``                 — shared content
  * ``users/<user_id>``        — owner-only content
  * ``projects/<project_id>``  — project-scoped content

Single-doc layout (legacy, for the CLI's ``paradoc-serve <bundle>``)::

    <root>/{manifest.json, paradoc.sqlite, ...}

In single-doc mode the entire root *is* the bundle and the store
implicitly serves ``Scope.shared()``; non-shared scopes return
``None`` / 404 since there's nowhere for them to live.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Optional

from paradoc.db import DbManager
from paradoc.db.models import PlotData, TableData, ThreeDData

from .base import DocStore, _default_shared_scope
from .manifest import read_manifest

if TYPE_CHECKING:
    from paradoc.serve.scope import Scope

    from .manifest import BundleManifest


class LocalDocStore(DocStore):
    """Filesystem-backed doc store. Scope-aware in multi-doc mode."""

    def __init__(self, root: Path, *, db_filename: str = "paradoc.sqlite") -> None:
        self.root = Path(root).resolve()
        self.db_filename = db_filename
        self._managers: dict[str, DbManager] = {}

    # ---------------- doc layout helpers ----------------

    def _is_single_doc(self) -> bool:
        return (self.root / self.db_filename).exists()

    def _scope_root(self, scope: "Scope") -> Path:
        """Resolve ``<root>/<scope.prefix()>`` for multi-doc mode.

        For single-doc mode, the entire root is the bundle and scope is
        ignored upstream — callers shouldn't ask for a scope_root here.
        """
        prefix_parts = scope.prefix().split("/")
        out = (self.root.joinpath(*prefix_parts)).resolve()
        if not out.is_relative_to(self.root):
            raise PermissionError(f"scope {scope!r} escapes the doc root")
        return out

    def _bundle_dir(self, doc_id: str, scope: "Scope") -> Path:
        """Resolve to a bundle directory, with traversal protection."""
        if self._is_single_doc():
            # Single-doc deployment: the root IS the bundle. Only shared
            # scope makes sense here; non-shared requests will miss when
            # the docs aren't actually in that scope.
            if scope.kind != "shared":
                raise FileNotFoundError(
                    f"single-doc deployment only serves shared scope; "
                    f"got {scope.kind!r}"
                )
            return self.root

        scope_root = self._scope_root(scope)
        candidate = (scope_root / doc_id).resolve()
        if not candidate.is_relative_to(scope_root):
            raise PermissionError(f"doc_id {doc_id!r} escapes the scope root")
        if not candidate.exists():
            raise FileNotFoundError(f"unknown doc_id: {doc_id!r}")
        return candidate

    def _db(self, doc_id: str, scope: "Scope") -> DbManager:
        bundle = self._bundle_dir(doc_id, scope)
        cached = self._managers.get(str(bundle))
        if cached is not None:
            return cached
        manager = DbManager(bundle / self.db_filename)
        self._managers[str(bundle)] = manager
        return manager

    # ---------------- DocStore interface ----------------

    def list_doc_ids(self, scope: Optional["Scope"] = None) -> list[str]:
        s = scope if scope is not None else _default_shared_scope()
        if self._is_single_doc():
            if s.kind != "shared":
                return []
            try:
                return [read_manifest(self.root).doc_id]
            except FileNotFoundError:
                return [self.root.name]
        scope_root = self._scope_root(s)
        if not scope_root.is_dir():
            return []
        out: list[str] = []
        for entry in sorted(scope_root.iterdir()):
            if entry.is_dir() and (entry / "manifest.json").exists():
                try:
                    out.append(read_manifest(entry).doc_id)
                except FileNotFoundError:
                    continue
        return out

    def get_file_bytes(
        self,
        doc_id: str,
        rel_path: str,
        *,
        scope: Optional["Scope"] = None,
    ) -> Optional[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s)
        except (FileNotFoundError, PermissionError):
            return None
        files_root = (bundle / "files").resolve()
        # Resolve the candidate path and reject anything that climbs out
        # of <bundle>/files/. ``resolve()`` collapses ``..`` segments;
        # ``is_relative_to`` is the final gate.
        candidate = (files_root / rel_path).resolve()
        if not candidate.is_relative_to(files_root):
            return None
        if not candidate.is_file():
            return None
        return candidate.read_bytes()

    def put_bundle_file(
        self,
        doc_id: str,
        rel_path: str,
        data: bytes,
        *,
        scope: Optional["Scope"] = None,
    ) -> None:
        s = scope if scope is not None else _default_shared_scope()
        # Single-doc deployments shouldn't be uploaded into via the
        # CLI; the file layout has no per-doc subdirectory.
        if self._is_single_doc():
            raise PermissionError(
                "uploads not supported on single-doc deployments"
            )
        scope_root = self._scope_root(s)
        bundle_root = (scope_root / doc_id).resolve()
        if not bundle_root.is_relative_to(scope_root):
            raise PermissionError(f"doc_id {doc_id!r} escapes scope root")
        target = (bundle_root / rel_path).resolve()
        if not target.is_relative_to(bundle_root):
            raise PermissionError(f"rel_path {rel_path!r} escapes bundle root")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def get_bundle_manifest(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional["BundleManifest"]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s)
        except (FileNotFoundError, PermissionError):
            return None
        try:
            return read_manifest(bundle)
        except (FileNotFoundError, Exception):
            return None

    def get_table(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[TableData]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            return self._db(doc_id, s).get_table(key)
        except FileNotFoundError:
            return None

    def get_plot(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[PlotData]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            return self._db(doc_id, s).get_plot(key)
        except FileNotFoundError:
            return None

    def get_three_d_meta(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[ThreeDData]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            return self._db(doc_id, s).get_three_d(key)
        except FileNotFoundError:
            return None

    def list_bundle_files(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> list:
        from .base import BundleFileEntry
        import mimetypes

        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s).resolve()
        except (FileNotFoundError, PermissionError):
            return []
        out: list[BundleFileEntry] = []
        for path in sorted(bundle.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(bundle).as_posix()
            try:
                size = path.stat().st_size
            except OSError:
                continue
            ctype, _ = mimetypes.guess_type(rel)
            out.append(BundleFileEntry(rel_path=rel, size=size, content_type=ctype or ""))
        return out

    def get_three_d_fea_artefact(
        self,
        doc_id: str,
        key: str,
        filename: str,
        *,
        scope: Optional["Scope"] = None,
    ) -> Optional[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s).resolve()
        except (FileNotFoundError, PermissionError):
            return None
        # Reject path traversal: filename must resolve under
        # `<bundle>/assets/3d/<key>/`.
        clean = filename.replace("\\", "/").strip("/")
        if not clean or ".." in clean.split("/") or "/" in key or ".." in key:
            return None
        artefact_root = (bundle / "assets" / "3d" / key).resolve()
        candidate = (artefact_root / clean).resolve()
        if not candidate.is_relative_to(artefact_root):
            return None
        if not candidate.is_file():
            return None
        return candidate.read_bytes()

    def get_three_d_poster(
        self, doc_id: str, key: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        meta = self.get_three_d_meta(doc_id, key, scope=s)
        if meta is None or not isinstance(meta.metadata, dict):
            return None
        image_path = meta.metadata.get("image_path")
        if not image_path:
            return None
        try:
            bundle = self._bundle_dir(doc_id, s)
        except (FileNotFoundError, PermissionError):
            return None
        # `assets/3d/<key>.png` lives outside <bundle>/files/, so we
        # resolve from the bundle root and just gate the result with
        # `is_relative_to(bundle)`.
        candidate = (bundle / image_path).resolve()
        bundle = bundle.resolve()
        if not candidate.is_relative_to(bundle):
            return None
        if not candidate.is_file():
            return None
        return candidate.read_bytes()

    def get_static_manifest_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        return self._read_static(doc_id, "manifest.json", scope)

    def get_static_section_bytes(
        self, doc_id: str, idx: int, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        if idx < 0:
            return None
        return self._read_static(doc_id, f"sections/{idx}.json", scope)

    def get_static_plots_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        return self._read_static(doc_id, "plots.json", scope)

    def get_static_tables_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        return self._read_static(doc_id, "tables.json", scope)

    def get_static_images_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        return self._read_static(doc_id, "images.json", scope)

    def get_presets_bytes(
        self, doc_id: str, *, scope: Optional["Scope"] = None
    ) -> Optional[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s)
        except FileNotFoundError:
            return None
        path = (bundle / "assets" / "presets.json").resolve()
        if not path.is_relative_to(bundle):
            raise PermissionError("presets path escapes bundle")
        if not path.is_file():
            return None
        return path.read_bytes()

    def _read_static(
        self, doc_id: str, rel: str, scope: Optional["Scope"]
    ) -> Optional[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        try:
            bundle = self._bundle_dir(doc_id, s)
        except FileNotFoundError:
            return None
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
        scope: Optional["Scope"] = None,
        chunk_size: int = 256 * 1024,
    ) -> AsyncIterator[bytes]:
        s = scope if scope is not None else _default_shared_scope()
        meta = self.get_three_d_meta(doc_id, key, scope=s)
        if meta is None:
            raise KeyError(f"3D asset not found: doc_id={doc_id!r} key={key!r}")

        bundle = self._bundle_dir(doc_id, s)
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
