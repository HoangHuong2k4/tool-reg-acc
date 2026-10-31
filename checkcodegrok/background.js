// =========================================================================
// Grok Code Hunter - Background Service Worker (Manifest V3)
// =========================================================================

const DEFAULT_SETTINGS = {
  enabled: true,
  reloadInterval: 45, // giây
  botToken: "8855096263:AAHuhzdQVm_ST0oT-hpCJcHWyuYsTOfsWcw",
  chatIds: "7353915691, 1007974270",
  targetUrl: "https://x.com/search?q=https%3A%2F%2Fgrok.com%2Frefer%2Fbot%3Fcode%3D&src=typed_query&f=live",
  history: [],
  seenCodes: [],
  seenTweetIds: [],
  stats: { totalCodes: 0, lastCheckTime: null }
};

// Khởi tạo cài đặt mặc định khi cài extension
chrome.runtime.onInstalled.addListener(async () => {
  const data = await chrome.storage.local.get(null);
  const toSet = {};
  for (const [key, val] of Object.entries(DEFAULT_SETTINGS)) {
    if (data[key] === undefined) {
      toSet[key] = val;
    }
  }
  if (Object.keys(toSet).length > 0) {
    await chrome.storage.local.set(toSet);
  }
  updateBadge(true);
});

function updateBadge(enabled, count) {
  if (!enabled) {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#64748b" });
  } else {
    chrome.action.setBadgeText({ text: count ? String(count) : "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#22c55e" });
  }
}

// Hàm gửi tin nhắn Telegram
async function sendTelegramMessage(text, customToken, customChatIds) {
  const store = await chrome.storage.local.get(["botToken", "chatIds"]);
  const botToken = (customToken || store.botToken || "").trim();
  const rawChatIds = (customChatIds || store.chatIds || "").trim();

  if (!botToken || !rawChatIds) {
    return { success: false, error: "Thiếu Bot Token hoặc Chat ID!" };
  }

  const chatIds = rawChatIds
    .split(/[,;\s]+/)
    .map(c => c.trim())
    .filter(Boolean);

  if (chatIds.length === 0) {
    return { success: false, error: "Danh sách Chat ID rỗng!" };
  }

  let successCount = 0;
  let lastError = null;

  for (const cid of chatIds) {
    try {
      const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: cid,
          text: text,
          parse_mode: "HTML",
          disable_web_page_preview: false
        })
      });
      const data = await res.json();
      if (data && data.ok) {
        successCount++;
      } else {
        lastError = data.description || "Lỗi Telegram API";
      }
    } catch (e) {
      lastError = e.message;
    }
  }

  return {
    success: successCount > 0,
    sentCount: successCount,
    error: successCount === 0 ? lastError : null
  };
}

// Lắng nghe message từ content script hoặc popup
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "NEW_CODE_FOUND") {
    handleNewCode(req.data).then(sendResponse);
    return true; // async response
  }

  if (req.action === "SEND_TELEGRAM_TEST") {
    const text = `🔔 <b>Grok Code Hunter: Kiểm tra kết nối thành công!</b>\n\nExtension đã sẵn sàng săn code referral từ X.com.`;
    sendTelegramMessage(text, req.botToken, req.chatIds).then(sendResponse);
    return true;
  }

  if (req.action === "CLEAR_HISTORY") {
    chrome.storage.local.set({ history: [], seenCodes: [], seenTweetIds: [] }).then(() => {
      sendResponse({ success: true });
    });
    return true;
  }
});

async function handleNewCode(item) {
  const store = await chrome.storage.local.get([
    "seenCodes",
    "seenTweetIds",
    "history",
    "stats",
    "enabled"
  ]);

  if (store.enabled === false) {
    return { isNew: false, reason: "Monitoring disabled" };
  }

  const seenCodes = new Set(store.seenCodes || []);
  const seenTweetIds = new Set(store.seenTweetIds || []);
  const history = store.history || [];

  const code = (item.code || "").toUpperCase().trim();
  const tweetId = item.tweetId || "";

  // Nếu code đã được gửi hoặc tweet này đã xử lý -> bỏ qua
  if (!code || seenCodes.has(code) || (tweetId && seenTweetIds.has(tweetId))) {
    return { isNew: false };
  }

  seenCodes.add(code);
  if (tweetId) seenTweetIds.add(tweetId);

  const newEntry = {
    ...item,
    code,
    timestamp: Date.now(),
    dateStr: new Date().toLocaleString("vi-VN")
  };

  history.unshift(newEntry);
  if (history.length > 100) history.pop();

  const totalCodes = (store.stats?.totalCodes || 0) + 1;
  await chrome.storage.local.set({
    seenCodes: Array.from(seenCodes),
    seenTweetIds: Array.from(seenTweetIds),
    history: history,
    stats: {
      totalCodes: totalCodes,
      lastCheckTime: Date.now()
    }
  });

  updateBadge(true, totalCodes);

  // Tạo nội dung tin nhắn Telegram
  const msgText = [
    `🔥 <b>PHÁT HIỆN MÃ REFERRAL GROK MỚI!</b>`,
    ``,
    `🔑 <b>Code:</b> <code>${code}</code>`,
    `🔗 <b>Link đăng ký:</b> <a href="${item.referUrl || `https://grok.com/refer/bot?code=${code}`}">${item.referUrl || `https://grok.com/refer/bot?code=${code}`}</a>`,
    ``,
    `👤 <b>Người đăng:</b> ${escapeHtml(item.author || "Ẩn danh")} (${escapeHtml(item.handle || "@user")})`,
    `📝 <b>Nội dung bài viết:</b>\n<i>${escapeHtml(item.text ? item.text.slice(0, 300) : "...")}</i>`,
    ``,
    `🐦 <b>Link Tweet:</b> ${item.tweetUrl ? `<a href="${item.tweetUrl}">Xem trên X.com</a>` : "N/A"}`,
    `⏰ <b>Thời gian:</b> ${newEntry.dateStr}`
  ].join("\n");

  await sendTelegramMessage(msgText);
  return { isNew: true, code: code };
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

