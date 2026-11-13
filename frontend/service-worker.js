"use strict";

// Bump BUILD whenever the front end changes. It must match BUILD_ID in backend/app/config.py
// and window.MNH_BUILD in index.html. Old caches are deleted on activation.
const BUILD = "2026.11.13-v14.2";
const CACHE_NAME = "mnh-calendar-shell-" + BUILD;
const APP_FILES = ["/", "/index.html", "/css/app.css", "/js/week-model.js", "/js/api-client.js", "/js/app.js"];

self.addEventListener("install", (event) => {
  // Offline fallback copy only; the network is always tried first (see fetch handler).
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => Promise.all(APP_FILES.map((path) => fetch(path, { cache: "no-store" }).then((r) => (r.ok ? cache.put(path, r) : null)).catch(() => null))))
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
        if (response.ok) {
          const copy = response.clone();
          const key = request.mode === "navigate" ? "/" : url.pathname;
          caches.open(CACHE_NAME).then((cache) => cache.put(key, copy));
        }
        return response;
      })
      .catch(async () => {
        const key = request.mode === "navigate" ? "/" : url.pathname;
        return (await caches.match(key)) || (await caches.match("/index.html")) || Response.error();
      }),
  );
});
