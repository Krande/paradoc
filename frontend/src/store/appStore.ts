import { create } from 'zustand'
import type { TocItem } from '../components/Navbar'

interface ProcessInfo {
  pid: number
  thread_id: number
}

interface AppState {
  connected: boolean
  sidebarOpen: boolean
  searchBarOpen: boolean
  processInfo: ProcessInfo | null
  frontendId: string
  connectedFrontends: string[]
  logFilePath: string
  docId: string
  toc: TocItem[]

  setConnected: (connected: boolean) => void
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  setSearchBarOpen: (open: boolean) => void
  setProcessInfo: (info: ProcessInfo | null) => void
  setFrontendId: (id: string) => void
  setConnectedFrontends: (ids: string[]) => void
  setLogFilePath: (path: string) => void
  setDocId: (id: string) => void
  setToc: (toc: TocItem[]) => void
}

export const useAppStore = create<AppState>((set) => ({
  connected: false,
  sidebarOpen: false,
  searchBarOpen: false,
  processInfo: null,
  frontendId: '',
  connectedFrontends: [],
  logFilePath: '',
  docId: 'demo',
  toc: [],

  setConnected: (connected) => set({ connected }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSearchBarOpen: (searchBarOpen) => set({ searchBarOpen }),
  setProcessInfo: (processInfo) => set({ processInfo }),
  setFrontendId: (frontendId) => set({ frontendId }),
  setConnectedFrontends: (connectedFrontends) => set({ connectedFrontends }),
  setLogFilePath: (logFilePath) => set({ logFilePath }),
  setDocId: (docId) => set({ docId }),
  setToc: (toc) => set({ toc }),
}))
