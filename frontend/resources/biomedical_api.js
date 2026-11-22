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
  var toolRowEl = null;
  var analysisSelectEl = null;
  var analysisColumnsEl = null;
  var analysisOptionsEl = null;
  var notebookNameEl = null;
  var notebookIdEl = null;
  var reportTitleEl = null;
  var reportFormatEl = null;
  var reopenButtonEl = null;
  var LIBRARY_TITLE = "Python Command Library for biomedical and health sciences";

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
    loadDataset: loadDataset,
    clearDatasetState: clearDatasetState,
    refreshAnalysisMethods: refreshAnalysisMethods,
    runAnalysis: runAnalysis,
    saveNotebook: saveNotebook,
    loadNotebook: loadNotebook,
    generateReport: generateReport,
    downloadReport: downloadReport
  };

  async function request(path, options) {
    options = options || {};
    if (!options.skipRunnerCheck) requireRunner();
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
    var previousBaseUrl = baseUrl;
    API.setBaseUrl(nextBaseUrl, false);
    try {
      var healthData = await health();
      runnerEnabled = true;
      API.setBaseUrl(nextBaseUrl, true);
      updateRunnerControls();
      setStatus("Backend runner enabled for " + baseUrl, "ok");
      refreshAnalysisMethods().catch(function () {});
      return healthData;
    } catch (error) {
      API.setBaseUrl(previousBaseUrl, false);
      runnerEnabled = false;
      updateRunnerControls();
      setStatus("Backend not enabled: " + (error && error.message ? error.message : String(error)), "error");
      throw error;
    }
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
    if (toolRowEl) {
      Array.prototype.forEach.call(toolRowEl.querySelectorAll("button,input,select"), function (control) {
        control.disabled = !runnerEnabled;
      });
    }
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
      ".bm-copy-in-code{position:absolute!important;top:7px;right:8px;z-index:2;width:30px;height:26px;padding:0!important;font-size:16px!important;line-height:24px!important;border:1px solid #3d5f72!important;border-radius:5px!important;background:#1b3446!important;color:#d8eaf3!important}",
      ".bm-copy-in-code:hover,.bm-copy-in-code:focus-visible{background:#315267!important;outline:none}",
      ".bm-run-btn[disabled]{opacity:.55;cursor:not-allowed}",
      ".bm-file-actions{padding:10px 12px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}",
      ".bm-file-actions button{padding:7px 10px}",
      ".bm-file-actions label{display:inline-flex;align-items:center;gap:6px;font-size:13px}",
      ".bm-file-status{padding:8px 12px;border-top:1px solid var(--bd,#cdd8e0);font-weight:600;color:var(--ac,#0b5d7a)}",
      ".bm-api-row{padding:6px 10px;display:flex;gap:6px;align-items:center;border-bottom:1px solid var(--bd,#cdd8e0)}",
      ".bm-api-row input{flex:1;min-width:0;padding:4px 6px;font-size:12px;border:1px solid var(--bd,#cdd8e0);border-radius:4px;background:var(--card,#eef5f8);color:var(--fg,#1b2a3a)}",
      ".bm-tools{padding:8px 10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;border-bottom:1px solid var(--bd,#cdd8e0)}",
      ".bm-tools select,.bm-tools input{flex:1;min-width:110px;padding:4px 6px;font-size:12px;border:1px solid var(--bd,#cdd8e0);border-radius:4px;background:var(--card,#eef5f8);color:var(--fg,#1b2a3a)}",
      ".bm-tools .bm-wide{flex-basis:100%}",
      ".bm-tools button[disabled]{opacity:.55;cursor:not-allowed}",
      ".bm-reopen{position:fixed;right:16px;bottom:16px;z-index:9999;display:none;padding:7px 10px;font-size:12px;border:1px solid var(--ac,#0b5d7a);border-radius:6px;background:var(--card,#eef5f8);color:var(--fg,#1b2a3a);box-shadow:0 4px 14px rgba(0,0,0,.2)}",
      ".bm-chapter-index{margin:12px 0 18px;padding:12px 14px;border:2px solid var(--ac,#0b5d7a);border-radius:10px;background:var(--card,#eef5f8)}",
      ".bm-chapter-index>strong{display:block;margin-bottom:8px;color:var(--ac,#0b5d7a);font-size:16px}",
      ".bm-chapter-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:6px}",
      ".bm-chapter-links a{display:block;padding:7px 8px;border:1px solid var(--bd,#cdd8e0);border-radius:6px;background:var(--bg,#fff);color:var(--fg,#1b2a3a);text-decoration:none;font-size:13px;line-height:1.25}",
      ".bm-chapter-links a:hover,.bm-chapter-links a:focus-visible{border-color:var(--ac,#0b5d7a);color:var(--ac,#0b5d7a)}",
      ".bm-chapter-track{margin:10px 0 2px}",
      ".bm-chapter-track>strong{display:block;margin-bottom:5px;color:var(--ac,#0b5d7a);font-size:13px}",
      ".bm-chapter-track .bm-chapter-links{margin-top:0}",
      "@media(max-width:640px){.bm-chapter-index{padding:10px}.bm-chapter-links{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.bm-chapter-links a{font-size:12px;padding:6px}}",
      "@media print{.bm-panel,.bm-reopen,.bm-run-btn,.bm-file-actions,.bm-chapter-index{display:none!important}}"
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
    var hideBtn = makeButton("Hide", hidePanel);
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

    toolRowEl = document.createElement("div");
    toolRowEl.className = "bm-tools";

    analysisSelectEl = document.createElement("select");
    analysisSelectEl.setAttribute("aria-label", "Statistical analysis method");
    analysisSelectEl.title = "Statistical analysis method";
    analysisSelectEl.appendChild(new Option("Loading methods…", ""));
    var analysisBtn = makeButton("Run analysis", function () { runAnalysisFromUI().catch(showError); });

    analysisColumnsEl = document.createElement("input");
    analysisColumnsEl.type = "text";
    analysisColumnsEl.placeholder = "Columns, comma-separated";
    analysisColumnsEl.setAttribute("aria-label", "Analysis columns");
    analysisColumnsEl.title = "Columns used by the statistical analysis";

    analysisOptionsEl = document.createElement("input");
    analysisOptionsEl.type = "text";
    analysisOptionsEl.className = "bm-wide";
    analysisOptionsEl.placeholder = 'Options JSON, e.g. {"alpha":0.05}';
    analysisOptionsEl.setAttribute("aria-label", "Analysis options JSON");
    analysisOptionsEl.title = "Optional JSON object passed to the analysis endpoint";

    notebookNameEl = document.createElement("input");
    notebookNameEl.type = "text";
    notebookNameEl.placeholder = "Notebook name";
    notebookNameEl.value = "Command library notebook";
    notebookNameEl.setAttribute("aria-label", "Notebook name");
    var saveNotebookBtn = makeButton("Save notebook", function () { saveNotebook().catch(showError); });

    notebookIdEl = document.createElement("input");
    notebookIdEl.type = "text";
    notebookIdEl.placeholder = "Notebook ID (blank = first)";
    notebookIdEl.setAttribute("aria-label", "Notebook ID to load");
    notebookIdEl.title = "Leave blank to load the most recently saved notebook";
    var loadNotebookBtn = makeButton("Load notebook", function () { loadNotebook().catch(showError); });

    reportTitleEl = document.createElement("input");
    reportTitleEl.type = "text";
    reportTitleEl.placeholder = "Report title";
    reportTitleEl.value = "Biomedical analysis report";
    reportTitleEl.setAttribute("aria-label", "Report title");
    reportFormatEl = document.createElement("select");
    reportFormatEl.setAttribute("aria-label", "Report format");
    [["pdf", "PDF"], ["html", "HTML"], ["xlsx", "Excel"], ["csv", "CSV"]].forEach(function (item) {
      reportFormatEl.appendChild(new Option(item[1], item[0]));
    });
    var reportBtn = makeButton("Download report", function () { downloadReport().catch(showError); });

    toolRowEl.appendChild(analysisSelectEl);
    toolRowEl.appendChild(analysisBtn);
    toolRowEl.appendChild(analysisColumnsEl);
    toolRowEl.appendChild(analysisOptionsEl);
    toolRowEl.appendChild(notebookNameEl);
    toolRowEl.appendChild(saveNotebookBtn);
    toolRowEl.appendChild(notebookIdEl);
    toolRowEl.appendChild(loadNotebookBtn);
    toolRowEl.appendChild(reportTitleEl);
    toolRowEl.appendChild(reportFormatEl);
    toolRowEl.appendChild(reportBtn);

    safetyEl = document.createElement("div");
    safetyEl.className = "bm-status bm-info";

    outputEl = document.createElement("pre");
    outputEl.className = "bm-output";
    outputEl.textContent = "Run a NOTEBOOK CELL card. Output appears here.";

    panel.appendChild(head);
    panel.appendChild(statusEl);
    panel.appendChild(sessionEl);
    panel.appendChild(apiRow);
    panel.appendChild(toolRowEl);
    panel.appendChild(safetyEl);
    panel.appendChild(outputEl);
    document.body.appendChild(panel);

    reopenButtonEl = makeButton("Show backend", showPanel);
    reopenButtonEl.className = "bm-reopen";
    reopenButtonEl.id = "bm-reopen";
    document.body.appendChild(reopenButtonEl);
    hidePanel();
    return panel;
  }

  function hidePanel() {
    if (panel) panel.style.display = "none";
    if (reopenButtonEl) reopenButtonEl.style.display = "block";
  }

  function showPanel() {
    if (panel) panel.style.display = "flex";
    if (reopenButtonEl) reopenButtonEl.style.display = "none";
  }

  function makeButton(label, handler) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", handler);
    return button;
  }

  function wireFocusReading(link) {
    link.addEventListener("click", function () {
      if (typeof window.enterFocusReading === "function") window.enterFocusReading();
    });
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
    if (!baseUrl) throw new Error("No backend API URL is configured.");
    var data = await request("/health", { skipRunnerCheck: true });
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
    clearDatasetState("No dataset loaded in the new session.");
    setStatus("New session created.", "ok");
    return sessionId;
  }

  async function resetSession() {
    clearDatasetState("No dataset loaded after reset. Select the file again.");
    if (!sessionId) return ensureSession();
    var data = await request("/sessions/" + encodeURIComponent(sessionId) + "/reset", {
      method: "POST",
      body: {}
    });
    if (sessionEl) sessionEl.textContent = "Session " + data.session_id.slice(0, 8) + " reset";
    clearDatasetState("No dataset loaded after reset. Select the file again.");
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

  function showData(title, data) {
    var text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    if (outputEl) outputEl.textContent = title + "\n" + text;
  }

  function clearDatasetState(reason) {
    window.__bmSelectedDataset = null;
    if (fileStatusEl) {
      fileStatusEl.textContent = reason || "No dataset selected.";
    }
  }

  async function refreshAnalysisMethods() {
    var data = await request("/analysis/methods", { skipRunnerCheck: true });
    var methods = (data && data.methods) || [];
    if (!analysisSelectEl) return methods;
    var previous = analysisSelectEl.value;
    analysisSelectEl.textContent = "";
    methods.forEach(function (method) {
      analysisSelectEl.appendChild(new Option(method, method));
    });
    if (methods.indexOf(previous) >= 0) analysisSelectEl.value = previous;
    return methods;
  }

  function analysisColumns() {
    var raw = analysisColumnsEl ? analysisColumnsEl.value : "";
    var columns = raw.split(",").map(function (value) { return value.trim(); }).filter(Boolean);
    if (columns.length) return columns;
    var selected = window.__bmSelectedDataset || {};
    var available = selected.numeric_columns || selected.column_names || [];
    return available.slice(0, 2);
  }

  function analysisOptions() {
    var raw = analysisOptionsEl ? analysisOptionsEl.value.trim() : "";
    if (!raw) return {};
    var parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Analysis options must be a JSON object.");
    }
    return parsed;
  }

  async function runAnalysis(options) {
    options = options || {};
    var selected = window.__bmSelectedDataset;
    if (!selected || !selected.dataset_id) {
      throw new Error("Choose or upload a dataset before running an analysis.");
    }
    var analysis = options.analysis || (analysisSelectEl ? analysisSelectEl.value : "");
    if (!analysis) throw new Error("Select a statistical method first.");
    var columns = options.columns || analysisColumns();
    var body = {
      dataset_id: options.dataset_id || selected.dataset_id,
      analysis: analysis,
      columns: columns,
      options: options.options || analysisOptions()
    };
    if (options.group_column) body.group_column = options.group_column;
    if (options.value_column) body.value_column = options.value_column;
    if (!body.value_column && columns.length) body.value_column = columns[0];
    if (!body.group_column && columns.length > 1) body.group_column = columns[1];
    setStatus("Running " + analysis + "…", "info");
    var data = await request("/analysis", { method: "POST", body: body });
    window.__bmLastAnalysis = data;
    showData("Analysis: " + analysis, data);
    setStatus("Analysis completed.", "ok");
    return data;
  }

  function runAnalysisFromUI() {
    return runAnalysis();
  }

  function collectNotebookCells() {
    return Array.prototype.map.call(
      document.querySelectorAll('[data-py="1"][data-exec-type="notebook"]'),
      function (card, index) {
        var codeEl = card.querySelector("pre:not(.o)");
        return {
          cell_type: "code",
          source: codeEl ? codeEl.textContent : "",
          execution_order: index + 1,
          outputs: [],
          metadata: {
            chapter: card.getAttribute("data-chapter-title") ||
              (card.closest("section.s") ? card.closest("section.s").id : ""),
            exec_type: "notebook"
          }
        };
      }
    ).filter(function (cell) { return cell.source.trim().length > 0; });
  }

  async function saveNotebook(options) {
    options = options || {};
    var name = options.name || (notebookNameEl ? notebookNameEl.value.trim() : "");
    if (!name) throw new Error("Enter a notebook name.");
    var cells = options.cells || collectNotebookCells();
    if (!cells.length) throw new Error("No notebook cells were found in this library.");
    var selected = window.__bmSelectedDataset || {};
    var data = await request("/notebooks", {
      method: "POST",
      body: {
        name: name,
        cells: cells,
        metadata: {
          source: "biomedical-command-library",
          dataset_id: selected.dataset_id || null,
          dataset_name: selected.filename || null,
          cell_count: cells.length
        }
      }
    });
    window.__bmLastNotebook = data;
    showData("Notebook saved", data);
    setStatus("Saved notebook '" + name + "'.", "ok");
    return data;
  }

  async function loadNotebook(options) {
    var notebooks = await request("/notebooks");
    if (!notebooks.length) throw new Error("No saved notebooks were found.");
    var notebookId = (options && options.notebook_id) ||
      (notebookIdEl ? notebookIdEl.value.trim() : "");
    if (!notebookId) {
      notebookId = notebooks[0].id || notebooks[0].notebook_id;
    }
    if (!notebookId) throw new Error("The selected notebook has no ID.");
    if (notebookIdEl) notebookIdEl.value = notebookId;
    var data = await request("/notebooks/" + encodeURIComponent(notebookId));
    window.__bmLoadedNotebook = data;
    var cells = data.cells || [];
    showData("Notebook loaded: " + data.name + " (" + cells.length + " cells)", {
      notebook_id: data.id || data.notebook_id,
      name: data.name,
      metadata: data.metadata,
      first_cells: cells.slice(0, 3).map(function (cell) { return cell.source; })
    });
    setStatus("Loaded notebook '" + data.name + "'.", "ok");
    return data;
  }

  function reportSections() {
    var analysis = window.__bmLastAnalysis;
    if (!analysis) {
      return {
        methods: "No statistical analysis was run from this browser session.",
        results: "No results were supplied by this interface.",
        limitations: "No study-specific limitations were supplied.",
        conclusions: "Not provided by this interface."
      };
    }
    return {
      methods: "Method: " + analysis.analysis + ". Assumptions: " +
        ((analysis.assumptions || []).join("; ") || "Not reported."),
      results: JSON.stringify(analysis.results || analysis, null, 2),
      limitations: "Results are computed from the selected dataset by the backend. No study-specific limitations were supplied.",
      conclusions: "Not provided by this interface."
    };
  }

  async function generateReport(options) {
    options = options || {};
    var selected = window.__bmSelectedDataset || {};
    var format = options.format || (reportFormatEl ? reportFormatEl.value : "pdf");
    var title = options.title || (reportTitleEl ? reportTitleEl.value.trim() : "") ||
      "Biomedical analysis report";
    var data = await request("/reports", {
      method: "POST",
      body: {
        title: title,
        study_description: options.study_description ||
          "Teaching report generated from the selected dataset using the biomedical Python backend.",
        format: format,
        sections: options.sections || reportSections(),
        dataset_id: options.dataset_id || selected.dataset_id || null,
        history_ids: options.history_ids || [],
        include_versions: true
      }
    });
    window.__bmLastReport = data;
    showData("Report generated", data);
    setStatus("Report generated (" + format.toUpperCase() + ").", "ok");
    return data;
  }

  async function downloadReport(options) {
    var report = await generateReport(options);
    requireRunner();
    var response;
    try {
      response = await fetch(baseUrl + "/reports/" + encodeURIComponent(report.report_id) + "/download");
    } catch (error) {
      throw new Error("Cannot reach backend at " + baseUrl + ".");
    }
    if (!response.ok) throw new Error("Report download failed (HTTP " + response.status + ").");
    var blob = await response.blob();
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = report.filename || ("report." + report.format);
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    setStatus("Report download started: " + link.download, "ok");
    return report;
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
    var metadata = {};
    try {
      metadata = await request("/datasets/" + encodeURIComponent(uploaded.dataset_id));
    } catch (error) { /* metadata is optional for loading df into the kernel */ }
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
      column_names: metadata.columns || [],
      numeric_columns: metadata.numeric_columns || [],
      categorical_columns: metadata.categorical_columns || [],
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
      wireFocusReading(link);
      var linkHost = nav.querySelector(".topic-track-links") || nav;
      var firstLink = linkHost.querySelector("a");
      linkHost.insertBefore(link, firstLink || null);
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

  var TOPIC_TRACKS = [
    { label: "Foundations", ids: ["ch0", "ch1", "ch2", "book3"] },
    { label: "Data handling", ids: ["book4", "book5", "book6", "book7", "supplement_data_quality"] },
    {
      label: "Wrangling, visualisation & aggregation",
      ids: [
        "book8", "supplement_variable_transformation", "book9", "supplement_visualisation",
        "book10", "supplement_descriptive_statistics", "book11"
      ]
    },
    {
      label: "Statistical methods & modelling",
      ids: [
        "book12", "supplement_hypothesis_testing", "supplement_mean_rank_tests",
        "supplement_categorical_correlation", "supplement_correlation_regression",
        "supplement_advanced_methods", "supplement_sensitivity_validation",
        "statistical_methodology_review"
      ]
    },
    {
      label: "Applied biomedical labs",
      ids: [
        "Biomedical_practical_workflow", "scientific_imports_numpy_lab", "infectious_disease_lab",
        "medical_microbiology_lab", "immunology_lab", "longitudinal_biomarker_review",
        "diagnostic_accuracy_lab", "epidemiology_confounding_lab",
        "infectious_disease_advanced_lab", "survival_analysis_lab", "predictive_modeling_lab"
      ]
    },
    {
      label: "Projects & reproducibility",
      ids: [
        "book13", "supplement_reporting_ethics", "supplement_reusable_workflows",
        "Biomedical_project_sequence", "Biomedical_reproducible_project_lab"
      ]
    },
    {
      label: "Reference & audit",
      ids: ["appendixA", "appendixB", "sol", "audit_coverage"]
    }
  ];

  function chapterLabel(section) {
    var labelled = section.getAttribute("data-topic-label") || "";
    if (labelled) return labelled.replace(/\s+/g, " ").trim();
    var raw = section.getAttribute("data-chapter-title") || "";
    if (!raw) {
      var heading = section.querySelector("h2");
      raw = heading ? heading.textContent : section.id;
    }
    return raw.replace(/Copy chapter code/gi, "").replace(/\s+/g, " ").trim() || section.id;
  }

  function createEmbeddedChapterIndex() {
    if (!embeddedMode || document.getElementById("bm-chapter-index")) return;
    var sections = Array.prototype.slice.call(document.querySelectorAll("section[data-topic-track][id]"));
    if (!sections.length) return;
    var byId = {};
    sections.forEach(function (section) {
      byId[section.id] = section;
    });

    var index = document.createElement("nav");
    index.id = "bm-chapter-index";
    index.className = "bm-chapter-index";
    index.setAttribute("aria-label", "Organized command library topics");

    var heading = document.createElement("strong");
    heading.textContent = "Organized topics (" + sections.length + ")";
    index.appendChild(heading);

    TOPIC_TRACKS.forEach(function (track) {
      var present = track.ids.filter(function (id) { return byId[id]; });
      if (!present.length) return;
      var group = document.createElement("section");
      group.className = "bm-chapter-track";
      group.setAttribute("aria-label", track.label);
      var groupTitle = document.createElement("strong");
      groupTitle.textContent = track.label;
      group.appendChild(groupTitle);
      var links = document.createElement("div");
      links.className = "bm-chapter-links";
      present.forEach(function (id) {
        var section = byId[id];
        var link = document.createElement("a");
        link.href = "#" + encodeURIComponent(section.id);
        link.textContent = chapterLabel(section);
        link.title = "Go to " + chapterLabel(section);
        wireFocusReading(link);
        links.appendChild(link);
      });
      group.appendChild(links);
      index.appendChild(group);
    });

    var cover = document.getElementById("designed-cover-page") || document.body.firstElementChild;
    var originalNav = document.querySelector("nav");
    if (originalNav && originalNav.parentNode) {
      originalNav.parentNode.insertBefore(index, originalNav);
    } else if (cover && cover.parentNode) {
      cover.parentNode.insertBefore(index, cover.nextSibling);
    } else {
      document.body.appendChild(index);
    }
    return index;
  }

  function renameLibraryTitle() {
    document.title = LIBRARY_TITLE;
    var heading = document.querySelector("h1");
    if (heading && heading.textContent.trim() === "Biomedical Python Command Library") {
      heading.textContent = LIBRARY_TITLE;
    }
  }

  function attach() {
    renameLibraryTitle();
    createPanel();
    createDataFileSection();
    createEmbeddedChapterIndex();
    createWindowsSimulation();
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

      var preEl = card.querySelector("pre");
      var copyBtn = Array.prototype.slice.call(header.querySelectorAll("button")).filter(function (candidate) {
        return /copy/i.test(candidate.textContent) || String(candidate.getAttribute("onclick") || "").indexOf("cp(this)") !== -1;
      })[0];
      if (preEl && copyBtn && !copyBtn.classList.contains("bm-copy-in-code")) {
        preEl.style.position = "relative";
        preEl.style.paddingTop = "38px";
        copyBtn.classList.add("bm-copy-in-code");
        copyBtn.textContent = "⧉";
        copyBtn.setAttribute("aria-label", "Copy command");
        copyBtn.setAttribute("title", "Copy command");
        preEl.appendChild(copyBtn);
      }
    });
    updateRunnerControls();
    if (runnerEnabled) {
      health().catch(function (error) {
        setStatus(error.message, "error");
      });
      refreshAnalysisMethods().catch(function () {});
    }
    return { attached: cards.length };
  }


  /* ---- Additive interactive Windows Python setup simulation ---------------- */
  /* Simulated state only. This module never runs host commands or edits PATH. */
  var SIM_KEY = 'biomedical_windows_setup_sim_v1';
  var B = String.fromCharCode(92);
  var NL = String.fromCharCode(10);
  var SIM = null;
  var simRoot = null;
  var simTerminalInput = null;
  var simTerminalOutput = null;
  var simInstallTimer = null;
  var simCurrentFault = '';
  var simDiagnosticsRun = {};

  function wp() {
    return Array.prototype.slice.call(arguments).join(B);
  }

  function simEsc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/'/g, '&#39;')
      .replace(/"/g, '&quot;');
  }

  function simDefaultState() {
    return {
      version: 1,
      selectedRelease: '3.12',
      releases: [
        { tag: '3.11', label: 'Python 3.11.9', note: 'Mature teaching release with broad scientific-package compatibility.' },
        { tag: '3.12', label: 'Python 3.12.10', note: 'Recommended teaching release in this simulated lab.' },
        { tag: '3.13', label: 'Python 3.13.3', note: 'Newer stable series; check package wheels before teaching.' },
        { tag: '3.14', label: 'Python 3.14.0', note: 'Newest stable series in this simulated catalogue; assess compatibility.' }
      ],
      downloaded: false,
      installerOpened: false,
      installing: false,
      installed: false,
      installVersion: '',
      installPath: '',
      pathAdded: false,
      installScope: 'user',
      admin: false,
      launcher: false,
      pipPresent: false,
      storeAlias: true,
      multipleInstalls: false,
      executionPolicy: 'RemoteSigned',
      env: {
        userPath: [wp('C:', 'Users', 'Learner', 'AppData', 'Local', 'Microsoft', 'WindowsApps')],
        systemPath: [wp('C:', 'Windows', 'System32'), wp('C:', 'Windows')]
      },
      pathSnapshot: [wp('C:', 'Windows', 'System32'), wp('C:', 'Windows'), wp('C:', 'Users', 'Learner', 'AppData', 'Local', 'Microsoft', 'WindowsApps')],
      dirs: [wp('C:'), wp('C:', 'Users'), wp('C:', 'Users', 'Learner'), wp('C:', 'Users', 'Learner', 'Downloads'), wp('C:', 'Windows'), wp('C:', 'Windows', 'System32'), wp('D:')],
      cwd: wp('C:', 'Users', 'Learner'),
      shell: 'cmd',
      venvs: {},
      activeVenv: null,
      globalPackages: {},
      jupyterInstalled: false,
      jupyterRunning: false,
      jupyterMode: '',
      notebooks: [],
      requirements: null,
      steps: {
        download: false,
        install: false,
        verify: false,
        path: false,
        jupyter: false,
        directories: false,
        venv: false,
        packages: false,
        requirements: false,
        troubleshooting: false
      },
      checklist: [
        'Choose a stable Python release with 64-bit Windows support',
        'Tick Add python.exe to PATH or record how you will fix PATH later',
        'Verify python, py and python -m pip',
        'Install notebook and jupyterlab with python -m pip',
        'Create an organised project folder',
        'Create a project virtual environment',
        'Install and record the scientific package stack'
      ],
      customChecklist: [],
      faults: {},
      commandCount: 0,
      log: [],
      lastTerminal: '',
      simulationOnly: true
    };
  }

  var SIM_PACKAGES = {
    pip: '24.2',
    numpy: '2.1.3',
    pandas: '2.2.3',
    scipy: '1.14.1',
    statsmodels: '0.14.4',
    matplotlib: '3.9.2',
    seaborn: '0.13.2',
    openpyxl: '3.1.5',
    lifelines: '0.30.0',
    'scikit-learn': '1.5.2',
    notebook: '7.2.1',
    jupyterlab: '4.2.5'
  };

  function simLoadState() {
    var fresh = simDefaultState();
    try {
      var raw = localStorage.getItem(SIM_KEY);
      if (!raw) return fresh;
      var saved = JSON.parse(raw);
      if (!saved || saved.version !== 1) return fresh;
      var merged = fresh;
      Object.keys(saved).forEach(function (key) {
        if (key === 'version') return;
        merged[key] = saved[key];
      });
      merged.steps = Object.assign(fresh.steps, saved.steps || {});
      merged.env = Object.assign(fresh.env, saved.env || {});
      merged.version = 1;
      return merged;
    } catch (error) {
      return fresh;
    }
  }

  function simSaveState() {
    try {
      localStorage.setItem(SIM_KEY, JSON.stringify(SIM));
    } catch (error) {}
  }

  function simMarkStep(name) {
    if (!SIM.steps[name]) {
      SIM.steps[name] = true;
      simSaveState();
    }
  }

  function simPathEntries() {
    return SIM.env.systemPath.concat(SIM.env.userPath);
  }

  function simPythonDir(releaseTag) {
    var tag = String(releaseTag || SIM.installVersion || SIM.selectedRelease).replace(/\./g, '');
    var root = SIM.installScope === 'all' ? wp('C:', 'Program Files') : wp('C:', 'Users', 'Learner', 'AppData', 'Local', 'Programs', 'Python');
    return wp(root, 'Python' + tag);
  }

  function simRefreshTerminal() {
    SIM.pathSnapshot = simPathEntries().slice();
    simSaveState();
    return 'Simulated terminal PATH refreshed. Newly added Python directories are now visible to newly opened commands.';
  }

  function simResolvePython() {
    if (SIM.activeVenv && SIM.venvs[SIM.activeVenv]) {
      var env = SIM.venvs[SIM.activeVenv];
      return { kind: 'venv', path: wp(env.path, 'Scripts', 'python.exe'), version: env.version, store: env.packages, label: SIM.activeVenv };
    }
    var installDir = SIM.installPath || simPythonDir();
    for (var i = 0; i < SIM.pathSnapshot.length; i++) {
      var entry = String(SIM.pathSnapshot[i]).toLowerCase();
      if (SIM.installed && installDir && entry === installDir.toLowerCase()) {
        return { kind: 'python', path: wp(installDir, 'python.exe'), version: SIM.installVersion, store: SIM.globalPackages, label: 'installed Python' };
      }
      if (SIM.multipleInstalls && entry === wp('C:', 'Program Files', 'Python311').toLowerCase()) {
        return { kind: 'python', path: wp('C:', 'Program Files', 'Python311', 'python.exe'), version: '3.11.9', store: SIM.globalPackages, label: 'secondary Python 3.11' };
      }
      if (SIM.storeAlias && entry.indexOf('windowsapps') !== -1) {
        return { kind: 'store', path: wp(entry, 'python.exe'), version: '', store: {}, label: 'Microsoft Store alias' };
      }
    }
    return { kind: 'none', path: '', version: '', store: {}, label: 'no interpreter' };
  }

  function simResolvePy() {
    if (!SIM.installed) return { available: false, versions: [] };
    var versions = [{ tag: SIM.installVersion ? SIM.installVersion.split('.').slice(0, 2).join('.') : SIM.selectedRelease, path: SIM.installPath || simPythonDir(), primary: true }];
    if (SIM.multipleInstalls) {
      versions.push({ tag: '3.11', path: wp('C:', 'Program Files', 'Python311'), primary: false });
    }
    return { available: true, versions: versions };
  }

  function simActiveStore() {
    var resolved = simResolvePython();
    if (resolved.store) return resolved.store;
    return SIM.globalPackages;
  }

  function simStoreLabel() {
    return SIM.activeVenv ? SIM.activeVenv : 'global environment';
  }

  function simFreezeLines(store) {
    return Object.keys(store || {}).sort().map(function (name) {
      return name + '==' + store[name];
    });
  }

  function simListLines(store) {
    var rows = [String('Package').padEnd(20) + String('Version').padEnd(12) + 'Environment'];
    Object.keys(store || {}).sort().forEach(function (name) {
      rows.push(String(name).padEnd(20) + String(store[name]).padEnd(12) + simStoreLabel());
    });
    return rows;
  }

  function simNormalise(value) {
    return String(value || '').toLowerCase().replace(/ +/g, ' ').trim();
  }

  function simResolveFsPath(input) {
    var path = String(input || '').trim().split('/').join(B).replace(/ +$/g, '');
    if (path.length > 2 && path.charAt(1) === ':' && path.charAt(2) === B) {
      return path.replace(/[\\]+$/g, '') || path;
    }
    if (path === '.' || path === '') return SIM.cwd;
    var parts = SIM.cwd.split(B).filter(function (part) { return part; });
    path.split(B).forEach(function (part) {
      if (!part || part === '.') return;
      if (part === '..') parts.pop();
      else parts.push(part);
    });
    return parts.join(B);
  }

  function simEnsureDir(path) {
    var resolved = simResolveFsPath(path);
    if (SIM.dirs.indexOf(resolved) === -1) SIM.dirs.push(resolved);
    return resolved;
  }

  function simExec(raw, options) {
    options = options || {};
    var cmd = String(raw || '').trim().replace(/ +/g, ' ');
    if (!cmd) return [''];
    var lower = cmd.toLowerCase();
    var shell = options.shell || SIM.shell;
    var out = [];
    var resolved = simResolvePython();
    var store = simActiveStore();

    SIM.commandCount += 1;
    SIM.log.push({ cmd: cmd, shell: shell, at: Date.now() });

    if (!SIM.verificationCommands) SIM.verificationCommands = [];
    if (!SIM.pathCommands) SIM.pathCommands = [];

    function done(lines) {
      SIM.lastTerminal = lines.join(NL);
      simFaultDiagnosticDone(cmd);
      if (SIM.verificationCommands && ['python --version', 'py --version', 'python -m pip --version'].every(function (item) { return SIM.verificationCommands.indexOf(item) !== -1; })) simMarkStep('verify');
      if (SIM.pathCommands && ['where.exe python', 'py -0p', 'python -c "import sys; print(sys.executable)"'].every(function (item) { return SIM.pathCommands.indexOf(item) !== -1; })) simMarkStep('path');
      simCheckFaultResolution();
      simSaveState();
      return lines;
    }

    if (lower === '@echo off') return done(['Echo is off. (simulated batch line)']);
    if (lower.indexOf('rem ') === 0) return done(['REM comment ignored. (simulated)']);
    if (lower.indexOf('echo ') === 0) return done([cmd.slice(5)]);
    if (lower === 'pause') return done(['Press any key to continue . . . (simulated)']);

    if (lower === 'python --version' || lower === 'python -v') {
      SIM.verificationCommands.push('python --version');
      if (resolved.kind === 'none') return done(["'python' is not recognised as an internal or external command, operable program or batch file."]);
      if (resolved.kind === 'store') return done(['Python was not found; run without arguments to install from the Microsoft Store, or disable this alias from Windows settings.']);
      return done(['Python ' + resolved.version]);
    }

    if (lower === 'py --version' || lower === 'py -v') {
      SIM.verificationCommands.push('py --version');
      var launcher = simResolvePy();
      if (!launcher.available) return done(["'py' is not recognised as an internal or external command, operable program or batch file."]);
      return done(['Python ' + launcher.versions[0].tag + ' (via Windows Python launcher)']);
    }

    if (lower === 'py -0p') {
      SIM.pathCommands.push('py -0p');
      var launcherList = simResolvePy();
      if (!launcherList.available) return done(["'py' is not recognised; install Python first so the Windows launcher exists."]);
      return done(['Installed Pythons found by the simulated launcher:', '-V:' + launcherList.versions[0].tag + ' *        ' + launcherList.versions[0].path].concat(
        launcherList.versions.slice(1).map(function (item) { return '-V:' + item.tag + '          ' + item.path; })
      ));
    }

    if (lower.indexOf('py -') === 0 && lower.indexOf('--version') !== -1) {
      var wanted = lower.split(' ')[1].replace('-', '');
      var launcherPick = simResolvePy();
      if (!launcherPick.available) return done(["'py' is not recognised."]);
      var pick = launcherPick.versions.filter(function (item) { return item.tag === wanted; })[0];
      if (!pick) return done(['No installed Python matches ' + wanted + '. Run py -0p to list available interpreters.']);
      return done(['Python ' + pick.tag + ' (selected explicitly with the Windows launcher)']);
    }

    if (lower === 'where.exe python' || lower === 'where python') {
      SIM.pathCommands.push('where.exe python');
      var matches = [];
      SIM.pathSnapshot.forEach(function (entry) {
        var e = entry.toLowerCase();
        if (SIM.installPath && e === SIM.installPath.toLowerCase() && SIM.installed) matches.push(wp(SIM.installPath, 'python.exe'));
        if (SIM.multipleInstalls && e === wp('C:', 'Program Files', 'Python311').toLowerCase()) matches.push(wp('C:', 'Program Files', 'Python311', 'python.exe'));
        if (SIM.storeAlias && e.indexOf('windowsapps') !== -1) matches.push(wp(entry, 'python.exe'));
      });
      if (!matches.length) return done(['INFO: Could not find files for the given pattern(s).']);
      return done(matches);
    }

    if (lower === 'where.exe py' || lower === 'where py') {
      SIM.pathCommands.push('where.exe py');
      if (!SIM.installed) return done(['INFO: Could not find files for the given pattern(s).']);
      return done([wp('C:', 'Windows', 'py.exe')]);
    }

    if (lower === 'winver') {
      return done([
        'Simulated Windows version dialog',
        'Edition: Windows 11 Pro (simulated)',
        'Version: 10.0.22631',
        'Architecture: 64-bit (x64)',
        'No host winver application was opened.'
      ]);
    }

    if (lower.indexOf('python -m pip ') === 0) {
      var pipArgs = cmd.slice('python -m pip '.length).trim();
      var pipLower = pipArgs.toLowerCase();
      if (pipLower === '--version' || pipLower === '-v') {
        SIM.verificationCommands.push('python -m pip --version');
        if (resolved.kind === 'none') return done(["'python' is not recognised, so pip cannot be reached through this interpreter."]);
        if (resolved.kind === 'store') return done(['The Microsoft Store alias does not provide a Python interpreter or pip.']);
        var pipVersion = store.pip || (SIM.pipPresent ? SIM_PACKAGES.pip : '');
        if (!pipVersion) return done([resolved.path + ': No module named pip']);
        var interpRoot = resolved.kind === 'venv'
          ? resolved.path.split(B).slice(0, -2).join(B)
          : resolved.path.split(B).slice(0, -1).join(B);
        var pipDir = wp(interpRoot, 'Lib', 'site-packages', 'pip');
        return done(['pip ' + pipVersion + ' from ' + pipDir + ' (python ' + resolved.version + ')']);
      }

      if (pipLower === 'list') return done(simListLines(store));
      if (pipLower === 'check') {
        if (store.pandas && store.numpy && store.pandas === '1.5.3' && parseFloat(store.numpy) >= 2) {
          return done(['pandas 1.5.3 requires numpy<2, but you have numpy ' + store.numpy + '.', 'pip check detected 1 broken requirement.']);
        }
        return done(['No broken requirements found.']);
      }

      if (pipLower === 'freeze') return done(simFreezeLines(store));
      if (pipLower.indexOf('freeze > requirements.txt') !== -1) {
        SIM.requirements = simFreezeLines(store).join(NL);
        simMarkStep('requirements');
        return done(['Wrote ' + SIM.requirements.split(NL).length + ' pinned requirements to simulated requirements.txt.', 'This file reflects the packages in ' + simStoreLabel() + '.']);
      }

      if (pipLower.indexOf('install ') === 0) {
        var installText = pipArgs.slice('install '.length).trim();
        var upgrade = false;
        if (installText.toLowerCase().indexOf('--upgrade ') === 0) {
          upgrade = true;
          installText = installText.slice('--upgrade '.length).trim();
        }
        if (installText.toLowerCase().indexOf('-r ') === 0 || installText.toLowerCase().indexOf('--requirement ') === 0) {
          var reqName = installText.replace(/^-r /i, '').replace(/^--requirement /i, '').trim();
          if (reqName.toLowerCase() !== 'requirements.txt' || !SIM.requirements) {
            return done(['ERROR: Could not open requirements file: ' + reqName + ' (simulated).']);
          }
          var reqRows = [];
          SIM.requirements.split(NL).forEach(function (line) {
            var pair = line.split('==');
            if (pair.length === 2) {
              store[pair[0]] = pair[1];
              reqRows.push(pair[0] + '==' + pair[1]);
            }
          });
          simMarkStep('requirements');
          return done(['Processing simulated requirements.txt', 'Requirement already satisfied or installed: ' + reqRows.join(', '), 'Simulated environment rebuild complete.']);
        }

        var names = installText.split(' ').filter(function (name) { return name; });
        var failed = [];
        var installedNames = [];
        var satisfiedNames = [];
        var cacheNote = SIM.commandCount % 2 === 0 ? 'Using cached wheel. ' : 'Downloading wheel from simulated index. ';
        names.forEach(function (name) {
          var key = name.toLowerCase().replace(/\[.*\]/, '');
          var fault = SIM.faults['package-install-failure'];
          if (key === 'badpkg-xyz' || (fault && fault.networkDown && key === 'lifelines')) {
            failed.push(name);
            return;
          }
          var version = SIM_PACKAGES[key];
          if (!version) {
            failed.push(name);
            return;
          }
          if (store[key] && !upgrade) {
            satisfiedNames.push(name);
            return;
          }
          store[key] = version;
          installedNames.push(name + '==' + version);
        });
        var installLines = [];
        installedNames.forEach(function (name) {
          installLines.push('Collecting ' + name.split('==')[0]);
          installLines.push(cacheNote + 'Saved simulated wheel for ' + name);
        });
        if (failed.length) {
          installLines.push('ERROR: Could not find a compatible simulated package or the simulated network was unavailable: ' + failed.join(', '));
          installLines.push('Nothing was installed for the failed requirement(s). Check the name, network fault or package compatibility.');
          return done(installLines);
        }
        if (satisfiedNames.length) installLines.push('Requirement already satisfied: ' + satisfiedNames.join(', '));
        if (installedNames.length) installLines.push('Successfully installed ' + installedNames.join(' '));
        if (!installedNames.length && !satisfiedNames.length) installLines.push('No packages were selected.');
        if (store.notebook && store.jupyterlab) {
          SIM.jupyterInstalled = true;
          simMarkStep('jupyter');
        }
        if (installedNames.length) simMarkStep('packages');
        return done(installLines);
      }

      if (pipLower.indexOf('uninstall ') === 0) {
        var target = pipArgs.slice('uninstall '.length).trim().toLowerCase();
        if (!store[target]) return done(['WARNING: Package ' + target + ' is not installed in ' + simStoreLabel() + '.']);
        delete store[target];
        return done(['Successfully uninstalled ' + target + ' from simulated ' + simStoreLabel() + '.']);
      }

      return done(['Simulator: python -m pip supports --version, install, list, check, freeze and uninstall in this lab.']);
    }

    if (lower === 'pip --version') {
      if (!SIM.pipPresent && !SIM.globalPackages.pip && !Object.keys(SIM.venvs).some(function (key) { return SIM.venvs[key].packages.pip; })) {
        return done(["'pip' is not recognised as an internal or external command. Prefer python -m pip so you know which interpreter is used."]);
      }
      return done(['pip ' + (store.pip || SIM_PACKAGES.pip) + ' (bare pip is ambiguous; python -m pip is recommended)']);
    }

    if (lower.indexOf('python -m venv ') === 0) {
      if (!SIM.installed) return done(['A Python installation is required before creating a virtual environment.']);
      var venvArg = cmd.slice('python -m venv '.length).trim();
      var venvPath = simResolveFsPath(venvArg);
      var parent = venvPath.split(B).slice(0, -1).join(B);
      if (SIM.dirs.indexOf(parent) === -1) return done(['Cannot create environment: parent folder does not exist in the simulated filesystem: ' + parent]);
      SIM.venvs[venvPath] = { path: venvPath, version: SIM.installVersion, packages: { pip: SIM_PACKAGES.pip }, created: Date.now() };
      simMarkStep('venv');
      return done(['Created simulated virtual environment at ' + venvPath, 'It has its own python.exe and package folder.', 'Activate it or call its python.exe directly; see the activation instructions in the lab.']);
    }

    if (lower.indexOf('python -c ') === 0) {
      var expr = cmd.slice('python -c '.length).trim();
      if ((expr.charAt(0) === '"' && expr.charAt(expr.length - 1) === '"') || (expr.charAt(0) === "'" && expr.charAt(expr.length - 1) === "'")) {
        expr = expr.slice(1, -1);
      }
      var exprLower = expr.toLowerCase();
      if (resolved.kind === 'none') return done(["'python' is not recognised, so the Python -c command cannot run."]);
      if (resolved.kind === 'store') return done(['The Microsoft Store alias cannot execute Python code.']);
      if (exprLower.indexOf('sys.executable') !== -1) {
        SIM.pathCommands.push('python -c "import sys; print(sys.executable)"');
        return done([resolved.path]);
      }
      if (exprLower.indexOf('platform.system()') !== -1) {
        return done(['Windows 11 64bit (AMD64) (simulated platform result)']);
      }
      if (exprLower.indexOf('import pandas') !== -1) {
        if (!store.pandas) return done(['Traceback (most recent call last):', 'ModuleNotFoundError: No module named pandas', 'The active simulated environment is ' + simStoreLabel() + '.']);
        return done([store.pandas]);
      }
      if (exprLower.indexOf('import numpy') !== -1) {
        if (!store.numpy) return done(['Traceback (most recent call last):', 'ModuleNotFoundError: No module named numpy']);
        return done([store.numpy]);
      }
      return done(['Simulated Python evaluated: ' + expr, 'Only the explicitly taught -c checks are modelled in this lab.']);
    }

    if (lower === 'jupyter notebook' || lower === 'jupyter lab') {
      if (!SIM.jupyterInstalled) return done(["'jupyter' is not recognised as an internal or external command. Install notebook and jupyterlab first."]);
      SIM.jupyterRunning = true;
      SIM.jupyterMode = lower.split(' ')[1];
      simMarkStep('jupyter');
      return done([
        'Jupyter ' + (SIM.jupyterMode === 'lab' ? 'Lab' : 'Notebook') + ' started in the simulation.',
        'Simulated browser opened at http://localhost:8888',
        'Kernel source: ' + simStoreLabel() + '. No real server was started.'
      ]);
    }

    if (lower === 'jupyter --version') {
      if (!SIM.jupyterInstalled) return done(["'jupyter' is not recognised. Install notebook and jupyterlab first."]);
      return done(['notebook ' + (store.notebook || SIM_PACKAGES.notebook), 'jupyterlab ' + (store.jupyterlab || SIM_PACKAGES.jupyterlab)]);
    }

    if (lower.indexOf('mkdir ') === 0) {
      var made = [];
      cmd.slice(6).split(' ').filter(function (part) { return part; }).forEach(function (part) {
        made.push(simEnsureDir(part));
      });
      simCheckProjectDirs();
      return done(['Created simulated folder(s): ' + made.join(', ')]);
    }

    if (lower.indexOf('new-item ') === 0) {
      if (shell !== 'ps') return done(['New-Item is PowerShell syntax. In Command Prompt use mkdir instead.']);
      var pathMatch = cmd.match(/new-item\s+-itemtype\s+directory\s+-path\s+(.+)/i);
      if (!pathMatch) return done(['Simulator expects: New-Item -ItemType Directory -Path <folder>']);
      var newDir = simEnsureDir(pathMatch[1].replace(/^"|"$/g, ''));
      simCheckProjectDirs();
      return done(['Created simulated PowerShell folder: ' + newDir]);
    }

    if (lower === 'cd /d ' + cmd.slice(6).toLowerCase() && lower.indexOf('cd /d ') === 0) {
      if (shell !== 'cmd') return done(['/d is a Command Prompt switch. In PowerShell use Set-Location or cd without /d.']);
      var targetCmd = simResolveFsPath(cmd.slice(6).trim());
      if (SIM.dirs.indexOf(targetCmd) === -1) return done(['The system cannot find the path specified: ' + targetCmd]);
      SIM.cwd = targetCmd;
      simCheckProjectDirs();
      return done(['Changed simulated directory to ' + SIM.cwd]);
    }

    if (lower.indexOf('cd /d ') === 0) {
      if (shell !== 'cmd') return done(['/d is a Command Prompt switch. In PowerShell use Set-Location or cd without /d.']);
      var cdTarget = simResolveFsPath(cmd.slice(6).trim());
      if (SIM.dirs.indexOf(cdTarget) === -1) return done(['The system cannot find the path specified: ' + cdTarget]);
      SIM.cwd = cdTarget;
      simCheckProjectDirs();
      return done(['Changed simulated directory to ' + SIM.cwd]);
    }

    if (lower.indexOf('set-location ') === 0) {
      if (shell !== 'ps') return done(['Set-Location is PowerShell syntax. In Command Prompt use cd or cd /d.']);
      var psTarget = simResolveFsPath(cmd.slice(13).trim().replace(/^-path +/i, ''));
      if (SIM.dirs.indexOf(psTarget) === -1) return done(['Set-Location: Cannot find path ' + psTarget + ' because it does not exist.']);
      SIM.cwd = psTarget;
      simCheckProjectDirs();
      return done(['Simulated PowerShell location: ' + SIM.cwd]);
    }

    if (lower.indexOf('cd ') === 0) {
      var plainTarget = simResolveFsPath(cmd.slice(3).trim());
      if (plainTarget.charAt(0) !== SIM.cwd.charAt(0) && shell === 'cmd') {
        return done(['Cannot change to another drive with plain cd in Command Prompt. Use cd /d ' + plainTarget]);
      }
      if (SIM.dirs.indexOf(plainTarget) === -1) return done(['The system cannot find the path specified: ' + plainTarget]);
      SIM.cwd = plainTarget;
      simCheckProjectDirs();
      return done(['Changed simulated directory to ' + SIM.cwd]);
    }

    if (lower === 'dir') {
      return done(simDirectoryLines());
    }
    if (lower === 'get-childitem') {
      if (shell !== 'ps') return done(['Get-ChildItem is PowerShell syntax. In Command Prompt use dir.']);
      return done(simDirectoryLines());
    }

    if (lower.indexOf('deactivate') === 0) {
      if (!SIM.activeVenv) return done(['No simulated virtual environment is active.']);
      var old = SIM.activeVenv;
      SIM.activeVenv = null;
      return done(['Deactivated simulated environment: ' + old]);
    }

    if (lower.indexOf('.venv' + B + 'scripts') !== -1) {
      return simHandleVenvDirect(cmd, lower, shell);
    }

    return done(['Simulator: command is not supported. This lab only interprets the Windows setup commands taught in this chapter and never runs host commands.', 'Try one of the quick commands above.']);
  }

  function simDirectoryLines() {
    var prefix = SIM.cwd.charAt(SIM.cwd.length - 1) === B ? SIM.cwd : SIM.cwd + B;
    var children = SIM.dirs.filter(function (dir) {
      return dir !== SIM.cwd && dir.indexOf(prefix) === 0 && dir.slice(prefix.length).indexOf(B) === -1;
    }).map(function (dir) { return '<DIR> ' + dir.slice(prefix.length); });
    if (SIM.requirements && SIM.cwd === wp('D:')) children.push('        requirements.txt');
    if (!children.length) children.push('No simulated child folders or files in ' + SIM.cwd);
    return children;
  }

  function simCheckProjectDirs() {
    var base = wp('D:', 'Biomedical_Project');
    var needed = ['data', 'notebooks', 'figures', 'results'].map(function (name) { return wp(base, name); });
    if (SIM.dirs.indexOf(base) !== -1 && needed.every(function (dir) { return SIM.dirs.indexOf(dir) !== -1; })) {
      simMarkStep('directories');
    }
  }

  function simHandleVenvDirect(cmd, lower, shell) {
    simFaultDiagnosticDone(cmd);
    var venvBase = simResolveFsPath('.venv');
    if (!SIM.venvs[venvBase]) return simExecResult(['No simulated .venv exists in ' + SIM.cwd + '. Create one with python -m venv .venv first.']);
    var isActivation = lower.indexOf('activate.bat') !== -1 || lower.indexOf('activate.ps1') !== -1;
    var isPythonExe = lower.indexOf('python.exe') !== -1;
    if (!isActivation && !isPythonExe) return simExecResult(['Simulator: only activation or direct python.exe calls are modelled for .venv scripts.']);
    if (isActivation) {
      if (lower.indexOf('activate.bat') !== -1 && shell !== 'cmd') return simExecResult(['activate.bat is Command Prompt syntax. In PowerShell use .venv' + B + 'Scripts' + B + 'Activate.ps1.']);
      if (lower.indexOf('activate.ps1') !== -1 && shell !== 'ps') return simExecResult(['Activate.ps1 is PowerShell syntax. In Command Prompt use .venv' + B + 'Scripts' + B + 'activate.bat.']);
      if (shell === 'ps' && SIM.executionPolicy === 'Restricted') {
        return simExecResult([
          'Activate.ps1 cannot be loaded because running scripts is disabled on this simulated system.',
          'Do not weaken institutional security policy. The safe alternative is to call the environment python directly:',
          '.venv' + B + 'Scripts' + B + 'python.exe --version',
          'The simulated environment is unchanged.'
        ]);
      }
      SIM.activeVenv = venvBase;
      return simExecResult(['Activated simulated environment: ' + venvBase, 'The prompt would now show (.venv).']);
    }
    var env = SIM.venvs[venvBase];
    if (simCurrentFault === 'ps-activation-blocked') {
      var directRecord = SIM.faults['ps-activation-blocked'] || {};
      directRecord.directUsed = true;
      SIM.faults['ps-activation-blocked'] = directRecord;
    }
    if (lower.indexOf('--version') !== -1) return simExecResult(['Python ' + env.version + ' (direct environment python.exe)']);
    if (lower.indexOf('-m pip --version') !== -1) return simExecResult(['pip ' + env.packages.pip + ' from simulated environment ' + venvBase]);
    return simExecResult(['Direct environment python.exe called. Only --version and -m pip --version are simulated.']);
  }

  function simExecResult(lines) {
    SIM.lastTerminal = lines.join(NL);
    simCheckFaultResolution();
    simSaveState();
    return lines;
  }

  function simRunBatch(text) {
    var lines = String(text || '').split(NL);
    var out = ['Simulated batch execution began. No host script was run.'];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) continue;
      var lower = line.toLowerCase();
      if (lower === '@echo off' || lower.indexOf('rem ') === 0 || lower.indexOf('echo ') === 0 || lower === 'pause' || lower.indexOf('mkdir ') === 0) {
        out = out.concat(simExec(line, { shell: 'cmd' }));
      } else {
        out.push('Blocked unsupported batch line: ' + line + ' (only mkdir, echo, rem and pause are allowed).');
      }
    }
    out.push('Simulated batch execution finished.');
    return out;
  }

  function simEnsureInstalled() {
    var tag = SIM.selectedRelease;
    SIM.installed = true;
    SIM.installVersion = tag;
    SIM.installPath = simPythonDir(tag);
    SIM.launcher = true;
    SIM.pipPresent = true;
    SIM.globalPackages.pip = SIM_PACKAGES.pip;
    if (SIM.dirs.indexOf(SIM.installPath) === -1) SIM.dirs.push(SIM.installPath);
    return SIM.installPath;
  }

  function simAddPythonToEnv(refresh) {
    var dir = SIM.installPath || simPythonDir();
    var scripts = wp(dir, 'Scripts');
    SIM.env.userPath = SIM.env.userPath.filter(function (item) {
      return item !== dir && item !== scripts;
    });
    SIM.env.userPath.unshift(dir);
    SIM.env.userPath.unshift(scripts);
    SIM.pathAdded = true;
    if (refresh) simRefreshTerminal();
  }

  function simRemovePythonFromEnv() {
    var dir = SIM.installPath || simPythonDir();
    var scripts = wp(dir, 'Scripts');
    SIM.env.userPath = SIM.env.userPath.filter(function (item) { return item !== dir && item !== scripts; });
    SIM.pathSnapshot = SIM.pathSnapshot.filter(function (item) { return item !== dir && item !== scripts; });
    SIM.pathAdded = false;
  }

  function simPutWindowsAppsFirst() {
    var apps = wp('C:', 'Users', 'Learner', 'AppData', 'Local', 'Microsoft', 'WindowsApps');
    var directory = SIM.installPath || simPythonDir();
    SIM.env.userPath = [apps, directory, wp(directory, 'Scripts')].concat(SIM.env.userPath.filter(function (item) {
      return item !== apps && item !== directory && item !== wp(directory, 'Scripts');
    }));
    SIM.pathSnapshot = SIM.env.systemPath.concat(SIM.env.userPath);
    SIM.storeAlias = true;
  }

  var SIM_FAULTS = {
    'python-not-recognised': {
      title: 'Python is not recognised',
      problem: 'A learner installed Python but a freshly opened Command Prompt says python is not recognised.',
      hint: 'Ask which executable the command environment can actually find, then check whether the interpreter folder is on PATH.',
      diagnostics: ['where.exe python', 'py -0p', 'python -c "import sys; print(sys.executable)"'],
      seed: function () {
        simEnsureInstalled();
        simRemovePythonFromEnv();
      },
      fix: function () {
        simAddPythonToEnv(true);
        return 'Added the simulated Python directories to user PATH and refreshed the terminal.';
      },
      resolveTest: function () { return simResolvePython().kind === 'python'; },
      explanation: 'py can exist even when python is missing from PATH. The Windows launcher lives in C:' + B + 'Windows, while python.exe is resolved through command PATH.'
    },
    'pip-not-recognised': {
      title: 'pip is not recognised',
      problem: 'python --version works, but pip is missing. Bare pip and python -m pip both fail.',
      hint: 'pip is part of the selected interpreter environment. Check the module associated with python.',
      diagnostics: ['python --version', 'python -m pip --version', 'pip --version'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        delete SIM.globalPackages.pip;
        SIM.pipPresent = false;
      },
      fix: function () {
        SIM.globalPackages.pip = SIM_PACKAGES.pip;
        SIM.pipPresent = true;
        return 'Restored pip in the simulated interpreter environment.';
      },
      resolveTest: function () { return Boolean(simActiveStore().pip); },
      explanation: 'python -m pip asks a specific interpreter for its pip module. Bare pip depends on PATH and can point to a different environment.'
    },
    'store-alias': {
      title: 'Python opens Microsoft Store',
      problem: 'python opens a Microsoft Store alias instead of the installed interpreter.',
      hint: 'Compare the first python.exe reported by where.exe with the installed interpreter directory.',
      diagnostics: ['where.exe python', 'python --version', 'python -c "import sys; print(sys.executable)"'],
      seed: function () {
        simEnsureInstalled();
        simPutWindowsAppsFirst();
      },
      fix: function () {
        simAddPythonToEnv(true);
        return 'Put the installed Python directories ahead of the Microsoft Store alias in the simulated user PATH.';
      },
      resolveTest: function () { return simResolvePython().kind === 'python'; },
      explanation: 'Microsoft Store aliases are PATH entries, not the Windows Python launcher. Their order can shadow a real interpreter.'
    },
    'wrong-python': {
      title: 'Wrong Python installation is used',
      problem: 'The project needs Python 3.12, but python reports 3.11.9.',
      hint: 'List launcher-discovered interpreters and print the executable path before changing anything.',
      diagnostics: ['where.exe python', 'py -0p', 'python -c "import sys; print(sys.executable)"'],
      seed: function () {
        simEnsureInstalled();
        SIM.multipleInstalls = true;
        var old = wp('C:', 'Program Files', 'Python311');
        if (SIM.dirs.indexOf(old) === -1) SIM.dirs.push(old);
        simAddPythonToEnv(false);
        SIM.env.userPath.unshift(old);
        SIM.pathSnapshot = SIM.env.systemPath.concat(SIM.env.userPath);
      },
      fix: function () {
        simAddPythonToEnv(true);
        return 'Moved the intended Python 3.12 directories ahead of the older installation.';
      },
      resolveTest: function () { return simResolvePython().version === SIM.installVersion; },
      explanation: 'PATH order decides which python.exe wins. py -0p can select an interpreter explicitly without changing PATH.'
    },
    'multiple-installs': {
      title: 'Multiple Python installations',
      problem: 'Two Python versions are installed and learners disagree about which one is in use.',
      hint: 'Distinguish what the launcher can see from what PATH resolves first.',
      diagnostics: ['where.exe python', 'where.exe py', 'py -0p'],
      seed: function () {
        simEnsureInstalled();
        SIM.multipleInstalls = true;
        var old = wp('C:', 'Program Files', 'Python311');
        if (SIM.dirs.indexOf(old) === -1) SIM.dirs.push(old);
        simAddPythonToEnv(true);
      },
      fix: function () {
        simAddPythonToEnv(true);
        return 'Selected the teaching interpreter as the first Python entry in the simulated PATH.';
      },
      resolveTest: function () { return simResolvePython().version === SIM.installVersion; },
      explanation: 'Multiple interpreters can coexist. A virtual environment pins the one used by a project and avoids PATH confusion.'
    },
    'jupyter-not-found': {
      title: 'Jupyter command not found',
      problem: 'Python works, but jupyter notebook fails with command not found.',
      hint: 'Jupyter is a package installed into an interpreter environment, not part of the base installer by default.',
      diagnostics: ['python --version', 'python -m pip --version', 'jupyter --version'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        delete SIM.globalPackages.notebook;
        delete SIM.globalPackages.jupyterlab;
        SIM.jupyterInstalled = false;
      },
      fix: function () {
        SIM.globalPackages.notebook = SIM_PACKAGES.notebook;
        SIM.globalPackages.jupyterlab = SIM_PACKAGES.jupyterlab;
        SIM.jupyterInstalled = true;
        simMarkStep('jupyter');
        return 'Installed notebook and jupyterlab into the simulated interpreter environment.';
      },
      resolveTest: function () { return SIM.jupyterInstalled; },
      explanation: 'python -m pip installs Jupyter into the Python that runs the command. Jupyter Notebook and JupyterLab can open the same .ipynb files.'
    },
    'package-install-failure': {
      title: 'Package installation failure',
      problem: 'Installing lifelines fails with a simulated network or wheel error.',
      hint: 'Read the package name and decide whether the failure is a bad requirement, network problem or incompatible wheel.',
      diagnostics: ['python -m pip --version', 'python -m pip install lifelines', 'python -m pip list'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        SIM.faults['package-install-failure'] = { networkDown: true, seeded: true, resolved: false };
      },
      fix: function () {
        var record = SIM.faults['package-install-failure'] || {};
        record.networkDown = false;
        SIM.faults['package-install-failure'] = record;
        return 'Restored the simulated package index connection. Retry the installation.';
      },
      resolveTest: function () {
        var record = SIM.faults['package-install-failure'];
        return Boolean(record && !record.networkDown && SIM.globalPackages.lifelines);
      },
      explanation: 'A failed download does not always mean the package is incompatible. Confirm the interpreter, index connection and available wheel before changing versions.'
    },
    'dependency-conflict': {
      title: 'Dependency conflict',
      problem: 'pip check reports that pandas requires a different numpy version.',
      hint: 'Use pip check, then compare the pinned versions with the simulated package catalogue.',
      diagnostics: ['python -m pip list', 'python -m pip check', 'python -m pip freeze'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        SIM.globalPackages.numpy = '2.1.3';
        SIM.globalPackages.pandas = '1.5.3';
      },
      fix: function () {
        SIM.globalPackages.pandas = SIM_PACKAGES.pandas;
        return 'Upgraded pandas to a version compatible with the installed numpy in this simulation.';
      },
      resolveTest: function () {
        return !(SIM.globalPackages.pandas === '1.5.3' && parseFloat(SIM.globalPackages.numpy) >= 2);
      },
      explanation: 'pip list shows what is installed, pip check validates dependencies and pip freeze records exact versions for later rebuilding.'
    },
    'path-not-refreshed': {
      title: 'PATH not refreshed',
      problem: 'The environment-variable editor shows Python on PATH, but the already-open terminal still cannot find it.',
      hint: 'An open process keeps the environment it started with. Compare the editor view with the terminal PATH snapshot.',
      diagnostics: ['where.exe python', 'python --version'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(false);
        SIM.pathSnapshot = SIM.env.systemPath.slice();
      },
      fix: function () { return simRefreshTerminal(); },
      resolveTest: function () {
        var dir = (SIM.installPath || '').toLowerCase();
        return SIM.pathSnapshot.some(function (entry) { return entry.toLowerCase() === dir; });
      },
      explanation: 'Environment changes usually affect newly started processes. Reopen or refresh the simulated terminal after editing PATH.'
    },
    'ps-activation-blocked': {
      title: 'PowerShell activation blocked',
      problem: 'Activate.ps1 cannot be loaded because script execution is restricted.',
      hint: 'Do not weaken institutional policy. The environment python.exe can be called directly.',
      diagnostics: ['.venv' + B + 'Scripts' + B + 'Activate.ps1', 'where.exe py'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        var venvPath = simResolveFsPath('.venv');
        SIM.venvs[venvPath] = { path: venvPath, version: SIM.installVersion, packages: { pip: SIM_PACKAGES.pip }, created: Date.now() };
        SIM.executionPolicy = 'Restricted';
        SIM.shell = 'ps';
        SIM.activeVenv = null;
      },
      fix: function () {
        var record = SIM.faults['ps-activation-blocked'] || {};
        record.directUsed = true;
        SIM.faults['ps-activation-blocked'] = record;
        return 'Recorded the safe direct-interpreter approach. No real execution-policy change was made.';
      },
      resolveTest: function () {
        var record = SIM.faults['ps-activation-blocked'];
        return Boolean(record && record.directUsed);
      },
      explanation: 'Activation changes the shell PATH. Calling the environment python.exe directly gives the same interpreter without changing PowerShell policy.'
    },
    'invalid-directory-path': {
      title: 'Invalid directory path',
      problem: 'cd /d to D:' + B + 'Biomedical_Project' + B + 'notebooks fails because the folder does not exist.',
      hint: 'Check the path one component at a time and create missing folders before navigating.',
      diagnostics: ['dir', 'cd /d ' + wp('D:', 'Biomedical_Project', 'notebooks')],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        simEnsureDir(wp('D:', 'Biomedical_Project'));
        SIM.dirs = SIM.dirs.filter(function (dir) { return dir !== wp('D:', 'Biomedical_Project', 'notebooks'); });
        SIM.cwd = wp('C:');
      },
      fix: function () {
        simEnsureDir(wp('D:', 'Biomedical_Project', 'notebooks'));
        SIM.cwd = wp('D:', 'Biomedical_Project', 'notebooks');
        return 'Created the simulated notebooks folder and changed into it.';
      },
      resolveTest: function () { return SIM.cwd === wp('D:', 'Biomedical_Project', 'notebooks'); },
      explanation: 'Windows paths use drive letters and backslashes. Command Prompt needs cd /d to change drive; PowerShell uses Set-Location.'
    },
    'permission-denied': {
      title: 'Permission denied',
      problem: 'An all-users Python installation fails because the simulated learner has no administrator rights.',
      hint: 'Installing for the current user avoids system-wide directory permissions.',
      diagnostics: ['winver', 'where.exe py'],
      seed: function () {
        SIM.installed = false;
        SIM.installScope = 'all';
        SIM.admin = false;
        SIM.installerOpened = true;
        SIM.pathAdded = false;
        SIM.env.userPath = [];
        SIM.pathSnapshot = SIM.env.systemPath.slice();
      },
      fix: function () {
        SIM.installScope = 'user';
        simEnsureInstalled();
        simAddPythonToEnv(true);
        return 'Installed Python for the current simulated user instead of all users.';
      },
      resolveTest: function () { return SIM.installed && SIM.installScope === 'user'; },
      explanation: 'All-users installation writes to Program Files and needs elevation. Current-user installation writes under the user profile.'
    },
    'imports-fail': {
      title: 'Python installed but imports fail',
      problem: 'python works, but import pandas fails inside the active environment.',
      hint: 'The interpreter and its package store must match. Check which environment owns the package.',
      diagnostics: ['python -c "import sys; print(sys.executable)"', 'python -m pip list', 'python -c "import pandas; print(pandas.__version__)"'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        delete SIM.globalPackages.pandas;
        SIM.activeVenv = null;
      },
      fix: function () {
        SIM.globalPackages.pandas = SIM_PACKAGES.pandas;
        simMarkStep('packages');
        return 'Installed pandas into the active simulated Python environment.';
      },
      resolveTest: function () { return Boolean(simActiveStore().pandas); },
      explanation: 'An import uses the active interpreter site-packages. Installing into a different environment does not fix this interpreter.'
    },
    'notebook-wrong-kernel': {
      title: 'Notebook using the wrong environment',
      problem: 'The notebook imports fail although the virtual environment has the packages.',
      hint: 'A notebook has a kernel, separate from the terminal environment. Match the kernel to the environment.',
      diagnostics: ['python -c "import sys; print(sys.executable)"', 'python -m pip list', 'jupyter --version'],
      seed: function () {
        simEnsureInstalled();
        simAddPythonToEnv(true);
        var venvPath = simResolveFsPath('.venv');
        SIM.venvs[venvPath] = {
          path: venvPath,
          version: SIM.installVersion,
          packages: { pip: SIM_PACKAGES.pip, pandas: SIM_PACKAGES.pandas, numpy: SIM_PACKAGES.numpy },
          created: Date.now()
        };
        SIM.globalPackages.pandas = SIM_PACKAGES.pandas;
        delete SIM.globalPackages.numpy;
        SIM.activeVenv = null;
        SIM.jupyterInstalled = true;
        SIM.jupyterRunning = true;
        SIM.jupyterMode = 'lab';
        SIM.notebooks = [{ name: 'biomedical_worked_example.ipynb', kernel: 'global' }];
      },
      fix: function () {
        var venvPath = simResolveFsPath('.venv');
        if (SIM.notebooks.length) SIM.notebooks[0].kernel = venvPath;
        return 'Selected the virtual environment kernel for the simulated notebook.';
      },
      resolveTest: function () {
        var venvPath = simResolveFsPath('.venv');
        return Boolean(SIM.notebooks.length && SIM.notebooks[0].kernel === venvPath);
      },
      explanation: 'Jupyter can run with a kernel whose interpreter differs from the terminal. Select the intended environment kernel before importing packages.'
    }
  };

  function simSeedFault(id) {
    var fault = SIM_FAULTS[id];
    if (!fault) return null;
    simCurrentFault = id;
    simDiagnosticsRun = {};
    SIM.faults[id] = { seeded: true, resolved: false };
    fault.seed(SIM);
    simSaveState();
    return fault;
  }

  function simFaultDiagnosticDone(cmd) {
    if (!simCurrentFault) return false;
    var fault = SIM_FAULTS[simCurrentFault];
    if (!fault) return false;
    var normal = simNormalise(cmd);
    var matched = fault.diagnostics.filter(function (item) { return simNormalise(item) === normal; })[0];
    if (!matched) return false;
    simDiagnosticsRun[simNormalise(matched)] = true;
    return true;
  }

  function simFaultDiagnosticsComplete() {
    var fault = SIM_FAULTS[simCurrentFault];
    if (!fault) return false;
    return fault.diagnostics.every(function (cmd) { return Boolean(simDiagnosticsRun[simNormalise(cmd)]); });
  }

  function simCheckFaultResolution() {
    if (!simCurrentFault) return;
    var fault = SIM_FAULTS[simCurrentFault];
    var record = SIM.faults[simCurrentFault];
    if (!fault || !record || record.resolved) return;
    if (!fault.resolveTest(SIM)) return;
    record.resolved = true;
    simMarkStep('troubleshooting');
    simSaveState();
  }

  function simStylesText() {
    return [
      '.bw-root{margin:18px 0;padding:14px;border:2px solid #0b5d7a;border-radius:12px;background:var(--card,#eef5f8);color:var(--fg,#1b2a3a);font:14px/1.5 system-ui}',
      '.bw-root *{box-sizing:border-box}',
      '.bw-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;margin-bottom:10px}',
      '.bw-head h3{margin:0;font-size:20px;color:var(--ac,#0b5d7a)}',
      '.bw-badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#7a1f2b;color:#fff;font-size:11px;font-weight:700;letter-spacing:.04em}',
      '.bw-progress{width:100%;height:10px;border-radius:999px;background:#c8d7e0;overflow:hidden;margin:6px 0}',
      '.bw-progress-bar{height:100%;width:0;background:#137a4a;transition:width .25s ease}',
      '.bw-progress-list{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0 12px}',
      '.bw-progress-list span{padding:3px 7px;border:1px solid #9db2c8;border-radius:999px;font-size:11px;background:var(--bg,#fff)}',
      '.bw-progress-list span.done{border-color:#137a4a;color:#12683c;font-weight:700}',
      '.bw-tabs{display:flex;flex-wrap:wrap;gap:6px;border-bottom:1px solid var(--bd,#cdd8e0);padding-bottom:8px;margin-bottom:12px}',
      '.bw-tabs button{padding:6px 10px;font-size:12px}',
      '.bw-tabs button[aria-selected=true]{background:#0b5d7a;color:#fff;border-color:#0b5d7a}',
      '.bw-panel{padding:4px 0 10px}',
      '.bw-panel[hidden]{display:none!important}',
      '.bw-desktop{position:relative;min-height:320px;border:1px solid #243e57;border-radius:8px;overflow:hidden;background:linear-gradient(135deg,#0d2b45,#20618a 55%,#6aa7c7);color:#fff;padding:12px}',
      '.bw-desktop-icons{display:grid;grid-template-columns:repeat(auto-fit,minmax(86px,1fr));gap:10px;max-width:640px}',
      '.bw-desktop-icons button{display:flex;flex-direction:column;align-items:center;gap:6px;min-height:78px;padding:8px 4px;background:rgba(255,255,255,.12);color:#fff;border:1px solid rgba(255,255,255,.35);border-radius:8px;font-size:12px;text-align:center}',
      '.bw-desktop-icons button:hover{background:rgba(255,255,255,.25)}',
      '.bw-icon{font-size:24px;line-height:1}',
      '.bw-taskbar{position:absolute;left:0;right:0;bottom:0;height:38px;display:flex;align-items:center;gap:10px;padding:0 10px;background:rgba(10,20,30,.9);font-size:12px}',
      '.bw-taskbar button{background:#0b5d7a;color:#fff;border-radius:4px}',
      '.bw-start-menu{position:absolute;left:8px;bottom:44px;width:230px;padding:10px;border-radius:8px;background:#f4f8fb;color:#1b2a3a;border:1px solid #0b5d7a;box-shadow:0 8px 24px rgba(0,0,0,.3)}',
      '.bw-start-menu button{display:block;width:100%;text-align:left;margin:3px 0;font-size:12px}',
      '.bw-window{border:1px solid #9db2c8;border-radius:8px;background:var(--bg,#fff);overflow:hidden;margin:10px 0}',
      '.bw-titlebar{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:#102b4e;color:#fff;font-size:12px;font-weight:700}',
      '.bw-body{padding:12px}',
      '.bw-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}',
      '.bw-card{border:1px solid #9db2c8;border-radius:8px;padding:10px;background:var(--bg,#fff)}',
      '.bw-card h4{margin:0 0 6px;font-size:14px;color:var(--ac,#0b5d7a)}',
      '.bw-card p{margin:5px 0;font-size:12px}',
      '.bw-url{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:10px}',
      '.bw-url input{flex:1;min-width:180px;padding:6px 8px;border:1px solid #9db2c8;border-radius:5px;font:12px ui-monospace,Menlo,Consolas,monospace}',
      '.bw-note{padding:9px 11px;border-left:4px solid #0b5d7a;background:var(--bg,#fff);margin:10px 0;font-size:12px}',
      '.bw-warn{border-left-color:#b8860b;background:#fff8e6}',
      '.bw-ok{border-left-color:#137a4a;background:#eaf8f0}',
      '.bw-error{border-left-color:#a61b1b;background:#fdecec;color:#7a1010}',
      '.bw-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}',
      '.bw-row label{display:inline-flex;align-items:center;gap:5px;font-size:12px}',
      '.bw-root button{padding:6px 9px;font-size:12px;cursor:pointer}',
      '.bw-root button[disabled]{opacity:.5;cursor:not-allowed}',
      '.bw-root input[type=text],.bw-root select,.bw-root textarea{border:1px solid #9db2c8;border-radius:5px;padding:6px 8px;background:var(--bg,#fff);color:var(--fg,#1b2a3a);font:12px system-ui}',
      '.bw-root textarea{width:100%;min-height:90px;font:12px ui-monospace,Menlo,Consolas,monospace}',
      '.bw-term{background:#10202b;color:#e6f1f7;border-radius:8px;padding:10px;min-height:210px;max-height:340px;overflow:auto;white-space:pre-wrap;word-break:break-word;font:12px ui-monospace,Menlo,Consolas,monospace}',
      '.bw-command-line{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:8px 0}',
      '.bw-command-line input{flex:1;min-width:200px;font:12px ui-monospace,Menlo,Consolas,monospace}',
      '.bw-quick{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}',
      '.bw-quick button{font:11px ui-monospace,Menlo,Consolas,monospace}',
      '.bw-list{max-height:210px;overflow:auto;padding-left:20px;margin:6px 0;font-size:12px}',
      '.bw-list li{margin:3px 0}',
      '.bw-tree{font:12px ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;background:#10202b;color:#dcecf4;padding:10px;border-radius:8px}',
      '.bw-pre{white-space:pre-wrap;word-break:break-word;padding:10px;border-radius:7px;background:#10202b;color:#e6f1f7;font:12px ui-monospace,Menlo,Consolas,monospace;max-height:260px;overflow:auto}',
      '.bw-status{font-size:12px;font-weight:700;color:var(--ac,#0b5d7a);margin:8px 0}',
      '.bw-scenario{border:1px solid #9db2c8;border-radius:8px;padding:11px;background:var(--bg,#fff)}',
      '.bw-diag{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}',
      '.bw-diag button.done{border-color:#137a4a;color:#12683c;font-weight:700}',
      '.bw-hidden{display:none!important}',
      '@media(max-width:640px){.bw-root{padding:10px}.bw-head h3{font-size:17px}.bw-desktop{min-height:360px}.bw-desktop-icons{grid-template-columns:repeat(2,minmax(0,1fr))}.bw-url input{min-width:100%}}',
      '@media print{.bw-root{display:none!important}}'
    ].join('');
  }

  function simCreateRoot() {
    if (simRoot || document.getElementById('bm-windows-simulation')) return simRoot;
    var chapter = document.getElementById('ch0');
    if (!chapter) return null;
    if (!document.getElementById('bm-win-sim-styles')) {
      var style = document.createElement('style');
      style.id = 'bm-win-sim-styles';
      style.textContent = simStylesText();
      document.head.appendChild(style);
    }
    var root = document.createElement('div');
    root.id = 'bm-windows-simulation';
    root.className = 'bw-root';
    root.setAttribute('aria-label', 'Interactive simulated Windows Python setup lab');
    root.innerHTML = `
      <div class='bw-head'>
        <div>
          <h3>Interactive Windows Python setup lab <span class='bw-badge'>SIMULATION ONLY</span></h3>
          <div class='bw-status' id='bw-progress-text'>Progress</div>
          <div class='bw-progress'><div class='bw-progress-bar' id='bw-progress-bar'></div></div>
          <div class='bw-progress-list' id='bw-progress-list'></div>
        </div>
        <button id='bw-reset' type='button'>Reset simulated setup</button>
      </div>
      <p class='bw-note bw-warn'><strong>Simulation boundary:</strong> this lab models Windows, Python, pip, Jupyter and PATH with local state only. It does not download installers, install packages, execute host shell commands or modify your real Windows environment.</p>
      <div class='bw-tabs' role='tablist' aria-label='Windows setup simulation sections'>
        <button type='button' role='tab' data-bw-tab='desktop' aria-selected='true'>Desktop</button>
        <button type='button' role='tab' data-bw-tab='browser' aria-selected='false'>Browser</button>
        <button type='button' role='tab' data-bw-tab='installer' aria-selected='false'>Installer</button>
        <button type='button' role='tab' data-bw-tab='terminal' aria-selected='false'>Terminal</button>
        <button type='button' role='tab' data-bw-tab='environment' aria-selected='false'>Environment variables</button>
        <button type='button' role='tab' data-bw-tab='explorer' aria-selected='false'>File Explorer</button>
        <button type='button' role='tab' data-bw-tab='jupyter' aria-selected='false'>Jupyter browser</button>
        <button type='button' role='tab' data-bw-tab='troubleshoot' aria-selected='false'>Troubleshooting lab</button>
        <button type='button' role='tab' data-bw-tab='activities' aria-selected='false'>Activities</button>
      </div>

      <div class='bw-panel' data-bw-panel='desktop'>
        <div class='bw-desktop'>
          <div class='bw-desktop-icons'>
            <button type='button' data-bw-open='browser'><span class='bw-icon'>🌐</span><span>Edge / python.org<br>simulated</span></button>
            <button type='button' data-bw-open='explorer'><span class='bw-icon'>📁</span><span>Downloads<br>folder</span></button>
            <button type='button' data-bw-open='installer'><span class='bw-icon'>⚙️</span><span>Python<br>installer</span></button>
            <button type='button' data-bw-open='terminal'><span class='bw-icon'>⌨️</span><span>Command<br>Prompt</span></button>
            <button type='button' data-bw-open='environment'><span class='bw-icon'>🧭</span><span>Environment<br>variables</span></button>
            <button type='button' data-bw-open='jupyter'><span class='bw-icon'>📓</span><span>Jupyter<br>browser</span></button>
          </div>
          <div class='bw-start-menu' id='bw-start-menu' hidden>
            <strong>Windows simulated Start menu</strong>
            <button type='button' data-bw-open='browser'>Microsoft Edge (simulated)</button>
            <button type='button' data-bw-open='installer'>Python installer</button>
            <button type='button' data-bw-open='terminal'>Windows Terminal / Command Prompt</button>
            <button type='button' data-bw-open='environment'>Edit environment variables</button>
          </div>
          <div class='bw-taskbar'><button id='bw-start-btn' type='button'>Start</button><span>Windows 11 setup simulation</span><span style='margin-left:auto'>SIMULATED DESKTOP</span></div>
        </div>
        <p class='bw-note'>Use the desktop icons to follow the installation story in order: browser → downloads → installer → terminal → environment variables → Jupyter.</p>
      </div>

      <div class='bw-panel' data-bw-panel='browser' hidden>
        <div class='bw-window'>
          <div class='bw-titlebar'><span>Edge (simulated)</span><span>python.org/downloads</span></div>
          <div class='bw-body'>
            <div class='bw-url'><input type='text' value='https://www.python.org/downloads/' readonly aria-label='Simulated browser address'/><button type='button' data-bw-open='desktop'>Back to desktop</button></div>
            <h4>Download Python for Windows</h4>
            <p>The simulated page offers several supported release series. Newer is not always better for a teaching environment: check scientific package compatibility before adopting the newest release.</p>
            <div class='bw-grid' id='bw-release-list'></div>
            <div class='bw-note'>Choose 64-bit Windows for modern scientific Python wheels. Python 3.11 and 3.12 are often suitable for teaching stacks; newer releases should be assessed against the packages you need.</div>
          </div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='installer' hidden>
        <div class='bw-window'>
          <div class='bw-titlebar'><span>Python Setup (simulated installer)</span><span>64-bit Windows</span></div>
          <div class='bw-body'>
            <div id='bw-installer-summary'></div>
            <div class='bw-row'>
              <label><input id='bw-path-checkbox' type='checkbox'/> Add python.exe to PATH</label>
            </div>
            <div class='bw-row'>
              <label><input id='bw-scope-user' type='radio' name='bw-scope' value='user' checked/> Install for current user</label>
              <label><input id='bw-scope-all' type='radio' name='bw-scope' value='all'/> Install for all users (requires administrator)</label>
            </div>
            <div class='bw-row'>
              <button id='bw-install-now' type='button'>Install Now</button>
              <button id='bw-customize' type='button'>Customize installation</button>
              <button type='button' data-bw-open='explorer'>Open Downloads folder</button>
            </div>
            <div id='bw-customize-options' class='bw-note bw-hidden'>
              <strong>Simulated optional features</strong>
              <div class='bw-row'><label><input type='checkbox' checked disabled/> pip</label><label><input type='checkbox' checked disabled/> documentation</label><label><input type='checkbox' checked disabled/> tcl/tk</label></div>
              <p>Customizing changes installation options in a real installer; this simulation keeps pip available so the later exercises work.</p>
            </div>
            <div class='bw-progress'><div class='bw-progress-bar' id='bw-install-progress'></div></div>
            <div class='bw-status' id='bw-installer-status'></div>
            <div class='bw-note bw-warn'>Leaving <strong>Add python.exe to PATH</strong> unticked is allowed. You will see the consequence in the simulated terminal and can repair it later with the environment-variable editor.</div>
          </div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='terminal' hidden>
        <div class='bw-row'>
          <label>Shell <select id='bw-shell-select'><option value='cmd'>Command Prompt</option><option value='ps'>PowerShell</option></select></label>
          <button id='bw-refresh-terminal' type='button'>Refresh terminal PATH</button>
          <button id='bw-new-terminal' type='button'>Open fresh terminal</button>
          <button type='button' data-bw-open='troubleshoot'>Back to troubleshooting</button>
        </div>
        <div class='bw-status' id='bw-terminal-meta'></div>
        <div class='bw-command-line'>
          <span id='bw-prompt'>&gt;</span>
          <input id='bw-command-input' type='text' aria-label='Simulated Windows command' placeholder='Type a taught command, for example python --version'/>
          <button id='bw-run-command' type='button'>Run</button>
        </div>
        <div class='bw-quick' id='bw-quick-commands'></div>
        <pre class='bw-term' id='bw-terminal-output' aria-live='polite'></pre>
        <p class='bw-note'>Only the commands taught in this chapter are interpreted. Unsupported commands are rejected without touching the host system.</p>
      </div>

      <div class='bw-panel' data-bw-panel='environment' hidden>
        <div class='bw-window'>
          <div class='bw-titlebar'><span>Environment Variables (simulated)</span><span>User and System PATH</span></div>
          <div class='bw-body'>
            <div class='bw-grid'>
              <div class='bw-card'><h4>User PATH</h4><ul class='bw-list' id='bw-user-path'></ul></div>
              <div class='bw-card'><h4>System PATH</h4><ul class='bw-list' id='bw-system-path'></ul></div>
            </div>
            <div class='bw-row'>
              <input id='bw-path-input' type='text' placeholder='C:...\\Python312' aria-label='Simulated PATH entry'/>
              <button id='bw-add-path' type='button'>Add to user PATH</button>
              <select id='bw-path-remove' aria-label='Choose a user PATH entry to remove'></select>
              <button id='bw-remove-path' type='button'>Remove</button>
              <button id='bw-env-refresh' type='button'>Refresh terminal</button>
            </div>
            <div class='bw-status' id='bw-env-status'></div>
            <div class='bw-note'>The Python installation directory contains python.exe. The Scripts directory contains console programs such as pip and Jupyter. User PATH applies to one account; System PATH applies to all accounts. An already-open terminal keeps its old PATH until you reopen or refresh it.</div>
            <div class='bw-card'><h4>Terminal PATH snapshot</h4><ul class='bw-list' id='bw-snapshot-path'></ul></div>
          </div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='explorer' hidden>
        <div class='bw-window'>
          <div class='bw-titlebar'><span>File Explorer (simulated)</span><span>Downloads and project folders</span></div>
          <div class='bw-body'>
            <div id='bw-explorer-files'></div>
            <h4>Simulated filesystem</h4>
            <pre class='bw-tree' id='bw-tree'></pre>
            <h4>requirements.txt</h4>
            <pre class='bw-pre' id='bw-requirements'></pre>
          </div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='jupyter' hidden>
        <div class='bw-window'>
          <div class='bw-titlebar'><span>Simulated Jupyter browser</span><span>http://localhost:8888</span></div>
          <div class='bw-body'>
            <div class='bw-url'><input type='text' value='http://localhost:8888' readonly aria-label='Simulated Jupyter address'/><span id='bw-jupyter-status'></span></div>
            <div class='bw-row'>
              <button id='bw-launch-notebook' type='button'>jupyter notebook</button>
              <button id='bw-launch-lab' type='button'>jupyter lab</button>
              <label>Kernel <select id='bw-kernel-select'></select></label>
              <button id='bw-new-notebook' type='button'>New notebook</button>
            </div>
            <p>Notebook and Lab are different interfaces for the same .ipynb notebook files. The kernel chooses which Python interpreter executes code.</p>
            <div id='bw-notebook-list'></div>
            <h4>Simulated notebook cell</h4>
            <textarea id='bw-cell-code' aria-label='Simulated notebook code cell'>import pandas
print(pandas.__version__)</textarea>
            <div class='bw-row'><button id='bw-run-cell' type='button'>Run cell in selected kernel</button></div>
            <pre class='bw-term' id='bw-cell-output'></pre>
            <div class='bw-note bw-warn'>No Jupyter server or browser tab is started on your computer.</div>
          </div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='troubleshoot' hidden>
        <div class='bw-scenario'>
          <div class='bw-row'>
            <label>Select a seeded fault <select id='bw-fault-select'></select></label>
            <button id='bw-load-fault' type='button'>Load fault</button>
          </div>
          <h4 id='bw-fault-title'></h4>
          <p id='bw-fault-problem'></p>
          <div class='bw-diag' id='bw-fault-diagnostics'></div>
          <div class='bw-row'><button id='bw-fault-hint' type='button'>Show a hint</button><button id='bw-fault-fix' type='button' disabled>Apply guided fix</button></div>
          <p class='bw-note bw-warn bw-hidden' id='bw-fault-hint-text'></p>
          <div class='bw-note bw-ok bw-hidden' id='bw-fault-explanation'></div>
        </div>
      </div>

      <div class='bw-panel' data-bw-panel='activities' hidden>
        <details open><summary><strong>Activity A: compare version commands</strong></summary>
          <div class='bw-quick'><button type='button' data-bw-cmd='python --version'>python --version</button><button type='button' data-bw-cmd='py --version'>py --version</button><button type='button' data-bw-cmd='python -m pip --version'>python -m pip --version</button></div>
          <p>Run each command in the terminal, then explain what it verifies: PATH-resolved interpreter, Windows launcher, and pip attached to that interpreter.</p>
        </details>
        <details><summary><strong>Activity B: seeded PATH fault</strong></summary>
          <p>Work in pairs: load the PATH fault, diagnose it with where.exe python, where.exe py, py -0p and sys.executable, then repair it.</p>
          <button id='bw-seed-path' type='button'>Seed broken PATH and open diagnostics</button>
        </details>
        <details><summary><strong>Activity C: installation checklist</strong></summary>
          <div id='bw-checklist'></div>
          <div class='bw-row'><input id='bw-checklist-input' type='text' placeholder='Add your own checklist item'/><button id='bw-add-checklist' type='button'>Add item</button></div>
        </details>
        <details><summary><strong>Activity D: two virtual environments</strong></summary>
          <p>Create two folders with mkdir, move into each with cd /d or Set-Location, then run python -m venv .venv in each. Install different package versions and compare.</p>
          <div class='bw-quick'><button id='bw-make-two-envs' type='button'>Create two simulated project environments</button><button id='bw-compare-envs' type='button'>Compare pip freeze output</button></div>
          <pre class='bw-pre' id='bw-env-compare'></pre>
        </details>
        <details><summary><strong>Activity E: pip check conflict</strong></summary>
          <button id='bw-seed-conflict' type='button'>Seed dependency conflict</button>
          <p>Read the pip check output in the terminal and resolve the mismatch with an upgrade.</p>
        </details>
        <details><summary><strong>Activity F: batch-file exercise</strong></summary>
          <p>Compose and inspect a .bat script. Only mkdir, echo, rem and pause lines are simulated. No host script is executed.</p>
          <textarea id='bw-batch-script' aria-label='Simulated batch file'></textarea>
          <div class='bw-row'><button id='bw-run-batch' type='button'>Run simulated batch</button></div>
          <pre class='bw-term' id='bw-batch-output'></pre>
          <div class='bw-note'>@echo off suppresses command echoing, mkdir creates folders, echo prints a line, and pause waits in a real batch file. Each line here is interpreted only in simulated state.</div>
        </details>
      </div>`;
    chapter.appendChild(root);
    simRoot = root;
    simTerminalInput = root.querySelector('#bw-command-input');
    simTerminalOutput = root.querySelector('#bw-terminal-output');
    simWireRoot();
    simRenderAll();
    return root;
  }

  var SIM_STEP_LABELS = {
    download: 'Installer downloaded',
    install: 'Python installed',
    verify: 'Version commands checked',
    path: 'PATH diagnosed',
    jupyter: 'Jupyter installed',
    directories: 'Project folders created',
    venv: 'Virtual environment created',
    packages: 'Scientific packages installed',
    requirements: 'Requirements recorded',
    troubleshooting: 'Fault resolved'
  };

  function simRenderAll() {
    if (!simRoot) return;
    simRenderProgress();
    simRenderBrowser();
    simRenderInstaller();
    simRenderTerminal();
    simRenderEnvironment();
    simRenderExplorer();
    simRenderJupyter();
    simRenderTroubleshooting();
    simRenderActivities();
  }

  function simRenderProgress() {
    if (!simRoot) return;
    var keys = Object.keys(SIM_STEP_LABELS);
    var done = keys.filter(function (key) { return Boolean(SIM.steps[key]); });
    var text = simRoot.querySelector('#bw-progress-text');
    var bar = simRoot.querySelector('#bw-progress-bar');
    var list = simRoot.querySelector('#bw-progress-list');
    if (text) text.textContent = 'Progress: ' + done.length + ' of ' + keys.length + ' simulated setup steps complete';
    if (bar) bar.style.width = Math.round(done.length / keys.length * 100) + '%';
    if (list) {
      list.innerHTML = keys.map(function (key) {
        return '<span class="' + (SIM.steps[key] ? 'done' : '') + '">' + (SIM.steps[key] ? '✓ ' : '○ ') + SIM_STEP_LABELS[key] + '</span>';
      }).join('');
    }
  }

  function simRenderBrowser() {
    if (!simRoot) return;
    var host = simRoot.querySelector('#bw-release-list');
    if (!host) return;
    host.innerHTML = SIM.releases.map(function (release) {
      var recommended = release.tag === '3.12';
      return `<div class='bw-card'><h4>${simEsc(release.label)}</h4><p>${simEsc(release.note)}</p><p><strong>${recommended ? 'Teaching recommendation' : 'Available release'}</strong></p><button type='button' data-bw-release='${simEsc(release.tag)}'>Download Windows 64-bit installer</button></div>`;
    }).join('');
    var status = SIM.downloaded ? 'Downloaded installer: python-' + SIM.selectedRelease + '-amd64.exe (simulated). Open it from the Downloads folder.' : 'No installer downloaded yet.';
    host.insertAdjacentHTML('afterend', '');
    var note = simRoot.querySelector('[data-bw-panel=browser] .bw-note');
    if (note) note.textContent = '64-bit Windows is required for modern scientific wheels. ' + status;
  }

  function simRenderInstaller() {
    if (!simRoot) return;
    if (typeof SIM.pathChoice !== 'boolean') SIM.pathChoice = SIM.pathAdded;
    var release = SIM.releases.filter(function (item) { return item.tag === SIM.selectedRelease; })[0] || SIM.releases[1];
    var summary = simRoot.querySelector('#bw-installer-summary');
    if (summary) {
      summary.innerHTML = `<p><strong>Selected:</strong> ${simEsc(release.label)} · 64-bit Windows · ${SIM.downloaded ? 'installer present in Downloads' : 'download an installer from the browser first'}</p><p><strong>Install location:</strong> ${simEsc(simPythonDir(SIM.selectedRelease))}</p>`;
    }
    var checkbox = simRoot.querySelector('#bw-path-checkbox');
    if (checkbox) checkbox.checked = Boolean(SIM.pathChoice);
    var user = simRoot.querySelector('#bw-scope-user');
    var all = simRoot.querySelector('#bw-scope-all');
    if (user) user.checked = SIM.installScope !== 'all';
    if (all) all.checked = SIM.installScope === 'all';
    var progress = simRoot.querySelector('#bw-install-progress');
    if (progress) progress.style.width = (SIM.installed ? 100 : (SIM.installProgress || 0)) + '%';
    var status = simRoot.querySelector('#bw-installer-status');
    if (status) status.textContent = SIM.installStatus || (SIM.installed ? 'Installation complete in the simulation.' : 'Installer ready. No real files are created.');
    var custom = simRoot.querySelector('#bw-customize-options');
    if (custom) custom.hidden = !SIM.customizeOpen;
  }

  function simRenderTerminal() {
    if (!simRoot) return;
    var shell = simRoot.querySelector('#bw-shell-select');
    if (shell) shell.value = SIM.shell;
    var meta = simRoot.querySelector('#bw-terminal-meta');
    if (meta) {
      var envName = SIM.activeVenv ? SIM.activeVenv : 'global environment';
      var pathState = SIM.pathSnapshot.some(function (entry) { return (SIM.installPath && entry.toLowerCase() === SIM.installPath.toLowerCase()); }) ? 'installed Python visible' : 'installed Python not visible';
      meta.textContent = 'Shell: ' + (SIM.shell === 'ps' ? 'PowerShell' : 'Command Prompt') + ' · Directory: ' + SIM.cwd + ' · Environment: ' + envName + ' · PATH snapshot: ' + pathState;
    }
    var prompt = simRoot.querySelector('#bw-prompt');
    if (prompt) prompt.textContent = SIM.shell === 'ps' ? 'PS>' : 'C:\\>';
    var quickHost = simRoot.querySelector('#bw-quick-commands');
    if (quickHost) {
      var quick = SIM.shell === 'ps' ? [
        'python --version',
        'py --version',
        'python -m pip --version',
        'Get-ChildItem',
        'New-Item -ItemType Directory -Path ' + wp('D:', 'Biomedical_Project'),
        'Set-Location -Path ' + wp('D:', 'Biomedical_Project', 'notebooks'),
        'python -m venv .venv',
        '.venv' + B + 'Scripts' + B + 'Activate.ps1'
      ] : [
        'python --version',
        'py --version',
        'python -m pip --version',
        'where.exe python',
        'py -0p',
        'dir',
        'cd /d ' + wp('D:', 'Biomedical_Project', 'notebooks'),
        'python -m venv .venv',
        '.venv' + B + 'Scripts' + B + 'activate.bat'
      ];
      quickHost.innerHTML = quick.map(function (cmd) { return '<button type="button" data-bw-cmd="' + simEsc(cmd) + '">' + simEsc(cmd) + '</button>'; }).join('');
    }
    var output = simRoot.querySelector('#bw-terminal-output');
    if (output) output.textContent = SIM.lastTerminal || 'Simulated terminal ready. Choose a shell, refresh PATH if needed, then run a taught command.';
  }

  function simRenderEnvironment() {
    if (!simRoot) return;
    var user = simRoot.querySelector('#bw-user-path');
    var system = simRoot.querySelector('#bw-system-path');
    var snapshot = simRoot.querySelector('#bw-snapshot-path');
    var remove = simRoot.querySelector('#bw-path-remove');
    if (user) user.innerHTML = SIM.env.userPath.length ? SIM.env.userPath.map(function (item) { return '<li>' + simEsc(item) + '</li>'; }).join('') : '<li>(empty)</li>';
    if (system) system.innerHTML = SIM.env.systemPath.map(function (item) { return '<li>' + simEsc(item) + '</li>'; }).join('');
    if (snapshot) snapshot.innerHTML = SIM.pathSnapshot.map(function (item) { return '<li>' + simEsc(item) + '</li>'; }).join('');
    if (remove) remove.innerHTML = SIM.env.userPath.map(function (item, index) { return '<option value="' + index + '">' + simEsc(item) + '</option>'; }).join('') || '<option value="">(no user PATH entries)</option>';
    var status = simRoot.querySelector('#bw-env-status');
    if (status) status.textContent = SIM.envStatus || 'Edits affect only simulated PATH. Refresh the simulated terminal after changing it.';
  }

  function simRenderExplorer() {
    if (!simRoot) return;
    var files = simRoot.querySelector('#bw-explorer-files');
    if (files) {
      var items = [];
      if (SIM.downloaded) items.push('<li>python-' + simEsc(SIM.selectedRelease) + '-amd64.exe — simulated downloaded installer</li>');
      if (SIM.requirements) items.push('<li>requirements.txt — generated from the active simulated environment</li>');
      SIM.notebooks.forEach(function (notebook) { items.push('<li>' + simEsc(notebook.name) + ' — kernel: ' + simEsc(notebook.kernel) + '</li>'); });
      files.innerHTML = '<h4>Files</h4><ul class="bw-list">' + (items.join('') || '<li>No files yet.</li>') + '</ul>';
    }
    var tree = simRoot.querySelector('#bw-tree');
    if (tree) {
      tree.textContent = SIM.dirs.slice().sort().map(function (dir) { return dir + B; }).join(NL);
    }
    var req = simRoot.querySelector('#bw-requirements');
    if (req) req.textContent = SIM.requirements || 'No simulated requirements.txt has been generated yet.';
  }

  function simRenderJupyter() {
    if (!simRoot) return;
    var status = simRoot.querySelector('#bw-jupyter-status');
    if (status) status.textContent = SIM.jupyterRunning ? 'Running (simulated): ' + SIM.jupyterMode : 'Not started';
    var kernel = simRoot.querySelector('#bw-kernel-select');
    if (kernel) {
      kernel.innerHTML = '<option value="">global environment</option>' + Object.keys(SIM.venvs).map(function (path) {
        return '<option value="' + simEsc(path) + '">' + simEsc(path) + '</option>';
      }).join('');
      kernel.value = SIM.activeVenv || '';
    }
    var list = simRoot.querySelector('#bw-notebook-list');
    if (list) {
      list.innerHTML = SIM.notebooks.length ? SIM.notebooks.map(function (notebook) {
        return '<div class="bw-card"><h4>' + simEsc(notebook.name) + '</h4><p>Kernel: ' + simEsc(notebook.kernel || 'global environment') + '</p></div>';
      }).join('') : '<p>No simulated notebook has been created yet.</p>';
    }
  }

  function simRenderTroubleshooting() {
    if (!simRoot) return;
    var select = simRoot.querySelector('#bw-fault-select');
    if (select) {
      select.innerHTML = Object.keys(SIM_FAULTS).map(function (id) {
        return '<option value="' + simEsc(id) + '">' + simEsc(SIM_FAULTS[id].title) + '</option>';
      }).join('');
      if (simCurrentFault) select.value = simCurrentFault;
    }
    var title = simRoot.querySelector('#bw-fault-title');
    var problem = simRoot.querySelector('#bw-fault-problem');
    var diagHost = simRoot.querySelector('#bw-fault-diagnostics');
    var hint = simRoot.querySelector('#bw-fault-hint-text');
    var explanation = simRoot.querySelector('#bw-fault-explanation');
    var fix = simRoot.querySelector('#bw-fault-fix');
    var fault = SIM_FAULTS[simCurrentFault];
    var record = SIM.faults[simCurrentFault];
    if (!fault) {
      if (title) title.textContent = 'No fault loaded';
      if (problem) problem.textContent = 'Choose one of the fourteen seeded Windows setup problems and load it.';
      if (diagHost) diagHost.innerHTML = '';
      if (fix) fix.disabled = true;
      if (hint) hint.hidden = true;
      if (explanation) explanation.hidden = true;
      return;
    }
    if (title) title.textContent = fault.title;
    if (problem) problem.textContent = fault.problem;
    if (diagHost) {
      diagHost.innerHTML = fault.diagnostics.map(function (cmd) {
        var normal = simNormalise(cmd);
        return '<button type="button" class="' + (simDiagnosticsRun[normal] ? 'done' : '') + '" data-bw-diagnostic="' + simEsc(cmd) + '">' + (simDiagnosticsRun[normal] ? '✓ ' : '') + simEsc(cmd) + '</button>';
      }).join('');
    }
    if (hint) {
      hint.hidden = !SIM.faultHintShown;
      hint.textContent = fault.hint;
    }
    if (fix) fix.disabled = !simFaultDiagnosticsComplete() || Boolean(record && record.fixApplied);
    if (explanation) {
      explanation.hidden = !(record && record.resolved);
      explanation.textContent = record && record.resolved ? 'Resolved. ' + fault.explanation : '';
    }
  }

  function simRenderActivities() {
    if (!simRoot) return;
    var checklist = simRoot.querySelector('#bw-checklist');
    if (checklist) {
      if (!SIM.checklistDone) SIM.checklistDone = {};
      var rows = SIM.checklist.map(function (item, index) {
        return '<label><input type="checkbox" data-bw-check="' + index + '" ' + (SIM.checklistDone[index] ? 'checked' : '') + '/> ' + simEsc(item) + '</label>';
      });
      SIM.customChecklist.forEach(function (item, index) {
        rows.push('<label><input type="checkbox" data-bw-custom-check="' + index + '" ' + (item.done ? 'checked' : '') + '/> ' + simEsc(item.text) + '</label><button type="button" data-bw-remove-check="' + index + '">Remove</button>');
      });
      checklist.innerHTML = rows.join('<br>');
    }
    var batch = simRoot.querySelector('#bw-batch-script');
    if (batch && !batch.value) {
      batch.value = [
        '@echo off',
        'mkdir ' + wp('D:', 'Biomedical_Project', 'data'),
        'mkdir ' + wp('D:', 'Biomedical_Project', 'notebooks'),
        'mkdir ' + wp('D:', 'Biomedical_Project', 'figures'),
        'mkdir ' + wp('D:', 'Biomedical_Project', 'results'),
        'echo Project structure created.',
        'pause'
      ].join(NL);
    }
  }

  function simShowPanel(name) {
    if (!simRoot) return;
    Array.prototype.slice.call(simRoot.querySelectorAll('[data-bw-panel]')).forEach(function (panel) {
      panel.hidden = panel.getAttribute('data-bw-panel') !== name;
    });
    Array.prototype.slice.call(simRoot.querySelectorAll('[data-bw-tab]')).forEach(function (tab) {
      tab.setAttribute('aria-selected', tab.getAttribute('data-bw-tab') === name ? 'true' : 'false');
    });
  }

  function simAnnounce(id, message) {
    var el = simRoot && simRoot.querySelector('#' + id);
    if (el) el.textContent = message;
  }

  function simOpenDownload(tag) {
    SIM.selectedRelease = tag;
    SIM.downloaded = true;
    simMarkStep('download');
    SIM.installStatus = 'Simulated installer downloaded: python-' + tag + '-amd64.exe. Open it from the Downloads folder or the installer tab.';
    simSaveState();
    simRenderAll();
    simShowPanel('installer');
  }

  function simRunInstaller() {
    if (SIM.installing) return;
    if (!SIM.downloaded && !SIM.installed) {
      SIM.installStatus = 'Download an installer from the simulated python.org page first.';
      simRenderInstaller();
      simShowPanel('browser');
      return;
    }
    SIM.installerOpened = true;
    SIM.installScope = simRoot && simRoot.querySelector('#bw-scope-all') && simRoot.querySelector('#bw-scope-all').checked ? 'all' : 'user';
    SIM.pathAdded = Boolean(SIM.pathChoice);
    SIM.installing = true;
    SIM.installProgress = 5;
    SIM.installStatus = 'Copying simulated Python files and registering the launcher...';
    simRenderInstaller();
    clearInterval(simInstallTimer);
    simInstallTimer = setInterval(function () {
      SIM.installProgress = Math.min(100, (SIM.installProgress || 0) + 18);
      simRenderInstaller();
      if (SIM.installProgress >= 100) {
        clearInterval(simInstallTimer);
        simInstallTimer = null;
        SIM.installing = false;
        if (SIM.installScope === 'all' && !SIM.admin) {
          SIM.installStatus = 'Installation failed: writing to Program Files needs administrator permission. Choose Install for current user and try again.';
          SIM.installed = false;
          simRenderAll();
          return;
        }
        simEnsureInstalled();
        if (SIM.pathAdded) simAddPythonToEnv(false);
        simMarkStep('install');
        SIM.installStatus = 'Installation complete in the simulation. ' + (SIM.pathAdded
          ? 'PATH was updated in the environment editor; refresh the terminal before verifying.'
          : 'python.exe was not added to PATH. Continue to the terminal exercise to see the consequence.');
        simSaveState();
        simRenderAll();
      }
    }, 180);
  }

  function simRunCommandText(command) {
    simShowPanel('terminal');
    if (simTerminalInput) simTerminalInput.value = command;
    simRunCommand();
  }

  function simRunCommand() {
    if (!simTerminalInput) return;
    var command = simTerminalInput.value;
    var lines = simExec(command, { shell: SIM.shell });
    if (simTerminalOutput) simTerminalOutput.textContent = lines.join(NL);
    simRenderAll();
  }

  function simRunDiagnostic(command) {
    simRunCommandText(command);
  }

  function simRefreshTerminalAction() {
    var message = simRefreshTerminal();
    SIM.lastTerminal = message;
    simRenderAll();
  }

  function simAddPath() {
    var input = simRoot && simRoot.querySelector('#bw-path-input');
    var value = input ? input.value.trim() : '';
    if (!value) {
      SIM.envStatus = 'Enter a simulated Windows path first.';
    } else if (!(value.charAt(1) === ':' && value.charAt(2) === B) && value.charAt(0) !== '%') {
      SIM.envStatus = 'Invalid simulated PATH entry. Use a drive path such as C:' + B + 'Python312 or an environment variable token.';
    } else if (SIM.env.userPath.indexOf(value) !== -1) {
      SIM.envStatus = 'That entry is already in simulated user PATH.';
    } else {
      if (value.toLowerCase().indexOf('python') !== -1 || value.toLowerCase().indexOf('scripts') !== -1) SIM.env.userPath.unshift(value);
      else SIM.env.userPath.push(value);
      SIM.envStatus = 'Added ' + value + ' to simulated user PATH. Python entries are placed ahead of store aliases. Existing terminals still use the old snapshot until refreshed.';
      if (value.toLowerCase().indexOf('python') !== -1) SIM.pathAdded = true;
      if (input) input.value = '';
    }
    simSaveState();
    simRenderEnvironment();
  }

  function simRemovePath() {
    var select = simRoot && simRoot.querySelector('#bw-path-remove');
    var index = select ? parseInt(select.value, 10) : -1;
    if (isNaN(index) || index < 0 || index >= SIM.env.userPath.length) {
      SIM.envStatus = 'Choose a simulated user PATH entry to remove.';
    } else {
      var removed = SIM.env.userPath.splice(index, 1)[0];
      SIM.envStatus = 'Removed ' + removed + ' from simulated user PATH.';
    }
    simSaveState();
    simRenderEnvironment();
  }

  function simLoadFault(id) {
    var fault = simSeedFault(id);
    if (!fault) return;
    SIM.faultHintShown = false;
    SIM.lastTerminal = 'Seeded fault loaded: ' + fault.title + '. Run diagnostics before applying a fix.';
    simRenderAll();
    simShowPanel('troubleshoot');
  }

  function simApplyFaultFix() {
    var fault = SIM_FAULTS[simCurrentFault];
    var record = SIM.faults[simCurrentFault];
    if (!fault || !simFaultDiagnosticsComplete() || (record && record.fixApplied)) return;
    var message = fault.fix(SIM);
    SIM.faults[simCurrentFault] = record || {};
    SIM.faults[simCurrentFault].fixApplied = true;
    SIM.lastTerminal = message;
    simCheckFaultResolution();
    simSaveState();
    simRenderAll();
  }

  function simRunCell() {
    var area = simRoot && simRoot.querySelector('#bw-cell-code');
    var code = area ? area.value.trim().split(NL)[0] : '';
    if (!code) return;
    var quote = String.fromCharCode(34);
    var lines = simExec('python -c ' + quote + code + quote, { shell: SIM.shell });
    var output = simRoot && simRoot.querySelector('#bw-cell-output');
    if (output) output.textContent = 'Kernel: ' + (SIM.activeVenv || 'global environment') + NL + lines.join(NL);
    simRenderAll();
  }

  function simMakeTwoEnvs() {
    var base = wp('D:', 'Biomedical_Project');
    var paths = [wp(base, 'project_a', '.venv'), wp(base, 'project_b', '.venv')];
    paths.forEach(function (path) { simEnsureDir(path.split(B).slice(0, -1).join(B)); });
    SIM.venvs[paths[0]] = { path: paths[0], version: SIM.installVersion || SIM.selectedRelease, packages: { pip: SIM_PACKAGES.pip, pandas: '2.2.3', numpy: '2.1.3' }, created: Date.now() };
    SIM.venvs[paths[1]] = { path: paths[1], version: SIM.installVersion || SIM.selectedRelease, packages: { pip: SIM_PACKAGES.pip, pandas: '1.5.3', numpy: '1.26.4' }, created: Date.now() };
    SIM.activeVenv = null;
    simMarkStep('venv');
    SIM.envCompare = 'Created two simulated environments with different pandas versions.';
    simSaveState();
    simRenderAll();
  }

  function simCompareEnvs() {
    var keys = Object.keys(SIM.venvs);
    var lines = keys.map(function (path) {
      return '--- ' + path + ' ---' + NL + simFreezeLines(SIM.venvs[path].packages).join(NL);
    });
    if (keys.length < 2) lines.push('Create two project environments first to compare them.');
    var output = simRoot && simRoot.querySelector('#bw-env-compare');
    if (output) output.textContent = lines.join(NL + NL);
  }

  function simAddChecklist() {
    var input = simRoot && simRoot.querySelector('#bw-checklist-input');
    var value = input ? input.value.trim() : '';
    if (!value) return;
    SIM.customChecklist.push({ text: value, done: false });
    if (input) input.value = '';
    simSaveState();
    simRenderActivities();
  }

  function simResetSimulation() {
    clearInterval(simInstallTimer);
    simInstallTimer = null;
    SIM = simDefaultState();
    simCurrentFault = '';
    simDiagnosticsRun = {};
    simSaveState();
    if (simTerminalInput) simTerminalInput.value = '';
    if (simTerminalOutput) simTerminalOutput.textContent = 'Simulation reset. No host installation, PATH or package state was changed.';
    simRenderAll();
    simShowPanel('desktop');
  }

  function simWireRoot() {
    simRoot.addEventListener('click', function (event) {
      var button = event.target.closest('button');
      if (!button) return;
      var tab = button.getAttribute('data-bw-tab');
      var open = button.getAttribute('data-bw-open');
      var release = button.getAttribute('data-bw-release');
      var command = button.getAttribute('data-bw-cmd');
      var diagnostic = button.getAttribute('data-bw-diagnostic');
      var check = button.getAttribute('data-bw-remove-check');
      if (tab) simShowPanel(tab);
      else if (open) {
        var menu = simRoot.querySelector('#bw-start-menu');
        if (menu) menu.hidden = true;
        simShowPanel(open);
      } else if (release) simOpenDownload(release);
      else if (command) simRunCommandText(command);
      else if (diagnostic) simRunDiagnostic(diagnostic);
      else if (check !== null && check !== undefined) {
        SIM.customChecklist.splice(parseInt(check, 10), 1);
        simSaveState();
        simRenderActivities();
      }
    });

    simRoot.addEventListener('change', function (event) {
      var target = event.target;
      if (target.id === 'bw-shell-select') {
        SIM.shell = target.value;
        simSaveState();
        simRenderTerminal();
      } else if (target.id === 'bw-path-checkbox') {
        SIM.pathChoice = Boolean(target.checked);
        simSaveState();
      } else if (target.id === 'bw-fault-select') {
        simCurrentFault = target.value;
      } else if (target.id === 'bw-kernel-select') {
        SIM.notebooks.forEach(function (notebook) { notebook.kernel = target.value || 'global environment'; });
        simSaveState();
        simRenderJupyter();
        simRenderExplorer();
      } else if (target.getAttribute('data-bw-check') !== null) {
        if (!SIM.checklistDone) SIM.checklistDone = {};
        SIM.checklistDone[target.getAttribute('data-bw-check')] = Boolean(target.checked);
        simSaveState();
      } else if (target.getAttribute('data-bw-custom-check') !== null) {
        var index = parseInt(target.getAttribute('data-bw-custom-check'), 10);
        if (SIM.customChecklist[index]) SIM.customChecklist[index].done = Boolean(target.checked);
        simSaveState();
      }
    });

    if (simTerminalInput) {
      simTerminalInput.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          simRunCommand();
        }
      });
    }

    function wire(id, handler) {
      var el = simRoot.querySelector('#' + id);
      if (el) el.addEventListener('click', handler);
    }
    wire('bw-reset', simResetSimulation);
    wire('bw-start-btn', function () {
      var menu = simRoot.querySelector('#bw-start-menu');
      if (menu) menu.hidden = !menu.hidden;
    });
    wire('bw-install-now', simRunInstaller);
    wire('bw-customize', function () {
      SIM.customizeOpen = !SIM.customizeOpen;
      simRenderInstaller();
    });
    wire('bw-run-command', simRunCommand);
    wire('bw-refresh-terminal', simRefreshTerminalAction);
    wire('bw-new-terminal', simRefreshTerminalAction);
    wire('bw-add-path', simAddPath);
    wire('bw-remove-path', simRemovePath);
    wire('bw-env-refresh', simRefreshTerminalAction);
    wire('bw-launch-notebook', function () { simRunCommandText('jupyter notebook'); });
    wire('bw-launch-lab', function () { simRunCommandText('jupyter lab'); });
    wire('bw-new-notebook', function () {
      var name = 'biomedical_notebook_' + (SIM.notebooks.length + 1) + '.ipynb';
      var kernel = simRoot.querySelector('#bw-kernel-select');
      SIM.notebooks.push({ name: name, kernel: kernel && kernel.value ? kernel.value : 'global environment' });
      simSaveState();
      simRenderJupyter();
      simRenderExplorer();
    });
    wire('bw-run-cell', simRunCell);
    wire('bw-load-fault', function () {
      var select = simRoot.querySelector('#bw-fault-select');
      if (select) simLoadFault(select.value);
    });
    wire('bw-fault-hint', function () {
      SIM.faultHintShown = true;
      simSaveState();
      simRenderTroubleshooting();
    });
    wire('bw-fault-fix', simApplyFaultFix);
    wire('bw-seed-path', function () { simLoadFault('python-not-recognised'); });
    wire('bw-add-checklist', simAddChecklist);
    wire('bw-make-two-envs', simMakeTwoEnvs);
    wire('bw-compare-envs', simCompareEnvs);
    wire('bw-seed-conflict', function () {
      simLoadFault('dependency-conflict');
      simRunCommandText('python -m pip check');
    });
    wire('bw-run-batch', function () {
      var area = simRoot.querySelector('#bw-batch-script');
      var lines = simRunBatch(area ? area.value : '');
      var output = simRoot.querySelector('#bw-batch-output');
      if (output) output.textContent = lines.join(NL);
      simRenderAll();
    });
    simRoot.querySelectorAll('input[name=bw-scope]').forEach(function (input) {
      input.addEventListener('change', function () {
        SIM.installScope = input.value;
        simSaveState();
      });
    });
  }

  SIM = simLoadState();
  window.BiomedicalSimulation = {
    create: createWindowsSimulation,
    getState: function () { return SIM; },
    execute: function (command) { return simExec(command, { shell: SIM.shell }); },
    reset: simResetSimulation,
    seedFault: simSeedFault,
    runDiagnostic: simFaultDiagnosticDone,
    diagnosticsComplete: simFaultDiagnosticsComplete,
    diagnosticsRun: function () { return Object.keys(simDiagnosticsRun); },
    faultDiagnostics: function (id) { return SIM_FAULTS[id] ? SIM_FAULTS[id].diagnostics.slice() : []; },
    applyFix: simApplyFaultFix,
    currentFault: function () { return simCurrentFault; },
    runBatch: simRunBatch,
    showPanel: simShowPanel,
    refreshTerminal: simRefreshTerminal,
    faults: Object.keys(SIM_FAULTS)
  };
  API.windowsSimulation = window.BiomedicalSimulation;

  function createWindowsSimulation() {
    return simCreateRoot();
  }

  window.BiomedicalAPI = API;
  addStyles();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach, { once: true });
  } else {
    attach();
  }
})();
