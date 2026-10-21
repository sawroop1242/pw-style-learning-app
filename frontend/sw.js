// StudySpace Service Worker - Safe offline behavior
// Cache version - increment when static assets change
const CACHE_VERSION = "v2";
const CACHE_NAME = `studyspace-${CACHE_VERSION}`;

// Static assets that are safe to cache (no auth, no private data)
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./api.js",
  "./manifest.webmanifest",
  "./assets/icon.svg"
];

// API paths that should NEVER be cached
const API_PATHS = ["/api/", "/token/", "/auth/"];

// Check if request is for an API endpoint
function isApiRequest(request) {
  const url = new URL(request.url);
  return API_PATHS.some(path => url.pathname.startsWith(path));
}

// Check if request is for a static asset we should cache
function isStaticAsset(request) {
  const url = new URL(request.url);
  return STATIC_ASSETS.some(asset => url.pathname.endsWith(asset.replace("./", "/")));
}

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(key => key.startsWith("studyspace-") && key !== CACHE_NAME)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  // Only handle GET requests
  if (event.request.method !== "GET") return;

  // NEVER cache API requests - always go to network
  if (isApiRequest(event.request)) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          // Return a proper error response, NOT the app shell
          return new Response(
            JSON.stringify({ error: "Network error. Check your connection." }),
            { status: 503, headers: { "Content-Type": "application/json" } }
          );
        })
    );
    return;
  }

  // For static assets: cache-first with network fallback
  if (isStaticAsset(event.request)) {
    event.respondWith(
      caches.match(event.request)
        .then(cached => cached || fetch(event.request)
          .then(response => {
            // Only cache successful responses
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
            }
            return response;
          })
          .catch(() => {
            // For static assets, return cached version if available
            // But don't return app shell for arbitrary paths
            return caches.match(event.request)
              .then(cached => cached || new Response("Not found", { status: 404 }));
          })
        )
    );
    return;
  }

  // For other requests (images, fonts, etc.): network-first with cache fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Notify clients when a new SW is ready
self.addEventListener("message", event => {
  if (event.data === "skipWaiting") {
    self.skipWaiting();
  }
});
