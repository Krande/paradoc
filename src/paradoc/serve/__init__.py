"""HTTP REST surface for serving compiled paradoc bundles.

This is the cloud-side counterpart of the WS live-view server. It
exposes a small REST API that mirrors `DocStore`, with HTTP `Range`
support on the binary endpoint so big glbs stream cleanly.
"""

from .app import create_app
from .auth import User, current_user, require_admin

__all__ = ["create_app", "User", "current_user", "require_admin"]
