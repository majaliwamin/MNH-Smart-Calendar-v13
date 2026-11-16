(function () {
  "use strict";
  const root = document.getElementById("class-rep-assistant");
  if (!root || root.dataset.ready === "1") return;
  root.dataset.ready = "1";

  const state = { history: [], busy: false, ready: false };
  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const header = el("div", "cr-head");
  const identity = el("div", "cr-identity");
  identity.append(el("span", "cr-mark", "CR"), el("div", "cr-heading"));
  identity.lastChild.append(el("strong", "", "Class Rep Assistant"), el("small", "cr-status", "Checking AI connection…"));
  const toggle = el("button", "cr-toggle", "−");
  toggle.type = "button"; toggle.setAttribute("aria-label", "Collapse assistant"); toggle.setAttribute("aria-expanded", "true");
  header.append(identity, toggle);
  const body = el("div", "cr-body");
  const intro = el("p", "cr-intro", "Ask about the timetable, examinations, announcements or class coordination. I can also prepare messages and meeting notes.");
  const prompts = el("div", "cr-prompts");
  [["This week's sessions", "Summarise this week's confirmed sessions, times and facilitators."],
   ["Upcoming exams", "What examination information is currently recorded?"],
   ["Draft an announcement", "Draft a concise class announcement using confirmed timetable information."],
   ["Message a lecturer", "Help me draft a polite message to a lecturer about a timetable clarification."]]
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
  const foot = el("p", "cr-foot", "AI responses can be mistaken. Confirm important changes with programme staff.");
  body.append(intro, prompts, transcript, form, foot);
  root.append(header, body);

  function status(text, ready) {
    const node = root.querySelector(".cr-status");
    node.textContent = text;
    node.dataset.state = ready ? "ready" : "unavailable";
  }
  function addMessage(role, text) {
    const bubble = el("div", "cr-message " + (role === "user" ? "cr-user" : "cr-assistant"), text);
    transcript.append(bubble);
    transcript.scrollTop = transcript.scrollHeight;
    return bubble;
  }
  async function checkStatus() {
    try {
      const response = await fetch("/api/class-rep/status", { cache: "no-store" });
      const result = await response.json();
      state.ready = Boolean(response.ok && result.ready);
      status(state.ready ? "AI connected · " + result.provider : "AI provider not configured", state.ready);
      if (!state.ready) addMessage("assistant", "The assistant interface is ready, but the AI provider still needs its server-side API key and model configuration.");
    } catch (_) {
      status("Connection unavailable", false);
    }
  }
  async function send(value) {
    const message = String(value || input.value).trim();
    if (!message || state.busy) return;
    input.value = "";
    prompts.hidden = true;
    addMessage("user", message);
    const pending = addMessage("assistant", "Thinking…");
    state.busy = true; sendButton.disabled = true; sendButton.textContent = "…";
    try {
      const response = await fetch("/api/class-rep/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        cache: "no-store", body: JSON.stringify({ message, history: state.history.slice(-10) })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || result.error || "The assistant could not complete this request.");
      pending.textContent = result.reply;
      state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply });
      state.history = state.history.slice(-12);
      status("AI connected · " + result.provider, true);
    } catch (error) {
      pending.textContent = error.message || "The assistant is temporarily unavailable. Please try again.";
      status("AI unavailable", false);
    } finally {
      state.busy = false; sendButton.disabled = false; sendButton.textContent = "Send";
      input.focus();
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); send(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  toggle.addEventListener("click", () => {
    const collapsed = body.hidden;
    body.hidden = !collapsed;
    toggle.textContent = collapsed ? "−" : "+";
    toggle.setAttribute("aria-expanded", String(collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Collapse assistant" : "Expand assistant");
  });
  checkStatus();
})();