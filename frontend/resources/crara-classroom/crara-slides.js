/* Native CRARA slide navigation, panel and full-view controls.
 * This enhances the existing LiveKit slide channel; it does not create a
 * second presenter, room, data channel or presentation application. */
(() => {
  "use strict";

  const RENDER_URL = "/api/class-rep/slides/render";
  const ACTIVE_CLASS = "cr-slides-active";
  const COLLAPSED_CLASS = "cr-slides-collapsed";
  const FULL_CLASS = "crara-slide-fullview";
  const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
  const DOCUMENT_TYPES = new Set([
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ]);

  let panel = null;
  let list = null;
  let countLabel = null;
  let titleLabel = null;
  let statusLabel = null;
  let expandButton = null;
  let reopenButton = null;
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
    if (!statusLabel) return;
    statusLabel.textContent = message || "";
    statusLabel.classList.toggle("error", Boolean(isError));
    statusLabel.hidden = !message;
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

  function update() {
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

    const bridge = window.__craraSlides || {};
    const deck = bridge.deck || null;
    const active = Boolean(deck && deck.count > 0);

    host.classList.toggle(ACTIVE_CLASS, active);
    if (panel) panel.hidden = !active;
    if (expandButton) expandButton.hidden = !active;
    if (reopenButton) {
      reopenButton.hidden = !active || !host.classList.contains(COLLAPSED_CLASS);
    }
    if (!active) {
      if (list) list.replaceChildren();
      if (countLabel) countLabel.textContent = "";
      if (titleLabel) titleLabel.textContent = "Presentation";
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
    if (statusLabel && !statusLabel.classList.contains("error")) setStatus("");
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
        if (body && body.detail) detail = String(body.detail);
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
    }, { once: true });
  } else {
    startObserver();
    update();
  }
  window.setInterval(update, 400);
})();
