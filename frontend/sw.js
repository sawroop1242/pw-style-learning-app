/* StudySpace service worker — offline shell, never caches student data.
 *
 * Strategy
 *   • Navigations + HTML  : network-first, fall back to cache, then offline.html
 *   • CSS / JS / icons    : network-first, so a deploy never pairs new HTML with
 *                           last release's stylesheet; cache is the offline fallback
 *   • API requests        : never cached, never served from cache
 *
 * Bump CACHE_VERSION whenever a shell asset changes so old clients refresh.
 */

const CACHE_VERSION = 'studyspace-v11';
const SHELL = [
  './',
  './index.html',
  './courses.html',
  './course.html',
  './tests.html',
  './test-player.html',
  './player.html',
  './downloads.html',
  './community.html',
  './profile.html',
  './splash.html',
  './dashboard.html',
  './login.html',
  './legal.html',
  './offline.html',
  './manifest.webmanifest',
  './assets/icon.svg',
  './assets/icon-192.png',
  './assets/icon-512.png',
  './assets/apple-touch-icon.png',
  './assets/css/tokens.css',
  './assets/css/base.css',
  './assets/css/components.css',
  './assets/css/pages.css',
  './assets/css/app.css',
  './assets/css/screens.css',
  './assets/js/core.js',
  './assets/js/data.js',
  './assets/js/ui.js',
  './assets/js/home.js',
  './assets/js/courses.js',
  './assets/js/course.js',
  './assets/js/tests.js',
  './assets/js/test-player.js',
  './assets/js/dashboard.js',
  './assets/js/auth.js',
  './assets/js/legal.js',
  './assets/js/player.js',
  './assets/js/downloads.js',
  './assets/js/community.js',
  './assets/js/profile.js',
  './assets/img/hero-art.jpg',
  './assets/img/poster-summit.jpg'
];

const API_PREFIXES = ['/api/', '/token/', '/auth/', '/admin/'];

const isApi = (url) => API_PREFIXES.some((p) => url.pathname.startsWith(p));
const isHtml = (req) => req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');

/* ------------------------------------------------------------------ */
/* Install                                                            */
/* ------------------------------------------------------------------ */

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_VERSION)
      // addAll rejects the whole install if one asset 404s — add individually.
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

/* ------------------------------------------------------------------ */
/* Activate                                                           */
/* ------------------------------------------------------------------ */

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key.startsWith('studyspace-') && key !== CACHE_VERSION).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

/* ------------------------------------------------------------------ */
/* Fetch                                                              */
/* ------------------------------------------------------------------ */

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Cross-origin (fonts, APIs on another host) — leave to the network.
  if (url.origin !== self.location.origin) return;

  // Student data must never be stored on disk.
  if (isApi(url)) {
    event.respondWith(
      fetch(request).catch(
        () =>
          new Response(JSON.stringify({ detail: 'You are offline. Reconnect to load this data.' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          })
      )
    );
    return;
  }

  if (isHtml(request)) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request, { ignoreSearch: true });
          if (cached) return cached;
          const shell = await caches.match('./index.html');
          const offline = await caches.match('./offline.html');
          return offline || shell || new Response('Offline', { status: 503 });
        })
    );
    return;
  }

  // Static assets: prefer the network so a new release is picked up immediately,
  // fall back to the cache when offline.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      })
      .catch(async () => (await caches.match(request)) || new Response('', { status: 504 }))
  );
});

/* ------------------------------------------------------------------ */
/* Messages                                                           */
/* ------------------------------------------------------------------ */

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
