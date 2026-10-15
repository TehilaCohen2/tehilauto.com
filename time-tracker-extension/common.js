const pad = (n) => String(n).padStart(2, "0");
function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

async function load() {
  const { running = null, sessions = [], projects = [] } = await chrome.storage.local.get(["running", "sessions", "projects"]);
  const names = [...new Set([...projects, ...sessions.map((s) => s.project)])];
  return { running, sessions, names };
}

function totalsOf(sessions) {
  const map = {};
  for (const s of sessions) map[s.project] = (map[s.project] || 0) + (s.end - s.start);
  return map;
}

async function addProject(name) {
  const { names } = await load();
  if (!names.includes(name)) await chrome.storage.local.set({ projects: [...names, name] });
}

// איפוס: מוחק את הזמן אבל משאיר את שם הפרויקט
async function resetProject(name) {
  const { sessions } = await load();
  await chrome.storage.local.set({ sessions: sessions.filter((s) => s.project !== name) });
}

// מחיקה: מוחק את הפרויקט כולו
async function deleteProject(name) {
  const { sessions, names } = await load();
  await chrome.storage.local.set({
    sessions: sessions.filter((s) => s.project !== name),
    projects: names.filter((n) => n !== name),
  });
}

// בונה שורת פרויקט עם כפתורי איפוס ומחיקה
function projectRow(name, ms, onChange) {
  const li = document.createElement("li");
  const n = Object.assign(document.createElement("span"), { className: "name", textContent: name });
  const t = Object.assign(document.createElement("span"), { className: "time", textContent: fmt(ms) });
  const r = Object.assign(document.createElement("button"), { className: "del", textContent: "↺", title: "איפוס זמן הפרויקט" });
  const d = Object.assign(document.createElement("button"), { className: "del", textContent: "✕", title: "מחיקת הפרויקט" });
  r.onclick = async () => {
    if (!confirm(`לאפס את הזמן של "${name}"? שם הפרויקט יישאר.`)) return;
    await resetProject(name); onChange();
  };
  d.onclick = async () => {
    if (!confirm(`האם הנך בטוח למחוק את שעות הפרויקט "${name}"? הפרויקט וכל הזמן שנשמר לו יימחקו.`)) return;
    await deleteProject(name); onChange();
  };
  li.append(n, t, r, d);
  return li;
}

function exportCsv(sessions) {
  const rows = ["project,start,end,minutes"];
  for (const s of sessions) {
    rows.push([`"${s.project.replace(/"/g, '""')}"`, new Date(s.start).toISOString(),
      new Date(s.end).toISOString(), ((s.end - s.start) / 60000).toFixed(1)].join(","));
  }
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "time-tracking.csv" });
  a.click();
  URL.revokeObjectURL(a.href);
}
