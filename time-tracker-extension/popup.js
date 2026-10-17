const $ = (id) => document.getElementById(id);
let tick = null;
let state = { sessions: [], names: [], subMap: {} };

async function render() {
  state = await load();
  const { running } = state;

  $("idle").hidden = !!running;
  $("active").hidden = !running;
  clearInterval(tick);
  if (running) {
    $("current").textContent = running.project;
    $("current-sub").textContent = running.sub ? `↳ ${running.sub}` : "";
    const update = () => ($("clock").textContent = fmt(Date.now() - running.start));
    update();
    tick = setInterval(update, 1000);
  }

  fillLists(state);
  bindSubList($("project"), $("subs-start"), () => state);
  $("empty").hidden = state.names.length > 0;
  renderProjects($("totals"), state, render);
}

$("start").onclick = async () => {
  const project = $("project").value.trim();
  const sub = $("sub").value.trim();
  if (!project) { $("project").focus(); return; }
  await addProject(project, sub);
  const running = { project, start: Date.now() };
  if (sub) running.sub = sub;
  await chrome.storage.local.set({ running });
  $("project").value = ""; $("sub").value = "";
  render();
};
for (const id of ["project", "sub"]) $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") $("start").click(); });

$("stop").onclick = async () => {
  const { running, sessions } = await load();
  if (!running) return;
  const entry = { project: running.project, start: running.start, end: Date.now() };
  if (running.sub) entry.sub = running.sub;
  sessions.push(entry);
  await chrome.storage.local.set({ sessions });
  await chrome.storage.local.remove("running");
  render();
};

$("open").onclick = () => chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
$("export").onclick = async () => exportCsv((await load()).sessions);

bindManual(() => state, render);
render();
