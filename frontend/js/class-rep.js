(function () {
  "use strict";
  const root = document.getElementById("class-rep-assistant");
  if (!root || root.dataset.ready === "1") return;
  root.dataset.ready = "1";

  const state = { history: [], busy: false, ready: false, recording: false, recorder: null, audioParts: [], documentToken: "", analyticsPassword: "", previousBodyOverflow: "", user: null, conversationId: null };
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const launcher = el("button", "cara-launcher", "CRARA");
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open CRARA, your intelligent academic relations assistant");
  launcher.setAttribute("aria-expanded", "false");
  const header = el("div", "cr-head");
  const brand = el("div", "cr-brand");
  const brandMark = el("span", "cr-brand-mark");
  brandMark.setAttribute("aria-hidden", "true");
  brandMark.innerHTML = '<svg viewBox="0 0 64 64" width="54" height="54" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 23 32 10l27 13-27 13L5 23Z" fill="currentColor"/><path d="m15 29 17 8 17-8v11c-9 8-25 8-34 0V29Z" fill="currentColor" opacity=".88"/><path d="M58 24v16" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="58" cy="43" r="3" fill="currentColor"/></svg>';
  const identity = el("div", "cr-identity");
  identity.append(el("strong", "cr-title", "Class Rep & Academic Relations Assistant"));
  identity.append(el("span", "cr-subtitle", "Your intelligent academic relations assistant"));
  brand.append(brandMark, identity);
  const homeBack = el("button", "cr-home-back");
  homeBack.type = "button";
  homeBack.setAttribute("aria-label", "Back to Home — Weekly Timetable");
  homeBack.title = "Back to Home";
  homeBack.innerHTML = '<svg viewBox="0 0 24 24" width="21" height="21" aria-hidden="true"><path d="M14.5 5 7.5 12l7 7M8 12h11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Back to Home</span>';
  homeBack.addEventListener("click", () => {
    setOpen(false);
    const homeNav = document.querySelector('#view-tabs .weekly-date-tab, .menu-nav[data-view="weekly"], .hd-tab[data-view="weekly"]');
    if (homeNav) homeNav.click();
  });
  header.append(brand, homeBack);
  const body = el("div", "cr-body");
  const transcript = el("div", "cr-transcript");
  transcript.setAttribute("role", "log"); transcript.setAttribute("aria-live", "polite"); transcript.setAttribute("aria-label", "Assistant conversation");
  const form = el("form", "cr-form");
  const attachButton = el("button", "cr-icon-button cr-attach"); attachButton.type = "button"; attachButton.setAttribute("aria-label", "Attach a file"); attachButton.title = "Attach file";
  const paperclip = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  paperclip.setAttribute("viewBox", "0 0 24 24"); paperclip.setAttribute("width", "22"); paperclip.setAttribute("height", "22"); paperclip.setAttribute("fill", "none"); paperclip.setAttribute("stroke", "currentColor"); paperclip.setAttribute("stroke-width", "2"); paperclip.setAttribute("stroke-linecap", "round"); paperclip.setAttribute("stroke-linejoin", "round"); paperclip.setAttribute("aria-hidden", "true");
  const paperclipPath = document.createElementNS("http://www.w3.org/2000/svg", "path"); paperclipPath.setAttribute("d", "m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.2-9.19a4 4 0 0 1 5.65 5.66l-9.2 9.19a2 2 0 0 1-2.82-2.83l8.49-8.48"); paperclip.append(paperclipPath); attachButton.append(paperclip);
  const input = el("textarea", "cr-input"); input.rows = 1; input.maxLength = 4000; input.placeholder = "Message CRARA…"; input.setAttribute("aria-label", "Message CRARA");
  const recordButton = el("button", "cr-icon-button cr-record"); recordButton.type = "button"; recordButton.setAttribute("aria-label", "Record a voice question"); recordButton.title = "Voice input";
  const micIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  micIcon.setAttribute("viewBox", "0 0 24 24"); micIcon.setAttribute("width", "22"); micIcon.setAttribute("height", "22"); micIcon.setAttribute("fill", "none"); micIcon.setAttribute("stroke", "currentColor"); micIcon.setAttribute("stroke-width", "2"); micIcon.setAttribute("stroke-linecap", "round"); micIcon.setAttribute("stroke-linejoin", "round"); micIcon.setAttribute("aria-hidden", "true");
  const micBody = document.createElementNS("http://www.w3.org/2000/svg", "rect"); micBody.setAttribute("x", "9"); micBody.setAttribute("y", "2"); micBody.setAttribute("width", "6"); micBody.setAttribute("height", "12"); micBody.setAttribute("rx", "3");
  const micStand = document.createElementNS("http://www.w3.org/2000/svg", "path"); micStand.setAttribute("d", "M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8");
  micIcon.append(micBody, micStand); recordButton.append(micIcon);
  const sendButton = el("button", "cr-icon-button cr-send", "➤"); sendButton.type = "submit"; sendButton.setAttribute("aria-label", "Send message"); sendButton.title = "Send message"; sendButton.hidden = true;
  function updateComposerAction() { const hasText = Boolean(input.value.trim()); recordButton.hidden = hasText; sendButton.hidden = !hasText; }
  const fileInput = el("input", "cr-file-input"); fileInput.type = "file"; fileInput.hidden = false; fileInput.tabIndex = -1; fileInput.setAttribute("aria-hidden", "true"); fileInput.style.cssText = "display:block;position:fixed;left:-10000px;top:0;width:1px;height:1px;opacity:0;";
  fileInput.accept = ".pdf,.docx,.pptx,.xlsx,.csv,.svg,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,image/svg+xml,image/png,image/jpeg,image/tiff,image/bmp,image/webp,text/plain"; fileInput.hidden = true;
  const statusNode = el("span", "cr-status"); statusNode.hidden = true; statusNode.setAttribute("aria-live", "polite");
  form.append(attachButton, input, recordButton, sendButton); body.append(transcript, form, fileInput, statusNode);
  const authPanel = el("section", "cr-auth-panel");
  const authCard = el("div", "cr-auth-card");
  const authTitle = el("strong", "cr-auth-title", "Your private CRARA account");
  const authIntro = el("p", "cr-auth-intro", "Sign in to continue your conversations and access your saved academic work.");
  const authName = el("input", "cr-auth-input"); authName.placeholder = "Your name"; authName.autocomplete = "name"; authName.hidden = true;
  const authEmail = el("input", "cr-auth-input"); authEmail.type = "email"; authEmail.placeholder = "Email address"; authEmail.autocomplete = "email";
  const authPassword = el("input", "cr-auth-input"); authPassword.type = "password"; authPassword.minLength = 4; authPassword.maxLength = 256; authPassword.placeholder = "Password (at least 4 characters)"; authPassword.autocomplete = "current-password";
  const authSubmit = el("button", "cr-auth-submit", "Sign in"); authSubmit.type = "button";
  const authSwitch = el("button", "cr-auth-switch", "Create a new account"); authSwitch.type = "button";
  const authFeedback = el("p", "cr-auth-feedback", "");
  authCard.append(authTitle, authIntro, authName, authEmail, authPassword, authSubmit, authSwitch, authFeedback);
  authPanel.append(authCard);
  root.append(body, authPanel);
  const landingNav = document.getElementById("view-tabs");
  if (landingNav) landingNav.appendChild(launcher);
  let landingVisible = true;
  let schedulingVisible = false;
  function updateLauncherVisibility() {
    launcher.hidden = root.classList.contains("is-open") || !landingVisible || schedulingVisible;
  }
  window.setCRARALandingVisible = (visible) => {
    landingVisible = Boolean(visible);
    if (!landingVisible && root.classList.contains("is-open")) setOpen(false);
    updateLauncherVisibility();
  };
  window.setCRARASchedulingVisible = (visible) => {
    schedulingVisible = Boolean(visible);
    updateLauncherVisibility();
  };
  updateLauncherVisibility();
  // Do not mount the assistant hero at all until authentication succeeds.
  function showHeader(visible) {
    if (visible) {
      if (!header.isConnected) root.insertBefore(header, body);
      header.hidden = false;
    } else {
      header.hidden = true;
      header.remove();
    }
  }
  root.classList.remove("class-rep-assistant");
  root.classList.add("cara-widget");
  root.classList.remove("is-open");
  showHeader(false);
  body.hidden = true;
  authPanel.hidden = true;
  function setAuthPresentation(active) {
    const enabled = Boolean(active);
    document.documentElement.classList.toggle("cara-auth-open", enabled);
    document.body.classList.toggle("cara-auth-open", enabled);
  }
  function status(text, ready) {
    const node = statusNode;
    node.textContent = text;
    node.dataset.state = ready ? "ready" : "unavailable";
  }
  async function requestJson(path, options = {}) {
    let response;
    try {
      response = await fetch(path, {
        ...options,
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json", ...(options.headers || {}) }
      });
    } catch (_) {
      throw new Error("Could not connect to CRARA services. Check your internet connection and try again.");
    }
    const raw = await response.text();
    let result = {};
    if (raw) {
      try { result = JSON.parse(raw); }
      catch (_) {
        if (response.ok) throw new Error("CRARA returned an unreadable response. Please refresh and try again.");
      }
    }
    return { response, result };
  }

  function renderInline(parent, value) {
    const pattern = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g;
    let cursor = 0;
    for (const match of value.matchAll(pattern)) {
      if (match.index > cursor) parent.append(document.createTextNode(value.slice(cursor, match.index)));
      const token = match[0];
      const node = document.createElement(token.startsWith("**") ? "strong" : "em");
      node.textContent = token.startsWith("**") ? token.slice(2, -2) : token.slice(1, -1);
      parent.append(node);
      cursor = match.index + token.length;
    }
    if (cursor < value.length) parent.append(document.createTextNode(value.slice(cursor)));
  }
  function renderMarkdown(bubble, value) {
    if (window.CRARAResponseRenderer) {
      window.CRARAResponseRenderer.render(bubble, value, transcript);
      return;
    }
    bubble.replaceChildren();
    const lines = String(value || "").replace(/\r/g, "").replace(/\\([*_.#>-])/g, "$1").split("\n");
    let paragraph = [];
    let list = null;
    let listType = "";
    const flushParagraph = () => {
      if (!paragraph.length) return;
      const p = document.createElement("p");
      renderInline(p, paragraph.join(" "));
      bubble.append(p);
      paragraph = [];
    };
    const closeList = () => { list = null; listType = ""; };
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) { flushParagraph(); closeList(); continue; }
      const heading = /^(#{1,3})\s+(.+)$/.exec(line);
      const bullet = /^(?:[-•]|\*)\s+(.+)$/.exec(line);
      const numbered = /^\d+[.)]\s+(.+)$/.exec(line);
      if (heading) {
        flushParagraph(); closeList();
        const h = document.createElement(heading[1].length === 1 ? "h3" : "h4");
        renderInline(h, heading[2]); bubble.append(h);
      } else if (bullet || numbered) {
        flushParagraph();
        const type = bullet ? "ul" : "ol";
        if (!list || listType !== type) {
          closeList(); list = document.createElement(type); listType = type; bubble.append(list);
        }
        const item = document.createElement("li");
        renderInline(item, (bullet || numbered)[1]); list.append(item);
      } else if (/^>\s?/.test(line)) {
        flushParagraph(); closeList();
        const quote = document.createElement("blockquote");
        renderInline(quote, line.replace(/^>\s?/, "")); bubble.append(quote);
      } else {
        closeList(); paragraph.push(line);
      }
    }
    flushParagraph();
    transcript.scrollTop = transcript.scrollHeight;
  }
  function addMessage(role, text) {
    const bubble = el("div", "cr-message " + (role === "user" ? "cr-user" : "cr-assistant"));
    if (role === "assistant") renderMarkdown(bubble, text);
    else bubble.textContent = text;
    transcript.append(bubble); transcript.scrollTop = transcript.scrollHeight; return bubble;
  }
  async function typeReply(bubble, value) {
    const answer = String(value || "");
    bubble.classList.remove("cr-thinking");
    bubble.removeAttribute("role");
    bubble.removeAttribute("aria-label");
    bubble.textContent = "";
    const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion || window.matchMedia("(max-width: 760px)").matches || answer.length < 90) { renderMarkdown(bubble, answer); return; }
    const step = answer.length > 1400 ? 10 : answer.length > 700 ? 7 : 4;
    for (let index = 0; index < answer.length; index += step) {
      bubble.textContent = answer.slice(0, index + step);
      transcript.scrollTop = transcript.scrollHeight;
      await new Promise(resolve => window.setTimeout(resolve, 16));
    }
    renderMarkdown(bubble, answer);
  }
  function demoReply(message) {
    const q = message.toLowerCase();
    if (/hello|hi|hey/.test(q)) return "Hello! I’m here to support the MNH class representative with clear academic communication. What would you like help with?";
    if (/exam|examination|test|assessment/.test(q)) return "I can help prepare an examination notice. Please confirm the date, time and venue in the Examinations section before sharing.";
    if (/session|timetable|schedule|class|lecture|this week/.test(q)) return "For accurate session dates, times, modules and facilitators, please check the live weekly timetable. I won't guess or invent a session.";
    if (/announcement|announce|remind|broadcast/.test(q)) return "Ready-to-edit announcement:\n\nGood day, everyone. Please refer to the MNH Smart Timetable for the confirmed module, date, time and delivery details. Kindly be punctual and come prepared.\n\nThank you,\nClass Representative";
    if (/lecturer|facilitator|professor|doctor|message|email|whatsapp/.test(q)) return "Good day, [Title and Name]. I hope you are well. I am writing on behalf of the MNH class to kindly seek clarification regarding [specific issue]. Could you please advise us when convenient?\n\nThank you for your time and guidance.\nKind regards,\nClass Representative";
    return "I can help draft class announcements, messages to lecturers, meeting agendas and other academic communications. For confirmed timetable details, please refer to the live shared calendar.";
  }
  async function checkStatus() {
    try {
      const { response, result } = await requestJson("/api/class-rep/status");
      if (!response.ok) throw new Error(result.detail || result.error || `HTTP ${response.status}`);
      state.ready = Boolean(response.ok && result.ready);
      state.voice = result.voice === "enabled";
      state.uploads = result.document_uploads === "enabled";
      status(state.ready ? "AI configured · " + result.provider + (result.connection === "not_tested" ? " · connection not tested" : result.fallbacks?.length ? " · fallbacks ready" : "") : "Built-in fallback · AI not configured", state.ready);
      recordButton.disabled = !state.voice; root.dataset.documentSearch = result.document_search || "unavailable";
    } catch (_) {
      state.ready = false; state.voice = false; state.uploads = false;
      status("Services unavailable", false);
      recordButton.disabled = true;
    }
  }
  let authMode = "login";
  // A temporary network/API failure is not proof that the saved session expired.
  let retrySessionCheck = false;
  let authCheckComplete = false;
  let authCheckRunning = false;
  function setAuthMode(mode) {
    authMode = mode;
    authName.hidden = mode !== "register";
    authPassword.autocomplete = mode === "register" ? "new-password" : "current-password";
    authPassword.minLength = mode === "register" ? 4 : 0;
    authPassword.placeholder = mode === "register" ? "Password (at least 4 characters)" : "Password";
    authSubmit.textContent = mode === "register" ? "Create account" : "Sign in";
    authSwitch.textContent = mode === "register" ? "I already have an account" : "Create a new account";
    authFeedback.textContent = "";
  }
  async function loadPreviousConversation() {
    try {
      const { response, result: data } = await requestJson("/api/class-rep/conversations");
      if (!response.ok) return;
      const latest = (data.conversations || [])[0];
      if (!latest) return;
      state.conversationId = latest.id;
      state.history = (latest.messages || []).slice(-12).map(m => ({ role: m.role, content: m.content }));
      transcript.replaceChildren();
      for (const message of state.history) addMessage(message.role, message.content);
    } catch (_) {}
  }
  async function checkAuth() {
    if (authCheckRunning) return;
    authCheckRunning = true;
    try {
      const { response, result } = await requestJson("/api/class-rep/auth/me");
      if (!response.ok) throw new Error(result.detail || result.error || `HTTP ${response.status}`);
      if (result.storage_ready === false) {
        authCheckComplete = true; authCheckRunning = false;
        state.user = null; 
        showHeader(false); body.hidden = true; authPanel.hidden = !root.classList.contains("is-open"); setAuthPresentation(root.classList.contains("is-open"));
        authTitle.textContent = "Your private CRARA account is being prepared";
        authIntro.textContent = result.message || "Persistent storage must be configured before you create an account.";
        authName.disabled = true; authEmail.disabled = true; authPassword.disabled = true;
        authSubmit.disabled = true; authSwitch.disabled = true;
        return;
      }
      authCheckComplete = true; authCheckRunning = false;
      retrySessionCheck = false;
      authTitle.textContent = "Your private CRARA account";
      authIntro.textContent = "Sign in to continue your conversations and access your saved tasks and memories.";
      authName.hidden = false; authEmail.hidden = false; authPassword.hidden = false;
      authSwitch.hidden = false; authSubmit.textContent = authMode === "register" ? "Create account" : "Sign in";
      authName.disabled = false; authEmail.disabled = false; authPassword.disabled = false;
      authSubmit.disabled = false; authSwitch.disabled = false;
      state.user = result.authenticated ? result.user : null;
      
      showHeader(Boolean(root.classList.contains("is-open") && state.user));
      setAuthPresentation(root.classList.contains("is-open") && !state.user);
      authPanel.hidden = !root.classList.contains("is-open") || Boolean(state.user);
      body.hidden = !state.user || !root.classList.contains("is-open");
      if (state.user) await loadPreviousConversation();
    } catch (error) {
      // A temporary network/API failure is not proof that the saved session
      // expired. Do not show the login form or discard the browser session.
      authCheckComplete = true; authCheckRunning = false;
      retrySessionCheck = true;
      showHeader(false); body.hidden = true;
      authPanel.hidden = !root.classList.contains("is-open");
      setAuthPresentation(root.classList.contains("is-open"));
      authTitle.textContent = "Your saved CRARA session is still protected";
      authIntro.textContent = "CRARA could not verify your saved sign-in because the service is temporarily unreachable. Retry when the connection is available; you will only need to sign in if your session has actually expired.";
      authName.hidden = true; authEmail.hidden = true; authPassword.hidden = true;
      authSwitch.hidden = true; authSubmit.textContent = "Retry connection";
      authFeedback.textContent = "";
      authSubmit.disabled = false;
    }
  }
  async function authenticate() {
    if (retrySessionCheck) {
      authSubmit.disabled = true;
      await checkAuth();
      return;
    }
    authSubmit.disabled = true;
    try {
      const payload = { email: authEmail.value.trim(), password: authPassword.value };
      if (authMode === "register") payload.name = authName.value.trim();
      const { response, result } = await requestJson("/api/class-rep/auth/" + authMode, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(result.detail || result.error || result.message || `Account request failed (HTTP ${response.status}).`);
      state.user = result.user; state.history = []; state.conversationId = null; 
      transcript.replaceChildren(); setAuthPresentation(false); showHeader(true); authPanel.hidden = true; body.hidden = false;
      authPassword.value = ""; status("Sign in successful", true);
    } catch (error) { authFeedback.textContent = error.message || "Could not sign in."; }
    finally { authSubmit.disabled = false; }
  }
  authSubmit.addEventListener("click", authenticate);
  authSwitch.addEventListener("click", () => setAuthMode(authMode === "login" ? "register" : "login"));
  authPassword.addEventListener("keydown", event => { if (event.key === "Enter") authenticate(); });
  const waitingPhrases = [
    "Thinking…",
    "Looking up…",
    "Preparing…",
    "Checking the details…",
    "Putting this together…",
    "Working through your request…",
    "Reviewing the information…",
    "Finding the relevant details…",
    "Drafting a helpful response…",
    "Almost ready…"
  ];
  let lastWaitingPhrase = -1;
  function nextWaitingPhrase() {
    let index = Math.floor(Math.random() * waitingPhrases.length);
    if (waitingPhrases.length > 1 && index === lastWaitingPhrase) {
      index = (index + 1 + Math.floor(Math.random() * (waitingPhrases.length - 1))) % waitingPhrases.length;
    }
    lastWaitingPhrase = index;
    return waitingPhrases[index];
  }
  async function send(value) {
    const message = String(value || input.value).trim();
    if (!message || state.busy || !state.user) return;
    const restrictedAnalytics = /analytics|performance|missed sessions?|attendance|delivery mode|online vs|face.to.face|teaching hours/i.test(message);
    if (!restrictedAnalytics && state.analyticsPassword) { state.analyticsPassword = ""; state.history = []; }
    input.value = ""; updateComposerAction();
    addMessage("user", message);
    const waitingLabel = nextWaitingPhrase().replace(/[.…]+$/, "");
    const pending = addMessage("assistant", "");
    pending.classList.add("cr-thinking");
    pending.setAttribute("role", "status");
    pending.setAttribute("aria-label", waitingLabel + ", waiting for CRARA response");
    const waitingText = document.createElement("span");
    waitingText.className = "cr-thinking-label";
    waitingText.textContent = waitingLabel;
    const waitingDots = document.createElement("span");
    waitingDots.className = "cr-thinking-dots";
    waitingDots.setAttribute("aria-hidden", "true");
    for (let dot = 0; dot < 3; dot++) waitingDots.append(document.createElement("i"));
    pending.replaceChildren(waitingText, waitingDots);
    state.busy = true; input.disabled = true;
    try {
      if (state.ready) {
        const headers = { "Content-Type": "application/json" };
        if (restrictedAnalytics) {
          const password = state.analyticsPassword || prompt("Management analytics are restricted. Enter the HOD, coordinator or executive dean password:");
          if (!password) { pending.classList.remove("cr-thinking"); pending.removeAttribute("role"); pending.removeAttribute("aria-label"); pending.textContent = "Management analytics access was cancelled. No restricted information was retrieved."; return; }
          state.analyticsPassword = password;
          headers["X-CARA-Analytics-Password"] = password;
        }
        const controller = new AbortController();
        const requestTimer = window.setTimeout(() => controller.abort(), 55000);
        let response, result;
        try {
          response = await fetch("/api/class-rep/chat", {
            method: "POST", headers, credentials: "same-origin", signal: controller.signal,
            cache: "no-store", body: JSON.stringify({ message, history: state.history.slice(-10), conversation_id: state.conversationId })
          });
          result = await response.json().catch(() => ({}));
        } catch (requestError) {
          if (requestError && requestError.name === "AbortError") {
            throw new Error("CRARA took too long to respond. Please try again; your message has not been lost from this chat.");
          }
          throw new Error("The connection to CRARA was interrupted. Check your internet connection and try again.");
        } finally {
          window.clearTimeout(requestTimer);
        }
        if (!response.ok) throw new Error(result.detail || result.error || `CRARA request failed (HTTP ${response.status}).`);
        await typeReply(pending, result.reply);
        state.conversationId = result.conversation_id || state.conversationId;
        if (restrictedAnalytics) { state.history = []; }
        else { state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply }); state.history = state.history.slice(-12); }
        status("AI connected · " + result.provider, true);
      } else {
        await typeReply(pending, demoReply(message));
        const saved = await fetch("/api/class-rep/conversation/turn", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, reply: pending.textContent, conversation_id: state.conversationId })
        }).then(r => r.ok ? r.json() : null).catch(() => null);
        if (saved) {
          state.conversationId = saved.conversation_id;
          await typeReply(pending, saved.reply);
          state.history.push({ role: "user", content: message }, { role: "assistant", content: saved.reply });
          state.history = state.history.slice(-12);
        }
        status("Built-in fallback · AI not configured", false);
      }
    } catch (error) {
      const detail = String(error && error.message || "");
      if (/password|authorised|analytics/i.test(detail)) {
        state.analyticsPassword = "";
        pending.classList.remove("cr-thinking"); pending.removeAttribute("role"); pending.removeAttribute("aria-label"); pending.textContent = "Management analytics access could not be verified. Please check your access credentials and try again.";
      } else {
        pending.classList.remove("cr-thinking"); pending.removeAttribute("role"); pending.removeAttribute("aria-label"); pending.textContent = detail && !/request could not be completed/i.test(detail) ? "CRARA service error: " + detail : "I can’t complete that request right now. Please try again shortly. I can still help draft announcements, messages and other class communications.";
      }
      if (!restrictedAnalytics && state.user) {
        const saved = await fetch("/api/class-rep/conversation/turn", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, reply: pending.textContent, conversation_id: state.conversationId })
        }).then(r => r.ok ? r.json() : null).catch(() => null);
        if (saved) {
          state.conversationId = saved.conversation_id;
          state.history.push({ role: "user", content: message }, { role: "assistant", content: saved.reply });
          state.history = state.history.slice(-12);
        }
      }
      status("", false);
    } finally {
      state.busy = false; input.disabled = false; input.focus();
    }
  }
  attachButton.addEventListener("click", () => { try { if (fileInput.showPicker) fileInput.showPicker(); else fileInput.click(); } catch (_) { fileInput.click(); } });
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { status("Files must be 10 MB or smaller", false); return; }
    try {
      const data = new FormData(); data.append("file", file);
      const response = await fetch("/api/class-rep/documents", {
        method: "POST", body: data
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      // Successful indexing is silent; the document is available to CRARA without a toast or transcript message.
    } catch (error) { status(error.message || "Document indexing failed", false); }
    finally { attachButton.disabled = false; }
  });
  recordButton.addEventListener("click", async () => {
    if (state.recording && state.recorder) { state.recorder.stop(); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      status("Audio recording is not supported in this browser", false); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"].find(type => MediaRecorder.isTypeSupported(type));
      state.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      state.audioParts = [];
      state.recorder.ondataavailable = event => { if (event.data.size) state.audioParts.push(event.data); };
      state.recorder.onstop = async () => {
        stream.getTracks().forEach(track => track.stop());
        state.recording = false; recordButton.replaceChildren(micIcon); recordButton.setAttribute("aria-label", "Record a voice question");
        const audio = new Blob(state.audioParts, { type: state.recorder.mimeType || "audio/webm" });
        const data = new FormData(); data.append("file", audio, "cara-question.webm");
        recordButton.disabled = true; status("Transcribing your question…", false);
        try {
          const response = await fetch("/api/class-rep/transcribe", { method: "POST", body: data });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || "Transcription failed");
          input.value = result.text; updateComposerAction(); input.focus(); status("Question transcribed · review and press Enter", true);
        } catch (error) { status(error.message || "Transcription failed", false); }
        finally { recordButton.disabled = false; }
      };
      state.recorder.start(); state.recording = true;
      recordButton.textContent = "■"; recordButton.setAttribute("aria-label", "Stop recording"); status("Listening… select Stop to finish", true);
    } catch (_) { status("Microphone permission was not granted", false); }
  });
  form.addEventListener("submit", event => { event.preventDefault(); send(); });
  input.addEventListener("input", updateComposerAction);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  function syncVisualViewport() {
    if (!window.visualViewport) return;
    const viewport = window.visualViewport;
    const keyboardInset = Math.max(0, window.innerHeight - (viewport.height + viewport.offsetTop));
    root.style.setProperty("--cara-keyboard-inset", Math.round(keyboardInset) + "px");
  }
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncVisualViewport, { passive: true });
    window.visualViewport.addEventListener("scroll", syncVisualViewport, { passive: true });
    window.addEventListener("orientationchange", syncVisualViewport, { passive: true });
  }
  let caraBackStateActive = false;
  function closeCRARA() {
    if (caraBackStateActive) window.history.back();
    else setOpen(false);
  }
  window.addEventListener("popstate", () => {
    if (root.classList.contains("is-open")) {
      caraBackStateActive = false;
      setOpen(false);
    }
  });
  window.closeCRARAForNavigation = () => {
    if (root.classList.contains("is-open")) {
      caraBackStateActive = false;
      setOpen(false);
    }
  };
  function setOpen(open) {
    if (open && !root.classList.contains("is-open")) {
      window.history.pushState({ ...(window.history.state || {}), caraAssistantOpen: true }, "", window.location.href);
      caraBackStateActive = true;
    }
    if (open) {
      state.previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      document.documentElement.classList.add("cara-open");
      document.body.classList.add("cara-open");
      syncVisualViewport();
    } else {
      document.body.style.overflow = state.previousBodyOverflow;
      document.documentElement.classList.remove("cara-open");
      document.body.classList.remove("cara-open");
      root.style.setProperty("--cara-keyboard-inset", "0px");
    }
    root.classList.toggle("is-open", open);
    setAuthPresentation(Boolean(open && !state.user));
    showHeader(Boolean(open && state.user)); body.hidden = true; authPanel.hidden = !open || Boolean(state.user) || !authCheckComplete; updateLauncherVisibility();
    launcher.setAttribute("aria-expanded", String(open));
    if (open) { void checkAuth(); }
  }
  setAuthMode("login");
  launcher.addEventListener("click", () => setOpen(true));
  // Restore a saved account as soon as the app loads, not only after the user opens CRARA.
  // Keep the login panel hidden while the saved session is being checked.
  void checkAuth();
  checkStatus();
})();