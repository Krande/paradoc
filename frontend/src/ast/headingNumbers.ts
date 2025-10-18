import type { SectionMeta } from './types'

export interface HeadingNumbering {
  number: string // e.g., "1.1", "A.2", etc.
  prefix: string // e.g., "", "APPENDIX "
  fullText: string // e.g., "1.1", "APPENDIX A.1"
}

/**
 * Calculate heading numbers for all sections in the manifest.
 *
 * Rules:
 * - Regular sections: 1, 1.1, 1.1.1, etc.
 * - Appendix sections: A, A.1, A.1.1, etc. with "APPENDIX " prefix
 *
 * @param sections All sections from the manifest
 * @returns Map of section id to heading numbering
 */
export function calculateHeadingNumbers(sections: SectionMeta[]): Map<string, HeadingNumbering> {
  const result = new Map<string, HeadingNumbering>()

  // Track numbering state
  const regularCounters: number[] = [0, 0, 0, 0, 0, 0] // For levels 1-6
  const appendixCounters: number[] = [0, 0, 0, 0, 0, 0] // For levels 1-6
  let inAppendix = false

  for (const section of sections) {
    const isAppendix = section.isAppendix === true
    const level = section.level

    // Check if we're transitioning into appendix
    if (isAppendix && !inAppendix) {
      inAppendix = true
    }

    // Use appropriate counter array
    const counters = isAppendix ? appendixCounters : regularCounters

    // Increment the counter for this level
    counters[level - 1]++

    // Reset all deeper levels
    for (let i = level; i < counters.length; i++) {
      counters[i] = 0
    }

    // Build the number string
    let number: string
    if (isAppendix && level === 1) {
      // Top-level appendix: A, B, C, etc.
      number = String.fromCharCode(64 + counters[0]) // 65 = 'A'
    } else {
      // Build hierarchical number
      const parts: string[] = []
      for (let i = 0; i < level; i++) {
        if (isAppendix && i === 0) {
          // First level in appendix uses letters
          parts.push(String.fromCharCode(64 + counters[i]))
        } else {
          parts.push(String(counters[i]))
        }
      }
      number = parts.join('.')
    }

    const prefix = isAppendix ? 'APPENDIX ' : ''
    const fullText = prefix + number

    result.set(section.id, { number, prefix, fullText })
  }

  return result
}

