"""DocStore abstraction: backend-neutral access to a built doc bundle.

`DocStore` is consumed by the WS server (Phase 5) and the future REST
server (Phase 10). This package ships `LocalDocStore` for live-view dev
mode; the REST follow-up adds an `S3DocStore` over obstore.
"""

from .base import DocStore
from .local import LocalDocStore
from .manifest import BUNDLE_VERSION, BundleManifest, read_manifest, write_manifest

__all__ = [
    "DocStore",
    "LocalDocStore",
    "BundleManifest",
    "BUNDLE_VERSION",
    "read_manifest",
    "write_manifest",
]
