// Cache-first for the static app shell only -- NEVER intercepts calls to
// the scoring or coach APIs (those must always hit the network; caching a
// credit score or a coach answer would be actively wrong, not just stale).
const CACHE_NAME = "finbuddy-shell-v1";
const APP_SHELL = ["./", "./index.html", "./manifest.json", "./icon.svg"];

const API_HOSTS = ["bhavyabhandary-finbuddy-scoring.hf.space", "bhavyabhandary-finbuddy-rag-coach.hf.space"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (API_HOSTS.includes(url.host)) {
    return; // let the browser handle it normally -- always network, never cached
  }

  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
