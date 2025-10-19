import React from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import type { PandocInline } from './types'
import { attrs, resolveAssetUrl } from './utils'
import { useDocId } from './context'

/**
 * Component to render LaTeX math using KaTeX
 */
export function MathElement({ latex, displayMode }: { latex: string; displayMode: boolean }): React.ReactElement {
  const elementRef = React.useRef<HTMLSpanElement>(null)

  React.useEffect(() => {
    if (elementRef.current) {
      try {
        katex.render(latex, elementRef.current, {
          displayMode,
          throwOnError: false,
          errorColor: '#cc0000',
          strict: false,
        })
      } catch (error) {
        console.error('KaTeX rendering error:', error)
        // Fallback: show the raw LaTeX if rendering fails
        if (elementRef.current) {
          elementRef.current.textContent = displayMode ? `\\[${latex}\\]` : `\\(${latex}\\)`
        }
      }
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
 * Component to render an image with async URL resolution (checks IndexedDB first)
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
    resolveAssetUrl(src, docId).then(setResolvedSrc).catch(() => setResolvedSrc(src))
  }, [src, docId])

  return <img {...imgAttrs} src={resolvedSrc} alt={alt} title={title} className={className} />
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
        out.push(<code key={i} {...codeAttrs} className={'px-1 py-0.5 rounded bg-gray-100 ' + (codeAttrs.className || '')}>{code}</code>)
        break
      }
      case 'Link': {
        const [a, content, [href, title]] = x.c
        const linkAttrs = attrs(a)
        // Check if this is an internal anchor link (starts with #)
        const isInternalLink = href.startsWith('#')
        const handleClick = isInternalLink ? (e: React.MouseEvent<HTMLAnchorElement>) => {
          e.preventDefault()
          const targetId = href.slice(1) // Remove the '#'
          // Use querySelector with attribute selector to handle IDs with special characters like colons
          // This works reliably for IDs like "tbl:table-name", "fig:figure-name", "eq:equation-name"
          const el = document.querySelector(`[id="${targetId}"]`) as HTMLElement | null
          if (el) {
            const topbar = document.getElementById('paradoc-topbar')
            const offset = topbar ? topbar.getBoundingClientRect().height : 0
            const top = window.scrollY + el.getBoundingClientRect().top - offset - 8
            window.scrollTo({ top, behavior: 'smooth' })
          }
        } : undefined
        out.push(
          <a
            key={i}
            {...linkAttrs}
            href={href}
            title={title}
            className={'text-blue-600 hover:underline cursor-pointer ' + (linkAttrs.className || '')}
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
