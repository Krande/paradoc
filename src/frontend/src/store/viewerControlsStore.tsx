import { createContext, useContext, useState, useEffect, ReactNode, JSX } from 'react'

interface ViewerControlsContextType {
  enabled: boolean
  toggleEnabled: () => void
  setEnabled: (enabled: boolean) => void
}

const ViewerControlsContext = createContext<ViewerControlsContextType | undefined>(undefined)

const STORAGE_KEY = 'paradoc:viewer-controls-enabled'

// Persisted across reloads via localStorage so the user's preference
// survives navigation. Defaults to on — discovering the controls is
// the point; an opt-out is friendlier than an opt-in.
export function ViewerControlsProvider({ children }: { children: ReactNode }): JSX.Element {
  const [enabled, setEnabled] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(STORAGE_KEY)
      if (v === 'false') return false
    } catch {}
    return true
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false')
    } catch {}
  }, [enabled])

  const toggleEnabled = () => setEnabled((prev) => !prev)

  return (
    <ViewerControlsContext.Provider value={{ enabled, toggleEnabled, setEnabled }}>
      {children}
    </ViewerControlsContext.Provider>
  )
}

export function useViewerControlsStore() {
  const ctx = useContext(ViewerControlsContext)
  if (!ctx) {
    throw new Error('useViewerControlsStore must be used within ViewerControlsProvider')
  }
  return ctx
}
