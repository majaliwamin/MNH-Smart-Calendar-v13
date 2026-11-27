// Static, read-only data client for the GitHub Pages copy of MNH Calendar.
//
// Every GET is served from a relative ./data/<name>.json snapshot exported by
// tools/export_static_data.py. No request ever leaves the static site: there is
// no backend, no localhost address and no leading "/" asset path. All writes
// (POST/PUT/PATCH/DELETE, login, uploads) are replaced by a friendly notice.
(function () {
  "use strict";

  const STATIC_MODE = true;
  const DATA_BASE = "./data/";
  const READ_ONLY_MESSAGE = "Read-only version — this GitHub Pages copy cannot save changes.";
  window.MNH_STATIC_MODE = STATIC_MODE;
  window.MNH_READ_ONLY_MESSAGE = READ_ONLY_MESSAGE;

  const cache = new Map();
  const pollers = new Set();
  const nativeFetch = window.fetch.bind(window);

  // Endpoint -> exported snapshot. Collection names are resolved dynamically below.
  const FILES = {
    "/api/ping": "ping.json",
    "/api/session": "session.json",
    "/api/health": "health.json",
    "/api/build": "health.json",
    "/api/export/modules": "export-modules.json",
    "/api/analytics": "analytics.json",
    "/api/history": "history.json",
  };
  const ALLOWED_COLLECTIONS = new Set([
    "cells", "resources", "settings", "modules", "facilitators",
    "examinations", "recurring", "communications",
  ]);

  // Backend-only GETs are answered with empty, harmless JSON so the read-only
  // views render without failed network requests or console errors.
  const STUBS = {
    "/api/reminders": {
      ok: false,
      whatsapp: { provider: "unavailable", configured: false, sender: "", recipients: [] },
      editor: false,
      settings: { enabled: false, leadMinutes: [10], recipientCount: 0, recipients: [] },
      recent: [],
    },
    "/api/comm/status": { ok: true, configured: false, emergencyStop: false, counts: {} },
    "/api/comm/whatsapp/profile": { name: "" },
    "/api/comm/contacts": { contacts: [] },
    "/api/comm/dnc": { items: [] },
    "/api/comm/templates": { templates: [] },
    "/api/comm/jobs": { jobs: [] },
    "/api/comm/history": { history: [] },
    "/api/comm/drafts": { drafts: [] },
    "/api/comm/voice/calls": { calls: [] },
    "/api/comm/ai/trigger-log": { items: [] },
    "/api/class-rep/status": { ok: true, ready: false, provider: "unavailable", static: true },
    "/api/class-rep/language": { ok: true, language: "en" },
    "/api/class-rep/auth/me": { ok: false, authenticated: false, role: "guest" },
    "/api/class-rep/conversations": { conversations: [], items: [] },
    "/api/class-rep/memories": { memories: [], items: [] },
    "/api/class-rep/projects": { projects: [], items: [] },
    "/api/class-rep/tasks": { tasks: [], items: [] },
    "/api/class-rep/reminders": { reminders: [], items: [] },
    "/api/class-rep/documents": { documents: [], items: [] },
    "/api/class-rep/voice/status": { ok: true, available: false },
    "/api/class-rep/diagnostics/provider": { ok: true, configured: false },
    "/api/class-rep/livekit/status": { ok: true, configured: false },
    "/api/public-chat/status": { joined: false, participant: null, participants: [] },
    "/api/public-chat/messages": { messages: [] },
    "/api/public-chat/unread": { unread: 0 },
    "/api/public-chat/preferences": { values: {} },
    "/api/public-chat/search": { messages: [] },
    "/api/public-chat/participants": { participants: [] },
    "/api/public-chat/blocks": { blocks: [] },
    "/api/public-chat/access-request": { request: null },
    "/api/exams/health": {
      ok: true, module: "exams", status: "read-only", identity: { exam_role: "guest" },
      capabilities: [], collections: {},
    },
    "/api/exams/capabilities": {
      ok: true, identity: { exam_role: "guest" }, capabilities: [],
      can_manage: false, can_take: false,
    },
    "/api/exams/overview": { ok: true, summary: {}, by_exam: [], counts: {} },
    "/api/exams/my": { ok: true, sessions: [], submissions: [], enrollments: [] },
    "/api/exams/exams": { ok: true, items: [] },
    "/api/exams/questions": { ok: true, items: [] },
    "/api/exams/enrollments": { ok: true, items: [] },
    "/api/exams/sessions": { ok: true, items: [] },
    "/api/exams/sessions/monitor": { ok: true, items: [] },
    "/api/exams/submissions": { ok: true, items: [] },
    "/api/exams/analytics": { ok: true, analytics: {}, by_exam: [], counts: {}, attempt_timeline: [] },
    "/api/exams/audit": { ok: true, items: [], count: 0 },
    "/api/exams/audit/verify": { ok: true, valid: true },
    "/api/exams/backup": { ok: true, schema_version: "static", documents: [] },
    "/api/export": [],
    "/api/backup": { format: "mnh-calendar-backup", version: 1, documents: [] },
  };

  // These prefixes are answered with an empty JSON object when no more
  // specific stub above matches (e.g. /api/exams/sessions/<id>/events).
  const STUB_PREFIXES = [
    "/api/exams/", "/api/public-chat/", "/api/class-rep/", "/api/comm/",
    "/api/ai/", "/api/resources/", "/api/reminders/",
  ];

  function showReadOnlyNotice() {
    let notice = document.getElementById("mnh-readonly-notice");
    if (!notice) {
      notice = document.createElement("div");
      notice.id = "mnh-readonly-notice";
      notice.className = "mnh-readonly-notice";
      notice.setAttribute("role", "status");
      notice.textContent = READ_ONLY_MESSAGE;
      (document.body || document.documentElement).appendChild(notice);
    }
    notice.classList.add("is-visible");
    window.clearTimeout(showReadOnlyNotice.timer);
    showReadOnlyNotice.timer = window.setTimeout(() => {
      notice.classList.remove("is-visible");
    }, 6000);
    window.dispatchEvent(new CustomEvent("mnh:read-only", { detail: { message: READ_ONLY_MESSAGE } }));
  }

  function jsonResponse(payload, status) {
    return new Response(JSON.stringify(payload), {
      status: status || 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  function splitPath(path) {
    const clean = String(path || "/");
    const question = clean.indexOf("?");
    const pathname = question === -1 ? clean : clean.slice(0, question);
    const query = question === -1 ? "" : clean.slice(question + 1);
    return { pathname, query: new URLSearchParams(query) };
  }

  function snapshotFile(pathname) {
    if (Object.prototype.hasOwnProperty.call(FILES, pathname)) return FILES[pathname];
    const match = /^\/api\/col\/([^/?]+)$/.exec(pathname);
    if (match) {
      const name = decodeURIComponent(match[1]);
      return ALLOWED_COLLECTIONS.has(name) ? `col-${name}.json` : null;
    }
    return null;
  }

  function loadSnapshot(file) {
    if (!cache.has(file)) {
      cache.set(
        file,
        nativeFetch(DATA_BASE + file, { cache: "force-cache" }).then((response) => {
          if (!response.ok) throw new Error(`Snapshot ${file} is missing`);
          return response.json();
        }),
      );
    }
    return cache.get(file);
  }

  function valueOfRow(row, key) {
    if (!row || typeof row !== "object") return undefined;
    const source = Object.prototype.hasOwnProperty.call(row, "data") && row.data && typeof row.data === "object"
      ? row.data
      : row;
    return source[key];
  }

  // Query-string filtering happens here, in JavaScript, on the loaded JSON.
  function applyQuery(payload, query) {
    const entries = Array.from(query.entries()).filter(([key]) => !["_", "v", "cache"].includes(key));
    if (!entries.length) return payload;

    if (Array.isArray(payload)) {
      let rows = payload;
      entries.forEach(([key, wanted]) => {
        if (["limit", "offset", "format", "theme", "font_scale", "week_start", "modules"].includes(key)) return;
        rows = rows.filter((row) => String(valueOfRow(row, key) ?? "") === String(wanted));
      });
      const offset = Math.max(0, Number(query.get("offset") || 0));
      if (query.has("limit")) rows = rows.slice(offset, offset + Math.max(0, Number(query.get("limit")) || 0));
      else if (offset) rows = rows.slice(offset);
      return rows;
    }

    if (payload && typeof payload === "object") {
      const result = JSON.parse(JSON.stringify(payload));
      const year = query.get("year");
      if (year && result.dashboard) {
        result.dashboard.selectedYear = String(year);
        result.dashboard.reportingPeriod = `Academic Year ${year}`;
      }
      const limit = Number(query.get("limit"));
      for (const key of ["items", "exams", "questions", "enrollments", "sessions", "submissions", "messages", "modules", "history"]) {
        if (Array.isArray(result[key]) && Number.isFinite(limit) && limit > 0) result[key] = result[key].slice(0, limit);
      }
      return result;
    }
    return payload;
  }

  function stubFor(pathname) {
    if (Object.prototype.hasOwnProperty.call(STUBS, pathname)) return STUBS[pathname];
    if (STUB_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return {};
    return null;
  }

  async function staticGet(path, options) {
    const { pathname, query } = splitPath(path);
    // The snapshot may record a signed-in public session. The read-only copy
    // must never enter editing mode, so force an unauthenticated session here.
    if (pathname === "/api/session") {
      return { authenticated: false, role: "public", static: true };
    }
    const file = snapshotFile(pathname);
    if (file) {
      const payload = applyQuery(await loadSnapshot(file), query);
      // The original app migrates undated timetable records into a dated week.
      // In a read-only snapshot that migration can never finish, so give those
      // records the same date the app already uses for display and stop looping.
      if (pathname === "/api/col/cells" && Array.isArray(payload)) {
        return payload.map((row) => {
          if (!row || !row.data || row.data.weekStart) return row;
          return { ...row, data: { ...row.data, weekStart: "2026-11-16" } };
        });
      }
      return payload;
    }
    const stub = stubFor(pathname);
    if (stub !== null) return applyQuery(stub, query);
    // An unknown static path still resolves to empty JSON: no failed requests.
    if (pathname.startsWith("/api/")) return {};
    return nativeFetch(path, options);
  }

  // Intercept fetch so the direct fetch() calls in app.js, exams.js and
  // class-rep.js also use the static snapshots instead of requesting a server.
  window.fetch = function staticFetch(input, init) {
    const url = typeof input === "string" ? input : input && input.url ? input.url : String(input);
    const pathname = splitPath(url).pathname;
    const method = String((init && init.method) || (input && input.method) || "GET").toUpperCase();
    if (!pathname.startsWith("/api/") && pathname !== "/health") {
      return nativeFetch(input, init);
    }
    if (method !== "GET" && method !== "HEAD") {
      showReadOnlyNotice();
      return Promise.resolve(jsonResponse({ ok: true, readOnly: true, message: READ_ONLY_MESSAGE }));
    }
    if (pathname === "/health") {
      return Promise.resolve(jsonResponse({ ok: true, build: window.MNH_BUILD || "static", static: true }));
    }
    if (pathname === "/api/export/timetable.pdf" || pathname === "/api/export/timetable.xlsx") {
      showReadOnlyNotice();
      return Promise.resolve(jsonResponse({ error: "PDF and Excel downloads need the backend. Use Print or CSV on this read-only copy." }, 200));
    }
    return staticGet(url, init).then((payload) => jsonResponse(payload));
  };

  function snapshot(rows) {
    return {
      docs: (Array.isArray(rows) ? rows : []).map((row) => ({ id: row.id, data: () => row.data })),
      empty: !rows || !rows.length,
      metadata: { fromCache: false, static: true },
    };
  }

  const collection = (name) => ({
    get: async () => snapshot(await staticGet(`/api/col/${encodeURIComponent(name)}`)),
    onSnapshot: (callback, onError) => {
      const tick = async () => {
        try {
          callback(snapshot(await staticGet(`/api/col/${encodeURIComponent(name)}`)));
        } catch (error) {
          if (onError) onError(error);
        }
      };
      pollers.add(tick);
      tick();
      return () => pollers.delete(tick);
    },
  });

  const doc = (path) => ({
    set: async () => { showReadOnlyNotice(); return { ok: true, readOnly: true }; },
    delete: async () => { showReadOnlyNotice(); return { ok: true, readOnly: true }; },
  });

  async function request(method, path, body) {
    const verb = String(method || "GET").toUpperCase();
    if (verb !== "GET" && verb !== "HEAD") {
      showReadOnlyNotice();
      return { ok: true, readOnly: true, message: READ_ONLY_MESSAGE };
    }
    return staticGet(path);
  }

  window.mnhApi = {
    STATIC_MODE,
    use: async (name) => (name === "db" ? { doc, collection } : null),
    request,
    flushQueue: async () => true,
    pendingWrites: () => 0,
    refresh: () => pollers.forEach((poll) => poll()),
  };
})();
