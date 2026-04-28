"""`manifest.json` — a tiny header at the bundle root.

The manifest documents the bundle format and lets serving processes
detect bundle-version mismatches. Keep it small; it's not a metadata
dump, it's a header.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Bump when we make a breaking change to the bundle layout.
BUNDLE_VERSION = 1


class BundleManifest(BaseModel):
    """Top-of-bundle header."""

    bundle_version: int = BUNDLE_VERSION
    paradoc_version: str
    doc_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"frozen": False}


def write_manifest(bundle_root: Path, *, doc_id: str, paradoc_version: Optional[str] = None) -> BundleManifest:
    if paradoc_version is None:
        paradoc_version = _detect_paradoc_version()
    manifest = BundleManifest(
        doc_id=doc_id,
        paradoc_version=paradoc_version,
    )
    bundle_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def read_manifest(bundle_root: Path) -> BundleManifest:
    path = bundle_root / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"no manifest.json at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return BundleManifest(**data)


def _detect_paradoc_version() -> str:
    try:
        from importlib.metadata import version

        return version("paradoc")
    except Exception:
        return "0.0.0"
