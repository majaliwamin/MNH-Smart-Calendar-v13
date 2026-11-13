const times=["08:00 – 10:00","10:00 – 12:00","12:00 – 13:30","13:30 – 15:30","15:30 – 17:30","17:30 – 19:00","19:00 – 21:00"];
// ---- Academic week state: the shared week model drives every date shown in this file ----
const WK=window.MNHWeek;
let weekOffset=0;
let dates=WK.dateLabels(0);
const LEGACY_ROW_MAP={0:0,1:1,2:2,3:2,4:3,5:4,6:5,7:6};
const days=["Monday","Tuesday","Wednesday","Thursday","Friday"];
let modules={
 "MIPN 8100":{title:"Medical Imaging in Pregnancy and Neonates",facilitator:"Not specified"},
 "ARMN – 8100":{title:"Antimicrobial Resistance in Maternal & Neonatal Health",facilitator:"G Bandawe"},
 "PNIM-8100":{title:"Pregnancy and Neonatal Immunology",facilitator:"D Mzinza"}
};
const JOURNAL={code:"Journal Club",title:"Journal Club",facilitator:"",colour:"#263D5C",recurring:true};
const tbody=document.getElementById("calendar-body");
const thead=document.getElementById("calendar-head");
const statusEl=document.getElementById("status");
const key="phd_mnh_weekly_calendar_v3";
const legacyKey="phd_mnh_weekly_calendar_v2";
let currentRole="student";
let moduleUnsubscribe=null;
let state={theme:"dark",cells:{}};
let editingUnlocked=false;
let analyticsUnlocked=false;
let securityIntent="edit";
let activeCell=null;
let selectedTime=-1;

function cellKey(r,c){return `${r}_${c}`;}
function isJournal(r,c){return r===2&&c===1;}
function parseClock(value){const m=/^(\d{1,2}):(\d{2})$/.exec(String(value||""));if(!m)return null;const h=+m[1],n=+m[2];return h<24&&n<60?h*60+n:null;}
function clockText(minutes){return `${String(Math.floor(minutes/60)).padStart(2,"0")}:${String(minutes%60).padStart(2,"0")}`;}
function parseRange(value){const m=/^\s*(\d{1,2}:\d{2})\s*(?:–|-|to)\s*(\d{1,2}:\d{2})\s*$/.exec(String(value||""));return m?{startTime:m[1],endTime:m[2]}:null;}
function defaultRange(row){const parts=parseRange(times[row]||"");return parts||{startTime:"08:00",endTime:"10:00"};}
function facilitatorFor(code){
 const configured=String(modules[code]?.facilitator||"").trim();
 const configuredId=String(modules[code]?.facilitatorId||"").trim();
 if((!configured||configured==="Not specified")&&!configuredId)return "";
 const normalise=name=>String(name||"").toLowerCase().replace(/\b(professor|prof|doctor|dr|mr|mrs|ms)\.?\b/g,"").replace(/[^a-z0-9]+/g," ").trim();
 const wanted=normalise(configured);
 const match=facilitatorRecords.find(x=>String(x.id)===configuredId||String(x.id)===configured||normalise(x.data?.name)===wanted||(wanted&&normalise(x.data?.name).endsWith(wanted)));
 return String(match?.data?.name||(configured==="Not specified"?"":configured));
}
function getSessionEntries(){
 const result=[];
 Object.entries(state.cells||{}).forEach(([id,data])=>{
  if(!data||typeof data!=="object")return;
  let dayIndex,startTime,endTime,rowIndex=-1;
  const legacy=/^(\d+)_(\d+)$/.exec(id);
  if(legacy){rowIndex=+legacy[1];dayIndex=+legacy[2];if(dayIndex<0||dayIndex>=5||rowIndex<0||rowIndex>=times.length)return;}
  else {dayIndex=Number(data.dayIndex);if(!Number.isInteger(dayIndex)||dayIndex<0||dayIndex>=5)return;}
  const fromLabel=parseRange(data.timeLabel);
  const fallback=legacy?defaultRange(rowIndex):{startTime:"08:00",endTime:"10:00"};
  startTime=String(data.startTime||fromLabel?.startTime||fallback.startTime);
  endTime=String(data.endTime||fromLabel?.endTime||fallback.endTime);
  const start=parseClock(startTime),end=parseClock(endTime);
  if(start===null||end===null||end<=start)return;
  const label=String(data.code||data.text||data.title||"Scheduled session");
  if(label==="Journal Club"&&dayIndex===1)return;
  result.push({id,dayIndex,c:dayIndex,r:rowIndex,label,title:String(data.title||label),sub:String(modules[data.code]?.title||""),facilitator:facilitatorFor(data.code)||String(data.facilitator||""),startTime,endTime,startMinutes:start,endMinutes:end,mins:end-start,timeLabel:`${startTime} – ${endTime}`,data});
 });
 result.push({id:"journal-club-fixed",dayIndex:1,c:1,r:2,label:"Journal Club",title:"Journal Club",sub:"Recurring academic discussion",facilitator:"",startTime:"13:00",endTime:"14:00",startMinutes:780,endMinutes:840,mins:60,timeLabel:"13:00 – 14:00",data:{code:"Journal Club",title:"Journal Club",recurring:true}});
 return result.sort((a,b)=>a.dayIndex-b.dayIndex||a.startMinutes-b.startMinutes);
}
function getEntry(r,c){return getSessionEntries().find(x=>x.dayIndex===c&&x.r===r)?.data||{};}
function setEditing(enabled){
 editingUnlocked=enabled;
 updateRoleNav();
 ["save","backup","import","edit-header"].forEach(id=>{const b=document.getElementById(id);if(b)b.disabled=!enabled;});
 document.getElementById("settings").disabled=false;
 const add=document.getElementById("weekly-add-session");if(add)add.hidden=!enabled;
 statusEl.className="status "+(enabled?"ok":"");
 statusEl.textContent=enabled?"Editing enabled. Changes can now be made.":"";
}
function showDialog(id){
 const el=document.getElementById(id),card=el.querySelector(".dialog-card")||el.querySelector(".call-card");
 if(card&&!card.querySelector(".dialog-close")){
  const close=document.createElement("button");close.type="button";close.className="dialog-close";close.setAttribute("aria-label","Close dialog");close.textContent="×";
  close.addEventListener("click",()=>id==="call-dialog"?stopRing():hideDialog(id));card.prepend(close);
 }
 el.classList.add("open");el.setAttribute("aria-hidden","false");
}
function hideDialog(id){const el=document.getElementById(id);if(el){el.classList.remove("open");el.setAttribute("aria-hidden","true");}}
function contrastColour(hex){
 const n=parseInt(hex.replace("#",""),16);
 const lum=(0.299*(n>>16)+0.587*((n>>8)&255)+0.114*(n&255))/255;
 return lum>0.58?"#172033":"#F7F8FA";
}
function applyCellColour(td,area,colour){td.style.background=colour;area.style.background=colour;area.style.color=contrastColour(colour);}
let facilitatorRecords=[];
function refreshModuleSelect(){
 const select=document.getElementById("module-select"),chosen=select.value;
 select.innerHTML='<option value="">Choose a module…</option>';
 Object.keys(modules).sort().forEach(code=>{const o=document.createElement("option");o.value=code;o.textContent=code+" — "+modules[code].title;select.appendChild(o);});
 if(chosen&&modules[chosen])select.value=chosen;
}
function onModules(snap){
 const next=Object.create(null);snap.docs.forEach(d=>{const v=d.data()||{};if(d.id&&v.title)next[d.id]={title:String(v.title),facilitator:String(v.facilitator||"Not specified"),facilitatorId:String(v.facilitatorId||""),semesterTargetSessions:v.semesterTargetSessions??null,semesterTargetHours:v.semesterTargetHours??null};});
 if(Object.keys(next).length)modules=next;
 refreshModuleSelect();
 if(currentView==="modules")renderModules();
 build();
}
async function addSharedModule(code,title,facilitatorId,targets={}){
 code=String(code||"").trim().slice(0,40);title=String(title||"").trim().slice(0,160);facilitatorId=String(facilitatorId||"").trim();
 if(!code||!title){statusEl.className="status error";statusEl.textContent="Enter both a module code and title.";return;}
 if(!/^[A-Za-z0-9][A-Za-z0-9_. –-]{0,39}$/.test(code)){statusEl.className="status error";statusEl.textContent="Use letters, numbers, spaces, dots or hyphens in the module code.";return;}
 if(Object.prototype.hasOwnProperty.call(modules,code)){statusEl.className="status error";statusEl.textContent="That module code already exists.";return;}
 try{
  const facilitator=facilitatorRecords.find(item=>String(item.id)===facilitatorId);
  const data={title,facilitator:facilitator?String(facilitator.data.name):"Not specified",facilitatorId:facilitator?facilitatorId:"",semesterTargetSessions:targets.semesterTargetSessions,semesterTargetHours:targets.semesterTargetHours,updatedAt:Date.now()};
  if(cloud)await cloud.doc("modules/"+code).set(data);
  else await window.mnhApi.request("PUT","/api/doc/modules/"+encodeURIComponent(code),data);
  statusEl.className="status ok";statusEl.textContent="Module added and shared with all users.";
 }catch(e){writeFailed(e);}
}
function updateModuleDetails(code){
 const box=document.getElementById("module-details");
 const labelField=document.getElementById("module-label"),lecturerField=document.getElementById("session-lecturer");
 const lecturer=code?facilitatorFor(code):"";
 // The activity label is the module code; the lecturer below it comes from the Facilitators directory.
 if(labelField){labelField.value=code||"";labelField.readOnly=!!code;labelField.placeholder=code?"":"Type a custom activity name";}
 if(lecturerField)lecturerField.value=code?(lecturer||"Not assigned"):"";
 if(modules[code]){const m=modules[code];box.textContent="";const strong=document.createElement("strong");strong.textContent=code;box.append(strong,document.createElement("br"),document.createTextNode(m.title),document.createElement("br"),document.createTextNode("Lecturer: "+(lecturer||"Not assigned")));}
 else if(code==="Journal Club")box.textContent="Journal Club · Every Tuesday, 13:00–14:00";
 else box.textContent=code?"This activity is not in the Modules directory yet.":"Select a module to fill the activity label (module code) and its lecturer.";
}
function openModuleDialog(dayIndex,startTime,entry){
 if(!editingUnlocked){statusEl.className="status";statusEl.textContent="Unlock editing to make changes.";return;}
 const existing=entry||null;
 const id=existing?.id||null;
 const start=startTime||"08:00";
 const end=existing?.endTime||(parseClock(start)+120<=1440?clockText(parseClock(start)+120):"23:59");
 activeCell={id,dayIndex,startTime:start,endTime:end};
 document.getElementById("session-day").value=String(dayIndex);
 document.getElementById("session-start").value=existing?.startTime||start;
 document.getElementById("session-end").value=existing?.endTime||end;
 document.getElementById("module-select").value=existing?.data?.moduleCode||existing?.data?.code||"";
 const existingCode=existing?.data?.moduleCode||existing?.data?.code||"";
 document.getElementById("module-label").value=existingCode||(existing?String(existing.title||existing.label||""):"");
 document.getElementById("session-lecturer").value=existingCode?(facilitatorFor(existingCode)||"Not assigned"):"";
 document.getElementById("module-mode").value=existing?.data?.mode||"unspecified";
 document.getElementById("module-colour").value=existing?.data?.colour||"";
 document.getElementById("session-status").value=existing?.data?.status||"scheduled";
 document.getElementById("delete-module").style.display=id?"inline-block":"none";
 updateModuleDetails(document.getElementById("module-select").value);
 showDialog("module-dialog");
}
function showSessionDetails(entry){
 if(!entry)return;
 const d=new Date(WEEK_START[0],WEEK_START[1],WEEK_START[2]+entry.dayIndex);
 const dateText=`${days[entry.dayIndex]} ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
 const details=document.getElementById("details-content");details.textContent="";
 const lines=[entry.label,entry.title!==entry.label?entry.title:"",dateText,`Time: ${entry.startTime} – ${entry.endTime}`,entry.facilitator?`Lecturer: ${entry.facilitator}`:"Lecturer: Not assigned",`Status: ${entry.data?.status||"Not recorded"}`,`Delivery: ${entry.data?.mode||"Not specified"}`].filter(Boolean);
 lines.forEach((line,i)=>{const div=document.createElement("div");if(i===0){const strong=document.createElement("strong");strong.textContent=line;div.appendChild(strong);}else div.textContent=line;details.appendChild(div);});
 document.getElementById("edit-details").style.display=(editingUnlocked&&entry.id!=="journal-club-fixed")?"inline-block":"none";
 document.getElementById("edit-details").onclick=()=>{hideDialog("details-dialog");openModuleDialog(entry.dayIndex,entry.startTime,entry);};
 showDialog("details-dialog");
}
function showEntryDetails(r,c){const entry=getSessionEntries().find(x=>x.dayIndex===c&&(x.r===r||x.id===`${r}_${c}`));showSessionDetails(entry);}
const LUNCH_START=12*60,LUNCH_END=13*60+30;
function build(){
 thead.innerHTML="";tbody.innerHTML="";
 const entries=getSessionEntries();
 let lunchDone=false;
 const appendLunchRow=()=>{
  lunchDone=true;
  const tr=document.createElement("tr");tr.className="lunch-row";tr.dataset.startTime=clockText(LUNCH_START);
  const th=document.createElement("th");th.className="time lunch-time";th.scope="row";th.textContent=clockText(LUNCH_START)+"–"+clockText(LUNCH_END);tr.appendChild(th);
  const td=document.createElement("td");td.colSpan=days.length;td.className="lunch-cell";
  const clashes=entries.filter(x=>x.startMinutes<LUNCH_END&&x.endMinutes>LUNCH_START).map(x=>`${days[x.dayIndex]} ${x.label} ${x.startTime}–${x.endTime}`);
  const label=document.createElement("span");label.className="lunch-label";label.textContent="Lunch Break";
  td.setAttribute("role","note");td.setAttribute("aria-label","Lunch Break 12:00 to 13:30");
  if(clashes.length)td.title="Sessions overlapping the lunch break (kept, shown in their own rows): "+clashes.join("; ");
  td.appendChild(label);tr.appendChild(td);tbody.appendChild(tr);
 };
 // Left column shows complete intervals: a row with sessions uses their real interval, otherwise the default programme slot.
 const defaultSlots=times.map(t=>parseRange(t)).filter(Boolean);
 const intervalFor=start=>{
  const rowEntries=entries.filter(x=>x.startTime===start);
  if(rowEntries.length){let end=rowEntries[0].endTime;rowEntries.forEach(x=>{if(parseClock(x.endTime)>parseClock(end))end=x.endTime;});return `${start}–${end}`;}
  const slot=defaultSlots.find(s=>s.startTime===start);
  return slot?`${slot.startTime}–${slot.endTime}`:start;
 };
 // The merged lunch row already represents the 12:00–13:30 band, so that slot is not repeated as a separate row.
 const slotStarts=defaultSlots.filter(s=>parseClock(s.startTime)!==LUNCH_START).map(s=>s.startTime);
 const starts=[...new Set([...slotStarts,...entries.map(x=>x.startTime)])].sort((a,b)=>parseClock(a)-parseClock(b));
 const hr=document.createElement("tr"),corner=document.createElement("th");corner.className="corner";corner.textContent="Time";hr.appendChild(corner);
 days.forEach((day,c)=>{const th=document.createElement("th");th.className="daycell";th.scope="col";th.innerHTML=`<span class="day"><span class="dfull">${day}</span><span class="dshort">${day.slice(0,3)}</span></span><span class="date">${dates[c]}</span>`;hr.appendChild(th);});thead.appendChild(hr);
 starts.forEach((start,index)=>{
  if(!lunchDone&&parseClock(start)>=LUNCH_START)appendLunchRow();
  const tr=document.createElement("tr");tr.dataset.startTime=start;
  const interval=intervalFor(start);
  const th=document.createElement("th");th.className="time"+(selectedTime===index?" highlight":"");th.scope="row";th.textContent=interval;th.tabIndex=0;th.setAttribute("role","button");th.setAttribute("aria-label",`Highlight the ${interval} row`);
  const toggle=()=>{selectedTime=selectedTime===index?-1:index;tbody.querySelectorAll("th.time:not(.lunch-time)").forEach((node,i)=>node.classList.toggle("highlight",i===selectedTime));};th.addEventListener("click",toggle);th.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle();}});tr.appendChild(th);
  days.forEach((day,dayIndex)=>{
   const td=document.createElement("td"),entry=entries.find(x=>x.dayIndex===dayIndex&&x.startTime===start);td.dataset.cellKey=`${start}_${dayIndex}`;
   const box=document.createElement("div");box.className="cell";const area=document.createElement("button");area.type="button";area.className="activity";area.setAttribute("aria-label",entry?`${day}: ${entry.label}${entry.facilitator?`, lecturer ${entry.facilitator}`:""}`:`Add session on ${day} at ${start}`);
   if(entry){const chosenColour=entry.data?.colour;if(chosenColour){area.style.backgroundColor=chosenColour;area.style.borderColor=chosenColour;area.style.color=contrastColour(chosenColour);}const name=document.createElement("span");name.className="activity-name";name.textContent=entry.label;area.appendChild(name);if(entry.facilitator){const lecturer=document.createElement("span");lecturer.className="activity-lecturer";lecturer.textContent=entry.facilitator;area.appendChild(lecturer);}if(entry.sub){const title=document.createElement("span");title.className="activity-module-title";title.textContent=entry.sub;area.appendChild(title);}area.title=[entry.title,entry.facilitator].filter(Boolean).join(" · ");area.addEventListener("click",()=>showSessionDetails(entry));}
   else {area.classList.add("empty-activity");area.textContent=editingUnlocked?"+":"";area.addEventListener("click",()=>requestEditing(()=>openModuleDialog(dayIndex,start,null)));}
   box.appendChild(area);td.appendChild(box);tr.appendChild(td);
  });tbody.appendChild(tr);
 });
 if(!lunchDone)appendLunchRow();
}
function remapLegacyCells(cells){
 const out={};
 Object.entries(cells).forEach(([k,v])=>{
  const [r,c]=k.split("_").map(Number);
  if(!(r in LEGACY_ROW_MAP))return;
  const nr=LEGACY_ROW_MAP[r],nk=cellKey(nr,c);
  if(nk==="2_1"&&r!==3)return;           // Tuesday 12:00–13:30 belongs to the recurring Journal Club
  if(r===3&&nk in out&&nk!=="2_1")return; // old 12:00–13:00 entry wins over old 13:00–14:00
  out[nk]=v;
 });
 return out;
}
function load(){
 try{
  let raw=localStorage.getItem(key);let legacy=false;
  if(!raw){raw=localStorage.getItem(legacyKey);legacy=!!raw;}
  if(raw){
   const parsed=JSON.parse(raw);
   if(legacy)parsed.cells=remapLegacyCells(parsed.cells||{});
   state={...state,...parsed,cells:{...(parsed.cells||{})}};
   Object.entries(state.cells).forEach(([id,v])=>{if((/^\d+_\d+$/.test(id)&&+id.split("_")[1]>=5)||(Number.isFinite(Number(v?.dayIndex))&&Number(v?.dayIndex)>=5))delete state.cells[id];});
   // Migrate known legacy free-text module labels into structured entries.
   Object.entries(state.cells).forEach(([k,v])=>{
    if(!v||v.code||!v.text)return;
    const text=v.text.trim();
    if(modules[text])state.cells[k]={...v,code:text};
   });
  }
 }catch(e){statusEl.textContent="Saved browser data could not be read. Existing browser data has not been overwritten.";statusEl.className="status error";}
 try{const tp=localStorage.getItem(themeKey);if(tp)state.theme=tp;}catch(e){}
 state.theme=normaliseTheme(state.theme);
 if(Object.keys(SEED_CELLS).length&&SEED_STAMP>(state.stamp||0)){state.cells={...SEED_CELLS,...state.cells};state.stamp=SEED_STAMP;}
 document.body.dataset.theme=state.theme;
 document.getElementById("theme").value=state.theme;
 build();setEditing(false);
}
function saveState(){
 state.theme=document.getElementById("theme").value;state.version=3;state.stamp=Date.now();
 localStorage.setItem(key,JSON.stringify(state));
}
// Four themes only; anything saved before this change maps onto them.
const THEMES=["dark","white","violet","green"];
function normaliseTheme(t){if(THEMES.includes(t))return t;return t==="light"?"white":"dark";}
document.getElementById("theme").addEventListener("change",e=>{
 state.theme=normaliseTheme(e.target.value);e.target.value=state.theme;document.body.dataset.theme=state.theme;
 try{localStorage.setItem(themeKey,state.theme);}catch(err){}
});
document.getElementById("settings").addEventListener("click",()=>showView("settings"));
function openSecurity(intent){
 securityIntent=intent;
 document.getElementById("security-password").value="";
 document.getElementById("security-message").textContent=intent==="analytics"
  ?"Analytics are restricted to HOD, coordinator and executive dean accounts."
  :"";
 document.getElementById("security-title").textContent=intent==="analytics"?"Analytics · Management access":"Settings · Security";
 document.querySelector("#security-dialog p").textContent=intent==="analytics"
  ?"Programme analytics are restricted to HOD, coordinator and executive dean accounts."
  :"Timetable editing is locked by default. Enter an authorised password to edit the timetable.";
 document.getElementById("security-unlock").textContent=intent==="analytics"?"View analytics":"✏️ Edit timetable";
 showDialog("security-dialog");
}
// Editing is unlocked from wherever it is needed: the action runs straight away
// when already unlocked, otherwise the security dialog asks for the password first.
let pendingEditAction=null;
function requestEditing(action){
 if(editingUnlocked){if(action)action();return;}
 pendingEditAction=action||null;
 openSecurity("edit");
}
function requestAnalytics(){
 if(analyticsUnlocked){showView("analytics");return;}
 openSecurity("analytics");
}
document.getElementById("security-unlock").addEventListener("click",()=>{
 (async()=>{
  const message=document.getElementById("security-message");
  try{
   const result=await fetch("/api/auth",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:document.getElementById("security-password").value.trim()})});
   const data=await result.json();
   if(!result.ok)throw new Error(data.error||"Incorrect password.");
   const intent=securityIntent;
   currentRole=data.role||"lecturer";
   hideDialog("security-dialog");document.getElementById("security-password").value="";
   if(intent==="analytics"){
    if(!["hod","coordinator","executive_dean"].includes(currentRole))throw new Error("Analytics are restricted to HOD, coordinator and executive dean accounts.");
    analyticsUnlocked=true;updateRoleNav();showView("analytics");
    statusEl.className="status ok";statusEl.textContent="Management analytics unlocked.";
   }else{
    setEditing(true);
    try{await window.mnhApi.flushQueue(true);}catch(e){}
    statusEl.className="status ok";statusEl.textContent="Editing enabled for your authorised role.";
    const next=pendingEditAction;pendingEditAction=null;
    if(next){try{next();}catch(e){}}
   }
  }catch(err){message.textContent=err.message||"Unable to verify your access.";}
 })();
});
document.getElementById("security-password").addEventListener("keydown",e=>{if(e.key==="Enter")document.getElementById("security-unlock").click();});
document.getElementById("close-security").addEventListener("click",()=>hideDialog("security-dialog"));
document.getElementById("module-select").addEventListener("change",e=>updateModuleDetails(e.target.value));
document.getElementById("cancel-module").addEventListener("click",()=>hideDialog("module-dialog"));
document.getElementById("close-details").addEventListener("click",()=>hideDialog("details-dialog"));
document.getElementById("weekly-add-session")?.addEventListener("click",()=>openModuleDialog(0,"08:00",null));
document.getElementById("apply-module").addEventListener("click",async()=>{
 if(!editingUnlocked||!activeCell)return;
 const dayIndex=Number(document.getElementById("session-day").value),startTime=document.getElementById("session-start").value,endTime=document.getElementById("session-end").value;
 const start=parseClock(startTime),end=parseClock(endTime);
 if(!Number.isInteger(dayIndex)||dayIndex<0||dayIndex>=5||start===null||end===null||end<=start){statusEl.className="status error";statusEl.textContent="Choose a weekday and a valid end time later than the start time.";return;}
 const code=document.getElementById("module-select").value,label=document.getElementById("module-label").value.trim().slice(0,80);
 const activityLabel=code||label;
 if(!code&&!label){statusEl.className="status error";statusEl.textContent="Select a module or enter an activity label.";return;}
 const oldId=activeCell.id;
 let id=oldId||`session-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
 if(oldId&&/^\d+_\d+$/.test(oldId)&&dayIndex!==activeCell.dayIndex)id=`session-${Date.now()}-${Math.random().toString(36).slice(2,7)}`;
 const conflict=getSessionEntries().find(x=>x.id!==oldId&&x.id!==id&&x.dayIndex===dayIndex&&start<x.endMinutes&&end>x.startMinutes);
 if(conflict){statusEl.className="status error";statusEl.textContent=`This overlaps ${conflict.label} (${conflict.startTime}–${conflict.endTime}). Choose another time.`;return;}
 const previous=state.cells[oldId||id]||{},module=modules[code]||{};
 const chosenColour=document.getElementById("module-colour").value;
 const record={...previous,dayIndex,startTime,endTime,code:activityLabel,title:code?module.title:(label),facilitator:code?(facilitatorFor(code)||module.facilitator||""):"",moduleCode:code,mode:document.getElementById("module-mode").value,status:document.getElementById("session-status").value};
 if(chosenColour)record.colour=chosenColour;else delete record.colour;
 state.cells[id]=record;if(oldId&&oldId!==id)delete state.cells[oldId];activeCell={id,dayIndex,startTime,endTime};hideDialog("module-dialog");build();const saved=await pushCell(id);if(saved&&oldId&&oldId!==id)await pushCell(oldId);
});
document.getElementById("delete-module").addEventListener("click",async()=>{
 if(!editingUnlocked||!activeCell?.id)return;
 const id=activeCell.id;delete state.cells[id];hideDialog("module-dialog");build();await pushCell(id);
});
document.getElementById("save").addEventListener("click",()=>{if(editingUnlocked)syncAll("Saved for everyone.");});
document.getElementById("backup").addEventListener("click",async()=>{
 if(!editingUnlocked)return;
 try{const response=await fetch("/api/backup",{cache:"no-store"});if(!response.ok)throw new Error("Backup request failed");const payload=await response.json();
  await downloadFile("MNH-Calendar-shared-backup.json",JSON.stringify(payload,null,2));
 }catch(e){statusEl.className="status error";statusEl.textContent="Shared backup could not be downloaded.";}
});
document.getElementById("import").addEventListener("click",()=>{if(editingUnlocked)document.getElementById("import-file").click();});
document.getElementById("import-file").addEventListener("change",async e=>{
 const f=e.target.files&&e.target.files[0];e.target.value="";if(!f||!editingUnlocked)return;
 try{
  const obj=JSON.parse(await f.text());
  if(obj&&obj.format==="mnh-calendar-backup"&&Array.isArray(obj.documents)){
   const response=await fetch("/api/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});
   const result=await response.json().catch(()=>({}));if(!response.ok)throw new Error(result.error||"Restore failed");
   statusEl.className="status ok";statusEl.textContent=`Shared backup restored (${result.restored} records). Reloading shared data…`;
   location.reload();return;
  }
  if(!obj||typeof obj.cells!=="object")throw new Error("bad");
  let cells=obj.cells;if(obj.version!==3)cells=remapLegacyCells(cells);
  const clean={};Object.entries(cells).forEach(([k,v])=>{if(!validKey(k)||k==="2_1"||(/^\d+_\d+$/.test(k)&&+k.split("_")[1]>=5)||(Number.isFinite(Number(v?.dayIndex))&&Number(v?.dayIndex)>=5))return;const c=cleanCell(v);if(c.code||c.text||c.title)clean[k]=c;});
  state.cells=clean;build();await syncAll("Backup restored and saved.");
 }catch(err){statusEl.className="status error";statusEl.textContent=err.message||"That file isn’t a valid timetable backup.";}
});
document.getElementById("print").addEventListener("click",downloadPdf);
async function downloadPdf(){
 const J=window.jspdf&&window.jspdf.jsPDF;
 if(!J){statusEl.className="status error";statusEl.textContent="The PDF tools could not load. Check your connection and try again.";return;}
 statusEl.className="status";statusEl.textContent="Preparing PDF…";
 try{
  const portrait=innerWidth<innerHeight;
  const pdf=new J({orientation:portrait?"p":"l",unit:"mm",format:"a4",compress:true});
  const PW=pdf.internal.pageSize.getWidth(),PH=pdf.internal.pageSize.getHeight(),M=8;
  const rgb=v=>{const m=/rgba?\(([^)]+)\)/.exec(v||"");if(!m)return null;const a=m[1].split(",").map(x=>parseFloat(x));return(a.length>3&&a[3]<.5)?null:a.slice(0,3).map(Math.round);};
  const hex=c=>"#"+c.map(x=>x.toString(16).padStart(2,"0")).join("");
  const cs=(el,p)=>getComputedStyle(el)[p];
  const page=rgb(cs(document.body,"backgroundColor"))||[6,19,38];
  const cssVar=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const parse=c=>{const r=rgb(c);if(r)return r;const h=String(c||"").replace("#","").trim();if(h.length>=6){const n=parseInt(h.slice(0,6),16);return[(n>>16)&255,(n>>8)&255,n&255];}return null;};
  const line=parse(cssVar("--gridline"))||[120,135,150];
  const ink=rgb(cs(document.body,"color"))||[255,255,255];
  const cyan=ink,white=ink;
  // Pick black or white ink from the background actually being drawn, so text never fades.
  const inkOn=bgc=>((0.299*bgc[0]+0.587*bgc[1]+0.114*bgc[2])>150?[17,24,39]:[255,255,255]);
  const clean=t=>String(t).replace(/[–—]/g,"-");
  const bg=()=>{pdf.setFillColor(...page);pdf.rect(0,0,PW,PH,"F");};
  const txt=(t,x,y,o)=>pdf.text(clean(t),x,y,o);
  bg();
  // title
  pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?13:16);pdf.setTextColor(...white);
  txt(document.getElementById("hd-title").textContent,M,M+5);
  pdf.setFontSize(portrait?9.5:11.5);pdf.setTextColor(...cyan);txt("Dashboard · "+WK.label(weekOffset)+" · Monday–Friday, "+WK.range(weekOffset),M,M+10.5);
  const top=M+14,foot=9,cw0=portrait?22:30,hh=portrait?13:12;
  const rows=[...tbody.querySelectorAll("tr")],nr=rows.length,nc=days.length;
  const cw=(PW-2*M-cw0)/nc,rh=(PH-top-M-foot-hh)/nr;
  const head=[...thead.querySelectorAll("th")];
  const dayPage=c=>2+c;
  // header row
  const hBg=rgb(cs(head[1],"backgroundColor"))||[14,37,71];
  pdf.setDrawColor(...line);pdf.setLineWidth(.4);
  head.forEach((th,i)=>{
   const x=i===0?M:M+cw0+(i-1)*cw,w=i===0?cw0:cw;
   pdf.setFillColor(...hBg);pdf.rect(x,top,w,hh,"FD");
   if(i===0){pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?9:11);pdf.setTextColor(...inkOn(hBg));txt("Time / Day",x+w/2,top+hh/2+1,{align:"center"});}
   else{
    const c=i-1;pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?11:14);pdf.setTextColor(...inkOn(hBg));txt(days[c],x+w/2,top+hh/2-.5,{align:"center"});
    pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?9:11);pdf.setTextColor(...inkOn(hBg));txt(dates[c],x+w/2,top+hh/2+4,{align:"center"});
    try{pdf.link(x,top,w,hh,{pageNumber:dayPage(c)});}catch(e){}
   }
  });
  // rows
  let editable=true;
  // Cells are <button class="activity"> in this build; keep the legacy textarea path for safety.
  const cellLabel=area=>{
   if(!area)return "";
   const name=area.querySelector&&area.querySelector(".activity-name");
   if(name)return clean(name.textContent||"");
   if(typeof area.value==="string"&&area.value)return clean(area.value);
   return clean(area.textContent||"");
  };
  rows.forEach((tr,r)=>{
   const y=top+hh+r*rh,cells=[...tr.children];
   const th=cells[0],hl=th.classList.contains("highlight");
   pdf.setFillColor(...(hl?(rgb(cs(th,"backgroundColor"))||[201,166,90]):hBg));pdf.rect(M,y,cw0,rh,"FD");
   pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?7:9);pdf.setTextColor(...(hl?[6,19,38]:white));
   const timeText=clean(th.textContent||tr.dataset.startTime||"");
   pdf.setFontSize(portrait?8:9.5);
   const timeLines=pdf.splitTextToSize(timeText,cw0-1.6);
   timeLines.forEach((ln,i)=>txt(ln,M+cw0/2,y+rh/2+1-(timeLines.length-1)*1.6+i*3.2,{align:"center"}));
   if(tr.classList.contains("lunch-row")){
    // One merged band across every weekday column, exactly as it appears on screen.
    const base=rgb(cs(cells[1],"backgroundColor"))||hBg,fg=rgb(cs(cells[1],"color"))||white;
    pdf.setFillColor(...base);pdf.setDrawColor(...line);pdf.rect(M+cw0,y,nc*cw,rh,"FD");
    pdf.setFont("helvetica","bold");pdf.setFontSize(portrait?10:12);pdf.setTextColor(...fg);
    txt("Lunch Break",M+cw0+nc*cw/2,y+rh/2+1,{align:"center"});
    return;
   }
   cells.slice(1).forEach((td,c)=>{
    const x=M+cw0+c*cw,area=td.querySelector("textarea")||td.querySelector(".activity")||td.firstElementChild;
    const base=rgb(cs(td,"backgroundColor"))||[10,29,56];
    pdf.setFillColor(...base);pdf.rect(x,y,cw,rh,"FD");
    const fill=area?(rgb(cs(area,"backgroundColor"))||base):base,fg=area?(rgb(cs(area,"color"))||white):white;
    const ix=x+.9,iy=y+.9,iw=cw-1.8,ih=rh-1.8;
    pdf.setFillColor(...fill);pdf.setDrawColor(...line);pdf.setLineWidth(.4);pdf.roundedRect(ix,iy,iw,ih,1.6,1.6,"FD");
    const value=cellLabel(area);
    const size=value.length>(portrait?30:44)?(portrait?8:9.5):(portrait?9.5:11);
    const cellInk=inkOn(fill);
    // Always draw the label as real text. jsPDF writes only form-field values, and most mobile
    // readers, printers and PDF renderers do not regenerate field appearances, so a fields-only
    // export showed empty coloured boxes. The editable field is added on top of the drawn text.
    if(value){
     pdf.setFont("helvetica","normal");pdf.setFontSize(size);pdf.setTextColor(...(fg&&((0.299*fg[0]+0.587*fg[1]+0.114*fg[2])>40||fill[0]+fill[1]+fill[2]>430)?fg:cellInk));
     const ls=pdf.splitTextToSize(value,iw-1.6);txt(ls,x+cw/2,y+rh/2-(ls.length-1)*1.6,{align:"center",baseline:"middle"});
    }
    if(editable&&!value){
     try{
      const f=new J.AcroForm.TextField();
      f.fieldName="cell_"+r+"_"+c;f.Rect=[ix+.4,iy+.4,iw-.8,ih-.8];f.multiline=true;f.value=value;f.defaultValue=value;
      f.fontSize=size;f.fontName="helvetica";f.color=hex(cellInk);try{f.quadding=1;}catch(e){}
      try{f.textAlign="center";}catch(e){}
      pdf.addField(f);
     }catch(e){editable=false;}
    }
   });
  });
  // footer
  pdf.setFont("helvetica","normal");pdf.setFontSize(9);pdf.setTextColor(...cyan);
  txt("Penrose ScholarMw · Your academic partner for excellence",M,PH-M+1);
  txt("Tap a day to open its page · empty cells can be filled in",PW-M,PH-M+1,{align:"right"});
  // one page per day (navigable)
  days.forEach((dn,c)=>{
   pdf.addPage();bg();
   pdf.setFont("helvetica","bold");pdf.setFontSize(17);pdf.setTextColor(...white);txt(dn+" "+dates[c],M,M+7);
   pdf.setFontSize(10.5);pdf.setFont("helvetica","normal");pdf.setTextColor(...cyan);
   pdf.textWithLink("< Dashboard",M,M+13,{pageNumber:1});
   if(c>0)pdf.textWithLink("< "+days[c-1],PW/2-20,M+13,{pageNumber:dayPage(c-1)});
   if(c<nc-1)pdf.textWithLink(days[c+1]+" >",PW-M-22,M+13,{pageNumber:dayPage(c+1)});
   let y=M+24;const list=dayEntries(c);
   if(!list.length){pdf.setTextColor(...white);txt("Nothing scheduled.",M,y);}
   list.forEach(x=>{
    const fac=(modules[x.label]&&modules[x.label].facilitator)||"";
    pdf.setFillColor(14,37,71);pdf.setDrawColor(...line);pdf.roundedRect(M,y-5,PW-2*M,16,2,2,"FD");
    pdf.setFont("helvetica","bold");pdf.setFontSize(10.5);pdf.setTextColor(...white);txt(x.timeLabel+"   "+x.label,M+3,y+.5);
    pdf.setFont("helvetica","normal");pdf.setFontSize(8.5);pdf.setTextColor(...cyan);
    txt([x.sub,fac&&fac!=="Not specified"?"Facilitator: "+fac:""].filter(Boolean).join(" · "),M+3,y+6);
    y+=19;
   });
  });
  try{pdf.outline.add(null,"Weekly Schedule",{pageNumber:1});days.forEach((dn,c)=>pdf.outline.add(null,dn+" "+dates[c],{pageNumber:dayPage(c)}));}catch(e){}
  pdf.setProperties({title:"PhD in Maternal and Neonatal Health : 3rd Block - "+WK.label(weekOffset)+" - "+WK.range(weekOffset)});
  const blob=pdf.output("blob"),name="MNH-PhD-Timetable-"+WK.isoMonday(weekOffset)+"-"+(weekOffset===0?"this-week":"week-"+weekOffset)+".pdf";
  const url=URL.createObjectURL(blob),l=document.createElement("a");l.href=url;l.download=name;l.click();setTimeout(()=>URL.revokeObjectURL(url),4000);statusEl.className="status ok";statusEl.textContent="PDF ready.";
 }catch(e){console.error(e);statusEl.className="status error";statusEl.textContent="The PDF could not be created.";}
}
document.addEventListener("keydown",e=>{if(e.key==="Escape"){hideDialog("module-dialog");hideDialog("security-dialog");hideDialog("details-dialog");}});
// ---- Shared cloud storage (published link) with local copy as fallback ----
const SEED_CELLS={
 "1_0":{code:"Biostatistics",title:"Biostatistics",timeLabel:"11:00–13:30",colour:"#2F5D8C"},
 "6_0":{code:"Bioethics",title:"Bioethics",timeLabel:"19:00–21:00",colour:"#7B3F61"},
 "6_1":{code:"Bioethics",title:"Bioethics",timeLabel:"19:00–21:00",colour:"#7B3F61"},
 "0_2":{code:"Immunology",title:"Immunology",timeLabel:"08:00–10:00",colour:"#3C7A5A"},
 "3_2":{code:"Imaging",title:"Imaging",timeLabel:"Afternoon–evening",colour:"#8A6D2F"},
 "1_3":{code:"Seminar in MNH",title:"Seminar in Maternal and Neonatal Health",timeLabel:"10:00–12:00",colour:"#2F5D8C"},
 "2_3":{code:"Biostatistics",title:"Biostatistics",timeLabel:"AM–afternoon",colour:"#2F5D8C"},
 "6_3":{code:"Immunology",title:"Immunology",timeLabel:"19:00–21:00",colour:"#3C7A5A"},
 "0_4":{code:"Immunology",title:"Immunology",timeLabel:"08:00–10:00",colour:"#3C7A5A"},
 "3_4":{code:"Library",title:"Library session",timeLabel:"Afternoon",colour:"#4B5D7A"},
};
const SEED_STAMP=1794350000001;   // corrected Monday–Friday programme for 9–13 November 2026
const themeKey="phd_mnh_theme";
const syncEl=document.getElementById("sync");
let cloud=null,syncing=false;
function setSync(t){const el=syncEl||document.getElementById("status");if(el)el.textContent=t;}
function cleanCell(v){const o={};["code","title","facilitator","colour","text","timeLabel","mode","moduleCode","startTime","endTime","status"].forEach(k=>{if(v&&typeof v[k]==="string")o[k]=v[k];});if(Number.isInteger(v?.dayIndex))o.dayIndex=v.dayIndex;return o;}
function validKey(k){const m=/^(\d+)_(\d+)$/.exec(k);return (!!m&&+m[1]<times.length&&+m[2]<5)||/^session-[A-Za-z0-9-]+$/.test(k);}
function writeFailed(e){
 try{saveState();}catch(x){}
 if(e&&e.queued){
  setSync("Offline · changes saved locally and waiting to sync");
  statusEl.className="status ok";
  statusEl.textContent="Saved on this device. This change will sync automatically when the connection returns.";
  return;
 }
 statusEl.className="status error";
 if(e&&e.code==="invalid_argument"){setSync("Shared timetable · read-only for this account");statusEl.textContent="Your account can’t change the shared timetable, so this edit is kept on this device only. Ask the owner for Contributor access.";}
 else if(e&&(e.status===400||e.status===409)){setSync("Schedule change rejected");statusEl.textContent=e.message||"The session could not be saved. Check its day and time.";}
 else{setSync("Shared timetable unreachable · local copy retained");statusEl.textContent="The shared timetable could not be reached. Your local copy is retained; reconnect and try again.";}
}
async function pushCell(idOrRow,c){
 const id=c===undefined?String(idOrRow):cellKey(idOrRow,c),v=state.cells[id];
 try{saveState();}catch(e){}
 const path="/api/doc/cells/"+encodeURIComponent(id);
 try{
  if(v){const data={...cleanCell(v),updatedAt:Date.now()};if(cloud)await cloud.doc("cells/"+id).set(data);else await window.mnhApi.request("PUT",path,data);}
  else if(cloud)await cloud.doc("cells/"+id).delete();else await window.mnhApi.request("DELETE",path);
  setSync("Shared timetable · saved");statusEl.className="status ok";statusEl.textContent="Saved for everyone.";return true;
 }catch(e){writeFailed(e);return Boolean(e&&e.queued);}
}
async function syncAll(okMsg){
 try{saveState();}catch(e){statusEl.className="status error";statusEl.textContent="Browser storage is unavailable. Use Download backup to keep a copy.";}
 if(!cloud){statusEl.className="status error";statusEl.textContent="The shared server is unavailable. Your local recovery copy is retained.";return;}
 syncing=true;
 try{
  const want={...state.cells};
  const snap=await cloud.collection("cells").get();
  const existing=snap.docs.map(d=>d.id);
  for(const [id,v] of Object.entries(want)){if(!validKey(id)||(/^\d+_\d+$/.test(id)&&+id.split("_")[1]>=5)||(Number.isFinite(Number(v?.dayIndex))&&Number(v?.dayIndex)>=5))continue;await cloud.doc("cells/"+id).set({...cleanCell(v),updatedAt:Date.now()});}
  for(const id of existing){if(!(id in want))await cloud.doc("cells/"+id).delete();}
  state.fromCloud=true;try{saveState();}catch(e){}
  setSync("Shared timetable · saved");statusEl.className="status ok";statusEl.textContent=okMsg||"Saved for everyone.";
 }catch(e){writeFailed(e);}
 finally{syncing=false;}
}
function onCells(snap){
 if(syncing)return;
 if(snap.metadata&&snap.metadata.fromCache&&snap.empty)return;
 const remote={};
 snap.docs.forEach(d=>{if(!validKey(d.id))return;const raw=d.data()||{};if((/^\d+_\d+$/.test(d.id)&&+d.id.split("_")[1]>=5)||(Number.isFinite(Number(raw.dayIndex))&&Number(raw.dayIndex)>=5))return;const v=cleanCell(raw);if(v.code||v.text||v.title)remote[d.id]=v;});
 if(!Object.keys(remote).length&&!state.fromCloud){
  setSync(Object.keys(state.cells).length?"Shared timetable is empty · use Save timetable to publish this copy":"Shared timetable · up to date");
  return;
 }
 state.cells=remote;state.fromCloud=true;
 try{saveState();}catch(e){}
 build();setSync("Shared timetable · up to date");
}
async function downloadFile(filename,text){
 const blob=new Blob([text],{type:"application/json"});
 const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=filename;a.click();URL.revokeObjectURL(url);
}
let cloudInitialising=false;
async function initCloud(){
 if(cloudInitialising||cloud)return;
 cloudInitialising=true;
 setSync("Connecting to the shared timetable…");
 try{
  const db=await window.mnhApi.use("db");
  if(!db){setSync("Shared server unavailable · local recovery copy retained");return;}
  cloud=db;
  try{const session=await fetch("/api/session",{cache:"no-store"}).then(r=>r.json());currentRole=session.role||"student";updateRoleNav();if(session.authenticated){setEditing(true);}}
  catch(e){}
  try{await window.mnhApi.flushQueue();}catch(e){}
  try{subscribeExtras(db);}catch(e){}
  try{db.collection("cells").onSnapshot(onCells,()=>setSync("Shared server unavailable · local recovery copy retained"));}
  catch(e){setSync("Shared server unavailable · local recovery copy retained");}
  try{moduleUnsubscribe=db.collection("modules").onSnapshot(onModules,()=>setSync("Module updates temporarily unavailable"));}catch(e){}
 }catch(e){setSync("Shared server unavailable · local recovery copy retained");}
 finally{cloudInitialising=false;}
}
window.addEventListener("online",()=>{if(!cloud)initCloud();});
setInterval(()=>{if(!cloud&&navigator.onLine)initCloud();},15000);
window.addEventListener("offline",()=>setSync("Offline · local calendar remains available"));
window.addEventListener("mnh:offline-queued",()=>setSync("Offline · changes saved locally and waiting to sync"));
window.addEventListener("mnh:offline-synced",()=>{
 setSync("Shared timetable · offline changes synchronised");
 statusEl.className="status ok";
 statusEl.textContent="Your offline changes have now been synchronised.";
});
// ---- Alarms: ring like an incoming call (per device, only while this page is open) ----
const alarmKey="phd_mnh_alarm_v1",firedKey="phd_mnh_alarm_fired";
let WEEK_START=WK.startParts(0);   // Monday of the academic week currently on screen
const baseTitle=document.title;
let alarm={on:false,lead:10},fired=[],snoozed=[],audioCtx=null,ringBus=null,ringTimer=null,ringStopTimer=null,titleTimer=null,ringing=null;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));}
function pad2(n){return String(n).padStart(2,"0");}
function hhmm(d){return pad2(d.getHours())+":"+pad2(d.getMinutes());}
function loadAlarm(){
 try{const a=JSON.parse(localStorage.getItem(alarmKey)||"null");if(a)alarm={on:!!a.on,lead:[0,5,10,15,30].includes(+a.lead)?+a.lead:10};}catch(e){}
 try{fired=JSON.parse(localStorage.getItem(firedKey)||"[]");if(!Array.isArray(fired))fired=[];}catch(e){fired=[];}
}
function saveAlarm(){try{localStorage.setItem(alarmKey,JSON.stringify(alarm));}catch(e){}}
function ensureAudio(){
 try{
  const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return null;
  if(!audioCtx){audioCtx=new AC();ringBus=audioCtx.createGain();ringBus.connect(audioCtx.destination);}
  if(audioCtx.state==="suspended")audioCtx.resume();
  return audioCtx;
 }catch(e){return null;}
}
function alarmEvents(){const ws=WK.startParts(WK.currentOffset());return getSessionEntries().map(x=>{const start=new Date(ws[0],ws[1],ws[2]+x.dayIndex);const [h,m]=x.startTime.split(":").map(Number);start.setHours(h,m,0,0);return {...x,start};});}
function playCycle(){
 const ctx=audioCtx;if(!ctx)return;
 if(ctx.state==="suspended")ctx.resume();
 const t0=ctx.currentTime+0.02;
 [0,0.6].forEach(off=>{
  const env=ctx.createGain(),trem=ctx.createGain(),lg=ctx.createGain();
  const lfo=ctx.createOscillator(),o1=ctx.createOscillator(),o2=ctx.createOscillator();
  o1.frequency.value=440;o2.frequency.value=480;lfo.frequency.value=20;
  trem.gain.value=0.5;lg.gain.value=0.5;
  lfo.connect(lg);lg.connect(trem.gain);o1.connect(trem);o2.connect(trem);trem.connect(env);env.connect(ringBus);
  const s=t0+off,e=s+0.45;
  env.gain.setValueAtTime(0,s);env.gain.linearRampToValueAtTime(0.35,s+0.03);
  env.gain.setValueAtTime(0.35,e-0.04);env.gain.linearRampToValueAtTime(0,e);
  [o1,o2,lfo].forEach(o=>{o.start(s);o.stop(e+0.05);});
 });
 try{if(navigator.vibrate)navigator.vibrate([450,150,450]);}catch(e){}
}
function startRing(ev){
 if(ringing)return;
 ringing=ev;ensureAudio();{const cd=document.getElementById("call-day");if(cd)cd.textContent=new Date().getDate();}
 document.getElementById("call-name").textContent=ev.label;
 const mins=Math.round((ev.start.getTime()-Date.now())/60000);
 const when=ev.test?"This is a test of the alarm sound":(mins>0?`Starts at ${hhmm(ev.start)} · in ${mins} min`:`Starting now · ${hhmm(ev.start)}`);
 document.getElementById("call-when").textContent=(ev.sub?ev.sub+" · ":"")+when;
 document.getElementById("call-snooze").style.display=ev.test?"none":"inline-block";
 showDialog("call-dialog");
 playCycle();ringTimer=setInterval(playCycle,3000);
 ringStopTimer=setTimeout(stopRing,60000);
 let flip=false;titleTimer=setInterval(()=>{flip=!flip;document.title=flip?"📞 "+ev.label:baseTitle;},900);
}
function stopRing(){
 clearInterval(ringTimer);clearTimeout(ringStopTimer);clearInterval(titleTimer);ringTimer=ringStopTimer=titleTimer=null;
 if(audioCtx&&ringBus){try{ringBus.disconnect();}catch(e){}ringBus=audioCtx.createGain();ringBus.connect(audioCtx.destination);}
 try{if(navigator.vibrate)navigator.vibrate(0);}catch(e){}
 document.title=baseTitle;hideDialog("call-dialog");ringing=null;
}
function alarmTick(){
 if(!alarm.on||ringing)return;
 const now=Date.now();
 for(const s of snoozed){if(!s.done&&now>=s.at){s.done=true;startRing(s.ev);return;}}
 for(const ev of alarmEvents()){
  const ring=ev.start.getTime()-alarm.lead*60000,id=ev.id+"|"+alarm.lead;
  if(now>=ring&&now<ring+90000&&!fired.includes(id)){
   fired.push(id);try{localStorage.setItem(firedKey,JSON.stringify(fired.slice(-100)));}catch(e){}
   startRing(ev);return;
  }
 }
}
function refreshAlarmUI(){
 const ab=document.getElementById("alarms"),al=alarm.on?`Alarms on (${alarm.lead?alarm.lead+" min before":"at start"})`:"Alarms off";ab.setAttribute("aria-label",al);ab.parentElement.dataset.label=al;ab.classList.toggle("on",alarm.on);
 document.getElementById("alarm-toggle").textContent=alarm.on?"Turn off":"Turn on";
 document.getElementById("alarm-lead").value=String(alarm.lead);
 const box=document.getElementById("alarm-next");
 if(!alarm.on){box.textContent="Alarms are off.";return;}
 const now=Date.now();let next=null;
 alarmEvents().forEach(ev=>{const ring=ev.start.getTime()-alarm.lead*60000;if(ring+90000>now&&(!next||ring<next.ring))next={ev,ring};});
 box.innerHTML=next
  ?`<strong>Next alarm</strong><br>${esc(next.ev.label)}<br>${days[next.ev.c]} ${dates[next.ev.c]} · rings ${hhmm(new Date(next.ring))}, starts ${hhmm(next.ev.start)}`
  :"No more activities this week.";
}
function initAlarms(){
 loadAlarm();refreshAlarmUI();
 document.getElementById("alarms").addEventListener("click",()=>{refreshAlarmUI();showDialog("alarm-dialog");});
 document.getElementById("alarm-close").addEventListener("click",()=>hideDialog("alarm-dialog"));
 document.getElementById("alarm-lead").addEventListener("change",e=>{alarm.lead=+e.target.value;saveAlarm();refreshAlarmUI();});
 document.getElementById("alarm-toggle").addEventListener("click",()=>{
  alarm.on=!alarm.on;
  if(alarm.on&&!ensureAudio()){statusEl.className="status error";statusEl.textContent="This browser can’t play alarm sounds. You will still see the call screen.";}
  saveAlarm();refreshAlarmUI();
 });
 document.getElementById("alarm-test").addEventListener("click",()=>{hideDialog("alarm-dialog");ensureAudio();startRing({r:-1,c:0,label:"Test alarm",sub:"",start:new Date(),test:true});});
 document.getElementById("call-decline").addEventListener("click",stopRing);
 document.getElementById("call-snooze").addEventListener("click",()=>{if(ringing&&!ringing.test)snoozed.push({ev:ringing,at:Date.now()+300000,done:false});stopRing();});
 document.getElementById("call-answer").addEventListener("click",()=>{const ev=ringing;stopRing();if(ev&&!ev.test)showSessionDetails(ev);});
 document.addEventListener("pointerdown",()=>{if(alarm.on&&(!audioCtx||audioCtx.state!=="running"))ensureAudio();},{passive:true});
 document.addEventListener("keydown",e=>{if(e.key==="Escape"){if(ringing)stopRing();hideDialog("alarm-dialog");}});
 setInterval(alarmTick,1000);
}
// ---- Header (editable + navigable) and extra views ----
const HEADER_DEFAULT={title:"PhD in Maternal and Neonatal Health : 3rd Block",subtitle:"Academic Calendar"};
const headerKey="phd_mnh_header",resKey="phd_mnh_resources",resCloudKey="phd_mnh_res_cloud";
const VIEWS=["dashboard","weekly","monthly","upcoming","modules","facilitators","examinations","recurring","communications","analytics","history","export","settings"];
function updateRoleNav(){document.querySelectorAll('.view-tab[data-view="analytics"]').forEach(x=>{x.title=analyticsUnlocked?"Analytics unlocked":"HOD, coordinator and executive dean access";});}
const MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],WD=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
let headerCfg={...HEADER_DEFAULT},resources=[],currentView="weekly";
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
function fmtH(m){const h=Math.floor(m/60),mm=m%60;return mm?(h?h+"h "+mm+"m":mm+"m"):h+"h";}
function todayIndexFor(offset){
 const n=new Date(),ws=offset==null?WEEK_START:WK.startParts(offset);
 for(let c=0;c<days.length;c++){const d=new Date(ws[0],ws[1],ws[2]+c);if(d.getFullYear()===n.getFullYear()&&d.getMonth()===n.getMonth()&&d.getDate()===n.getDate())return c;}
 return -1;
}
// The bell and the header always describe the real current week, whatever week is being viewed.
function todayIndex(){return todayIndexFor(WK.currentOffset());}
function dayEntries(c,offset){
 const ws=offset==null?WEEK_START:WK.startParts(offset);
 return getSessionEntries().filter(x=>x.dayIndex===c).map(x=>{const start=new Date(ws[0],ws[1],ws[2]+c);const [h,m]=x.startTime.split(":").map(Number);start.setHours(h,m,0,0);const end=new Date(start);const [eh,em]=x.endTime.split(":").map(Number);end.setHours(eh,em,0,0);return {...x,start,end};});
}
function allEntries(){return days.flatMap((d,c)=>dayEntries(c));}
// ---- header ----
function applyHeader(h){
 if(!h)return false;
 const t=String(h.title||"").trim().slice(0,80),s=String(h.subtitle||"").trim().slice(0,60);
 if(!t)return false;
 headerCfg={title:t,subtitle:s};
 document.getElementById("hd-title").textContent=t;document.getElementById("hd-sub").textContent=s;
 document.getElementById("hd-sub").hidden=!s;
 try{localStorage.setItem(headerKey,JSON.stringify(headerCfg));}catch(e){}
 return true;
}
function initHeaderFromLocal(){try{const h=JSON.parse(localStorage.getItem(headerKey)||"null");if(h)applyHeader(h);}catch(e){}}
async function saveHeader(h){
 if(!applyHeader(h))return;
 const data={title:headerCfg.title,subtitle:headerCfg.subtitle,updatedAt:Date.now()};
 try{
  if(cloud)await cloud.doc("settings/header").set(data);
  else await window.mnhApi.request("PUT","/api/doc/settings/header",data);
  statusEl.className="status ok";statusEl.textContent="Header saved for everyone.";
 }catch(e){writeFailed(e);}
}
function closeBell(){const p=document.getElementById("bell-panel");p.hidden=true;document.getElementById("hd-bell").setAttribute("aria-expanded","false");}
function refreshHeader(){
 const d=new Date();
 document.getElementById("hd-date").textContent=WD[d.getDay()]+", "+d.getDate()+" "+MONTHS[d.getMonth()]+" "+d.getFullYear();
 {const hd=document.getElementById("hd-day");if(hd)hd.textContent=d.getDate();}
 const c=todayIndex(),now=Date.now();
 const rem=c<0?[]:dayEntries(c,WK.currentOffset()).filter(x=>x.end.getTime()>now);
 const badge=document.getElementById("hd-badge");badge.textContent=rem.length;badge.hidden=!rem.length;
 document.getElementById("hd-bell").setAttribute("aria-label","Today’s activities: "+rem.length+" remaining");
 const panel=document.getElementById("bell-panel");panel.textContent="";
 panel.appendChild(el("div","bp-h","Today"));
 if(!rem.length)panel.appendChild(el("div","bp-empty",c<0?"No activities today.":"Nothing left today."));
 rem.forEach(x=>{
  const b=el("button","bp-item");b.type="button";
  b.append(el("span","bp-t",x.timeLabel),el("span","bp-n",x.label));
  b.addEventListener("click",()=>{closeBell();showSessionDetails(x);});
  panel.appendChild(b);
 });
}
// ---- academic week navigation (one control beside Analytics) ----
function setWeek(offset){
 weekOffset=Math.max(0,Math.trunc(Number(offset)||0));
 applyWeekView(false);
}
function applyWeekView(keepStatus){
 WEEK_START=WK.startParts(weekOffset);
 dates=WK.dateLabels(weekOffset);
 renderWeekNav();
 const lead=document.getElementById("schedule-lead");
 if(lead)lead.textContent="Everything planned for the week of "+WK.range(weekOffset)+" ("+WK.label(weekOffset)+"). Select an item for details.";
 if(!keepStatus){statusEl.className="status";statusEl.textContent=WK.label(weekOffset)+" · "+WK.range(weekOffset);}
 renderView(currentView);
}
function renderWeekNav(){
 const prev=document.getElementById("week-prev"),next=document.getElementById("week-next"),now=document.getElementById("week-now");
 if(!prev||!next||!now)return;
 const label=WK.label(weekOffset),range=WK.range(weekOffset);
 const lab=document.getElementById("week-now-label"),rng=document.getElementById("week-now-range");
 if(lab)lab.textContent=label;if(rng)rng.textContent=range;
 now.title=label+" · "+range+" — click to return to this week";
 now.setAttribute("aria-label",label+", "+range+". Show this week");
 now.dataset.default=String(weekOffset===0);
 prev.disabled=weekOffset<=0;
 prev.setAttribute("aria-disabled",String(weekOffset<=0));
 next.disabled=false;
}
function initWeekNav(){
 const prev=document.getElementById("week-prev"),next=document.getElementById("week-next"),now=document.getElementById("week-now");
 if(!prev||!next||!now)return;
 prev.addEventListener("click",()=>setWeek(weekOffset-1));
 next.addEventListener("click",()=>setWeek(weekOffset+1));
 now.addEventListener("click",()=>setWeek(0));
 applyWeekView(false);
}
// ---- navigation ----
function showView(name){
 if(!VIEWS.includes(name))name="weekly";
 if(name==="analytics"&&!analyticsUnlocked){requestAnalytics();return;}
 currentView=name;
 const weekly=document.getElementById("view-weekly"),home=document.getElementById("view-dashboard"),workspace=document.getElementById("view-workspace"),analytics=document.getElementById("view-analytics");
 home.hidden=name!=="dashboard";weekly.hidden=name!=="weekly";analytics.hidden=name!=="analytics";
 workspace.hidden=!(["modules","monthly","upcoming","facilitators","examinations","recurring","communications","history","export","settings"].includes(name));
 document.querySelectorAll(".menu-nav[data-view]").forEach(t=>t.classList.toggle("active",t.dataset.view===name));
 document.querySelectorAll(".view-tab[data-view],.hd-tab[data-view]").forEach(t=>{const on=t.dataset.view===name;t.classList.toggle("active",on);if(on)t.setAttribute("aria-current","page");else t.removeAttribute("aria-current");});
 renderView(name);
}
function renderView(name){
 if(name==="dashboard")renderDashboard();
 else if(name==="weekly")build();
 else if(name==="modules")renderModules();
 else if(name==="analytics")renderAnalytics();
 else if(name==="monthly")renderMonthly();
 else if(name==="upcoming")renderUpcoming();
 else if(name==="facilitators")renderManaged("facilitators");
 else if(name==="examinations")renderManaged("examinations");
 else if(name==="recurring")renderManaged("recurring");
 else if(name==="communications")renderCommunications();
 else if(name==="history")renderHistoryPage();
 else if(name==="export")renderExportPage();
 else if(name==="settings")renderSettingsPage();
}
const WORKSPACE_META={
 monthly:["Monthly Calendar","Browse the current academic month and its scheduled sessions."],
 modules:["Modules","Manage programme modules and review their scheduled sessions."],
 upcoming:["Upcoming Academic Activities","Timetable sessions, examinations and recurring activities."],
 facilitators:["Facilitators","Shared facilitator directory."],
 examinations:["Examinations","Examination dates, times, venues and notes."],
 recurring:["Recurring Activities","Regular academic activities and their schedules."],
 communications:["WhatsApp & Communications","Shared announcements, communication notes and useful links."],
 history:["Activity History","New timetable sessions and shared activities added by Rep or Staff."],
 export:["Export & Sharing","Download the timetable, shared data and printable calendar."],
 settings:["Settings","Application preferences, access and header controls."]
};
function workspace(title,lead){document.getElementById("workspace-title").textContent=title;document.getElementById("workspace-lead").textContent=lead;const root=document.getElementById("workspace-body");root.textContent="";return root;}
async function apiRequest(method,path,body){return window.mnhApi.request(method,path,body);}
function fieldInput(placeholder,max=180,type="text"){const i=document.createElement("input");i.placeholder=placeholder;i.type=type;if(type==="text")i.maxLength=max;i.setAttribute("aria-label",placeholder);if(type==="date"){const pad=n=>String(n).padStart(2,"0"),iso=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`,now=new Date();i.min=iso(now);i.max=iso(new Date(now.getFullYear()+3,now.getMonth(),now.getDate()));i.title="Choose today or a future date, up to three years ahead.";}if(type==="time")i.step="900";i.style.cssText="display:block;width:100%;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--field);color:var(--text);font:inherit";return i;}
async function loadRows(collection){return apiRequest("GET","/api/col/"+encodeURIComponent(collection));}
async function saveRow(collection,id,data){await apiRequest("PUT","/api/doc/"+encodeURIComponent(collection)+"/"+encodeURIComponent(id),data);}
async function deleteRow(collection,id){await apiRequest("DELETE","/api/doc/"+encodeURIComponent(collection)+"/"+encodeURIComponent(id));}
function makeId(prefix){return prefix+"-"+Date.now().toString(36)+"-"+Math.random().toString(36).slice(2,7);}
function missedEntries(){return getSessionEntries().filter(x=>(x.data?.status||"")==="missed");}
function updateMissedTab(){
 const rows=missedEntries(), n=rows.length;
 const tab=document.getElementById("tab-missed");
 if(tab)tab.textContent="Missed Sessions ("+n+")";
 const badge=document.getElementById("missed-count");
 if(badge)badge.textContent="("+n+")";
 const list=document.getElementById("missed-list");
 if(list){list.textContent="";if(!rows.length)list.appendChild(el("p","muted","No sessions are marked as missed."));rows.forEach(x=>list.appendChild(itemButton(x)));}
}
function renderDashboard(){updateMissedTab();
 const box=document.getElementById("dashboard-overview");box.textContent="";
 const stats=[[Object.keys(modules).length,"Modules"],[allEntries().length,"Scheduled sessions"],[resources.length,"Shared resources"]];
 stats.forEach(([v,l])=>{const c=el("div","card");c.append(el("div","stat",String(v)),el("div","statlabel",l));box.appendChild(c);});
 const upcoming=document.getElementById("dashboard-upcoming");upcoming.textContent="";const entries=allEntries().slice(0,5);
 if(!entries.length)upcoming.appendChild(el("div","muted","No timetable sessions have been published yet."));
 entries.forEach(x=>upcoming.appendChild(itemButton(x)));
 const recent=document.getElementById("dashboard-recent");recent.textContent="";
 apiRequest("GET","/api/history").then(rows=>{recent.textContent="";if(!rows.length)recent.appendChild(el("div","muted","No recent additions."));rows.slice(0,5).forEach(r=>recent.appendChild(el("div","item",`${r.role} · ${r.summary}`)));}).catch(()=>recent.textContent="Recent activity is unavailable.");
}
function renderMonthly(){
 const root=workspace(...WORKSPACE_META.monthly),card=el("div","card"),grid=el("div","month-grid");
 const year=2026,month=10,daysInMonth=new Date(year,month+1,0).getDate();
 card.appendChild(el("h3",null,"November 2026 · Weekdays"));
 ["Mon","Tue","Wed","Thu","Fri"].forEach(d=>grid.appendChild(el("div","month-dow",d)));
 const events=allEntries();
 for(let day=1;day<=daysInMonth;day++){
  const date=new Date(year,month,day);if(date.getDay()===0||date.getDay()===6)continue;
  if(!grid.dataset.padded){grid.dataset.padded="1";for(let i=1;i<date.getDay();i++)grid.appendChild(el("div","month-empty"));}
  const cell=el("div","month-day"),num=el("strong",null,String(day));cell.appendChild(num);
  const col=day>=9&&day<=13?day-9:-1;
  if(col>=0){const list=events.filter(x=>x.c===col);list.forEach(x=>cell.appendChild(el("span","month-event",x.label)));}
  grid.appendChild(cell);
 }
 card.appendChild(grid);root.appendChild(card);
 root.appendChild(el("p","muted","The month view displays the dated teaching week currently configured in the shared timetable. Additional dates appear as dated calendar records are added."));
}
function renderUpcoming(){const root=workspace(...WORKSPACE_META.upcoming);const list=el("div","cards");const entries=allEntries();entries.forEach(x=>{const c=el("div","card");c.append(el("h3",null,x.label),el("div","muted",`${days[x.c]} ${dates[x.c]} · ${x.startTime}–${x.endTime}`));if(x.sub)c.appendChild(el("p","muted",x.sub));list.appendChild(c);});loadRows("examinations").then(rows=>rows.forEach(r=>{const d=r.data||{},c=el("div","card");c.append(el("h3",null,d.title||r.id),el("div","muted",[d.date,d.time,d.venue].filter(Boolean).join(" · ")));list.appendChild(c);})).catch(()=>{});root.appendChild(list);if(!entries.length)root.appendChild(el("p","muted","No upcoming timetable sessions are currently recorded."));}

// ---- Facilitator initials (titles ignored: "Dr D Mzinza" -> "DM") and photographs ----
const NAME_TITLES=/\b(professor|prof|doctor|dr|mr|mrs|ms|miss|mx)\b\.?/gi;
function facilitatorInitials(name){
 const words=String(name||"").replace(NAME_TITLES," ").replace(/\./g," ").split(/\s+/).filter(Boolean);
 if(!words.length)return "?";
 if(words.length===1)return words[0].slice(0,2).toUpperCase();
 return (words[0][0]+words[words.length-1][0]).toUpperCase();
}
const PHOTO_TYPES=["image/jpeg","image/png","image/webp","image/gif","image/avif","image/bmp"];
function facilitatorAvatar(d){
 const wrap=document.createElement("span");wrap.className="avatar";
 if(typeof d.photo==="string"&&/^data:image\/(jpeg|png|webp|gif|avif|bmp);base64,/.test(d.photo)){const img=document.createElement("img");img.src=d.photo;img.alt=String(d.name||"Facilitator")+" photograph";wrap.appendChild(img);}
 else{wrap.textContent=facilitatorInitials(d.name);wrap.setAttribute("aria-label","Initials "+facilitatorInitials(d.name));}
 return wrap;
}
function resizeImage(file,max=320){
 return new Promise((resolve,reject)=>{
  if(!PHOTO_TYPES.includes(file.type)){reject(new Error("Choose a JPEG, PNG, WebP, GIF, AVIF or BMP photograph."));return;}
  if(file.size>12*1024*1024){reject(new Error("That photograph is larger than 12 MB."));return;}
  const url=URL.createObjectURL(file),img=new Image();
  img.onload=()=>{const k=Math.min(1,max/Math.max(img.width,img.height)),c=document.createElement("canvas");c.width=Math.max(1,Math.round(img.width*k));c.height=Math.max(1,Math.round(img.height*k));
   const g=c.getContext("2d");g.fillStyle="#fff";g.fillRect(0,0,c.width,c.height);g.drawImage(img,0,0,c.width,c.height);URL.revokeObjectURL(url);resolve(c.toDataURL("image/jpeg",.86));};
  img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error("That image could not be read by this browser."));};
  img.src=url;
 });
}
function photoPicker(label){
 const wrap=document.createElement("label");wrap.className="photo-picker";wrap.textContent=label||"Photograph (optional)";
 const input=document.createElement("input");input.type="file";input.accept=PHOTO_TYPES.join(",");wrap.appendChild(input);return {wrap,input};
}
const MANAGED_FIELDS={facilitators:["name","title","department","email","phone"],examinations:["title","date","time","venue","notes"],recurring:["title","frequency","day","time","venue","notes"]};
const MANAGED_LABELS={facilitators:"Facilitator",examinations:"Examination",recurring:"Recurring activity"};
async function renderManaged(collection){const [title,lead]=WORKSPACE_META[collection],root=workspace(title,lead);{const form=el("div","card res-form");form.appendChild(el("h3",null,"Add "+MANAGED_LABELS[collection].toLowerCase()));const fields={};MANAGED_FIELDS[collection].forEach(k=>{if(collection==="recurring"&&k==="day"){const select=document.createElement("select");select.setAttribute("aria-label","Weekday");["Choose weekday","Monday","Tuesday","Wednesday","Thursday","Friday"].forEach((name,i)=>{const option=document.createElement("option");option.value=i?name:"";option.textContent=name;select.appendChild(option);});select.style.cssText="display:block;width:100%;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--field);color:var(--text);font:inherit";fields[k]=select;}else{const type=k==="date"?"date":k==="time"?"time":"text";fields[k]=fieldInput(k[0].toUpperCase()+k.slice(1),k==="notes"?500:180,type);}form.appendChild(fields[k]);});let photoInput=null;if(collection==="facilitators"){photoInput=photoPicker();form.appendChild(photoInput.wrap);}const add=el("button","primary","Save "+MANAGED_LABELS[collection].toLowerCase());add.type="button";add.addEventListener("click",()=>requestEditing(async()=>{const data={};Object.entries(fields).forEach(([k,v])=>data[k]=v.value.trim());if(!data[MANAGED_FIELDS[collection][0]]){statusEl.className="status error";statusEl.textContent="Please enter a title or name.";return;}if(data.date){const now=new Date(),today=new Date(now.getFullYear(),now.getMonth(),now.getDate()),max=new Date(now.getFullYear()+3,now.getMonth(),now.getDate()),chosen=new Date(data.date+"T00:00:00");if(isNaN(chosen)||chosen<today||chosen>max){statusEl.className="status error";statusEl.textContent="Choose a date between today and three years from today.";return;}}if(photoInput&&photoInput.input.files[0]){try{data.photo=await resizeImage(photoInput.input.files[0]);}catch(e){statusEl.className="status error";statusEl.textContent=e.message;return;}}try{await saveRow(collection,makeId(collection.slice(0,3)),data);statusEl.className="status ok";statusEl.textContent="Saved and shared with all users.";renderManaged(collection);}catch(e){writeFailed(e);}}));form.appendChild(add);root.appendChild(form);}const list=el("div","cards");root.appendChild(list);try{const rows=await loadRows(collection);if(!rows.length)list.appendChild(el("p","muted","No records have been added yet."));rows.forEach(row=>{const d=row.data||{},c=el("div","card");if(collection==="facilitators")c.appendChild(facilitatorAvatar(d));c.appendChild(el("h3",null,d.title||d.name||row.id));const detail=MANAGED_FIELDS[collection].filter(k=>d[k]).map(k=>`${k[0].toUpperCase()+k.slice(1)}: ${d[k]}`).join(" · ");if(detail)c.appendChild(el("p","muted",detail));if(collection==="facilitators"&&editingUnlocked){const pp=photoPicker("Change photograph");pp.input.addEventListener("change",async()=>{const f=pp.input.files[0];if(!f)return;try{const photo=await resizeImage(f);await saveRow(collection,row.id,{...d,photo});statusEl.className="status ok";statusEl.textContent="Photograph updated and shared.";renderManaged(collection);}catch(e){statusEl.className="status error";statusEl.textContent=e.message||"Photograph could not be saved.";}});c.appendChild(pp.wrap);}if(editingUnlocked){const del=el("button","res-del","Remove record");del.type="button";del.addEventListener("click",async()=>{if(!confirm("Remove this shared record?"))return;try{await deleteRow(collection,row.id);renderManaged(collection);}catch(e){writeFailed(e);}});c.appendChild(del);}list.appendChild(c);});}catch(e){list.appendChild(el("p","muted","Could not load shared records: "+e.message));}}
async function renderReminderCard(root){
 const card=el("div","card res-form");
 card.appendChild(el("h3",null,"WhatsApp reminders"));
 card.appendChild(el("p","muted","Everyone on the list gets a WhatsApp message before each session, sent as “Maternal & Neonatal Health Smart Time Table”. Choose 10, 20 or 30 minutes."));
 const statusLine=el("p","muted","Checking WhatsApp delivery…");
 card.appendChild(statusLine);
 let info=null;
 try{info=await apiRequest("GET","/api/reminders");}catch(e){statusLine.textContent="Reminder status is unavailable: "+e.message;}
 if(info){
  const wa=info.whatsapp||{},cfg=info.settings||{};
  statusLine.textContent=wa.configured
   ?`Delivery ready · sender "${wa.sender}" · WhatsApp Cloud API ${wa.apiVersion}`
   :`Not configured yet — add ${(wa.missing||[]).join(" and ")||"WhatsApp credentials"} on the server, then send the sample again.`;
  const leadRow=el("div","reminder-leads");
  [10,20,30].forEach(minutes=>{
   const label=el("label","reminder-lead"),box=document.createElement("input");
   box.type="checkbox";box.value=String(minutes);box.checked=(cfg.leadMinutes||[10,20,30]).includes(minutes);box.disabled=!editingUnlocked;
   label.append(box,document.createTextNode(" "+minutes+" min before"));leadRow.appendChild(label);
  });
  card.appendChild(leadRow);
  card.appendChild(el("label","field-label","Recipient WhatsApp numbers (one per line)"));
  const numbers=document.createElement("textarea");
  numbers.rows=3;numbers.maxLength=2000;numbers.placeholder="+265881988156";numbers.disabled=!editingUnlocked;
  numbers.value=(cfg.recipients||[]).join("\n");
  numbers.style.cssText="display:block;width:100%;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--field);color:var(--text);font:inherit";
  card.appendChild(numbers);
  const save=el("button",null,"Save reminder settings");save.type="button";save.disabled=!editingUnlocked;
  save.addEventListener("click",async()=>{
   const leadMinutes=[...card.querySelectorAll(".reminder-leads input:checked")].map(b=>Number(b.value)).sort((a,b)=>a-b);
   const recipients=numbers.value.split(/[\n,;]+/).map(x=>x.trim()).filter(Boolean);
   if(!leadMinutes.length){statusEl.className="status error";statusEl.textContent="Choose at least one reminder time (10, 20 or 30 minutes).";return;}
   try{await saveRow("settings","reminders",{enabled:true,leadMinutes,recipients,updatedAt:Date.now()});statusEl.className="status ok";statusEl.textContent="Reminder settings saved for everyone.";renderCommunications();}catch(e){writeFailed(e);}
  });
  card.appendChild(save);
  const testRow=el("div","reminder-test");
  const testNumber=fieldInput("WhatsApp number for the sample","40");
  testNumber.value="+265881988156";testNumber.disabled=!editingUnlocked;
  const testBtn=el("button","primary","Send sample reminder");testBtn.type="button";testBtn.disabled=!editingUnlocked;
  testBtn.addEventListener("click",async()=>{
   testBtn.disabled=true;statusEl.className="status";statusEl.textContent="Sending the sample WhatsApp reminder…";
   try{const r=await apiRequest("POST","/api/reminders/test",{to:testNumber.value.trim()});statusEl.className="status ok";statusEl.textContent=`Sample sent to +${r.to} from "${r.sender}".`;}
   catch(e){statusEl.className="status error";statusEl.textContent=e.message||"The sample could not be sent.";}
   finally{testBtn.disabled=!editingUnlocked;}
  });
  testRow.append(testNumber,testBtn);card.appendChild(testRow);
  const run=el("button",null,"Check the timetable now");run.type="button";run.disabled=!editingUnlocked;
  run.addEventListener("click",async()=>{
   try{const r=await apiRequest("POST","/api/reminders/run",{});statusEl.className="status ok";statusEl.textContent=`Checked ${r.checked||0} due reminder(s); sent ${r.sent||0}.`;}
   catch(e){statusEl.className="status error";statusEl.textContent=e.message;}
  });
  card.appendChild(run);
  if(info.recent&&info.recent.length){
   const log=el("div","reminder-log");
   info.recent.slice(0,6).forEach(r=>log.appendChild(el("div","item",`${r.status} · ${r.code||""} · ${r.lead} min · ${r.sent_at}`)));
   card.appendChild(log);
  }
 }
 root.appendChild(card);
}
async function renderCommunications(){const root=workspace(...WORKSPACE_META.communications);if(editingUnlocked){const form=el("div","card res-form");form.appendChild(el("h3",null,"Publish an announcement or communication"));const title=fieldInput("Announcement title",160),message=fieldInput("Message / communication details",1000),link=fieldInput("Optional WhatsApp or web link",400,"url");form.append(title,message,link);const add=el("button","primary","Publish communication");add.type="button";add.addEventListener("click",async()=>{if(!title.value.trim()||!message.value.trim()){statusEl.className="status error";statusEl.textContent="Enter an announcement title and message.";return;}try{await saveRow("communications",makeId("com"),{title:title.value.trim(),message:message.value.trim(),url:safeUrl(link.value),createdAt:Date.now()});statusEl.className="status ok";statusEl.textContent="Communication published for all users.";renderCommunications();}catch(e){writeFailed(e);}});form.appendChild(add);root.appendChild(form);}const list=el("div","cards");root.appendChild(list);try{const rows=await loadRows("communications");if(!rows.length)list.appendChild(el("p","muted","No communications have been published."));rows.forEach(r=>{const d=r.data||{},c=el("div","card");c.append(el("h3",null,d.title||"Announcement"),el("p",null,d.message||""));if(d.url){const a=el("a","res-link","Open shared link");a.href=d.url;a.target="_blank";a.rel="noopener noreferrer";c.appendChild(a);}const wa=el("a","res-link","Share via WhatsApp");wa.href="https://wa.me/?text="+encodeURIComponent([d.title,d.message,d.url].filter(Boolean).join("\n"));wa.target="_blank";wa.rel="noopener noreferrer";c.appendChild(wa);if(editingUnlocked){const del=el("button","res-del","Remove");del.type="button";del.onclick=async()=>{try{await deleteRow("communications",r.id);renderCommunications();}catch(e){writeFailed(e);}};c.appendChild(del);}list.appendChild(c);});}catch(e){list.appendChild(el("p","muted",e.message));}const resourcesCard=el("div","card");resourcesCard.appendChild(el("h3",null,"Shared resources"));root.appendChild(resourcesCard);renderResources();const existing=document.getElementById("res-list");if(existing)resourcesCard.appendChild(existing);const f=document.getElementById("res-form-wrap");if(f)resourcesCard.appendChild(f);renderReminderCard(root);}
async function renderHistoryPage(){const root=workspace(...WORKSPACE_META.history);const card=el("div","card");root.appendChild(card);try{const rows=await apiRequest("GET","/api/history");if(!rows.length)card.appendChild(el("p","muted","No new sessions or activities have been recorded."));rows.forEach(r=>{const when=new Date(r.at).toLocaleString();card.appendChild(el("div","item",`${r.role} · ${r.summary} · ${when}`));});}catch(e){card.appendChild(el("p","muted",e.message));}}
function renderExportPage(){const root=workspace(...WORKSPACE_META.export);const card=el("div","card res-form");card.appendChild(el("h3",null,"Download and share calendar data"));[["Download editable Excel timetable (.xlsx)",()=>window.downloadTimetableExcel()],["Download timetable PDF",()=>document.getElementById("print").click()],["Export timetable CSV",()=>window.exportTimetableCSV()],["Download high-resolution timetable photo — PNG",()=>downloadTimetableImage("image/png")],["Download high-resolution timetable photo — JPEG",()=>downloadTimetableImage("image/jpeg")],["Download high-resolution timetable photo — WebP",()=>downloadTimetableImage("image/webp")],["Download shared JSON backup",()=>window.downloadSharedBackup()]].forEach(([label,action])=>{const b=el("button",null,label);b.type="button";b.addEventListener("click",action);card.appendChild(b);});const info=el("p","muted","The Excel workbook includes a Monday–Friday weekly view, editable session details, filters and links between the timetable and session register. Photo exports are rendered at 4× scale in PNG, JPEG or WebP. They are image copies and are not editable timetable data.");card.appendChild(info);root.appendChild(card);}
async function downloadTimetableImage(mime){
 const status=document.getElementById("status"),weekly=document.getElementById("view-weekly"),wasHidden=weekly.hidden;
 if(typeof window.html2canvas!=="function"){status.className="status error";status.textContent="The image export library did not load. Check your internet connection and try again.";return;}
 try{
  status.className="status";status.textContent="Rendering high-resolution timetable image…";
  build();weekly.hidden=false;
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  const target=weekly.querySelector(".wrap");if(!target)throw new Error("The weekly timetable is not available.");
  const canvas=await window.html2canvas(target,{scale:4,useCORS:true,backgroundColor:getComputedStyle(document.body).backgroundColor,logging:false,windowWidth:Math.max(document.documentElement.clientWidth,target.scrollWidth),onclone:doc=>{const cloned=doc.querySelector("#view-weekly");if(cloned)cloned.hidden=false;}});
  const actualMime=mime==="image/webp"&&!canvas.toDataURL("image/webp").startsWith("data:image/webp")?"image/png":mime;
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error("The browser could not encode this image.")),actualMime,actualMime==="image/png"?undefined:.98));
  const ext=actualMime.split("/")[1],url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=`MNH-Smart-Calendar-Weekly-Timetable.${ext}`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
  status.className="status ok";status.textContent=`High-resolution ${ext.toUpperCase()} timetable image downloaded.`;
 }catch(error){console.error(error);status.className="status error";status.textContent="The timetable image could not be created: "+error.message;}finally{weekly.hidden=wasHidden;}
}
window.downloadTimetableImage=downloadTimetableImage;
function renderSettingsPage(){const root=workspace(...WORKSPACE_META.settings);const card=el("div","card res-form");card.appendChild(el("h3",null,"Appearance"));const label=el("label",null,"Dashboard theme");const sel=document.getElementById("theme").cloneNode(true);sel.id="theme-visible";sel.hidden=false;sel.style.cssText="padding:10px;background:var(--field);color:var(--text);border:1px solid var(--line);border-radius:7px";sel.value=state.theme;sel.onchange=()=>{document.getElementById("theme").value=sel.value;document.getElementById("theme").dispatchEvent(new Event("change"));};card.append(label,sel);root.appendChild(card);
 const access=el("div","card res-form");access.appendChild(el("h3",null,"Access and security"));access.appendChild(el("p","muted",editingUnlocked?`Editing unlocked · ${currentRole}`:"Viewing is open; editing requires an authorised password."));const b=el("button","primary","\u270F "+(editingUnlocked?"Lock editing":"Unlock editing"));b.type="button";b.onclick=()=>document.getElementById(editingUnlocked?"lock":"unlock").click();access.appendChild(b);const hdr=el("button",null,"Edit calendar title and subtitle");hdr.type="button";hdr.disabled=!editingUnlocked;hdr.onclick=()=>document.getElementById("edit-header").click();access.appendChild(hdr);root.appendChild(access);
 const alarm=el("div","card res-form");alarm.appendChild(el("h3",null,"Alarms and reminders"));const alarmBtn=el("button",null,"Manage alarms and reminders");alarmBtn.type="button";alarmBtn.onclick=()=>document.getElementById("alarms").click();alarm.appendChild(alarmBtn);root.appendChild(alarm);
 const data=el("div","card res-form");data.appendChild(el("h3",null,"Data and backups"));[["Save changes for everyone",()=>document.getElementById("save").click(),true],["Download shared JSON backup",()=>window.downloadSharedBackup(),true],["Restore from JSON backup",()=>document.getElementById("import").click(),true],["Download PDF",()=>document.getElementById("print").click(),false]].forEach(([label,action,locked])=>{const x=el("button",null,label);x.type="button";x.disabled=locked&&!editingUnlocked;x.onclick=action;data.appendChild(x);});root.appendChild(data);}
function itemButton(x){
 const b=el("button","item");b.type="button";
 b.appendChild(el("span","it",x.timeLabel));
 const n=el("span","in",x.label);if(x.sub)n.appendChild(el("span","is",x.sub));b.appendChild(n);
 b.addEventListener("click",()=>showSessionDetails(x));
 return b;
}
function renderSchedule(){
 const root=document.getElementById("schedule-body");root.textContent="";
 const ti=todayIndexFor(weekOffset);
 days.forEach((dn,c)=>{
  const card=el("div","card"+(c===ti?" today":""));
  const h=el("h3",null,dn+" "+dates[c]);if(c===ti)h.appendChild(el("span","pill","Today"));
  card.appendChild(h);
  const list=dayEntries(c);
  if(!list.length)card.appendChild(el("div","muted","Nothing scheduled."));
  list.forEach(x=>card.appendChild(itemButton(x)));
  root.appendChild(card);
 });
}
function renderModules(){
 const root=workspace(...WORKSPACE_META.modules);const body=el("div","cards");root.appendChild(body);
 {
  const form=el("div","card");form.style.marginBottom="12px";form.appendChild(el("h3",null,"Add a module"));
  const code=document.createElement("input");code.placeholder="Module code";code.maxLength=40;code.setAttribute("aria-label","Module code");
  const title=document.createElement("input");title.placeholder="Full module title";title.maxLength=160;title.setAttribute("aria-label","Full module title");
  const targetSessions=document.createElement("input");targetSessions.type="number";targetSessions.min="0";targetSessions.step="1";targetSessions.placeholder="Semester target: sessions (optional)";targetSessions.setAttribute("aria-label","Semester target sessions");
  const targetHours=document.createElement("input");targetHours.type="number";targetHours.min="0";targetHours.step="0.5";targetHours.placeholder="Semester target: teaching hours (optional)";targetHours.setAttribute("aria-label","Semester target hours");
  const fac=document.createElement("select");fac.setAttribute("aria-label","Assign lecturer");const none=document.createElement("option");none.value="";none.textContent="No lecturer assigned";fac.appendChild(none);
  facilitatorRecords.forEach(item=>{const option=document.createElement("option");option.value=String(item.id);option.textContent=String(item.data.name);fac.appendChild(option);});
  [code,title,targetSessions,targetHours,fac].forEach(x=>{x.style.cssText="display:block;width:100%;margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:6px;background:var(--field);color:var(--text);";form.appendChild(x);});
  const add=el("button","primary","Add module");add.type="button";add.addEventListener("click",()=>requestEditing(async()=>{await addSharedModule(code.value,title.value,fac.value,{semesterTargetSessions:targetSessions.value===""?null:Number(targetSessions.value),semesterTargetHours:targetHours.value===""?null:Number(targetHours.value)});}));form.appendChild(add);root.insertBefore(form,body);
 }
 const all=allEntries();
 const sessionsFor=code=>all.filter(x=>x.label===code);
 const addCard=(code,title,fac)=>{
  const card=el("div","card");card.appendChild(el("h3",null,code));
  if(title&&title!==code)card.appendChild(el("div",null,title));
  if(fac)card.appendChild(el("div","muted","Facilitator: "+fac));
  if(editingUnlocked){
   const targetS=document.createElement("input"),targetH=document.createElement("input");
   targetS.type="number";targetS.min="0";targetS.step="1";targetS.placeholder="Semester target sessions";targetS.value=modules[code]?.semesterTargetSessions??"";
   targetH.type="number";targetH.min="0";targetH.step="0.5";targetH.placeholder="Semester target hours";targetH.value=modules[code]?.semesterTargetHours??"";
   [targetS,targetH].forEach(input=>{input.style.cssText="display:block;width:100%;margin:6px 0;padding:9px;border:1px solid var(--line);border-radius:6px;background:var(--field);color:var(--text)";card.appendChild(input);});
   const saveTargets=el("button","primary","Save semester targets");saveTargets.type="button";saveTargets.onclick=async()=>{const data={...modules[code],semesterTargetSessions:targetS.value===""?null:Number(targetS.value),semesterTargetHours:targetH.value===""?null:Number(targetH.value),updatedAt:Date.now()};try{if(cloud)await cloud.doc("modules/"+code).set(data);else await apiRequest("PUT","/api/doc/modules/"+encodeURIComponent(code),data);modules[code]=data;statusEl.className="status ok";statusEl.textContent="Semester targets saved.";renderModules();}catch(e){writeFailed(e);}};card.appendChild(saveTargets);
  }
  const s=sessionsFor(code),mins=s.reduce((a,x)=>a+x.mins,0);
  card.appendChild(el("div","muted","This week: "+s.length+" session"+(s.length===1?"":"s")+(s.length?" · "+fmtH(mins):"")));
  s.forEach(x=>{const b=el("button","item");b.type="button";b.append(el("span","it",days[x.c]),el("span","in",x.timeLabel));b.addEventListener("click",()=>showSessionDetails(x));card.appendChild(b);});
  body.appendChild(card);
 };
 Object.keys(modules).forEach(code=>addCard(code,modules[code].title,facilitatorFor(code)));
 const others=[];all.forEach(x=>{if(!modules[x.label]&&!others.includes(x.label))others.push(x.label);});
 others.forEach(l=>addCard(l,"",""));
}
async function renderAnalytics(){
 const root=document.getElementById("analytics-body");root.textContent="";
 try{
  const data=await apiRequest("GET","/api/analytics"),summary=data.summary||{},modulesData=data.modules||[];
  const stats=el("div","cards");
  [[summary.sessions||0,"Timetable entries"],[fmtH(summary.hours||0),"Scheduled teaching hours"],[summary.missed||0,"Marked missed (timetable)"],[`${summary.missedPercent||0}%`,"Marked-missed share"],[summary.online||0,"Scheduled online"],[summary.faceToFace||0,"Scheduled face-to-face"]].forEach(([v,l])=>{const c=el("div","card");c.append(el("div","stat",String(v)),el("div","statlabel",l));stats.appendChild(c);});root.appendChild(stats);
  const chart=(title,rows,suffix="")=>{const card=el("div","card");card.style.marginTop="12px";card.appendChild(el("h3",null,title));const max=Math.max(1,...rows.map(r=>Number(r.value)||0));rows.forEach(r=>{const row=el("div","barrow"),bar=el("div","bar"),fill=document.createElement("i");fill.style.width=Math.max(0,Math.min(100,(Number(r.value)||0)/max*100))+"%";bar.appendChild(fill);row.append(el("span",null,r.label),bar,el("span","muted",`${r.value}${suffix}`));card.appendChild(row);});root.appendChild(card);};
  chart("Delivery mode · timetable entries",[{label:"Online",value:summary.online||0},{label:"Face-to-face",value:summary.faceToFace||0},{label:"Unspecified",value:summary.unspecified||0}]);
  chart("Weekly teaching hours by module",modulesData.map(m=>({label:m.code,value:m.weeklyHours||0}))," h");
  const grid=el("div","cards");modulesData.forEach(m=>{const c=el("div","card");c.append(el("h3",null,m.code),el("p","muted",m.title||"Module title not recorded"));c.append(el("div",null,`This week: ${m.weeklySessions} sessions · ${m.weeklyHours} hours`),el("div",null,`Semester to date: ${m.semesterTracked?`${m.semesterSessions} sessions · ${m.semesterHours} hours`:"Not yet tracked — dated attendance records are required"}`),el("div",null,`Semester target: ${m.targetSessions??"Not set"} sessions · ${m.targetHours??"Not set"} hours`),el("div",null,`Marked missed: ${m.missedSessions} · Scheduled online: ${m.onlineSessions} · Scheduled face-to-face: ${m.faceToFaceSessions}`));
   if(m.semesterTracked&&m.targetSessions!=null&&m.targetSessions>0){const pct=Math.min(100,m.semesterSessions/m.targetSessions*100);const bar=el("div","bar"),fill=document.createElement("i");fill.style.width=pct+"%";bar.appendChild(fill);c.append(el("div","muted",`Session target progress: ${pct.toFixed(1)}%`),bar);}
   if(m.semesterTracked&&m.targetHours!=null&&m.targetHours>0){const pct=Math.min(100,m.semesterHours/m.targetHours*100);const bar=el("div","bar"),fill=document.createElement("i");fill.style.width=pct+"%";bar.appendChild(fill);c.append(el("div","muted",`Hours target progress: ${pct.toFixed(1)}%`),bar);}
   grid.appendChild(c);});root.appendChild(grid);
  root.appendChild(el("p","muted",data.note||"Only sessions with an explicitly recorded status are counted as completed or missed. Semester totals include all dated session records currently stored."));
 }catch(e){root.appendChild(el("div","card",e.status===403?"Analytics are restricted to HOD, coordinator and executive dean accounts.":"Analytics could not be loaded: "+e.message));}
}
// ---- resources (shared) ----
function safeUrl(u){
 u=String(u||"").trim();if(!u)return "";if(!/^https?:\/\//i.test(u))u="https://"+u;
 try{const x=new URL(u);return(x.protocol==="http:"||x.protocol==="https:")?x.href:"";}catch(e){return "";}
}
function cleanRes(v){return{title:String(v&&v.title||"").trim().slice(0,120),url:safeUrl(v&&v.url),note:String(v&&v.note||"").trim().slice(0,200),createdAt:+(v&&v.createdAt)||0};}
function cacheResources(){try{localStorage.setItem(resKey,JSON.stringify(resources));}catch(e){}}
function loadResources(){try{const r=JSON.parse(localStorage.getItem(resKey)||"[]");if(Array.isArray(r))resources=r.map(x=>({id:String(x.id||""),...cleanRes(x)})).filter(x=>x.id&&x.title&&x.url);}catch(e){}}
async function addResource(t,u,n){
 const rec=cleanRes({title:t,url:u,note:n,createdAt:Date.now()});
 if(!rec.title||!rec.url){statusEl.className="status error";statusEl.textContent="Enter a title and a valid web address.";return false;}
 const r={id:"r"+Date.now().toString(36)+Math.random().toString(36).slice(2,6),...rec};
 resources.push(r);cacheResources();renderResources();
 try{
  const data={title:r.title,url:r.url,note:r.note,createdAt:r.createdAt};
  if(cloud)await cloud.doc("resources/"+r.id).set(data);
  else await window.mnhApi.request("PUT","/api/doc/resources/"+encodeURIComponent(r.id),data);
  statusEl.className="status ok";statusEl.textContent="Saved for everyone.";
 }catch(e){writeFailed(e);}
 return true;
}
async function removeResource(id){
 resources=resources.filter(x=>x.id!==id);cacheResources();renderResources();
 try{
  if(cloud)await cloud.doc("resources/"+id).delete();
  else await window.mnhApi.request("DELETE","/api/doc/resources/"+encodeURIComponent(id));
  statusEl.className="status ok";statusEl.textContent="Removed for everyone.";
 }catch(e){writeFailed(e);}
}
function renderResources(){
 const list=document.getElementById("res-list"),form=document.getElementById("res-form-wrap");
 list.textContent="";
 if(!resources.length)list.appendChild(el("p","muted","No resources have been added yet."));
 resources.forEach(r=>{
  const card=el("div","card res");
  const a=el("a","res-link",r.title);a.href=r.url;a.target="_blank";a.rel="noopener noreferrer";card.appendChild(a);
  if(r.note)card.appendChild(el("div","muted",r.note));
  card.appendChild(el("div","res-url muted",r.url));
  if(editingUnlocked){const d=el("button","res-del","Remove");d.type="button";d.addEventListener("click",()=>removeResource(r.id));card.appendChild(d);}
  list.appendChild(card);
 });
 form.textContent="";
 if(editingUnlocked){
  const f=el("div","res-form");f.appendChild(el("h3",null,"Add a resource"));
  const mk=(ph,max)=>{const i=document.createElement("input");i.type="text";i.placeholder=ph;i.maxLength=max;i.setAttribute("aria-label",ph);return i;};
  const t=mk("Title",120),u=mk("Web address (https://…)",300),n=mk("Short note (optional)",200);
  const b=el("button","primary","Add resource");b.type="button";
  b.addEventListener("click",async()=>{if(await addResource(t.value,u.value,n.value)){t.value=u.value=n.value="";}});
  f.append(t,u,n,b);form.appendChild(f);
 }
}
function subscribeExtras(db){
 db.collection("settings").onSnapshot(snap=>{snap.docs.forEach(d=>{if(d.id==="header"){const v=d.data();applyHeader({title:v.title,subtitle:v.subtitle});}});},()=>{});
 db.collection("facilitators").onSnapshot(snap=>{
  facilitatorRecords=snap.docs.map(d=>({id:d.id,data:d.data()||{}})).filter(x=>x.data.name);
  build();if(currentView==="modules")renderModules();
 },()=>{});
 db.collection("resources").onSnapshot(snap=>{
  if(snap.metadata&&snap.metadata.fromCache&&snap.empty)return;
  const remote=snap.docs.map(d=>({id:d.id,...cleanRes(d.data())})).filter(x=>x.title&&x.url).sort((a,b)=>a.createdAt-b.createdAt);
  let seen=false;try{seen=localStorage.getItem(resCloudKey)==="1";}catch(e){}
  if(!remote.length&&!seen&&resources.length)return;   // first run: keep the local copy until saved
  if(remote.length){try{localStorage.setItem(resCloudKey,"1");}catch(e){}}
  resources=remote;cacheResources();renderResources();
 },()=>{});
}
function initHeader(){
 initHeaderFromLocal();loadResources();
 const bell=document.getElementById("hd-bell"),panel=document.getElementById("bell-panel");
 bell.addEventListener("click",e=>{e.stopPropagation();const open=panel.hidden;if(open){closeMenu();refreshHeader();}panel.hidden=!open;bell.setAttribute("aria-expanded",String(open));});
 panel.addEventListener("click",e=>e.stopPropagation());
 document.addEventListener("click",()=>{if(!panel.hidden)closeBell();});
 document.getElementById("menu-btn").addEventListener("click",closeBell);
 document.addEventListener("keydown",e=>{if(e.key==="Escape"){if(!panel.hidden){closeBell();bell.focus();}hideDialog("header-dialog");}});
 document.querySelectorAll(".view-tab[data-view],.hd-tab[data-view],.menu-nav[data-view]").forEach(t=>t.addEventListener("click",e=>{e.preventDefault();closeMenu();closeBell();if(t.dataset.view==="analytics"&&!analyticsUnlocked){requestAnalytics();return;}try{location.hash=t.dataset.view;}catch(x){}showView(t.dataset.view);}));
 window.addEventListener("hashchange",()=>showView(location.hash.slice(1)));
 // header editing
 document.getElementById("edit-header").addEventListener("click",()=>{
  if(!editingUnlocked)return;
  document.getElementById("header-title-input").value=headerCfg.title;document.getElementById("header-sub-input").value=headerCfg.subtitle;showDialog("header-dialog");
 });
 document.getElementById("header-cancel").addEventListener("click",()=>hideDialog("header-dialog"));
 document.getElementById("header-reset").addEventListener("click",()=>{document.getElementById("header-title-input").value=HEADER_DEFAULT.title;document.getElementById("header-sub-input").value=HEADER_DEFAULT.subtitle;});
 document.getElementById("header-save").addEventListener("click",()=>{
  const t=document.getElementById("header-title-input").value;
  if(!t.trim()){statusEl.className="status error";statusEl.textContent="The header title can’t be empty.";return;}
  hideDialog("header-dialog");saveHeader({title:t,subtitle:document.getElementById("header-sub-input").value});
 });
 // keep views and header fresh when the timetable or editing state changes
 const _build=build;build=function(){_build();refreshHeader();updateMissedTab();if(currentView==="dashboard")renderDashboard();else if(currentView==="modules")renderModules();};
 const _se=setEditing;setEditing=function(v){_se(v);if(currentView==="communications")renderCommunications();if(currentView==="modules")renderModules();if(currentView==="facilitators"||currentView==="examinations"||currentView==="recurring")renderView(currentView);};
 setInterval(refreshHeader,30000);
 refreshHeader();showView(location.hash.slice(1)||"weekly");
 initWeekNav();
}
// ---- Hamburger menu ----
const menuBtn=document.getElementById("menu-btn"),menuPanel=document.getElementById("menu-panel");
function openMenu(){menuPanel.hidden=false;menuBtn.setAttribute("aria-expanded","true");menuBtn.setAttribute("aria-label","Close menu");}
function closeMenu(){menuPanel.hidden=true;menuBtn.setAttribute("aria-expanded","false");menuBtn.setAttribute("aria-label","Open menu");}
menuBtn.addEventListener("click",e=>{e.stopPropagation();menuPanel.hidden?openMenu():closeMenu();});
menuPanel.addEventListener("click",e=>{e.stopPropagation();if(e.target.closest("button:not([data-keep])"))closeMenu();});
document.addEventListener("click",()=>{if(!menuPanel.hidden)closeMenu();});
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!menuPanel.hidden){closeMenu();menuBtn.focus();}});
// Status messages are temporary: they clear themselves so the dashboard stays clean.
let statusTimer;
new MutationObserver(()=>{
 clearTimeout(statusTimer);
 if(statusEl.textContent&&!statusEl.classList.contains("error"))statusTimer=setTimeout(()=>{statusEl.textContent="";statusEl.className="status";},5000);
}).observe(statusEl,{childList:true,characterData:true,subtree:true});
// ---- Tap-to-see-name labels for icon buttons ----
const tipEl=document.createElement("div");tipEl.className="tip";tipEl.setAttribute("role","status");document.body.appendChild(tipEl);let tipT;
function showTip(target,text){
 const r=target.getBoundingClientRect();tipEl.textContent=text;tipEl.classList.add("show");
 const w=tipEl.offsetWidth;tipEl.style.left=Math.min(Math.max(8,r.left+r.width/2-w/2),innerWidth-w-8)+"px";tipEl.style.top=(r.bottom+8+tipEl.offsetHeight>innerHeight?r.top-tipEl.offsetHeight-8:r.bottom+8)+"px";
 clearTimeout(tipT);tipT=setTimeout(()=>tipEl.classList.remove("show"),1800);
}
document.addEventListener("click",e=>{const m=e.target.closest("[data-label]");if(m)showTip(m,m.dataset.label);},true);
document.getElementById("theme-btn").addEventListener("click",e=>{
 const sel=document.getElementById("theme"),i=(sel.selectedIndex+1)%sel.options.length;
 sel.selectedIndex=i;sel.dispatchEvent(new Event("change"));showTip(e.currentTarget,"Theme: "+sel.options[i].textContent);
});
{const cd=document.getElementById("call-day");if(cd)cd.textContent=new Date().getDate();}
load();initCloud();initAlarms();initHeader();

// ---- Calendar quality layer: clash checks, CSV export and shared backup ----
(function(){
 const $=id=>document.getElementById(id);
 const say=(msg,kind)=>{if(typeof statusEl!=="undefined"&&statusEl){statusEl.textContent=msg;statusEl.className="status "+(kind||"");}};
 function exportCSV(){
  const rows=[["Date","Weekday","Start time","End time","Activity","Module title","Lecturer","Delivery mode"]];
  allEntries().forEach(x=>{const date=new Date(WEEK_START[0],WEEK_START[1],WEEK_START[2]+x.dayIndex),isoDate=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;rows.push([isoDate,days[x.dayIndex],x.startTime,x.endTime,x.label,x.sub,x.facilitator,x.data?.mode||"unspecified"]);});
  const csv=rows.map(row=>row.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(",")).join("\r\n");
  const blob=new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="MNH-Calendar-timetable.csv";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  say("CSV export prepared. It opens in Excel and other spreadsheet applications.","ok");
 }
 window.exportTimetableCSV=exportCSV;
 window.downloadTimetableExcel=async()=>{
  say("Preparing the editable Excel timetable…");
  try{
   const response=await fetch("/api/export/timetable.xlsx",{cache:"no-store"});
   if(!response.ok){
    const hint=response.status===404?" The server answering on this address does not have the Excel export — an older copy of the application may still be running on this port.":response.status===503?" Install the backend requirements (openpyxl) and restart.":"";
    throw new Error("Excel export failed (HTTP "+response.status+")."+hint);
   }
   const blob=await response.blob();
   const head=new Uint8Array(await blob.slice(0,2).arrayBuffer());
   if(head[0]!==0x50||head[1]!==0x4B)throw new Error("The server did not return a valid .xlsx workbook.");
   const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="MNH-Smart-Calendar-Editable-Timetable.xlsx";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
   say("Editable Excel timetable downloaded (Monday–Friday, independent copy).","ok");
  }catch(error){say(error&&error.message?error.message:"Excel export could not be created.","error");}
 };
 document.getElementById("weekly-export-xlsx")?.addEventListener("click",()=>window.downloadTimetableExcel());
 window.downloadSharedBackup=async()=>{
  if(!editingUnlocked){say("Unlock editing first to download the shared backup.","error");return;}
  say("Creating a consistent database backup…");
  try{const r=await fetch("/api/backup",{cache:"no-store"});if(!r.ok)throw Error("Backup export failed");
   const data=await r.json(),blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="MNH-Calendar-server-backup.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   say("A complete shared-data backup has been downloaded. Automatic daily server snapshots are also enabled.","ok");
  }catch(e){say("Backup could not be created. Check the server connection and try again.","error");}
 };
 // Validate and flag actual session intervals, including legacy and custom records.
 function checkClashes(){
  document.querySelectorAll("td.time-clash").forEach(el=>el.classList.remove("time-clash"));
  const byDay=Array.from({length:days.length},()=>[]);
  getSessionEntries().forEach(entry=>byDay[entry.dayIndex].push(entry));
  let conflicts=0;
  byDay.forEach(entries=>{
   entries.forEach((a,i)=>entries.slice(i+1).forEach(b=>{
    if(a.startMinutes<b.endMinutes&&b.startMinutes<a.endMinutes){
     conflicts++;
     [a,b].forEach(entry=>{
      const cell=Array.from(document.querySelectorAll("td[data-cell-key]")).find(td=>td.dataset.cellKey===`${entry.startTime}_${entry.dayIndex}`);
      if(cell)cell.classList.add("time-clash");
     });
    }
   }));
  });
  if(conflicts){say(`${conflicts} overlapping session pair(s) detected. Review the highlighted timetable entries.`,"error");}
  return conflicts;
 }
 const clashStyle=document.createElement("style");
 clashStyle.textContent='.time-clash{outline:2px solid #df6969!important;outline-offset:-2px;position:relative}.time-clash:after{content:"Time overlap";display:block;color:#ff9999;font-size:10px;font-weight:700}';
 document.head.appendChild(clashStyle);
 const body=$("calendar-body");
 if(body){new MutationObserver(()=>{checkClashes();}).observe(body,{childList:true,subtree:true});}
 checkClashes();
})();
