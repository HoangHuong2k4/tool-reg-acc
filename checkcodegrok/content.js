// =========================================================================
// Grok Code Hunter - Content Script for X.com (Twitter)
// =========================================================================

(function () {
  let isEnabled = true;
  let reloadInterval = 45; // giây mặc định
  let countdown = 45;
  let timerId = null;
  let isPaused = false;
  let totalDetectedSession = 0;
  let lastFoundCode = "";

  // Kiểm tra xem trang hiện tại có phải trang tìm kiếm Grok referral không
  function isTargetPage() {
    const url = window.location.href.toLowerCase();
    return url.includes("x.com/search") || url.includes("twitter.com/search");
  }

  // Khởi động
  async function init() {
    const store = await chrome.storage.local.get(["enabled", "reloadInterval"]);
    isEnabled = store.enabled !== false;
    reloadInterval = store.reloadInterval || 45;
    countdown = reloadInterval;

    if (!isTargetPage()) {
      return;
    }

    createFloatingWidget();
    scanTweets();

    // Theo dõi DOM thay đổi (khi Twitter load thêm tweet mới)
    const observer = new MutationObserver(() => {
      scanTweets();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    startCountdown();
  }

  // Quét các tweet hiển thị trên trang
  function scanTweets() {
    if (!isEnabled) return;

    const tweetArticles = document.querySelectorAll('article[data-testid="tweet"]');
    tweetArticles.forEach(article => {
      processTweetArticle(article);
    });
  }

  // Xử lý 1 phần tử tweet
  function processTweetArticle(article) {
    try {
      // 1. Trích xuất text của tweet
      const tweetTextEl = article.querySelector('div[data-testid="tweetText"]');
      const tweetText = tweetTextEl ? tweetTextEl.innerText : "";

      // 2. Tìm tất cả các link trong tweet (bao gồm text, href, title)
      const links = Array.from(article.querySelectorAll("a"));
      let foundCode = null;
      let referUrl = null;

      // Regex tìm kiếm code Grok referral
      const codeRegex = /grok\.com\/refer\/bot\?code=([A-Za-z0-9_-]{6,24})/i;
      const genericCodeRegex = /code=([A-Za-z0-9_-]{6,24})/i;

      // Check trong toàn bộ nội dung text của tweet và các thẻ a
      const fullTextToScan = [
        tweetText,
        ...links.map(a => `${a.href || ""} ${a.innerText || ""} ${a.title || ""}`)
      ].join(" ");

      const matchFull = fullTextToScan.match(codeRegex);
      if (matchFull && matchFull[1]) {
        foundCode = matchFull[1].trim();
      } else {
        const matchGeneric = fullTextToScan.match(genericCodeRegex);
        if (matchGeneric && matchGeneric[1]) {
          foundCode = matchGeneric[1].trim();
        }
      }

      if (!foundCode) return;

      referUrl = `https://grok.com/refer/bot?code=${foundCode}`;

      // 3. Trích xuất thông tin người đăng & link bài viết
      const userNameEl = article.querySelector('div[data-testid="User-Name"]');
      let author = "X User";
      let handle = "@user";
      let tweetUrl = "";

      if (userNameEl) {
        const textParts = userNameEl.innerText.split("\n").map(s => s.trim()).filter(Boolean);
        if (textParts.length > 0) author = textParts[0];
        const handleMatch = userNameEl.innerText.match(/@([A-Za-z0-9_]+)/);
        if (handleMatch) handle = `@${handleMatch[1]}`;
      }

      // Tìm link status của tweet
      const statusLink = links.find(a => a.href && a.href.includes("/status/"));
      let tweetId = "";
      if (statusLink) {
        tweetUrl = statusLink.href;
        const idMatch = tweetUrl.match(/\/status\/(\d+)/);
        if (idMatch) tweetId = idMatch[1];
      }

      // Gửi sang background.js để kiểm tra trùng lặp & phát thông báo Telegram
      chrome.runtime.sendMessage(
        {
          action: "NEW_CODE_FOUND",
          data: {
            code: foundCode,
            referUrl,
            author,
            handle,
            tweetUrl,
            tweetId,
            text: tweetText
          }
        },
        response => {
          if (response && response.isNew) {
            totalDetectedSession++;
            lastFoundCode = foundCode;
            updateWidgetUI();
            flashWidget();
          }
        }
      );
    } catch (e) {
      console.warn("[GrokHunter] Lỗi khi xử lý tweet:", e);
    }
  }

  // Đếm ngược tự động reload trang
  function startCountdown() {
    if (timerId) clearInterval(timerId);

    timerId = setInterval(() => {
      if (isPaused || !isEnabled) return;

      countdown--;
      updateWidgetCountdown();

      if (countdown <= 0) {
        countdown = reloadInterval;
        // Thực hiện tải lại trang để nạp các bài tweet Live mới nhất
        window.location.reload();
      }
    }, 1000);
  }

  // Tạo UI Widget nổi trên góc trang web
  function createFloatingWidget() {
    if (document.getElementById("grok-hunter-widget")) return;

    const widget = document.createElement("div");
    widget.id = "grok-hunter-widget";
    widget.innerHTML = `
      <div class="gh-header">
        <div class="gh-title">
          <span class="gh-dot"></span>
          <span>Grok Hunter</span>
        </div>
        <div class="gh-controls">
          <button id="gh-btn-pause" title="Tạm dừng / Tiếp tục">⏸</button>
          <button id="gh-btn-reload" title="Tải lại ngay">🔄</button>
          <button id="gh-btn-toggle" title="Thu nhỏ / Mở rộng">_</button>
        </div>
      </div>
      <div class="gh-body" id="gh-body-content">
        <div class="gh-row">
          <span class="gh-label">Tự reload sau:</span>
          <span class="gh-value" id="gh-timer">${countdown}s</span>
        </div>
        <div class="gh-row">
          <span class="gh-label">Đã bắt trong phiên:</span>
          <span class="gh-value gh-count" id="gh-count">${totalDetectedSession}</span>
        </div>
        <div class="gh-row" id="gh-latest-row" style="display: none;">
          <span class="gh-label">Mã mới nhất:</span>
          <span class="gh-value gh-code" id="gh-latest-code" title="Bấm để copy">--</span>
        </div>
      </div>
    `;

    document.body.appendChild(widget);

    // Bắt sự kiện các nút trên widget
    const btnPause = document.getElementById("gh-btn-pause");
    const btnReload = document.getElementById("gh-btn-reload");
    const btnToggle = document.getElementById("gh-btn-toggle");
    const latestCodeEl = document.getElementById("gh-latest-code");

    btnPause.addEventListener("click", () => {
      isPaused = !isPaused;
      btnPause.innerText = isPaused ? "▶" : "⏸";
      btnPause.title = isPaused ? "Tiếp tục" : "Tạm dừng";
      const dot = widget.querySelector(".gh-dot");
      if (dot) dot.style.backgroundColor = isPaused ? "#f59e0b" : "#22c55e";
    });

    btnReload.addEventListener("click", () => {
      window.location.reload();
    });

    btnToggle.addEventListener("click", () => {
      const body = document.getElementById("gh-body-content");
      if (body.style.display === "none") {
        body.style.display = "block";
        btnToggle.innerText = "_";
      } else {
        body.style.display = "none";
        btnToggle.innerText = "+";
      }
    });

    latestCodeEl.addEventListener("click", () => {
      if (lastFoundCode) {
        navigator.clipboard.writeText(lastFoundCode);
        const orig = latestCodeEl.innerText;
        latestCodeEl.innerText = "ĐÃ COPY!";
        setTimeout(() => {
          latestCodeEl.innerText = orig;
        }, 1500);
      }
    });
  }

  function updateWidgetCountdown() {
    const el = document.getElementById("gh-timer");
    if (el) el.innerText = `${countdown}s`;
  }

  function updateWidgetUI() {
    const countEl = document.getElementById("gh-count");
    const latestRow = document.getElementById("gh-latest-row");
    const latestCodeEl = document.getElementById("gh-latest-code");

    if (countEl) countEl.innerText = totalDetectedSession;
    if (lastFoundCode && latestRow && latestCodeEl) {
      latestRow.style.display = "flex";
      latestCodeEl.innerText = lastFoundCode;
    }
  }

  function flashWidget() {
    const widget = document.getElementById("grok-hunter-widget");
    if (!widget) return;
    widget.classList.add("gh-flash");
    setTimeout(() => {
      widget.classList.remove("gh-flash");
    }, 1200);
  }

  // Khởi chạy khi DOM sẵn sàng
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

