/* Offline shell for The Iron Ledger.
 *
 * The version is not written in this file. iron-ledger.html registers it as
 * sw.js?v=<BUILD>, and the worker reads that back below, so BUILD in the app
 * stays the single source of truth and this file cannot go stale against it.
 *
 * Documents are network-first. That is deliberate: a home-screen app that
 * serves whatever it cached first is exactly how this project has lost time
 * to iOS handing back an old build. Online, you always get the current one;
 * offline, the cache answers. Fonts and icons are cache-first — they are
 * content-addressed by filename and never change under the same name.
 *
 * Nothing here touches localStorage. The log lives there and is never cached,
 * evicted or synced by this worker.
 */
const VERSION = new URL(self.location.href).searchParams.get("v") || "dev";
const CACHE = "iron-ledger-" + VERSION;

const SHELL = [
  "./",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/apple-touch-icon.png",
  "./fonts/Archivo-latin.woff2",
  "./fonts/Archivo-latin-ext.woff2",
  "./fonts/IBMPlexMono-400-latin.woff2",
  "./fonts/IBMPlexMono-500-latin.woff2",
  "./fonts/IBMPlexMono-600-latin.woff2",
  "./fonts/IBMPlexMono-400-latin-ext.woff2",
  "./fonts/IBMPlexMono-500-latin-ext.woff2",
  "./fonts/IBMPlexMono-600-latin-ext.woff2",
];

self.addEventListener("install", (e) => {
  // allSettled, not all: one 404 must not leave the app with no offline copy
  // at all. Whatever fetched is cached; the rest is picked up at runtime.
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(new Request(u, { cache: "reload" })))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith("iron-ledger-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Documents: current build when online, cached build when not.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("./", copy));
          return res;
        })
        .catch(() => caches.match("./", { ignoreSearch: true }).then((r) => r || caches.match(req)))
    );
    return;
  }

  // Everything else: cache first, fill the cache on a miss.
  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) =>
      hit || fetch(req).then((res) => {
        if (res && res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
    )
  );
});

// Lets the page ask a waiting worker to take over immediately.
self.addEventListener("message", (e) => {
  if (e.data === "skip-waiting") self.skipWaiting();
});
