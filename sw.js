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
// Big data files that change on USDA's schedule, not the app's: the grocery
// brands (8 MB). They live in a store of their own that a new build does not
// clear — otherwise every update would make every phone download them again.
// The release is in the file name, so a new release is a new file.
const DATA = "iron-ledger-data";
// The barcode reader (1.3 MB, versioned in its file names) lives there too:
// it is fetched when grocery brands are, so the first scan works offline.
const isData = (url) => /\/vendor\/(usda\/brands-|zxing\/)[^/]+$/.test(url.pathname);

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
  // The food library: 0.3 MB as served, and the whole point of it is answering
  // with no connection, so it is kept from install rather than first use.
  "./vendor/usda/foods.js",
  // The restaurant menus: 28 KB, answered offline from the first use.
  "./vendor/menus/menus.js",
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
        keys.filter((k) => k.startsWith("iron-ledger-") && k !== CACHE && k !== DATA).map((k) => caches.delete(k))))
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

  // Data files: their own store, cache first, kept across builds.
  if (isData(url)) {
    e.respondWith(
      caches.open(DATA).then((c) => c.match(req, { ignoreSearch: true }).then((hit) =>
        hit || fetch(req).then((res) => {
          if (res && res.ok && res.type === "basic") c.put(req, res.clone());
          return res;
        })))
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
