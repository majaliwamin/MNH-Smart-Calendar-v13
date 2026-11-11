const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("frontend/js/api-client.js", "utf8");
const storage = new Map();
const serverRows = { cells: [{ id: "0_0", data: { code: "Existing" } }] };
let online = true;
let queuedEvents = 0;
let syncedEvents = 0;
let rejectWrites = false;

const localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
};

class CustomEventMock {
  constructor(type, options) {
    this.type = type;
    this.detail = options?.detail;
  }
}

const listeners = new Map();
const window = {
  MNH_API: "",
  location: { href: "http://localhost:8000/", origin: "http://localhost:8000" },
  addEventListener: (name, callback) => listeners.set(name, callback),
  dispatchEvent: (event) => {
    if (event.type === "mnh:offline-queued") queuedEvents += 1;
    if (event.type === "mnh:offline-synced") syncedEvents += 1;
    return true;
  },
};

async function fetchMock(url, options = {}) {
  if (!online) throw new TypeError("Network unavailable");
  const method = options.method || "GET";
  const match = /^\/api\/doc\/([^/]+)\/(.+)$/.exec(url);

  if (match && method === "PUT") {
    if (rejectWrites) {
      return {
        ok: false,
        status: 401,
        json: async () => ({ error: "Authentication required" }),
      };
    }
    const collection = decodeURIComponent(match[1]);
    const id = decodeURIComponent(match[2]);
    const data = JSON.parse(options.body);
    const index = serverRows[collection].findIndex((row) => row.id === id);
    const row = { id, data };
    if (index >= 0) serverRows[collection][index] = row;
    else serverRows[collection].push(row);
    return response({ ok: true });
  }

  const collectionMatch = /^\/api\/col\/([^/]+)$/.exec(url);
  if (collectionMatch && method === "GET") {
    return response(serverRows[decodeURIComponent(collectionMatch[1])] || []);
  }

  return response({ ok: true });
}

function response(payload) {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
  };
}

const context = {
  window,
  localStorage,
  navigator: { get onLine() { return online; } },
  document: { hidden: false },
  fetch: fetchMock,
  CustomEvent: CustomEventMock,
  URL,
  Date,
  JSON,
  Map,
  Array,
  String,
  Object,
  Math,
  TypeError,
  setInterval: () => 1,
  clearInterval: () => {},
};

(async () => {
  vm.runInNewContext(source, context, { filename: "api-client.js" });

  const first = await window.mnhApi.request("GET", "/api/col/cells");
  assert.equal(first.length, 1, "online collection read should work");

  online = false;
  await assert.rejects(
    window.mnhApi.request("PUT", "/api/doc/cells/1_0", { code: "Offline edit" }),
    (error) => error.queued === true,
  );
  assert.equal(window.mnhApi.pendingWrites(), 1, "offline write should persist in the queue");
  assert.equal(queuedEvents, 1, "offline queue event should be dispatched");

  const cached = await window.mnhApi.request("GET", "/api/col/cells");
  assert.equal(cached.fromCache, true, "offline read should be marked as cached");
  assert.ok(cached.some((row) => row.id === "1_0"), "cached data should include the queued edit");

  online = true;
  await window.mnhApi.request("PUT", "/api/doc/cells/1_0", { code: "Newer online edit" });
  assert.equal(window.mnhApi.pendingWrites(), 0, "successful sync should clear the queue");
  assert.equal(syncedEvents, 1, "sync completion event should be dispatched");
  const syncedRow = serverRows.cells.find((row) => row.id === "1_0");
  assert.equal(syncedRow.data.code, "Newer online edit", "older queued data must not overwrite a newer online edit");

  rejectWrites = true;
  await assert.rejects(window.mnhApi.request("PUT", "/api/doc/cells/2_0", { code: "Unauthorized" }));
  assert.equal(window.mnhApi.pendingWrites(), 0, "authorization failures must not be queued as offline writes");

  console.log("Offline API client checks passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
