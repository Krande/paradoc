"""CAD model figure source: STEP / IFC → glb + PNG."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from ..models import CADModelFile
from .base import FigureSourceFilter, RenderResult, register_filter


@register_filter
class CADModelFileFilter(FigureSourceFilter):
    figure_source = "cad_model_file"

    def render(self, spec, *, key):
        if not isinstance(spec, CADModelFile):
            raise TypeError(f"CADModelFileFilter received non-CAD spec: {type(spec).__name__}")

        source_path = Path(spec.source_inp)
        if not source_path.is_absolute():
            # Resolve relative to bundle root (paradoc convention).
            source_path = (self.bundle_root / source_path).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"CAD source file not found: {source_path}")

        # Layout: <bundle_root>/assets/3d/<key>.glb and assets/3d/<key>.png.
        out_dir = self.bundle_root / "assets" / "3d"
        out_dir.mkdir(parents=True, exist_ok=True)

        glb_path = out_dir / f"{key}.glb"
        png_path = out_dir / f"{key}.png"

        # Fast path: a pre-rendered `<source>.glb` (and optional .png)
        # next to the input bypasses the adapy tessellation entirely.
        # Useful when the build env doesn't have ada-py installed, when
        # adapy doesn't tessellate the specific STEP file cleanly (e.g.
        # the round-trip-from-Beam case that hits the TopoDS_Solid
        # geometry bug in 0.7.11), or when the asset is genuinely
        # static and re-rendering on every build is wasted work.
        prebuilt_glb = source_path.with_suffix(".glb")
        prebuilt_png = source_path.with_suffix(".png")
        if prebuilt_glb.is_file():
            import shutil

            shutil.copy(prebuilt_glb, glb_path)
            # When the caller asked for the chromium backend we always
            # re-render — the prebuilt `.png` was almost certainly baked
            # by the pygfx default and won't reflect the embed's output.
            if spec.renderer == "pygfx" and prebuilt_png.is_file():
                shutil.copy(prebuilt_png, png_path)
            else:
                # Render from the glb directly using the chosen backend.
                # Falls back silently to a missing PNG if rendering fails.
                self._render_png_from_glb(glb_path, png_path, renderer=spec.renderer)
        else:
            self._render_with_adapy(
                source_path, glb_path, png_path, spec.camera_pos, renderer=spec.renderer,
            )

        glb_bytes = glb_path.read_bytes()
        return RenderResult(
            png_path=str(Path("assets") / "3d" / png_path.name),
            glb_path=str(Path("assets") / "3d" / glb_path.name),
            glb_sha256=hashlib.sha256(glb_bytes).hexdigest(),
            glb_size=len(glb_bytes),
            caption=spec.figure_title,
            camera_pos=spec.camera_pos,
            source_type=self.figure_source,
            metadata={"source_inp": str(source_path)},
        )

    def _render_png_from_glb(
        self, glb_in: Path, png_out: Path, *, renderer: str = "pygfx",
    ) -> None:
        """Render a PNG straight from an existing GLB.

        Used when a pre-baked `.glb` exists but the matching `.png` is
        missing OR when the figure spec explicitly asks for the
        chromium backend (in which case we can't reuse the prebuilt
        pygfx-baked PNG).

        Failures are swallowed — the bundle survives without a poster
        and the frontend falls back to a placeholder card.
        """
        if renderer == "chromium":
            try:
                from ada.visit.rendering.chromium_offscreen_utils import (
                    glb_to_image_via_browser,
                )

                glb_to_image_via_browser(glb_in).save(png_out)
                return
            except Exception as exc:  # pragma: no cover - exercised manually
                # Surface the actual failure (playwright not installed,
                # chromium libs missing on the build host, render
                # timeout, etc.) so CI logs can pinpoint why the
                # chromium poster is missing. Then fall through to the
                # trimesh best-effort path so the bundle still gets
                # *some* poster.
                logger.warning(
                    "chromium poster render failed for %s: %s",
                    glb_in.name, exc, exc_info=True,
                )

        try:
            import trimesh

            scene = trimesh.load(glb_in)
            try:
                png = scene.save_image(resolution=(800, 600))
            except Exception:
                png = None
            if png:
                png_out.write_bytes(png)
        except Exception:
            pass

    def _render_with_adapy(
        self,
        source: Path,
        glb_out: Path,
        png_out: Path,
        camera_pos: str,
        *,
        renderer: str = "pygfx",
    ) -> None:
        """Run adapy to produce the glb + PNG.

        Adapy is an optional runtime dep (only build-time needs it). We
        import lazily so test environments without adapy can still parse
        markdown and run unrelated tests.

        ``renderer`` picks the offscreen backend for the static PNG:

        * ``"pygfx"`` (default) — fast wgpu render, `camera` argument
          honored.
        * ``"chromium"`` — drives the production embed in headless
          Chromium and screenshots the canvas. `camera` is ignored;
          the embed applies the bundle's ``camera_pos`` preset itself.
        """
        try:
            import ada
        except ImportError as exc:  # pragma: no cover - exercised manually
            raise RuntimeError(
                "ada-py is required to render CAD figure sources. "
                "Install it in the doc build environment."
            ) from exc

        suffix = source.suffix.lower()
        if suffix in (".step", ".stp"):
            assembly = ada.from_step(source)
        elif suffix in (".ifc",):
            assembly = ada.from_ifc(source)
        else:
            raise NotImplementedError(f"Unsupported CAD format: {suffix}")

        # Glb for the interactive viewer.
        assembly.to_gltf(glb_out)

        # Static PNG for Word/PDF/HTML — adapy returns a PIL Image.
        if renderer == "chromium":
            image = assembly.render_offscreen(backend="chromium")
        else:
            camera = self._build_camera_for_assembly(assembly, camera_pos)
            image = assembly.render_offscreen(camera=camera)
        image.save(png_out)

    def _build_camera_for_assembly(self, assembly, camera_pos: str):
        """Translate a paradoc preset name into an adapy Camera object.

        We import adapy + paradoc presets lazily here so the figure_sources
        package stays importable without adapy installed.
        """
        from paradoc.camera.presets import BUILTIN_PRESETS

        preset = BUILTIN_PRESETS.get(camera_pos)
        if preset is None:
            # Unknown name — fall back to a sensible default to avoid hard
            # failure at build time. The frontend viewer will still respect
            # the literal string.
            preset = BUILTIN_PRESETS["iso_3"]

        try:
            from ada.visit.colors import Camera  # type: ignore
        except ImportError:
            try:
                from ada.geom import Camera  # type: ignore
            except ImportError:
                return None  # adapy will pick a default

        # The paradoc preset is bbox-relative; adapy's Camera typically takes
        # explicit positions. We pass camera as None and let adapy autoframe;
        # the paradoc preset is applied client-side on the glb.
        return None
