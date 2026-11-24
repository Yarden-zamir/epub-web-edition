// Offline reading. tools/web/99_offline.py writes this file to the site root and fills VERSION and FILES.
//
// - Pages, styles, scripts and data ("shell"): network first, so a correction shows at once. Offline, or with no
//   answer within NETWORK_WAIT, the copy that this version of the worker saved at install.
// - Book images ("media"): from the cache once read. A cached image is kept under its content hash, so a
//   changed image is fetched again and the old one is deleted when the new version activates.
// - Map tiles and video thumbnails from other hosts: from the cache once read, at most REMOTE_LIMIT entries.
//   The map library is a site file (shell).
// - The EPUB download and every file the build did not list: network only, never cached.
// - An app installed to the home screen asks the worker to save every book image ("save-all").
"use strict";

const VERSION = "__VERSION__";
/** @type {Record<string, [hash: string, kind: "shell" | "media"]>} Site path -> content hash and kind. */
const FILES = __FILES__;
const SHELL = `reader-shell-${VERSION}`; // Old versions are deleted on activate.
const MEDIA = "reader-media"; // Entries keyed by path?v=hash; stale ones are deleted on activate.
const REMOTE = "reader-remote";
const NETWORK_WAIT = 4000; // ms. A weak signal falls back to the saved copy after this long.
// Known limit: tiles are trimmed by count, not bytes (about 20 KB each). Revisit if the maps get many more tiles.
const REMOTE_LIMIT = 3000;
const SAVE_PARALLEL = 4;

const scope = new URL(self.registration.scope);
const key = (path) => new URL(`${path}?v=${FILES[path][0]}`, scope).href;
// Pages that were served from the cache. Their scripts and styles come from the same cache, so a page never
// mixes two versions. Known limit: the set lives in memory; a worker restart forgets it, and such a page then
// gets network first. Revisit if mixed versions show up offline.
const offlineClients = new Set();

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL);
    const old = (await caches.keys()).filter((name) => name.startsWith("reader-shell-") && name !== SHELL);
    const paths = Object.keys(FILES).filter((path) => FILES[path][1] === "shell");
    await Promise.all(paths.map(async (path) => {
      // A file with the same hash in an older version is copied, not downloaded again.
      for (const name of old) {
        const hit = await (await caches.open(name)).match(key(path));
        if (hit) return shell.put(key(path), hit);
      }
      const response = await fetch(new URL(path, scope), { cache: "reload" });
      if (!response.ok) throw new Error(`sw: ${path} answered ${response.status}`);
      await shell.put(key(path), response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith("reader-shell-") && name !== SHELL) await caches.delete(name);
    }
    const media = await caches.open(MEDIA);
    const wanted = new Set(Object.keys(FILES).filter((path) => FILES[path][1] === "media").map(key));
    for (const request of await media.keys()) {
      if (!wanted.has(request.url)) await media.delete(request);
    }
    await self.clients.claim();
  })());
});

function sitePath(url) {
  const path = decodeURIComponent(url.pathname.slice(scope.pathname.length));
  return path === "" ? "index.html" : path;
}

// The network answer, or the cached copy when the network fails or is slower than NETWORK_WAIT.
async function networkFirst(request, path, clientId) {
  const cached = async () => markOffline(await caches.match(key(path), { cacheName: SHELL }));
  if (offlineClients.has(clientId)) {
    const hit = await cached();
    if (hit) return hit;
  }
  const network = fetch(request);
  const slow = new Promise((resolve) => setTimeout(resolve, NETWORK_WAIT, "slow"));
  try {
    const first = await Promise.race([network, slow]);
    if (first !== "slow") return first;
    const hit = await cached();
    return hit ?? await network;
  } catch (error) {
    const hit = await cached();
    if (hit) return hit;
    throw error;
  }
}

async function page(event) {
  try {
    const response = await networkFirst(event.request, "index.html", null);
    if (response.headers.has("x-offline-copy")) offlineClients.add(event.resultingClientId);
    return response;
  } catch {
    return new Response("<!doctype html><meta charset=utf-8><title>אין חיבור</title><p dir=rtl>אין חיבור לרשת, והספר עוד לא נשמר במכשיר הזה.</p>",
      { status: 503, headers: { "content-type": "text/html; charset=utf-8" } });
  }
}

// An image that cannot load offline shows as an empty box (the layout already reserves its size), not a broken icon.
const EMPTY_IMAGE = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>';
function emptyImage() {
  return new Response(EMPTY_IMAGE, { headers: { "content-type": "image/svg+xml" } });
}

async function cacheFirst(request, path) {
  const media = await caches.open(MEDIA);
  const hit = await media.match(key(path));
  if (hit) return hit;
  try {
    const response = await fetch(request);
    if (response.ok) await media.put(key(path), response.clone());
    return response;
  } catch (error) {
    if (request.destination === "image") return emptyImage();
    throw error;
  }
}

let remotePuts = 0;
async function remote(request) {
  const cache = await caches.open(REMOTE);
  const hit = await cache.match(request);
  if (hit) return hit;
  try {
    const response = await fetch(request);
    // Only readable (CORS) answers: an opaque answer can hold an error and takes megabytes of quota.
    if (response.ok) {
      await cache.put(request, response.clone());
      if (++remotePuts % 100 === 0) {
        const keys = await cache.keys(); // Oldest first.
        await Promise.all(keys.slice(0, Math.max(0, keys.length - REMOTE_LIMIT)).map((k) => cache.delete(k)));
      }
    }
    return response;
  } catch (error) {
    if (request.destination === "image") return emptyImage();
    throw error;
  }
}

// Mark a response from the shell cache, so page() knows the page came from the cache.
async function markOffline(response) {
  if (!response) return response;
  const headers = new Headers(response.headers);
  headers.set("x-offline-copy", VERSION);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin === scope.origin) {
    if (!url.pathname.startsWith(scope.pathname)) return;
    if (request.mode === "navigate") {
      event.respondWith(page(event));
      return;
    }
    const path = sitePath(url);
    const file = FILES[path];
    // Pages ask for scripts and styles as path?v=<content hash> (tools/web/99_offline.py). Another query, an older
    // hash (a page of another build), downloads, build.json and unlisted files go to the network untouched.
    if (!file || (url.search && url.search !== `?v=${file[0]}`)) return;
    event.respondWith(file[1] === "shell" ? networkFirst(request, path, event.clientId) : cacheFirst(request, path));
    return;
  }
  // Map tiles and video thumbnails. YouTube players (frames) are not cached.
  if (request.destination === "image") event.respondWith(remote(request));
});

// Save every book image, skipping what is cached already.
// The page sends "save-all" on each start of the installed app, so an interrupted save resumes there.
async function saveAll(source) {
  const media = await caches.open(MEDIA);
  const todo = [];
  for (const path of Object.keys(FILES).filter((p) => FILES[p][1] === "media")) {
    if (!(await media.match(key(path)))) todo.push(() => fetch(new URL(path, scope)).then((r) => r.ok && media.put(key(path), r)));
  }
  const total = todo.length;
  let done = 0, failed = 0;
  const report = () => source?.postMessage({ type: "save-progress", done, failed, total });
  report();
  const worker = async () => {
    for (let job = todo.shift(); job; job = todo.shift()) {
      try { await job(); } catch { failed++; }
      done++;
      if (done % 20 === 0) report();
    }
  };
  await Promise.all(Array.from({ length: SAVE_PARALLEL }, worker));
  report();
  source?.postMessage({ type: failed ? "save-incomplete" : "saved", total, failed });
}

// Images the page loaded before this worker controlled it (the first visit). Unlisted paths are ignored.
async function savePaths(paths) {
  const media = await caches.open(MEDIA);
  await Promise.all(paths.filter((path) => FILES[path]?.[1] === "media").map(async (path) => {
    if (await media.match(key(path))) return;
    const response = await fetch(new URL(path, scope));
    if (response.ok) await media.put(key(path), response);
  }));
}

self.addEventListener("message", (event) => {
  if (event.data?.type === "save-all") event.waitUntil(saveAll(event.source));
  if (event.data?.type === "save-read") event.waitUntil(savePaths(event.data.paths));
});
