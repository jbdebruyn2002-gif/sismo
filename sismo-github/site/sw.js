// Sismo : fonctionnement hors connexion.
// Page : réseau d'abord (pour avoir les dernières données), copie en cache si hors ligne.
const CACHE = "sismo-v1";
const FILES = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
               "./icon-maskable-512.png", "./apple-touch-icon.png", "./favicon-32.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;            // polices Google : laissées au navigateur
  if (req.mode === "navigate" || url.pathname.endsWith(".html")) {
    e.respondWith(fetch(req).then(r => {
      const copy = r.clone(); caches.open(CACHE).then(c => c.put("./index.html", copy)); return r;
    }).catch(() => caches.match("./index.html")));
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
});
