import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  // Vite emits `__vitePreload(loader, __VITE_PRELOAD__)` at every dynamic
  // import site to fetch sibling preload dependencies. In a single-file
  // bundle (viteSingleFile) there are no siblings to preload, but the
  // `__VITE_PRELOAD__` constant is still referenced and only defined by
  // the preload-runtime chunk we don't ship — every `import('./x')`
  // crashes with `ReferenceError: __VITE_PRELOAD__ is not defined` at
  // boot. Replace it with `void 0` at compile time to no-op the deps
  // argument; the loader still runs and resolves the dynamic module
  // (which has been inlined by viteSingleFile).
  define: {
    '__VITE_PRELOAD__': '[]',
  },
  build: {
    // Ensure inlined assets
    assetsInlineLimit: 100000000,
    // Disable module preload for the same single-file reason.
    modulePreload: false,
    rollupOptions: {
      output: {
        // Force everything into a single chunk
        manualChunks: undefined,
        inlineDynamicImports: true,
      }
    }
  },
  server: {
    port: 5173,
    host: 'localhost'
  }
})
