# Figure source examples

This page demonstrates every form of the figure-source / filter system:

- `<!-- paradoc:figure -->` block sugar for one-off CAD figures
- Named filter references via `${ filter.attr }`
- Inline scalars with format specs
- A standalone rasterized PNG produced by `assembly.render_offscreen()`
- Custom camera presets in `paradoc.toml`

## 1. Inline CAD figure (comment-block sugar)

The simplest path: drop a STEP file in line with no Python at all.

<!-- paradoc:figure
figure_source: cad_model_file
figure_title: Source CAD Model (STEP)
source_inp: files/cad.stp
camera_pos: iso_3
-->

The block above expands to a static PNG plus a `data-3d-key=...` so the
live-view frontend renders an interactive 3D viewer when the user clicks
"3D".

## 2. Named filter references

For computed views — eigenvalue results, comparison plots, multiple
camera angles of the same model — use a filter class declared in
`filters.py` and reference it from markdown.

The first eigenfrequency: ${ eig_main.first_freq:.2f } Hz.

The first three eigenmodes are summarized in:

${ eig_main.frequency_table }

## 3. Rasterized preview (offscreen render)

The same model also ships with a pre-rendered PNG. `populate_sources.py`
calls `assembly.render_offscreen()` (adapy's pygfx-backed renderer) and
saves the result alongside `cad.stp` — so a Word / PDF export, or any
viewer without WebGL, still sees an image of the geometry rather than
a broken 3D placeholder.

![Offscreen-rendered CAD model](files/cad.png){#fig:cad-rasterized width=80%}

Re-running `populate_sources.py` regenerates the PNG from scratch; the
markdown reference picks up whatever the script last wrote.

## 4. Custom camera presets

Define alternative camera presets in `paradoc.toml` under
`[cameras.custom.<name>]` and reference them from any figure source.
