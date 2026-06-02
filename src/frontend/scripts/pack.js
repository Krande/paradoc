// Package the built single-file HTML into a zip and copy to Python resources
// Requires devDependency: adm-zip
import fs from 'fs'
import path from 'path'
import AdmZip from 'adm-zip'

const root = path.resolve(process.cwd())
const distDir = path.join(root, 'dist')
const distIndex = path.join(distDir, 'index.html')
const outZipFrontend = path.join(distDir, 'frontend.zip')
const resourcesZip = path.resolve(root, '..', 'paradoc', 'frontend','resources', 'frontend.zip')

function ensureDir(p) {
  const dir = path.dirname(p)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

function main() {
  if (!fs.existsSync(distIndex)) {
    console.error('[pack] dist/index.html not found. Did you run "vite build"?')
    process.exit(1)
  }

  // Vite's `__vitePreload(loader, __VITE_PRELOAD__)` calls reference a
  // runtime constant that vite itself rewrites in chunks but not after
  // the singleFile inlining. With no module preload to do (single
  // bundle), patch the dist HTML to pass an empty deps array instead
  // so dynamic imports don't crash with
  // `ReferenceError: __VITE_PRELOAD__ is not defined`.
  const distHtml = fs.readFileSync(distIndex, 'utf8')
  if (distHtml.includes('__VITE_PRELOAD__')) {
    const patched = distHtml.replace(/__VITE_PRELOAD__/g, '[]')
    fs.writeFileSync(distIndex, patched)
    console.log('[pack] patched __VITE_PRELOAD__ → [] in dist/index.html')
  }

  // Create zip with everything from dist (excluding the zip itself), so workers/assets are preserved
  const zip = new AdmZip()

  // Add all files under dist, preserving paths
  const entries = fs.readdirSync(distDir)
  for (const entry of entries) {
    const full = path.join(distDir, entry)
    if (full === outZipFrontend) continue
    const stat = fs.statSync(full)
    if (stat.isFile()) {
      zip.addLocalFile(full, '')
    } else if (stat.isDirectory()) {
      zip.addLocalFolder(full, entry)
    }
  }

  zip.writeZip(outZipFrontend)
  console.log(`[pack] Wrote ${outZipFrontend}`)

  // Copy to Python resources
  ensureDir(resourcesZip)
  fs.copyFileSync(outZipFrontend, resourcesZip)
  console.log(`[pack] Copied to ${resourcesZip}`)
}

main()
