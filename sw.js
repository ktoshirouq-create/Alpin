// Offline support. The page itself is always fetched fresh when online,
// so edits to index.html show up without touching this file.
const CACHE = 'training-guide-21';
const CORE = ['./', './index.html', './manifest.json', './icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const save = res => {
    if (res && (res.ok || res.type === 'opaque')) {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(req, copy));
    }
    return res;
  };
  if (req.mode === 'navigate') {
    // page: network first, cached copy when offline
    e.respondWith(fetch(req).then(save).catch(() => caches.match(req).then(r => r || caches.match('./index.html'))));
  } else {
    // everything else (icon, fonts): cache first
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(save)));
  }
});
