"""paradoc.toml schema for paradoc.tasks.

Schema (Q5/Q6 from the design doc):

    [paradoc]
    # Path to the pixi.toml for this document's build env(s),
    # resolved relative to paradoc.toml. The recommended layout is
    # one pixi.toml per document — the doc owns its build env so it
    # stays reproducible without coupling to sibling packages. Only
    # docs that *intentionally* verify an external package against
    # its own pixi env (eg adapy's verification report, which both
    # tests adapy and uses adapy in its output) should reach across
    # directories.
    pixi_toml = "pixi.toml"

    [paradoc.envs]
    default  = "docs"         # alias used by @task(env="default") or env=None
                              # in `PixiSubprocessExecutor`-pure mode
    meshing  = "meshing"      # alias referenced by @task(env="meshing")
    calculix = "calculix"

    # One or more profiles. Profile name = the `paradoc build` argument.
    [build.verification]
    # Inherits the @task-declared fanout for every task; explicit
    # overrides go below. List replacement, not merge (Q5).

    [build.verification.fanout.mesh]
    geom_repr  = ["line", "shell", "solid"]
    elem_order = [1, 2]

    [build.verification.fanout.run_eig]
    solver = ["abaqus", "calculix", "code_aster", "sesam"]

    # Per-profile env-map overrides (eg smoke build reuses the slim env
    # for what would normally be the calculix-specific env).
    [build.verification.envs]
    calculix = "tests"

Hard cuts deferred from Q7 hard-cuts: no `inherit = "..."` between
profiles in v0. Each `[build.<name>]` is flat.

The bare-`@task` ergonomic (no env declared → run in the controlling
process, no subprocess overhead) is implemented by `HybridExecutor`,
not here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib  # py>=3.11
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """Pydantic base that rejects unknown keys — typos in paradoc.toml
    should fail loud, not silently."""

    model_config = ConfigDict(extra="forbid")


class BuildProfile(_StrictModel):
    """One `[build.<name>]` section.

    `fanout` maps task qualname (or bare name) -> { axis -> [values] }.
    Per-axis replacement semantics: only listed axes override; unlisted
    axes inherit the decorator's fanout.

    `envs` maps env alias -> pixi env name, overriding the top-level
    `[paradoc.envs]` for this profile only.

    `outputs` is a list of export formats (eg `["docx", "pdf"]`) the
    orchestrator should produce per build. Empty list means "let the
    caller pick one format" — the CLI's `--format` flag in that case.
    """

    fanout: dict[str, dict[str, list[Any]]] = Field(default_factory=dict)
    envs: dict[str, str] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)


class TasksToml(_StrictModel):
    """Top-level `[paradoc]` section.

    `pixi_toml` is resolved relative to the location of paradoc.toml.
    `envs` is the global alias -> pixi env name mapping; profiles can
    override per-key.
    """

    pixi_toml: Optional[Path] = None
    envs: dict[str, str] = Field(default_factory=dict)


@dataclass
class TaskConfig:
    """Loaded + resolved task config for a single profile.

    Constructed by `load_task_config`. Holds everything the runner
    needs to build an executor + apply fanout overrides:
    - `pixi_toml`: absolute path the executor passes to `pixi run
      --manifest-path`.
    - `envs`: alias -> pixi env name, profile overrides applied.
    - `fanout_overrides`: task qualname -> { axis -> [values] }.
    """

    pixi_toml: Optional[Path]
    envs: dict[str, str]
    fanout_overrides: dict[str, dict[str, list[Any]]]
    outputs: list[str] = field(default_factory=list)
    profile: str = "default"


def load_task_config(
    toml_path: Path,
    *,
    profile: str = "default",
) -> TaskConfig:
    """Parse a paradoc.toml and resolve a profile into a TaskConfig.

    Behavior:
    - Missing toml file is not an error: returns an empty config.
      Authors with no `paradoc.toml` get the in-process-only fallback.
    - Missing `[paradoc]` section is also fine.
    - Profile is required to exist in `[build.*]` *only* if the toml
      has any `[build.*]` sections at all. The "no profiles defined,
      use whatever the @task declarations say" case is supported by
      returning an empty `fanout_overrides`.
    - Unknown profile name raises KeyError.
    """
    toml_path = Path(toml_path).resolve()
    if not toml_path.exists():
        return TaskConfig(pixi_toml=None, envs={}, fanout_overrides={}, profile=profile)

    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)

    paradoc_section = data.get("paradoc", {}) or {}
    paradoc_cfg = TasksToml(**paradoc_section)

    if paradoc_cfg.pixi_toml is not None:
        pixi_toml_resolved = (toml_path.parent / paradoc_cfg.pixi_toml).resolve()
    else:
        pixi_toml_resolved = None

    build_sections: dict[str, Any] = data.get("build", {}) or {}
    if build_sections and profile not in build_sections:
        raise KeyError(
            f"paradoc.toml has no [build.{profile}] section. "
            f"Known profiles: {sorted(build_sections)!r}"
        )

    profile_cfg = (
        BuildProfile(**build_sections[profile]) if profile in build_sections else BuildProfile()
    )

    # Resolve env-map: global envs, then profile overrides on top.
    resolved_envs = {**paradoc_cfg.envs, **profile_cfg.envs}

    return TaskConfig(
        pixi_toml=pixi_toml_resolved,
        envs=resolved_envs,
        fanout_overrides=profile_cfg.fanout,
        outputs=profile_cfg.outputs,
        profile=profile,
    )


def merge_fanout(
    task_fanout: dict[str, list[Any]],
    override: Optional[dict[str, list[Any]]],
) -> dict[str, list[Any]]:
    """Per-axis replacement: override wins on listed axes only.

    Used by `Runner.expand()` when a fanout_overrides map is supplied.
    Returns a fresh dict so callers can mutate without affecting the
    task's declared fanout.
    """
    out = dict(task_fanout)
    if override:
        out.update(override)
    return out


def build_executor_from_config(config: TaskConfig):
    """Construct a `HybridExecutor` (or `InProcessExecutor` fallback)
    from a `TaskConfig`.

    Returns:
    - `InProcessExecutor` if the config has no `pixi_toml` (no envs to
      switch to → in-process for everything).
    - `HybridExecutor` otherwise: env=None tasks stay in-process,
      env=<alias> tasks dispatch to a `PixiSubprocessExecutor` configured
      from the loaded config.
    """
    from .executors import HybridExecutor, InProcessExecutor, PixiSubprocessExecutor

    if config.pixi_toml is None:
        return InProcessExecutor()
    pixi = PixiSubprocessExecutor(
        pixi_toml=config.pixi_toml,
        env_map=config.envs,
    )
    return HybridExecutor(in_process=InProcessExecutor(), pixi=pixi)
