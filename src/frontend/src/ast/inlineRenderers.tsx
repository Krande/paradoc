import React from 'react'
import type { PandocInline } from './types'
import { attrs, resolveAssetUrl } from './utils'
import { useDocId } from './context'
import { authedFetch } from '../services/auth/oidc'
import { isDocApiPath } from '../transport/docScope'
import { revealElement, scrollToHeading } from '../components/readerNav'

// KaTeX (~265 KB of script, plus its stylesheet) is loaded the first time a formula renders, not
// with the app: most sections, and many documents, have no math at all.
let katexPromise: Promise<any> | null = null
function loadKatex(): Promise<any> {
  if (!katexPromise) {
    katexPromise = Promise.all([import('katex'), import('katex/dist/katex.min.css')]).then(
      ([m]) => (m as any).default || m,
    )
    katexPromise.catch(() => {
      katexPromise = null
    })
  }
  return katexPromise
}

/**
 * Component to render LaTeX math using KaTeX
 */
export function MathElement({ latex, displayMode }: { latex: string; displayMode: boolean }): React.ReactElement {
  const elementRef = React.useRef<HTMLSpanElement>(null)

  React.useEffect(() => {
    let canceled = false
    const el = elementRef.current
    if (!el) return
    const fallback = () => {
      el.textContent = displayMode ? `\\[${latex}\\]` : `\\(${latex}\\)`
    }
    loadKatex()
      .then((katex) => {
        if (canceled) return
        try {
          katex.render(latex, el, {
            displayMode,
            throwOnError: false,
            errorColor: '#cc0000',
            strict: false,
          })
        } catch (error) {
          console.error('KaTeX rendering error:', error)
          // Fallback: show the raw LaTeX if rendering fails
          fallback()
        }
      })
      .catch((error) => {
        console.error('KaTeX failed to load:', error)
        if (!canceled) fallback()
      })
    return () => {
      canceled = true
    }
  }, [latex, displayMode])

  return (
    <span
      ref={elementRef}
      className={displayMode ? "block my-4 text-center" : "inline-block mx-0.5"}
    />
  )
}

/**
 * Component to render an image with async URL resolution.
 *
 * resolveAssetUrl gives us one of three shapes:
 *   * data: URL (embedded base64 from IndexedDB, WS embed mode) — use directly.
 *   * absolute http(s):// URL or static-mode relative path — set as
 *     src; native ``loading="lazy"`` defers off-screen browser fetches.
 *   * `/api/...` route path (REST mode) — needs the bearer token, so
 *     we ``authedFetch`` the bytes per-image and swap to a ``blob:``
 *     URL. Per-image fetch replaces the legacy ~10 MB bulk preload;
 *     section-level virtualization in VirtualReader keeps off-screen
 *     sections (and their <img>s) unmounted so this stays cheap.
 */
export function AsyncImage({ src, alt, title, className, imgAttrs }: {
  src: string;
  alt: string;
  title: string;
  className?: string;
  imgAttrs?: any;
}): React.ReactElement {
  const docId = useDocId()
  const [resolvedSrc, setResolvedSrc] = React.useState<string>(src)

  React.useEffect(() => {
    let cancelled = false
    let blobUrl: string | null = null
    ;(async () => {
      try {
        const resolved = await resolveAssetUrl(src, docId)
        if (cancelled) return
        // API-routed images go through authedFetch so the bearer
        // token reaches the server. We swap to a blob: URL so the
        // browser caches it and the <img> can decode normally.
        if (resolved.startsWith('/api/') || isDocApiPath(resolved)) {
          try {
            const res = await authedFetch(resolved)
            if (!res.ok) throw new Error(`HTTP ${res.status}`)
            const blob = await res.blob()
            if (cancelled) return
            blobUrl = URL.createObjectURL(blob)
            setResolvedSrc(blobUrl)
            return
          } catch {
            if (!cancelled) setResolvedSrc(resolved)
            return
          }
        }
        setResolvedSrc(resolved)
      } catch {
        if (!cancelled) setResolvedSrc(src)
      }
    })()
    return () => {
      cancelled = true
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [src, docId])

  return (
    <img
      {...imgAttrs}
      src={resolvedSrc}
      alt={alt}
      title={title}
      className={className}
      loading="lazy"
      decoding="async"
    />
  )
}

/**
 * Render inline elements (text, emphasis, links, images, etc.)
 */
export function renderInlines(xs: PandocInline[]): React.ReactNode {
  const out: React.ReactNode[] = []
  xs.forEach((x, i) => {
    switch (x.t) {
      case 'Str': out.push(x.c); break
      case 'Space': out.push(' '); break
      case 'SoftBreak': out.push('\n'); break
      case 'LineBreak': out.push(<br key={i} />); break
      case 'Emph': out.push(<em key={i}>{renderInlines(x.c)}</em>); break
      case 'Strong': out.push(<strong key={i}>{renderInlines(x.c)}</strong>); break
      case 'Code': {
        const [a, code] = x.c
        const codeAttrs = attrs(a)
        // Inline className wins over the @layer base `code { ... }`
        // rule, so the dark variants have to live here too — otherwise
        // inline tokens like `${ name(.attr)?(args)? }` render with a
        // light-gray fill against dark-mode body text and become
        // unreadable.
        out.push(
          <code
            key={i}
            {...codeAttrs}
            className={
              'px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 ' +
              (codeAttrs.className || '')
            }
          >
            {code}
          </code>,
        )
        break
      }
      case 'Link': {
        const [a, content, [href, title]] = x.c
        const linkAttrs = attrs(a)
        // Check if this is an internal anchor link (starts with #)
        const isInternalLink = href.startsWith('#')
        const handleClick = isInternalLink ? (e: React.MouseEvent<HTMLAnchorElement>) => {
          e.preventDefault()
          let targetId = href.slice(1) // Remove the '#'
          try {
            targetId = decodeURIComponent(targetId)
          } catch {}
          // The target ("fig:…", "tbl:…", "eq:…", a heading) may sit in a section the reader has
          // not rendered yet: reveal mounts it, then scroll the reader (not the window, which
          // does not scroll -- the reader is its own scroll container).
          void revealElement(targetId).then((el) => {
            if (el) scrollToHeading(el)
          })
        } : undefined
        out.push(
          <a
            key={i}
            {...linkAttrs}
            href={href}
            title={title}
            className={'text-blue-600 dark:text-blue-400 hover:underline cursor-pointer ' + (linkAttrs.className || '')}
            onClick={handleClick}
          >
            {renderInlines(content)}
          </a>
        )
        break
      }
      case 'Image': {
        const [a, alt, [src, title]] = x.c
        const imgAttrs = attrs(a)
        out.push(<AsyncImage key={i} imgAttrs={imgAttrs} src={src} alt={String(renderInlines(alt))} title={title} className={'max-w-full ' + (imgAttrs.className || '')} />)
        break
      }
      case 'Span': {
        const [a, content] = (x as any).c
        const spanAttrs = attrs(a)
        out.push(<span key={i} {...spanAttrs}>{renderInlines(content)}</span>)
        break
      }
      // Pandoc turns straight quotes into Quoted nodes (smart punctuation); without a case here the
      // quoted words vanished -- `Beam("MyBeam", …)` read `Beam(, …)`. The formatting nodes below
      // were dropped the same way, text and all.
      case 'Quoted': {
        const [quoteType, content] = (x as any).c
        const [open, close] = quoteType?.t === 'SingleQuote' ? ['‘', '’'] : ['“', '”']
        out.push(<React.Fragment key={i}>{open}{renderInlines(content)}{close}</React.Fragment>)
        break
      }
      case 'Superscript': out.push(<sup key={i}>{renderInlines((x as any).c)}</sup>); break
      case 'Subscript': out.push(<sub key={i}>{renderInlines((x as any).c)}</sub>); break
      case 'Strikeout': out.push(<s key={i}>{renderInlines((x as any).c)}</s>); break
      case 'Underline': out.push(<u key={i}>{renderInlines((x as any).c)}</u>); break
      case 'SmallCaps': out.push(<span key={i} style={{ fontVariant: 'small-caps' }}>{renderInlines((x as any).c)}</span>); break
      // Cite: [citations, inlines] -- the inlines are the citation as written, e.g. "[@smith, p. 3]".
      case 'Cite': out.push(<React.Fragment key={i}>{renderInlines((x as any).c[1])}</React.Fragment>); break
      case 'Math': {
        // Math: c = [{t: 'InlineMath'|'DisplayMath'}, latex_string]
        const [mathType, latex] = (x as any).c
        const isDisplay = mathType && typeof mathType === 'object' && mathType.t === 'DisplayMath'
        out.push(<MathElement key={i} latex={latex} displayMode={isDisplay} />)
        break
      }
      default:
        // Handle RawInline and other types
        if ((x as any).t === 'RawInline') {
          const [, rawContent] = (x as any).c
          if (rawContent && rawContent.includes('\\appendix')) {
            // Skip rendering this inline element
            break
          }
          out.push(<span key={i} dangerouslySetInnerHTML={{ __html: rawContent }} />)
        }
        break
    }
  })
  return out
}
