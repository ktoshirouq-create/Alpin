// Offline support. The page itself is always fetched fresh when online,
// so edits to index.html show up without touching this file.
const CACHE = 'training-guide-124';
const CORE = ['./', './index.html', './manifest.json', './icon-v2.png'];

self.addEventListener('install', e => {
  // fetch past the browser's own cache, so a new version never installs yesterday's files
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE.map(u => new Request(u, {cache: 'reload'})))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', e => {
  if (e.data === 'version') e.source.postMessage({version: CACHE});
  if (e.data === 'update') self.skipWaiting();
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
  if (req.mode === 'navigate' || /manifest\.json(\?|$)/.test(req.url)) {
    // the manifest too: Android reads the icon from it when you install
    // page: network first, cached copy when offline
    // always ask the network for a fresh page, bypassing the browser's own HTTP cache
    e.respondWith(fetch(req, {cache: 'reload'}).then(save)
      .catch(() => fetch(req).then(save))
      .catch(() => caches.match(req).then(r => r || (req.mode === 'navigate' ? caches.match('./index.html') : Response.error()))));
  } else {
    // everything else (icon, fonts): cache first
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(save)));
  }
});
