(function(){
  "use strict";

  const rootId = "exams-body";
  const state = {
    session: null,
    exam: null,
    timer: null,
    autosave: null,
    heartbeat: null,
    abort: null,
    serverOffset: 0,
    saving: false
  };
  let dialogCount = 0;

  function esc(value){
    return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[ch]));
  }

  async function fetchJson(url, options){
    const opts = options || {};
    const res = await fetch(url, Object.assign({ credentials: "same-origin" }, opts, {
      headers: Object.assign({ "Accept": "application/json", "Content-Type": "application/json" }, opts.headers || {})
    }));
    const data = await res.json().catch(() => ({}));
    if(!res.ok) throw new Error(data.error || data.detail || ("HTTP " + res.status));
    return data;
  }

  function card(title, bodyHtml){
    return '<section class="exams-card"><h3>' + esc(title) + "</h3>" + bodyHtml + "</section>";
  }

  function fmt(ms){
    try{ return ms ? new Date(Number(ms)).toLocaleString() : ""; }
    catch(_err){ return ""; }
  }

  function datetimeLocal(ms){
    if(!ms) return "";
    const d = new Date(Number(ms));
    const pad = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      "T" + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function parseTimeInput(value){
    const text = String(value || "").trim();
    if(!text) return null;
    const parsed = Date.parse(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function serverNow(){
    return Date.now() + Number(state.serverOffset || 0);
  }

  function showMsg(id, text, isErr){
    const el = document.getElementById(id);
    if(!el) return;
    el.className = isErr ? "exams-error" : "exams-note";
    el.setAttribute("role", isErr ? "alert" : "status");
    el.textContent = text || "";
  }

  function stopTimers(){
    if(state.timer){ clearInterval(state.timer); state.timer = null; }
    if(state.autosave){ clearInterval(state.autosave); state.autosave = null; }
    if(state.heartbeat){ clearInterval(state.heartbeat); state.heartbeat = null; }
  }

  function detachListeners(){
    if(state.abort) state.abort.abort();
    state.abort = null;
  }

  function openDialog(config){
    const options = config || {};
    return new Promise(resolve => {
      const previousFocus = document.activeElement;
      const wrap = document.createElement("div");
      wrap.className = "exams-modal-backdrop";
      const titleId = "exams-dialog-title-" + (++dialogCount);
      wrap.innerHTML =
        '<div class="exams-modal' + (options.wide ? " exams-modal-wide" : "") + '" role="dialog" aria-modal="true" aria-labelledby="' + titleId + '">' +
          '<h3 id="' + titleId + '" class="exams-dialog-title">' + esc(options.title || "EXAMS") + "</h3>" +
          '<div class="exams-dialog-body">' + (options.bodyHtml || "") + "</div>" +
          '<div class="exams-form-actions exams-dialog-actions">' +
            (options.showCancel === false ? "" : '<button type="button" class="exams-btn exams-dialog-cancel">Cancel</button>') +
            '<button type="button" class="exams-btn ' + (options.danger ? "danger" : "primary") + ' exams-dialog-ok">' + esc(options.okText || "OK") + "</button>" +
          "</div>" +
          '<div class="exams-note exams-dialog-msg" role="status"></div>' +
        "</div>";
      const dialog = wrap.querySelector(".exams-modal");
      const ok = wrap.querySelector(".exams-dialog-ok");
      const cancel = wrap.querySelector(".exams-dialog-cancel");
      const msg = wrap.querySelector(".exams-dialog-msg");
      const focusable = () => Array.from(dialog.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]"));

      const close = value => {
        document.removeEventListener("keydown", onKey, true);
        wrap.remove();
        if(previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
        resolve(value);
      };
      const onKey = event => {
        if(event.key === "Escape"){
          event.preventDefault();
          close(null);
          return;
        }
        if(event.key !== "Tab") return;
        const items = focusable();
        if(!items.length) return;
        const first = items[0], last = items[items.length - 1];
        if(event.shiftKey && document.activeElement === first){ event.preventDefault(); last.focus(); }
        else if(!event.shiftKey && document.activeElement === last){ event.preventDefault(); first.focus(); }
      };

      if(cancel) cancel.addEventListener("click", () => close(null));
      wrap.addEventListener("click", event => { if(event.target === wrap) close(null); });
      ok.addEventListener("click", async () => {
        if(!options.onOk){ close(true); return; }
        ok.disabled = true;
        msg.className = "exams-note";
        msg.textContent = "Working...";
        try{
          const value = await options.onOk(dialog);
          close(value === undefined ? true : value);
        }catch(err){
          msg.className = "exams-error";
          msg.setAttribute("role", "alert");
          msg.textContent = err && err.message ? err.message : String(err);
          ok.disabled = false;
        }
      });
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(wrap);
      if(options.onMount) options.onMount(dialog);
      const firstField = dialog.querySelector("input, select, textarea");
      (firstField || ok).focus();
    });
  }

  function uiConfirm(message, okText, danger){
    return openDialog({
      title: okText || "Confirm",
      bodyHtml: '<p class="exams-modal-msg"></p>',
      okText: okText || "Confirm",
      danger: !!danger,
      onMount: dialog => { dialog.querySelector(".exams-modal-msg").textContent = message; }
    }).then(value => value === true);
  }

  function questionFieldsHtml(question){
    const q = question || {};
    const options = (q.options || []).map(o => o.id + "|" + o.text).join("\n");
    return "" +
      '<label>Prompt<textarea name="prompt" required rows="3" maxlength="8000">' + esc(q.prompt || "") + "</textarea></label>" +
      '<label>Type<select name="type">' +
        ["mcq", "multiple_select", "true_false", "short_text", "essay"].map(type =>
          '<option value="' + type + '"' + (q.type === type ? " selected" : "") + ">" + type + "</option>").join("") +
      "</select></label>" +
      '<label>Options (one per line: id|text)<textarea name="options" rows="3" placeholder="a|Option A&#10;b|Option B">' + esc(options) + "</textarea></label>" +
      '<label>Correct option IDs (comma separated)<input name="correct_option_ids" maxlength="200" value="' + esc((q.correct_option_ids || []).join(",")) + '"></label>' +
      '<label>Reference answer / exact match<input name="correct_text" maxlength="4000" value="' + esc(q.correct_text || "") + '"></label>' +
      '<label>Rubric / grading guide<textarea name="rubric" rows="2" maxlength="4000">' + esc(q.rubric || "") + "</textarea></label>" +
      '<label>Explanation<textarea name="explanation" rows="2" maxlength="4000">' + esc(q.explanation || "") + "</textarea></label>" +
      '<label>Tags (comma separated)<input name="tags" maxlength="500" value="' + esc((q.tags || []).join(",")) + '"></label>' +
      '<label>Points<input name="points" type="number" min="0" max="1000" step="0.5" value="' + esc(q.points == null ? 1 : q.points) + '"></label>' +
      '<label class="exams-check"><input name="active" type="checkbox"' + (q.active === false ? "" : " checked") + "> Active</label>" +
      '<div class="exams-form-actions"><button type="submit" class="exams-btn primary">Save question</button></div>' +
      '<div id="exams-q-msg" class="exams-note" role="status"></div>';
  }

  function parseOptions(text){
    return String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
      const split = line.indexOf("|");
      if(split < 0) return { id: line.slice(0, 40), text: line.slice(0, 1000) };
      return { id: line.slice(0, split).trim().slice(0, 40), text: line.slice(split + 1).trim().slice(0, 1000) };
    }).filter(item => item.id && item.text);
  }

  function splitList(value){
    return String(value || "").split(",").map(item => item.trim()).filter(Boolean);
  }

  function sessionExpiry(session){
    return Number((session && (session.effective_expires_at || session.expires_at)) || 0);
  }

  function renderAttempt(){
    const session = state.session, exam = state.exam;
    if(!session || !exam) return "";
    const questions = exam.question_items || [];
    const answers = session.answers || {};
    const remaining = Math.max(0, sessionExpiry(session) - serverNow());
    const mins = Math.floor(remaining / 60000);
    const secs = Math.floor((remaining % 60000) / 1000);
    const active = String(session.state || "") === "active";
    const flags = (session.flags || []).map(flag =>
      '<span class="exams-badge ' + (String(flag).indexOf("suspicious:") === 0 ? "warn" : "err") + '">' + esc(flag) + "</span>").join(" ");

    const questionHtml = questions.map((question, index) => {
      const qid = String(question.id || "");
      const value = answers[question.id];
      let input = "";
      if(question.type === "mcq" || question.type === "true_false"){
        input = (question.options || []).map(option =>
          '<label class="exams-opt"><input type="radio" name="ans_' + esc(qid) + '" value="' + esc(option.id) + '"' +
          (String(value || "") === String(option.id) ? " checked" : "") + (active ? "" : " disabled") + "> " + esc(option.text) + "</label>").join("");
      }else if(question.type === "multiple_select"){
        const chosen = new Set(Array.isArray(value) ? value.map(String) : []);
        input = (question.options || []).map(option =>
          '<label class="exams-opt"><input type="checkbox" name="ans_' + esc(qid) + '" value="' + esc(option.id) + '"' +
          (chosen.has(String(option.id)) ? " checked" : "") + (active ? "" : " disabled") + "> " + esc(option.text) + "</label>").join("");
      }else if(question.type === "essay"){
        input = '<textarea data-ans="' + esc(qid) + '" rows="5" class="exams-answer"' + (active ? "" : " disabled") + ">" + esc(value || "") + "</textarea>";
      }else{
        input = '<input data-ans="' + esc(qid) + '" class="exams-answer" maxlength="4000" value="' + esc(value || "") + '"' + (active ? "" : " disabled") + ">";
      }
      return '<fieldset class="exams-question"><legend><strong>Q' + (index + 1) + ".</strong> " + esc(question.prompt || "") +
        ' <span class="exams-muted">(' + esc(Number(question.points || 0)) + " pts, " + esc(question.type || "") + ")</span></legend>" + input + "</fieldset>";
    }).join("");

    return card(active ? "Active Exam Session" : "Exam Session", "" +
      '<p><strong>' + esc(exam.title || "Exam") + "</strong> · Session <code>" + esc(session.id || "") +
        "</code> · State <code>" + esc(session.state || "") + "</code> · Attempt " + esc(session.attempt_no || 1) + "</p>" +
      '<p><strong>Time remaining:</strong> <span id="exams-countdown" role="timer" aria-live="off">' + mins + ":" + String(secs).padStart(2, "0") + "</span>" +
        (session.paused_at ? ' <span class="exams-badge warn">paused</span>' : "") + "</p>" +
      (flags ? '<p class="exams-note">Flags: ' + flags + "</p>" : "") +
      '<div id="exams-attempt">' + (questionHtml || '<p class="exams-note">No questions are composed into this exam yet.</p>') + "</div>" +
      '<div class="exams-form-actions">' +
        '<button id="exams-save-btn" class="exams-btn"' + (active ? "" : " disabled") + ">Autosave now</button>" +
        '<button id="exams-submit-btn" class="exams-btn primary"' + (active ? "" : " disabled") + ">Submit exam</button>" +
      "</div>" +
      '<p class="exams-note">Answers are saved by the server. Visibility, focus and connectivity changes are logged as untrusted activity signals only.</p>' +
      '<div id="exams-session-msg" class="exams-note" role="status"></div>');
  }

  function collectAnswers(){
    const scope = document.getElementById("exams-attempt");
    if(!scope) return {};
    const out = {};
    scope.querySelectorAll("[data-ans]").forEach(el => { out[el.getAttribute("data-ans")] = el.value; });
    scope.querySelectorAll('input[type="radio"]:checked').forEach(el => {
      const name = el.name || "";
      if(name.indexOf("ans_") === 0) out[name.slice(4)] = el.value;
    });
    const multi = {};
    scope.querySelectorAll('input[type="checkbox"]').forEach(el => {
      const name = el.name || "";
      if(name.indexOf("ans_") !== 0) return;
      const key = name.slice(4);
      multi[key] = multi[key] || [];
      if(el.checked) multi[key].push(el.value);
    });
    return Object.assign(out, multi);
  }

  async function recordActivity(type, detail){
    if(!state.session || String(state.session.state || "") !== "active") return;
    const payload = {
      event_type: type,
      detail: String(detail || "").slice(0, 300),
      client_event_id: "evt_" + state.session.id + "_" + type + "_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8),
      expected_updated_at: state.session.updated_at
    };
    try{
      const result = await fetchJson("/api/exams/sessions/" + encodeURIComponent(state.session.id) + "/events", {
        method: "POST", body: JSON.stringify(payload)
      });
      if(result.item) state.session = result.item;
    }catch(_err){
      /* Activity logging is best-effort and must never interrupt the attempt. */
    }
  }

  async function render(){
    const host = document.getElementById(rootId);
    if(!host) return;
    stopTimers();
    detachListeners();
    const controller = new AbortController();
    state.abort = controller;
    const signal = controller.signal;
    host.innerHTML = '<div class="exams-loading">Loading EXAMS module...</div>';

    try{
      const [health, exams, questions] = await Promise.all([
        fetchJson("/api/exams/health"),
        fetchJson("/api/exams/exams?limit=100"),
        fetchJson("/api/exams/questions?limit=100").catch(() => ({ items: [] }))
      ]);
      if(signal.aborted) return;
      if(Number.isFinite(Number(health.server_now)) && health.server_now){
        state.serverOffset = Number(health.server_now) - Date.now();
      }
      const caps = health.capabilities || [];
      const has = name => caps.indexOf(name) >= 0;
      const canManage = has("exams.manage");
      const canQ = has("exams.question.manage");
      const canGrade = has("exams.grade");
      const canInvigilate = canManage || has("exams.invigilate");
      const canAudit = has("exams.audit.view");
      const canBackup = has("exams.backup");
      const canAnalytics = canManage || canGrade || has("exams.analytics");
      const items = exams.items || [];
      const qItems = questions.items || [];

      const examRows = items.map(exam => "" +
        "<tr><td><strong>" + esc(exam.title || "") + "</strong><div class=\"exams-note\">" + esc(exam.course_code || "") + "</div></td>" +
        "<td>" + esc(exam.status || "draft") + "</td><td>" + esc(Number(exam.duration_minutes || 0)) + " min</td>" +
        "<td>" + esc(Number((exam.questions || []).length || 0)) + "</td><td>" +
        (canManage ? '<button class="exams-btn" data-exam-edit="' + esc(exam.id) + '">Edit</button> ' +
          '<button class="exams-btn danger" data-exam-del="' + esc(exam.id) + '">Archive</button>' : "") +
        (exam.status === "published" ? '<button class="exams-btn primary" data-exam-start="' + esc(exam.id) + '">Start/Resume</button>' : "") +
        "</td></tr>").join("");

      const questionRows = qItems.map(question =>
        "<tr><td><div>" + esc(question.prompt || "") + '</div><div class="exams-note">' + esc(question.type || "") +
        " • " + esc(Number(question.points || 0)) + " pts • <code>" + esc(question.id || "") + "</code></div></td><td>" +
        (canQ ? '<button class="exams-btn" data-q-edit="' + esc(question.id) + '">Edit</button> ' +
          '<button class="exams-btn danger" data-q-del="' + esc(question.id) + '">Deactivate</button>' : "") + "</td></tr>").join("");

      let enrollments = [];
      if(canManage){
        enrollments = await fetchJson("/api/exams/enrollments?limit=200").then(data => data.items || []).catch(() => []);
      }
      if(signal.aborted) return;
      const enrollmentRows = enrollments.map(enrollment =>
        "<tr><td><code>" + esc(enrollment.exam_id || "") + "</code></td><td><code>" + esc(enrollment.actor_id || "") +
        "</code></td><td>" + esc(enrollment.display_name || "") + "</td><td>" + esc(enrollment.role || "candidate") +
        "</td><td>" + esc(enrollment.mnh_role || "") + "</td><td>" +
        (canManage ? '<button class="exams-btn danger" data-enroll-del="' + esc(enrollment.id) + '">Remove</button>' : "") + "</td></tr>").join("");

      const my = await fetchJson("/api/exams/my").catch(() => ({ sessions: [], submissions: [], enrollments: [] }));
      if(signal.aborted) return;
      const myRows = (my.sessions || []).map(session => {
        const submission = (my.submissions || []).find(item => item.session_id === session.id || item.id === session.submission_id);
        const released = submission && submission.results_released !== false;
        const score = released && submission && submission.score ? submission.score.percent : null;
        return "<tr><td><code>" + esc(session.exam_id || "") + '</code><div class="exams-note">Session <code>' + esc(session.id || "") +
          "</code></div></td><td>" + esc(session.state || "") + "</td><td>" + esc(fmt(session.updated_at)) + "</td><td>" +
          (score == null ? "—" : esc(score) + "%") + "</td><td>" +
          (session.state === "active" ? '<button class="exams-btn primary" data-resume-session="' + esc(session.id) +
            '" data-resume-exam="' + esc(session.exam_id || "") + '">Resume</button>' : "") + "</td></tr>";
      }).join("");

      const myEnrollmentRows = (my.enrollments || []).map(enrollment =>
        "<tr><td><code>" + esc(enrollment.exam_id || "") + "</code></td><td>" + esc(enrollment.display_name || "") +
        "</td><td>" + esc(enrollment.role || "candidate") + "</td></tr>").join("");

      const overview = await fetchJson("/api/exams/overview").catch(() => ({ summary: {}, by_exam: [] }));
      const analytics = canAnalytics ? await fetchJson("/api/exams/analytics").catch(() => null) : null;
      if(signal.aborted) return;
      const summary = overview.summary || (analytics && analytics.analytics) || {};
      const byExamRows = (overview.by_exam || (analytics && analytics.by_exam) || []).map(row =>
        "<tr><td>" + esc(row.title || row.exam_id) + "</td><td>" + esc(row.status || "") + "</td><td>" +
        esc(Number(row.enrolled || row.enrolled_candidates || 0)) + "</td><td>" + esc(Number(row.sessions || row.attempts || 0)) +
        "</td><td>" + esc(Number(row.submitted || row.submissions || 0)) + "</td><td>" +
        (row.avg_percent == null ? "—" : esc(row.avg_percent) + "%") + "</td></tr>").join("");

      const limitations = (health.limitations || []).map(item => "<li>" + esc(item) + "</li>").join("");
      host.innerHTML = [
        '<div id="exams-global-msg" class="exams-note" role="status" aria-live="polite"></div>',
        card("EXAMS", "" +
          '<p><strong>Status:</strong> ' + esc(health.status || "") + " · isolated from legacy <code>examinations</code>.</p>" +
          '<p><strong>Identity:</strong> <code>' + esc((health.identity || {}).mnh_role || "public") + "</code> · <code>" +
          esc((health.identity || {}).exam_role || "guest") + "</code> · " + esc((health.identity || {}).actor_id || "public") + "</p>" +
          '<p class="exams-note">The server enforces timing, attempts, autosave revisions, submission idempotency, scoring, result release and permissions. The browser is a presentation client only.</p>' +
          (limitations ? '<ul class="exams-note">' + limitations + "</ul>" : "")),
        card("Analytics Summary", "" +
          '<div class="exams-kpis">' +
          '<div class="exams-kpi"><span>Active sessions</span><strong>' + esc(Number(summary.active_sessions || 0)) + "</strong></div>" +
          '<div class="exams-kpi"><span>Submitted sessions</span><strong>' + esc(Number(summary.submitted_sessions || 0)) + "</strong></div>" +
          '<div class="exams-kpi"><span>Submissions</span><strong>' + esc(Number(summary.submissions || 0)) + "</strong></div>" +
          '<div class="exams-kpi"><span>Enrollments</span><strong>' + esc(Number(summary.enrollments || 0)) + "</strong></div>" +
          "</div>" +
          (canAnalytics ? '<p><a class="exams-btn" href="/api/exams/analytics?format=csv" download>Download CSV</a></p>' : "") +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Exam</th><th>Status</th><th>Enrolled</th><th>Sessions</th><th>Submitted</th><th>Avg %</th></tr></thead>' +
          "<tbody>" + (byExamRows || '<tr><td colspan="6" class="exams-note">No exam analytics yet.</td></tr>') + "</tbody></table></div>"),
        canInvigilate ? card("Invigilation Monitor", "" +
          '<p class="exams-note">Activity signals and staff actions are logged. This is monitoring, not remote proctoring or device lockdown.</p>' +
          '<div class="exams-form-actions"><button id="exams-refresh-invig" class="exams-btn" type="button">Refresh roster</button></div>' +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Session</th><th>Exam</th><th>Actor</th><th>State</th><th>Flags</th><th>Last activity</th><th>Actions</th></tr></thead>' +
          '<tbody id="exams-invig-body"><tr><td colspan="7" class="exams-note">Loading...</td></tr></tbody></table></div>') : "",
        card("My Exam Activity", "" +
          '<h4 class="exams-section-title">Sessions</h4>' +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Exam/Session</th><th>State</th><th>Updated</th><th>Score</th><th>Action</th></tr></thead>' +
          "<tbody>" + (myRows || '<tr><td colspan="5" class="exams-note">No exam sessions yet.</td></tr>') + "</tbody></table></div>" +
          '<h4 class="exams-section-title">Enrollments</h4>' +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Exam</th><th>Name</th><th>Role</th></tr></thead>' +
          "<tbody>" + (myEnrollmentRows || '<tr><td colspan="3" class="exams-note">No enrollments found.</td></tr>') + "</tbody></table></div>"),
        state.session && state.exam ? renderAttempt() : "",
        canManage ? card("Enrollment Management", "" +
          '<form id="exams-enroll-form" class="exams-form exams-form-grid">' +
          '<label>Exam<select name="exam_id" required>' + (items.map(exam => '<option value="' + esc(exam.id) + '">' + esc(exam.title || exam.id) + "</option>").join("") || '<option value="">No exams</option>') + "</select></label>" +
          '<label>Actor ID<input name="actor_id" required maxlength="120" placeholder="mnh:role:sid"></label>' +
          '<label>Display name<input name="display_name" maxlength="120"></label>' +
          '<label>MNH role<input name="mnh_role" maxlength="80" placeholder="executive_dean"></label>' +
          '<label>Enrollment role<select name="role"><option value="candidate">candidate</option><option value="invigilator">invigilator</option><option value="grader">grader</option></select></label>' +
          '<div class="exams-form-actions"><button type="submit" class="exams-btn primary">Save enrollment</button></div>' +
          '<div id="exams-enroll-msg" class="exams-note" role="status"></div></form>' +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Exam</th><th>Actor</th><th>Name</th><th>Role</th><th>MNH role</th><th>Action</th></tr></thead>' +
          "<tbody>" + (enrollmentRows || '<tr><td colspan="6" class="exams-note">No enrollments yet.</td></tr>') + "</tbody></table></div>") : "",
        canQ ? card("Question Bank", "" +
          '<form id="exams-q-form" class="exams-form">' + questionFieldsHtml() + "</form>" +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Question</th><th>Actions</th></tr></thead>' +
          "<tbody>" + (questionRows || '<tr><td colspan="2" class="exams-note">No questions yet.</td></tr>') + "</tbody></table></div>") : "",
        canManage ? card("Create Exam Definition", "" +
          '<form id="exams-create-form" class="exams-form exams-form-grid">' +
          '<label>Title<input name="title" required maxlength="200"></label>' +
          '<label>Course code<input name="course_code" maxlength="80"></label>' +
          '<label>Duration (minutes)<input name="duration_minutes" type="number" min="1" max="600" value="60"></label>' +
          '<label>Status<select name="status"><option value="draft">draft</option><option value="published">published</option><option value="archived">archived</option></select></label>' +
          '<label>Pass mark %<input name="pass_mark_percent" type="number" min="0" max="100" step="0.5" value="50"></label>' +
          '<label>Max attempts<input name="max_attempts" type="number" min="1" max="10" value="1"></label>' +
          '<label>Available from<input name="available_from" type="datetime-local"></label>' +
          '<label>Available until<input name="available_until" type="datetime-local"></label>' +
          '<label>Results release<select name="results_release"><option value="on_return">on return / release</option><option value="immediate">immediate</option><option value="scheduled">scheduled</option><option value="never">never</option></select></label>' +
          '<label>Results release at<input name="results_release_at" type="datetime-local"></label>' +
          '<label class="exams-check"><input name="require_enrollment" type="checkbox"> Require enrollment</label>' +
          '<label class="exams-check"><input name="shuffle_questions" type="checkbox"> Shuffle questions</label>' +
          '<label class="exams-check"><input name="shuffle_options" type="checkbox"> Shuffle options</label>' +
          '<label>Question IDs / points (comma separated: qid:points)<input name="questions" placeholder="q_abc,q_def:5"></label>' +
          '<label>Description<textarea name="description" rows="2" maxlength="4000"></textarea></label>' +
          '<label>Instructions<textarea name="instructions" rows="3" maxlength="8000"></textarea></label>' +
          '<div class="exams-form-actions"><button class="exams-btn primary" type="submit">Create exam</button></div>' +
          '<div id="exams-create-msg" class="exams-note" role="status"></div></form>') :
          card("Access", '<p class="exams-note">Published exams are visible. Starting an attempt requires authentication and may require enrollment.</p>'),
        canGrade ? card("Submission Review / Grading", "" +
          '<p class="exams-note">Objective answers are auto-scored; short text and essay answers can be graded per question. Release controls when candidates see results.</p>' +
          '<div class="exams-form-actions"><button id="exams-refresh-subs" class="exams-btn" type="button">Refresh submissions</button></div>' +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Submission</th><th>Exam</th><th>Actor</th><th>Score</th><th>Status</th><th>Actions</th></tr></thead>' +
          '<tbody id="exams-subs-body"><tr><td colspan="6" class="exams-note">Loading...</td></tr></tbody></table></div>' +
          '<div id="exams-grade-msg" class="exams-note" role="status"></div>') : "",
        canAudit ? card("Audit & Integrity", "" +
          '<p class="exams-note">The audit ledger is append-only and hash-chained. SQLite also blocks UPDATE/DELETE with triggers.</p>' +
          '<div class="exams-form-actions"><button id="exams-audit-verify" class="exams-btn" type="button">Verify chain</button>' +
          '<button id="exams-audit-refresh" class="exams-btn" type="button">Refresh events</button></div>' +
          '<div id="exams-audit-body" class="exams-note">Loading recent events...</div>') : "",
        canBackup ? card("EXAMS Backup & Restore", "" +
          '<p class="exams-note">This export is separate from the generic calendar backup, which always excludes EXAMS. The file contains answer keys and candidate responses; store it securely.</p>' +
          '<div class="exams-form-actions"><button id="exams-backup-download" class="exams-btn" type="button">Download EXAMS backup</button></div>' +
          '<div class="exams-form-grid">' +
          '<label>Import file<input id="exams-backup-file" type="file" accept="application/json,.json"></label>' +
          '<label class="exams-check"><input id="exams-backup-overwrite" type="checkbox"> Overwrite conflicts (admin only)</label>' +
          "</div>" +
          '<div class="exams-form-actions"><button id="exams-backup-import" class="exams-btn primary" type="button">Import backup</button></div>' +
          '<div id="exams-backup-msg" class="exams-note" role="status"></div>') : "",
        card("Exam Definitions", "" +
          '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Title</th><th>Status</th><th>Duration</th><th>Questions</th><th>Actions</th></tr></thead>' +
          "<tbody>" + (examRows || '<tr><td colspan="5" class="exams-note">No exams found.</td></tr>') + "</tbody></table></div>")
      ].filter(Boolean).join("\n");

      wireForms(signal, { items, qItems, enrollments, canGrade });
      if(canInvigilate) loadInvig();
      if(canGrade) loadSubs();
      if(canAudit) loadAudit();
      if(state.session && state.exam) wireAttempt(signal);
    }catch(err){
      if(signal.aborted) return;
      host.innerHTML = card("EXAMS unavailable", '<p class="exams-error">' + esc(err && err.message ? err.message : String(err)) + "</p>");
    }
  }

  function wireForms(signal, context){
    const qForm = document.getElementById("exams-q-form");
    if(qForm){
      qForm.addEventListener("submit", async event => {
        event.preventDefault();
        const msg = document.getElementById("exams-q-msg");
        showMsg("exams-q-msg", "Saving...", false);
        const data = new FormData(qForm);
        const editId = String(qForm.dataset.editId || "");
        let options = parseOptions(data.get("options"));
        if(String(data.get("type") || "") === "true_false" && !options.length){
          options = [{ id: "true", text: "True" }, { id: "false", text: "False" }];
        }
        const payload = {
          prompt: String(data.get("prompt") || "").trim(),
          type: String(data.get("type") || "mcq"),
          options,
          correct_option_ids: splitList(data.get("correct_option_ids")),
          correct_text: String(data.get("correct_text") || ""),
          rubric: String(data.get("rubric") || ""),
          explanation: String(data.get("explanation") || ""),
          tags: splitList(data.get("tags")),
          points: Number(data.get("points") || 1),
          active: !!data.get("active")
        };
        try{
          const url = editId ? "/api/exams/questions/" + encodeURIComponent(editId) : "/api/exams/questions";
          await fetchJson(url, { method: editId ? "PUT" : "POST", body: JSON.stringify(payload) });
          await render();
        }catch(err){
          showMsg("exams-q-msg", err.message || String(err), true);
        }
      }, { signal });
      qForm.querySelectorAll("[data-q-edit]").forEach(() => {});
      document.querySelectorAll("[data-q-edit]").forEach(button => {
        button.addEventListener("click", () => {
          const question = context.qItems.find(item => item.id === button.getAttribute("data-q-edit"));
          const form = document.getElementById("exams-q-form");
          if(!question || !form) return;
          form.dataset.editId = question.id;
          form.querySelector('[name="prompt"]').value = question.prompt || "";
          form.querySelector('[name="type"]').value = question.type || "mcq";
          form.querySelector('[name="options"]').value = (question.options || []).map(option => option.id + "|" + option.text).join("\n");
          form.querySelector('[name="correct_option_ids"]').value = (question.correct_option_ids || []).join(",");
          form.querySelector('[name="correct_text"]').value = question.correct_text || "";
          form.querySelector('[name="rubric"]').value = question.rubric || "";
          form.querySelector('[name="explanation"]').value = question.explanation || "";
          form.querySelector('[name="tags"]').value = (question.tags || []).join(",");
          form.querySelector('[name="points"]').value = String(question.points == null ? 1 : question.points);
          form.querySelector('[name="active"]').checked = question.active !== false;
          const submit = form.querySelector('button[type="submit"]');
          if(submit) submit.textContent = "Update question";
          showMsg("exams-q-msg", "Editing question " + question.id, false);
          form.scrollIntoView({ behavior: "smooth", block: "start" });
        }, { signal });
      });
      document.querySelectorAll("[data-q-del]").forEach(button => {
        button.addEventListener("click", async () => {
          if(!await uiConfirm("Deactivate this question? Historical submissions remain intact.", "Deactivate question", true)) return;
          try{
            await fetchJson("/api/exams/questions/" + encodeURIComponent(button.getAttribute("data-q-del")), { method: "DELETE" });
            await render();
          }catch(err){ showMsg("exams-q-msg", err.message || String(err), true); }
        }, { signal });
      });
    }

    const examForm = document.getElementById("exams-create-form");
    if(examForm){
      examForm.addEventListener("submit", async event => {
        event.preventDefault();
        showMsg("exams-create-msg", "Saving...", false);
        const data = new FormData(examForm);
        const editId = String(examForm.dataset.editId || "");
        const links = String(data.get("questions") || "").split(",").map((item, index) => {
          const parts = item.trim().split(":");
          const link = { question_id: parts[0].trim(), order: index };
          if(parts.length > 1 && Number.isFinite(Number(parts[1]))) link.points = Number(parts[1]);
          return link;
        }).filter(link => link.question_id);
        const existing = editId ? (context.items.find(item => item.id === editId) || {}) : {};
        const payload = Object.assign({}, existing, {
          title: String(data.get("title") || "").trim(),
          course_code: String(data.get("course_code") || "").trim(),
          duration_minutes: Number(data.get("duration_minutes") || 60),
          status: String(data.get("status") || "draft"),
          pass_mark_percent: Number(data.get("pass_mark_percent") || 50),
          max_attempts: Number(data.get("max_attempts") || 1),
          available_from: parseTimeInput(data.get("available_from")),
          available_until: parseTimeInput(data.get("available_until")),
          results_release: String(data.get("results_release") || "on_return"),
          results_release_at: parseTimeInput(data.get("results_release_at")),
          require_enrollment: !!data.get("require_enrollment"),
          shuffle_questions: !!data.get("shuffle_questions"),
          shuffle_options: !!data.get("shuffle_options"),
          description: String(data.get("description") || ""),
          instructions: String(data.get("instructions") || ""),
          questions: links
        });
        try{
          const url = editId ? "/api/exams/exams/" + encodeURIComponent(editId) : "/api/exams/exams";
          await fetchJson(url, { method: editId ? "PUT" : "POST", body: JSON.stringify(payload) });
          await render();
        }catch(err){ showMsg("exams-create-msg", err.message || String(err), true); }
      }, { signal });

      document.querySelectorAll("[data-exam-edit]").forEach(button => {
        button.addEventListener("click", () => {
          const exam = context.items.find(item => item.id === button.getAttribute("data-exam-edit"));
          const form = document.getElementById("exams-create-form");
          if(!exam || !form) return;
          const fields = {
            title: exam.title || "", course_code: exam.course_code || "", duration_minutes: exam.duration_minutes || 60,
            status: exam.status || "draft", pass_mark_percent: exam.pass_mark_percent == null ? 50 : exam.pass_mark_percent,
            max_attempts: exam.max_attempts || 1, available_from: datetimeLocal(exam.available_from),
            available_until: datetimeLocal(exam.available_until), results_release: exam.results_release || "on_return",
            results_release_at: datetimeLocal(exam.results_release_at)
          };
          Object.keys(fields).forEach(name => {
            const field = form.querySelector('[name="' + name + '"]');
            if(field) field.value = String(fields[name]);
          });
          ["require_enrollment", "shuffle_questions", "shuffle_options"].forEach(name => {
            const field = form.querySelector('[name="' + name + '"]');
            if(field) field.checked = !!exam[name];
          });
          form.querySelector('[name="questions"]').value = (exam.questions || []).map(link =>
            link.points == null ? link.question_id : link.question_id + ":" + link.points).join(",");
          form.querySelector('[name="description"]').value = exam.description || "";
          form.querySelector('[name="instructions"]').value = exam.instructions || "";
          form.dataset.editId = exam.id;
          const submit = form.querySelector('button[type="submit"]');
          if(submit) submit.textContent = "Update exam";
          showMsg("exams-create-msg", "Editing exam " + exam.id, false);
          form.scrollIntoView({ behavior: "smooth", block: "start" });
        }, { signal });
      });
      document.querySelectorAll("[data-exam-del]").forEach(button => {
        button.addEventListener("click", async () => {
          if(!await uiConfirm("Archive this exam? Existing sessions and submissions are preserved.", "Archive exam", true)) return;
          try{
            await fetchJson("/api/exams/exams/" + encodeURIComponent(button.getAttribute("data-exam-del")), { method: "DELETE" });
            await render();
          }catch(err){ showMsg("exams-create-msg", err.message || String(err), true); }
        }, { signal });
      });
    }

    const enrollmentForm = document.getElementById("exams-enroll-form");
    if(enrollmentForm){
      enrollmentForm.addEventListener("submit", async event => {
        event.preventDefault();
        const data = new FormData(enrollmentForm);
        const payload = {
          exam_id: String(data.get("exam_id") || ""),
          actor_id: String(data.get("actor_id") || ""),
          display_name: String(data.get("display_name") || ""),
          mnh_role: String(data.get("mnh_role") || ""),
          role: String(data.get("role") || "candidate")
        };
        try{
          await fetchJson("/api/exams/enrollments", { method: "POST", body: JSON.stringify(payload) });
          await render();
        }catch(err){ showMsg("exams-enroll-msg", err.message || String(err), true); }
      }, { signal });
      document.querySelectorAll("[data-enroll-del]").forEach(button => {
        button.addEventListener("click", async () => {
          if(!await uiConfirm("Remove this enrollment? Active attempts are flagged, not erased.", "Remove enrollment", true)) return;
          try{
            await fetchJson("/api/exams/enrollments/" + encodeURIComponent(button.getAttribute("data-enroll-del")), { method: "DELETE" });
            await render();
          }catch(err){ showMsg("exams-global-msg", err.message || String(err), true); }
        }, { signal });
      });
    }

    document.querySelectorAll("[data-exam-start]").forEach(button => {
      button.addEventListener("click", () => startOrResume(button.getAttribute("data-exam-start")), { signal });
    });
    document.querySelectorAll("[data-resume-session]").forEach(button => {
      button.addEventListener("click", () => startOrResume(button.getAttribute("data-resume-exam")), { signal });
    });
    document.querySelectorAll("[data-view-sub]").forEach(button => {
      button.addEventListener("click", () => viewSubmission(button.getAttribute("data-view-sub")), { signal });
    });

    const refreshInvig = document.getElementById("exams-refresh-invig");
    if(refreshInvig) refreshInvig.addEventListener("click", loadInvig, { signal });
    const refreshSubs = document.getElementById("exams-refresh-subs");
    if(refreshSubs) refreshSubs.addEventListener("click", loadSubs, { signal });
    const auditVerify = document.getElementById("exams-audit-verify");
    if(auditVerify) auditVerify.addEventListener("click", verifyAudit, { signal });
    const auditRefresh = document.getElementById("exams-audit-refresh");
    if(auditRefresh) auditRefresh.addEventListener("click", loadAudit, { signal });
    const backupDownload = document.getElementById("exams-backup-download");
    if(backupDownload) backupDownload.addEventListener("click", downloadBackup, { signal });
    const backupImport = document.getElementById("exams-backup-import");
    if(backupImport) backupImport.addEventListener("click", importBackup, { signal });
  }

  async function startOrResume(examId){
    try{
      const started = await fetchJson("/api/exams/sessions/start", {
        method: "POST", body: JSON.stringify({ exam_id: examId })
      });
      const detail = await fetchJson("/api/exams/sessions/" + encodeURIComponent(started.item.id));
      if(Number.isFinite(Number(detail.server_now)) && detail.server_now){
        state.serverOffset = Number(detail.server_now) - Date.now();
      }
      state.session = started.item;
      state.exam = detail.exam;
      state.exam.question_items = detail.exam.question_items || [];
      await render();
    }catch(err){ showMsg("exams-global-msg", err.message || String(err), true); }
  }

  async function viewSubmission(submissionId){
    if(!submissionId) return;
    try{
      const result = await fetchJson("/api/exams/submissions/" + encodeURIComponent(submissionId));
      const submission = result.item || {};
      const exam = result.exam || {};
      const canSeeResult = submission.results_released !== false;
      const lines = [
        "Submission: " + (submission.id || submissionId),
        "Exam: " + (exam.title || submission.exam_id || ""),
        "Actor: " + (submission.actor_id || ""),
        "Status: " + (submission.status || "")
      ];
      if(!canSeeResult){
        lines.push("Results: Not released yet.");
      }else{
        lines.push("Score: " + (submission.score && submission.score.percent != null ? submission.score.percent + "%" : "n/a"));
        lines.push("Feedback: " + (submission.feedback || ""));
        lines.push("", "Answers:");
        const answers = submission.answers || {};
        Object.keys(answers).forEach(key => lines.push("- " + key + ": " + (Array.isArray(answers[key]) ? answers[key].join(", ") : String(answers[key]))));
      }
      await openDialog({
        title: "Submission detail",
        bodyHtml: '<pre class="exams-detail"></pre>',
        okText: "Close",
        showCancel: false,
        onMount: dialog => { dialog.querySelector(".exams-detail").textContent = lines.join("\n"); }
      });
    }catch(err){ showMsg("exams-global-msg", err.message || String(err), true); }
  }

  async function loadSubs(){
    const body = document.getElementById("exams-subs-body");
    if(!body) return;
    try{
      const result = await fetchJson("/api/exams/submissions?limit=100");
      const submissions = result.items || [];
      body.innerHTML = submissions.map(submission =>
        "<tr><td><code>" + esc(submission.id || "") + '</code><div class="exams-note">' + esc(fmt(submission.submitted_at || submission.updated_at)) +
        "</div></td><td><code>" + esc(submission.exam_id || "") + "</code></td><td><code>" + esc(submission.actor_id || "") +
        "</code></td><td>" + esc(submission.score && submission.score.percent != null ? submission.score.percent + "%" : "n/a") +
        "</td><td>" + esc(submission.status || "") + "</td><td>" +
        '<button class="exams-btn" data-view-sub="' + esc(submission.id) + '">View</button> ' +
        '<button class="exams-btn primary" data-grade-sub="' + esc(submission.id) + '">Grade</button></td></tr>').join("") ||
        '<tr><td colspan="6" class="exams-note">No submissions yet.</td></tr>';
      body.querySelectorAll("[data-view-sub]").forEach(button => button.addEventListener("click", () => viewSubmission(button.getAttribute("data-view-sub"))));
      body.querySelectorAll("[data-grade-sub]").forEach(button => button.addEventListener("click", () => gradeSubmission(button.getAttribute("data-grade-sub"), submissions)));
    }catch(err){
      body.innerHTML = '<tr><td colspan="6" class="exams-error">' + esc(err.message || String(err)) + "</td></tr>";
    }
  }

  async function gradeSubmission(submissionId, submissions){
    const submission = (submissions || []).find(item => item.id === submissionId);
    if(!submission) return;
    let review;
    try{ review = await fetchJson("/api/exams/submissions/" + encodeURIComponent(submissionId) + "/review"); }
    catch(err){ showMsg("exams-grade-msg", err.message || String(err), true); return; }
    const details = (submission.score && submission.score.details) || [];
    const detailMap = {};
    details.forEach(detail => { detailMap[detail.question_id] = detail; });
    const questionRows = (review.questions || []).map((question, index) => {
      const detail = detailMap[question.id] || {};
      const earned = detail.earned_points == null ? 0 : detail.earned_points;
      const rubric = (review.rubric_notes || {})[question.id] || "";
      return '<div class="exams-grade-row"><label><strong>Q' + (index + 1) + ":</strong> " + esc(question.prompt || "") +
        "</label>" + (rubric ? '<div class="exams-note">Rubric: ' + esc(rubric) + "</div>" : "") +
        '<div class="exams-note">Auto: ' + esc(detail.auto_earned_points == null ? "n/a" : detail.auto_earned_points) +
        " / " + esc(question.points || 0) + "</div>" +
        '<input class="exams-grade-points" data-question="' + esc(question.id) + '" type="number" min="0" max="' + esc(question.points || 100000) +
        '" step="0.5" value="' + esc(earned) + '">' +
        '<textarea class="exams-grade-feedback" data-question="' + esc(question.id) + '" rows="2" maxlength="4000" placeholder="Feedback">' +
        esc(detail.feedback || "") + "</textarea></div>";
    }).join("");
    const bodyHtml = "" +
      '<p class="exams-note"><code>' + esc(submission.id || "") + "</code> · " + esc(submission.actor_id || "") + "</p>" +
      '<label>Status<select id="exams-grade-status"><option value="submitted">submitted</option><option value="graded">graded</option><option value="returned">returned</option></select></label>' +
      '<label>Overall feedback<textarea id="exams-grade-feedback" rows="3" maxlength="8000">' + esc(submission.feedback || "") + "</textarea></label>" +
      '<label class="exams-check"><input id="exams-grade-release" type="checkbox"> Release result to candidate (applies when status is returned)</label>' +
      '<div class="exams-grade-list">' + (questionRows || '<p class="exams-note">No questions found for this exam.</p>') + "</div>";

    await openDialog({
      title: "Grade submission",
      bodyHtml,
      okText: "Save grade",
      wide: true,
      onMount: dialog => {
        dialog.querySelector("#exams-grade-status").value = ["submitted", "graded", "returned"].indexOf(submission.status) >= 0 ? submission.status : "graded";
      },
      onOk: async dialog => {
        const questionScores = Array.from(dialog.querySelectorAll(".exams-grade-points")).map(input => ({
          question_id: input.getAttribute("data-question"),
          earned_points: Number(input.value || 0),
          feedback: String((dialog.querySelector('textarea.exams-grade-feedback[data-question="' + input.getAttribute("data-question") + '"]') || {}).value || "")
        }));
        const payload = {
          status: String(dialog.querySelector("#exams-grade-status").value || "graded"),
          feedback: String(dialog.querySelector("#exams-grade-feedback").value || ""),
          question_scores: questionScores,
          expected_updated_at: submission.updated_at,
          release: !!dialog.querySelector("#exams-grade-release").checked
        };
        const result = await fetchJson("/api/exams/submissions/" + encodeURIComponent(submissionId) + "/grade", {
          method: "POST", body: JSON.stringify(payload)
        });
        if(result.conflict) throw new Error("This submission changed elsewhere. Refresh and retry.");
        showMsg("exams-grade-msg", "Submission graded: " + (result.item && result.item.score ? result.item.score.percent + "%" : "saved"), false);
        await loadSubs();
        return true;
      }
    });
  }

  async function loadInvig(){
    const body = document.getElementById("exams-invig-body");
    if(!body) return;
    try{
      const result = await fetchJson("/api/exams/sessions/monitor?limit=100");
      body.innerHTML = (result.items || []).map(session => {
        const flags = (session.flags || []).map(flag => '<span class="exams-badge warn">' + esc(flag) + "</span>").join(" ");
        const notes = (session.notes || []).slice(-2).map(note => esc(note.note || "")).join("; ");
        return "<tr><td><code>" + esc(session.id || "") + "</code></td><td><code>" + esc(session.exam_id || "") +
          "</code></td><td><code>" + esc(session.actor_id || "") + '</code></td><td><span class="exams-badge ' +
          (session.state === "active" ? "warn" : session.state === "submitted" ? "ok" : "err") + '">' + esc(session.state || "") +
          "</span></td><td>" + (flags || "—") + "</td><td>" + esc(fmt(session.last_activity_at)) +
          (notes ? '<div class="exams-note">' + notes + "</div>" : "") + "</td><td>" +
          '<button class="exams-btn" data-invig-action="extend_time" data-invig-id="' + esc(session.id) + '" data-updated="' + esc(session.updated_at) + '">+ time</button> ' +
          '<button class="exams-btn" data-invig-action="' + (session.paused_at ? "resume" : "pause") + '" data-invig-id="' + esc(session.id) + '" data-updated="' + esc(session.updated_at) + '">' + (session.paused_at ? "Resume" : "Pause") + "</button> " +
          '<button class="exams-btn" data-invig-action="flag" data-invig-id="' + esc(session.id) + '" data-updated="' + esc(session.updated_at) + '">Flag</button> ' +
          '<button class="exams-btn danger" data-invig-action="invalidate" data-invig-id="' + esc(session.id) + '" data-updated="' + esc(session.updated_at) + '">Invalidate</button></td></tr>';
      }).join("") || '<tr><td colspan="7" class="exams-note">No sessions.</td></tr>';
      body.querySelectorAll("[data-invig-action]").forEach(button => {
        button.addEventListener("click", () => invigilationAction(
          button.getAttribute("data-invig-id"),
          button.getAttribute("data-invig-action"),
          Number(button.getAttribute("data-updated") || 0)
        ));
      });
    }catch(err){
      body.innerHTML = '<tr><td colspan="7" class="exams-error">' + esc(err.message || String(err)) + "</td></tr>";
    }
  }

  async function invigilationAction(sessionId, action, updatedAt){
    const needsReason = action === "flag" || action === "invalidate" || action === "note";
    await openDialog({
      title: "Invigilation: " + action.replace("_", " "),
      bodyHtml: "" +
        (action === "extend_time" ? '<label>Minutes<input id="exams-invig-minutes" type="number" min="1" max="120" value="5"></label>' : "") +
        '<label>Reason / note<textarea id="exams-invig-reason" rows="2" maxlength="1000"' + (needsReason ? " required" : "") + "></textarea></label>" +
        '<p class="exams-note">This action is written to the audit ledger with the previous and new session state.</p>',
      okText: "Apply",
      danger: action === "invalidate",
      onOk: async dialog => {
        const payload = {
          action,
          reason: String(dialog.querySelector("#exams-invig-reason").value || ""),
          expected_updated_at: updatedAt
        };
        if(action === "extend_time") payload.minutes = Number(dialog.querySelector("#exams-invig-minutes").value || 0);
        const result = await fetchJson("/api/exams/sessions/" + encodeURIComponent(sessionId) + "/actions", {
          method: "POST", body: JSON.stringify(payload)
        });
        if(result.conflict) throw new Error("Session changed elsewhere. Refresh the roster and retry.");
        await loadInvig();
        return true;
      }
    });
  }

  async function loadAudit(){
    const body = document.getElementById("exams-audit-body");
    if(!body) return;
    try{
      const result = await fetchJson("/api/exams/audit?limit=20");
      const events = result.items || [];
      body.innerHTML = '<div class="exams-table-wrap"><table class="exams-table"><thead><tr><th>Seq</th><th>Time</th><th>Action</th><th>Actor</th><th>Session</th></tr></thead><tbody>' +
        (events.map(event => "<tr><td>" + esc(event.seq) + "</td><td>" + esc(fmt(event.at)) + "</td><td>" + esc(event.action) +
          "</td><td><code>" + esc(event.actor_id || "") + "</code></td><td><code>" + esc(event.session_id || "") + "</code></td></tr>").join("") ||
          '<tr><td colspan="5" class="exams-note">No audit events.</td></tr>') + "</tbody></table></div>";
    }catch(err){ body.innerHTML = '<p class="exams-error">' + esc(err.message || String(err)) + "</p>"; }
  }

  async function verifyAudit(){
    try{
      const result = await fetchJson("/api/exams/audit/verify");
      showMsg("exams-audit-body", result.ok ? "Chain verified: " + result.verified + " events." : "Chain verification failed at seq " + result.broken_at_seq, !result.ok);
    }catch(err){ showMsg("exams-audit-body", err.message || String(err), true); }
  }

  async function downloadBackup(){
    try{
      const payload = await fetchJson("/api/exams/backup");
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "MNH-EXAMS-backup-" + new Date().toISOString().slice(0, 10) + ".json";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      showMsg("exams-backup-msg", "Backup exported with SHA-256 " + payload.integrity.sha256, false);
    }catch(err){ showMsg("exams-backup-msg", err.message || String(err), true); }
  }

  async function importBackup(){
    const input = document.getElementById("exams-backup-file");
    const file = input && input.files && input.files[0];
    if(!file){ showMsg("exams-backup-msg", "Choose a backup JSON file first.", true); return; }
    try{
      const text = await file.text();
      const payload = JSON.parse(text);
      payload.overwrite_conflicts = !!(document.getElementById("exams-backup-overwrite") || {}).checked;
      const result = await fetchJson("/api/exams/restore", { method: "POST", body: JSON.stringify(payload) });
      showMsg("exams-backup-msg", "Restored " + result.restored + " EXAMS records.", false);
      await render();
    }catch(err){ showMsg("exams-backup-msg", err.message || String(err), true); }
  }

  function wireAttempt(signal){
    const session = state.session;
    const saving = async () => {
      if(!state.session || String(state.session.state || "") !== "active" || state.saving) return;
      state.saving = true;
      try{
        const payload = {
          answers: collectAnswers(),
          client_save_id: "save_" + Date.now() + "_" + Math.random().toString(36).slice(2),
          seq: Number(state.session.save_seq || 0) + 1,
          expected_updated_at: state.session.updated_at
        };
        const result = await fetchJson("/api/exams/sessions/" + encodeURIComponent(state.session.id) + "/autosave", {
          method: "POST", body: JSON.stringify(payload)
        });
        if(result.item) state.session = result.item;
        if(result.conflict){
          showMsg("exams-session-msg", "The session changed elsewhere. Review the latest server state before saving again.", true);
        }else if(result.item && !result.ignored && !result.expired && !result.duplicate){
          showMsg("exams-session-msg", "Saved at " + new Date().toLocaleTimeString(), false);
        }
      }catch(err){ showMsg("exams-session-msg", err.message || String(err), true); }
      finally{ state.saving = false; }
    };

    const saveButton = document.getElementById("exams-save-btn");
    if(saveButton) saveButton.addEventListener("click", saving, { signal });
    const submitButton = document.getElementById("exams-submit-btn");
    if(submitButton) submitButton.addEventListener("click", async () => {
      if(!await uiConfirm("Submit this exam? Submission is final for the current attempt.", "Submit exam")) return;
      submitButton.disabled = true;
      try{
        const result = await fetchJson("/api/exams/sessions/" + encodeURIComponent(state.session.id) + "/submit", {
          method: "POST",
          body: JSON.stringify({
            answers: collectAnswers(),
            client_submit_id: "sub_" + state.session.id,
            expected_updated_at: state.session.updated_at
          })
        });
        if(result.conflict){
          if(result.item) state.session = result.item;
          throw new Error("The session changed elsewhere. Review the latest state and submit again.");
        }
        state.session = result.item;
        showMsg("exams-session-msg", "Submitted. Score: " + (result.submission && result.submission.score ? result.submission.score.percent + "%" : "pending release"), false);
        await render();
      }catch(err){
        submitButton.disabled = false;
        showMsg("exams-session-msg", err.message || String(err), true);
      }
    }, { signal });

    document.addEventListener("visibilitychange", () => {
      recordActivity(document.hidden ? "tab_hidden" : "tab_visible", document.visibilityState);
    }, { signal });
    window.addEventListener("blur", () => recordActivity("focus_lost", "window blur"), { signal });
    window.addEventListener("focus", () => recordActivity("focus_gained", "window focus"), { signal });
    window.addEventListener("offline", () => recordActivity("offline", "network offline"), { signal });
    window.addEventListener("online", () => recordActivity("reconnected", "network online"), { signal });

    state.timer = setInterval(() => {
      const el = document.getElementById("exams-countdown");
      if(!el || !state.session) return;
      const remaining = Math.max(0, sessionExpiry(state.session) - serverNow());
      const mins = Math.floor(remaining / 60000);
      const secs = Math.floor((remaining % 60000) / 1000);
      el.textContent = mins + ":" + String(secs).padStart(2, "0");
      if(remaining <= 0){
        stopTimers();
        showMsg("exams-session-msg", "Session expired. The server will reject late submissions.", true);
      }
    }, 1000);

    if(String(session.state || "") === "active"){
      state.autosave = setInterval(saving, 30000);
      state.heartbeat = setInterval(async () => {
        if(!state.session || String(state.session.state || "") !== "active") return;
        try{
          const result = await fetchJson("/api/exams/sessions/" + encodeURIComponent(state.session.id) + "/heartbeat", { method: "POST" });
          if(result.item) state.session = result.item;
        }catch(_err){ /* heartbeat is advisory */ }
      }, 20000);
    }
  }

  window.MNHExams = { render };
})();
