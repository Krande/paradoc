// Pure helpers for the reader's progressive section mounting (see VirtualReader).
//
// The reader used to render every section of a document at once: on a large report that was the
// whole document's DOM -- every table, figure and 3D poster -- built, laid out and paginated
// before the first line could be read. It now mounts sections in document order as the reader
// scrolls toward them, with an estimated-height placeholder for the rest. Mounting strictly in
// order means content only ever grows *below* what has been laid out, so page numbers and scroll
// positions of everything already on screen stay exact.
//
// No DOM imports: unit-tested under plain Node.

/** Rough page count of a section, for its placeholder before it is rendered. */
export function estimatePages(blocks: unknown[]): number {
  let pages = 0
  const walk = (nodes: unknown[]) => {
    for (const n of nodes) {
      if (!n || typeof n !== 'object') continue
      const b = n as { t?: string; c?: unknown }
      switch (b.t) {
        case 'Para':
        case 'Plain':
          pages += 0.03 + textLength(b.c) / 3000
          break
        case 'Header':
          pages += 0.05
          break
        case 'Figure':
          pages += 0.4
          break
        case 'Table':
          pages += 0.1 + 0.025 * tableRows(b.c)
          break
        case 'Div':
          if (Array.isArray(b.c) && Array.isArray(b.c[1])) walk(b.c[1] as unknown[])
          break
        case 'BulletList':
        case 'OrderedList':
          pages += 0.03 + textLength(b.c) / 3000
          break
        default:
          pages += 0.03
      }
    }
  }
  walk(Array.isArray(blocks) ? blocks : [])
  return Math.max(1, Math.ceil(pages))
}

/** Characters of text under a node (Str leaves). */
function textLength(node: unknown): number {
  let n = 0
  const stack: unknown[] = [node]
  while (stack.length) {
    const x = stack.pop()
    if (Array.isArray(x)) {
      for (const y of x) stack.push(y)
    } else if (x && typeof x === 'object') {
      const o = x as { t?: string; c?: unknown }
      if (o.t === 'Str' && typeof o.c === 'string') n += o.c.length + 1
      else if (o.c !== undefined) stack.push(o.c)
    }
  }
  return n
}

/** Body rows of a Pandoc Table's content array. */
function tableRows(c: unknown): number {
  if (!Array.isArray(c)) return 0
  const bodies = c[4]
  if (!Array.isArray(bodies)) return 0
  let rows = 0
  for (const body of bodies) {
    if (Array.isArray(body) && Array.isArray(body[3])) rows += body[3].length
  }
  return rows
}

/**
 * Every anchor id in a section's blocks: Pandoc `Attr` triples `[id, [classes], [[k, v]]]` on
 * headers, figures, tables, divs, spans, images and code. Cross-reference targets live here.
 */
export function collectIds(blocks: unknown): Set<string> {
  const ids = new Set<string>()
  const stack: unknown[] = [blocks]
  while (stack.length) {
    const x = stack.pop()
    if (Array.isArray(x)) {
      if (x.length === 3 && typeof x[0] === 'string' && Array.isArray(x[1]) && Array.isArray(x[2])) {
        if (x[0]) ids.add(x[0])
      }
      for (const y of x) if (y && typeof y === 'object') stack.push(y)
    } else if (x && typeof x === 'object') {
      const o = x as { c?: unknown; attrs?: unknown }
      if (o.c && typeof o.c === 'object') stack.push(o.c)
    }
  }
  return ids
}

/**
 * How many leading sections to mount, given each unmounted section's top edge relative to the
 * bottom of the area that must be covered (viewport plus look-ahead margin): every section that
 * starts above that line. At least `mounted`; never more than `tops.length + mounted`.
 *
 * `tops[i]` is the top of section `mounted + i`, measured as `top - coverBottom` (negative =
 * inside the area). A reader who jumped far ahead sees a placeholder deep in the document; every
 * section before it is mounted in one step, so it lands on real content.
 */
export function mountTarget(mounted: number, tops: number[]): number {
  let target = mounted
  for (let i = 0; i < tops.length; i++) {
    if (tops[i] < 0) target = mounted + i + 1
    else break
  }
  return target
}
