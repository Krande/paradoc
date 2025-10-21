import React from 'react'
import type { Plain, Para, Header, BulletList, OrderedList, CodeBlock, BlockQuote, RawBlock, PandocInline } from './types'
import type { HeadingNumbering } from './headingNumbers'
import { attrs } from './utils'
import { renderInlines } from './inlineRenderers'
import { PlotRenderer } from '../components/PlotRenderer'
import { TableRenderer } from '../components/TableRenderer'
import { useDocId } from './context'
import { SourceBadge } from "../components/SourceBadge"

/**
 * Component to detect and render plot/table references in paragraph content
 */
function InteractiveParagraph({ inlines }: { inlines: PandocInline[] }) {
  const docId = useDocId()

  // Check if paragraph contains a plot or table reference
  // Pattern: {{__key__}} optionally followed by {plt:...} or {tbl:...}
  const text = inlines.map(x => x.t === 'Str' ? x.c : x.t === 'Space' ? ' ' : '').join('')

  // Match plot references: {{__plot_key__}} with optional {plt:...} annotation
  const plotMatch = text.match(/\{\{__([^_][^}]*)__}}(?:\{plt:[^}]*})?/)
  if (plotMatch) {
    const plotKey = plotMatch[1]
      return <SourceBadge><PlotRenderer plotKey={plotKey} docId={docId} /></SourceBadge>
  }

  // Match table references: {{__table_key__}} with optional {tbl:...} annotation
  const tableMatch = text.match(/\{\{__([^_][^}]*)__}}(?:\{tbl:[^}]*})?/)
  if (tableMatch) {
    const tableKey = tableMatch[1]
      return <SourceBadge><TableRenderer tableKey={tableKey} docId={docId} /></SourceBadge>
  }

  // Regular paragraph - no interactive content
    return <SourceBadge><p className="my-3">{renderInlines(inlines)}</p></SourceBadge>
}

/**
 * Render a Plain block (paragraph without margins)
 */
export function renderPlain(b: Plain, key?: React.Key): React.ReactElement {
    return <SourceBadge><p key={key} className="my-3">{renderInlines(b.c)}</p></SourceBadge>
}

/**
 * Render a Para block (standard paragraph)
 */
export function renderPara(b: Para, key?: React.Key): React.ReactElement | null {
  const inlines = b.c
  // Filter out paragraphs containing only \appendix
  if (inlines.length === 1 && inlines[0].t === 'Str' && inlines[0].c === '\\appendix') {
    return null
  }
  // Check for plot/table references - wrap in a div with the key
    return <SourceBadge><div key={key}><InteractiveParagraph inlines={inlines} /></div></SourceBadge>
}

/**
 * Render a Header block (h1-h6)
 */
export function renderHeader(b: Header, key?: React.Key, headingNumber?: HeadingNumbering): React.ReactElement {
  const [level, a, inls] = b.c
  const headerAttrs = attrs(a)
  const common = { ...headerAttrs, className: `mt-6 mb-2 font-semibold ${headerAttrs.className || ''}` }
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
    return <SourceBadge><h6 key={key} {...common} className={common.className + ' text-sm'}>{numberedContent}</h6></SourceBadge>
}

/**
 * Render a BulletList block
 */
export function renderBulletList(b: BulletList, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
  const items = b.c
    return <SourceBadge><ul key={key} className="list-disc ml-6 my-2">{items.map((blocks, i) => <li key={i}>{blocks.map((bb, j) => renderBlock(bb, j))}</li>)}</ul></SourceBadge>
}

/**
 * Render an OrderedList block
 */
export function renderOrderedList(b: OrderedList, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
  const [, items] = b.c
    return <SourceBadge><ol key={key} className="list-decimal ml-6 my-2">{items.map((blocks, i) => <li key={i}>{blocks.map((bb, j) => renderBlock(bb, j))}</li>)}</ol></SourceBadge>
}

/**
 * Render a CodeBlock
 */
export function renderCodeBlock(b: CodeBlock, key?: React.Key): React.ReactElement {
  const [a, code] = b.c
  const codeAttrs = attrs(a)
  return (
    <SourceBadge><pre key={key} {...codeAttrs} className={'my-3 p-3 rounded bg-gray-100 overflow-auto text-sm ' + (codeAttrs.className || '')}>
      <code>{code}</code>
    </pre></SourceBadge>
  )
}

/**
 * Render a BlockQuote
 */
export function renderBlockQuote(b: BlockQuote, renderBlock: (b: any, k?: React.Key, hn?: HeadingNumbering) => React.ReactElement | null, key?: React.Key): React.ReactElement {
    return <SourceBadge><blockquote key={key} className="border-l-4 pl-4 my-3 text-gray-700">{b.c.map((bb, j) => renderBlock(bb, j))}</blockquote></SourceBadge>
}

/**
 * Render a HorizontalRule
 */
export function renderHorizontalRule(key?: React.Key): React.ReactElement {
    return <SourceBadge><hr key={key} className="my-6" /></SourceBadge>
}

/**
 * Render a RawBlock
 */
export function renderRawBlock(b: RawBlock, key?: React.Key): React.ReactElement | null {
  const [, html] = b.c
  // Filter out \appendix LaTeX commands - they're used internally to mark appendix sections
  // but should not be rendered in the frontend
  if (html.includes('\\appendix')) {
    return null
  }
    return <SourceBadge><div key={key} dangerouslySetInnerHTML={{ __html: html }} /></SourceBadge>
}
