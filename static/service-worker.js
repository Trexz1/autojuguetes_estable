const CACHE_NAME = 'jugueteriabot-panel-v2';
const CORE_ASSETS = ['/panel', '/static/panel.css', '/static/panel-react.js', '/static/panel-gsap.js', '/static/logo_robles.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS)).catch(() => null));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  event.respondWith(fetch(req).catch(() => caches.match(req).then(res => res || caches.match('/panel'))));
});
