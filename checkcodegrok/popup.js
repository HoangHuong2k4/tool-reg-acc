// =========================================================================
// Grok Code Hunter - Popup Script
// =========================================================================

const TARGET_SEARCH_URL = "https://x.com/search?q=https%3A%2F%2Fgrok.com%2Frefer%2Fbot%3Fcode%3D&src=typed_query&f=live";

document.addEventListener("DOMContentLoaded", async () => {
  const toggleEnabled = document.getElementById("toggle-enabled");
  const inputInterval = document.getElementById("reload-interval");
  const inputBotToken = document.getElementById("bot-token");
  const inputChatIds = document.getElementById("chat-ids");
  const btnSave = document.getElementById("btn-save");
  const btnTestTelegram = document.getElementById("btn-test-telegram");
  const btnOpenSearch = document.getElementById("btn-open-search");
  const btnClearHistory = document.getElementById("btn-clear-history");
  const historyContainer = document.getElementById("history-container");
  const totalCountEl = document.getElementById("total-count");
  const statusMsg = document.getElementById("status-msg");

  // Load cài đặt hiện tại
  const store = await chrome.storage.local.get([
    "enabled",
    "reloadInterval",
    "botToken",
    "chatIds",
    "history",
    "stats"
  ]);

  toggleEnabled.checked = store.enabled !== false;
  inputInterval.value = store.reloadInterval || 45;
  inputBotToken.value = store.botToken || "";
  inputChatIds.value = store.chatIds || "";

  renderHistory(store.history || []);
  if (totalCountEl) totalCountEl.innerText = store.stats?.totalCodes || (store.history || []).length;

  // Bật/tắt trạng thái
  toggleEnabled.addEventListener("change", async () => {
    await chrome.storage.local.set({ enabled: toggleEnabled.checked });
    chrome.action.setBadgeText({ text: toggleEnabled.checked ? "ON" : "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: toggleEnabled.checked ? "#22c55e" : "#64748b" });
    showStatus(toggleEnabled.checked ? "Đã bật theo dõi!" : "Đã tắt theo dõi.");
  });

  // Lưu cấu hình
  btnSave.addEventListener("click", async () => {
    const interval = parseInt(inputInterval.value, 10) || 45;
    const botToken = inputBotToken.value.trim();
    const chatIds = inputChatIds.value.trim();

    await chrome.storage.local.set({
      reloadInterval: Math.max(10, interval),
      botToken: botToken,
      chatIds: chatIds
    });

    showStatus("✅ Đã lưu cài đặt thành công!");
  });

  // Test gửi Telegram
  btnTestTelegram.addEventListener("click", () => {
    const botToken = inputBotToken.value.trim();
    const chatIds = inputChatIds.value.trim();

    if (!botToken || !chatIds) {
      showStatus("❌ Vui lòng nhập Bot Token và Chat ID trước!", true);
      return;
    }

    btnTestTelegram.disabled = true;
    btnTestTelegram.innerText = "Đang gửi...";

    chrome.runtime.sendMessage(
      {
        action: "SEND_TELEGRAM_TEST",
        botToken: botToken,
        chatIds: chatIds
      },
      res => {
        btnTestTelegram.disabled = false;
        btnTestTelegram.innerText = "📩 Test Telegram";
        if (res && res.success) {
          showStatus(`✅ Đã gửi test thành công tới ${res.sentCount} chat ID!`);
        } else {
          showStatus(`❌ Lỗi: ${res?.error || "Không gửi được"}`, true);
        }
      }
    );
  });

  // Mở trang X.com Live Search
  btnOpenSearch.addEventListener("click", () => {
    chrome.tabs.create({ url: TARGET_SEARCH_URL });
  });

  // Xóa lịch sử
  btnClearHistory.addEventListener("click", () => {
    if (confirm("Bạn có chắc chắn muốn xóa lịch sử các mã đã quét?")) {
      chrome.runtime.sendMessage({ action: "CLEAR_HISTORY" }, () => {
        renderHistory([]);
        if (totalCountEl) totalCountEl.innerText = "0";
        showStatus("Đã làm sạch lịch sử.");
      });
    }
  });

  function showStatus(text, isError = false) {
    statusMsg.innerText = text;
    statusMsg.style.display = "block";
    statusMsg.style.color = isError ? "#ef4444" : "#22c55e";
    setTimeout(() => {
      statusMsg.style.display = "none";
    }, 3000);
  }

  function renderHistory(items) {
    if (!historyContainer) return;
    if (!items || items.length === 0) {
      historyContainer.innerHTML = '<div class="empty-state">Chưa quét được mã nào. Hãy mở trang X.com Live Search để bắt đầu!</div>';
      return;
    }

    historyContainer.innerHTML = items
      .map(item => `
        <div class="history-item">
          <div class="history-header">
            <span class="code-badge" data-code="${escapeHtml(item.code)}" title="Click để copy mã">${escapeHtml(item.code)}</span>
            <span class="history-time">${escapeHtml(item.dateStr || "")}</span>
          </div>
          <div class="history-meta">
            👤 <b>${escapeHtml(item.author || "User")}</b> (${escapeHtml(item.handle || "@user")})
          </div>
          <div class="history-links">
            <a href="${item.referUrl}" target="_blank">🔗 Mở link Grok</a>
            ${item.tweetUrl ? `<a href="${item.tweetUrl}" target="_blank">🐦 Xem Tweet</a>` : ""}
          </div>
        </div>
      `)
      .join("");

    // Sự kiện click copy badge
    historyContainer.querySelectorAll(".code-badge").forEach(badge => {
      badge.addEventListener("click", () => {
        const code = badge.getAttribute("data-code");
        if (code) {
          navigator.clipboard.writeText(code);
          const orig = badge.innerText;
          badge.innerText = "COPIED!";
          setTimeout(() => {
            badge.innerText = orig;
          }, 1200);
        }
      });
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});

