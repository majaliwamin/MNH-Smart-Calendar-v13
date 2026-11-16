(function () {
  "use strict";
  const root = document.getElementById("class-rep-assistant");
  if (!root || root.dataset.ready === "1") return;
  root.dataset.ready = "1";

  const state = { history: [], busy: false, ready: false, recording: false, recorder: null, audioParts: [], documentToken: "", analyticsPassword: "" };
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
  identity.append(el("span", "cr-mark", "C"), el("div", "cr-heading"));
  identity.lastChild.append(el("strong", "", "CARA"), el("small", "cr-tagline", "Your intelligent academic relations assistant"), el("small", "cr-status", "Checking services…"));
  const toggle = el("button", "cr-toggle", "×");
  toggle.type = "button"; toggle.setAttribute("aria-label", "Close CARA"); toggle.setAttribute("aria-expanded", "true");
  header.append(identity, toggle);
  const body = el("div", "cr-body");
  const intro = el("p", "cr-intro", "Ask about the live timetable, modules, facilitators, examinations, recurring activities, announcements, resources, uploaded documents and recent changes. CARA is read-only.");
  const prompts = el("div", "cr-prompts");
  [["This week's sessions", "Summarise this week's confirmed sessions, times and facilitators."],
   ["Upcoming exams", "What examination information is currently recorded?"],
   ["Draft an announcement", "Draft a concise class announcement using confirmed timetable information."],
   ["Search programme notes", "Search uploaded programme documents for information about assessment and course requirements."]]
    .forEach(([label, prompt]) => {
      const button = el("button", "cr-prompt", label);
      button.type = "button"; button.addEventListener("click", () => send(prompt));
      prompts.append(button);
    });
  const transcript = el("div", "cr-transcript");
  transcript.setAttribute("role", "log"); transcript.setAttribute("aria-live", "polite"); transcript.setAttribute("aria-label", "Assistant conversation");
  const form = el("form", "cr-form");
  const input = el("textarea", "cr-input");
  input.rows = 2; input.maxLength = 4000; input.placeholder = "Ask the class assistant…"; input.setAttribute("aria-label", "Message the Class Rep Assistant");
  const sendButton = el("button", "cr-send", "Send"); sendButton.type = "submit";
  form.append(input, sendButton);
  const tools = el("div", "cr-tools");
  const recordButton = el("button", "cr-prompt", "🎙 Record question"); recordButton.type = "button";
  const uploadButton = el("button", "cr-prompt", "Add programme document"); uploadButton.type = "button";
  const fileInput = el("input", "cr-file-input"); fileInput.type = "file"; fileInput.accept = ".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";
  fileInput.hidden = true;
  const docsButton = el("button", "cr-prompt", "Manage documents"); docsButton.type = "button";
  tools.append(recordButton, uploadButton, docsButton, fileInput);
  const docsPanel = el("div", "cr-documents"); docsPanel.hidden = true;
  const foot = el("p", "cr-foot", "CARA reads shared calendar records and authorised uploaded documents. Voice requests are processed by Cloudflare. CARA does not change timetable records or send messages.");
  body.append(intro, prompts, transcript, form, tools, docsPanel, foot);
  root.append(launcher, header, body);
  root.classList.remove("class-rep-assistant");
  root.classList.add("cara-widget");
  root.classList.remove("is-open");
  header.hidden = true;
  body.hidden = true;
  addMessage("assistant", "Hello! I’m CARA, your intelligent academic relations assistant. I can retrieve information from the live shared calendar and authorised uploaded programme documents, and I can listen to questions and read responses aloud when voice services are configured.");

  function status(text, ready) {
    const node = root.querySelector(".cr-status");
    node.textContent = text;
    node.dataset.state = ready ? "ready" : "unavailable";
  }
  function addMessage(role, text) {
    const bubble = el("div", "cr-message " + (role === "user" ? "cr-user" : "cr-assistant"), text);
    transcript.append(bubble);
    if (role === "assistant") {
      const speakButton = el("button", "cr-prompt cr-speak", "▶ Listen");
      speakButton.type = "button";
      speakButton.addEventListener("click", async () => {
        speakButton.disabled = true;
        try {
          const response = await fetch("/api/class-rep/speak", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: bubble.textContent })
          });
          if (!response.ok) throw new Error("Speech service unavailable");
          const audio = new Audio(URL.createObjectURL(await response.blob()));
          audio.onended = () => URL.revokeObjectURL(audio.src);
          await audio.play();
        } catch (_) { status("Voice playback unavailable", false); }
        finally { speakButton.disabled = false; }
      });
      transcript.append(speakButton);
    }
    transcript.scrollTop = transcript.scrollHeight;
    return bubble;
  }
  function demoReply(message) {
    const q = message.toLowerCase();
    if (/hello|hi|hey/.test(q)) return "Hello! I’m here to support the MNH class representative with clear academic communication. What would you like help with?";
    if (/exam|examination|test|assessment/.test(q)) return "I can help prepare an examination notice. Please confirm the date, time and venue in the Examinations section before sharing.";
    if (/session|timetable|schedule|class|lecture|this week/.test(q)) return "For accurate session dates, times, modules and facilitators, please check the live weekly timetable. I won't guess or invent a session.";
    if (/announcement|announce|remind|broadcast/.test(q)) return "Ready-to-edit announcement:\n\nGood day, everyone. Please refer to the MNH Smart Timetable for the confirmed module, date, time and delivery details. Kindly be punctual and come prepared.\n\nThank you,\nClass Representative";
    if (/lecturer|facilitator|professor|doctor|message|email|whatsapp/.test(q)) return "Good day, [Title and Name]. I hope you are well. I am writing on behalf of the MNH class to kindly seek clarification regarding [specific issue]. Could you please advise us when convenient?\n\nThank you for your time and guidance.\nKind regards,\nClass Representative";
    return "I can help with class announcements, messages to lecturers, meeting agendas and timetable guidance. Configure a CARA AI provider to enable live AI answers.";
  }
  async function checkStatus() {
    try {
      const response = await fetch("/api/class-rep/status", { cache: "no-store" });
      const result = await response.json();
      state.ready = Boolean(response.ok && result.ready);
      state.voice = result.voice === "enabled";
      state.uploads = result.document_uploads === "enabled";
      status(state.ready ? "AI connected · " + result.provider + (result.fallbacks?.length ? " · fallbacks ready" : "") : "Built-in fallback · AI not configured", state.ready);
      recordButton.disabled = !state.voice;
      root.dataset.documentSearch = result.document_search || "unavailable";
      uploadButton.disabled = !state.uploads;
      if (!state.uploads) uploadButton.title = "Document administration is not configured by the server.";
    } catch (_) {
      state.ready = false; state.voice = false; state.uploads = false;
      status("Services unavailable", false);
      recordButton.disabled = true;
    }
  }
  async function send(value) {
    const message = String(value || input.value).trim();
    if (!message || state.busy) return;
    const restrictedAnalytics = /analytics|performance|missed sessions?|attendance|delivery mode|online vs|face.to.face|teaching hours/i.test(message);
    if (!restrictedAnalytics && state.analyticsPassword) { state.analyticsPassword = ""; state.history = []; }
    input.value = "";
    prompts.hidden = true;
    addMessage("user", message);
    const pending = addMessage("assistant", "Preparing a response…");
    state.busy = true; sendButton.disabled = true; sendButton.textContent = "…";
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
          cache: "no-store", body: JSON.stringify({ message, history: state.history.slice(-10) })
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.detail || "AI provider unavailable");
        pending.textContent = result.reply;
        if (restrictedAnalytics) { state.history = []; }
        else { state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply }); state.history = state.history.slice(-12); }
        status("AI connected · " + result.provider, true);
      } else {
        pending.textContent = demoReply(message);
        status("Built-in fallback · AI not configured", false);
      }
    } catch (error) {
      pending.textContent = error.message || "AI temporarily unavailable";
      if (/password|authorised|analytics/i.test(error.message || "")) state.analyticsPassword = "";
      status(error.message || "AI temporarily unavailable", false);
    } finally {
      state.busy = false; sendButton.disabled = false; sendButton.textContent = "Send";
      input.focus();
    }
  }
  async function loadDocuments() {
    docsPanel.hidden = false;
    docsPanel.replaceChildren(el("p", "cr-foot", "Loading document register…"));
    try {
      const response = await fetch("/api/class-rep/documents", { cache: "no-store" });
      const result = await response.json();
      docsPanel.replaceChildren();
      if (!result.documents?.length) docsPanel.append(el("p", "cr-foot", "No programme documents have been indexed yet."));
      result.documents?.forEach(doc => {
        const row = el("div", "cr-document-row");
        row.append(el("span", "", doc.title + " · " + doc.chunks + " passages"));
        const remove = el("button", "cr-prompt", "Delete");
        remove.type = "button";
        remove.addEventListener("click", async () => {
          const token = state.documentToken || prompt("Enter the document administrator credential to delete this file:");
          if (!token) return;
          state.documentToken = token;
          const deleted = await fetch("/api/class-rep/documents/" + encodeURIComponent(doc.id), {
            method: "DELETE", headers: { "X-CARA-Admin-Token": token }
          });
          if (!deleted.ok) { status("Document deletion was not authorised", false); return; }
          loadDocuments();
        });
        row.append(remove); docsPanel.append(row);
      });
    } catch (_) { docsPanel.replaceChildren(el("p", "cr-foot", "Could not load the document register.")); }
  }
  docsButton.addEventListener("click", () => { if (docsPanel.hidden) loadDocuments(); else docsPanel.hidden = true; });
  uploadButton.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { status("Files must be 10 MB or smaller", false); return; }
    const token = state.documentToken || prompt("Enter the document administrator credential to upload and index this file:");
    if (!token) return;
    state.documentToken = token;
    uploadButton.disabled = true; uploadButton.textContent = "Indexing…";
    try {
      const data = new FormData(); data.append("file", file);
      const response = await fetch("/api/class-rep/documents", {
        method: "POST", headers: { "X-CARA-Admin-Token": token }, body: data
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      status("Indexed " + result.title + " · " + result.chunks + " passages", true);
      docsPanel.hidden = false; await loadDocuments();
    } catch (error) { status(error.message || "Document indexing failed", false); }
    finally { uploadButton.disabled = false; uploadButton.textContent = "Add programme document"; }
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
        state.recording = false; recordButton.textContent = "🎙 Record question";
        const audio = new Blob(state.audioParts, { type: state.recorder.mimeType || "audio/webm" });
        const data = new FormData(); data.append("file", audio, "cara-question.webm");
        recordButton.disabled = true; status("Transcribing your question…", false);
        try {
          const response = await fetch("/api/class-rep/transcribe", { method: "POST", body: data });
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail || "Transcription failed");
          input.value = result.text; input.focus(); status("Question transcribed · review then Send", true);
        } catch (error) { status(error.message || "Transcription failed", false); }
        finally { recordButton.disabled = false; }
      };
      state.recorder.start(); state.recording = true;
      recordButton.textContent = "■ Stop recording"; status("Listening… select Stop recording when finished", true);
    } catch (_) { status("Microphone permission was not granted", false); }
  });
  form.addEventListener("submit", event => { event.preventDefault(); send(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  function setOpen(open) {
    root.classList.toggle("is-open", open);
    header.hidden = !open; body.hidden = !open; launcher.hidden = open;
    launcher.setAttribute("aria-expanded", String(open)); toggle.setAttribute("aria-expanded", String(open));
  }
  launcher.addEventListener("click", () => setOpen(true));
  toggle.addEventListener("click", () => setOpen(false));
  checkStatus();
})();