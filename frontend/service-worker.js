"use strict";

// Bump BUILD whenever the front end changes. It must match BUILD_ID in backend/app/config.py
// and window.MNH_BUILD in index.html. Old caches are deleted on activation.
const BUILD = "2026.11.21-install-button-copy-v17";
const CACHE_NAME = "mnh-calendar-shell-" + BUILD;
const APP_FILES = ["/", "/index.html", "/css/app.css", "/js/week-model.js", "/js/api-client.js", "/js/app.js", "/js/class-rep-renderer.js", "/js/class-rep.js", "/css/class-rep.css", "/favicon.svg", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/icon-maskable-512.png", "/icons/apple-touch-icon.png"];

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
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

// Network-first: a reachable server always wins, so an update can never be hidden behind stale files.
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/health" || url.pathname === "/service-worker.js") return;

  const isShell = request.mode === "navigate" || APP_FILES.includes(url.pathname);
  if (!isShell) return;

  event.respondWith(
    fetch(request, { cache: "no-store" })
      .then((response) => {
        if (response.ok && request.mode !== "navigate") {
          // Navigation URLs carry one-use reload markers and can redirect; the
          // stable /index.html copy cached at install is the offline fallback.
          cacheResponse(url.pathname, response.clone());
        }
        return response;
      })
      .catch(async () => {
        const key = request.mode === "navigate" ? "/index.html" : url.pathname;
        return (await caches.match(key)) || (await caches.match("/index.html")) || Response.error();
      }),
  );
});
