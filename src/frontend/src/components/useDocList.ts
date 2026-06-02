import React from 'react'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

interface DocGroup {
  key: string
  label: string
  docs: string[]
}

interface DocsResponse {
  docs?: string[]
  groups?: DocGroup[]
}

export interface DocList {
  loaded: boolean
  groups: DocGroup[]
  flat: string[]
  /** Convenience: union of all doc IDs across groups, deduped + ordered. */
  allDocs: string[]
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

// Single source of truth for the /api/docs fetch. DocSwitcher and the
// mobile OverflowMenu both need this list; sharing the hook keeps them
// from racing two parallel requests on every page load.
export function useDocList(): DocList {
  const [groups, setGroups] = React.useState<DocGroup[]>([])
  const [flat, setFlat] = React.useState<string[]>([])
  const [loaded, setLoaded] = React.useState(false)

  React.useEffect(() => {
    const cfg = getRuntimeConfig()
    if (cfg.transport !== 'rest') {
      setLoaded(true)
      return
    }
    let canceled = false
    ;(async () => {
      try {
        const res = await authedFetch(joinUrl(cfg.apiBase || '', '/api/docs'), { cache: 'no-store' })
        if (!res.ok) return
        const body = (await res.json()) as DocsResponse
        if (canceled) return
        setGroups(body.groups || [])
        setFlat(body.docs || [])
      } catch {
        // Silent — consumers handle the empty-state.
      } finally {
        if (!canceled) setLoaded(true)
      }
    })()
    return () => {
      canceled = true
    }
  }, [])

  const allDocs = React.useMemo(() => {
    if (groups.length === 0) return flat
    const seen = new Set<string>()
    const out: string[] = []
    for (const g of groups) {
      for (const id of g.docs) {
        if (!seen.has(id)) {
          seen.add(id)
          out.push(id)
        }
      }
    }
    return out
  }, [groups, flat])

  return { loaded, groups, flat, allDocs }
}
