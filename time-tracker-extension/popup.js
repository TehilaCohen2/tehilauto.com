const $ = (id) => document.getElementById(id);
let tick = null;

const pad = (n) => String(n).padStart(2, "0");
function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}

async function load() {
  const { running = null, sessions = [] } = await chrome.storage.local.get(["running", "sessions"]);
  return { running, sessions };
}

function totalsOf(sessions) {
  const map = {};
  for (const s of sessions) map[s.project] = (map[s.project] || 0) + (s.end - s.start);
  return map;
}

async function render() {
  const { running, sessions } = await load();

  $("idle").hidden = !!running;
  $("active").hidden = !running;
  clearInterval(tick);
  if (running) {
    $("current").textContent = running.project;
    const update = () => ($("clock").textContent = fmt(Date.now() - running.start));
    update();
    tick = setInterval(update, 1000);
  }

  const totals = totalsOf(sessions);
  const names = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
  $("projects").replaceChildren(...names.map((n) => Object.assign(document.createElement("option"), { value: n })));
  $("empty").hidden = names.length > 0;
  $("export").hidden = names.length === 0;

  $("totals").replaceChildren(...names.map((name) => {
    const li = document.createElement("li");
    const n = Object.assign(document.createElement("span"), { className: "name", textContent: name });
    const t = Object.assign(document.createElement("span"), { className: "time", textContent: fmt(totals[name]) });
    const d = Object.assign(document.createElement("button"), { className: "del", textContent: "✕", title: "מחיקת הפרויקט" });
    d.onclick = async () => {
      if (!confirm(`למחוק את כל הזמן שנשמר ל"${name}"?`)) return;
      const cur = await load();
      await chrome.storage.local.set({ sessions: cur.sessions.filter((s) => s.project !== name) });
      render();
    };
    li.append(n, t, d);
    return li;
  }));
}

$("start").onclick = async () => {
  const project = $("project").value.trim();
  if (!project) { $("project").focus(); return; }
  await chrome.storage.local.set({ running: { project, start: Date.now() } });
  $("project").value = "";
  render();
};
$("project").addEventListener("keydown", (e) => { if (e.key === "Enter") $("start").click(); });

$("stop").onclick = async () => {
  const { running, sessions } = await load();
  if (!running) return;
  sessions.push({ project: running.project, start: running.start, end: Date.now() });
  await chrome.storage.local.set({ sessions });
  await chrome.storage.local.remove("running");
  render();
};

$("export").onclick = async () => {
  const { sessions } = await load();
  const rows = ["project,start,end,minutes"];
  for (const s of sessions) {
    rows.push([`"${s.project.replace(/"/g, '""')}"`, new Date(s.start).toISOString(),
      new Date(s.end).toISOString(), ((s.end - s.start) / 60000).toFixed(1)].join(","));
  }
  const blob = new Blob(["﻿" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "time-tracking.csv" });
  a.click();
  URL.revokeObjectURL(a.href);
};

render();
