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

// Zoom of the A4 sheets. `null` fits a sheet to the reader's width (never above 100 %), which is
// what a phone needs: a 210 mm sheet is about twice a phone's width, and the browser's own pinch
// zoom cannot go below the device width to show it whole. Not remembered: fit is the right start.
export const MIN_ZOOM = 0.25
export const MAX_ZOOM = 3
export const clampZoom = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))

type PageViewState = {
  enabled: boolean
  toggle: () => void
  /** Sheet scale, or null to fit the sheet to the reader's width. */
  zoom: number | null
  setZoom: (zoom: number | null) => void
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
  zoom: null,
  setZoom: (zoom) => set({ zoom: zoom === null ? null : clampZoom(zoom) }),
}))
