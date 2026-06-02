/// <reference lib="webworker" />

// Minimal Service Worker for sectioned static bundles
// Caches manifest and section JSON under a versioned cache name.
//
// `self` is typed as `Window` because the DOM lib is loaded for the
// rest of the SPA; the local cast pulls in the SW shape for this
// file without stomping the global declaration.

const sw = self as unknown as ServiceWorkerGlobalScope

const CACHE = 'paradoc-sections-v1'

sw.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil((async () => {
    await sw.skipWaiting?.()
  })())
})

sw.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil((async () => {
    await sw.clients?.claim?.()
    const keys = await caches.keys()
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
  })())
})

sw.addEventListener('fetch', (event: FetchEvent) => {
  const url = new URL(event.request.url)
  // Only handle our JSON endpoints
  const isManifest = /\/doc\/[^/]+\/manifest\.json$/.test(url.pathname)
  const isSection = /\/doc\/[^/]+\/section\/(.+)\.json$/.test(url.pathname)
  if (!(isManifest || isSection)) return

  event.respondWith((async () => {
    const cache = await caches.open(CACHE)
    // Network first, cache fallback for freshness; SW runs only in prod build normally
    try {
      const res = await fetch(event.request)
      // Clone and store a copy
      void cache.put(event.request, res.clone())
      return res
    } catch {
      const cached = await cache.match(event.request)
      if (cached) return cached
      throw new Error('offline and not cached')
    }
  })())
})
