// Minimal Pandoc JSON AST type declarations for core nodes we render
// See: https://pandoc.org/lua-filters.html for structure; we model a pragmatic subset.

export type PandocInline = Str | Space | SoftBreak | LineBreak | Emph | Strong | Code | Link | Image | Span | Math
export type PandocBlock = Para | Plain | Figure | Header | BulletList | OrderedList | CodeBlock | BlockQuote | HorizontalRule | RawBlock | Div | Table

// Attr can be in object form {id, classes, attributes} or array form [id, [classes], {attributes}]
export type Attr = AttrObject | AttrArray

export interface AttrObject {
  id: string
  classes: string[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  attributes: Record<string, any>
}

// Array form: [id, [classes], {attributes}]
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AttrArray = [string, string[], Record<string, any>]

export interface Str { t: 'Str'; c: string }
export interface Space { t: 'Space' }
export interface SoftBreak { t: 'SoftBreak' }
export interface LineBreak { t: 'LineBreak' }
export interface Emph { t: 'Emph'; c: PandocInline[] }
export interface Strong { t: 'Strong'; c: PandocInline[] }
export interface Code { t: 'Code'; c: [Attr, string] }
export interface Link { t: 'Link'; c: [Attr, PandocInline[], [string, string]] }
export interface Image { t: 'Image'; c: [Attr, PandocInline[], [string, string]] }
export interface Span { t: 'Span'; c: [Attr, PandocInline[]] }
export interface Math { t: 'Math'; c: [{ t: string }, string] }

export interface Plain { t: 'Plain'; c: PandocInline[] }
export interface Para { t: 'Para'; c: PandocInline[] }
export interface Header { t: 'Header'; c: [number, Attr, PandocInline[]] }
export interface BulletList { t: 'BulletList'; c: (PandocBlock[])[] }
export interface OrderedList { t: 'OrderedList'; c: [[number, string, string], (PandocBlock[])[]] }
export interface CodeBlock { t: 'CodeBlock'; c: [Attr, string] }
export interface BlockQuote { t: 'BlockQuote'; c: PandocBlock[] }
export interface HorizontalRule { t: 'HorizontalRule' }
export interface RawBlock { t: 'RawBlock'; c: [string, string] }
export interface Div { t: 'Div'; c: [Attr, PandocBlock[]] }

// Table structure in Pandoc JSON
// Table: [Attr, Caption, [ColSpec], TableHead, [TableBody], TableFoot]
export interface Table {
  t: 'Table'
  c: [
    Attr, // table attributes
    any, // caption
    any[], // column specifications
    any, // table head
    any[], // table bodies
    any // table foot
  ]
}

export interface PandocDocument {
  // top-level Pandoc JSON: { pandoc-api-version: [..], meta: {}, blocks: [...] }
  'pandoc-api-version'?: unknown
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  meta?: Record<string, any>
  blocks: PandocBlock[]
}

export interface SectionMeta {
  id: string // section id (e.g., h1 anchor)
  title: string
  index: number // ordering in the document
  level: number // header level of the section root
  isAppendix?: boolean // whether this section is in the appendix
}

export interface SectionBundle {
  section: SectionMeta
  doc: PandocDocument // blocks limited to the section
}

export interface DocManifest {
  docId: string
  sections: SectionMeta[]
  assetBase?: string // optional: base URL for resolving relative asset paths
  // Optional additional data like cross-ref registry can be added later
}
