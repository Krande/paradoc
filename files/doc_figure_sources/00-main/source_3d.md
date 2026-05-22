# Figure source examples

This page demonstrates every form of the figure-source / filter system:

- `<!-- paradoc:figure -->` block sugar for one-off CAD figures
- Named filter references via `${ filter.attr }`
- Inline scalars with format specs
- A standalone rasterized PNG produced by `assembly.render_offscreen()`
- A side-by-side comparison of the pygfx vs. headless-Chromium offscreen backends
- Custom camera presets in `paradoc.toml`

## Inline CAD figure (comment-block sugar)

The simplest path: drop a STEP file in line with no Python at all.

The markdown that produces the figure below looks like:

```markdown
<!-- paradoc:figure
figure_source: cad_model_file
figure_title: Source CAD Model (STEP)
source_inp: files/cad.stp
camera_pos: iso_3
-->
```

And the rendered output, in this very document:

<!-- paradoc:figure
figure_source: cad_model_file
figure_title: Source CAD Model (STEP)
source_inp: files/cad.stp
camera_pos: iso_3
-->

The block above expands to a static PNG plus a `data-3d-key=...` so the
live-view frontend renders an interactive 3D viewer when the user clicks
"3D".

## Named filter references

For computed views — eigenvalue results, comparison plots, multiple
camera angles of the same model — use a filter class declared in
`filters.py` and reference it from markdown.

The first eigenfrequency: ${ eig_main.first_freq:.2f } Hz.

The first three eigenmodes are summarized in:

${ eig_main.frequency_table }

## Rasterized preview (offscreen render)

The same model also ships with a pre-rendered PNG. `populate_sources.py`
calls `assembly.render_offscreen()` (adapy's pygfx-backed renderer) and
saves the result alongside `cad.stp` — so a Word / PDF export, or any
viewer without WebGL, still sees an image of the geometry rather than
a broken 3D placeholder.

![Offscreen-rendered CAD model](files/cad.png){#fig:cad-rasterized width=80%}

Re-running `populate_sources.py` regenerates the PNG from scratch; the
markdown reference picks up whatever the script last wrote.

## Renderer comparison: pygfx vs. headless Chromium

The `<!-- paradoc:figure -->` block accepts a `renderer:` key
(`pygfx` or `chromium`) that picks the offscreen backend used to bake
the static poster PNG. Two paradoc-figure blocks pointed at the same
`cad.stp`, one per backend, render the comparison below at compile
time — no pre-rendered images checked into the repo:

```markdown
<!-- paradoc:figure
figure_source: cad_model_file
figure_title: pygfx (fast, pure-Python wgpu)
source_inp: files/cad.stp
camera_pos: iso_3
renderer: pygfx
-->

<!-- paradoc:figure
figure_source: cad_model_file
figure_title: chromium (live-embed screenshot)
source_inp: files/cad.stp
camera_pos: iso_3
renderer: chromium
-->
```

| Backend     | How                                                                                                | Output                                            |
| ----------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `pygfx`     | Pure-Python wgpu render. Fast (~1 s/figure), no browser dependency.                                 | What `assembly.render_offscreen()` has always produced. |
| `chromium`  | Mounts the production adapy embed (`mountViewer`) in headless Chromium via Playwright and screenshots the canvas. | Bit-identical to what the live 3D viewer renders in the user's browser. |

The chromium path's framing, materials, and edge lines are whatever the
embed's `applyCameraPreset` + Three.js setup emits — so if the live viewer
ever drifts visually, the static poster drifts with it instead of needing
a separate re-implementation kept in sync.

<!-- paradoc:figure
figure_source: cad_model_file
figure_title: pygfx (fast, pure-Python wgpu)
source_inp: files/cad.stp
camera_pos: iso_3
renderer: pygfx
-->

<!-- paradoc:figure
figure_source: cad_model_file
figure_title: chromium (live-embed screenshot)
source_inp: files/cad.stp
camera_pos: iso_3
renderer: chromium
-->

Under the hood both blocks dispatch into adapy as
`assembly.render_offscreen(backend=…)`, exposed as a regular Python kwarg
so you can call it directly from a Task or a notebook when the comment-
block sugar is the wrong fit.

## Multi-view renderer comparison (FOV / framing diff)

The single iso comparison above didn't make the framing drift obvious.
This grid renders the same beam through both backends at four standard
camera presets so any FOV / fit / aspect mismatch shows up as a
position or scale shift between paired cells. `populate_sources.py`
calls `assembly.render_offscreen(backend=…, preset=…, size=(640, 480))`
once per cell — same dispatch the figure-source block sugar uses, so
a drift here is a drift the doc would render anywhere.

| view      | pygfx                                                      | chromium                                                       |
| --------- | ---------------------------------------------------------- | -------------------------------------------------------------- |
| front     | ![](files/beam_front_pygfx.png){width=100%}                | ![](files/beam_front_chromium.png){width=100%}                 |
| top       | ![](files/beam_top_pygfx.png){width=100%}                  | ![](files/beam_top_chromium.png){width=100%}                   |
| left      | ![](files/beam_left_pygfx.png){width=100%}                 | ![](files/beam_left_chromium.png){width=100%}                  |
| iso\_1    | ![](files/beam_iso_1_pygfx.png){width=100%}                | ![](files/beam_iso_1_chromium.png){width=100%}                 |

Both backends consume the same `CameraPreset` shape (azimuth, elevation,
fov, distance, margin). Chromium drives the production embed via
Playwright so its output is the live viewer's render exactly.
Visible drift between paired cells is a pygfx-side bug worth chasing.

## Custom camera presets

Define alternative camera presets in `paradoc.toml` under
`[cameras.custom.<name>]` and reference them from any figure source.
