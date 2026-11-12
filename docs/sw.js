/* toolrx offline shell.
 *
 * The Pages app is fully client-side, so it can keep working with no network
 * after the first visit. Navigation is network-first (so a deploy is picked up
 * while online) with a cached shell fallback. Assets are cache-first with a
 * background refresh. Bump CACHE when the shipped asset list changes.
 */
const CACHE = "toolrx-shell-v12";
const CORE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icon.svg",
  "./web/blake2b.js",
  "./web/router.js",
  "./web/sandbox.js",
  "./web/skills.js",
  "./web/templates.js",
  "./web/patches.js",
  "./web/llm.js",
  "./web/lang.js",
  "./web/i18n.json",
  "./web/engine2d.js",
  "./web/engine2d.embed.js",
  "./web/engine3d.js",
  "./web/engine3d.embed.js",
  "./web/worldgen.js",
  "./web/worldgen.embed.js",
  "./web/rpg2.js",
  "./web/rpg2.embed.js",
  // Library catalog metadata is embedded in commands.json, so the Library
  // panel works offline without a second fetch.
  "./web/commands.json",
  "./web/model.json",
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function put(request, response) {
  if (!response || !response.ok) return response;
  const copy = response.clone();
  caches.open(CACHE).then(cache => cache.put(request, copy)).catch(() => {});
  return response;
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(response => put("./index.html", response))
        .catch(() => caches.match("./index.html").then(hit => hit || caches.match("./")))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(hit => {
      if (hit) {
        fetch(request)
          .then(response => put(request, response))
          .catch(() => {});
        return hit;
      }
      return fetch(request)
        .then(response => put(request, response))
        .catch(() => caches.match(request));
    })
  );
});
