// סימון על האייקון + תזכורת כשהטיימר רץ יותר מדי זמן
const REMIND_AFTER_MIN = 180; // 3 שעות
const REPEAT_EVERY_MIN = 60;  // ואז תזכורת חוזרת כל שעה
const ALARM = "forgotten-timer";

function updateBadge(running) {
  chrome.action.setBadgeText({ text: running ? "●" : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#e5484d" });
}

function scheduleReminder(running) {
  chrome.alarms.clear(ALARM);
  if (!running) return;
  const when = Math.max(running.start + REMIND_AFTER_MIN * 60000, Date.now() + 5000);
  chrome.alarms.create(ALARM, { when, periodInMinutes: REPEAT_EVERY_MIN });
}

async function sync() {
  const { running } = await chrome.storage.local.get("running");
  updateBadge(!!running);
  scheduleReminder(running);
}

chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onInstalled.addListener(sync);
chrome.storage.onChanged.addListener((changes) => {
  if (changes.running) {
    updateBadge(!!changes.running.newValue);
    scheduleReminder(changes.running.newValue);
  }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM) return;
  const { running } = await chrome.storage.local.get("running");
  if (!running) { chrome.alarms.clear(ALARM); return; }
  const hours = Math.floor((Date.now() - running.start) / 3600000);
  const name = running.project + (running.sub ? " › " + running.sub : "");
  chrome.notifications.create("forgotten-timer", {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: "הטיימר עדיין רץ ⏱",
    message: `הטיימר על "${name}" רץ כבר ${hours} שעות. עדיין עובדת? אם סיימת, לחצי על האייקון ו"סיום טיימר".`,
    priority: 2,
  });
});
