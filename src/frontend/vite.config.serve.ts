import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Serve config — split-chunk build for the cloud paradoc-serve image.
// Distinct from vite.config.ts (singlefile, used by `build:standalone` for
// emailable/offline doc bundles): here we let Vite emit separate JS/CSS/
// asset files so the browser can cache and parallel-load them.
export default defineConfig({
  plugins: [react()],
  build: {
    // Split per-route chunks so heavy libs load separately and cache
    // independently of app code. plotly is intentionally NOT pinned —
    // PlotRenderer dynamic-imports it, and a manualChunks pin forces
    // it into the entry's modulepreload hints, defeating the
    // lazy-load. Letting Rollup chunk it via the dynamic import keeps
    // ~1.5 MiB gz off the critical path.
    rollupOptions: {
      output: {
        manualChunks: {
          katex: ['katex'],
          react: ['react', 'react-dom'],
        },
      },
    },
  },
  server: {
    port: 5173,
    host: 'localhost',
  },
})
