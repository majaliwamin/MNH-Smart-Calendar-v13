"use strict";

// Bump BUILD whenever the front end changes. It must match BUILD_ID in backend/app/config.py
// and window.MNH_BUILD in index.html. Old caches are deleted on activation.
const BUILD = "2026.11.22-statistical-tests-glossary-v44";
const CACHE_NAME = "mnh-calendar-shell-" + BUILD;
// KaTeX splits symbols across many font faces. Caching only the fonts used by
// the first online render leaves Greek, operator, size and script glyphs blank
// on an offline phone, so every bundled font is installed with the shell.
const KATEX_FONTS = [
  "KaTeX_AMS-Regular.woff", "KaTeX_AMS-Regular.woff2",
  "KaTeX_Caligraphic-Bold.woff", "KaTeX_Caligraphic-Bold.woff2",
  "KaTeX_Caligraphic-Regular.woff", "KaTeX_Caligraphic-Regular.woff2",
  "KaTeX_Fraktur-Bold.woff", "KaTeX_Fraktur-Bold.woff2",
  "KaTeX_Fraktur-Regular.woff", "KaTeX_Fraktur-Regular.woff2",
  "KaTeX_Main-Bold.woff", "KaTeX_Main-Bold.woff2",
  "KaTeX_Main-BoldItalic.woff", "KaTeX_Main-BoldItalic.woff2",
  "KaTeX_Main-Italic.woff", "KaTeX_Main-Italic.woff2",
  "KaTeX_Main-Regular.woff", "KaTeX_Main-Regular.woff2",
  "KaTeX_Math-BoldItalic.woff", "KaTeX_Math-BoldItalic.woff2",
  "KaTeX_Math-Italic.woff", "KaTeX_Math-Italic.woff2",
  "KaTeX_SansSerif-Bold.woff", "KaTeX_SansSerif-Bold.woff2",
  "KaTeX_SansSerif-Italic.woff", "KaTeX_SansSerif-Italic.woff2",
  "KaTeX_SansSerif-Regular.woff", "KaTeX_SansSerif-Regular.woff2",
  "KaTeX_Script-Regular.woff", "KaTeX_Script-Regular.woff2",
  "KaTeX_Size1-Regular.woff", "KaTeX_Size1-Regular.woff2",
  "KaTeX_Size2-Regular.woff", "KaTeX_Size2-Regular.woff2",
  "KaTeX_Size3-Regular.woff", "KaTeX_Size3-Regular.woff2",
  "KaTeX_Size4-Regular.woff", "KaTeX_Size4-Regular.woff2",
  "KaTeX_Typewriter-Regular.woff", "KaTeX_Typewriter-Regular.woff2"
];
const APP_FILES = [
  "/", "/index.html", "/css/app.css", "/js/week-model.js", "/js/api-client.js",
  "/js/app.js", "/js/class-rep-renderer.js", "/js/class-rep.js", "/css/class-rep.css",
  "/favicon.svg", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png",
  "/icons/icon-maskable-512.png", "/icons/apple-touch-icon.png",
  "/vendor/katex/katex.min.js", "/vendor/katex/katex.min.css", "/vendor/katex/auto-render.min.js",
  "/vendor/marked.min.js", "/vendor/purify.min.js", "/vendor/chart.umd.min.js",
  "/resources/python-command-library.html", "/resources/python-jupyter-windows-setup-simulation.html",
  "/resources/python-statistical-tests-glossary.html",
  "/resources/stat8100_practical_companion.html",
  "/resources/hypothesis-testing-lab.html",
  "/resources/data/statistical-tables.json",
  "/resources/stat8100_biostatistics_epidemiology_practical.ipynb",
  "/resources/stat8100_practical_results.json",
  ...KATEX_FONTS.map((name) => "/vendor/katex/fonts/" + name)
];
const REMOVED_APP_FILES = ["/resources/stat8100_practical_companion_ny.html"];

async function cacheResponse(key, response) {
  // Cache writes are best-effort: a failed write must never become an unhandled
  // promise rejection or break the network-first page load.
  try {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(key, response);
  } catch (_) {}
}

self.addEventListener("install", (event) => {
  // Offline fallback copy only; the network is always tried first (see fetch handler).
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => Promise.all(APP_FILES.map(async (path) => {
        try {
          const response = await fetch(path, { cache: "no-store" });
          if (response.ok) await cache.put(path, response);
        } catch (_) {}
      })))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(async () => {
        const cache = await caches.open(CACHE_NAME);
        await Promise.all(REMOVED_APP_FILES.map((path) => cache.delete(path)));
      })
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
  if (event.data && event.data.type === "MNH_CLEAR_CACHE") {
    event.waitUntil(caches.keys().then((names) => Promise.all(names.map((name) => caches.delete(name)))));
  }
});

// Network-first: a reachable server always wins, so an update can never be hidden behind stale files.
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/health" || url.pathname === "/service-worker.js") return;

  const isShell = request.mode === "navigate" || APP_FILES.includes(url.pathname) || url.pathname.startsWith("/vendor/");
  if (!isShell) return;

  event.respondWith(
    fetch(request, { cache: "no-store" })
      .then((response) => {
        if (response.ok) {
          // Store successful navigations under the stable offline key too, so a
          // phone that goes offline opens the newest page it actually loaded.
          // Query-string reload markers never become cache keys.
          cacheResponse(request.mode === "navigate" ? "/index.html" : url.pathname, response.clone());
        }
        return response;
      })
      .catch(async () => {
        const key = request.mode === "navigate" ? "/index.html" : url.pathname;
        return (await caches.match(key)) || (await caches.match("/index.html")) || Response.error();
      }),
  );
});
