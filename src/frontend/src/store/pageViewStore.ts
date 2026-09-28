import { create } from 'zustand'

// Whether the reader lays the document out on A4 sheets, the way the DOCX / PDF exports print it.
// Remembered per browser, like the theme.

const STORAGE_KEY = 'paradoc-page-view'

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
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
