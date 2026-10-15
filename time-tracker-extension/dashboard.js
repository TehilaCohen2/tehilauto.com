const $ = (id) => document.getElementById(id);

async function render() {
  const { running, sessions, names } = await load();
  const totals = totalsOf(sessions);
  const sorted = [...names].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));
  $("grand").textContent = fmt(Object.values(totals).reduce((a, b) => a + b, 0));
  $("running").hidden = !running;
  if (running) $("running").textContent = `● טיימר פעיל כרגע: ${running.project}`;
  $("empty").hidden = sorted.length > 0;
  $("totals").replaceChildren(...sorted.map((n) => projectRow(n, totals[n] || 0, render)));
}

$("export").onclick = async () => exportCsv((await load()).sessions);
chrome.storage.onChanged.addListener(render);
render();
