import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Serve config — split-chunk build for the cloud paradoc-serve image.
// Distinct from vite.config.ts (singlefile, used by `build:standalone` for
// emailable/offline doc bundles): here we let Vite emit separate JS/CSS/
// asset files so the browser can cache and parallel-load them.
export default defineConfig({
  plugins: [react()],
  build: {
    // Split per-route chunks so the heavy libs (plotly.js, katex) load
    // separately and cache independently of app code.
    rollupOptions: {
      output: {
        manualChunks: {
          plotly: ['plotly.js-dist-min'],
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
