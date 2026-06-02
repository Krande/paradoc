"""Git provenance extraction for bundle manifests.

Mirrors the shape adapy's ada-build CLI bakes into its sidecar
``.build.json`` files — same commit / branch / dirty fields, same CI
env-var fallbacks for detached HEADs — so a future cross-app viewer can
read either provenance block without per-app special-casing.

The module is deliberately standalone (no pydantic, no async, no
network): callable from a build that hasn't even loaded the rest of
paradoc yet. The pydantic mirror used in the manifest model lives in
``manifest.py`` next door.
"""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GitProvenance:
    commit: str
    short_commit: str
    parents: list[str] = field(default_factory=list)
    branch: str = ""
    author_email: str = ""
    author_name: str = ""
    timestamp: str = ""
    remote_url: str = ""
    is_dirty: bool = False

    def to_dict(self) -> dict:
        return {
            "commit": self.commit,
            "short_commit": self.short_commit,
            "parents": list(self.parents),
            "branch": self.branch,
            "author_email": self.author_email,
            "author_name": self.author_name,
            "timestamp": self.timestamp,
            "remote_url": self.remote_url,
            "is_dirty": self.is_dirty,
        }


def find_repo_root(start: pathlib.Path) -> pathlib.Path | None:
    """Walk up from ``start`` until a ``.git`` entry exists.

    Stops at the filesystem root. Returns ``None`` when there is no
    enclosing git repo — caller is expected to set ``git=None`` on the
    manifest in that case rather than crash.
    """
    p = start.resolve()
    for candidate in (p, *p.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _run(args: list[str], cwd: pathlib.Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def extract(repo: pathlib.Path) -> GitProvenance | None:
    """Extract provenance from a working tree.

    Returns ``None`` if any of the core ``rev-parse`` / ``log`` calls
    fail (e.g. a shallow checkout with no commits, ``git`` not on PATH).
    Less critical fields (remote URL, dirty flag) degrade to defaults
    rather than failing the whole extraction.
    """
    try:
        commit = _run(["rev-parse", "HEAD"], repo)
        short_commit = _run(["rev-parse", "--short", "HEAD"], repo)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("git provenance: rev-parse failed in %s (%s)", repo, exc)
        return None

    try:
        parents_raw = _run(["rev-list", "--parents", "-n", "1", "HEAD"], repo)
        parents = parents_raw.split()[1:]
    except subprocess.CalledProcessError:
        parents = []

    try:
        branch = _run(["symbolic-ref", "--short", "HEAD"], repo)
    except subprocess.CalledProcessError:
        # Detached HEAD — common in CI checkouts. Fall back to env vars
        # the major CI systems set so a tagged-build still records a
        # human-meaningful branch/ref name.
        branch = (
            os.environ.get("GITHUB_REF_NAME")
            or os.environ.get("CI_COMMIT_BRANCH")
            or os.environ.get("FORGEJO_REF_NAME")
            or os.environ.get("FORGEJO_REF")
            or ""
        )

    try:
        author_email = _run(["log", "-1", "--format=%ae", "HEAD"], repo)
    except subprocess.CalledProcessError:
        author_email = ""

    try:
        author_name = _run(["log", "-1", "--format=%an", "HEAD"], repo)
    except subprocess.CalledProcessError:
        author_name = ""

    try:
        timestamp = _run(["log", "-1", "--format=%cI", "HEAD"], repo)
    except subprocess.CalledProcessError:
        timestamp = ""

    try:
        remote_url = _run(["remote", "get-url", "origin"], repo)
    except subprocess.CalledProcessError:
        remote_url = ""

    try:
        is_dirty = bool(_run(["status", "--porcelain"], repo))
    except subprocess.CalledProcessError:
        is_dirty = False

    return GitProvenance(
        commit=commit,
        short_commit=short_commit,
        parents=parents,
        branch=branch,
        author_email=author_email,
        author_name=author_name,
        timestamp=timestamp,
        remote_url=remote_url,
        is_dirty=is_dirty,
    )
