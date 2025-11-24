// Package the built single-file HTML into a zip and copy to Python resources
// Requires devDependency: adm-zip
import fs from 'fs'
import path from 'path'
import AdmZip from 'adm-zip'

const root = path.resolve(process.cwd())
const distDir = path.join(root, 'dist')
const distIndex = path.join(distDir, 'index.html')
const outZipFrontend = path.join(distDir, 'frontend.zip')
const resourcesZip = path.resolve(root, '..', 'src', 'paradoc', 'frontend','resources', 'frontend.zip')

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
