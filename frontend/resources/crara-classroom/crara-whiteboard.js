(function () {
  "use strict";

  // Additive CRARA whiteboard. It reuses the existing classroom LiveKit data
  // channel through the thin bridge exposed by crara-classroom.js. It does not
  // create a second classroom, chat, AI service, or voice system.
  const NS = "http://www.w3.org/2000/svg";
  const TOPIC = "crara-whiteboard";
  const STORAGE_KEY = "crara-whiteboard-v1";
  const COLORS = ["#000000", "#2563eb", "#dc2626", "#16a34a", "#cbd5e1"];
  const TOOLS = {
    pen: "pen",
    pencil: "pencil",
    marker: "marker",
    highlighter: "highlighter",
    eraser: "eraser",
    select: "select",
    text: "text",
    equation: "equation",
    graph: "graph",
    line: "line",
    arrow: "arrow",
    rect: "rect",
    circle: "circle",
    pan: "pan"
  };
  const INSTRUCTIONS = new Set([
    "WRITE_TEXT", "DRAW_STROKE", "DRAW_LINE", "DRAW_ARROW", "DRAW_CIRCLE",
    "DRAW_RECTANGLE", "DRAW_CURVE", "DRAW_GRAPH", "RENDER_EQUATION",
    "HIGHLIGHT", "ERASE", "MOVE_OBJECT", "RESIZE_OBJECT", "EDIT_TEXT",
    "ADD_PAGE", "DELETE_PAGE", "NAVIGATE_PAGE", "UNDO", "REDO",
    "CLEAR_BOARD", "ZOOM", "PAN"
  ]);
  const SHAPE_TOOLS = new Set([TOOLS.line, TOOLS.arrow, TOOLS.rect, TOOLS.circle]);
  const DRAW_TOOLS = new Set([TOOLS.pen, TOOLS.pencil, TOOLS.marker, TOOLS.highlighter]);
  const CHAT_MODES = ["Active", "Question Queue", "Host-selected", "Chat-only", "Silent monitoring"];
  const TEACHING = ["idle", "teaching", "listening", "answering", "paused", "stopped"];
  const API = {
    instructions: "/api/class-rep/whiteboard/instructions",
    session: "/api/class-rep/whiteboard/session",
    control: "/api/class-rep/whiteboard/control",
    authorize: "/api/class-rep/whiteboard/authorize"
  };

  const state = {
    actor: "crara-board-" + Math.random().toString(36).slice(2, 10),
    seq: Date.now(),
    lastSeq: 0,
    pages: [blankPage()],
    pageIndex: 0,
    tool: TOOLS.pen,
    color: "#2563eb",
    width: 3,
    eraserSize: 18,
    zoom: 1,
    pan: { x: 0, y: 0 },
    selected: "",
    undo: [],
    redo: [],
    teaching: "idle",
    lesson: "Hypothesis Testing",
    role: "student",
    chatMode: "Active",
    permissions: { canWrite: true, canControl: false, boardLocked: false, boardOwner: "", granted: [] },
    questionQueue: [],
    aiBusy: false,
    narrationAudio: null,
    sessionKey: "local",
    identity: "",
    interrupted: false,
    introduced: false
  };
  let session = null;
  let open = false;
  let root = null;
  let svg = null;
  let scene = null;
  let statusEl = null;
  let pageEl = null;
  let captionEl = null;
  let modeEl = null;
  let questionEl = null;
  let hostPanel = null;
  let pointerDraft = null;
  let pointerDrag = null;

  function blankPage() {
    return { id: "page-" + Math.random().toString(36).slice(2, 10), objects: [] };
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clamp(value, low, high, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? Math.min(high, Math.max(low, n)) : fallback;
  }

  function cleanColor(value, fallback) {
    const text = String(value || "");
    return /^#[0-9a-fA-F]{6}$/.test(text) ? text : fallback;
  }

  function cleanText(value, max) {
    return String(value === undefined || value === null ? "" : value).slice(0, max || 1200);
  }

  function cleanPoints(value, max) {
    if (!Array.isArray(value)) return [];
    return value.slice(0, max || 500).map(function (p) {
      const source = Array.isArray(p) ? { x: p[0], y: p[1] } : (p || {});
      return {
        x: clamp(source.x, -10000, 10000, 0),
        y: clamp(source.y, -10000, 10000, 0)
      };
    }).filter(function (p) { return Number.isFinite(p.x) && Number.isFinite(p.y); });
  }

  function cleanStyle(style) {
    const src = style || {};
    return {
      color: cleanColor(src.color, "#2563eb"),
      width: clamp(src.width, 1, 40, 3),
      opacity: clamp(src.opacity, 0.05, 1, 1),
      highlight: Boolean(src.highlight)
    };
  }

  function cleanObject(raw) {
    if (!raw || typeof raw !== "object") return null;
    const type = String(raw.type || "").toLowerCase();
    const allowed = ["stroke", "curve", "graph", "line", "arrow", "rect", "circle", "text", "equation"];
    if (allowed.indexOf(type) < 0) return null;
    const item = {
      id: cleanText(raw.id || ("obj-" + Math.random().toString(36).slice(2, 10)), 80),
      type: type,
      style: cleanStyle(raw.style)
    };
    if (type === "stroke" || type === "curve" || type === "graph") {
      item.points = cleanPoints(raw.points, 500);
      if (!item.points.length) return null;
      if (type === "graph") item.label = cleanText(raw.label, 120);
    } else if (type === "line" || type === "arrow" || type === "rect" || type === "circle") {
      item.x1 = clamp(raw.x1, -10000, 10000, 0);
      item.y1 = clamp(raw.y1, -10000, 10000, 0);
      item.x2 = clamp(raw.x2, -10000, 10000, 100);
      item.y2 = clamp(raw.y2, -10000, 10000, 100);
    } else if (type === "text") {
      item.x = clamp(raw.x, -10000, 10000, 0);
      item.y = clamp(raw.y, -10000, 10000, 0);
      item.text = cleanText(raw.text, 1200);
      if (!item.text) return null;
    } else if (type === "equation") {
      item.x = clamp(raw.x, -10000, 10000, 0);
      item.y = clamp(raw.y, -10000, 10000, 0);
      item.latex = cleanText(raw.latex, 800);
      if (!item.latex) return null;
    }
    return item;
  }

  function cleanPages(value) {
    if (!Array.isArray(value) || !value.length) return [blankPage()];
    return value.slice(0, 50).map(function (page) {
      const objects = Array.isArray(page && page.objects) ? page.objects.slice(0, 500).map(cleanObject).filter(Boolean) : [];
      return { id: cleanText(page && page.id, 80) || blankPage().id, objects: objects };
    });
  }

  function currentPage() {
    if (!state.pages[state.pageIndex]) state.pages[state.pageIndex] = blankPage();
    return state.pages[state.pageIndex];
  }

  function snapshot() {
    return JSON.stringify(currentPage());
  }

  function uid(prefix) {
    return (prefix || "obj") + "-" + Math.random().toString(36).slice(2, 11);
  }

  function pushHistory() {
    state.undo.push(snapshot());
    if (state.undo.length > 80) state.undo.shift();
    state.redo.length = 0;
  }

  function notifySession() {
    if (!open) dispatchState();
  }

  function dispatchState() {
    window.dispatchEvent(new CustomEvent("crara-whiteboard-state", { detail: { open: open } }));
  }

  function persist() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        pages: state.pages,
        pageIndex: state.pageIndex,
        zoom: state.zoom,
        pan: state.pan,
        chatMode: state.chatMode,
        permissions: state.permissions,
        sessionKey: state.sessionKey
      }));
    } catch (_) {
      /* Storage can be unavailable in private browsing; the board still works. */
    }
  }

  function publish(type, extra) {
    if (!session || typeof session.publishWhiteboardData !== "function" || session.status !== "connected") return;
    state.seq = Math.max(state.seq, Date.now()) + 1;
    const packet = Object.assign({ v: 1, type: type, actor: state.actor, seq: state.seq, lesson: state.lesson }, extra || {});
    const result = session.publishWhiteboardData(TOPIC, packet);
    if (result && typeof result.catch === "function") result.catch(function () {});
  }

  function publishState() {
    publish("state", { pages: state.pages, pageIndex: state.pageIndex });
  }

  function commit(options) {
    const config = options || {};
    if (config.history !== false) pushHistory();
    persist();
    render();
    publishState();
  }

  function restore() {
    let raw = null;
    try { raw = window.localStorage.getItem(STORAGE_KEY); } catch (_) {}
    if (!raw) return false;
    try {
      const saved = JSON.parse(raw);
      state.pages = cleanPages(saved.pages);
      state.pageIndex = clamp(saved.pageIndex, 0, state.pages.length - 1, 0);
      state.zoom = clamp(saved.zoom, 0.2, 5, 1);
      state.pan = {
        x: clamp(saved.pan && saved.pan.x, -5000, 5000, 0),
        y: clamp(saved.pan && saved.pan.y, -5000, 5000, 0)
      };
      if (CHAT_MODES.indexOf(saved.chatMode) >= 0) state.chatMode = saved.chatMode;
      setPermissions(saved.permissions || {});
      if (saved.sessionKey) state.sessionKey = cleanText(saved.sessionKey, 160);
      state.undo.length = 0;
      state.redo.length = 0;
      render();
      publishState();
      return true;
    } catch (_) {
      return false;
    }
  }

  function setSession(value) {
    const previous = session;
    session = value || null;
    state.sessionKey = session && session.roomName ? cleanText(session.roomName, 160) : "local";
    state.identity = session && session.selfName ? cleanText(session.selfName, 160) : "";
    if (statusEl) {
      const connected = Boolean(session && session.status === "connected");
      statusEl.textContent = connected ? "Live · synchronized" : "Local · reconnecting";
      statusEl.className = "cr-wb-status " + (connected ? "live" : "");
    }
    if (!previous && session && connected()) publish("hello");
    if (open && connected() && !state.introduced) startLessonIntro();
  }

  function connected() {
    return Boolean(session && session.status === "connected" && typeof session.publishWhiteboardData === "function");
  }

  function onRemote(topic, data, participant) {
    if (topic !== TOPIC) return;
    let packet = null;
    try {
      packet = JSON.parse(new TextDecoder().decode(data));
    } catch (_) {
      return;
    }
    if (!packet || packet.v !== 1 || packet.actor === state.actor) return;
    const seq = Number(packet.seq);
    if (!Number.isFinite(seq) || seq <= state.lastSeq) return;
    state.lastSeq = seq;
    if (packet.type === "hello") {
      publishState();
      return;
    }
    if (packet.type === "state") {
      state.pages = cleanPages(packet.pages);
      state.pageIndex = clamp(packet.pageIndex, 0, state.pages.length - 1, 0);
      state.undo.length = 0;
      state.redo.length = 0;
      persist();
      render();
      return;
    }
    if (packet.type === "caption") {
      setCaption(cleanText(packet.text, 300), cleanText(packet.from, 80));
      return;
    }
    if (packet.type === "teaching" || packet.type === "mode" || packet.type === "permissions") {
      if (packet.authority) authorizeControl(packet);
      return;
    }
    if (packet.type === "interrupt") {
      interruptLesson(cleanText(packet.reason, 300));
      return;
    }
    if (packet.type === "answer") {
      setCaption(cleanText(packet.caption, 300), "CRARA");
    }
  }

  function svgNode(tag, attrs) {
    const node = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) {
      if (attrs[key] !== undefined && attrs[key] !== null) node.setAttribute(key, String(attrs[key]));
    });
    return node;
  }

  function pointsText(points) {
    return points.map(function (p) { return p.x + "," + p.y; }).join(" ");
  }

  function renderObject(obj) {
    const style = obj.style || cleanStyle(null);
    const common = { "data-wb-id": obj.id, class: "cr-wb-object" + (state.selected === obj.id ? " selected" : "") };
    const stroke = {
      fill: "none",
      stroke: style.color,
      "stroke-width": style.width * (style.highlight ? 3 : 1),
      "stroke-opacity": style.highlight ? 0.35 : style.opacity,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      "vector-effect": "non-scaling-stroke"
    };
    let node = null;
    if (obj.type === "stroke" || obj.type === "curve" || obj.type === "graph") {
      node = svgNode("polyline", Object.assign({}, common, stroke, { points: pointsText(obj.points) }));
      if (obj.type === "graph") node.setAttribute("data-wb-label", obj.label || "graph");
    } else if (obj.type === "line" || obj.type === "arrow") {
      node = svgNode("line", Object.assign({}, common, stroke, {
        x1: obj.x1, y1: obj.y1, x2: obj.x2, y2: obj.y2,
        "marker-end": obj.type === "arrow" ? "url(#cr-wb-arrow)" : ""
      }));
    } else if (obj.type === "rect") {
      node = svgNode("rect", Object.assign({}, common, stroke, {
        x: Math.min(obj.x1, obj.x2), y: Math.min(obj.y1, obj.y2),
        width: Math.abs(obj.x2 - obj.x1), height: Math.abs(obj.y2 - obj.y1)
      }));
    } else if (obj.type === "circle") {
      const cx = (obj.x1 + obj.x2) / 2;
      const cy = (obj.y1 + obj.y2) / 2;
      node = svgNode("ellipse", Object.assign({}, common, stroke, {
        cx: cx, cy: cy,
        rx: Math.max(1, Math.abs(obj.x2 - obj.x1) / 2),
        ry: Math.max(1, Math.abs(obj.y2 - obj.y1) / 2)
      }));
    } else if (obj.type === "text") {
      node = svgNode("text", Object.assign({}, common, {
        x: obj.x, y: obj.y, fill: style.color, "font-size": Math.max(12, style.width * 6)
      }));
      node.textContent = obj.text;
    } else if (obj.type === "equation") {
      node = svgNode("foreignObject", Object.assign({}, common, {
        x: obj.x, y: obj.y, width: 420, height: 120
      }));
      const box = el("div", "cr-wb-equation");
      try {
        if (window.katex && typeof window.katex.render === "function") {
          window.katex.render(obj.latex, box, { throwOnError: false, trust: false });
        } else {
          box.textContent = obj.latex;
        }
      } catch (_) {
        box.textContent = obj.latex;
      }
      node.appendChild(box);
    }
    return node;
  }

  function applyView() {
    if (!scene) return;
    scene.setAttribute("transform", "translate(" + state.pan.x + " " + state.pan.y + ") scale(" + state.zoom + ")");
    if (pageEl) pageEl.textContent = "Page " + (state.pageIndex + 1) + " / " + state.pages.length;
  }

  function render() {
    if (!scene) return;
    scene.replaceChildren();
    currentPage().objects.forEach(function (obj) {
      const node = renderObject(obj);
      if (node) scene.appendChild(node);
    });
    applyView();
  }

  function buildUI() {
    root = el("div", "cr-wb-overlay");
    root.hidden = true;
    root.setAttribute("aria-label", "CRARA shared whiteboard");

    const head = el("header", "cr-wb-head");
    const brand = el("div", "cr-wb-brand");
    brand.append(el("b", "cr-wb-name", "CRARA Whiteboard"), el("span", "cr-wb-sub", state.lesson));
    statusEl = el("span", "cr-wb-status", "Local · not connected");
    const headActions = el("div", "cr-wb-headactions");
    const saveBtn = el("button", "cr-wb-btn", "Save on this device");
    const restoreBtn = el("button", "cr-wb-btn", "Restore saved");
    const exportBtn = el("button", "cr-wb-btn", "Export SVG");
    const closeBtn = el("button", "cr-wb-btn cr-wb-close", "Close");
    headActions.append(saveBtn, restoreBtn, exportBtn, closeBtn);
    head.append(brand, statusEl, headActions);

    const tools = el("div", "cr-wb-tools");
    tools.setAttribute("role", "toolbar");
    tools.setAttribute("aria-label", "Whiteboard tools");
    const toolButtons = [
      ["select", "Select"], ["pen", "Pen"], ["pencil", "Pencil"], ["marker", "Marker"],
      ["highlighter", "Highlighter"], ["eraser", "Eraser"], ["text", "Text"],
      ["equation", "Equation"], ["graph", "Graph"], ["line", "Line"], ["arrow", "Arrow"],
      ["rect", "Rectangle"], ["circle", "Circle"], ["pan", "Pan"]
    ];
    toolButtons.forEach(function (entry) {
      const button = el("button", "cr-wb-tool", entry[1]);
      button.dataset.wbTool = entry[0];
      button.title = entry[1] + " tool";
      tools.appendChild(button);
    });
    tools.appendChild(el("span", "cr-wb-divider"));
    COLORS.forEach(function (color) {
      const button = el("button", "cr-wb-color");
      button.style.background = color;
      button.dataset.wbColor = color;
      button.title = "Use " + color;
      tools.appendChild(button);
    });
    const custom = document.createElement("input");
    custom.type = "color";
    custom.className = "cr-wb-custom";
    custom.value = state.color;
    custom.title = "Custom colour";
    tools.appendChild(custom);

    const width = document.createElement("input");
    width.type = "range";
    width.min = "1";
    width.max = "40";
    width.value = String(state.width);
    width.className = "cr-wb-width";
    width.title = "Stroke thickness";
    tools.appendChild(width);

    const editBtn = el("button", "cr-wb-btn", "Edit selected");
    const undoBtn = el("button", "cr-wb-btn", "Undo");
    const redoBtn = el("button", "cr-wb-btn", "Redo");
    const clearBtn = el("button", "cr-wb-btn cr-wb-danger", "Clear");
    const addPageBtn = el("button", "cr-wb-btn", "+ Page");
    const prevPageBtn = el("button", "cr-wb-btn", "Previous");
    const nextPageBtn = el("button", "cr-wb-btn", "Next");
    const deletePageBtn = el("button", "cr-wb-btn", "Delete page");
    const zoomOutBtn = el("button", "cr-wb-btn", "Zoom −");
    const zoomInBtn = el("button", "cr-wb-btn", "Zoom +");
    const fitBtn = el("button", "cr-wb-btn", "Fit to screen");
    tools.append(editBtn, undoBtn, redoBtn, clearBtn, el("span", "cr-wb-divider"),
      addPageBtn, prevPageBtn, nextPageBtn, deletePageBtn, el("span", "cr-wb-divider"),
      zoomOutBtn, zoomInBtn, fitBtn);

    const control = el("div", "cr-wb-control");
    control.setAttribute("role", "toolbar");
    control.setAttribute("aria-label", "CRARA lesson controls");
    const modeLabel = el("label", "cr-wb-label", "Chat mode");
    modeEl = document.createElement("select");
    modeEl.className = "cr-wb-mode";
    CHAT_MODES.forEach(function (mode) {
      const option = document.createElement("option");
      option.value = mode;
      option.textContent = mode;
      modeEl.appendChild(option);
    });
    modeEl.value = state.chatMode;
    modeLabel.appendChild(modeEl);
    const askInput = document.createElement("input");
    askInput.type = "text";
    askInput.className = "cr-wb-ask-input";
    askInput.maxLength = 600;
    askInput.placeholder = "Ask CRARA a question about Hypothesis Testing";
    askInput.setAttribute("aria-label", "Question for CRARA");
    const askBtn = el("button", "cr-wb-btn cr-wb-ask", "Ask CRARA");
    hostPanel = el("div", "cr-wb-host");
    const hostButtons = [
      ["pause", "Pause CRARA"], ["resume", "Resume CRARA"], ["stop", "Stop CRARA"],
      ["take", "Take board control"], ["lock", "Lock board"], ["unlock", "Unlock board"],
      ["enable", "Enable student writing"], ["disable", "Disable student writing"],
      ["grant", "Grant permission"], ["revoke", "Revoke permission"],
      ["server-save", "Save session"], ["server-restore", "Restore session"]
    ];
    hostButtons.forEach(function (entry) {
      const button = el("button", "cr-wb-btn", entry[1]);
      button.dataset.wbHost = entry[0];
      hostPanel.appendChild(button);
    });
    questionEl = el("div", "cr-wb-queue");
    questionEl.setAttribute("aria-live", "polite");
    control.append(modeLabel, askInput, askBtn, hostPanel, questionEl);

    const stage = el("div", "cr-wb-stage");
    svg = svgNode("svg", {
      class: "cr-wb-svg",
      viewBox: "0 0 1600 900",
      preserveAspectRatio: "xMidYMid meet",
      role: "application",
      "aria-label": "CRARA whiteboard canvas"
    });
    svg.innerHTML = '<defs><pattern id="cr-wb-grid" width="40" height="40" patternUnits="userSpaceOnUse">' +
      '<path d="M40 0H0V40" fill="none" stroke="#1b2545" stroke-width="1"/></pattern>' +
      '<marker id="cr-wb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">' +
      '<path d="M0 0 10 5 0 10z" fill="context-stroke"/></marker></defs>' +
      '<rect class="cr-wb-bg" x="-5000" y="-5000" width="10000" height="10000" fill="url(#cr-wb-grid)"/>';
    scene = svgNode("g", { class: "cr-wb-scene" });
    svg.appendChild(scene);
    stage.appendChild(svg);

    const foot = el("footer", "cr-wb-foot");
    pageEl = el("span", "cr-wb-page", "Page 1 / 1");
    captionEl = el("span", "cr-wb-caption", "");
    foot.append(pageEl, captionEl);

    root.append(head, tools, control, stage, foot);
    document.body.appendChild(root);

    closeBtn.addEventListener("click", close);
    saveBtn.addEventListener("click", function () { persist(); announce("Whiteboard saved on this device."); });
    restoreBtn.addEventListener("click", function () { announce(restore() ? "Saved whiteboard restored." : "No saved whiteboard found."); });
    exportBtn.addEventListener("click", exportSvg);
    editBtn.addEventListener("click", editSelected);
    undoBtn.addEventListener("click", undo);
    redoBtn.addEventListener("click", redo);
    clearBtn.addEventListener("click", function () {
      if (!window.confirm("Clear every object on this page?")) return;
      mutate(function () { currentPage().objects = []; state.selected = ""; });
    });
    addPageBtn.addEventListener("click", function () {
      mutate(function () { state.pages.splice(state.pageIndex + 1, 0, blankPage()); state.pageIndex += 1; state.selected = ""; });
    });
    prevPageBtn.addEventListener("click", function () { navigatePage(state.pageIndex - 1); });
    nextPageBtn.addEventListener("click", function () { navigatePage(state.pageIndex + 1); });
    deletePageBtn.addEventListener("click", function () {
      if (state.pages.length === 1) return announce("The whiteboard needs at least one page.");
      mutate(function () { state.pages.splice(state.pageIndex, 1); state.pageIndex = Math.min(state.pageIndex, state.pages.length - 1); state.selected = ""; });
    });
    zoomOutBtn.addEventListener("click", function () { setZoom(state.zoom / 1.2); });
    zoomInBtn.addEventListener("click", function () { setZoom(state.zoom * 1.2); });
    fitBtn.addEventListener("click", fitToScreen);
    modeEl.addEventListener("change", function () { hostSetMode(modeEl.value); });
    askBtn.addEventListener("click", function () {
      const question = askInput.value.trim();
      if (!question) return announce("Type a question for CRARA first.");
      askInput.value = "";
      askQuestion({ id: uid("ask"), body: question, from: state.role === "host" ? "Host" : "You", mine: true });
    });
    askInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); askBtn.click(); }
    });
    hostPanel.addEventListener("click", function (event) {
      const button = event.target.closest("[data-wb-host]");
      if (button) hostAction(button.dataset.wbHost);
    });

    tools.addEventListener("click", function (event) {
      const tool = event.target.closest("[data-wb-tool]");
      if (tool) {
        setTool(tool.dataset.wbTool);
        return;
      }
      const color = event.target.closest("[data-wb-color]");
      if (color) {
        state.color = cleanColor(color.dataset.wbColor, state.color);
        refreshToolState();
      }
    });
    custom.addEventListener("input", function () {
      state.color = cleanColor(custom.value, state.color);
      refreshToolState();
    });
    width.addEventListener("input", function () {
      state.width = clamp(width.value, 1, 40, 3);
    });

    svg.addEventListener("pointerdown", onPointerDown);
    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("pointercancel", onPointerUp);
    svg.addEventListener("wheel", function (event) {
      event.preventDefault();
      setZoom(state.zoom * (event.deltaY > 0 ? 0.9 : 1.1));
    }, { passive: false });

    refreshToolState();
    refreshRoleState();
    renderQueue();
    render();
  }

  function announce(message) {
    if (captionEl) captionEl.textContent = String(message || "");
  }

  function refreshToolState() {
    if (!root) return;
    root.querySelectorAll("[data-wb-tool]").forEach(function (button) {
      button.classList.toggle("active", button.dataset.wbTool === state.tool);
    });
    root.querySelectorAll("[data-wb-color]").forEach(function (button) {
      button.classList.toggle("active", button.dataset.wbColor === state.color);
    });
    const custom = root.querySelector(".cr-wb-custom");
    if (custom) custom.value = state.color;
  }

  function setTool(tool) {
    if (!TOOLS[tool]) return;
    state.tool = tool;
    state.selected = "";
    refreshToolState();
    render();
    announce(tool.charAt(0).toUpperCase() + tool.slice(1) + " selected.");
  }

  function pointFromEvent(event) {
    if (!svg || !scene) return { x: 0, y: 0 };
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const matrix = scene.getScreenCTM();
    if (!matrix) return { x: event.clientX, y: event.clientY };
    const local = point.matrixTransform(matrix.inverse());
    return { x: clamp(local.x, -10000, 10000, 0), y: clamp(local.y, -10000, 10000, 0) };
  }

  function objectFromEvent(event) {
    const target = event.target;
    const node = target && target.closest ? target.closest("[data-wb-id]") : null;
    if (!node) return null;
    return currentPage().objects.find(function (obj) { return obj.id === node.getAttribute("data-wb-id"); }) || null;
  }

  function styleForTool() {
    const highlighter = state.tool === TOOLS.highlighter || state.tool === TOOLS.marker;
    return cleanStyle({
      color: state.color,
      width: highlighter ? Math.max(8, state.width * 2) : state.tool === TOOLS.pencil ? Math.max(1, state.width / 2) : state.width,
      opacity: highlighter ? 0.35 : 1,
      highlight: highlighter
    });
  }

  function onPointerDown(event) {
    if (!open || event.button > 0) return;
    if (!canEditBoard() && state.tool !== TOOLS.pan && state.tool !== TOOLS.select) {
      announce("Board editing is locked by the host.");
      return;
    }
    const point = pointFromEvent(event);
    const hit = objectFromEvent(event);
    try { svg.setPointerCapture(event.pointerId); } catch (_) {}

    if (state.tool === TOOLS.pan) {
      pointerDrag = { kind: "pan", x: event.clientX, y: event.clientY, pan: { x: state.pan.x, y: state.pan.y } };
      return;
    }
    if (state.tool === TOOLS.select) {
      state.selected = hit ? hit.id : "";
      if (hit && canEditBoard()) pointerDrag = { kind: "object", id: hit.id, start: point, original: JSON.parse(JSON.stringify(hit)) };
      render();
      return;
    }
    if (state.tool === TOOLS.eraser) {
      if (!hit) return;
      mutate(function () {
        currentPage().objects = currentPage().objects.filter(function (obj) { return obj.id !== hit.id; });
        if (state.selected === hit.id) state.selected = "";
      });
      return;
    }
    if (state.tool === TOOLS.text || state.tool === TOOLS.equation || state.tool === TOOLS.graph) {
      promptObject(state.tool, point);
      return;
    }
    const style = styleForTool();
    if (DRAW_TOOLS.has(state.tool)) {
      pointerDraft = { kind: "draw", object: cleanObject({ id: uid("stroke"), type: "stroke", points: [point], style: style }) };
      pushHistory();
      currentPage().objects.push(pointerDraft.object);
      render();
      return;
    }
    if (SHAPE_TOOLS.has(state.tool)) {
      const shapeMap = { line: "line", arrow: "arrow", rect: "rect", circle: "circle" };
      pointerDraft = {
        kind: "shape",
        object: cleanObject({
          id: uid("shape"), type: shapeMap[state.tool], x1: point.x, y1: point.y,
          x2: point.x + 1, y2: point.y + 1, style: style
        })
      };
      pushHistory();
      currentPage().objects.push(pointerDraft.object);
      render();
    }
  }

  function onPointerMove(event) {
    if (!pointerDraft && !pointerDrag) return;
    if (pointerDrag && pointerDrag.kind === "pan") {
      state.pan.x = pointerDrag.pan.x + (event.clientX - pointerDrag.x);
      state.pan.y = pointerDrag.pan.y + (event.clientY - pointerDrag.y);
      applyView();
      return;
    }
    const point = pointFromEvent(event);
    if (pointerDrag && pointerDrag.kind === "object") {
      const original = pointerDrag.original;
      const dx = point.x - pointerDrag.start.x;
      const dy = point.y - pointerDrag.start.y;
      const target = currentPage().objects.find(function (obj) { return obj.id === pointerDrag.id; });
      if (!target) return;
      if (target.points) target.points = original.points.map(function (p) { return { x: p.x + dx, y: p.y + dy }; });
      if (target.x1 !== undefined) {
        target.x1 = original.x1 + dx; target.y1 = original.y1 + dy;
        target.x2 = original.x2 + dx; target.y2 = original.y2 + dy;
      }
      if (target.x !== undefined) { target.x = original.x + dx; target.y = original.y + dy; }
      render();
      return;
    }
    if (!pointerDraft) return;
    if (pointerDraft.kind === "draw") {
      const points = pointerDraft.object.points;
      const last = points[points.length - 1];
      if (!last || Math.abs(last.x - point.x) + Math.abs(last.y - point.y) > 1.5) {
        points.push(point);
        if (points.length > 500) points.shift();
      }
    } else if (pointerDraft.kind === "shape") {
      pointerDraft.object.x2 = point.x;
      pointerDraft.object.y2 = point.y;
    }
    render();
  }

  function onPointerUp() {
    if (pointerDrag && pointerDrag.kind === "object") {
      pointerDrag = null;
      commit();
      return;
    }
    if (pointerDrag && pointerDrag.kind === "pan") {
      pointerDrag = null;
      persist();
      publishState();
      return;
    }
    if (!pointerDraft) return;
    const obj = pointerDraft.object;
    pointerDraft = null;
    if (obj.type === "stroke" && obj.points.length < 2) obj.points.push({ x: obj.points[0].x + 1, y: obj.points[0].y + 1 });
    state.selected = obj.id;
    commit({ history: false });
  }

  function promptObject(kind, point) {
    let value = window.prompt(kind === "text" ? "Text to write on the board:" : kind === "equation" ? "LaTeX equation:" : "Graph points as x,y pairs separated by commas:");
    if (value === null || !String(value).trim()) return;
    let obj = null;
    if (kind === "text") {
      obj = { id: uid("text"), type: "text", x: point.x, y: point.y, text: cleanText(value, 1200), style: cleanStyle({ color: state.color, width: state.width }) };
    } else if (kind === "equation") {
      const latex = String(value).trim().replace(/^\$+|\$+$/g, "");
      obj = { id: uid("eq"), type: "equation", x: point.x, y: point.y, latex: cleanText(latex, 800), style: cleanStyle({ color: state.color, width: state.width }) };
    } else {
      const points = String(value).split(/[\n,;]+/).map(function (item) {
        const pair = item.trim().split(/\s+/);
        return { x: Number(pair[0]), y: Number(pair[1]) };
      }).filter(function (p) { return Number.isFinite(p.x) && Number.isFinite(p.y); });
      if (points.length < 2) return announce("Enter at least two valid numeric points.");
      obj = { id: uid("graph"), type: "graph", points: cleanPoints(points, 500), label: "validated data", style: cleanStyle({ color: state.color, width: state.width }) };
    }
    const clean = cleanObject(obj);
    if (!clean) return;
    mutate(function () { currentPage().objects.push(clean); state.selected = clean.id; });
  }

  function editSelected() {
    if (!state.selected) return announce("Select an object first.");
    const obj = currentPage().objects.find(function (item) { return item.id === state.selected; });
    if (!obj) return announce("The selected object is no longer on this page.");
    if (obj.type === "text" || obj.type === "equation") {
      const label = obj.type === "text" ? "Text" : "LaTeX equation";
      const value = window.prompt("Edit " + label + ":", obj.type === "text" ? obj.text : obj.latex);
      if (value === null) return;
      mutate(function () {
        if (obj.type === "text") obj.text = cleanText(value, 1200);
        else obj.latex = cleanText(value, 800);
      });
      return;
    }
    const scaleText = window.prompt("Resize factor (0.1 to 5):", "1");
    const scale = Number(scaleText);
    if (!Number.isFinite(scale) || scale <= 0) return announce("Enter a positive resize factor.");
    resizeObject(obj.id, clamp(scale, 0.1, 5, 1));
  }

  function mutate(fn, system) {
    if (!system && !canEditBoard()) {
      announce("Board editing is locked by the host.");
      return;
    }
    pushHistory();
    fn();
    persist();
    render();
    publishState();
  }

  function systemMutate(fn) {
    mutate(fn, true);
  }

  function undo() {
    if (!state.undo.length) return announce("Nothing to undo.");
    state.redo.push(snapshot());
    state.pages[state.pageIndex] = JSON.parse(state.undo.pop());
    state.selected = "";
    persist();
    render();
    publishState();
  }

  function redo() {
    if (!state.redo.length) return announce("Nothing to redo.");
    state.undo.push(snapshot());
    state.pages[state.pageIndex] = JSON.parse(state.redo.pop());
    state.selected = "";
    persist();
    render();
    publishState();
  }

  function navigatePage(index) {
    const next = clamp(index, 0, state.pages.length - 1, state.pageIndex);
    if (next === state.pageIndex) return;
    state.pageIndex = next;
    state.selected = "";
    state.undo.length = 0;
    state.redo.length = 0;
    persist();
    render();
    publishState();
  }

  function setZoom(value) {
    state.zoom = clamp(value, 0.2, 5, 1);
    applyView();
    persist();
    publishState();
  }

  function fitToScreen() {
    state.zoom = 1;
    state.pan = { x: 0, y: 0 };
    applyView();
    persist();
    publishState();
  }

  function findObject(id) {
    return currentPage().objects.find(function (obj) { return obj.id === id; }) || null;
  }

  function resizeObject(id, scale) {
    const obj = findObject(id);
    if (!obj) return fail("Object not found.");
    const factor = clamp(scale, 0.1, 5, 1);
    if (obj.points) {
      const cx = obj.points.reduce(function (sum, p) { return sum + p.x; }, 0) / obj.points.length;
      const cy = obj.points.reduce(function (sum, p) { return sum + p.y; }, 0) / obj.points.length;
      obj.points = obj.points.map(function (p) { return { x: cx + (p.x - cx) * factor, y: cy + (p.y - cy) * factor }; });
    }
    if (obj.x1 !== undefined) {
      const cx = (obj.x1 + obj.x2) / 2;
      const cy = (obj.y1 + obj.y2) / 2;
      obj.x1 = cx + (obj.x1 - cx) * factor;
      obj.y1 = cy + (obj.y1 - cy) * factor;
      obj.x2 = cx + (obj.x2 - cx) * factor;
      obj.y2 = cy + (obj.y2 - cy) * factor;
    }
    commit();
    return ok();
  }

  function exportSvg() {
    render();
    const copy = svg.cloneNode(true);
    copy.setAttribute("xmlns", NS);
    const source = new XMLSerializer().serializeToString(copy);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = el("a");
    link.href = url;
    link.download = "crara-whiteboard-" + Date.now() + ".svg";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function ok() { return { ok: true }; }
  function fail(error) { return { ok: false, error: String(error || "Invalid instruction.") }; }

  function requireId(args) {
    const id = cleanText(args.id, 80);
    return findObject(id) ? id : null;
  }

  // Validated, code-free instruction executor. Every supported operation maps
  // to a fixed SVG primitive; AI-generated JavaScript is never executed.
  function executeInstruction(raw) {
    const mutate = systemMutate;
    if (!raw || typeof raw !== "object") return fail("Instruction must be an object.");
    const name = String(raw.type || raw.op || "").toUpperCase();
    if (!INSTRUCTIONS.has(name)) return fail("Unsupported instruction: " + name);
    const args = raw.args && typeof raw.args === "object" ? raw.args : raw;
    let obj = null;
    let id = null;

    if (name === "WRITE_TEXT") {
      const text = cleanText(args.text, 1200);
      if (!text) return fail("WRITE_TEXT requires text.");
      obj = cleanObject({ id: uid("text"), type: "text", x: clamp(args.x, -10000, 10000, 80), y: clamp(args.y, -10000, 10000, 120), text: text, style: cleanStyle(args.style) });
    } else if (name === "DRAW_STROKE" || name === "DRAW_CURVE" || name === "DRAW_GRAPH") {
      const points = cleanPoints(args.points, 500);
      if (points.length < 2) return fail(name + " requires at least two points.");
      obj = cleanObject({ id: uid("draw"), type: name === "DRAW_CURVE" ? "curve" : name === "DRAW_GRAPH" ? "graph" : "stroke", points: points, label: cleanText(args.label, 120), style: cleanStyle(args.style) });
      if (!obj) return fail("Invalid points.");
      mutate(function () { currentPage().objects.push(obj); });
      return ok();
    } else if (name === "DRAW_LINE" || name === "DRAW_ARROW" || name === "DRAW_CIRCLE" || name === "DRAW_RECTANGLE") {
      const type = name === "DRAW_RECTANGLE" ? "rect" : name.toLowerCase().replace("draw_", "");
      obj = cleanObject({
        id: uid("shape"), type: type,
        x1: clamp(args.x1, -10000, 10000, 80), y1: clamp(args.y1, -10000, 10000, 80),
        x2: clamp(args.x2, -10000, 10000, 480), y2: clamp(args.y2, -10000, 10000, 320),
        style: cleanStyle(args.style)
      });
    } else if (name === "RENDER_EQUATION") {
      const latex = cleanText(args.latex, 800);
      if (!latex) return fail("RENDER_EQUATION requires latex.");
      obj = cleanObject({ id: uid("eq"), type: "equation", x: clamp(args.x, -10000, 10000, 80), y: clamp(args.y, -10000, 10000, 120), latex: latex, style: cleanStyle(args.style) });
    } else if (name === "HIGHLIGHT") {
      id = requireId(args);
      if (!id) return fail("HIGHLIGHT requires a valid id.");
      mutate(function () { findObject(id).style.highlight = true; });
      return ok();
    } else if (name === "ERASE") {
      id = requireId(args);
      if (!id) return fail("ERASE requires a valid id.");
      mutate(function () {
        currentPage().objects = currentPage().objects.filter(function (item) { return item.id !== id; });
        if (state.selected === id) state.selected = "";
      });
      return ok();
    } else if (name === "MOVE_OBJECT") {
      id = requireId(args);
      if (!id) return fail("MOVE_OBJECT requires a valid id.");
      const dx = clamp(args.dx, -5000, 5000, 0);
      const dy = clamp(args.dy, -5000, 5000, 0);
      mutate(function () {
        const target = findObject(id);
        if (target.points) target.points = target.points.map(function (p) { return { x: p.x + dx, y: p.y + dy }; });
        if (target.x1 !== undefined) { target.x1 += dx; target.y1 += dy; target.x2 += dx; target.y2 += dy; }
        if (target.x !== undefined) { target.x += dx; target.y += dy; }
      });
      return ok();
    } else if (name === "RESIZE_OBJECT") {
      id = requireId(args);
      if (!id) return fail("RESIZE_OBJECT requires a valid id.");
      return resizeObject(id, args.scale);
    } else if (name === "EDIT_TEXT") {
      id = requireId(args);
      if (!id) return fail("EDIT_TEXT requires a valid id.");
      const target = findObject(id);
      if (target.type !== "text" && target.type !== "equation") return fail("EDIT_TEXT only works on text or equations.");
      const value = cleanText(args.text !== undefined ? args.text : args.latex, 1200);
      if (!value) return fail("EDIT_TEXT requires new content.");
      mutate(function () {
        if (target.type === "text") target.text = value;
        else target.latex = value;
      });
      return ok();
    } else if (name === "ADD_PAGE") {
      mutate(function () { state.pages.splice(state.pageIndex + 1, 0, blankPage()); state.pageIndex += 1; state.selected = ""; });
      return ok();
    } else if (name === "DELETE_PAGE") {
      if (state.pages.length <= 1) return fail("The board needs at least one page.");
      mutate(function () {
        const index = clamp(args.index, 0, state.pages.length - 1, state.pageIndex);
        state.pages.splice(index, 1);
        state.pageIndex = Math.min(state.pageIndex, state.pages.length - 1);
        state.selected = "";
      });
      return ok();
    } else if (name === "NAVIGATE_PAGE") {
      navigatePage(clamp(args.index, 0, state.pages.length - 1, state.pageIndex));
      return ok();
    } else if (name === "UNDO") {
      undo();
      return ok();
    } else if (name === "REDO") {
      redo();
      return ok();
    } else if (name === "CLEAR_BOARD") {
      mutate(function () { currentPage().objects = []; state.selected = ""; });
      return ok();
    } else if (name === "ZOOM") {
      setZoom(args.value !== undefined ? args.value : state.zoom * clamp(args.factor, 0.1, 10, 1));
      return ok();
    } else if (name === "PAN") {
      state.pan.x = clamp(state.pan.x + clamp(args.dx, -5000, 5000, 0), -10000, 10000, state.pan.x);
      state.pan.y = clamp(state.pan.y + clamp(args.dy, -5000, 5000, 0), -10000, 10000, state.pan.y);
      applyView();
      persist();
      publishState();
      return ok();
    }

    if (!obj) return fail("Invalid instruction arguments.");
    mutate(function () { currentPage().objects.push(obj); state.selected = obj.id; });
    return ok();
  }

  function isHost() {
    return state.role === "host" || state.role === "owner" || state.role === "crara";
  }

  function canEditBoard() {
    if (isHost()) return true;
    const permissions = state.permissions;
    if (!permissions.canWrite || permissions.boardLocked) return false;
    if (!permissions.boardOwner) return true;
    return permissions.boardOwner === state.actor || permissions.boardOwner === state.identity ||
      (Array.isArray(permissions.granted) && permissions.granted.indexOf(state.identity) >= 0);
  }

  function setRole(value) {
    const role = cleanText(value, 24) || "student";
    state.role = role;
    refreshRoleState();
  }

  function refreshRoleState() {
    if (!root) return;
    root.classList.toggle("cr-wb-host-mode", isHost());
    if (hostPanel) hostPanel.hidden = !isHost();
    if (modeEl) {
      modeEl.value = state.chatMode;
      modeEl.disabled = !isHost();
      modeEl.title = isHost() ? "Choose how CRARA handles live chat" : "The host controls the chat mode";
    }
  }

  function setPermissions(patch) {
    if (!patch || typeof patch !== "object") return;
    const src = patch.permissions && typeof patch.permissions === "object" ? patch.permissions : patch;
    state.permissions = {
      canWrite: src.canWrite === undefined ? state.permissions.canWrite : Boolean(src.canWrite),
      canControl: src.canControl === undefined ? state.permissions.canControl : Boolean(src.canControl),
      boardLocked: src.boardLocked === undefined ? state.permissions.boardLocked : Boolean(src.boardLocked),
      boardOwner: src.boardOwner === undefined ? state.permissions.boardOwner : cleanText(src.boardOwner, 160),
      granted: Array.isArray(src.granted) ? src.granted.slice(0, 100).map(function (id) { return cleanText(id, 160); }) : state.permissions.granted
    };
    refreshRoleState();
  }

  function setChatMode(value, broadcast) {
    const mode = CHAT_MODES.indexOf(value) >= 0 ? value : "Active";
    state.chatMode = mode;
    if (modeEl) modeEl.value = mode;
    if (broadcast !== false) {
      persist();
      publish("mode", { mode: mode });
    }
    announce("Chat mode: " + mode + ".");
  }

  function authorizeControl(packet) {
    let value = {};
    if (packet.type === "mode") value = { mode: cleanText(packet.mode, 40) };
    else if (packet.type === "teaching") value = { value: cleanText(packet.value, 24) };
    else if (packet.permissions && typeof packet.permissions === "object") value = packet.permissions;
    postJson(API.authorize, {
      key: state.sessionKey,
      type: packet.type,
      value: value,
      token: cleanText(packet.authority, 2000)
    }).then(function (result) {
      if (!result.ok) return;
      if (packet.type === "mode") setChatMode(value.mode, false);
      else if (packet.type === "teaching") setTeachingState(value.value);
      else setPermissions(value);
    }).catch(function () {});
  }

  async function hostSetMode(value) {
    if (!isHost()) return announce("Host controls are available to the classroom host.");
    const mode = CHAT_MODES.indexOf(value) >= 0 ? value : "Active";
    try {
      const result = await postJson(API.control, {
        key: state.sessionKey,
        type: "mode",
        value: { mode: mode }
      });
      setChatMode(result.value.mode, false);
      publish("mode", { mode: result.value.mode, authority: result.token });
    } catch (_) {
      announce("Chat mode requires the CRARA lesson service.");
    }
  }

  async function hostSetTeaching(value) {
    if (!isHost()) return announce("Host controls are available to the classroom host.");
    const stateValue = TEACHING.indexOf(value) >= 0 ? value : "idle";
    try {
      const result = await postJson(API.control, {
        key: state.sessionKey,
        type: "teaching",
        value: { value: stateValue }
      });
      setTeachingState(result.value.value);
      publish("teaching", { value: result.value.value, authority: result.token });
      return result.value.value;
    } catch (_) {
      announce("Lesson controls require the CRARA lesson service.");
      return null;
    }
  }

  async function hostSetPermissions(patch) {
    if (!isHost()) return announce("Host controls are available to the classroom host.");
    const next = Object.assign({}, state.permissions, patch || {});
    try {
      const result = await postJson(API.control, {
        key: state.sessionKey,
        type: "permissions",
        value: next
      });
      setPermissions(result.value);
      publish("permissions", { permissions: result.value, authority: result.token });
      return result.value;
    } catch (_) {
      announce("Board permissions require the CRARA lesson service.");
      return null;
    }
  }

  function renderQueue() {
    if (!questionEl) return;
    questionEl.replaceChildren();
    if (!state.questionQueue.length) {
      questionEl.appendChild(el("span", "cr-wb-queue-empty", "No queued questions"));
      return;
    }
    questionEl.appendChild(el("span", "cr-wb-queue-title", "Question queue"));
    state.questionQueue.slice(0, 8).forEach(function (question, index) {
      const row = el("div", "cr-wb-queue-row");
      row.appendChild(el("span", "cr-wb-queue-text", cleanText(question.from, 60) + ": " + cleanText(question.body, 160)));
      if (isHost()) {
        const answer = el("button", "cr-wb-btn", "Answer");
        answer.addEventListener("click", function () {
          const item = state.questionQueue.splice(index, 1)[0];
          renderQueue();
          if (item) askQuestion(item);
        });
        row.appendChild(answer);
      }
      questionEl.appendChild(row);
    });
  }

  function askQuestion(question) {
    return onChat(question);
  }

  function onChat(message) {
    if (!message || state.teaching === "stopped" || state.aiBusy) return;
    const body = cleanText(message.body, 600);
    if (!body || /^crara\b/i.test(cleanText(message.from, 80))) return;
    const hostQuestion = isHost() || message.mine === true;
    if (state.chatMode === "Silent monitoring") {
      setCaption("Silent monitoring — question noted for the host.", "CRARA");
      return;
    }
    if ((state.chatMode === "Question Queue" || state.chatMode === "Host-selected") && !hostQuestion) {
      state.questionQueue.push({ id: cleanText(message.id, 80) || uid("q"), body: body, from: cleanText(message.from, 80) || "Student" });
      state.questionQueue = state.questionQueue.slice(-20);
      renderQueue();
      setCaption("Question added to the host queue.", "CRARA");
      publish("question", { body: body, from: cleanText(message.from, 80) });
      return;
    }
    return respondToQuestion({ id: cleanText(message.id, 80), body: body, from: cleanText(message.from, 80) || "Student" });
  }

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) throw new Error("Request failed: " + response.status);
    return response.json();
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) throw new Error("Request failed: " + response.status);
    return response.json();
  }

  async function runInstructions(instructions, caption) {
    const results = [];
    const list = Array.isArray(instructions) ? instructions.slice(0, 50) : [];
    for (let index = 0; index < list.length; index += 1) {
      await new Promise(function (resolve) { window.setTimeout(resolve, 180); });
      const result = executeInstruction(list[index]);
      results.push(result);
      if (!result.ok) {
        publish("instruction-error", { index: index, error: result.error });
      } else if (caption) {
        setCaption(caption + " · board step " + (index + 1) + "/" + list.length, "CRARA");
      }
    }
    return results;
  }

  function speakNarration(text) {
    const narration = cleanText(text, 1200);
    if (!narration) return;
    try {
      if (state.narrationAudio) {
        state.narrationAudio.pause();
        state.narrationAudio = null;
      }
      fetch("/api/class-rep/speak", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: narration, lesson: state.lesson })
      }).then(async function (response) {
        if (!response.ok) return;
        const type = response.headers.get("content-type") || "";
        let url = "";
        if (type.indexOf("application/json") >= 0) {
          const data = await response.json();
          url = data.audio_url || data.audioUrl || data.url || "";
        } else {
          url = URL.createObjectURL(await response.blob());
        }
        if (!url) return;
        const audio = new Audio(url);
        state.narrationAudio = audio;
        audio.play().catch(function () {});
      }).catch(function () {});
    } catch (_) {
      /* Voice is optional; captions and the board still work. */
    }
  }

  function startLessonIntro() {
    if (state.introduced || state.aiBusy || state.teaching === "stopped") return;
    state.introduced = true;
    setTeachingState("teaching");
    setCaption("CRARA is introducing Hypothesis Testing…", "CRARA");
    return respondToQuestion({
      id: uid("intro"),
      body: "Introduce the Hypothesis Testing lesson. Explain the null and alternative hypotheses, the significance level, the test statistic, the p-value and the decision rule. Write the decision flow and render the z-test equation on the board while you speak.",
      from: "CRARA",
      mine: true,
      intro: true
    });
  }

  async function respondToQuestion(question) {
    if (state.aiBusy) return;
    state.aiBusy = true;
    let finalCaption = "";
    let teachingToken = null;
    if (question && question.intro) {
      setTeachingState("teaching");
      setCaption("CRARA is introducing Hypothesis Testing…", "CRARA");
    } else {
      pauseAudio();
      setTeachingState("listening");
      setCaption("CRARA is preparing an answer and board illustration…", "CRARA");
    }
    try {
      const payload = await postJson(API.instructions, {
        key: state.sessionKey,
        lesson: state.lesson,
        prompt: cleanText(question.body, 600),
        from: cleanText(question.from, 80) || "Student",
        mode: state.chatMode,
        pages: state.pages.length,
        ids: currentPage().objects.map(function (object) { return object.id; })
      });
      if (payload.control && payload.control.type === "teaching") {
        teachingToken = cleanText(payload.control.token, 2000);
        publish("teaching", {
          value: cleanText(payload.control.value && payload.control.value.value, 24),
          authority: teachingToken
        });
      }
      setTeachingState("answering");
      const narration = cleanText(payload.narration, 1200);
      finalCaption = cleanText(payload.caption || narration, 300) || "Answer ready.";
      setCaption(finalCaption, "CRARA");
      if (payload.speak !== false && state.chatMode !== "Chat-only" && narration) speakNarration(narration);
      const instructions = state.chatMode === "Chat-only" ? [] : payload.instructions;
      const results = await runInstructions(instructions, finalCaption);
      const failed = results.filter(function (result) { return !result.ok; }).length;
      finalCaption = finalCaption + (failed ? " · " + failed + " board step" + (failed === 1 ? "" : "s") + " skipped" : "");
      setCaption(finalCaption, "CRARA");
      publish("answer", { question: cleanText(question.body, 600), caption: finalCaption, narration: narration, results: results });
    } catch (_) {
      finalCaption = "CRARA could not reach the lesson service. The classroom remains available.";
      setCaption(finalCaption, "CRARA");
    } finally {
      state.aiBusy = false;
      resumeLesson(finalCaption, teachingToken);
    }
  }

  async function saveServer() {
    if (!isHost()) return announce("Only the host can save the room session.");
    try {
      const data = await postJson(API.session, {
        key: state.sessionKey,
        room: state.sessionKey,
        lesson: state.lesson,
        pages: state.pages,
        pageIndex: state.pageIndex,
        chatMode: state.chatMode,
        permissions: state.permissions
      });
      announce("Session saved to the CRARA library.");
      publish("session", { key: state.sessionKey, savedAt: data.savedAt || Date.now() });
    } catch (_) {
      announce("The session could not be saved. The local copy is still available.");
    }
  }

  async function restoreServer() {
    if (!isHost()) return announce("Only the host can restore the room session.");
    try {
      const data = await getJson(API.session + "?key=" + encodeURIComponent(state.sessionKey));
      const saved = data.session;
      if (!saved) return announce("No saved session was found for this room.");
      state.pages = cleanPages(saved.pages);
      state.pageIndex = clamp(saved.pageIndex, 0, state.pages.length - 1, 0);
      if (CHAT_MODES.indexOf(saved.chatMode) >= 0) state.chatMode = saved.chatMode;
      setPermissions(saved.permissions || {});
      state.undo.length = 0;
      state.redo.length = 0;
      persist();
      refreshRoleState();
      render();
      publishState();
      announce("Saved CRARA session restored.");
    } catch (_) {
      announce("The saved session could not be restored.");
    }
  }

  async function hostAction(action) {
    if (!isHost()) return announce("Host controls are available to the classroom host.");
    if (action === "pause") {
      if (state.narrationAudio) state.narrationAudio.pause();
      await hostSetTeaching("paused");
      setCaption("CRARA lesson paused by the host.", "CRARA");
    } else if (action === "resume") {
      await hostSetTeaching("teaching");
      resumeLesson("CRARA lesson resumed by the host.");
    } else if (action === "stop") {
      if (state.narrationAudio) state.narrationAudio.pause();
      await hostSetTeaching("stopped");
      setCaption("CRARA lesson stopped by the host.", "CRARA");
    } else if (action === "take") {
      const value = await hostSetPermissions({ boardOwner: state.actor, boardLocked: false });
      if (value) announce("You now control the board.");
    } else if (action === "lock" || action === "unlock") {
      const value = await hostSetPermissions({ boardLocked: action === "lock" });
      if (value) announce(action === "lock" ? "Board locked for students." : "Board unlocked.");
    } else if (action === "enable" || action === "disable") {
      const value = await hostSetPermissions({ canWrite: action === "enable" });
      if (value) announce(action === "enable" ? "Student writing enabled." : "Student writing disabled.");
    } else if (action === "grant" || action === "revoke") {
      const identity = window.prompt("Participant name or identity:");
      if (!identity || !identity.trim()) return;
      const name = cleanText(identity, 160);
      const granted = state.permissions.granted.slice();
      const index = granted.indexOf(name);
      if (action === "grant" && index < 0) granted.push(name);
      if (action === "revoke" && index >= 0) granted.splice(index, 1);
      const value = await hostSetPermissions({ granted: granted });
      if (value) announce(action === "grant" ? "Permission granted." : "Permission revoked.");
    } else if (action === "server-save") {
      await saveServer();
    } else if (action === "server-restore") {
      await restoreServer();
    }
  }

  function onMedia(media) {
    const mic = media && media.mic ? media.mic : {};
    const active = mic.status === "active" && mic.enabled !== false;
    if (active && state.teaching === "teaching" && !state.interrupted) {
      state.interrupted = true;
      interruptLesson("Microphone opened — CRARA is listening.");
      publish("interrupt", { reason: "microphone" });
      return;
    }
    if (!active && state.interrupted) {
      state.interrupted = false;
      respondToQuestion({
        id: uid("voice"),
        body: "The student interrupted the lesson with the microphone. Ask what they need about Hypothesis Testing, answer it, then resume the lesson.",
        from: "Student",
        mine: false
      });
    }
  }

  function setCaption(text, from) {
    const value = cleanText(text, 300);
    if (!captionEl) return;
    captionEl.textContent = from ? from + ": " + value : value;
  }

  function setTeachingState(value) {
    const clean = cleanText(value, 24) || "idle";
    state.teaching = TEACHING.indexOf(clean) >= 0 ? clean : "idle";
    if (statusEl) {
      statusEl.textContent = connected()
        ? "Live · " + state.teaching
        : "Local · " + state.teaching;
    }
  }

  function pauseAudio() {
    if (state.narrationAudio) {
      state.narrationAudio.pause();
      state.narrationAudio = null;
    }
  }

  function interruptLesson(reason) {
    pauseAudio();
    setTeachingState("listening");
    setCaption(cleanText(reason, 300) || "Question received — pausing the lesson.", "CRARA");
  }

  function resumeLesson(caption, authority) {
    if (state.teaching === "stopped") return;
    setTeachingState("teaching");
    if (caption) setCaption(caption, "CRARA");
    publish("teaching", { value: "teaching", authority: authority || "" });
  }

  function openBoard() {
    if (!root) buildUI();
    open = true;
    root.hidden = false;
    document.body.classList.add("crara-whiteboard-open");
    if (!session && window.__craraWhiteboardSession) setSession(window.__craraWhiteboardSession);
    applyView();
    dispatchState();
    startLessonIntro();
  }

  function closeBoard() {
    open = false;
    if (root) root.hidden = true;
    document.body.classList.remove("crara-whiteboard-open");
    dispatchState();
  }

  function toggleBoard() {
    if (open) closeBoard();
    else openBoard();
    return open;
  }

  window.__craraWhiteboard = {
    toggle: toggleBoard,
    open: openBoard,
    close: closeBoard,
    onRemote: onRemote,
    onChat: onChat,
    onMedia: onMedia,
    executeInstruction: executeInstruction,
    getState: function () {
      return JSON.parse(JSON.stringify({
        pages: state.pages,
        pageIndex: state.pageIndex,
        teaching: state.teaching,
        role: state.role,
        chatMode: state.chatMode,
        permissions: state.permissions,
        questionQueue: state.questionQueue,
        aiBusy: state.aiBusy,
        introduced: state.introduced,
        sessionKey: state.sessionKey
      }));
    },
    setCaption: setCaption,
    setTeachingState: setTeachingState,
    setRole: setRole,
    setPermissions: setPermissions,
    setChatMode: setChatMode,
    hostSetMode: hostSetMode,
    hostSetTeaching: hostSetTeaching,
    hostSetPermissions: hostSetPermissions,
    askQuestion: askQuestion,
    startLessonIntro: startLessonIntro,
    respondToQuestion: respondToQuestion,
    interruptLesson: interruptLesson,
    resumeLesson: resumeLesson,
    saveServer: saveServer,
    restoreServer: restoreServer,
    hostAction: hostAction,
    restore: restore
  };

  window.addEventListener("crara-whiteboard-session", function (event) {
    setSession(event.detail);
    applyServerRole();
  });

  function applyServerRole() {
    if (window.__craraClassroomRole) setRole(window.__craraClassroomRole);
    if (window.__craraClassroomPermissions) setPermissions(window.__craraClassroomPermissions);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () {
    applyServerRole();
    if (window.__craraWhiteboardSession) setSession(window.__craraWhiteboardSession);
  });
  else {
    applyServerRole();
    if (window.__craraWhiteboardSession) setSession(window.__craraWhiteboardSession);
  }
})();
