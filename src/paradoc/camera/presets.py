"""Camera preset model + builtins, owned by paradoc.

Presets are bbox-relative so the same `iso_3` works on a 5 mm bracket and
a 30 m girder. The renderer (adapy backend) and the viewer (frontend)
both consume the same dict at build time.

Custom presets live in `paradoc.toml`::

    [cameras.custom.detail_iso]
    azimuth_deg = 45
    elevation_deg = 20
    distance = 0.6
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Mapping, Union

from pydantic import BaseModel, Field, field_validator

try:
    import tomllib  # py>=3.11
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


_DistanceSpec = Union[Literal["fit"], float]


class CameraPreset(BaseModel):
    """A bbox-relative camera placement.

    Attributes
    ----------
    name : str
        Identifier used in markdown (`camera_pos: iso_3`).
    azimuth_deg : float
        Rotation around the vertical axis, 0 = looking down +X.
    elevation_deg : float
        Vertical angle, positive = above horizon.
    roll_deg : float
        Camera roll. Default 0.
    target : Literal["bbox_center"]
        For now only bbox-center is supported. Reserved for future modes.
    distance : "fit" | float
        "fit" → frame the bbox with a small margin. Float → multiplier on
        the bbox diagonal length (1.0 = exactly diagonal-distance away).
    fov_deg : float
        Vertical field of view in degrees.
    margin : float
        Multiplier on the `distance="fit"` result. The fit distance is
        `radius / sin(fov/2)` (just-touches-the-viewport); `margin`
        scales it. ``1.0`` is the tightest crop, ``1.15`` (default)
        gives a comfortable 15 %-padding feel, ``< 1.0`` puts the
        camera *inside* the bbox so avoid that. Same semantics adapy's
        embed viewer uses for `applyCameraPreset.margin`.
    """

    name: str = Field(..., description="Preset identifier.")
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    roll_deg: float = 0.0
    target: Literal["bbox_center"] = "bbox_center"
    distance: _DistanceSpec = "fit"
    fov_deg: float = 45.0
    # 1.15 matches adapy embed's DEFAULT_MARGIN. The earlier 0.1 read
    # like "10% padding" but the embed multiplies the fit distance by
    # this value, so 0.1 landed the camera inside the geometry.
    margin: float = 1.15

    model_config = {"frozen": True}

    @field_validator("name")
    @classmethod
    def _name_is_identifier(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"camera preset name {v!r} must be a valid identifier")
        return v


CameraPresetMap = dict[str, CameraPreset]


# ---------------- builtins ----------------

# Isometric variants pick the four axis-aligned octants in the +Y up convention.
# The naming follows common CAD viewer convention: iso_1 = front-right-top, etc.
BUILTIN_PRESETS: CameraPresetMap = {
    p.name: p
    for p in [
        CameraPreset(name="iso_1", azimuth_deg=45, elevation_deg=30),
        CameraPreset(name="iso_2", azimuth_deg=135, elevation_deg=30),
        CameraPreset(name="iso_3", azimuth_deg=-135, elevation_deg=30),
        CameraPreset(name="iso_4", azimuth_deg=-45, elevation_deg=30),
        CameraPreset(name="top", azimuth_deg=0, elevation_deg=89.9),
        CameraPreset(name="bottom", azimuth_deg=0, elevation_deg=-89.9),
        CameraPreset(name="front", azimuth_deg=0, elevation_deg=0),
        CameraPreset(name="back", azimuth_deg=180, elevation_deg=0),
        CameraPreset(name="left", azimuth_deg=90, elevation_deg=0),
        CameraPreset(name="right", azimuth_deg=-90, elevation_deg=0),
    ]
}


# ---------------- loading ----------------


def load_camera_presets(paradoc_toml: Path | None = None) -> CameraPresetMap:
    """Return builtins merged with `[cameras.custom.<name>]` from `paradoc.toml`.

    Custom presets fully override builtins of the same name. Unknown keys
    raise — typos in toml shouldn't slip past silently.
    """
    presets: CameraPresetMap = dict(BUILTIN_PRESETS)
    if paradoc_toml is None or not paradoc_toml.exists():
        return presets

    data = tomllib.loads(paradoc_toml.read_text(encoding="utf-8"))
    custom = data.get("cameras", {}).get("custom", {})
    for name, body in custom.items():
        merged = {"name": name, **body}
        presets[name] = CameraPreset(**merged)
    return presets


def export_presets_json(presets: Mapping[str, CameraPreset], dest: Path) -> None:
    """Write `presets.json` for the frontend viewer.

    The shape is `{name: {...preset fields without `name`}}` so the JSON
    object reads naturally as a lookup table on the JS side.
    """
    payload = {
        name: preset.model_dump(exclude={"name"})
        for name, preset in presets.items()
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
