import React from 'react'

// Create a context to pass docId through the render tree
const DocIdContext = React.createContext<string | undefined>(undefined)

export function RenderWithDocId({ docId, children }: { docId?: string; children: React.ReactNode }) {
  return <DocIdContext.Provider value={docId}>{children}</DocIdContext.Provider>
}

export function useDocId() {
  return React.useContext(DocIdContext)
}

