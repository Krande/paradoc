import type { Attr } from './types'
import { getEmbeddedImage, getStaticBasePath, isStaticMode } from '../sections/store'
import { getRuntimeConfig } from '../transport'

/**
 * Check if a URL is absolute or a data URL
 */
export function isAbsoluteOrData(url: string): boolean {
  return /^([a-z]+:)?\/\//i.test(url) || url.startsWith('data:')
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + (path.startsWith('/') ? path : '/' + path)
}

function encodePathSegments(path: string): string {
  return path.split('/').map(encodeURIComponent).join('/')
}

/**
 * Resolve an asset URL.
 *
 * Order of preference (per transport):
 *   1. Absolute / data URLs pass through.
 *   2. Already-API-routed URLs (``/api/docs/...``) pass through. Some
 *      callers (e.g. Interactive3DFigure's poster) already construct
 *      the full API path; double-prefixing would break them.
 *   3. REST mode + relative path: route through ``/api/docs/{id}/files/...``.
 *      ``files/...`` srcs have the leading ``files/`` stripped first
 *      (the endpoint adds it back), so a markdown ``![](files/x.png)``
 *      doesn't end up as ``/files/files/x.png``.
 *   4. Static (embed) mode: return ``<basePath><path>`` so the browser
 *      fetches the file the static exporter copied alongside the SPA.
 *   5. WS mode: check IndexedDB for an image pushed via the
 *      ``embedded_images`` WS protocol (worker fan-in stores by path).
 *   6. Fall back to ``__PARADOC_ASSET_BASE`` for the WS+HTTP-sidecar
 *      case where images are served by the side HTTP server.
 */
export async function resolveAssetUrl(src: string, docId?: string): Promise<string> {
  try {
    if (!src) return src
    if (isAbsoluteOrData(src)) return src

    // Already an API path — caller did the routing; don't double-prefix.
    if (src.startsWith('/api/') || src.includes('/api/docs/')) return src

    const cfg = getRuntimeConfig()
    const normalized = src.replace(/^\.\//, '').replace(/^\//, '')

    // REST mode → per-image API endpoint. The backend's `_get_file`
    // serves any bundle-relative path, so `_images/foo.png` works as
    // well as `files/foo.png`. The `files/` prefix gets stripped
    // because the endpoint root *is* `files/<rel>` — without the
    // strip, `files/x.png` becomes `/files/files/x.png`.
    if (cfg.transport === 'rest' && docId) {
      const apiBase = cfg.apiBase || ''
      const rel = normalized.startsWith('files/')
        ? normalized.slice('files/'.length)
        : normalized
      return joinUrl(
        apiBase,
        `/api/docs/${encodeURIComponent(docId)}/files/${encodePathSegments(rel)}`,
      )
    }

    // Static (embed) mode → direct relative URL. The static exporter
    // copies each referenced image to `<output_dir>/<normalized>`, so
    // the browser fetches it lazily via the same web root that serves
    // the SPA.
    if (cfg.transport === 'static' || isStaticMode()) {
      const basePath = getStaticBasePath()
      return basePath + normalized
    }

    // WS mode → check IndexedDB for an image pushed via the worker's
    // embedded_images relay. Fall through to __PARADOC_ASSET_BASE for
    // the embed-images=false case where a sidecar HTTP server serves
    // the bundle.
    if (docId) {
      const pathVariants = [src, normalized]
      for (const path of pathVariants) {
        const embeddedImage = await getEmbeddedImage(docId, path)
        if (embeddedImage) return embeddedImage
      }
    }

    const base = (window as any).__PARADOC_ASSET_BASE as string | undefined
    if (!base) return src
    const b = base.endsWith('/') ? base : base + '/'
    return b + normalized
  } catch {
    return src
  }
}

/**
 * Convert Pandoc Attr to React props
 */
export function attrs(a: Attr | undefined): { id?: string; className?: string; [k: string]: string | undefined } {
  if (!a) return {}

  // Handle both array form [id, classes, attributes] and object form {id, classes, attributes}
  let id: string | undefined
  let classes: string[] = []
  let attributes: Array<[string, string]> | Record<string, any> = []

  if (Array.isArray(a)) {
    // Array form: [id, [classes], [[key, value], ...]]
    id = (a[0] && typeof a[0] === 'string') ? a[0] : undefined
    classes = (Array.isArray(a[1])) ? a[1] : []
    attributes = (a[2]) ? a[2] : []
  } else {
    // Object form: {id, classes, attributes}
    id = a.id
    classes = a.classes || []
    attributes = a.attributes || []
  }

  const other: Record<string, string> = {}

  // Handle attributes as array of [key, value] pairs (Pandoc format)
  if (Array.isArray(attributes)) {
    for (const attr of attributes) {
      if (Array.isArray(attr) && attr.length >= 2) {
        const [k, v] = attr
        if (typeof k === 'string' && typeof v === 'string') {
          other[k] = v
        }
      }
    }
  } else {
    // Handle attributes as object (legacy format)
    for (const k in attributes || {}) {
      const v = attributes[k]
      if (typeof v === 'string') other[k] = v
    }
  }

  return {
    id: id || undefined,
    className: (classes || []).join(' ') || undefined,
    ...other
  }
}
