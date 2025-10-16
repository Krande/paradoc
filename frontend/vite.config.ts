import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    // Ensure inlined assets
    assetsInlineLimit: 100000000,
  },
  server: {
    port: 5173,
    host: 'localhost'
  }
})
