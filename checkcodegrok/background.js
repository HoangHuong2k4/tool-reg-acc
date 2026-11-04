// =========================================================================
// Grok Auto Link Opener (Receiver Pro) - Background Service Worker
// Tự động nhận link Grok từ Tool Python ngầm và chuyển hướng tab Grok
// Không cần đăng nhập X.com
// =========================================================================

importScripts("relay-config.js", "receiver-engine.js");

const FLASK_POLL_ALARM = "grok-flask-poll";
let lastPolledCode = "";

chrome.storage.local.get("lastPolledCode").then(res => {
  if (res.lastPolledCode) lastPolledCode = res.lastPolledCode;
});

// Cập nhật biểu tượng trạng thái
async function updateBadge(enabled) {
  try {
    await chrome.action.setBadgeText({ text: enabled ? "ON" : "OFF" });
    await chrome.action.setBadgeBackgroundColor({ color: enabled ? "#10b981" : "#64748b" });
  } catch {}
}

// Khởi chạy khi cài đặt extension
chrome.runtime.onInstalled.addListener(async () => {
  const { settings } = await chrome.storage.local.get("settings");
  if (!settings) {
    await chrome.storage.local.set({
      settings: {
        enabled: true, // Mặc định BẬT sẵn để người dùng mở là chạy luôn
        autoBind: true,
        autoClickTrial: true,
        enabledAt: Date.now(),
        boundTabId: null,
        boundUrl: "",
        delayMs: 5000
      }
    });
  }
  const current = await ReceiverEngine.getSettings();
  await updateBadge(current.enabled);
  void ReceiverEngine.init().catch(console.error);
  await startFlaskPolling();
});

// Khởi chạy khi mở trình duyệt
chrome.runtime.onStartup.addListener(async () => {
  const current = await ReceiverEngine.getSettings();
  await updateBadge(current.enabled);
  void ReceiverEngine.init().catch(console.error);
  await startFlaskPolling();
});

// Lắng nghe thay đổi cài đặt
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.settings) {
    const isEnabled = changes.settings.newValue?.enabled === true;
    updateBadge(isEnabled);
    if (isEnabled) {
      startFlaskPolling();
    }
  }
});

// ── Fallback Poller từ Flask Web Server (http://127.0.0.1:5050) ────────
async function startFlaskPolling() {
  await chrome.alarms.create(FLASK_POLL_ALARM, { periodInMinutes: 0.1 }); // ~6s alarm
  pollFlaskOnce();
}

async function pollFlaskOnce() {
  const settings = await ReceiverEngine.getSettings();
  if (!settings.enabled) return;

  try {
    const res = await fetch("http://127.0.0.1:5050/api/grok/live_latest_code", {
      signal: AbortSignal.timeout(2000)
    });
    if (res.ok) {
      const data = await res.json();
      await chrome.storage.local.set({ toolSync: data });

      const code = data?.latest?.code;
      if (code && code !== lastPolledCode) {
        lastPolledCode = code;
        await chrome.storage.local.set({ lastPolledCode: code });
        await ReceiverEngine.localDeliver(code);
      }
    }
  } catch {}
}

// Lặp poll Flask nhanh (mỗi 2.5s khi worker còn sống)
setInterval(() => {
  void pollFlaskOnce().catch(() => {});
}, 2500);

// Lắng nghe alarms
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === FLASK_POLL_ALARM) {
    void pollFlaskOnce().catch(() => {});
  }
  ReceiverEngine.handleAlarm(alarm);
});

// Lắng nghe đóng tab
chrome.tabs.onRemoved.addListener(tabId => {
  ReceiverEngine.handleTabRemoved(tabId);
});

// Lắng nghe message từ Popup
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req?.action === "FORCE_OPEN_CODE" || req?.action === "OPEN_CODE") {
    const code = req.code || "";
    ReceiverEngine.forceOpenCode(code).then(res => {
      sendResponse(res);
    });
    return true;
  }

  if (req?.action === "SIMULATE_CODE") {
    const code = req.code || "DEMO999XYZ";
    ReceiverEngine.localDeliver(code).then(res => {
      sendResponse(res);
    });
    return true;
  }

  return ReceiverEngine.handleMessage(req, sender, sendResponse);
});

// Khởi tạo ban đầu
void ReceiverEngine.init().catch(console.error);
