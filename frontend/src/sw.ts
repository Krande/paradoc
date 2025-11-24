// Minimal Service Worker for sectioned static bundles
// Caches manifest and section JSON under a versioned cache name.

const CACHE = 'paradoc-sections-v1'

self.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil((async () => {
    // Activate immediately
    // @ts-expect-error skipWaiting exists in SW context
    await self.skipWaiting?.()
  })())
})

self.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil((async () => {
    // @ts-expect-error clients in SW context
    await self.clients?.claim?.()
    // Cleanup old caches
    const keys = await caches.keys()
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
  })())
})

self.addEventListener('fetch', (event: FetchEvent) => {
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
