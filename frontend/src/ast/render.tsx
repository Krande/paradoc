import React from 'react'
import type {
  PandocBlock, Plain, Para, Header, BulletList, OrderedList, CodeBlock, BlockQuote, HorizontalRule, RawBlock, Table,
} from './types'
import type { HeadingNumbering } from './headingNumbers'
import { RenderWithDocId } from './context'
import {
  renderPlain,
  renderPara,
  renderHeader,
  renderBulletList,
  renderOrderedList,
  renderCodeBlock,
  renderBlockQuote,
  renderHorizontalRule,
  renderRawBlock,
} from './basicBlockRenderers'
import { renderDiv, renderFigure, renderTable } from './complexBlockRenderers'

// Re-export context components for backward compatibility
export { RenderWithDocId }

export function renderBlock(b: PandocBlock, key?: React.Key, headingNumber?: HeadingNumbering): React.ReactElement | null {
  switch (b.t) {
    case 'Plain':
      return renderPlain(b as Plain, key)
    case 'Para':
      return renderPara(b as Para, key)
    case 'Header':
      return renderHeader(b as Header, key, headingNumber)
    case 'BulletList':
      return renderBulletList(b as BulletList, renderBlock, key)
    case 'OrderedList':
      return renderOrderedList(b as OrderedList, renderBlock, key)
    case 'CodeBlock':
      return renderCodeBlock(b as CodeBlock, key)
    case 'BlockQuote':
      return renderBlockQuote(b as BlockQuote, renderBlock, key)
    case 'HorizontalRule':
      return renderHorizontalRule(key)
    case 'RawBlock':
      return renderRawBlock(b as RawBlock, key)
    case 'Div':
      return renderDiv(b, renderBlock, key)
    case 'Figure':
      return renderFigure(b, renderBlock, key)
    case 'Table':
      return renderTable(b as Table, renderBlock, key)
    default:
      return null
  }
}

export function renderBlocks(blocks: PandocBlock[]): React.ReactNode {
  return (<>
    {blocks.map((b, i) => renderBlock(b, i))}
  </>)
}
