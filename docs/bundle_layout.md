# Bundle layout

A compiled paradoc doc is a self-contained directory. The same layout
is consumed by the local WS server (Phase 5) and — in the follow-up
PR — by the cloud REST server backed by S3 / obstore.

```
<bundle_root>/
├── manifest.json          # bundle_version, paradoc_version, doc_id, created_at
├── paradoc.sqlite         # tables, plots, three_d index
├── assets/
│   ├── presets.json       # camera presets shared with the frontend viewer
│   └── 3d/
│       ├── <key>.glb      # binary 3D asset
│       └── <key>.png      # static fallback image
├── 00-main/
│   └── *.md               # rewritten markdown files
└── 01-app/
    └── *.md
```

## Portability invariants

- All paths stored in `paradoc.sqlite` are bundle-relative. Move the
  bundle, change `<bundle_root>`, and references still resolve.
- Cache addressing is by content hash (`sha256`), not file mtime, so
  bundles round-trip through S3 without losing cache hits.
- The bundle never needs adapy at serve time. Adapy is a build-time
  dep only — required when the figure-source filters render glb / PNG.

## Single-doc vs multi-doc deployments

`LocalDocStore` accepts both layouts:

```
# single-doc (the bundle root *is* the doc)
<root>/manifest.json
<root>/paradoc.sqlite
<root>/assets/...

# multi-doc (each subdir is a doc)
<root>/<doc_id_1>/manifest.json
<root>/<doc_id_2>/manifest.json
```

The future REST follow-up uses the multi-doc layout in S3 at
`s3://<bucket>/<doc_id>/...`.

## Why content-hash caches

The frontend caches glb bytes in IndexedDB keyed by `sha256`. Multiple
references to the same model — across docs or across rebuilds — share
storage. The WS protocol's `binary_fetch_request` carries an optional
`sha256` hint; if it matches what the server has, the server replies
`binary_fetch_cached` and skips the transfer entirely.
