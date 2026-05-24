"""Generate the figure-sources demo's CAD assets from scratch.

Three outputs land next to this script under ``files/``:

  * ``cad.stp`` — the STEP source the markdown's ``<!-- paradoc:figure -->``
    block consumes. paradoc's figure-source pipeline reads this and emits
    the bundle's interactive ``cad.glb`` and poster ``cad.png``.
  * ``cad.glb`` — a pre-baked glTF copy of the same model. The
    ``CADModelFileFilter`` fast-path copies it into the bundle without
    re-running adapy's tessellation, useful when the build env doesn't
    have the OCC stack available.
  * ``cad.png`` — an offscreen-rendered rasterized image of the same
    model. Used as the standalone PNG in the "Rasterized preview"
    section of ``source_3d.md``.

Re-running this script regenerates all three. The renderer-comparison
section in ``source_3d.md`` does *not* pre-render PNGs here — it relies
on the ``<!-- paradoc:figure renderer: pygfx|chromium -->`` block sugar
to bake both backends at compile time straight from this same
``cad.stp`` source.
"""

from __future__ import annotations

import logging
from pathlib import Path

import ada

logger = logging.getLogger(__name__)

# Output directory is ``files/`` next to this script — same path the
# markdown block's ``source_inp:`` resolves to.
OUT_DIR = Path(__file__).resolve().parent / "files"


def _build_assembly() -> ada.Assembly:
    """Canonical demo model — one IPE300 beam, 10 m long."""
    bm = ada.Beam("bm1", (0, 0, 0), (10, 0, 0), "IPE300")
    return ada.Assembly() / bm


def write_step(assembly: ada.Assembly, dest: Path) -> None:
    assembly.to_stp(str(dest))
    logger.info("wrote %s", dest)


def write_glb(assembly: ada.Assembly, dest: Path) -> None:
    """Emit a glTF copy as a fast-path artefact for CADModelFileFilter."""
    assembly.to_gltf(dest)
    logger.info("wrote %s", dest)


def write_png(assembly: ada.Assembly, dest: Path) -> None:
    """Render the model offscreen with adapy's pygfx-backed renderer.

    Headless — runs fine in CI as long as wgpu/pygfx + a libGL stack
    are present. ``Camera.fit_view=True`` (the default) auto-frames
    the bounding box so the one-beam scene comes out centred without
    extra setup.
    """
    image = assembly.render_offscreen(camera=None)
    image.save(dest)
    logger.info("wrote %s (size %s, mode %s)", dest, image.size, image.mode)


# Side-by-side renderer comparison: one beam, four camera presets, both
# backends. Lands as eight PNGs the markdown table in source_3d.md
# stitches into a 4×2 visual diff so the reader (and we) can spot
# framing / FOV / lighting drift between pygfx-offscreen and the
# chromium-headless screenshot of the live embed.
#
# Presets duplicate `paradoc.camera.presets.BUILTIN_PRESETS` keys
# verbatim (CameraPreset's field names match `render_offscreen`'s
# preset-dict kwargs). Inlining keeps the example self-contained:
# the `examples-figs` pixi env brings adapy + offscreen renderers
# but not paradoc itself.
_COMPARISON_PRESETS: dict[str, dict] = {
    "front":  {"azimuth_deg": 0,    "elevation_deg": 0},
    "top":    {"azimuth_deg": 0,    "elevation_deg": 89.9},
    "left":   {"azimuth_deg": 90,   "elevation_deg": 0},
    "iso_1":  {"azimuth_deg": 45,   "elevation_deg": 30},
}


def write_comparison_grid(assembly: ada.Assembly) -> None:
    """Render each preset through both pygfx + chromium backends.

    Output filenames follow ``beam_<preset>_<backend>.png`` so the
    markdown table can reference them with predictable paths. Backend
    selection routes through ``assembly.render_offscreen(backend=…)``
    — same dispatch the figure-sources block sugar uses, so a drift
    seen here is a drift the doc would render anyway.
    """
    for preset_name, preset in _COMPARISON_PRESETS.items():
        for backend in ("pygfx", "chromium"):
            dest = OUT_DIR / f"beam_{preset_name}_{backend}.png"
            try:
                image = assembly.render_offscreen(
                    camera=None,
                    backend=backend,
                    preset=preset,
                    size=(640, 480),
                )
                image.save(dest)
                logger.info("wrote %s (backend=%s, preset=%s)", dest, backend, preset_name)
            except Exception as exc:
                logger.warning(
                    "comparison render failed (%s, %s): %s", backend, preset_name, exc
                )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assembly = _build_assembly()
    write_step(assembly, OUT_DIR / "cad.stp")
    write_glb(assembly, OUT_DIR / "cad.glb")
    write_png(assembly, OUT_DIR / "cad.png")
    write_comparison_grid(assembly)


if __name__ == "__main__":
    main()
