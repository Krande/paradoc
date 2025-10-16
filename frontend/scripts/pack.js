// Package the built single-file HTML into a zip and copy to Python resources
// Requires devDependency: adm-zip
import fs from 'fs'
import path from 'path'
import AdmZip from 'adm-zip'

const root = path.resolve(process.cwd())
const distIndex = path.join(root, 'dist', 'index.html')
const outZipFrontend = path.join(root, 'dist', 'frontend.zip')
const resourcesZip = path.resolve(root, '..', 'src', 'paradoc', 'resources', 'frontend.zip')

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

  // Create zip with only index.html (renamed to index.html inside zip)
  const zip = new AdmZip()
  zip.addLocalFile(distIndex, '', 'index.html')
  zip.writeZip(outZipFrontend)
  console.log(`[pack] Wrote ${outZipFrontend}`)

  // Copy to Python resources
  ensureDir(resourcesZip)
  fs.copyFileSync(outZipFrontend, resourcesZip)
  console.log(`[pack] Copied to ${resourcesZip}`)
}

main()
