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
  // Extract source metadata if present (added by Python backend)
  const sourceInfo = (b as any)._paradoc_source as { source_file?: string; source_dir?: string } | undefined

  switch (b.t) {
    case 'Plain':
      return renderPlain(b as Plain, key, sourceInfo)
    case 'Para':
      return renderPara(b as Para, key, sourceInfo)
    case 'Header':
      return renderHeader(b as Header, key, headingNumber, sourceInfo)
    case 'BulletList':
      return renderBulletList(b as BulletList, renderBlock, key, sourceInfo)
    case 'OrderedList':
      return renderOrderedList(b as OrderedList, renderBlock, key, sourceInfo)
    case 'CodeBlock':
      return renderCodeBlock(b as CodeBlock, key, sourceInfo)
    case 'BlockQuote':
      return renderBlockQuote(b as BlockQuote, renderBlock, key, sourceInfo)
    case 'HorizontalRule':
      return renderHorizontalRule(key, sourceInfo)
    case 'RawBlock':
      return renderRawBlock(b as RawBlock, key, sourceInfo)
    case 'Div':
      return renderDiv(b, renderBlock, key, sourceInfo)
    case 'Figure':
      return renderFigure(b, renderBlock, key, sourceInfo)
    case 'Table':
      return renderTable(b as Table, renderBlock, key, sourceInfo)
    default:
      return null
  }
}

export function renderBlocks(blocks: PandocBlock[]): React.ReactNode {
  return (<>
    {blocks.map((b, i) => renderBlock(b, i))}
  </>)
}
