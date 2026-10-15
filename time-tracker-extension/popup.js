const $ = (id) => document.getElementById(id);
let tick = null;

async function render() {
  const { running, sessions, names } = await load();

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
  const sorted = [...names].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));
  $("projects").replaceChildren(...sorted.map((n) => Object.assign(document.createElement("option"), { value: n })));
  $("empty").hidden = sorted.length > 0;
  $("totals").replaceChildren(...sorted.map((n) => projectRow(n, totals[n] || 0, render)));
}

$("start").onclick = async () => {
  const project = $("project").value.trim();
  if (!project) { $("project").focus(); return; }
  await addProject(project);
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

$("open").onclick = () => chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
$("export").onclick = async () => exportCsv((await load()).sessions);

render();
