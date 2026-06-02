import React from 'react'
import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

interface DocListProps {
  // Called when the user picks a doc. Implementation updates the URL +
  // store; we keep the click handler outside so DocList stays free of
  // routing knowledge.
  onSelect: (docId: string) => void
}

interface State {
  status: 'loading' | 'ready' | 'error'
  docs: string[]
  error?: string
}

function joinUrl(base: string, path: string): string {
  return base.replace(/\/?$/, '') + path
}

export function DocList({ onSelect }: DocListProps) {
  const [state, setState] = React.useState<State>({ status: 'loading', docs: [] })

  React.useEffect(() => {
    const cfg = getRuntimeConfig()
    const apiBase = cfg.apiBase || ''
    let canceled = false
    ;(async () => {
      try {
        const res = await authedFetch(joinUrl(apiBase, '/api/docs'), { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const body = (await res.json()) as { docs: string[] }
        if (canceled) return
        setState({ status: 'ready', docs: body.docs || [] })
      } catch (err: any) {
        if (canceled) return
        setState({ status: 'error', docs: [], error: String(err?.message || err) })
      }
    })()
    return () => {
      canceled = true
    }
  }, [])

  if (state.status === 'loading') {
    return (
      <div className="flex-1 overflow-auto p-6">
        <p className="text-sm text-gray-500">Loading available documents…</p>
      </div>
    )
  }
  if (state.status === 'error') {
    return (
      <div className="flex-1 overflow-auto p-6">
        <div className="border border-red-300 rounded bg-red-50 p-4">
          <p className="text-red-600 font-semibold">Could not load document list</p>
          <p className="text-red-500 text-sm">{state.error}</p>
        </div>
      </div>
    )
  }
  if (state.docs.length === 0) {
    return (
      <div className="flex-1 overflow-auto p-6">
        <p className="text-sm text-gray-500">
          No documents are published yet. Run the example pipeline or upload a bundle.
        </p>
      </div>
    )
  }
  return (
    <div className="flex-1 overflow-auto p-6">
      <h1 className="text-xl font-semibold mb-4">Available documents</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {state.docs.map((docId) => (
          <button
            key={docId}
            onClick={() => onSelect(docId)}
            className="text-left border border-gray-300 rounded-lg p-4 bg-white hover:bg-gray-50 hover:border-gray-400 transition"
          >
            <p className="font-medium text-gray-900 break-all">{docId}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
