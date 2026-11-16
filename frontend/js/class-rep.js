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
  const launcher = el("button", "cara-launcher", "CARA");
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open CARA, your intelligent academic relations assistant");
  launcher.setAttribute("aria-expanded", "false");
  const header = el("div", "cr-head");
  const identity = el("div", "cr-identity");
  identity.append(el("span", "cr-mark", "C"), el("div", "cr-heading"));
  identity.lastChild.append(el("strong", "", "CARA"), el("small", "cr-tagline", "Your intelligent academic relations assistant"), el("small", "cr-status", "Demo mode · built-in responses"));
  const toggle = el("button", "cr-toggle", "×");
  toggle.type = "button"; toggle.setAttribute("aria-label", "Close CARA"); toggle.setAttribute("aria-expanded", "true");
  header.append(identity, toggle);
  const body = el("div", "cr-body");
  const intro = el("p", "cr-intro", "Ask about class coordination, examinations or announcements. Demo mode is active: responses are built in and do not yet read live timetable records.");
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
  const foot = el("p", "cr-foot", "Demo responses are illustrative. Confirm dates, times and decisions against the live calendar and programme office.");
  body.append(intro, prompts, transcript, form, foot);
  root.append(launcher, header, body);
  root.classList.remove("class-rep-assistant");
  root.classList.add("cara-widget");
  root.classList.remove("is-open");
  header.hidden = true;
  body.hidden = true;
  addMessage("assistant", "Hello! I’m CARA, your intelligent academic relations assistant. I’m currently running with built-in demo responses, so I can help draft class communications and guide you to the right calendar section. Live timetable-aware AI will be connected later.");

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
  function demoReply(message) {
    const q = message.toLowerCase();
    if (/\b(hello|hi|hey|good morning|good afternoon|good evening)\b/.test(q)) return "Hello! I’m here to support the MNH class representative with clear academic communication. What would you like help with?";
    if (/exam|examination|test|assessment/.test(q)) return "I can help prepare an examination notice, but demo mode is not connected to the live examination register. Please open the Examinations section and confirm the date, time and venue there. Share the confirmed details and I can turn them into a clear class announcement.";
    if (/session|timetable|schedule|class|lecture|this week/.test(q)) return "For accurate session dates, times, modules and facilitators, Please check the live weekly timetable above. Demo mode does not read calendar records, so I won't guess or invent a session. I can draft a reminder once you provide the confirmed details.";
    if (/announcement|announce|remind|broadcast/.test(q)) return "Ready-to-edit announcement:\\n\\nGood day, everyone. This is a reminder about our upcoming academic session. Please refer to the MNH Smart Timetable for the confirmed module, date, time and delivery details. Kindly be punctual and come prepared.\\n\\nThank you,\\nClass Representative\\n\\nPlease verify the timetable details before sharing.";
    if (/lecturer|facilitator|professor|doctor|message|email|whatsapp/.test(q)) return "Polite message draft:\\n\\nGood day, [Title and Name]. I hope you are well. I am writing on behalf of the MNH class to kindly seek clarification regarding [state the specific issue]. Could you please advise us when convenient?\\n\\nThank you for your time and guidance.\\nKind regards,\\nClass Representative";
    if (/agenda|meeting|minutes/.test(q)) return "Suggested class meeting agenda:\\n\\n1. Welcome and purpose of the meeting\\n2. Review of confirmed timetable and assessments\\n3. Student questions or concerns\\n4. Agreed actions, responsible persons and deadlines\\n5. Any other business and closing\\n\\nRecord only decisions actually agreed by the group.";
    if (/thank/.test(q)) return "You're welcome. I’m ready to help with class announcements, messages to lecturers, meeting agendas and timetable guidance.";
    return "I can help with class announcements, messages to lecturers, meeting agendas and general timetable guidance. Try one of the suggested prompts, or tell me what message you want drafted.\\n\\nThis is a hardcoded demo response; live calendar lookup and provider-based AI are not enabled yet.";
  }
  async function checkStatus() {
    try {
      const response = await fetch("/api/class-rep/status", { cache: "no-store" });
      const result = await response.json();
      state.ready = Boolean(response.ok && result.ready);
      status(state.ready ? "AI connected · " + result.provider : "Demo mode · built-in responses", state.ready);
    } catch (_) {
      state.ready = false;
      status("Demo mode · built-in responses", false);
    }
  }
  async function send(value) {
    const message = String(value || input.value).trim();
    if (!message || state.busy) return;
    input.value = "";
    prompts.hidden = true;
    addMessage("user", message);
    const pending = addMessage("assistant", "Preparing a response…");
    state.busy = true; sendButton.disabled = true; sendButton.textContent = "…";
    try {
      if (state.ready) {
        const response = await fetch("/api/class-rep/chat", {
          method: "POST", headers: { "Content-Type": "application/json" },
          cache: "no-store", body: JSON.stringify({ message, history: state.history.slice(-10) })
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error("AI provider unavailable");
        pending.textContent = result.reply;
        state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply });
        state.history = state.history.slice(-12);
        status("AI connected · " + result.provider, true);
      } else {
        pending.textContent = demoReply(message);
        status("Demo mode · built-in responses", false);
      }
    } catch (_) {
      state.ready = false;
      pending.textContent = demoReply(message);
      status("Demo mode · built-in responses", false);
    } finally {
      state.busy = false; sendButton.disabled = false; sendButton.textContent = "Send";
      input.focus();
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); send(); });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  function setOpen(open) {
    root.classList.toggle("is-open", open);
    header.hidden = !open;
    body.hidden = !open;
    launcher.hidden = open;
    launcher.setAttribute("aria-expanded", String(open));
    toggle.setAttribute("aria-expanded", String(open));
  }
  launcher.addEventListener("click", () => setOpen(true));
  toggle.addEventListener("click", () => setOpen(false));
  checkStatus();
})();