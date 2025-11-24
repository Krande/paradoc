import React from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'

const container = document.getElementById('root')!
const root = createRoot(container)
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

// Register Service Worker in production builds
if ('serviceWorker' in navigator) {
  // Vite serves from root; sw is bundled to /sw.js after build if configured
  const url = new URL('./sw.ts', import.meta.url)
  // In dev, skip registration to avoid caching dev assets
  if (import.meta.env && import.meta.env.PROD) {
    navigator.serviceWorker.register(url).catch(() => { /* ignore */ })
  }
}
