// Same-origin data client with durable offline collection caching and write queuing.
(function () {
  "use strict";

  const API_BASE = String(window.MNH_API || "").replace(/\/$/, "");
  const CACHE_PREFIX = "mnh_calendar_collection_v1:";
  const QUEUE_KEY = "mnh_calendar_offline_write_queue_v1";
  const pollers = new Set();
  let pending = 0;
  let flushing = false;
  let queueBlocked = false;

  function readJson(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value ? JSON.parse(value) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function getQueue() {
    const queue = readJson(QUEUE_KEY, []);
    return Array.isArray(queue) ? queue : [];
  }

  function notify(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail }));
  }

  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }

  function requestOptions(method, body) {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      credentials:
        API_BASE && new URL(API_BASE, window.location.href).origin !== window.location.origin
          ? "include"
          : "same-origin",
    };
  }

  async function send(method, path, body) {
    const response = await fetch(apiUrl(path), requestOptions(method, body));
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw Object.assign(
        new Error(payload.error || `HTTP ${response.status}`),
        { status: response.status },
      );
    }

    return payload;
  }

  function collectionNameFromPath(path) {
    const match = /^\/api\/col\/([^/?]+)$/.exec(path);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function applyQueuedChanges(collectionName, rows) {
    const result = new Map(
      rows.map((row) => [String(row.id), { id: String(row.id), data: row.data }]),
    );

    getQueue().forEach((item) => {
      const match = /^\/api\/doc\/([^/]+)\/(.+)$/.exec(item.path || "");
      if (!match || decodeURIComponent(match[1]) !== collectionName) return;

      const id = decodeURIComponent(match[2]);
      if (item.method === "DELETE") {
        result.delete(id);
      } else if (item.method === "PUT") {
        result.set(id, { id, data: item.body });
      }
    });

    return Array.from(result.values()).sort((a, b) => a.id.localeCompare(b.id));
  }

  function enqueue(method, path, body) {
    const queue = getQueue().filter((item) => item.path !== path);
    queue.push({ method, path, body, queuedAt: Date.now() });

    if (!writeJson(QUEUE_KEY, queue)) {
      throw new Error("Offline storage is full. Download a backup before continuing.");
    }

    notify("mnh:offline-queued", { count: queue.length, path });
  }

  async function flushQueue(force = false) {
    if (flushing || !navigator.onLine) return false;
    if (queueBlocked && !force) return false;
    if (force) queueBlocked = false;

    let queue = getQueue();
    if (!queue.length) return true;

    flushing = true;
    const hadPendingWrites = true;

    try {
      while (queue.length) {
        const item = queue[0];
        try {
          await send(item.method, item.path, item.body);
        } catch (error) {
          // Preserve rejected writes and pause retries until connectivity or sign-in changes.
          if (error.status != null && error.status < 500) queueBlocked = true;
          return false;
        }

        queue = queue.slice(1);
        if (!writeJson(QUEUE_KEY, queue)) return false;
      }

      if (hadPendingWrites) {
        notify("mnh:offline-synced", { count: 0 });
      }
      return true;
    } finally {
      flushing = false;
    }
  }

  async function api(method, path, body) {
    const verb = String(method || "GET").toUpperCase();
    const isWrite = verb === "PUT" || verb === "DELETE";
    const collectionName = verb === "GET" ? collectionNameFromPath(path) : null;

    // Older queued writes must reach the server before a newer edit is sent.
    if (verb === "GET" || isWrite) await flushQueue();
    if (isWrite) pending += 1;

    try {
      const payload = await send(verb, path, body);
      if (collectionName && Array.isArray(payload)) {
        writeJson(CACHE_PREFIX + collectionName, payload);
        return applyQueuedChanges(collectionName, payload);
      }
      return payload;
    } catch (error) {
      if (collectionName) {
        const cached = readJson(CACHE_PREFIX + collectionName, null);
        if (Array.isArray(cached)) {
          const rows = applyQueuedChanges(collectionName, cached);
          Object.defineProperty(rows, "fromCache", { value: true });
          return rows;
        }
      }

      const isNetworkFailure = error.status == null
        ? error instanceof TypeError || !navigator.onLine
        : error.status >= 500;
      if (isNetworkFailure && isWrite) {
        enqueue(verb, path, body);
        throw Object.assign(
          new Error("You are offline. This change has been saved on this device and will sync automatically."),
          { queued: true },
        );
      }

      throw error;
    } finally {
      if (isWrite) {
        pending -= 1;
        refresh();
      }
    }
  }

  const refresh = () => pollers.forEach((poll) => poll());

  const doc = (path) => {
    const [collection, ...rest] = String(path).split("/");
    const id = rest.join("/");
    const url = `/api/doc/${encodeURIComponent(collection)}/${encodeURIComponent(id)}`;

    return {
      set: async (data) => api("PUT", url, data),
      delete: async () => api("DELETE", url),
    };
  };

  const snapshot = (rows) => ({
    docs: rows.map((row) => ({ id: row.id, data: () => row.data })),
    empty: !rows.length,
    metadata: { fromCache: Boolean(rows.fromCache) },
  });

  const collection = (name) => ({
    get: async () => snapshot(await api("GET", `/api/col/${encodeURIComponent(name)}`)),
    onSnapshot: (callback, onError) => {
      let last = "";
      let stopped = false;
      let busy = false;
      let failures = 0;

      const tick = async () => {
        if (stopped || pending || busy || document.hidden) return;
        busy = true;

        try {
          const rows = await api("GET", `/api/col/${encodeURIComponent(name)}`);
          const signature = JSON.stringify(rows);
          failures = 0;
          if (signature !== last) {
            last = signature;
            callback(snapshot(rows));
          }
        } catch (error) {
          failures = Math.min(failures + 1, 5);
          if (onError) onError(error);
        } finally {
          busy = false;
        }
      };

      pollers.add(tick);
      tick();
      const timer = setInterval(tick, Math.min(15000, 2500 * (1 + failures)));

      return () => {
        stopped = true;
        clearInterval(timer);
        pollers.delete(tick);
      };
    },
  });

  window.addEventListener("online", async () => {
    await flushQueue(true);
    refresh();
  });

  window.mnhApi = {
    use: async (name) =>
      name === "db" ? (await api("GET", "/api/ping"), { doc, collection }) : null,
    request: api,
    flushQueue,
    pendingWrites: () => getQueue().length,
  };
})();
