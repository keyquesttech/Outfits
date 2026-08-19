// Cache the shell so the app opens instantly on the LAN; always go to the
// network for API calls and photos so wardrobe data is never stale.
const CACHE = 'outfits-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icon.svg']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  // Photos: serve from cache when present, refresh in the background.
  if (url.pathname.startsWith('/photos/')) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const hit = await cache.match(request)
        const fetched = fetch(request).then((res) => {
          if (res.ok) cache.put(request, res.clone())
          return res
        }).catch(() => hit)
        return hit || fetched
      })
    )
    return
  }

  // App shell: network first, fall back to cache when the Pi is unreachable.
  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok && res.type === 'basic') {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put(request, copy))
        }
        return res
      })
      .catch(() => caches.match(request).then((hit) => hit || caches.match('/index.html')))
  )
})
