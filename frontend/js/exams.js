(function(){
  "use strict";
  const rootId = "exams-body";
  const state = {session:null, exam:null, timer:null};
  function esc(s){ return String(s==null?"":s).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
  async function fetchJson(url, opts={}){
    const res = await fetch(url, Object.assign({credentials:"same-origin"}, opts, {headers:Object.assign({"Accept":"application/json","Content-Type":"application/json"}, opts.headers||{})}));
    const data = await res.json().catch(()=>({}));
    if(!res.ok) throw new Error(data.error || data.detail || ("HTTP "+res.status));
    return data;
  }
  function card(title, bodyHtml){ return `<section class="exams-card"><h3>${esc(title)}</h3>${bodyHtml}</section>`; }
  function fmt(ms){ try{ return ms?new Date(ms).toLocaleString():""; }catch(_e){ return ""; } }
  function stopTimer(){ if(state.timer){ clearInterval(state.timer); state.timer=null; } }
  function showMsg(id, text, isErr){ const el=document.getElementById(id); if(!el) return; el.className=isErr?'exams-error':'exams-note'; el.textContent=text||''; }
  function uiConfirm(message, okText='Confirm', danger=false){
    return new Promise(resolve=>{
      const wrap=document.createElement('div'); wrap.className='exams-modal-backdrop';
      wrap.innerHTML=`<div class="exams-modal" role="dialog" aria-modal="true"><p class="exams-modal-msg"></p><div class="exams-form-actions"><button type="button" class="exams-btn exams-modal-cancel">Cancel</button><button type="button" class="exams-btn ${danger?'danger':'primary'} exams-modal-ok"></button></div></div>`;
      wrap.querySelector('.exams-modal-msg').textContent=message;
      wrap.querySelector('.exams-modal-ok').textContent=okText;
      const done=(v)=>{ wrap.remove(); resolve(v); };
      wrap.querySelector('.exams-modal-cancel').addEventListener('click',()=>done(false));
      wrap.querySelector('.exams-modal-ok').addEventListener('click',()=>done(true));
      wrap.addEventListener('click',(e)=>{ if(e.target===wrap) done(false); });
      document.body.appendChild(wrap);
      wrap.querySelector('.exams-modal-ok').focus();
    });
  }

  function questionFieldsHtml(){
    return `
      <label>Prompt<textarea name="prompt" required rows="3" maxlength="8000"></textarea></label>
      <label>Type<select name="type"><option value="mcq">mcq</option><option value="multiple_select">multiple_select</option><option value="true_false">true_false</option><option value="short_text">short_text</option><option value="essay">essay</option></select></label>
      <label>Options (one per line, format: id|text; for true_false use true|True and false|False)<textarea name="options" rows="3" placeholder="a|Option A&#10;b|Option B"></textarea></label>
      <label>Correct option IDs (comma separated)<input name="correct_option_ids" placeholder="a"></label>
      <label>Correct text (for short_text/essay exact-match placeholder)<input name="correct_text" maxlength="4000"></label>
      <label>Points<input name="points" type="number" min="0" max="1000" step="0.5" value="1"></label>
      <div class="exams-form-actions"><button type="submit" class="exams-btn primary">Save question</button></div>
      <div id="exams-q-msg" class="exams-note"></div>`;
  }

  function parseOptions(text){
    return String(text||"").split(/\r?\n/).map(l=>l.trim()).filter(Boolean).map(line=>{
      const i=line.indexOf("|"); if(i<0) return {id:line.slice(0,40), text:line.slice(0,1000)};
      return {id:line.slice(0,i).trim().slice(0,40), text:line.slice(i+1).trim().slice(0,1000)};
    }).filter(x=>x.id && x.text);
  }

  function renderAttempt(host){
    const sess = state.session, exam = state.exam;
    if(!sess || !exam) return '';
    const qs = exam.question_items || [];
    const answers = sess.answers || {};
    const remaining = Math.max(0, Number(sess.expires_at||0) - Date.now());
    const mins = Math.floor(remaining/60000), secs = Math.floor((remaining%60000)/1000);
    const qHtml = qs.map((q,idx)=>{
      const qid = esc(q.id||'');
      const val = answers[q.id];
      let input = '';
      if(q.type==='mcq' || q.type==='true_false'){
        input = (q.options||[]).map(o=>`<label class="exams-opt"><input type="radio" name="ans_${qid}" value="${esc(o.id)}" ${String(val||'')===String(o.id)?'checked':''}> ${esc(o.text)}</label>`).join('');
      } else if(q.type==='multiple_select'){
        const set = new Set(Array.isArray(val)?val.map(String):[]);
        input = (q.options||[]).map(o=>`<label class="exams-opt"><input type="checkbox" name="ans_${qid}" value="${esc(o.id)}" ${set.has(String(o.id))?'checked':''}> ${esc(o.text)}</label>`).join('');
      } else if(q.type==='essay'){
        input = `<textarea data-ans="${qid}" rows="5" class="exams-answer">${esc(val||'')}</textarea>`;
      } else {
        input = `<input data-ans="${qid}" class="exams-answer" value="${esc(val||'')}">`;
      }
      return `<div class="exams-question"><div class="exams-qhead"><strong>Q${idx+1}.</strong> ${esc(q.prompt||'')} <span class="exams-note">(${Number(q.points||0)} pts, ${esc(q.type||'')})</span></div>${input}</div>`;
    }).join('');
    return card(sess.state==='active' ? 'Active Exam Session' : 'Exam Session', `
      <p><strong>${esc(exam.title||'Exam')}</strong> · Session <code>${esc(sess.id||'')}</code> · State <code>${esc(sess.state||'')}</code></p>
      <p><strong>Time remaining:</strong> <span id="exams-countdown">${mins}:${String(secs).padStart(2,'0')}</span></p>
      <div id="exams-attempt">${qHtml || '<p class="exams-note">No questions composed into this exam yet.</p>'}</div>
      <div class="exams-form-actions">
        <button id="exams-save-btn" class="exams-btn">Autosave now</button>
        <button id="exams-submit-btn" class="exams-btn primary">Submit exam</button>
      </div>
      <div id="exams-session-msg" class="exams-note"></div>
    `);
  }

  function collectAnswers(){
    const out = {};
    document.querySelectorAll('[data-ans]').forEach(el=>{ out[el.getAttribute('data-ans')] = el.value; });
    document.querySelectorAll('input[type=radio]:checked').forEach(el=>{ const name=el.name||''; if(name.startsWith('ans_')) out[name.slice(4)] = el.value; });
    const multi = {};
    document.querySelectorAll('input[type=checkbox]').forEach(el=>{ const name=el.name||''; if(!name.startsWith('ans_')) return; const k=name.slice(4); multi[k]=multi[k]||[]; if(el.checked) multi[k].push(el.value); });
    Object.assign(out, multi);
    return out;
  }

  async function render(){
    const host = document.getElementById(rootId);
    if(!host) return;
    stopTimer();
    host.innerHTML = `<div class="exams-loading">Loading EXAMS module...</div>`;
    try {
      const [health, exams, questions] = await Promise.all([
        fetchJson('/api/exams/health'),
        fetchJson('/api/exams/exams?limit=100'),
        fetchJson('/api/exams/questions?limit=100').catch(()=>({items:[],count:0}))
      ]);
      const canManage = !!health.capabilities?.includes('exams.manage');
      const canQ = !!health.capabilities?.includes('exams.question.manage');
      const items = exams.items || [];
      const qItems = questions.items || [];

      const examRows = items.map(x=>`
        <tr>
          <td><strong>${esc(x.title||'')}</strong><div class="exams-note">${esc(x.course_code||'')}</div></td>
          <td>${esc(x.status||'draft')}</td><td>${Number(x.duration_minutes||0)} min</td><td>${Number((x.questions||[]).length||0)}</td>
          <td>${canManage?`<button class="exams-btn" data-exam-edit="${esc(x.id)}">Edit</button> <button class="exams-btn danger" data-exam-del="${esc(x.id)}">Delete</button>`:''}
              ${x.status==='published'?`<button class="exams-btn primary" data-exam-start="${esc(x.id)}">Start/Resume</button>`:''}
          </td>
        </tr>`).join('');

      const qRows = qItems.map(q=>`<tr><td><div>${esc(q.prompt||'')}</div><div class="exams-note">${esc(q.type||'')} • ${Number(q.points||0)} pts • ${esc(q.id||'')}</div></td><td>${canQ?`<button class="exams-btn" data-q-edit="${esc(q.id)}">Edit</button> <button class="exams-btn danger" data-q-del="${esc(q.id)}">Delete</button>`:''}</td></tr>`).join('');
      let enrollments = [];
      if (canManage) {
        enrollments = await fetchJson('/api/exams/enrollments?limit=200').then(d=>d.items||[]).catch(()=>[]);
      }
      const enrollRows = enrollments.map(e=>`<tr><td><code>${esc(e.exam_id||'')}</code></td><td><code>${esc(e.actor_id||'')}</code></td><td>${esc(e.role||'candidate')}</td><td>${esc(e.status||'active')}</td></tr>`).join('');

      const my = await fetchJson('/api/exams/my').catch(()=>({sessions:[],submissions:[],enrollments:[]}));
      const myRows = (my.sessions||[]).map(s=>{
        const sub = (my.submissions||[]).find(x=>x.session_id===s.id || x.id===s.submission_id);
        const score = sub?.score?.percent;
        const canResume = s.state === 'active';
        return `<tr><td><code>${esc(s.exam_id||'')}</code><div class="exams-note">Session ${esc(s.id||'')}</div></td><td>${esc(s.state||'')}</td><td>${esc(fmt(s.updated_at))}</td><td>${score==null?'—':esc(score)+'%'}</td><td>${canResume?`<button class="exams-btn primary" data-resume-session="${esc(s.id)}" data-resume-exam="${esc(s.exam_id||'')}">Resume</button>`:''}</td></tr>`;
      }).join('');
      const myEnrollRows = (my.enrollments||[]).map(e=>`<tr><td><code>${esc(e.exam_id||'')}</code></td><td>${esc(e.role||'candidate')}</td><td>${esc(e.status||'active')}</td></tr>`).join('');

            const overview = await fetchJson('/api/exams/overview').catch(()=>({summary:{},by_exam:[],counts:{}}));
      const analytics = (canManage || canGrade || !!health.capabilities?.includes('exams.analytics')) ? await fetchJson('/api/exams/analytics').catch(()=>null) : null;
      const canInvigilate = (canManage || !!health.capabilities?.includes('exams.invigilate'));
      const summary = overview.summary || analytics?.analytics || {};
      const byExamRows = (overview.by_exam||analytics?.by_exam||[]).map(r=>`<tr><td>${esc(r.title||r.exam_id)}</td><td>${esc(r.status||'')}</td><td>${Number(r.enrolled||0)}</td><td>${Number(r.sessions||0)}</td><td>${Number(r.submitted||0)}</td><td>${r.avg_percent==null?'—':esc(r.avg_percent)+'%'}</td></tr>`).join('');
      host.innerHTML = [
        `<div id="exams-global-msg" class="exams-note" role="status" aria-live="polite"></div>`,
        card('EXAMS', `
          <p><strong>Status:</strong> ${esc(health.status)} • isolated from legacy <code>examinations</code>.</p>
          <p><strong>Identity:</strong> <code>${esc(health.identity?.mnh_role||'public')}</code> • <code>${esc(health.identity?.exam_role||'guest')}</code></p>
          <p class="exams-note">Exams, question bank, enrollment, session delivery, autosave/submit, basic grading, and basic analytics are available. Invigilation is limited to session monitoring.</p>
        `),
        card('Analytics Summary', `
          <div class="exams-kpis">
            <div class="exams-kpi"><span>Active sessions</span><strong>${Number(summary.active_sessions||0)}</strong></div>
            <div class="exams-kpi"><span>Submitted sessions</span><strong>${Number(summary.submitted_sessions||0)}</strong></div>
            <div class="exams-kpi"><span>Submissions</span><strong>${Number(summary.submissions||0)}</strong></div>
            <div class="exams-kpi"><span>Enrollments</span><strong>${Number(summary.enrollments||0)}</strong></div>
          </div>
          <table class="exams-table"><thead><tr><th>Exam</th><th>Status</th><th>Enrolled</th><th>Sessions</th><th>Submitted</th><th>Avg %</th></tr></thead>
          <tbody>${byExamRows || '<tr><td colspan="6" class="exams-note">No exam analytics yet.</td></tr>'}</tbody></table>
        `),
        canInvigilate ? card('Invigilation Monitor', `
          <p class="exams-note">Live session states for monitoring. This is monitoring only, not full proctoring/lockdown.</p>
          <table class="exams-table"><thead><tr><th>Session</th><th>Exam</th><th>Actor</th><th>State</th><th>Updated</th></tr></thead>
          <tbody id="exams-invig-body"><tr><td colspan="5" class="exams-note">Loading...</td></tr></tbody></table>
        `) : '',
        card('My Exam Activity', `
          <h4 style="margin:.2rem 0 .4rem">Sessions</h4>
          <table class="exams-table"><thead><tr><th>Exam/Session</th><th>State</th><th>Updated</th><th>Score</th><th>Action</th></tr></thead>
          <tbody>${myRows || '<tr><td colspan="5" class="exams-note">No exam sessions yet.</td></tr>'}</tbody></table>
          <h4 style="margin:.8rem 0 .4rem">Enrollments</h4>
          <table class="exams-table"><thead><tr><th>Exam</th><th>Role</th><th>Status</th></tr></thead>
          <tbody>${myEnrollRows || '<tr><td colspan="3" class="exams-note">No enrollments found.</td></tr>'}</tbody></table>
        `),
        state.session && state.exam ? renderAttempt(host) : '',
        canManage ? card('Enrollment Management', `
          <form id="exams-enroll-form" class="exams-form exams-form-grid">
            <label>Exam<select name="exam_id" required>${items.map(x=>`<option value="${esc(x.id)}">${esc(x.title||x.id)}</option>`).join('') || '<option value="">No exams</option>'}</select></label>
            <label>Actor ID<input name="actor_id" required placeholder="MNH:student"></label>
            <label>Role<select name="role"><option value="candidate">candidate</option><option value="invigilator">invigilator</option></select></label>
            <label>Status<select name="status"><option value="active">active</option><option value="inactive">inactive</option></select></label>
            <div class="exams-form-actions"><button type="submit" class="exams-btn primary">Save enrollment</button></div>
            <div id="exams-enroll-msg" class="exams-note"></div>
          </form>
          <table class="exams-table"><thead><tr><th>Exam</th><th>Actor</th><th>Role</th><th>Status</th></tr></thead><tbody>${enrollRows || '<tr><td colspan="4" class="exams-note">No enrollments yet.</td></tr>'}</tbody></table>
        `) : '',
        canQ ? card('Question Bank', `
          <form id="exams-q-form" class="exams-form">${questionFieldsHtml()}</form>
          <table class="exams-table"><thead><tr><th>Question</th><th>Actions</th></tr></thead><tbody>${qRows || '<tr><td colspan="2" class="exams-note">No questions yet.</td></tr>'}</tbody></table>
        `) : '',
        canManage ? card('Create Exam Definition', `
          <form id="exams-create-form" class="exams-form">
            <label>Title<input name="title" required maxlength="200"></label>
            <label>Course code<input name="course_code" maxlength="80"></label>
            <label>Duration (minutes)<input name="duration_minutes" type="number" min="1" max="600" value="60"></label>
            <label>Status<select name="status"><option value="draft">draft</option><option value="published">published</option><option value="archived">archived</option></select></label>
            <label>Question IDs (comma separated, from question bank)<input name="questions" placeholder="q_xxx,q_yyy"></label>
            <label>Description<textarea name="description" rows="2"></textarea></label>
            <label>Instructions<textarea name="instructions" rows="3"></textarea></label>
            <div class="exams-form-actions"><button class="exams-btn primary" type="submit">Create exam</button></div>
            <div id="exams-create-msg" class="exams-note"></div>
          </form>
        `) : card('Access', `<p class="exams-note">Published exams are visible. Starting a session requires authentication. Management requires mapped EXAMS role.</p>`),
        canGrade ? card('Submission Review / Grading', `
          <p class="exams-note">View submitted attempts and apply manual score/feedback overrides. Objective auto-scoring remains basic.</p>
          <div class="exams-form-actions"><button id="exams-refresh-subs" class="exams-btn" type="button">Refresh submissions</button></div>
          <table class="exams-table"><thead><tr><th>Submission</th><th>Exam</th><th>Actor</th><th>Score</th><th>Status</th><th>Action</th></tr></thead>
          <tbody id="exams-subs-body"><tr><td colspan="6" class="exams-note">Loading...</td></tr></tbody></table>
          <div id="exams-grade-msg" class="exams-note"></div>
        `) : '',
        card('Exam Definitions', `
          <table class="exams-table"><thead><tr><th>Title</th><th>Status</th><th>Duration</th><th>Questions</th><th>Actions</th></tr></thead>
          <tbody>${examRows || '<tr><td colspan="5" class="exams-note">No exams found.</td></tr>'}</tbody></table>
        `)
      ].filter(Boolean).join('\n');

      const qForm = document.getElementById('exams-q-form');
      if(qForm) qForm.addEventListener('submit', async (e)=>{
        e.preventDefault(); const msg=document.getElementById('exams-q-msg'); msg.className='exams-note'; msg.textContent='Saving...';
        const fd=new FormData(qForm);
        const editId=String(qForm.dataset.editId||'').trim();
        const type=String(fd.get('type')||'mcq');
        let options=parseOptions(fd.get('options'));
        if(type==='true_false' && options.length===0) options=[{id:'true',text:'True'},{id:'false',text:'False'}];
        const payload={prompt:String(fd.get('prompt')||'').trim(), type, options, correct_option_ids:String(fd.get('correct_option_ids')||'').split(',').map(s=>s.trim()).filter(Boolean), correct_text:String(fd.get('correct_text')||''), points:Number(fd.get('points')||1), explanation:'', tags:[], active:true};
        try{
          if(editId) await fetchJson('/api/exams/questions/'+encodeURIComponent(editId),{method:'PUT',body:JSON.stringify(payload)});
          else await fetchJson('/api/exams/questions',{method:'POST',body:JSON.stringify(payload)});
          qForm.reset(); delete qForm.dataset.editId; const sb=qForm.querySelector('button[type="submit"]'); if(sb) sb.textContent='Save question';
          await render();
        }catch(err){ msg.className='exams-error'; msg.textContent=err.message||String(err); }
      });
      host.querySelectorAll('[data-q-edit]').forEach(btn=>btn.addEventListener('click', ()=>{
        const id=btn.getAttribute('data-q-edit'); const q=qItems.find(x=>x.id===id); const form=document.getElementById('exams-q-form');
        if(!q||!form) return;
        form.dataset.editId=id;
        form.querySelector('[name="prompt"]').value=q.prompt||'';
        form.querySelector('[name="type"]').value=q.type||'mcq';
        form.querySelector('[name="options"]').value=(q.options||[]).map(o=>`${o.id}|${o.text}`).join('\n');
        form.querySelector('[name="correct_option_ids"]').value=(q.correct_option_ids||[]).join(',');
        form.querySelector('[name="correct_text"]').value=q.correct_text||'';
        form.querySelector('[name="points"]').value=String(q.points??1);
        const sb=form.querySelector('button[type="submit"]'); if(sb) sb.textContent='Update question';
        showMsg('exams-q-msg','Editing question '+id,false);
        form.scrollIntoView({behavior:'smooth',block:'start'});
      }));

      host.querySelectorAll('[data-q-del]').forEach(btn=>btn.addEventListener('click', async ()=>{ if(!await uiConfirm('Delete this question? This cannot be undone.','Delete question',true)) return; try{ await fetchJson('/api/exams/questions/'+encodeURIComponent(btn.getAttribute('data-q-del')), {method:'DELETE'}); await render(); }catch(err){ showMsg('exams-q-msg', err.message||String(err), true); } }));

      const cForm=document.getElementById('exams-create-form');
      if(cForm) cForm.addEventListener('submit', async (e)=>{
        e.preventDefault(); const msg=document.getElementById('exams-create-msg');
        const fd=new FormData(cForm);
        const editId=String(cForm.dataset.editId||'').trim();
        msg.className='exams-note'; msg.textContent=editId?'Updating...':'Creating...';
        const qids=String(fd.get('questions')||'').split(',').map(s=>s.trim()).filter(Boolean).map((id,i)=>({question_id:id,order:i}));
        const existing = editId ? (items.find(x=>x.id===editId)||{}) : {};
        const payload={...existing, title:String(fd.get('title')||'').trim(), course_code:String(fd.get('course_code')||'').trim(), duration_minutes:Number(fd.get('duration_minutes')||60), status:String(fd.get('status')||'draft'), description:String(fd.get('description')||''), instructions:String(fd.get('instructions')||''), pass_mark_percent:Number(existing.pass_mark_percent??50), max_attempts:Number(existing.max_attempts??1), shuffle_questions:!!existing.shuffle_questions, shuffle_options:!!existing.shuffle_options, questions:qids};
        try{
          if(editId){ await fetchJson('/api/exams/exams/'+encodeURIComponent(editId),{method:'PUT',body:JSON.stringify(payload)}); }
          else { await fetchJson('/api/exams/exams',{method:'POST',body:JSON.stringify(payload)}); }
          cForm.reset(); delete cForm.dataset.editId; const submit=cForm.querySelector('button[type="submit"]'); if(submit) submit.textContent='Create exam';
          await render();
        }catch(err){ msg.className='exams-error'; msg.textContent=err.message||String(err); }
      });

      host.querySelectorAll('[data-exam-del]').forEach(btn=>btn.addEventListener('click', async ()=>{ if(!await uiConfirm('Delete this exam definition? Existing sessions/submissions may become orphaned.','Delete exam',true)) return; try{ await fetchJson('/api/exams/exams/'+encodeURIComponent(btn.getAttribute('data-exam-del')), {method:'DELETE'}); await render(); }catch(err){ showMsg('exams-create-msg', err.message||String(err), true); } }));
      const eForm = document.getElementById('exams-enroll-form');
      if(eForm) eForm.addEventListener('submit', async (e)=>{
        e.preventDefault();
        const fd=new FormData(eForm); const msg=document.getElementById('exams-enroll-msg');
        const payload={exam_id:String(fd.get('exam_id')||''), actor_id:String(fd.get('actor_id')||''), role:String(fd.get('role')||'candidate'), status:String(fd.get('status')||'active')};
        try{ await fetchJson('/api/exams/enrollments',{method:'POST',body:JSON.stringify(payload)}); await render(); }catch(err){ if(msg){msg.className='exams-error'; msg.textContent=err.message||String(err);} }
      });
      host.querySelectorAll('[data-exam-edit]').forEach(btn=>btn.addEventListener('click', async ()=>{
        const id=btn.getAttribute('data-exam-edit'); const item=items.find(x=>x.id===id); if(!item) return;
        const form=document.getElementById('exams-create-form');
        if(!form){ showMsg('exams-global-msg','Create form unavailable.',true); return; }
        form.querySelector('[name="title"]').value=item.title||'';
        form.querySelector('[name="course_code"]').value=item.course_code||'';
        form.querySelector('[name="duration_minutes"]').value=String(item.duration_minutes||60);
        form.querySelector('[name="status"]').value=item.status||'draft';
        form.querySelector('[name="questions"]').value=(item.questions||[]).map(q=>q.question_id).join(',');
        form.querySelector('[name="description"]').value=item.description||'';
        form.querySelector('[name="instructions"]').value=item.instructions||'';
        form.dataset.editId=id;
        const submit=form.querySelector('button[type="submit"]'); if(submit) submit.textContent='Update exam';
        showMsg('exams-create-msg','Editing exam '+id+'. Update fields and click "Update exam".',false);
        form.scrollIntoView({behavior:'smooth',block:'start'});
      }));

      async function startOrResumeExam(id){
        const started=await fetchJson('/api/exams/sessions/start',{method:'POST',body:JSON.stringify({exam_id:id})});
        const sess=started.item;
        const full=await fetchJson('/api/exams/exams/'+encodeURIComponent(id));
        state.session=sess; state.exam=full.item; await render();
      }
      host.querySelectorAll('[data-exam-start]').forEach(btn=>btn.addEventListener('click', async ()=>{
        try{ await startOrResumeExam(btn.getAttribute('data-exam-start')); }catch(err){ showMsg('exams-global-msg', err.message||String(err), true); }
      }));
      host.querySelectorAll('[data-resume-session]').forEach(btn=>btn.addEventListener('click', async ()=>{
        try{ await startOrResumeExam(btn.getAttribute('data-resume-exam')); }catch(err){ showMsg('exams-global-msg', err.message||String(err), true); }
      }));
      host.querySelectorAll('[data-view-sub]').forEach(btn=>btn.addEventListener('click', async ()=>{
        const id=btn.getAttribute('data-view-sub'); if(!id) return;
        try{
          const res=await fetchJson('/api/exams/submissions/'+encodeURIComponent(id));
          const sub=res.item||{}; const exam=res.exam||{};
          const lines=[`Submission: ${sub.id||id}`,`Exam: ${exam.title||sub.exam_id||''}`,`Actor: ${sub.actor_id||''}`,`Status: ${sub.status||''}`,`Score: ${sub.score?.percent ?? 'n/a'}% (${sub.score?.earned_points ?? 'n/a'}/${sub.score?.total_points ?? 'n/a'})`,`Feedback: ${sub.feedback||''}`,'','Answers:'];
          const ans=sub.answers||{};
          Object.keys(ans).forEach(k=>lines.push(`- ${k}: ${Array.isArray(ans[k])?ans[k].join(', '):String(ans[k])}`));
          await uiConfirm(lines.join('\n'),'Close');
        }catch(err){ showMsg('exams-global-msg', err.message||String(err), true); }
      }));


      async function loadSubs(){
        const body=document.getElementById('exams-subs-body'); if(!body) return;
        try{
          const res=await fetchJson('/api/exams/submissions?limit=100');
          const items=res.items||[];
          body.innerHTML = items.map(sub=>`<tr><td><code>${esc(sub.id||'')}</code><div class="exams-note">${esc(fmt(sub.submitted_at||sub.updated_at))}</div></td><td><code>${esc(sub.exam_id||'')}</code></td><td><code>${esc(sub.actor_id||'')}</code></td><td>${esc(sub.score?.percent ?? 'n/a')}%</td><td>${esc(sub.status||'')}</td><td><button class="exams-btn" data-grade-sub="${esc(sub.id||'')}">Grade</button></td></tr>`).join('') || '<tr><td colspan="6" class="exams-note">No submissions yet.</td></tr>';
          body.querySelectorAll('[data-grade-sub]').forEach(btn=>btn.addEventListener('click', async ()=>{
            const id=btn.getAttribute('data-grade-sub'); const sub=items.find(x=>x.id===id); if(!sub) return;
            const wrap=document.createElement('div'); wrap.className='exams-modal-backdrop';
            wrap.innerHTML=`<div class="exams-modal" role="dialog" aria-modal="true"><h3 style="margin-top:0">Grade submission</h3>
              <p class="exams-note"><code>${esc(id)}</code> · ${esc(sub.actor_id||'')} · ${esc(sub.exam_id||'')}</p>
              <label>Percent score<input id="exams-grade-pct" type="number" min="0" max="100" step="0.01" value="${esc(sub.score?.percent ?? '')}"></label>
              <label>Status<select id="exams-grade-status"><option value="submitted">submitted</option><option value="graded">graded</option><option value="returned">returned</option></select></label>
              <label>Feedback<textarea id="exams-grade-feedback" rows="4">${esc(sub.feedback||'')}</textarea></label>
              <div class="exams-form-actions"><button type="button" class="exams-btn" id="exams-grade-cancel">Cancel</button><button type="button" class="exams-btn primary" id="exams-grade-save">Save grade</button></div>
              <div id="exams-grade-modal-msg" class="exams-note"></div>
            </div>`;
            document.body.appendChild(wrap);
            wrap.querySelector('#exams-grade-status').value=['submitted','graded','returned'].includes(sub.status)?sub.status:'graded';
            const close=()=>wrap.remove();
            wrap.querySelector('#exams-grade-cancel').addEventListener('click', close);
            wrap.addEventListener('click',(e)=>{ if(e.target===wrap) close(); });
            wrap.querySelector('#exams-grade-save').addEventListener('click', async ()=>{
              const pct=wrap.querySelector('#exams-grade-pct').value;
              const payload={feedback:String(wrap.querySelector('#exams-grade-feedback').value||''), status:String(wrap.querySelector('#exams-grade-status').value||'graded')};
              if(String(pct).trim()!==''){ const n=Number(pct); if(!Number.isNaN(n)) payload.percent=n; }
              try{ await fetchJson('/api/exams/submissions/'+encodeURIComponent(id)+'/grade',{method:'POST',body:JSON.stringify(payload)}); close(); showMsg('exams-grade-msg','Submission graded.',false); await loadSubs(); }catch(err){ const m=wrap.querySelector('#exams-grade-modal-msg'); m.className='exams-error'; m.textContent=err.message||String(err); }
            });
          }));
        }catch(err){ body.innerHTML = `<tr><td colspan="6" class="exams-error">${esc(err.message||String(err))}</td></tr>`; }
      }
      const refreshSubs=document.getElementById('exams-refresh-subs'); if(refreshSubs) refreshSubs.addEventListener('click', loadSubs);
      if(document.getElementById('exams-subs-body')) loadSubs();
      async function loadInvig(){
        const body=document.getElementById('exams-invig-body'); if(!body) return;
        try{
          const res=await fetchJson('/api/exams/sessions?limit=100');
          const items=res.items||[];
          body.innerHTML = items.map(sx=>`<tr><td><code>${esc(sx.id||'')}</code></td><td><code>${esc(sx.exam_id||'')}</code></td><td><code>${esc(sx.actor_id||'')}</code></td><td><span class="exams-badge ${sx.state==='active'?'warn':sx.state==='submitted'?'ok':'err'}">${esc(sx.state||'')}</span></td><td>${esc(fmt(sx.updated_at))}</td></tr>`).join('') || '<tr><td colspan="5" class="exams-note">No sessions.</td></tr>';
        }catch(err){ body.innerHTML=`<tr><td colspan="5" class="exams-error">${esc(err.message||String(err))}</td></tr>`; }
      }
      if(document.getElementById('exams-invig-body')) loadInvig();
      if(state.session && state.exam){
        const saveBtn=document.getElementById('exams-save-btn');
        const submitBtn=document.getElementById('exams-submit-btn');
        const msg=document.getElementById('exams-session-msg');
        async function doSave(silent){
          if(!state.session) return;
          try{
            const payload={answers:collectAnswers(), client_save_id:'save_'+Date.now()+'_'+Math.random().toString(36).slice(2), seq:Number(state.session.save_seq||0)+1};
            const res=await fetchJson('/api/exams/sessions/'+encodeURIComponent(state.session.id)+'/autosave',{method:'POST',body:JSON.stringify(payload)});
            state.session=res.item;
            if(!silent && msg){ msg.className='exams-note'; msg.textContent='Saved at '+new Date().toLocaleTimeString(); }
          }catch(err){ if(msg){ msg.className='exams-error'; msg.textContent=err.message||String(err); } }
        }
        if(saveBtn) saveBtn.addEventListener('click', ()=>doSave(false));
        if(submitBtn) submitBtn.addEventListener('click', async ()=>{
          if(!await uiConfirm('Submit this exam? Submission is final for the current attempt.','Submit exam')) return;
          submitBtn.disabled=true;
          try{
            const res=await fetchJson('/api/exams/sessions/'+encodeURIComponent(state.session.id)+'/submit',{method:'POST',body:JSON.stringify({answers:collectAnswers(), client_submit_id:'sub_'+state.session.id})});
            state.session=res.item;
            if(msg){ msg.className='exams-note'; msg.textContent='Submitted. Score: '+(res.submission?.score?.percent ?? 'n/a')+'%'; }
            await render();
          }catch(err){ submitBtn.disabled=false; if(msg){ msg.className='exams-error'; msg.textContent=err.message||String(err); } }
        });
        stopTimer();
        state.timer=setInterval(()=>{
          const el=document.getElementById('exams-countdown');
          if(!el || !state.session) return;
          const rem=Math.max(0, Number(state.session.expires_at||0)-Date.now());
          const m=Math.floor(rem/60000), s=Math.floor((rem%60000)/1000);
          el.textContent=m+':'+String(s).padStart(2,'0');
          if(rem<=0){ stopTimer(); if(msg){ msg.className='exams-error'; msg.textContent='Session expired. Save/submit may be rejected by server.'; } }
        },1000);
      }

    } catch (err) {
      host.innerHTML = card('EXAMS unavailable', `<p class="exams-error">${esc(err.message||String(err))}</p>`);
    }
  }
  window.MNHExams = { render };
})();
