(function () {
  "use strict";
  const root = document.getElementById("class-rep-assistant");
  if (!root || root.dataset.ready === "1") return;
  root.dataset.ready = "1";
  // Keep the full-screen assistant outside app header/transform stacking contexts.
  if (root.parentElement !== document.body) document.body.appendChild(root);

  const state = { history: [], busy: false, ready: false, recording: false, recorder: null, audioParts: [], documentToken: "", analyticsPassword: "", previousBodyOverflow: "", user: null, conversationId: null };
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const launcher = el("button", "cara-launcher", "CARA");
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open CARA, your intelligent academic relations assistant");
  launcher.setAttribute("aria-expanded", "false");
  const header = el("div", "cr-head");
  const identity = el("div", "cr-identity");
  identity.append(el("strong", "cr-title", "CARA (Classroom and Academic Relations Assistant)"));
  identity.append(el("span", "cr-subtitle", "Your intelligent academic relations assistant"));
  const toggle = el("button", "cr-toggle", "×"); toggle.type = "button"; toggle.setAttribute("aria-label", "Close CARA"); toggle.setAttribute("aria-expanded", "true");
  const signOut = el("button", "cr-account", "Sign out"); signOut.type = "button"; signOut.hidden = true;\n  header.append(identity, signOut, toggle);
  const body = el("div", "cr-body");
  const transcript = el("div", "cr-transcript");
  transcript.setAttribute("role", "log"); transcript.setAttribute("aria-live", "polite"); transcript.setAttribute("aria-label", "Assistant conversation");
  const form = el("form", "cr-form");
  const attachButton = el("button", "cr-icon-button cr-attach", "+"); attachButton.type = "button"; attachButton.setAttribute("aria-label", "Attach a programme file"); attachButton.title = "Attach file";
  const input = el("textarea", "cr-input"); input.rows = 1; input.maxLength = 4000; input.placeholder = "Message CARA…"; input.setAttribute("aria-label", "Message CARA");
  const recordButton = el("button", "cr-icon-button cr-record"); recordButton.type = "button"; recordButton.setAttribute("aria-label", "Record a voice question"); recordButton.title = "Voice input";
  const micIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  micIcon.setAttribute("viewBox", "0 0 24 24"); micIcon.setAttribute("width", "22"); micIcon.setAttribute("height", "22"); micIcon.setAttribute("fill", "none"); micIcon.setAttribute("stroke", "currentColor"); micIcon.setAttribute("stroke-width", "2"); micIcon.setAttribute("stroke-linecap", "round"); micIcon.setAttribute("stroke-linejoin", "round"); micIcon.setAttribute("aria-hidden", "true");
  const micBody = document.createElementNS("http://www.w3.org/2000/svg", "rect"); micBody.setAttribute("x", "9"); micBody.setAttribute("y", "2"); micBody.setAttribute("width", "6"); micBody.setAttribute("height", "12"); micBody.setAttribute("rx", "3");
  const micStand = document.createElementNS("http://www.w3.org/2000/svg", "path"); micStand.setAttribute("d", "M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8");
  micIcon.append(micBody, micStand); recordButton.append(micIcon);
  const sendButton = el("button", "cr-icon-button cr-send", "➤"); sendButton.type = "submit"; sendButton.setAttribute("aria-label", "Send message"); sendButton.title = "Send message"; sendButton.hidden = true;
  function updateComposerAction() { const hasText = Boolean(input.value.trim()); recordButton.hidden = hasText; sendButton.hidden = !hasText; }
  const fileInput = el("input", "cr-file-input"); fileInput.type = "file";
  fileInput.accept = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,image/png,image/jpeg,image/tiff,image/bmp,image/webp"; fileInput.hidden = true;
  const statusNode = el("span", "cr-status"); statusNode.hidden = true; statusNode.setAttribute("aria-live", "polite");
  form.append(attachButton, input, recordButton, sendButton); body.append(transcript, form, fileInput, statusNode);
  const authPanel = el("section", "cr-auth-panel");
  const authCard = el("div", "cr-auth-card");
  const authTitle = el("strong", "cr-auth-title", "Your private CARA account");
  const authIntro = el("p", "cr-auth-intro", "Sign in to continue your conversations and access your saved tasks and memories.");
  const authName = el("input", "cr-auth-input"); authName.placeholder = "Your name"; authName.autocomplete = "name"; authName.hidden = true;
  const authEmail = el("input", "cr-auth-input"); authEmail.type = "email"; authEmail.placeholder = "Email address"; authEmail.autocomplete = "email";
  const authPassword = el("input", "cr-auth-input"); authPassword.type = "password"; authPassword.placeholder = "Password (at least 12 characters)"; authPassword.autocomplete = "current-password";
  const authSubmit = el("button", "cr-auth-submit", "Sign in"); authSubmit.type = "button";
  const authSwitch = el("button", "cr-auth-switch", "Create a new account"); authSwitch.type = "button";
  const authFeedback = el("p", "cr-auth-feedback", "");
  authCard.append(authTitle, authIntro, authName, authEmail, authPassword, authSubmit, authSwitch, authFeedback);
  authPanel.append(authCard);
  root.append(launcher, header, body, authPanel);
  root.classList.remove("class-rep-assistant");
  root.classList.add("cara-widget");
  root.classList.remove("is-open");
  header.hidden = true;
  body.hidden = true;
  function status(text, ready) {
    const node = statusNode;
    node.textContent = text;
    node.dataset.state = ready ? "ready" : "unavailable";
  }
  function addMessage(role, text) { const bubble = el("div", "cr-message " + (role === "user" ? "cr-user" : "cr-assistant"), text); transcript.append(bubble); transcript.scrollTop = transcript.scrollHeight; return bubble; }
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
      const response = await fetch("/api/class-rep/status", { cache: "no-store" });
      const result = await response.json();
      state.ready = Boolean(response.ok && result.ready);
      state.voice = result.voice === "enabled";
      state.uploads = result.document_uploads === "enabled";
      status(state.ready ? "AI connected · " + result.provider + (result.fallbacks?.length ? " · fallbacks ready" : "") : "Built-in fallback · AI not configured", state.ready);
      recordButton.disabled = !state.voice; root.dataset.documentSearch = result.document_search || "unavailable";
      attachButton.disabled = !state.uploads; if (!state.uploads) attachButton.title = "File uploads are not configured by the server.";
    } catch (_) {
      state.ready = false; state.voice = false; state.uploads = false;
      status("Services unavailable", false);
      recordButton.disabled = true; attachButton.disabled = true;
    }
  }
  let authMode = "login";
  function setAuthMode(mode) {
    authMode = mode;
    authName.hidden = mode !== "register";
    authPassword.autocomplete = mode === "register" ? "new-password" : "current-password";
    authSubmit.textContent = mode === "register" ? "Create account" : "Sign in";
    authSwitch.textContent = mode === "register" ? "I already have an account" : "Create a new account";
    authFeedback.textContent = "";
  }
  async function loadPreviousConversation() {
    try {
      const response = await fetch("/api/class-rep/conversations", { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const latest = (data.conversations || [])[0];
      if (!latest) return;
      state.conversationId = latest.id;
      state.history = (latest.messages || []).slice(-12).map(m => ({ role: m.role, content: m.content }));
      transcript.replaceChildren();
      for (const message of state.history) addMessage(message.role, message.content);
    } catch (_) {}
  }
  async function checkAuth() {
    try {
      const response = await fetch("/api/class-rep/auth/me", { cache: "no-store" });
      const result = await response.json();
      state.user = result.authenticated ? result.user : null;
      signOut.hidden = !state.user;
      authPanel.hidden = Boolean(state.user);
      body.hidden = !state.user;
      if (state.user) await loadPreviousConversation();
    } catch (_) {
      state.user = null; authPanel.hidden = false; body.hidden = true;
    }
  }
  async function authenticate() {
    authSubmit.disabled = true;
    try {
      const payload = { email: authEmail.value.trim(), password: authPassword.value };
      if (authMode === "register") payload.name = authName.value.trim();
      const response = await fetch("/api/class-rep/auth/" + authMode, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Account request failed.");
      state.user = result.user; state.history = []; state.conversationId = null;
      transcript.replaceChildren(); authPanel.hidden = true; body.hidden = false; signOut.hidden = false;
      authPassword.value = ""; status("Signed in · private memory enabled", true);
    } catch (error) { authFeedback.textContent = error.message || "Could not sign in."; }
    finally { authSubmit.disabled = false; }
  }
  authSubmit.addEventListener("click", authenticate);
  authSwitch.addEventListener("click", () => setAuthMode(authMode === "login" ? "register" : "login"));
  authPassword.addEventListener("keydown", event => { if (event.key === "Enter") authenticate(); });
  signOut.addEventListener("click", async () => {
    await fetch("/api/class-rep/auth/logout", { method: "POST" }).catch(() => {});
    state.user = null; state.history = []; state.conversationId = null; transcript.replaceChildren();
    body.hidden = true; authPanel.hidden = false; signOut.hidden = true; setAuthMode("login");
  });
  async function send(value) {
    const message = String(value || input.value).trim();
    if (!message || state.busy || !state.user) return;
    const restrictedAnalytics = /analytics|performance|missed sessions?|attendance|delivery mode|online vs|face.to.face|teaching hours/i.test(message);
    if (!restrictedAnalytics && state.analyticsPassword) { state.analyticsPassword = ""; state.history = []; }
    input.value = ""; updateComposerAction();
    addMessage("user", message);
    const pending = addMessage("assistant", "Preparing a response…");
    state.busy = true; input.disabled = true;
    try {
      if (state.ready) {
        const headers = { "Content-Type": "application/json" };
        if (restrictedAnalytics) {
          const password = state.analyticsPassword || prompt("Management analytics are restricted. Enter the HOD, coordinator or executive dean password:");
          if (!password) { pending.textContent = "Management analytics access was cancelled. No restricted information was retrieved."; return; }
          state.analyticsPassword = password;
          headers["X-CARA-Analytics-Password"] = password;
        }
        const response = await fetch("/api/class-rep/chat", {
          method: "POST", headers,
          cache: "no-store", body: JSON.stringify({ message, history: state.history.slice(-10), conversation_id: state.conversationId })
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error("Request could not be completed");
        pending.textContent = result.reply;
        state.conversationId = result.conversation_id || state.conversationId;
        if (restrictedAnalytics) { state.history = []; }
        else { state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply }); state.history = state.history.slice(-12); }
        status("AI connected · " + result.provider, true);
      } else {
        pending.textContent = demoReply(message);
        status("Built-in fallback · AI not configured", false);
      }
    } catch (error) {
      const detail = String(error && error.message || "");
      if (/password|authorised|analytics/i.test(detail)) {
        state.analyticsPassword = "";
        pending.textContent = "Management analytics access could not be verified. Please check your access credentials and try again.";
      } else {
        pending.textContent = "I can’t complete that request right now. Please try again shortly. I can still help draft announcements, messages and other class communications.";
      }
      status("", false);
    } finally {
      state.busy = false; input.disabled = false; input.focus();
    }
  }
  attachButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { status("Files must be 10 MB or smaller", false); return; }
    const token = state.documentToken || prompt("Enter the document administrator credential to upload and index this file:");
    if (!token) return;
    state.documentToken = token;
    attachButton.disabled = true;
    try {
      const data = new FormData(); data.append("file", file);
      const response = await fetch("/api/class-rep/documents", {
        method: "POST", headers: { "X-CARA-Admin-Token": token }, body: data
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      status("Indexed " + result.title + " · " + result.chunks + " passages", true); addMessage("assistant", "File indexed successfully: " + result.title + ".");
    } catch (error) { status(error.message || "Document indexing failed", false); }
    finally { attachButton.disabled = !state.uploads; }
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
  function setOpen(open) {
    if (open) {
      state.previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      document.documentElement.classList.add("cara-open");
      syncVisualViewport();
    } else {
      document.body.style.overflow = state.previousBodyOverflow;
      document.documentElement.classList.remove("cara-open");
      root.style.setProperty("--cara-keyboard-inset", "0px");
    }
    root.classList.toggle("is-open", open);
    header.hidden = !open; body.hidden = true; authPanel.hidden = !open; launcher.hidden = open;
    launcher.setAttribute("aria-expanded", String(open)); toggle.setAttribute("aria-expanded", String(open));
    if (open) { void checkAuth(); }
  }
  setAuthMode("login");
  launcher.addEventListener("click", () => setOpen(true));
  toggle.addEventListener("click", () => setOpen(false));
  checkStatus();
})();