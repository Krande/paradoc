import type { Attr } from './types'
import { getEmbeddedImage } from '../sections/store'
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

/**
 * Resolve an asset URL.
 *
 * Order of preference:
 *   1. Absolute / data URLs pass through.
 *   2. Markdown ``files/...`` paths in REST mode → ``/api/docs/{id}/files/{path}``.
 *      Stops the IndexedDB race (sections render before images.json
 *      finished seeding) and avoids paying the embedded-base64 cost
 *      for files that already live in S3.
 *   3. IndexedDB lookup (static-mode SPA + any path that was embedded
 *      via ``images.json``).
 *   4. Whatever ``__PARADOC_ASSET_BASE`` rewriting the host runtime
 *      configured.
 */
export async function resolveAssetUrl(src: string, docId?: string): Promise<string> {
  try {
    if (!src) return src
    if (isAbsoluteOrData(src)) return src

    // REST mode + relative path starting with `files/`: route through
    // the doc's static-file endpoint. This is the fast path for plain
    // markdown image references — no IndexedDB round-trip, no race
    // with the bulk images.json fetch.
    const cfg = getRuntimeConfig()
    if (cfg.transport === 'rest' && docId) {
      const normalized = src.replace(/^\.\//, '').replace(/^\//, '')
      if (normalized.startsWith('files/')) {
        const apiBase = cfg.apiBase || ''
        const rel = normalized.slice('files/'.length)
        return joinUrl(
          apiBase,
          `/api/docs/${encodeURIComponent(docId)}/files/${rel
            .split('/')
            .map(encodeURIComponent)
            .join('/')}`,
        )
      }
    }

    // Try to get embedded image from IndexedDB next (static-mode bundle).
    if (docId) {
      // Normalize path: try original, without ./, and without leading /
      const pathVariants = [
        src,
        src.replace(/^\.\//, ''),  // Remove leading ./
        src.replace(/^\//, ''),     // Remove leading /
      ]

      for (const path of pathVariants) {
        const embeddedImage = await getEmbeddedImage(docId, path)
        if (embeddedImage) {
          return embeddedImage
        }
      }
    }

    // Fall back to HTTP server
    const base = (window as any).__PARADOC_ASSET_BASE as string | undefined
    if (!base) return src
    const b = base.endsWith('/') ? base : base + '/'
    const s = src.startsWith('/') ? src.slice(1) : src.replace(/^\.\//, '')
    return b + s
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
