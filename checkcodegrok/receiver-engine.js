// =========================================================================
// Grok Link Receiver Engine (Integrated into Unified Extension)
// =========================================================================

globalThis.CodeReceiver = (() => {
  const defaults = { enabled: true, autoBind: true, autoClickTrial: true, enabledAt: 0, boundTabId: null, boundUrl: "", delayMs: 3000 };
  function isGrokPage(raw) {
    if (!raw) return false;
    return raw.includes("grok.com") || raw.includes("x.ai");
  }
  function referralUrl(code) {
    if (typeof code !== "string" || !/^[A-Za-z0-9_-]{6,128}$/.test(code)) throw new Error("Mã nhận không hợp lệ.");
    return `https://grok.com/refer/bot?code=${encodeURIComponent(code)}`;
  }
  function validateSettings(raw) {
    return {
      enabled: raw.enabled !== false,
      autoBind: raw.autoBind !== false,
      autoClickTrial: raw.autoClickTrial !== false,
      enabledAt: Number(raw.enabledAt) || 0,
      boundTabId: raw.boundTabId || null,
      boundUrl: String(raw.boundUrl || ""),
      delayMs: Math.min(30000, Math.max(1000, Number(raw.delayMs) || 3000))
    };
  }
  return { defaults, isGrokPage, referralUrl, validateSettings };
})();

globalThis.ReceiverEngine = (() => {
  const QUEUE_ALARM = "grok-receiver-queue";
  const CONNECTION_ALARM = "grok-relay-reconnect";
  const MAX_AGE_MS = 600000;
  let tasks = Promise.resolve();
  let draining = false;
  let relaySocket = null;
  let reconnectTimer = null;
  let inbound = Promise.resolve();
  let lastHeartbeat = 0;
  let relayClientId = "";

  function exclusive(work) {
    const next = tasks.then(work);
    tasks = next.catch(() => {});
    return next;
  }

  async function getSettings() {
    const { settings } = await chrome.storage.local.get("settings");
    return { ...CodeReceiver.defaults, ...settings };
  }

  function cancelPending(log) {
    for (const entry of log) {
      if (entry.status === "queued") {
        Object.assign(entry, { status: "cancelled", error: "Đã dừng hoặc đổi cấu hình." });
      }
    }
  }

  async function saveLog(log) {
    await chrome.storage.local.set({ deliveryLog: log.slice(0, 100) });
  }

  async function checkTab(tabId) {
    if (!Number.isInteger(tabId)) throw new Error("Chưa chọn tab Grok.");
    const tab = await chrome.tabs.get(tabId);
    if (!tab) throw new Error("Tab Grok đã đóng.");
    return tab;
  }

  async function ensureBoundTab(settings) {
    if (Number.isInteger(settings.boundTabId)) {
      try {
        const tab = await checkTab(settings.boundTabId);
        if (tab && tab.id) return tab;
      } catch {}
    }
    const allTabs = await chrome.tabs.query({});
    let tab = allTabs.find(t => t.url && (t.url.includes("grok.com") || t.url.includes("x.ai")) && t.active);
    if (!tab) {
      tab = allTabs.find(t => t.url && (t.url.includes("grok.com") || t.url.includes("x.ai")));
    }
    if (!tab) {
      tab = allTabs.find(t => t.active);
    }
    if (!tab) {
      tab = await chrome.tabs.create({ url: "https://grok.com/", active: true });
    }
    settings.boundTabId = tab.id;
    settings.boundUrl = tab.url || "https://grok.com/";
    try {
      await chrome.storage.local.set({ settings });
    } catch {}
    return tab;
  }

  function sendRelayReport(message, status, error = "") {
    if (relaySocket?.readyState === WebSocket.OPEN) {
      relaySocket.send(JSON.stringify({
        type: "result",
        epoch: message.relayEpoch || message.epoch,
        sequence: message.relaySequence || message.sequence,
        status,
        error
      }));
    }
  }

  async function probeReadiness(probeId, socket) {
    const settings = await exclusive(getSettings);
    let ready = settings.enabled, note = "Sẵn sàng mở link Grok.";
    if (relaySocket === socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "probe_result", probeId, ready, note }));
    }
  }

  async function acceptRelayCode(message) {
    return exclusive(async () => {
      const settings = await getSettings();
      if (!settings.enabled) return { success: false, skipped: true };
      if (message.type !== "code") return { success: false, skipped: true };
      const code = typeof message.code === "string" ? message.code.trim() : "";
      if (!code || !/^[A-Za-z0-9_-]{6,128}$/.test(code)) {
        return { success: false, skipped: true };
      }
      const url = CodeReceiver.referralUrl(code);

      const { deliveryLog = [], relayCursor = {} } = await chrome.storage.local.get(["deliveryLog", "relayCursor"]);

      // Tránh mở trùng lặp mã nếu vừa mở trong 10 giây qua
      const recentSame = deliveryLog.find(item => item.code === code && (Date.now() - (item.receivedAt || item.timestamp || 0) < 10000));
      if (recentSame && message.retry !== true && message.force !== true) {
        return { success: true, duplicate: true };
      }

      const cursor = { epoch: message.epoch, sequence: message.sequence };

      try {
        const targetTab = await ensureBoundTab(settings);
        await chrome.tabs.update(targetTab.id, { url, active: true });
        if (targetTab.windowId) {
          try { await chrome.windows.update(targetTab.windowId, { focused: true }); } catch {}
        }
        const entry = {
          id: crypto.randomUUID(),
          code,
          url,
          timestamp: message.timestamp || Date.now(),
          receivedAt: Date.now(),
          finishedAt: Date.now(),
          status: "opened",
          relayEpoch: message.epoch,
          relaySequence: message.sequence,
          source: "relay"
        };
        deliveryLog.unshift(entry);
        await chrome.storage.local.set({ deliveryLog: deliveryLog.slice(0, 100), relayCursor: cursor });
        sendRelayReport(entry, "opened");
        return { success: true, accepted: true, status: "opened", url };
      } catch (err) {
        const entry = {
          id: crypto.randomUUID(),
          code,
          url,
          timestamp: message.timestamp || Date.now(),
          receivedAt: Date.now(),
          finishedAt: Date.now(),
          status: "failed",
          error: err.message,
          relayEpoch: message.epoch,
          relaySequence: message.sequence,
          source: "relay"
        };
        deliveryLog.unshift(entry);
        await chrome.storage.local.set({ deliveryLog: deliveryLog.slice(0, 100), relayCursor: cursor });
        sendRelayReport(entry, "failed", err.message);
        return { success: false, error: err.message };
      }
    });
  }

  // Local loopback delivery: when Hunter in the SAME profile finds a code, open directly!
  async function localDeliver(code) {
    return exclusive(async () => {
      const settings = await getSettings();
      if (!settings.enabled) return { success: false, skipped: true };
      const validCode = typeof code === "string" ? code.trim() : "";
      if (!/^[A-Za-z0-9_-]{6,128}$/.test(validCode)) return { success: false, skipped: true };
      const url = CodeReceiver.referralUrl(validCode);

      const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
      const recentSame = deliveryLog.find(item => item.code === validCode && (Date.now() - (item.receivedAt || item.timestamp || 0) < 10000));
      if (recentSame) {
        return { success: true, duplicate: true };
      }

      try {
        const targetTab = await ensureBoundTab(settings);
        await chrome.tabs.update(targetTab.id, { url, active: true });
        if (targetTab.windowId) {
          try { await chrome.windows.update(targetTab.windowId, { focused: true }); } catch {}
        }
        const entry = {
          id: crypto.randomUUID(),
          code: validCode,
          url,
          timestamp: Date.now(),
          receivedAt: Date.now(),
          finishedAt: Date.now(),
          status: "opened",
          source: "flask_sync"
        };
        deliveryLog.unshift(entry);
        await chrome.storage.local.set({ deliveryLog: deliveryLog.slice(0, 100) });
        return { success: true, accepted: true, status: "opened", url };
      } catch (err) {
        return { success: false, error: err.message };
      }
    });
  }

  // Force open code on demand (bypasses duplicate check and opens tab immediately)
  async function forceOpenCode(code) {
    return exclusive(async () => {
      const settings = await getSettings();
      const validCode = typeof code === "string" ? code.trim() : "";
      if (!/^[A-Za-z0-9_-]{6,128}$/.test(validCode)) return { success: false, error: "Mã không hợp lệ." };
      const url = CodeReceiver.referralUrl(validCode);
      try {
        const targetTab = await ensureBoundTab(settings);
        await chrome.tabs.update(targetTab.id, { url, active: true });
        if (targetTab.windowId) {
          try { await chrome.windows.update(targetTab.windowId, { focused: true }); } catch {}
        }
        const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
        const entry = {
          id: crypto.randomUUID(),
          code: validCode,
          url,
          timestamp: Date.now(),
          receivedAt: Date.now(),
          finishedAt: Date.now(),
          status: "opened",
          source: "manual_sync"
        };
        deliveryLog.unshift(entry);
        await chrome.storage.local.set({ deliveryLog: deliveryLog.slice(0, 100) });
        return { success: true, status: "opened", url };
      } catch (err) {
        return { success: false, error: err.message };
      }
    });
  }

  async function finishJob(id, result) {
    await exclusive(async () => {
      const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
      const entry = deliveryLog.find(item => item.id === id);
      if (entry) Object.assign(entry, result, { finishedAt: Date.now() });
      await saveLog(deliveryLog);
      if (entry && entry.relayEpoch) sendRelayReport(entry, result.status, result.error);
    });
  }

  async function waitBeforeNext(settings) {
    const started = Date.now();
    while (Date.now() - started < Math.max(15000, settings.delayMs)) {
      const current = await getSettings();
      if (!current.enabled || current.boundTabId !== settings.boundTabId) return;
      let tab;
      try { tab = await checkTab(settings.boundTabId); } catch { return; }
      if (tab.status === "complete" && Date.now() - started >= settings.delayMs) return;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }

  async function drainQueue() {
    if (draining) return;
    draining = true;
    try {
      while (true) {
        const job = await exclusive(async () => {
          const settings = await getSettings();
          if (!settings.enabled) return null;
          const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
          const entry = [...deliveryLog].reverse().find(item => item.status === "queued");
          if (!entry) { await chrome.alarms.clear(QUEUE_ALARM); return null; }
          if (Date.now() - entry.timestamp > MAX_AGE_MS) {
            Object.assign(entry, { status: "failed", error: "Mã đã chờ quá 2 phút." });
            await saveLog(deliveryLog);
            return { expired: true };
          }
          try {
            const targetTab = await ensureBoundTab(settings);
            entry.status = "processing";
            await saveLog(deliveryLog);
            const url = CodeReceiver.referralUrl(entry.code);
            await chrome.tabs.update(targetTab.id, { url, active: true });
            return { entry, settings, result: { success: true, status: "opened", url } };
          } catch (error) {
            return { entry, settings, result: { success: false, status: "failed", error: error.message } };
          }
        });
        if (!job) break;
        if (job.expired) continue;
        await finishJob(job.entry.id, job.result);
        await waitBeforeNext(job.settings);
      }
    } finally { draining = false; }
  }

  async function connectionStatus(connected, error = "") {
    await chrome.storage.local.set({ relayConnection: { connected, error, clientId: relayClientId, timestamp: Date.now() } });
  }

  function disconnectRelay() {
    clearTimeout(reconnectTimer);
    const previous = relaySocket;
    relaySocket = null;
    if (previous) previous.close();
  }

  function reconnectSoon() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => { void connectRelay().catch(console.error); }, 2000);
  }

  async function connectRelay() {
    const settings = await getSettings();
    if (!settings.enabled) {
      disconnectRelay();
      await chrome.alarms.clear(CONNECTION_ALARM);
      await connectionStatus(false, "Đang tắt nhận mã.");
      return;
    }
    await chrome.alarms.create(CONNECTION_ALARM, { periodInMinutes: 0.5 });
    if (relaySocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(relaySocket.readyState)) return;
    let socket;
    try { socket = new WebSocket(GROK_RELAY_CONFIG.wsUrl); }
    catch (error) { await connectionStatus(false, error.message); reconnectSoon(); return; }
    relaySocket = socket;
    lastHeartbeat = Date.now();
    socket.onopen = () => {
      void (async () => {
        const current = await getSettings();
        if (relaySocket !== socket || !current.enabled) return;
        const { relayCursor = {} } = await chrome.storage.local.get("relayCursor");
        socket.send(JSON.stringify({
          type: "subscribe",
          token: GROK_RELAY_CONFIG.token,
          epoch: relayCursor.epoch || "",
          after: relayCursor.sequence || 0,
          since: current.enabledAt
        }));
      })().catch(error => { console.warn(error); socket.close(); });
    };
    socket.onmessage = event => {
      inbound = inbound.then(async () => {
        if (relaySocket !== socket) return;
        lastHeartbeat = Date.now();
        const message = JSON.parse(event.data);
        if (message.type === "hello") { relayClientId = message.clientId || ""; await connectionStatus(true); }
        else if (message.type === "heartbeat") socket.send(JSON.stringify({ type: "ping" }));
        else if (message.type === "probe") await probeReadiness(message.probeId, socket);
        else if (message.type === "code") {
          await acceptRelayCode(message);
        }
      }).catch(error => { console.warn("[GrokReceiver]", error.message); });
    };
    socket.onerror = () => {};
    socket.onclose = () => {
      if (relaySocket !== socket) return;
      relaySocket = null;
      void connectionStatus(false, "Mất kết nối relay. Chạy ./start-relay.command trên Mac hoặc START-RELAY.cmd trên Windows.");
      reconnectSoon();
    };
  }

  async function init() {
    return exclusive(async () => {
      const settings = await getSettings();
      const { runStarted } = await chrome.storage.session.get("runStarted");
      const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
      for (const entry of deliveryLog) {
        if (entry.status === "processing") {
          Object.assign(entry, { status: "failed", error: "Phiên xử lý bị ngắt; không tự mở lại." });
        }
      }
      if (!runStarted) {
        settings.enabledAt = Date.now();
        cancelPending(deliveryLog);
        await chrome.storage.local.set({ relayCursor: {} });
        await chrome.storage.session.set({ runStarted: true });
      }
      await chrome.storage.local.set({ settings });
      await saveLog(deliveryLog);
    }).then(async () => {
      await connectRelay();
      await drainQueue();
    }).catch(console.error);
  }

  function handleMessage(req, sender, sendResponse) {
    const action = req?.action;
    if (!["SAVE_SETTINGS", "BIND_TAB", "STOP", "RECONNECT", "GET_RECEIVER_SETTINGS"].includes(action)) return false;

    exclusive(async () => {
      const previous = await getSettings();
      if (action === "GET_RECEIVER_SETTINGS") {
        return { success: true, settings: previous };
      }
      if (action === "RECONNECT") {
        return { success: true, settings: previous };
      }
      const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
      let settings;
      if (action === "BIND_TAB") {
        const tab = await checkTab(req.tabId);
        settings = { ...previous, boundTabId: tab.id, boundUrl: tab.url };
        await chrome.storage.session.set({ boundTabId: tab.id });
      } else if (action === "STOP") {
        settings = { ...previous, enabled: false };
      } else {
        settings = CodeReceiver.validateSettings({
          ...req.settings,
          boundTabId: previous.boundTabId,
          boundUrl: previous.boundUrl,
          enabledAt: previous.enabledAt
        });
        if (settings.enabled) await ensureBoundTab(settings);
      }
      if (!previous.enabled && settings.enabled) settings.enabledAt = Date.now();
      cancelPending(deliveryLog);
      await chrome.storage.local.set({ settings });
      await saveLog(deliveryLog);
      await chrome.alarms.clear(QUEUE_ALARM);
      return { success: true, settings };
    }).then(async result => {
      disconnectRelay();
      await connectRelay();
      sendResponse(result);
    }, error => {
      sendResponse({ success: false, error: error.message });
    });
    return true;
  }

  function handleAlarm(alarm) {
    if (alarm.name === QUEUE_ALARM) void drainQueue().catch(console.error);
    if (alarm.name === CONNECTION_ALARM) {
      if (relaySocket && Date.now() - lastHeartbeat > 45000) disconnectRelay();
      void connectRelay().catch(console.error);
    }
  }

  function handleTabRemoved(tabId) {
    void exclusive(async () => {
      const settings = await getSettings();
      if (settings.boundTabId !== tabId) return;
      await chrome.storage.session.remove("boundTabId");
      settings.boundTabId = null;
      settings.boundUrl = "";
      if (!settings.autoBind) settings.enabled = false;
      const { deliveryLog = [] } = await chrome.storage.local.get("deliveryLog");
      cancelPending(deliveryLog);
      await chrome.storage.local.set({ settings });
      await saveLog(deliveryLog);
    }).then(() => connectRelay()).catch(console.error);
  }

  return {
    getSettings,
    connectRelay,
    disconnectRelay,
    drainQueue,
    localDeliver,
    forceOpenCode,
    init,
    handleMessage,
    handleAlarm,
    handleTabRemoved
  };
})();

