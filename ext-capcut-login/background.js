// =========================================================================
// CapCut Auto Login - Background Service Worker
// =========================================================================

const DEFAULT_SETTINGS = {
  autoLoginOnLoad: true,
  autoNextOnSuccess: true,
  autoDismissPopups: true,
  toolApiUrl: "http://127.0.0.1:5050/api/capcut/accounts"
};

chrome.runtime.onInstalled.addListener(async () => {
  const data = await chrome.storage.local.get(["settings", "accounts", "currentIndex"]);
  if (!data.settings) {
    await chrome.storage.local.set({ settings: DEFAULT_SETTINGS });
  }
  if (!data.accounts) {
    await chrome.storage.local.set({ accounts: [] });
  }
  if (data.currentIndex === undefined) {
    await chrome.storage.local.set({ currentIndex: 0 });
  }
  updateBadge(data.accounts || [], data.currentIndex || 0);
});

async function updateBadge(accounts, currentIndex) {
  if (!accounts || accounts.length === 0) {
    chrome.action.setBadgeText({ text: "" });
    return;
  }
  const remaining = accounts.filter(a => !a.used).length;
  chrome.action.setBadgeText({ text: String(remaining) });
  chrome.action.setBadgeBackgroundColor({ color: remaining > 0 ? "#00F0FE" : "#6c757d" });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "OPEN_CAPCUT_LOGIN") {
    (async () => {
      try {
        const url = "https://www.capcut.com/vi-vn/login";
        // Check if there is already a CapCut tab
        const tabs = await chrome.tabs.query({ url: "*://*.capcut.com/*" });
        if (tabs && tabs.length > 0) {
          const tab = tabs[0];
          await chrome.tabs.update(tab.id, { url, active: true });
          if (tab.windowId) {
            await chrome.windows.update(tab.windowId, { focused: true });
          }
          sendResponse({ success: true, tabId: tab.id });
        } else {
          const tab = await chrome.tabs.create({ url, active: true });
          sendResponse({ success: true, tabId: tab.id });
        }
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true; // async
  }

  if (message.type === "FETCH_FROM_TOOL") {
    (async () => {
      try {
        const apiUrl = message.url || "http://127.0.0.1:5050/api/capcut/accounts";
        const resp = await fetch(apiUrl, { cache: "no-store" });
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        const json = await resp.json();
        const rawAccounts = json.accounts || [];
        sendResponse({ success: true, accounts: rawAccounts });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true; // async
  }

  if (message.type === "UPDATE_BADGE") {
    (async () => {
      const { accounts = [], currentIndex = 0 } = await chrome.storage.local.get(["accounts", "currentIndex"]);
      updateBadge(accounts, currentIndex);
      sendResponse({ success: true });
    })();
    return true;
  }
});

