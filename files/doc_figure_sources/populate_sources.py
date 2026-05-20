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
    model. Used as the static poster shown in HTML / PDF / Word and
    embedded in the "Rasterized preview" section of ``source_3d.md`` as
    a standalone figure.

Re-running this script regenerates all three. The demo therefore stays
self-contained: a clone + ``pixi run -e examples-figs python populate_sources.py``
reproduces the CAD assets without any hand-placed PNGs.
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assembly = _build_assembly()
    write_step(assembly, OUT_DIR / "cad.stp")
    write_glb(assembly, OUT_DIR / "cad.glb")
    write_png(assembly, OUT_DIR / "cad.png")


if __name__ == "__main__":
    main()
