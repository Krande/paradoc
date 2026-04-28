"""Declarative `Task` model.

This is intentionally bare. The real runner — input/output hashing,
DAG resolution, partial reruns — lives in the follow-up PR (likely
backed by pixi-tasks or snakemake). What this PR locks in:

- Stable identity (`name`).
- The fields a hashing runner needs to memoize executions.
- Optional list of upstream tasks that must complete first.

Filter authors can already assign a Task to `Filter.task`; the runtime
won't do anything with it yet, but the data lives in the right shape so
the migration to a real runner is purely additive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    """A unit of upstream computation a filter depends on."""

    name: str = Field(..., description="Unique identifier (used for caching and logs).")
    inputs: list[str] = Field(default_factory=list, description="Input files / globs.")
    outputs: list[str] = Field(default_factory=list, description="Expected output files / globs.")
    env_lock: Optional[Path] = Field(
        default=None,
        description="Lockfile pinning the script execution environment.",
    )
    solver_version: Optional[str] = Field(
        default=None,
        description="Version pin for the simulation solver, if any.",
    )
    depends_on: list[str] = Field(default_factory=list, description="Upstream task names.")

    model_config = {"frozen": False}
