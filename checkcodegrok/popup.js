// =========================================================================
// Grok Auto Opener Pro - Popup Controller (v3.0.0)
// Tự động nhận diện và đồng bộ real-time với Tool Python săn mã ngầm
// =========================================================================

document.addEventListener("DOMContentLoaded", async () => {
  // Elements: Settings & Tab Grok
  const enabled = document.getElementById("enabled");
  const boundTab = document.getElementById("bound-tab");
  const btnBindTab = document.getElementById("btn-bind-tab");
  const btnOpenGrok = document.getElementById("btn-open-grok");
  const autoBind = document.getElementById("auto-bind");
  const autoClickTrial = document.getElementById("auto-click-trial");
  const delay = document.getElementById("delay");
  const btnSave = document.getElementById("btn-save");
  const btnTestOpen = document.getElementById("btn-test-open");
  const btnStop = document.getElementById("btn-stop");
  const statusMsg = document.getElementById("status-msg");
  const historyContainer = document.getElementById("history-container");
  const pendingCount = document.getElementById("pending-count");

  // Elements: Đồng Bộ Tool Python
  const toolStatusBadge = document.getElementById("tool-status-badge");
  const syncPulseDot = document.getElementById("sync-pulse-dot");
  const syncLatestCode = document.getElementById("sync-latest-code");
  const syncCodeTime = document.getElementById("sync-code-time");
  const syncTotalCodes = document.getElementById("sync-total-codes");
  const syncReceivers = document.getElementById("sync-receivers");
  const btnSyncOpenLatest = document.getElementById("btn-sync-open-latest");
  const btnSyncRefresh = document.getElementById("btn-sync-refresh");

  let currentSettings = {
    enabled: true,
    autoBind: true,
    autoClickTrial: true,
    boundTabId: null,
    boundUrl: "",
    delayMs: 5000
  };

  let activeToolCode = "";

  function showMessage(text, isError = false) {
    statusMsg.textContent = text;
    statusMsg.style.color = isError ? "var(--danger)" : "var(--accent)";
    statusMsg.style.display = "block";
    setTimeout(() => { statusMsg.style.display = "none"; }, 3500);
  }

  function renderSettings(settings, syncInputs = false) {
    currentSettings = { ...currentSettings, ...settings };
    enabled.checked = currentSettings.enabled === true;

    if (Number.isInteger(currentSettings.boundTabId)) {
      boundTab.innerHTML = `📌 <b>Đã ghim tab #${currentSettings.boundTabId}</b><br><span style="font-size:10px;color:var(--text-muted);">${escapeHtml(currentSettings.boundUrl || "")}</span>`;
    } else {
      boundTab.textContent = "Chưa ghim tab Grok nào (Sẽ tự chọn hoặc mở tab mới).";
    }

    if (syncInputs) {
      autoBind.checked = currentSettings.autoBind !== false;
      autoClickTrial.checked = currentSettings.autoClickTrial !== false;
      delay.value = (currentSettings.delayMs || 5000) / 1000;
    }
  }

  // Cập nhật thẻ Đồng Bộ Tool Python
  async function fetchToolSync() {
    try {
      const res = await fetch("http://127.0.0.1:5050/api/grok/live_latest_code", {
        signal: AbortSignal.timeout(1500)
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();

      if (data.is_running) {
        toolStatusBadge.className = "status-pill on";
        toolStatusBadge.textContent = "🟢 SĂN CODE ĐANG CHẠY";
        syncPulseDot.className = "sync-pulse";
      } else {
        toolStatusBadge.className = "status-pill off";
        toolStatusBadge.textContent = "⚪ SĂN CODE ĐANG TẮT";
        syncPulseDot.className = "sync-pulse off";
      }

      activeToolCode = data.latest?.code || "";
      if (activeToolCode) {
        syncLatestCode.textContent = activeToolCode;
        btnSyncOpenLatest.disabled = false;
      } else {
        syncLatestCode.textContent = "-- Chưa có mã --";
        btnSyncOpenLatest.disabled = true;
      }

      if (data.latest?.time) {
        syncCodeTime.textContent = `Lúc: ${data.latest.time}`;
      } else {
        syncCodeTime.textContent = "Thời gian: --";
      }

      syncTotalCodes.textContent = `${data.total_seen || 0} mã đã quét`;
      syncReceivers.textContent = `${data.receivers || 0} Profile Grok kết nối`;

    } catch (err) {
      toolStatusBadge.className = "status-pill off";
      toolStatusBadge.textContent = "🔴 MẤT KẾT NỐI SERVER";
      syncPulseDot.className = "sync-pulse off";
      syncReceivers.textContent = "Chưa nối với Python (5050)";
    }
  }

  const STATUS_LABELS = {
    queued: "⏳ Đang chờ",
    processing: "🚀 Đang mở",
    opened: "✅ Đã mở link",
    failed: "❌ Lỗi",
    cancelled: "⏹ Đã hủy"
  };

  function renderHistory(log = []) {
    historyContainer.innerHTML = "";
    const pending = log.filter(item => ["queued", "processing"].includes(item.status)).length;
    pendingCount.textContent = pending ? `(${pending} đang chờ)` : "";

    if (!log || log.length === 0) {
      historyContainer.innerHTML = `<div class="empty-state">Đang chờ mã mới từ Tool Python... Bạn chỉ cần đăng nhập sẵn Grok!</div>`;
      return;
    }

    log.slice(0, 50).forEach(item => {
      const div = document.createElement("div");
      div.className = "history-item";
      const statusLabel = STATUS_LABELS[item.status] || item.status;
      const refUrl = `https://grok.com/refer/bot?code=${encodeURIComponent(item.code)}`;
      div.innerHTML = `
        <div class="history-header">
          <span class="code-badge" title="Bấm để mở lại mã này">${escapeHtml(item.code)}</span>
          <span style="font-size:11px;font-weight:600;">${statusLabel}</span>
        </div>
        <div class="history-links">
          <a href="${escapeHtml(refUrl)}" target="_blank">${escapeHtml(refUrl)}</a>
        </div>
        <div class="history-time">${new Date(item.receivedAt || item.timestamp || Date.now()).toLocaleString("vi-VN")}</div>
        ${item.error ? `<div style="color:var(--danger);font-size:11px;margin-top:2px;">${escapeHtml(item.error)}</div>` : ""}
      `;

      // Bấm vào badge mã để mở ngay
      div.querySelector(".code-badge")?.addEventListener("click", () => {
        chrome.runtime.sendMessage({ action: "FORCE_OPEN_CODE", code: item.code }, res => {
          if (res?.success) showMessage(`✅ Đã mở lại mã ${item.code}!`);
        });
      });

      historyContainer.appendChild(div);
    });
  }

  // Tải dữ liệu ban đầu
  const store = await chrome.storage.local.get(null);
  renderSettings(store.settings, true);
  renderHistory(store.deliveryLog || []);
  await fetchToolSync();

  // Polling đồng bộ liên tục khi popup mở
  const syncInterval = setInterval(fetchToolSync, 1800);
  window.addEventListener("unload", () => clearInterval(syncInterval));

  // Lắng nghe thay đổi storage trực tiếp
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local") return;
    chrome.storage.local.get(null).then(updated => {
      if (changes.settings) renderSettings(updated.settings);
      if (changes.deliveryLog) renderHistory(updated.deliveryLog);
      if (changes.toolSync) fetchToolSync();
    });
  });

  // Sự kiện nút Đồng Bộ
  btnSyncOpenLatest.addEventListener("click", () => {
    if (!activeToolCode) {
      showMessage("Chưa có mã Grok nào từ Tool Python!", true);
      return;
    }
    showMessage(`⚡ Đang chuyển tab Grok tới mã ${activeToolCode}...`);
    chrome.runtime.sendMessage({ action: "FORCE_OPEN_CODE", code: activeToolCode }, res => {
      if (res?.success) {
        showMessage(`✅ Đã mở thành công mã ${activeToolCode} trên Grok!`);
      } else {
        showMessage(`❌ ${res?.error || "Không mở được tab Grok"}`, true);
      }
    });
  });

  btnSyncRefresh.addEventListener("click", async () => {
    showMessage("🔄 Đang phát lệnh đồng bộ tới tất cả Profile...");
    try {
      const res = await fetch("http://127.0.0.1:5050/api/grok/sync_now", { method: "POST" });
      const d = await res.json();
      if (d?.success) {
        showMessage(`✅ Đã phát mã ${d.code} tới tất cả các Profile!`);
      }
    } catch {}
    await fetchToolSync();
  });

  // Sự kiện nút Cài đặt & Quản lý
  enabled.addEventListener("change", () => {
    const newSettings = {
      ...currentSettings,
      enabled: enabled.checked
    };
    chrome.runtime.sendMessage({ action: "SAVE_SETTINGS", settings: newSettings }, res => {
      if (res?.success) {
        renderSettings(res.settings);
        showMessage(res.settings.enabled ? "✅ Đã bật tự mở link Grok!" : "Đã tắt tự mở link.");
      }
    });
  });

  btnBindTab.addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url || !tab.url.startsWith("https://grok.com")) {
      showMessage("Hãy chuyển sang tab https://grok.com rồi mở popup để ghim!", true);
      return;
    }
    chrome.runtime.sendMessage({ action: "BIND_TAB", tabId: tab.id }, res => {
      if (res?.success) {
        renderSettings(res.settings);
        showMessage(`✅ Đã ghim tab Grok #${tab.id}!`);
      } else {
        showMessage(`❌ ${res?.error || "Lỗi ghim tab"}`, true);
      }
    });
  });

  btnOpenGrok.addEventListener("click", () => {
    chrome.tabs.create({ url: "https://grok.com/", active: true });
  });

  btnSave.addEventListener("click", () => {
    const newSettings = {
      ...currentSettings,
      enabled: enabled.checked,
      autoBind: autoBind.checked,
      autoClickTrial: autoClickTrial.checked,
      delayMs: Math.max(3, parseInt(delay.value, 10) || 5) * 1000
    };
    chrome.runtime.sendMessage({ action: "SAVE_SETTINGS", settings: newSettings }, res => {
      if (res?.success) {
        renderSettings(res.settings);
        showMessage("✅ Đã lưu cài đặt Grok Auto Opener!");
      } else {
        showMessage(`❌ ${res?.error || "Lỗi lưu cài đặt"}`, true);
      }
    });
  });

  btnStop.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "STOP" }, res => {
      if (res?.success) {
        renderSettings(res.settings);
        showMessage("🛑 Đã dừng và hủy hàng đợi.");
      }
    });
  });

  // Nút test mở thử 1 mã
  btnTestOpen.addEventListener("click", () => {
    const demoCode = "DEMO" + Math.floor(1000 + Math.random() * 9000);
    showMessage(`Đang thử nghiệm mở mã ${demoCode}...`);
    chrome.runtime.sendMessage({ action: "SIMULATE_CODE", code: demoCode }, res => {
      if (res?.success) {
        showMessage(`✅ Đã đưa mã ${demoCode} vào hàng đợi mở tab Grok!`);
      } else {
        showMessage(`⚠️ ${res?.error || "Không thử nghiệm được"}`, true);
      }
    });
  });
});

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
