#!/usr/bin/env bash
# Rebuild src/frontend/vendor/ada-viewer from adapy's WebGPU-only embed (src/frontend/embed-webgpu).
#
#   scripts/vendor_ada_viewer.sh <adapy checkout> <dir with adacpp_render.js + adacpp_render.wasm>
#
# The renderer files come from adacpp (tools/build_render_wasm.sh); they are inlined into the bundle,
# so the report's 3D figures need nothing served beside it. Records both sources in SOURCE.
set -euo pipefail
ADAPY="$(cd "${1:?adapy checkout}" && pwd)"
RENDER="$(cd "${2:?adacpp_render.js/.wasm directory}" && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$HERE/src/frontend/vendor/ada-viewer"

(cd "$ADAPY/src/frontend" && ADACPP_RENDER_DIR="$RENDER" npm run build:embed-webgpu)
cp "$ADAPY/src/frontend/dist-embed-webgpu/index.js" "$ADAPY/src/frontend/dist-embed-webgpu/index.d.ts" "$OUT/"
{
    echo "adapy: $(git -C "$ADAPY" rev-parse HEAD)"
    echo "adacpp renderer: $(cat "$RENDER/adacpp_render.ref" 2>/dev/null || echo "unrecorded; sha256 $(sha256sum "$RENDER/adacpp_render.wasm" | cut -c1-16)")"
} > "$OUT/SOURCE"
ls -la "$OUT"
