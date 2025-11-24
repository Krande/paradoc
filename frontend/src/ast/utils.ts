import type { Attr } from './types'
import { getEmbeddedImage } from '../sections/store'

/**
 * Check if a URL is absolute or a data URL
 */
export function isAbsoluteOrData(url: string): boolean {
  return /^([a-z]+:)?\/\//i.test(url) || url.startsWith('data:')
}

/**
 * Resolve an asset URL by checking IndexedDB first, then falling back to HTTP server
 */
export async function resolveAssetUrl(src: string, docId?: string): Promise<string> {
  try {
    if (!src) return src
    if (isAbsoluteOrData(src)) return src

    // Try to get embedded image from IndexedDB first
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
