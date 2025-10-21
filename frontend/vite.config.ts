import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    // Ensure inlined assets
    assetsInlineLimit: 100000000,
    // Disable module preload polyfill which doesn't work with file:// protocol
    modulePreload: {
      polyfill: false
    },
    rollupOptions: {
      output: {
        // Force everything into a single chunk
        manualChunks: undefined,
      }
    }
  },
  server: {
    port: 5173,
    host: 'localhost'
  }
})
