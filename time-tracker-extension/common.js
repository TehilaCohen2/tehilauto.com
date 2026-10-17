const pad = (n) => String(n).padStart(2, "0");
function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

// מבנה הנתונים:
// sessions: [{ project, sub?, start, end }]   projects: [שמות]   subs: { פרויקט: [תתי-פרויקטים] }
async function load() {
  const { running = null, sessions = [], projects = [], subs = {} } =
    await chrome.storage.local.get(["running", "sessions", "projects", "subs"]);
  const names = [...new Set([...projects, ...sessions.map((s) => s.project)])];
  const subMap = {};
  for (const n of names) {
    subMap[n] = [...new Set([...(subs[n] || []), ...sessions.filter((s) => s.project === n && s.sub).map((s) => s.sub)])];
  }
  return { running, sessions, names, subMap };
}

// sub === undefined: כל הזמן של הפרויקט (כולל תתי-פרויקטים). sub === "": רק זמן ללא תת-פרויקט
function totalFor(sessions, project, sub) {
  let t = 0;
  for (const s of sessions) {
    if (s.project !== project) continue;
    if (sub !== undefined && (s.sub || "") !== sub) continue;
    t += s.end - s.start;
  }
  return t;
}

async function addProject(name, sub) {
  const { names, subMap } = await load();
  const subs = {};
  for (const n of names) subs[n] = subMap[n];
  if (!subs[name]) subs[name] = [];
  if (sub && !subs[name].includes(sub)) subs[name].push(sub);
  await chrome.storage.local.set({ projects: [...new Set([...names, name])], subs });
}

const matches = (s, project, sub) => s.project === project && (sub === undefined || (s.sub || "") === sub);

// איפוס: מוחק את הזמן ומשאיר את השם
async function resetProject(name, sub) {
  const { sessions } = await load();
  await chrome.storage.local.set({ sessions: sessions.filter((s) => !matches(s, name, sub)) });
}

// מחיקה: מוחק את הפרויקט (או תת-הפרויקט) כולו
async function deleteProject(name, sub) {
  const { sessions, names, subMap } = await load();
  const rest = sessions.filter((s) => !matches(s, name, sub));
  const subs = {};
  for (const n of names) subs[n] = subMap[n];
  let projects = names;
  if (sub === undefined) { projects = names.filter((n) => n !== name); delete subs[name]; }
  else subs[name] = subs[name].filter((x) => x !== sub);
  await chrome.storage.local.set({ sessions: rest, projects, subs });
}

function el(tag, props) { return Object.assign(document.createElement(tag), props); }

function projectRow(name, sub, ms, onChange) {
  const isSub = sub !== undefined;
  const li = el("li", { className: isSub ? "sub" : "" });
  const label = isSub ? sub : name;
  const r = el("button", { className: "del", textContent: "↺", title: "איפוס זמן" });
  const d = el("button", { className: "del", textContent: "✕", title: "מחיקה" });
  r.onclick = async () => {
    const what = isSub ? `תת-הפרויקט "${sub}"` : `הפרויקט "${name}"`;
    if (!confirm(`לאפס את הזמן של ${what}? השם יישאר.`)) return;
    await resetProject(name, sub); onChange();
  };
  d.onclick = async () => {
    const msg = isSub
      ? `האם הנך בטוח למחוק את שעות תת-הפרויקט "${sub}"? תת-הפרויקט וכל הזמן שנשמר לו יימחקו.`
      : `האם הנך בטוח למחוק את שעות הפרויקט "${name}"? הפרויקט, תתי-הפרויקטים וכל הזמן שנשמר יימחקו.`;
    if (!confirm(msg)) return;
    await deleteProject(name, sub); onChange();
  };
  li.append(el("span", { className: "name", textContent: (isSub ? "↳ " : "") + label }),
            el("span", { className: "time", textContent: fmt(ms) }), r, d);
  return li;
}

// מצייר את כל הפרויקטים ותתי-הפרויקטים
function renderProjects(ul, state, onChange) {
  const { sessions, names, subMap } = state;
  const sorted = [...names].sort((a, b) => totalFor(sessions, b) - totalFor(sessions, a));
  const rows = [];
  for (const n of sorted) {
    rows.push(projectRow(n, undefined, totalFor(sessions, n), onChange));
    const subs = [...subMap[n]].sort((a, b) => totalFor(sessions, n, b) - totalFor(sessions, n, a));
    const direct = totalFor(sessions, n, "");
    if (subs.length && direct > 0) {
      const li = el("li", { className: "sub muted" });
      li.append(el("span", { className: "name", textContent: "↳ ללא תת-פרויקט" }), el("span", { className: "time", textContent: fmt(direct) }));
      rows.push(li);
    }
    for (const s of subs) rows.push(projectRow(n, s, totalFor(sessions, n, s), onChange));
  }
  ul.replaceChildren(...rows);
}

// ממלא את רשימות ההשלמה האוטומטית
function fillLists(state) {
  const p = document.getElementById("projects");
  if (p) p.replaceChildren(...state.names.map((n) => el("option", { value: n })));
}
function bindSubList(input, datalist, getState) {
  input._subUpdate = () => {
    const subs = getState().subMap[input.value.trim()] || [];
    datalist.replaceChildren(...subs.map((s) => el("option", { value: s })));
  };
  if (!input._subBound) { input._subBound = true; input.addEventListener("input", () => input._subUpdate()); }
  input._subUpdate();
}

// טופס הוספת שעות ידנית (משותף לחלונית ולעמוד הפרויקטים)
function bindManual(getState, onDone) {
  const $ = (id) => document.getElementById(id);
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  $("m-date").value = today();
  $("m-add").onclick = async () => {
    const project = $("m-project").value.trim();
    const sub = $("m-sub").value.trim();
    const mins = (parseInt($("m-hours").value, 10) || 0) * 60 + (parseInt($("m-min").value, 10) || 0);
    const msg = $("m-msg");
    if (!project) { msg.textContent = "יש לכתוב שם פרויקט"; return; }
    if (mins <= 0) { msg.textContent = "יש להזין שעות או דקות"; return; }
    const date = $("m-date").value || today();
    const end = date === today() ? Date.now() : new Date(`${date}T12:00:00`).getTime();
    await addProject(project, sub);
    const { sessions } = await load();
    const entry = { project, start: end - mins * 60000, end };
    if (sub) entry.sub = sub;
    sessions.push(entry);
    await chrome.storage.local.set({ sessions });
    $("m-hours").value = ""; $("m-min").value = "";
    msg.textContent = `נוספו ${Math.floor(mins / 60)} שעות ו-${mins % 60} דקות ל"${project}${sub ? " › " + sub : ""}" ✓`;
    onDone();
  };
  bindSubList($("m-project"), $("subs-manual"), getState);
}

function exportCsv(sessions) {
  const q = (v) => `"${String(v).replace(/"/g, '""')}"`;
  const rows = ["project,subproject,start,end,minutes"];
  for (const s of sessions) {
    rows.push([q(s.project), q(s.sub || ""), new Date(s.start).toISOString(),
      new Date(s.end).toISOString(), ((s.end - s.start) / 60000).toFixed(1)].join(","));
  }
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: "time-tracking.csv" });
  a.click();
  URL.revokeObjectURL(a.href);
}
