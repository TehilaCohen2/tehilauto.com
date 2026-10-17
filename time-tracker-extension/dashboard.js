const $ = (id) => document.getElementById(id);
let state = { sessions: [], names: [], subMap: {}, view: [] };
let editingId = null;

const two = (n) => String(n).padStart(2, "0");
const toLocalInput = (ms) => { const d = new Date(ms); return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}T${two(d.getHours())}:${two(d.getMinutes())}`; };
const dateLabel = (ms) => { const d = new Date(ms); return `${two(d.getDate())}/${two(d.getMonth() + 1)}/${d.getFullYear()}`; };
const timeLabel = (ms) => { const d = new Date(ms); return `${two(d.getHours())}:${two(d.getMinutes())}`; };

function historyRow(s) {
  const box = el("div", { className: "hrow" });
  if (editingId === s.id) {
    const project = el("input", { type: "text", value: s.project, placeholder: "פרויקט" });
    const sub = el("input", { type: "text", value: s.sub || "", placeholder: "תת-פרויקט (לא חובה)" });
    const from = el("input", { type: "datetime-local", value: toLocalInput(s.start) });
    const to = el("input", { type: "datetime-local", value: toLocalInput(s.end) });
    const msg = el("div", { className: "msg err" });
    const save = el("button", { className: "primary", textContent: "שמירה" });
    const cancel = el("button", { className: "link", textContent: "ביטול" });
    save.onclick = async () => {
      // שדות הזמן מדויקים רק לדקה, לכן ערך שלא שונה נשמר כמו שהוא
      const st = from.value === toLocalInput(s.start) ? s.start : new Date(from.value).getTime();
      const en = to.value === toLocalInput(s.end) ? s.end : new Date(to.value).getTime();
      if (!project.value.trim()) { msg.textContent = "יש לכתוב שם פרויקט"; return; }
      if (!(st < en)) { msg.textContent = "שעת הסיום חייבת להיות אחרי שעת ההתחלה"; return; }
      await updateSession(s.id, { project: project.value.trim(), sub: sub.value.trim(), start: st, end: en });
      editingId = null; render();
    };
    cancel.onclick = () => { editingId = null; render(); };
    box.append(el("label", { textContent: "פרויקט" }), project, el("label", { textContent: "תת-פרויקט" }), sub,
      el("label", { textContent: "התחלה" }), from, el("label", { textContent: "סיום" }), to, msg, save, cancel);
    return box;
  }
  const info = el("div", { className: "hinfo" });
  info.append(el("div", { className: "hname", textContent: s.project + (s.sub ? " › " + s.sub : "") }),
    el("div", { className: "hmeta", textContent: `${dateLabel(s.start)} · ${timeLabel(s.start)}–${timeLabel(s.end)}` }));
  const edit = el("button", { className: "del", textContent: "✎", title: "עריכה" });
  const del = el("button", { className: "del", textContent: "✕", title: "מחיקת הרשומה" });
  edit.onclick = () => { editingId = s.id; render(); };
  del.onclick = async () => {
    if (!confirm("האם הנך בטוח למחוק את הרשומה הזו?")) return;
    await deleteSession(s.id); render();
  };
  box.classList.add("view");
  box.append(info, el("span", { className: "time", textContent: fmt(s.end - s.start) }), edit, del);
  return box;
}

async function render() {
  state = await load();
  const { running, sessions, names, view, period } = state;
  $("grand").textContent = fmt(view.reduce((a, s) => a + (s.end - s.start), 0));
  $("running").hidden = !running;
  if (running) $("running").textContent = `● טיימר פעיל כרגע: ${running.project}${running.sub ? " › " + running.sub : ""}`;
  $("empty").hidden = names.length > 0;
  fillLists(state);
  bindPeriod($("period"), () => state, render);
  renderProjects($("totals"), state, render);

  const from = periodFrom(period);
  const recent = sessions.filter((s) => s.end > from).sort((a, b) => b.end - a.end);
  const LIMIT = 100;
  $("history").replaceChildren(...recent.slice(0, LIMIT).map(historyRow));
  $("hist-note").hidden = recent.length > 0 && recent.length <= LIMIT;
  $("hist-note").textContent = recent.length === 0 ? "אין רשומות בתקופה הזו." : `מוצגות ${LIMIT} הרשומות האחרונות מתוך ${recent.length}.`;
}

$("export").onclick = async () => exportCsv((await load()).sessions);
chrome.storage.onChanged.addListener(() => { if (editingId === null) render(); });
bindManual(() => state, render);
render();
