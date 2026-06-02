"""`manifest.json` — a tiny header at the bundle root.

The manifest documents the bundle format and lets serving processes
detect bundle-version mismatches. Keep it small; it's not a metadata
dump, it's a header.

v2 added ``published_at`` (alongside the existing ``created_at``) and
``git`` (provenance extracted from the source repo at compile time).
Both fields are optional in the model — older v1 manifests still
deserialise without the values, defaulting to ``published_at ==
created_at`` and ``git == None``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ._git import extract as _git_extract
from ._git import find_repo_root

# Bump when we make a breaking change to the bundle layout.
BUNDLE_VERSION = 2


class GitProvenance(BaseModel):
    """Pydantic mirror of ``_git.GitProvenance``.

    Kept here (not in ``_git.py``) so build scripts that don't have
    pydantic loaded can still call the extractor — the dataclass and
    pydantic shapes share field names so conversion is a dict round-trip.
    """

    commit: str
    short_commit: str
    parents: list[str] = Field(default_factory=list)
    branch: str = ""
    author_email: str = ""
    author_name: str = ""
    timestamp: str = ""
    remote_url: str = ""
    is_dirty: bool = False


class BundleManifest(BaseModel):
    """Top-of-bundle header."""

    bundle_version: int = BUNDLE_VERSION
    paradoc_version: str
    doc_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Defaults to ``created_at`` at write time; carrying both lets a
    # later "mark live" flow update published_at independently without
    # rewriting the bundle. None = pre-v2 bundle that didn't have it.
    published_at: Optional[str] = None
    git: Optional[GitProvenance] = None

    model_config = {"frozen": False}


def write_manifest(
    bundle_root: Path,
    *,
    doc_id: str,
    paradoc_version: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> BundleManifest:
    """Write ``<bundle_root>/manifest.json`` with git provenance.

    ``repo_root`` is the path to walk up from when looking for an
    enclosing ``.git`` directory. Callers typically pass
    ``Document.source_dir`` so the git block reflects the project repo
    that contains the build script, not paradoc's own source tree. If
    omitted, defaults to the bundle root's parent (sensible when the
    bundle lives inside the repo it documents). When no ``.git`` is
    found we leave ``git=None`` rather than fail — paradoc must stay
    usable outside version control.
    """
    if paradoc_version is None:
        paradoc_version = _detect_paradoc_version()

    git_block: Optional[GitProvenance] = None
    search_from = repo_root if repo_root is not None else bundle_root.parent
    repo = find_repo_root(search_from)
    if repo is not None:
        dc = _git_extract(repo)
        if dc is not None:
            git_block = GitProvenance(**dc.to_dict())

    now = datetime.now(timezone.utc).isoformat()
    manifest = BundleManifest(
        doc_id=doc_id,
        paradoc_version=paradoc_version,
        created_at=now,
        published_at=now,
        git=git_block,
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
