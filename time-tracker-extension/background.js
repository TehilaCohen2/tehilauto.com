// מציג סימון על האייקון כשהטיימר רץ
function updateBadge(running) {
  chrome.action.setBadgeText({ text: running ? "●" : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#e5484d" });
}

async function sync() {
  const { running } = await chrome.storage.local.get("running");
  updateBadge(!!running);
}

chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onInstalled.addListener(sync);
chrome.storage.onChanged.addListener((changes) => {
  if (changes.running) updateBadge(!!changes.running.newValue);
});
