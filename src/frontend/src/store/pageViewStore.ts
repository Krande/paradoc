import { create } from 'zustand'

// Whether the reader lays the document out on A4 sheets, the way the DOCX / PDF exports print it.
// The page view is the default; a reader's own choice is remembered per browser, like the theme.

const STORAGE_KEY = 'paradoc-page-view'
const DEFAULT_ENABLED = true

function readStored(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === null ? DEFAULT_ENABLED : stored === '1'
  } catch {
    return DEFAULT_ENABLED
  }
}

type PageViewState = {
  enabled: boolean
  toggle: () => void
}

export const usePageViewStore = create<PageViewState>((set, get) => ({
  enabled: readStored(),
  toggle: () => {
    const enabled = !get().enabled
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0')
    } catch {}
    set({ enabled })
  },
}))
