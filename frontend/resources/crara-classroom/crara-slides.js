/* Native CRARA slide navigation, panel and full-view controls.
 * This enhances the existing LiveKit slide channel; it does not create a
 * second presenter, room, data channel or presentation application. */
(() => {
  "use strict";

  const RENDER_URL = "/api/class-rep/slides/render";
  const RESOURCES_URL = "/resources/crara-classroom/crara-resources.json";
  const ACTIVE_CLASS = "cr-slides-active";
  const COLLAPSED_CLASS = "cr-slides-collapsed";
  const FULL_CLASS = "crara-slide-fullview";
  const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
  const DOCUMENT_TYPES = new Set([
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ]);
  const FILE_ACCEPT = "application/pdf,.pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,.pptx,image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp";
  const CRARA_SOURCE = "crara";
  const CRARA_DECK_TITLES = new Set([
    "Antimicrobial Resistance in Maternal and Neonatal Health in Malawi",
  ]);

  let panel = null;
  let list = null;
  let countLabel = null;
  let titleLabel = null;
  let statusLabel = null;
  let expandButton = null;
  let reopenButton = null;
  let importButton = null;
  let importStatus = null;
  let filesPanel = null;
  let filesInput = null;
  let filesStatus = null;
  let filesList = null;
  let resources = [];
  let resourcesList = null;
  let resourcePreview = null;
  let sharedResourceId = "";
  let filesSignature = "";
  let presenter = null;
  let lastSignature = "";
  let observer = null;

  function isDocument(file) {
    const type = String(file.type || "").toLowerCase();
    const name = String(file.name || "").toLowerCase();
    return DOCUMENT_TYPES.has(type) || name.endsWith(".pdf") || name.endsWith(".pptx");
  }

  function isImage(file) {
    const type = String(file.type || "").toLowerCase();
    const name = String(file.name || "").toLowerCase();
    return IMAGE_TYPES.has(type) || /\.(png|jpe?g|webp)$/.test(name);
  }

  function findPresenter() {
    return document.querySelector(".presenter") || null;
  }

  function makeButton(label, className, title) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.setAttribute("aria-label", title || label);
    button.title = title || label;
    return button;
  }

  function ensureImportControls() {
    const bar = document.querySelector(".controls");
    if (bar) {
      let button = bar.querySelector(".cr-slide-import");
      if (!button) {
        button = makeButton("▤", "cr-slide-import", "Present slides");
        const label = document.createElement("small");
        label.textContent = "Present slides";
        button.append(label);
        button.addEventListener("click", () => {
          const input = document.querySelector(".stagefile");
          if (!input) {
            setStatus("Stop the current presentation or screen share before loading slides.", true);
            return;
          }
          input.click();
        });
        bar.appendChild(button);
      }
      importButton = button;
    }

    if (importStatus && importStatus.isConnected) return;
    importStatus = document.createElement("p");
    importStatus.className = "cr-slide-status cr-slide-import-status";
    importStatus.setAttribute("role", "status");
    importStatus.setAttribute("aria-live", "polite");
    importStatus.hidden = true;
    document.body.appendChild(importStatus);
  }

  function setFilesStatus(message, isError) {
    if (!filesStatus || !filesStatus.isConnected) return;
    filesStatus.textContent = message || "";
    filesStatus.classList.toggle("error", Boolean(isError));
    filesStatus.hidden = !message;
  }

  function submitDeviceFiles(selected) {
    sharedResourceId = "";
    window.__craraSlideShare = null;
    const files = selected.filter((file) => isDocument(file) || isImage(file));
    if (!files.length) {
      setStatus("Use a PDF, PowerPoint (.pptx) or PNG/JPEG/WebP slide image.", true);
      return;
    }
    const input = document.querySelector(".stagefile");
    if (!input) {
      setStatus("Stop the current presentation or screen share before adding files.", true);
      return;
    }
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "files").set;
    setter.call(input, transfer.files);
    input.dispatchEvent(new Event("change", { bubbles: true }));
    const documents = files.filter(isDocument);
    if (documents.length) {
      setStatus(`Preparing ${documents.length} file${documents.length === 1 ? "" : "s"} from your device…`, false);
    }
  }

  function makeLink(label, href, className, title) {
    const link = document.createElement("a");
    link.className = className;
    link.textContent = label;
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("aria-label", title || label);
    link.title = title || label;
    return link;
  }

  function renderResourceList() {
    if (!resourcesList) return;
    if (!resources.length) {
      resourcesList.textContent = "Loading CRARA resources…";
      return;
    }
    const cards = resources.map((resource) => {
      const card = document.createElement("article");
      card.className = "cr-resource-card";

      const head = document.createElement("div");
      head.className = "cr-resource-head";
      const title = document.createElement("strong");
      title.textContent = resource.title || "CRARA resource";
      const badge = document.createElement("span");
      badge.className = "cr-resource-badge";
      badge.textContent = resource.category || "CRARA resource";
      head.append(title, badge);

      const summary = document.createElement("p");
      summary.className = "cr-resource-summary";
      summary.textContent = resource.summary || "";

      const actions = document.createElement("div");
      actions.className = "cr-resource-actions";
      if (resource.kind === "link" && resource.url) {
        actions.appendChild(makeLink(
          "Open resource", resource.url, "cr-resource-action",
          "Open " + (resource.title || "this resource")
        ));
      } else {
        const action = makeButton(
          resource.kind === "deck" ? "Share in room" : "View chapters",
          "cr-resource-action",
          resource.kind === "deck"
            ? "Share this CRARA resource with everyone in the room"
            : "Show the CRARA chapter outlines"
        );
        action.addEventListener("click", () => {
          if (resource.kind === "deck") void shareResourceDeck(resource);
          else showChapterPreview(resource);
        });
        actions.appendChild(action);
      }
      if (resource.downloadUrl) {
        actions.appendChild(makeLink(
          "Original file", resource.downloadUrl, "cr-resource-download",
          "Download the original " + (resource.downloadName || "file")
        ));
      }

      card.append(head, summary, actions);
      return card;
    });
    resourcesList.replaceChildren(...cards);
  }

  function showChapterPreview(resource) {
    if (!resourcePreview) return;
    const book = resource.book || {};
    const chapters = Array.isArray(book.chapters) ? book.chapters : [];
    resourcePreview.hidden = false;

    const heading = document.createElement("h4");
    heading.textContent = book.title || resource.title || "Chapter outlines";

    const honesty = document.createElement("p");
    honesty.className = "cr-resource-honesty";
    honesty.textContent = book.accessNoteEn || "CRARA uses bundled chapter outlines, not licensed chapter text.";

    const list = document.createElement("div");
    list.className = "cr-chapter-list";
    chapters.forEach((chapter) => {
      const item = document.createElement("article");
      item.className = "cr-chapter";
      const title = document.createElement("strong");
      title.textContent = `Chapter ${chapter.number} — ${chapter.title}`;
      const meta = document.createElement("span");
      meta.textContent = chapter.pages ? `pp. ${chapter.pages}` : "";
      const english = document.createElement("p");
      english.textContent = chapter.scopeEn || "";
      const chichewa = document.createElement("p");
      chichewa.className = "cr-chapter-ny";
      chichewa.textContent = chapter.scopeNy || "";
      const ask = makeButton(
        "Ask CRARA", "cr-resource-ask",
        `Ask CRARA about chapter ${chapter.number}`
      );
      ask.addEventListener("click", () => askCraraAboutChapter(book, chapter));
      const head = document.createElement("div");
      head.className = "cr-chapter-head";
      head.append(title, meta);
      item.append(head, english, chichewa, ask);
      list.appendChild(item);
    });

    const links = document.createElement("div");
    links.className = "cr-resource-preview-links";
    if (book.url) {
      links.appendChild(makeLink(
        "Publisher reference", book.url, "cr-resource-download",
        "Open the publisher reference for this book"
      ));
    }
    const close = makeButton("Close outlines", "cr-resource-close", "Close chapter outlines");
    close.addEventListener("click", () => {
      resourcePreview.hidden = true;
      resourcePreview.replaceChildren();
    });
    links.appendChild(close);

    resourcePreview.replaceChildren(heading, honesty, list, links);
  }

  function askCraraAboutChapter(book, chapter) {
    const input = document.querySelector('.compose input[aria-label="Message CRARA and the classroom"]')
      || document.querySelector(".compose input");
    if (!input) {
      setFilesStatus("Open the chat panel before asking CRARA about a chapter.", true);
      return;
    }
    input.value = `Read chapter ${chapter.number}, ${chapter.title}, from ${book.title || "the bundled reference"}`;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const chatTab = Array.from(document.querySelectorAll(".tabs button")).find(
      (tab) => String(tab.textContent || "").trim() === "Chat"
    );
    if (chatTab) chatTab.click();
    input.focus();
    setFilesStatus("Question placed in chat. Press Send to ask CRARA.", false);
  }

  async function shareResourceDeck(resource) {
    const input = document.querySelector(".stagefile");
    if (!input) {
      setFilesStatus("Stop the current presentation or screen share before adding files.", true);
      return;
    }
    setFilesStatus(`Sharing ${resource.title} with the room…`, false);
    try {
      const response = await fetch(resource.url, { cache: "no-store" });
      if (!response.ok) throw new Error("The bundled resource could not be opened.");
      const payload = await response.json();
      const entries = Array.isArray(payload.slides) ? payload.slides : [];
      if (!entries.length || entries.length > 60) {
        throw new Error("The bundled presentation has an unsupported slide count.");
      }
      const files = await Promise.all(entries.map(async (entry) => {
        const imageResponse = await fetch(entry.url, { cache: "no-store" });
        if (!imageResponse.ok) throw new Error("A bundled slide could not be read.");
        const blob = await imageResponse.blob();
        return new File([blob], entry.name || "slide.jpg", { type: blob.type || "image/jpeg" });
      }));
      sharedResourceId = resource.id;
      window.__craraSlideShare = {
        source: CRARA_SOURCE,
        id: resource.id,
        title: resource.title,
      };
      feedFiles(input, files);
      setFilesStatus(`Shared ${resource.title} — ${files.length} slides from CRARA resources.`, false);
    } catch (error) {
      setFilesStatus(error instanceof Error ? error.message : "The resource could not be shared.", true);
    }
  }

  async function loadResources() {
    try {
      const response = await fetch(RESOURCES_URL, { cache: "no-store" });
      if (!response.ok) throw new Error("Resources unavailable");
      const payload = await response.json();
      resources = Array.isArray(payload.resources) ? payload.resources : [];
    } catch (_) {
      resources = [];
    }
    renderResourceList();
  }

  function buildFilesPanel() {
    filesPanel = document.createElement("section");
    filesPanel.className = "cr-files-panel";
    filesPanel.setAttribute("aria-label", "Shared files");

    const heading = document.createElement("h3");
    heading.textContent = "Shared files";

    const add = document.createElement("label");
    add.className = "cr-file-add";
    add.textContent = "Add files from device";
    filesInput = document.createElement("input");
    filesInput.type = "file";
    filesInput.className = "cr-file-input";
    filesInput.multiple = true;
    filesInput.accept = FILE_ACCEPT;
    filesInput.setAttribute("aria-label", "Add slide files from your device");
    filesInput.addEventListener("change", () => {
      submitDeviceFiles(Array.from(filesInput.files || []));
      filesInput.value = "";
    });
    add.appendChild(filesInput);

    filesStatus = document.createElement("p");
    filesStatus.className = "cr-files-status cr-slide-status";
    filesStatus.setAttribute("role", "status");
    filesStatus.setAttribute("aria-live", "polite");
    filesStatus.hidden = true;

    const resourcesHeading = document.createElement("h4");
    resourcesHeading.className = "cr-resources-heading";
    resourcesHeading.textContent = "CRARA resources";

    resourcesList = document.createElement("div");
    resourcesList.className = "cr-resource-list";

    resourcePreview = document.createElement("div");
    resourcePreview.className = "cr-resource-preview";
    resourcePreview.hidden = true;

    filesList = document.createElement("div");
    filesList.className = "cr-files-list";

    const note = document.createElement("p");
    note.className = "cr-files-note";
    note.textContent = "Slides added here are shared with CRARA and everyone in this room.";

    filesPanel.append(
      heading, add, filesStatus,
      resourcesHeading, resourcesList, resourcePreview,
      filesList, note
    );
    filesSignature = "";
    renderResourceList();
  }

  function activeTabName() {
    const active = document.querySelector(".tabs button.active");
    return active ? String(active.textContent || "").trim() : "";
  }

  function renderFilesList() {
    if (!filesList) return;
    const bridge = window.__craraSlides || {};
    const deck = bridge.deck || null;
    const active = Boolean(deck && deck.count > 0);
    const pages = active && Array.isArray(deck.pages) ? deck.pages : [];
    const signature = [
      active ? "deck" : "empty",
      active ? deck.deckId || "" : "",
      active ? deck.index : "",
      active ? deck.count : "",
      active ? deck.title || "" : "",
      active ? deck.source || "" : "",
      active ? (deck.isOwner ? "1" : "0") : "",
      active ? deck.ownerName || "" : "",
      active ? sharedResourceId : "",
      pages.map((page) => (page ? String(page).slice(-32) : "")).join("|"),
    ].join("~");
    if (signature === filesSignature) return;
    filesSignature = signature;

    if (!active) {
      const empty = document.createElement("p");
      empty.className = "cr-files-empty";
      empty.textContent = "No files shared yet. Add a PDF, PowerPoint (.pptx) or slide images to share them with CRARA and the room.";
      filesList.replaceChildren(empty);
      return;
    }

    const card = document.createElement("article");
    card.className = "cr-file-card";

    const head = document.createElement("div");
    head.className = "cr-file-head";
    const title = document.createElement("strong");
    title.textContent = deck.title || "Shared presentation";
    const source = document.createElement("span");
    const owner = deck.isOwner ? "You" : String(deck.ownerName || "a participant");
    const byCrara = Boolean(sharedResourceId)
      || deck.source === CRARA_SOURCE
      || /crara/i.test(owner)
      || CRARA_DECK_TITLES.has(deck.title || "");
    source.className = "cr-file-source" + (byCrara ? " crara" : "");
    source.textContent = byCrara ? "Shared by CRARA" : deck.isOwner ? "Shared by you" : "Shared by " + owner;
    head.append(title, source);

    const meta = document.createElement("p");
    meta.className = "cr-file-meta";
    meta.textContent = `${deck.count} slide${deck.count === 1 ? "" : "s"} · slide ${deck.index + 1} of ${deck.count}`;

    const grid = document.createElement("div");
    grid.className = "cr-file-grid";
    pages.slice(0, 24).forEach((page, index) => {
      const button = makeButton("", "cr-file-thumb" + (index === deck.index ? " active" : ""), `Show slide ${index + 1}`);
      button.disabled = deck.isOwner !== true;
      if (page) {
        const image = document.createElement("img");
        image.alt = "";
        image.loading = "lazy";
        image.decoding = "async";
        image.src = page;
        button.appendChild(image);
      }
      const number = document.createElement("span");
      number.textContent = String(index + 1).padStart(2, "0");
      button.appendChild(number);
      button.addEventListener("click", () => {
        if (typeof bridge.goTo === "function") bridge.goTo(index);
      });
      grid.appendChild(button);
    });

    const actions = document.createElement("div");
    actions.className = "cr-file-actions";
    if (deck.isOwner) {
      const show = makeButton("Start from slide 1", "cr-file-action", "Show the first slide in the room");
      show.addEventListener("click", () => {
        if (typeof bridge.goTo === "function") bridge.goTo(0);
      });
      const stop = makeButton("Stop sharing", "cr-file-action danger", "Stop presenting these slides");
      stop.addEventListener("click", () => {
        if (typeof bridge.stopSlides === "function") bridge.stopSlides();
      });
      actions.append(show, stop);
    } else {
      const locked = document.createElement("p");
      locked.className = "cr-file-locked";
      locked.textContent = "Only the presenter can change these slides.";
      actions.appendChild(locked);
    }

    card.append(head, meta, grid, actions);
    filesList.replaceChildren(card);
  }

  function ensureFilesPanel() {
    const right = document.querySelector(".right");
    if (!right) return;
    const isFiles = activeTabName() === "Files";
    right.classList.toggle("cr-files-active", isFiles);
    if (!isFiles) {
      if (filesPanel) filesPanel.hidden = true;
      return;
    }
    if (!filesPanel || filesPanel.parentElement !== right) {
      buildFilesPanel();
      right.appendChild(filesPanel);
    }
    filesPanel.hidden = false;
    renderFilesList();
  }

  function ensurePanel(host) {
    if (panel && panel.isConnected && panel.parentElement === host) return;

    panel = document.createElement("aside");
    panel.className = "cr-slide-panel";
    panel.setAttribute("aria-label", "Slide navigator");

    const head = document.createElement("div");
    head.className = "cr-slide-panel-head";

    const heading = document.createElement("div");
    heading.className = "cr-slide-panel-title";
    titleLabel = document.createElement("strong");
    titleLabel.textContent = "Presentation";
    countLabel = document.createElement("span");
    countLabel.className = "cr-slide-count";
    countLabel.setAttribute("aria-live", "polite");
    heading.append(titleLabel, countLabel);

    const collapse = makeButton("‹", "cr-slide-collapse", "Collapse slide panel");
    collapse.addEventListener("click", () => {
      host.classList.add(COLLAPSED_CLASS);
      update();
    });

    head.append(heading, collapse);

    list = document.createElement("div");
    list.className = "cr-slide-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", "Presentation slides");

    statusLabel = document.createElement("p");
    statusLabel.className = "cr-slide-status";
    statusLabel.setAttribute("role", "status");
    statusLabel.setAttribute("aria-live", "polite");
    statusLabel.hidden = true;

    panel.append(head, list, statusLabel);
    host.insertBefore(panel, host.firstChild);

    const bar = host.querySelector(".stagebarright") || host.querySelector(".presenterbar");
    if (bar) {
      expandButton = makeButton("Expand slides", "cr-slide-expand", "Expand slide presentation");
      expandButton.addEventListener("click", () => {
        setFullView(!document.body.classList.contains(FULL_CLASS));
      });
      bar.appendChild(expandButton);
    }

    reopenButton = makeButton("Slides ›", "cr-slide-reopen", "Reopen slide panel");
    reopenButton.hidden = true;
    reopenButton.addEventListener("click", () => {
      host.classList.remove(COLLAPSED_CLASS);
      update();
    });
    host.appendChild(reopenButton);
  }

  function setStatus(message, isError) {
    for (const node of [statusLabel, importStatus, filesStatus]) {
      if (!node || !node.isConnected) continue;
      node.textContent = message || "";
      node.classList.toggle("error", Boolean(isError));
      node.hidden = !message;
    }
  }

  function thumbnail(pages, index, deck, goTo) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cr-slide-thumb" + (index === deck.index ? " active" : "");
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", index === deck.index ? "true" : "false");
    button.setAttribute("aria-label", `Slide ${index + 1} of ${deck.count}`);
    button.title = deck.isOwner
      ? `Show slide ${index + 1}`
      : "Only the presenter can change slides";
    button.disabled = deck.isOwner !== true;

    const image = document.createElement("img");
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    if (pages[index]) {
      image.src = pages[index];
    } else {
      image.hidden = true;
    }

    const number = document.createElement("span");
    number.textContent = String(index + 1).padStart(2, "0");

    button.append(image, number);
    button.addEventListener("click", () => {
      if (typeof goTo === "function") goTo(index);
    });
    return button;
  }

  let applyingUpdate = false;

  function update() {
    if (applyingUpdate) return;
    applyingUpdate = true;
    try {
      applyUpdate();
    } finally {
      applyingUpdate = false;
    }
  }

  function applyUpdate() {
    ensureImportControls();
    ensureFilesPanel();
    const bridge = window.__craraSlides || {};
    if (importButton) {
      const connected = Boolean(bridge.session && bridge.session.status === "connected");
      importButton.disabled = !connected;
      importButton.title = connected
        ? "Load a PDF, PowerPoint (.pptx) or slide images for everyone"
        : "Join the live classroom before presenting slides";
    }

    const host = findPresenter();
    if (!host) {
      presenter = null;
      lastSignature = "";
      return;
    }
    if (!panel || panel.parentElement !== host) {
      presenter = host;
      ensurePanel(host);
      lastSignature = "";
    }
    presenter = host;

    const deck = bridge.deck || null;
    const active = Boolean(deck && deck.count > 0);

    host.classList.toggle(ACTIVE_CLASS, active);
    if (panel) panel.hidden = !active;
    if (expandButton) expandButton.hidden = !active;
    if (reopenButton) {
      reopenButton.hidden = !active || !host.classList.contains(COLLAPSED_CLASS);
    }
    if (!active) {
      if (list && list.childNodes.length) list.replaceChildren();
      if (countLabel && countLabel.textContent !== "") countLabel.textContent = "";
      if (titleLabel && titleLabel.textContent !== "Presentation") titleLabel.textContent = "Presentation";
      lastSignature = "";
      return;
    }

    const pages = Array.isArray(deck.pages) ? deck.pages : [];
    const signature = [
      deck.deckId || "",
      deck.index,
      deck.count,
      deck.title || "",
      deck.isOwner ? "1" : "0",
      pages.map((page) => (page ? String(page).slice(-32) : "")).join("|"),
    ].join("~");
    if (signature === lastSignature) return;
    lastSignature = signature;

    if (titleLabel) titleLabel.textContent = deck.title || "Presentation";
    if (countLabel) countLabel.textContent = `${deck.index + 1} / ${deck.count}`;
    if (list) {
      const buttons = [];
      for (let index = 0; index < deck.count; index += 1) {
        buttons.push(thumbnail(pages, index, deck, bridge.goTo));
      }
      list.replaceChildren(...buttons);
      const current = list.children[deck.index];
      if (current && typeof current.scrollIntoView === "function") {
        current.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    }
    for (const node of [statusLabel, importStatus]) {
      if (node && !node.classList.contains("error")) {
        node.textContent = "";
        node.hidden = true;
      }
    }
  }

  function setFullView(on) {
    document.body.classList.toggle(FULL_CLASS, Boolean(on));
    if (expandButton) {
      expandButton.textContent = on ? "Restore classroom" : "Expand slides";
      expandButton.setAttribute("aria-label", on ? "Restore classroom layout" : "Expand slide presentation");
      expandButton.title = on ? "Restore classroom layout" : "Expand slide presentation";
    }
    if (on && presenter && presenter.requestFullscreen && !document.fullscreenElement) {
      const request = presenter.requestFullscreen();
      if (request && typeof request.catch === "function") request.catch(() => {});
    }
    if (!on && document.fullscreenElement && document.exitFullscreen) {
      const exit = document.exitFullscreen();
      if (exit && typeof exit.catch === "function") exit.catch(() => {});
    }
    window.setTimeout(update, 0);
  }

  async function dataUrlToFile(dataUrl, name) {
    const response = await fetch(dataUrl);
    if (!response.ok) throw new Error("The rendered slide could not be read.");
    const blob = await response.blob();
    return new File([blob], name, { type: "image/jpeg" });
  }

  async function renderDocument(file) {
    const form = new FormData();
    form.append("file", file, file.name);
    const response = await fetch(RENDER_URL, { method: "POST", body: form });
    if (response.status === 401) {
      throw new Error("Open CRARA before presenting slides.");
    }
    if (!response.ok) {
      let detail = `The presentation could not be prepared (HTTP ${response.status}).`;
      try {
        const body = await response.json();
        if (body && (body.detail || body.error)) detail = String(body.detail || body.error);
      } catch (_) {}
      throw new Error(detail);
    }
    const body = await response.json();
    if (!body || !Array.isArray(body.slides) || body.slides.length === 0) {
      throw new Error("No slides were found in that presentation.");
    }
    const files = [];
    for (const slide of body.slides) {
      files.push(await dataUrlToFile(slide.dataUrl, slide.name || "slide.jpg"));
    }
    return files;
  }

  function feedFiles(input, files) {
    if (!files.length) return;
    const transfer = new DataTransfer();
    files.forEach((file) => transfer.items.add(file));
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "files").set;
    setter.call(input, transfer.files);
    input.dataset.craraFeed = "1";
    input.dispatchEvent(new Event("change", { bubbles: true }));
    window.setTimeout(() => {
      delete input.dataset.craraFeed;
      try { input.value = ""; } catch (_) {}
    }, 0);
  }

  async function handleFileChange(event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("stagefile")) return;
    if (input.dataset.craraFeed === "1") return;
    sharedResourceId = "";
    window.__craraSlideShare = null;

    const selected = Array.from(input.files || []);
    if (!selected.length) return;
    const documents = selected.filter(isDocument);
    if (!documents.length) {
      if (selected.some((file) => !isImage(file))) {
        event.preventDefault();
        event.stopImmediatePropagation();
        input.value = "";
        setStatus("Use a PDF, PowerPoint (.pptx) or PNG/JPEG/WebP slide image.", true);
      }
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    input.value = "";
    setStatus(`Preparing ${documents.length} presentation file${documents.length === 1 ? "" : "s"}…`, false);

    const converted = [];
    const failures = [];
    for (const file of selected) {
      if (!isDocument(file)) {
        converted.push(file);
        continue;
      }
      try {
        const pages = await renderDocument(file);
        converted.push(...pages);
      } catch (error) {
        failures.push(`${file.name}: ${error instanceof Error ? error.message : "processing failed"}`);
      }
    }

    if (!converted.length) {
      setStatus(failures.join(" ") || "The presentation could not be prepared.", true);
      return;
    }
    if (failures.length) {
      setStatus(`Some files were skipped. ${failures.join(" ")}`, true);
    } else {
      setStatus(`Prepared ${converted.length} slides for the room.`, false);
    }
    feedFiles(input, converted);
  }

  function startObserver() {
    if (observer) return;
    observer = new MutationObserver(() => {
      update();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  document.addEventListener("change", handleFileChange, true);
  document.addEventListener("click", (event) => {
    const tab = event.target && event.target.closest ? event.target.closest(".tabs button") : null;
    if (tab && String(tab.textContent || "").trim() === "Files") window.setTimeout(update, 0);
  }, true);
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement) {
      document.body.classList.remove(FULL_CLASS);
      if (expandButton) {
        expandButton.textContent = "Expand slides";
        expandButton.setAttribute("aria-label", "Expand slide presentation");
        expandButton.title = "Expand slide presentation";
      }
      update();
    }
  });
  window.addEventListener("crara-whiteboard-session", update);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      startObserver();
      update();
      void loadResources();
    }, { once: true });
  } else {
    startObserver();
    update();
    void loadResources();
  }
  window.setInterval(update, 400);
})();
