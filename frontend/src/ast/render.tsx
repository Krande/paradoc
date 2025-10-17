import React from 'react'
import type {
  PandocBlock, PandocInline, Plain, Para, Header, BulletList, OrderedList, CodeBlock, BlockQuote, HorizontalRule, RawBlock, Attr,
} from './types'

function isAbsoluteOrData(url: string): boolean {
  return /^([a-z]+:)?\/\//i.test(url) || url.startsWith('data:')
}

function resolveAssetUrl(src: string): string {
  try {
    if (!src) return src
    if (isAbsoluteOrData(src)) return src
    const base = (window as any).__PARADOC_ASSET_BASE as string | undefined
    if (!base) return src
    const b = base.endsWith('/') ? base : base + '/'
    const s = src.startsWith('/') ? src.slice(1) : src
    return b + s
  } catch {
    return src
  }
}

function attrs(a: Attr | undefined): { id?: string; className?: string; [k: string]: string | undefined } {
  if (!a) return {}
  const { id, classes, attributes } = a
  const other: Record<string, string> = {}
  for (const k in attributes || {}) {
    const v = attributes[k]
    if (typeof v === 'string') other[k] = v
  }
  return { id: id || undefined, className: (classes || []).join(' ') || undefined, ...other }
}

function renderInlines(xs: PandocInline[]): React.ReactNode {
  const out: React.ReactNode[] = []
  xs.forEach((x, i) => {
    switch (x.t) {
      case 'Str': out.push(x.c); break
      case 'Space': out.push(' '); break
      case 'SoftBreak': out.push('\n'); break
      case 'LineBreak': out.push(<br key={i} />); break
      case 'Emph': out.push(<em key={i}>{renderInlines(x.c)}</em>); break
      case 'Strong': out.push(<strong key={i}>{renderInlines(x.c)}</strong>); break
      case 'Code': out.push(<code key={i} {...attrs(x.c[0])} className={'px-1 py-0.5 rounded bg-gray-100 ' + (x.c[0]?.classes?.join(' ') || '')}>{x.c[1]}</code>); break
      case 'Link': {
        const [a, content, [href, title]] = x.c
        out.push(<a key={i} {...attrs(a)} href={href} title={title} className={'text-blue-600 hover:underline cursor-pointer ' + (a?.classes?.join(' ') || '')}>{renderInlines(content)}</a>)
        break
      }
      case 'Image': {
        const [a, alt, [src, title]] = x.c
        const resolved = resolveAssetUrl(src)
        out.push(<img key={i} {...attrs(a)} src={resolved} alt={String(renderInlines(alt))} title={title} className={'max-w-full ' + (a?.classes?.join(' ') || '')} />)
        break
      }
      case 'Span': {
        const [a, content] = (x as any).c
        out.push(<span key={i} {...attrs(a)} className={(a?.classes?.join(' ') || undefined)}>{renderInlines(content)}</span>)
        break
      }
      default:
        out.push(null)
    }
  })
  return out
}

export function renderBlock(b: PandocBlock, key?: React.Key): React.ReactElement | null {
  switch (b.t) {
    case 'Plain':
      return <p key={key} className="my-3">{renderInlines((b as Plain).c)}</p>
    case 'Para':
      return <p key={key} className="my-3">{renderInlines((b as Para).c)}</p>
    case 'Header': {
      const [level, a, inls] = (b as Header).c
      const common = { ...attrs(a), className: `mt-6 mb-2 font-semibold ${a?.classes?.join(' ') || ''}` }
      const content = renderInlines(inls)
      if (level === 1) return <h1 key={key} {...common} className={common.className + ' text-3xl'}>{content}</h1>
      if (level === 2) return <h2 key={key} {...common} className={common.className + ' text-2xl'}>{content}</h2>
      if (level === 3) return <h3 key={key} {...common} className={common.className + ' text-xl'}>{content}</h3>
      if (level === 4) return <h4 key={key} {...common} className={common.className + ' text-lg'}>{content}</h4>
      if (level === 5) return <h5 key={key} {...common} className={common.className + ' text-base'}>{content}</h5>
      return <h6 key={key} {...common} className={common.className + ' text-sm'}>{content}</h6>
    }
    case 'BulletList': {
      const items = (b as BulletList).c
      return <ul key={key} className="list-disc ml-6 my-2">{items.map((blocks, i) => <li key={i}>{blocks.map((bb, j) => renderBlock(bb, j))}</li>)}</ul>
    }
    case 'OrderedList': {
      const [, items] = (b as OrderedList).c
      return <ol key={key} className="list-decimal ml-6 my-2">{items.map((blocks, i) => <li key={i}>{blocks.map((bb, j) => renderBlock(bb, j))}</li>)}</ol>
    }
    case 'CodeBlock': {
      const [a, code] = (b as CodeBlock).c
      return (
        <pre key={key} {...attrs(a)} className={'my-3 p-3 rounded bg-gray-100 overflow-auto text-sm ' + (a?.classes?.join(' ') || '')}>
          <code>{code}</code>
        </pre>
      )
    }
    case 'BlockQuote':
      return <blockquote key={key} className="border-l-4 pl-4 my-3 text-gray-700">{(b as BlockQuote).c.map((bb, j) => renderBlock(bb, j))}</blockquote>
    case 'HorizontalRule':
      return <hr key={key} className="my-6" />
    case 'RawBlock': {
      const [, html] = (b as RawBlock).c
      return <div key={key} dangerouslySetInnerHTML={{ __html: html }} />
    }
    case 'Div': {
      const [a, blocks] = (b as any).c as [Attr, PandocBlock[]]
      const classList = a?.classes || []
      if (classList.includes('figure')) {
        // Basic figure styling; render children and allow captions to flow
        return (
          <figure key={key} {...attrs(a)} className={'my-4 ' + (a?.classes?.join(' ') || '')}>
            {blocks.map((bb, j) => renderBlock(bb, j))}
          </figure>
        )
      }
      return <div key={key} {...attrs(a)}>{blocks.map((bb, j) => renderBlock(bb, j))}</div>
    }
    case 'Figure': {
      // Pandoc v3+ Figure block: c = [Attr, [ShortCaption|null, [Blocks caption]], [Blocks content]]
      const [a, cap, content] = (b as any).c as [Attr, any, PandocBlock[]]
      const captionBlocks: any[] = (cap && Array.isArray(cap) && Array.isArray(cap[1])) ? cap[1] : []
      // Extract inlines from first caption block if present
      let captionInlines: any[] = []
      if (captionBlocks.length > 0) {
        const firstCap = captionBlocks[0]
        // Supports { t: 'Plain'|'Para', c: [inlines...] } and list-form
        if (firstCap && typeof firstCap === 'object') {
          if (Array.isArray(firstCap)) {
            // list-form, [ 'Plain', inlines ]
            captionInlines = (firstCap.length > 1 && Array.isArray(firstCap[1])) ? firstCap[1] : []
          } else if ('t' in firstCap) {
            captionInlines = Array.isArray((firstCap as any).c) ? (firstCap as any).c : []
          }
        }
      }
      return (
        <figure key={key} {...attrs(a)} className={'my-4 ' + (a as any)?.classes?.join(' ') || ''}>
          {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb as any, j)) : null}
          {captionInlines && captionInlines.length > 0 ? (
            <figcaption className="text-sm text-gray-600 italic mt-2">
              {renderInlines(captionInlines as any)}
            </figcaption>
          ) : null}
        </figure>
      )
    }
    default:
      return null
  }
}

export function renderBlocks(blocks: PandocBlock[]): React.ReactNode {
  return (<>
    {blocks.map((b, i) => renderBlock(b, i))}
  </>)
}
