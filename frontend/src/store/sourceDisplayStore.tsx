import {createContext, useContext, useState, ReactNode, JSX} from 'react'

interface SourceDisplayContextType {
  enabled: boolean
  toggleEnabled: () => void
  setEnabled: (enabled: boolean) => void
}

const SourceDisplayContext = createContext<SourceDisplayContextType | undefined>(undefined)

export function SourceDisplayProvider({ children }: { children: ReactNode }): JSX.Element {
  const [enabled, setEnabled] = useState(false)

  const toggleEnabled = () => setEnabled(prev => !prev)

  return (
    <SourceDisplayContext.Provider value={{ enabled, toggleEnabled, setEnabled }}>
      {children}
    </SourceDisplayContext.Provider>
  )
}

export function useSourceDisplayStore() {
  const context = useContext(SourceDisplayContext)
  if (!context) {
    throw new Error('useSourceDisplayStore must be used within SourceDisplayProvider')
  }
  return context
}

