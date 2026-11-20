/*
 * Additive bridge between the Biomedical Python Command Library HTML and the
 * local FastAPI backend. It does not alter any existing learning content.
 *
 * Default API: http://127.0.0.1:8000/api/v1
 * Embedded calendars should use ?runner=off so execution is opt-in.
 * Override before this script runs with:
 *   <script>window.BIOMEDICAL_API_BASE_URL = "http://host:8000/api/v1";</script>
 */
(function () {
  "use strict";

  var DEFAULT_BASE = "http://127.0.0.1:8000/api/v1";
  var SAMPLES = [
    { label: "Simulated data 1: anc_cohort.csv", file: "anc_cohort.csv" },
    { label: "Simulated data 2: bp_paired.csv", file: "bp_paired.csv" },
    { label: "Simulated data 3: postpartum_survival.csv", file: "postpartum_survival.csv" }
  ];
  var savedBaseUrl = "";
  var queryBaseUrl = "";
  var runnerParam = "";
  var runnerEnabled = true;
  var embeddedMode = false;
  var runnerButtons = [];
  var sampleButtons = [];
  var fileInputs = [];
  try { savedBaseUrl = localStorage.getItem("biomedical_api_base") || ""; } catch (error) {}
  try { embeddedMode = window.self !== window.top; } catch (error) { embeddedMode = true; }
  try {
    var pageParams = new URLSearchParams(window.location.search);
    queryBaseUrl = pageParams.get("api") || "";
    runnerParam = String(pageParams.get("runner") || "").toLowerCase();
  } catch (error) {}
  if (runnerParam === "off" || runnerParam === "0" || runnerParam === "false") {
    runnerEnabled = false;
  } else if (runnerParam === "on" || runnerParam === "1" || runnerParam === "true") {
    runnerEnabled = true;
  } else if (embeddedMode) {
    runnerEnabled = false;
  }
  if (window.BIOMEDICAL_RUNNER_ENABLED === false) runnerEnabled = false;
  var explicitBaseUrl = String(window.BIOMEDICAL_API_BASE_URL || queryBaseUrl).trim().replace(/\/+$/, "");
  // public/embedded pages never inherit the local trusted backend URL.
  var baseUrl = explicitBaseUrl ||
    (runnerEnabled && !embeddedMode
      ? (String(savedBaseUrl).trim().replace(/\/+$/, "") || DEFAULT_BASE)
      : "");
  var sessionId = null;
  var fileStatusEl = null;
  var sampleData = null;
  var sampleDataPromise = null;
  var busy = false;
  var panel = null;
  var statusEl = null;
  var outputEl = null;
  var sessionEl = null;
  var safetyEl = null;
  var apiButtonEl = null;

  var API = {
    defaultBaseUrl: DEFAULT_BASE,
    getBaseUrl: function () { return baseUrl; },
    isRunnerEnabled: function () { return runnerEnabled; },
    setBaseUrl: function (value, persist) {
      baseUrl = String(value || "").trim().replace(/\/+$/, "");
      if (persist) {
        try {
          if (baseUrl) localStorage.setItem("biomedical_api_base", baseUrl);
          else localStorage.removeItem("biomedical_api_base");
        } catch (error) {}
      }
      return baseUrl;
    },
    enableRunner: function (value) { return enableRunner(value); },
    getSessionId: function () { return sessionId; },
    getLastResult: function () { return window.__bmLastResult || null; },
    attach: attach,
    health: health,
    ensureSession: ensureSession,
    newSession: newSession,
    resetSession: resetSession,
    execute: executeCode,
    runCard: runCard,
    samples: SAMPLES,
    selectSample: selectSample,
    uploadFile: uploadFile,
    loadDataset: loadDataset
  };

  async function request(path, options) {
    options = options || {};
    requireRunner();
    var config = {
      method: options.method || "GET",
      headers: options.headers || {}
    };
    if (options.body !== undefined) {
      config.body = JSON.stringify(options.body);
      config.headers["Content-Type"] = "application/json";
    }
    var response;
    try {
      response = await fetch(baseUrl + path, config);
    } catch (error) {
      throw new Error("Cannot reach backend at " + baseUrl + ". Check the URL and that the trusted backend is running.");
    }
    var payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new Error("Backend returned a non-JSON response (HTTP " + response.status + ").");
    }
    if (!response.ok || payload.success === false) {
      var detail = payload.message || (payload.errors && payload.errors[0] && payload.errors[0].detail) || response.statusText;
      throw new Error(String(detail));
    }
    return payload.data;
  }

  function setStatus(text, kind) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = "bm-status bm-" + (kind || "info");
  }

  function requireRunner() {
    if (!runnerEnabled) {
      throw new Error("Backend execution is off in this page. Enter a trusted backend URL and press Enable runner.");
    }
    if (!baseUrl) {
      throw new Error("No backend API URL is configured.");
    }
  }

  async function enableRunner(value) {
    var nextBaseUrl = value === undefined ? baseUrl : String(value).trim().replace(/\/+$/, "");
    if (!nextBaseUrl) {
      throw new Error("Enter a trusted backend API URL before enabling the runner.");
    }
    API.setBaseUrl(nextBaseUrl, true);
    runnerEnabled = true;
    updateRunnerControls();
    setStatus("Backend runner enabled for " + baseUrl, "info");
    return health();
  }

  function updateRunnerControls() {
    runnerButtons.forEach(function (button) {
      if (button.dataset.bmExecType !== "notebook") return;
      button.disabled = !runnerEnabled;
      button.textContent = runnerEnabled ? "▶ Run backend" : "Run backend (off)";
      button.title = runnerEnabled
        ? "Run this cell in the local trusted Python backend"
        : "Backend execution is off in this page.";
    });
    sampleButtons.forEach(function (button) {
      button.disabled = !runnerEnabled;
      button.title = runnerEnabled ? "Load this simulated dataset" : "Enable the backend runner first.";
    });
    fileInputs.forEach(function (input) {
      input.disabled = !runnerEnabled;
    });
    if (apiButtonEl) {
      apiButtonEl.textContent = runnerEnabled ? "Set API" : "Enable runner";
    }
    if (safetyEl) {
      safetyEl.textContent = runnerEnabled
        ? "Local trusted backend only. Use simulated or non-sensitive teaching data."
        : "No backend is configured on this public page. Enter a trusted backend URL only if you deliberately want to enable execution.";
    }
    if (!runnerEnabled) {
      setStatus("Backend execution is off.", "info");
    }
  }

  function addStyles() {
    if (document.getElementById("bm-api-styles")) return;
    var style = document.createElement("style");
    style.id = "bm-api-styles";
    style.textContent = [
      ".bm-panel{position:fixed;right:16px;bottom:16px;width:min(430px,calc(100vw - 32px));max-height:62vh;z-index:9999;",
      "background:var(--card,#eef5f8);color:var(--fg,#1b2a3a);border:1px solid var(--ac,#0b5d7a);",
      "border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden;font:13px system-ui}",
      ".bm-head{padding:8px 10px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--bd,#cdd8e0)}",
      ".bm-head strong{margin-right:auto}.bm-panel button{padding:4px 8px;font-size:12px}",
      ".bm-status{padding:6px 10px;font-size:12px;border-bottom:1px solid var(--bd,#cdd8e0)}",
      ".bm-ok{color:#12683c}.bm-error{color:#a61b1b}.bm-info{color:var(--ac,#0b5d7a)}",
      ".bm-output{margin:0;padding:10px;max-height:40vh;overflow:auto;white-space:pre-wrap;word-break:break-word;",
      "background:#10202b;color:#e6f1f7;font:12px Consolas,monospace}",
      ".bm-output img{display:block;max-width:100%;margin:8px 0;background:#fff}",
      ".bm-run-btn{padding:3px 8px!important;font-size:12px!important;white-space:nowrap}",
      ".bm-run-btn[disabled]{opacity:.55;cursor:not-allowed}",
      ".bm-file-actions{padding:10px 12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}",
      ".bm-file-actions button{padding:7px 10px}",
      ".bm-file-actions label{display:inline-flex;align-items:center;gap:6px;font-size:13px}",
      ".bm-file-status{padding:8px 12px;border-top:1px solid var(--bd,#cdd8e0);font-weight:600;color:var(--ac,#0b5d7a)}",
      ".bm-api-row{padding:6px 10px;display:flex;gap:6px;align-items:center;border-bottom:1px solid var(--bd,#cdd8e0)}",
      ".bm-api-row input{flex:1;min-width:0;padding:4px 6px;font-size:12px;border:1px solid var(--bd,#cdd8e0);border-radius:4px;background:var(--card,#eef5f8);color:var(--fg,#1b2a3a)}",
      ".bm-chapter-index{margin:12px 0 18px;padding:12px 14px;border:2px solid var(--ac,#0b5d7a);border-radius:10px;background:var(--card,#eef5f8)}",
      ".bm-chapter-index>strong{display:block;margin-bottom:8px;color:var(--ac,#0b5d7a);font-size:16px}",
      ".bm-chapter-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px}",
      ".bm-chapter-links a{display:block;padding:7px 8px;border:1px solid var(--bd,#cdd8e0);border-radius:6px;background:var(--bg,#fff);color:var(--fg,#1b2a3a);text-decoration:none;font-size:13px;line-height:1.25}",
      ".bm-chapter-links a:hover,.bm-chapter-links a:focus-visible{border-color:var(--ac,#0b5d7a);color:var(--ac,#0b5d7a)}",
      "@media(max-width:640px){.bm-chapter-index{padding:10px}.bm-chapter-links{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.bm-chapter-links a{font-size:12px;padding:6px}}",
      "@media print{.bm-panel,.bm-run-btn,.bm-file-actions,.bm-chapter-index{display:none!important}}"
    ].join("");
    document.head.appendChild(style);
  }

  function createPanel() {
    if (panel) return panel;
    addStyles();
    panel = document.createElement("div");
    panel.className = "bm-panel";
    panel.setAttribute("aria-label", "Biomedical backend runner");

    var head = document.createElement("div");
    head.className = "bm-head";
    var title = document.createElement("strong");
    title.textContent = "Backend runner";
    head.appendChild(title);

    var newBtn = makeButton("New session", function () { newSession().catch(showError); });
    var resetBtn = makeButton("Reset variables", function () { resetSession().catch(showError); });
    var clearBtn = makeButton("Clear output", clearOutput);
    var hideBtn = makeButton("Hide", function () { panel.style.display = "none"; });
    head.appendChild(newBtn);
    head.appendChild(resetBtn);
    head.appendChild(clearBtn);
    head.appendChild(hideBtn);

    statusEl = document.createElement("div");
    statusEl.className = "bm-status bm-info";
    statusEl.textContent = runnerEnabled ? "Checking backend…" : "Backend execution is off.";

    sessionEl = document.createElement("div");
    sessionEl.className = "bm-status bm-info";
    sessionEl.textContent = "No session yet";

    var apiRow = document.createElement("div");
    apiRow.className = "bm-api-row";
    var apiInput = document.createElement("input");
    apiInput.type = "url";
    apiInput.value = baseUrl;
    apiInput.placeholder = "Backend API base URL";
    apiInput.setAttribute("aria-label", "Backend API base URL");
    apiButtonEl = makeButton(runnerEnabled ? "Set API" : "Enable runner", function () {
      enableRunner(apiInput.value).then(function () {
        apiInput.value = baseUrl;
      }).catch(showError);
    });
    apiRow.appendChild(apiInput);
    apiRow.appendChild(apiButtonEl);

    safetyEl = document.createElement("div");
    safetyEl.className = "bm-status bm-info";

    outputEl = document.createElement("pre");
    outputEl.className = "bm-output";
    outputEl.textContent = "Run a NOTEBOOK CELL card. Output appears here.";

    panel.appendChild(head);
    panel.appendChild(statusEl);
    panel.appendChild(sessionEl);
    panel.appendChild(apiRow);
    panel.appendChild(safetyEl);
    panel.appendChild(outputEl);
    document.body.appendChild(panel);
    return panel;
  }

  function makeButton(label, handler) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
  }

  function showError(error) {
    var message = error && error.message ? error.message : String(error);
    setStatus(message, "error");
    if (outputEl) outputEl.textContent = "Error: " + message;
  }

  function clearOutput() {
    if (outputEl) outputEl.textContent = "Output cleared.";
  }

  async function health() {
    var data = await request("/health");
    setStatus("Backend online (" + baseUrl + ")", "ok");
    return data;
  }

  async function ensureSession() {
    if (sessionId) return sessionId;
    var data = await request("/sessions", {
      method: "POST",
      body: { name: "HTML Command Library" }
    });
    sessionId = data.session_id;
    if (sessionEl) sessionEl.textContent = "Session " + sessionId.slice(0, 8) + " (" + data.mode + ")";
    return sessionId;
  }

  async function newSession() {
    var old = sessionId;
    sessionId = null;
    if (old) {
      try { await request("/sessions/" + encodeURIComponent(old), { method: "DELETE" }); }
      catch (error) { /* a stale session should not block a new one */ }
    }
    var data = await request("/sessions", {
      method: "POST",
      body: { name: "HTML Command Library" }
    });
    sessionId = data.session_id;
    if (sessionEl) sessionEl.textContent = "New session " + sessionId.slice(0, 8);
    setStatus("New session created.", "ok");
    return sessionId;
  }

  async function resetSession() {
    if (!sessionId) return ensureSession();
    var data = await request("/sessions/" + encodeURIComponent(sessionId) + "/reset", {
      method: "POST",
      body: {}
    });
    if (sessionEl) sessionEl.textContent = "Session " + data.session_id.slice(0, 8) + " reset";
    setStatus("Session variables cleared.", "ok");
    return data;
  }

  async function executeCode(code, options) {
    options = options || {};
    if (!String(code || "").trim()) throw new Error("Code is empty.");
    if (busy) throw new Error("A cell is already running.");
    busy = true;
    setStatus("Running…", "info");
    if (outputEl) outputEl.textContent = "Running…";
    try {
      var id = await ensureSession();
      var data = await request("/execute", {
        method: "POST",
        body: {
          code: String(code),
          session_id: id,
          timeout_seconds: options.timeout_seconds || 30,
          reset_first: Boolean(options.reset_first)
        }
      });
      renderResult(data);
      window.__bmLastResult = data;
      return data;
    } finally {
      busy = false;
    }
  }

  function renderResult(data) {
    var parts = [];
    if (data.stdout) parts.push(data.stdout);
    if (data.results && data.results.length) parts.push(data.results.join("\n"));
    if (data.stderr) parts.push("[stderr]\n" + data.stderr);
    if (data.error) {
      parts.push("[error] " + data.error.ename + ": " + data.error.evalue);
      if (data.error.traceback && data.error.traceback.length) {
        parts.push(data.error.traceback.join("\n"));
      }
    }
    if (!parts.length) parts.push("(No textual output.)");
    parts.push("[status=" + data.status + ", duration_ms=" + data.duration_ms + ", execution=" + data.execution_count + "]");
    if (outputEl) {
      outputEl.textContent = parts.join("\n");
      (data.figures || []).forEach(function (figure) {
        if (figure.base64) {
          var image = document.createElement("img");
          image.src = "data:image/png;base64," + figure.base64;
          image.alt = "Generated figure " + figure.filename;
          outputEl.appendChild(image);
        }
      });
    }
    setStatus(
      data.status === "ok" ? "Completed in " + data.duration_ms + " ms" : "Cell raised " + data.error.ename,
      data.status === "ok" ? "ok" : "error"
    );
  }

  async function runCard(card, button) {
    var execType = card.getAttribute("data-exec-type") || "unknown";
    if (execType !== "notebook") {
      setStatus(execType.toUpperCase() + " cells are not sent to the Python API.", "info");
      return null;
    }
    var codeEl = card.querySelector("pre:not(.o)");
    var code = codeEl ? codeEl.textContent : "";
    if (!code.trim()) {
      setStatus("This card has no Python code to run.", "error");
      return null;
    }
    if (button) {
      button.disabled = true;
      button.textContent = "Running…";
    }
    try {
      return await executeCode(code);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "▶ Run backend";
      }
    }
  }

  function loadSampleData() {
    if (sampleData) return Promise.resolve(sampleData);
    if (sampleDataPromise) return sampleDataPromise;
    sampleDataPromise = new Promise(function (resolve) {
      if (window.BM_SAMPLE_FILES) {
        sampleData = window.BM_SAMPLE_FILES;
        resolve(sampleData);
        return;
      }
      var script = document.createElement("script");
      script.src = "./sample_data.js";
      script.onload = function () {
        sampleData = window.BM_SAMPLE_FILES || {};
        resolve(sampleData);
      };
      script.onerror = function () {
        sampleData = {};
        resolve(sampleData);
      };
      document.head.appendChild(script);
    });
    return sampleDataPromise;
  }

  function base64ToBlob(base64, type) {
    var binary = atob(base64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: type || "text/csv" });
  }

  async function fetchSample(file) {
    var embedded = await loadSampleData();
    if (embedded[file]) {
      return base64ToBlob(embedded[file], "text/csv");
    }
    var response;
    try {
      response = await fetch("./samples/" + encodeURIComponent(file));
    } catch (error) {
      throw new Error("Sample data is unavailable. Regenerate sample_data.js with python frontend_integration\\embed_samples.py");
    }
    if (!response.ok) {
      throw new Error("Sample file not found: " + file + ". Regenerate sample_data.js with python frontend_integration\\embed_samples.py");
    }
    return await response.blob();
  }

  async function uploadRequest(file) {
    requireRunner();
    var form = new FormData();
    form.append("file", file, file.name);
    var response;
    try {
      response = await fetch(baseUrl + "/datasets", { method: "POST", body: form });
    } catch (error) {
      throw new Error("Cannot reach backend at " + baseUrl + ".");
    }
    var payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new Error("Backend returned a non-JSON upload response (HTTP " + response.status + ").");
    }
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || "Dataset upload failed (HTTP " + response.status + ").");
    }
    return payload.data;
  }

  async function selectSample(file, label) {
    if (!file) throw new Error("No sample file specified.");
    var blob = await fetchSample(file);
    var named = new File([blob], file, { type: blob.type || "text/csv" });
    return uploadFile(named, label || file);
  }

  async function uploadFile(file, label) {
    if (!file) throw new Error("Choose a file first.");
    setStatus("Uploading " + file.name + "…", "info");
    var uploaded = await uploadRequest(file);
    return loadDataset(uploaded, label || file.name);
  }

  async function loadDataset(uploaded, label) {
    await ensureSession();
    var name = uploaded.filename || label || "dataset";
    var lower = name.toLowerCase();
    var pathLiteral = JSON.stringify(uploaded.storage_path);
    var reader;
    if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
      reader = "pd.read_excel(" + pathLiteral + ")";
    } else if (lower.endsWith(".json")) {
      reader = "pd.read_json(" + pathLiteral + ")";
    } else {
      reader = "pd.read_csv(" + pathLiteral + ")";
    }
    var code = [
      "import pandas as pd",
      "DATASET_ID = " + JSON.stringify(uploaded.dataset_id),
      "DATASET_NAME = " + JSON.stringify(name),
      "df = " + reader,
      'print(f"Loaded {DATASET_NAME}: {df.shape[0]} rows x {df.shape[1]} columns")',
      "df.head()"
    ].join("\n");
    var result = await executeCode(code);
    var selected = {
      label: label || name,
      filename: name,
      dataset_id: uploaded.dataset_id,
      rows: uploaded.rows,
      columns: uploaded.columns_count,
      session_id: result.session_id,
      storage_path: uploaded.storage_path
    };
    window.__bmSelectedDataset = selected;
    if (fileStatusEl) {
      fileStatusEl.textContent =
        "Loaded " + selected.label + ": " + selected.rows + " rows × " + selected.columns +
        " columns (dataset " + selected.dataset_id.slice(0, 8) + ")";
    }
    return selected;
  }

  function createDataFileSection() {
    if (document.getElementById("simulated_data_files")) return document.getElementById("simulated_data_files");

    var nav = document.querySelector("nav");
    if (nav && !nav.querySelector('a[href="#simulated_data_files"]')) {
      var link = document.createElement("a");
      link.href = "#simulated_data_files";
      link.textContent = "Simulated data";
      link.title = "Choose a simulated dataset for the backend runner";
      var firstLink = nav.querySelector("a");
      nav.insertBefore(link, firstLink || null);
    }

    var section = document.createElement("section");
    section.className = "s";
    section.id = "simulated_data_files";
    section.setAttribute("data-chapter-title", "Simulated data files for the backend runner");

    var heading = document.createElement("h2");
    heading.textContent = "Data files: choose a simulated dataset";
    section.appendChild(heading);

    var intro = document.createElement("div");
    intro.className = "chapter-intro-simple";
    intro.textContent =
      "Select one of the bundled simulated datasets, or upload your own CSV, Excel or JSON file. " +
      "The selected file is uploaded to the local backend and loaded into the active runner session as df, " +
      "with DATASET_ID and DATASET_NAME available for reproducible notes. These files are simulated teaching data, not patient data.";
    section.appendChild(intro);

    var declaration = document.createElement("div");
    declaration.className = "w";
    declaration.innerHTML = "<b>DECLARATION: All sample files are simulated and for educational purposes only.</b>";
    section.appendChild(declaration);

    var card = document.createElement("div");
    card.className = "c";
    card.setAttribute("data-exec-type", "files");

    var header = document.createElement("div");
    header.className = "t";
    var title = document.createElement("span");
    title.textContent = "Simulated data files";
    var badge = document.createElement("span");
    badge.className = "exec-badge exec-notebook";
    badge.textContent = "DATA FILES";
    header.appendChild(title);
    header.appendChild(badge);
    card.appendChild(header);

    var message = document.createElement("div");
    message.className = "m";
    message.textContent =
      "Choose a file below. It is uploaded through /api/v1/datasets and loaded into the same persistent kernel used by the Run backend buttons.";
    card.appendChild(message);

    var actions = document.createElement("div");
    actions.className = "bm-file-actions";
    SAMPLES.forEach(function (sample) {
      var button = makeButton(sample.label, function () {
        selectSample(sample.file, sample.label).catch(showError);
      });
      button.dataset.bmSample = sample.file;
      sampleButtons.push(button);
      actions.appendChild(button);
    });

    var label = document.createElement("label");
    label.textContent = "Upload your own file: ";
    var input = document.createElement("input");
    input.type = "file";
    input.accept = ".csv,.xlsx,.xls,.json";
    fileInputs.push(input);
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) {
        uploadFile(input.files[0]).catch(showError);
      }
    });
    label.appendChild(input);
    actions.appendChild(label);
    card.appendChild(actions);

    fileStatusEl = document.createElement("div");
    fileStatusEl.className = "bm-file-status";
    fileStatusEl.textContent = "No dataset selected.";
    card.appendChild(fileStatusEl);

    var after = document.createElement("div");
    after.className = "run-after";
    after.innerHTML = "<strong>After selection: </strong><code>df</code>, <code>DATASET_ID</code> and <code>DATASET_NAME</code> are ready in the active backend session. Run other cells normally.";
    card.appendChild(after);

    var errors = document.createElement("div");
    errors.className = "card-errors";
    errors.textContent = "If sample loading fails, serve this folder over HTTP and keep samples/ beside the integrated HTML. Check that the backend is running on the configured base URL.";
    card.appendChild(errors);

    section.appendChild(card);
    var first = document.querySelector("section.s");
    if (first && first !== section) {
      first.parentNode.insertBefore(section, first);
    } else {
      document.body.appendChild(section);
    }
    return section;
  }

  function chapterLabel(section) {
    var raw = section.getAttribute("data-chapter-title") || "";
    if (!raw) {
      var heading = section.querySelector("h2");
      raw = heading ? heading.textContent : section.id;
    }
    return raw.replace(/Copy chapter code/gi, "").replace(/\s+/g, " ").trim() || section.id;
  }

  function createEmbeddedChapterIndex() {
    if (!embeddedMode || document.getElementById("bm-chapter-index")) return;
    var sections = Array.prototype.slice.call(document.querySelectorAll("section.s[id]"));
    if (!sections.length) return;

    var index = document.createElement("nav");
    index.id = "bm-chapter-index";
    index.className = "bm-chapter-index";
    index.setAttribute("aria-label", "Command library chapters");

    var heading = document.createElement("strong");
    heading.textContent = "Chapters in this library (" + sections.length + ")";
    index.appendChild(heading);

    var links = document.createElement("div");
    links.className = "bm-chapter-links";
    sections.forEach(function (section) {
      var link = document.createElement("a");
      link.href = "#" + encodeURIComponent(section.id);
      link.textContent = chapterLabel(section);
      link.title = "Go to " + chapterLabel(section);
      links.appendChild(link);
    });
    index.appendChild(links);

    var cover = document.getElementById("designed-cover-page") || document.body.firstElementChild;
    if (cover && cover.parentNode) {
      cover.parentNode.insertBefore(index, cover);
    } else {
      document.body.appendChild(index);
    }
    return index;
  }

  function attach() {
    createPanel();
    createDataFileSection();
    createEmbeddedChapterIndex();
    var cards = document.querySelectorAll('[data-py="1"]');
    cards.forEach(function (card) {
      if (card.querySelector(".bm-run-btn")) return;
      var header = card.querySelector(".t") || card;
      var execType = card.getAttribute("data-exec-type") || "unknown";
      var button = makeButton(execType === "notebook" ? "▶ Run backend" : "Backend: n/a", function () {
        runCard(card, button).catch(showError);
      });
      button.className = "bm-run-btn";
      button.dataset.bmExecType = execType;
      runnerButtons.push(button);
      if (execType !== "notebook") {
        button.disabled = true;
        button.title = execType.toUpperCase() + " commands are not Python notebook cells.";
      }
      header.appendChild(button);
    });
    updateRunnerControls();
    if (runnerEnabled) {
      health().catch(function (error) {
        setStatus(error.message, "error");
      });
    }
    return { attached: cards.length };
  }

  window.BiomedicalAPI = API;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach, { once: true });
  } else {
    attach();
  }
})();
