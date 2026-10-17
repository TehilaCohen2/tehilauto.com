const $ = (id) => document.getElementById(id);
let state = { sessions: [], names: [], subMap: {} };

async function render() {
  state = await load();
  const { running, sessions, names } = state;
  $("grand").textContent = fmt(sessions.reduce((a, s) => a + (s.end - s.start), 0));
  $("running").hidden = !running;
  if (running) $("running").textContent = `● טיימר פעיל כרגע: ${running.project}${running.sub ? " › " + running.sub : ""}`;
  $("empty").hidden = names.length > 0;
  fillLists(state);
  renderProjects($("totals"), state, render);
}

$("export").onclick = async () => exportCsv((await load()).sessions);
chrome.storage.onChanged.addListener(render);
bindManual(() => state, render);
render();
