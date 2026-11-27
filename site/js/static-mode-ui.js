// Small UI layer for the read-only GitHub Pages copy.
// It hides backend-only controls, adds a clear notice, and keeps PDF/Excel/ICS
// exports available without a server.
(function () {
  "use strict";
  if (!window.MNH_STATIC_MODE) return;

  const MESSAGE = window.MNH_READ_ONLY_MESSAGE || "Read-only version — changes are not saved.";

  function banner() {
    if (document.getElementById("mnh-static-banner")) return;
    const bar = document.createElement("div");
    bar.id = "mnh-static-banner";
    bar.className = "mnh-static-banner";
    bar.textContent = "Read-only snapshot · hosted on GitHub Pages · changes and sign-in are unavailable";
    document.body.insertBefore(bar, document.body.firstChild);
  }

  // The install gate belongs to the hosted app, not to the read-only snapshot.
  // Every other view stays reachable; write controls are disabled below and
  // backend-only views carry an explicit read-only notice.
  function hideBackendViews() {
    document.querySelectorAll("#mnh-first-open-gate").forEach((node) => {
      node.hidden = true;
      node.style.display = "none";
    });
  }

  const VIEW_NOTICES = {
    "public-chat": "Read-only snapshot — the group chat needs the backend. Message history and sending are unavailable.",
    "communications": "Read-only snapshot — saved announcements are shown below. WhatsApp, contacts and messaging tools are unavailable.",
    "exams": "Read-only snapshot — the exam workspace needs the backend. Questions, attempts and submissions are unavailable.",
  };

  // Deep links into a resource subview must still have somewhere sensible to
  // go back to. Walk through the parent view first so app.js records the same
  // "previous" view it would have recorded after a normal Resources tap.
  const RESOURCE_PARENTS = {
    "python-library": "resources",
    "statistical-glossary": "resources",
    "stat8100-practical": "resources",
    "hypothesis-lab": "resources",
    "python-setup-simulation": "python-library",
  };

  function updateViewNotice(name) {
    const text = VIEW_NOTICES[name] || "";
    [
      ["view-workspace", "mnh-static-workspace-notice"],
      ["view-exams", "mnh-static-exams-notice"],
    ].forEach(([hostId, noticeId]) => {
      const host = document.getElementById(hostId);
      if (!host) return;
      let node = document.getElementById(noticeId);
      if (!node) {
        node = document.createElement("div");
        node.id = noticeId;
        node.className = "mnh-view-notice";
        host.insertBefore(node, host.firstChild);
      }
      node.textContent = text;
      node.hidden = !text;
    });
  }

  function annotateAssistant() {
    const root = document.getElementById("class-rep-assistant");
    if (!root || document.getElementById("mnh-static-assistant-notice")) return;
    const note = document.createElement("div");
    note.id = "mnh-static-assistant-notice";
    note.className = "mnh-view-notice";
    note.textContent = "Read-only snapshot — Class Rep chat and LiveKit classroom need the backend. Offline classroom slides are linked under Resources.";
    root.insertBefore(note, root.firstChild);
  }

  const WRITE_LABEL = /^(add|edit|delete|remove|save|create|upload|import|backup|restore|sign in|log in|register|join|send|record voice|start exam|submit|grade|mark as|hang up|post|react|approve|reject|sync now)/i;
  function disableWrites(root) {
    const scan = (node) => {
      if (!node || !node.querySelectorAll) return;
      node.querySelectorAll("button, input[type=file], input[type=submit]").forEach((control) => {
        if (control.type === "file" || control.type === "submit") {
          control.disabled = true;
          control.hidden = true;
          return;
        }
        const label = (control.textContent || control.getAttribute("aria-label") || control.title || "").trim();
        if (!WRITE_LABEL.test(label)) return;
        if (control.disabled) return;
        control.disabled = true;
        control.dataset.mnhReadOnlyDisabled = "1";
        control.classList.add("mnh-readonly-disabled");
        control.title = MESSAGE;
      });
    };
    scan(root || document);
  }

  // ---- Client-side exports -------------------------------------------------
  async function rowsFor(collection) {
    return window.mnhApi.request("GET", `/api/col/${collection}`);
  }

  function download(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function timetableRows(rows) {
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    return rows
      .map((row) => row.data || row)
      .filter((item) => item && (item.title || item.code))
      .map((item) => {
        const day = Number(item.dayIndex);
        return {
          week: item.weekStart || "weekly template",
          day: Number.isInteger(day) && day >= 0 && day < days.length ? days[day] : String(item.day || ""),
          start: item.startTime || "",
          end: item.endTime || "",
          code: item.code || item.moduleCode || "",
          title: item.title || "",
          presenter: item.facilitator || "",
          mode: item.mode || "",
          status: item.status || "",
        };
      })
      .sort((a, b) => a.day.localeCompare(b.day) || a.start.localeCompare(b.start));
  }

  async function exportCsv() {
    const table = timetableRows(await rowsFor("cells"));
    const headers = ["Week", "Day", "Start", "End", "Code", "Title", "Presenter", "Mode", "Status"];
    const escape = (value) => '"' + String(value ?? "").replace(/"/g, '""') + '"';
    const text = [headers.map(escape).join(",")]
      .concat(table.map((row) => headers.map((key) => escape(row[key.toLowerCase()])).join(",")))
      .join("\r\n");
    download(new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8" }), "MNH-Smart-Calendar-Timetable.csv");
  }

  async function exportIcs() {
    const rows = timetableRows(await rowsFor("cells"));
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const stamp = (date) => date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MNH Smart Calendar//Static Export//EN", "CALSCALE:GREGORIAN"];
    rows.forEach((row, index) => {
      const dayIndex = days.indexOf(row.day);
      if (dayIndex < 0 || !row.start) return;
      const base = row.week && /^\d{4}-\d{2}-\d{2}$/.test(row.week)
        ? new Date(`${row.week}T00:00:00`)
        : new Date();
      base.setDate(base.getDate() + ((dayIndex - base.getDay() + 7) % 7));
      const [sh, sm] = row.start.split(":").map(Number);
      const [eh, em] = (row.end || row.start).split(":").map(Number);
      const start = new Date(base); start.setHours(sh || 0, sm || 0, 0, 0);
      const end = new Date(base); end.setHours(eh || sh || 0, em || sm || 0, 0, 0);
      if (end <= start) end.setTime(start.getTime() + 60 * 60 * 1000);
      lines.push(
        "BEGIN:VEVENT",
        `UID:mnh-static-${index}-${stamp(start)}@mnh-smart-calendar.github.io`,
        `DTSTAMP:${stamp(new Date())}`,
        `DTSTART:${stamp(start)}`,
        `DTEND:${stamp(end)}`,
        `SUMMARY:${(row.code ? row.code + " — " : "") + (row.title || "Session")}`.replace(/,/g, "\\,"),
        `DESCRIPTION:${[row.presenter && "Presenter: " + row.presenter, row.status && "Status: " + row.status].filter(Boolean).join("; ")}`.replace(/,/g, "\\,"),
        "END:VEVENT"
      );
    });
    lines.push("END:VCALENDAR");
    download(new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" }), "MNH-Smart-Calendar.ics");
  }

  async function exportPdf() {
    const rows = timetableRows(await rowsFor("cells"));
    if (!window.jspdf || !window.jspdf.jsPDF) throw new Error("PDF library is not available");
    const doc = new window.jspdf.jsPDF({ orientation: "landscape", unit: "pt", format: "a4" });
    doc.setFontSize(15);
    doc.text("MNH Smart Calendar — Weekly Timetable", 40, 44);
    doc.setFontSize(9);
    doc.text("Read-only snapshot exported from GitHub Pages", 40, 60);
    const columns = [
      { title: "Day", key: "day", width: 90 },
      { title: "Time", key: "time", width: 85 },
      { title: "Code", key: "code", width: 110 },
      { title: "Title", key: "title", width: 260 },
      { title: "Presenter", key: "presenter", width: 105 },
      { title: "Status", key: "status", width: 75 },
    ];
    const lines = rows.map((row) => ({
      day: row.day,
      time: row.start + (row.end ? "–" + row.end : ""),
      code: row.code,
      title: String(row.title || "").slice(0, 52),
      presenter: row.presenter,
      status: row.status,
    }));
    let y = 78;
    const pageHeight = doc.internal.pageSize.getHeight();
    doc.setFont("helvetica", "bold");
    doc.setFontSize(8);
    columns.forEach((column, index) => {
      const x = 40 + columns.slice(0, index).reduce((sum, item) => sum + item.width, 0);
      doc.text(column.title, x, y);
    });
    doc.setFont("helvetica", "normal");
    lines.forEach((line, lineIndex) => {
      y += 18;
      if (y > pageHeight - 30) {
        doc.addPage();
        y = 45;
      }
      if (lineIndex % 2 === 1) {
        doc.setFillColor(240, 244, 250);
        doc.rect(38, y - 12, columns.reduce((sum, item) => sum + item.width, 0) + 4, 17, "F");
      }
      columns.forEach((column, index) => {
        const x = 40 + columns.slice(0, index).reduce((sum, item) => sum + item.width, 0);
        doc.text(String(line[column.key] ?? "").slice(0, 40), x, y);
      });
    });
    doc.save("MNH-Smart-Calendar-Timetable.pdf");
  }

  async function loadXlsxLibrary() {
    if (window.XLSX) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "./vendor/xlsx.full.min.js";
      script.onload = resolve;
      script.onerror = () => reject(new Error("Excel library is not available"));
      document.head.appendChild(script);
    });
  }

  async function exportXlsx() {
    const rows = timetableRows(await rowsFor("cells"));
    await loadXlsxLibrary();
    const sheet = window.XLSX.utils.json_to_sheet(rows);
    const book = window.XLSX.utils.book_new();
    window.XLSX.utils.book_append_sheet(book, sheet, "Timetable");
    const buffer = window.XLSX.write(book, { type: "array", bookType: "xlsx" });
    download(new Blob([buffer], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }), "MNH-Smart-Calendar-Editable-Timetable.xlsx");
  }

  function notice(error) {
    const node = document.createElement("div");
    node.className = "mnh-readonly-notice is-visible";
    node.textContent = "Export could not be created: " + (error && error.message ? error.message : error);
    document.body.appendChild(node);
    window.setTimeout(() => node.remove(), 6000);
  }

  function wireDownloads() {
    const menu = document.getElementById("dl-menu");
    if (menu && !menu.querySelector('[data-static-ics]')) {
      const item = document.createElement("button");
      item.type = "button";
      item.setAttribute("role", "menuitem");
      item.dataset.staticIcs = "1";
      item.textContent = "Calendar (.ics)";
      menu.appendChild(item);
    }
    document.addEventListener("click", (event) => {
      const item = event.target.closest && event.target.closest("#dl-menu button");
      if (!item) return;
      const kind = item.dataset.staticIcs ? "ics" : item.dataset.fmt;
      if (!["pdf", "xlsx", "ics"].includes(kind)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const menuNode = document.getElementById("dl-menu");
      if (menuNode) menuNode.hidden = true;
      const task = kind === "pdf" ? exportPdf() : kind === "xlsx" ? exportXlsx() : exportIcs();
      task.catch(notice);
    }, true);

    window.downloadTimetablePDF = () => exportPdf().catch(notice);
    window.downloadTimetableExcel = () => exportXlsx().catch(notice);
    window.exportTimetableICS = () => exportIcs().catch(notice);
    window.exportTimetableCSV = () => exportCsv().catch(notice);
  }

  function init() {
    banner();
    hideBackendViews();
    disableWrites(document);
    wireDownloads();

    // Keep the read-only notices in step with the app's own view changes.
    const originalShowView = window.showView;
    if (typeof originalShowView === "function") {
      window.showView = function (name) {
        const result = originalShowView.apply(this, arguments);
        updateViewNotice(name);
        return result;
      };
    }

    const requestedView = new URLSearchParams(location.search).get("view");
    updateViewNotice(requestedView || "weekly");

    // app.js looks for a "view-<name>" element before honouring ?view=. The
    // workspace-backed views (chat, communications, exams, modules, …) live in
    // the shared view-workspace, and exams.js loads after app.js, so the first
    // attempt falls back to the weekly page. Re-apply the deep link now that
    // every script has loaded and the showView wrapper is installed.
    if (requestedView && requestedView !== "weekly" && typeof window.showView === "function") {
      const parent = RESOURCE_PARENTS[requestedView];
      if (parent) window.showView(parent);
      window.showView(requestedView);
    }
    annotateAssistant();

    // Dynamically rendered buttons (dialogs, chat, exam workspace) are covered too.
    const observer = new MutationObserver((records) => {
      records.forEach((record) => {
        record.addedNodes.forEach((node) => {
          if (node.nodeType === 1) disableWrites(node);
        });
      });
      hideBackendViews();
      annotateAssistant();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
