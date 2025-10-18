import React from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import type {
  PandocBlock, PandocInline, Plain, Para, Header, BulletList, OrderedList, CodeBlock, BlockQuote, HorizontalRule, RawBlock, Attr, Table,
} from './types'
import type { HeadingNumbering } from './headingNumbers'

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

  // Handle both array form [id, classes, attributes] and object form {id, classes, attributes}
  let id: string | undefined
  let classes: string[] = []
  let attributes: Record<string, any> = {}

  if (Array.isArray(a)) {
    // Array form: [id, [classes], {attributes}]
    id = (a[0] && typeof a[0] === 'string') ? a[0] : undefined
    classes = (Array.isArray(a[1])) ? a[1] : []
    attributes = (a[2] && typeof a[2] === 'object') ? a[2] : {}
  } else {
    // Object form: {id, classes, attributes}
    id = a.id
    classes = a.classes || []
    attributes = a.attributes || {}
  }

  const other: Record<string, string> = {}
  for (const k in attributes || {}) {
    const v = attributes[k]
    if (typeof v === 'string') other[k] = v
  }

  return {
    id: id || undefined,
    className: (classes || []).join(' ') || undefined,
    ...other
  }
}

/**
 * Component to render LaTeX math using KaTeX
 */
function MathElement({ latex, displayMode }: { latex: string; displayMode: boolean }): React.ReactElement {
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
            {...attrs(a)}
            href={href}
            title={title}
            className={'text-blue-600 hover:underline cursor-pointer ' + (a?.classes?.join(' ') || '')}
            onClick={handleClick}
          >
            {renderInlines(content)}
          </a>
        )
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
      case 'Math': {
        // Math: c = [{t: 'InlineMath'|'DisplayMath'}, latex_string]
        const [mathType, latex] = (x as any).c
        const isDisplay = mathType && typeof mathType === 'object' && mathType.t === 'DisplayMath'
        out.push(<MathElement key={i} latex={latex} displayMode={isDisplay} />)
        break
      }
      case 'RawInline': {
        // Filter out \appendix LaTeX commands - they're used internally to mark appendix sections
        // but should not be rendered in the frontend
        const [, rawContent] = (x as any).c
        if (rawContent && typeof rawContent === 'string' && rawContent.includes('\\appendix')) {
          // Skip rendering this inline element
          break
        }
        out.push(<span key={i} dangerouslySetInnerHTML={{ __html: rawContent }} />)
        break
      }
      default:
        out.push(null)
    }
  })
  return out
}

export function renderBlock(b: PandocBlock, key?: React.Key, headingNumber?: HeadingNumbering): React.ReactElement | null {
  switch (b.t) {
    case 'Plain':
      return <p key={key} className="my-3">{renderInlines((b as Plain).c)}</p>
    case 'Para': {
      // Filter out paragraphs containing only \appendix
      const inlines = (b as Para).c
      if (inlines.length === 1 && inlines[0].t === 'Str' && inlines[0].c === '\\appendix') {
        return null
      }
      return <p key={key} className="my-3">{renderInlines(inlines)}</p>
    }
    case 'Header': {
      const [level, a, inls] = (b as Header).c
      const common = { ...attrs(a), className: `mt-6 mb-2 font-semibold ${a?.classes?.join(' ') || ''}` }
      const content = renderInlines(inls)
      const numberedContent = headingNumber ? (
        <>
          <span className="mr-2">{headingNumber.fullText}</span>
          {content}
        </>
      ) : content

      if (level === 1) return <h1 key={key} {...common} className={common.className + ' text-3xl'}>{numberedContent}</h1>
      if (level === 2) return <h2 key={key} {...common} className={common.className + ' text-2xl'}>{numberedContent}</h2>
      if (level === 3) return <h3 key={key} {...common} className={common.className + ' text-xl'}>{numberedContent}</h3>
      if (level === 4) return <h4 key={key} {...common} className={common.className + ' text-lg'}>{numberedContent}</h4>
      if (level === 5) return <h5 key={key} {...common} className={common.className + ' text-base'}>{numberedContent}</h5>
      return <h6 key={key} {...common} className={common.className + ' text-sm'}>{numberedContent}</h6>
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
      // Filter out \appendix LaTeX commands - they're used internally to mark appendix sections
      // but should not be rendered in the frontend
      if (html && typeof html === 'string' && html.includes('\\appendix')) {
        return null
      }
      return <div key={key} dangerouslySetInnerHTML={{ __html: html }} />
    }
    case 'Div': {
      const [a, blocks] = (b as any).c as [Attr, PandocBlock[]]
      const classList = a?.classes || []
      if (classList.includes('figure')) {
        // Basic figure styling; render children and allow captions to flow
        const figAttrs = attrs(a)
        const className = ['my-4', ...(a?.classes || [])].filter(Boolean).join(' ')
        return (
          <figure key={key} {...figAttrs} className={className}>
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
      const figAttrs = attrs(a)
      const className = ['my-4', ...(a?.classes || [])].filter(Boolean).join(' ')
      return (
        <figure key={key} {...figAttrs} className={className}>
          {Array.isArray(content) ? content.map((bb, j) => renderBlock(bb as any, j)) : null}
          {captionInlines && captionInlines.length > 0 ? (
            <figcaption className="text-sm text-gray-600 italic mt-2">
              {renderInlines(captionInlines as any)}
            </figcaption>
          ) : null}
        </figure>
      )
    }
    case 'Table': {
      // Table: [Attr, Caption, [ColSpec], TableHead, [TableBody], TableFoot]
      const [a, caption, colSpecs, tableHead, tableBodies, tableFoot] = (b as Table).c

      // Extract caption text if present
      let captionInlines: any[] = []
      if (caption && Array.isArray(caption)) {
        // Caption structure: [ShortCaption|null, [Blocks]]
        const captionBlocks = (Array.isArray(caption[1])) ? caption[1] : []
        if (captionBlocks.length > 0) {
          const firstBlock = captionBlocks[0]
          if (firstBlock && typeof firstBlock === 'object' && 't' in firstBlock && Array.isArray(firstBlock.c)) {
            captionInlines = firstBlock.c
          }
        }
      }

      // Helper to render table cells
      const renderCell = (cell: any, cellKey: number, isHeader = false) => {
        // Cell structure: [Attr, Alignment, RowSpan, ColSpan, [Blocks]]
        if (!cell || !Array.isArray(cell)) return null
        const [cellAttr, , rowSpan, colSpan, cellBlocks] = cell
        const cellAttrs = attrs(cellAttr)
        const content = Array.isArray(cellBlocks) ? cellBlocks.map((bb: any, i: number) => renderBlock(bb, i)) : null
        const className = isHeader
          ? 'px-3 py-2 bg-gray-100 font-semibold text-left border border-gray-300'
          : 'px-3 py-2 border border-gray-300'

        const Tag = isHeader ? 'th' : 'td'
        return (
          <Tag
            key={cellKey}
            {...cellAttrs}
            className={className + (cellAttrs.className ? ' ' + cellAttrs.className : '')}
            rowSpan={rowSpan > 1 ? rowSpan : undefined}
            colSpan={colSpan > 1 ? colSpan : undefined}
          >
            {content}
          </Tag>
        )
      }

      // Helper to render table rows
      const renderRow = (row: any, rowKey: number, isHeader = false) => {
        // Row structure: [Attr, [Cell]]
        if (!row || !Array.isArray(row)) return null
        const [rowAttr, cells] = row
        const rowAttrs = attrs(rowAttr)
        return (
          <tr key={rowKey} {...rowAttrs}>
            {Array.isArray(cells) ? cells.map((cell: any, i: number) => renderCell(cell, i, isHeader)) : null}
          </tr>
        )
      }

      const tableAttrs = attrs(a)

      return (
        <div key={key} className="my-4 overflow-x-auto">
          <table
            {...tableAttrs}
            className={'min-w-full border-collapse border border-gray-300 ' + (tableAttrs.className || '')}
          >
            {tableHead && Array.isArray(tableHead) && tableHead.length > 1 && Array.isArray(tableHead[1]) && tableHead[1].length > 0 ? (
              <thead>
                {tableHead[1].map((row: any, i: number) => renderRow(row, i, true))}
              </thead>
            ) : null}
            {Array.isArray(tableBodies) && tableBodies.length > 0 ? (
              <tbody>
                {tableBodies.map((tbody: any, tbodyIdx: number) => {
                  // TableBody: [Attr, RowHeadColumns, [HeaderRow], [BodyRow]]
                  if (!Array.isArray(tbody) || tbody.length < 4) return null
                  const [, , headerRows, bodyRows] = tbody
                  return (
                    <React.Fragment key={tbodyIdx}>
                      {Array.isArray(headerRows) ? headerRows.map((row: any, i: number) => renderRow(row, `tbody-${tbodyIdx}-h-${i}`, true)) : null}
                      {Array.isArray(bodyRows) ? bodyRows.map((row: any, i: number) => renderRow(row, `tbody-${tbodyIdx}-b-${i}`, false)) : null}
                    </React.Fragment>
                  )
                })}
              </tbody>
            ) : null}
            {tableFoot && Array.isArray(tableFoot) && tableFoot.length > 1 && Array.isArray(tableFoot[1]) && tableFoot[1].length > 0 ? (
              <tfoot>
                {tableFoot[1].map((row: any, i: number) => renderRow(row, i, false))}
              </tfoot>
            ) : null}
          </table>
          {captionInlines && captionInlines.length > 0 ? (
            <div className="text-sm text-gray-600 italic mt-2 text-center">
              {renderInlines(captionInlines)}
            </div>
          ) : null}
        </div>
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
