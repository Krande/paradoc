import { useEffect, useState } from 'react'

// Tri-state theme. `system` follows prefers-color-scheme live; `light`
// and `dark` pin the choice. We keep this outside zustand because the
// pre-paint script in index.html also reads the same key — using
// localStorage directly avoids a second source of truth.

export type Theme = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'paradoc-theme'

function readStored(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {}
  return 'system'
}

function applyTheme(theme: Theme): void {
  const prefersDark =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  const dark = theme === 'dark' || (theme === 'system' && prefersDark)
  const root = document.documentElement
  if (dark) root.classList.add('dark')
  else root.classList.remove('dark')
}

/** React hook returning [theme, setTheme]. Persists to localStorage and
 *  reacts to OS-level dark-mode flips when theme is 'system'. */
export function useTheme(): [Theme, (next: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(() => readStored())

  useEffect(() => {
    applyTheme(theme)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {}
  }, [theme])

  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  return [theme, setThemeState]
}
