// =========================================================================
// Grok Auto Link Opener - Content Script (content.js)
// Tự động phát hiện và BẤM nút "Start your 14 day free trial" / Nhận ưu đãi / Tiếp tục
// Chạy trực tiếp trên tab grok.com
// =========================================================================

(() => {
  let isScanning = false;
  let clickedElements = new WeakSet();
  let lastClickedTime = 0;
  let bannerEl = null;

  // Hiển thị thông báo góc màn hình
  function showBanner(text, type = "info") {
    try {
      if (!bannerEl) {
        bannerEl = document.createElement("div");
        bannerEl.id = "grok-auto-opener-banner";
        Object.assign(bannerEl.style, {
          position: "fixed",
          top: "16px",
          right: "16px",
          zIndex: "2147483647",
          padding: "10px 16px",
          borderRadius: "8px",
          fontSize: "13px",
          fontWeight: "600",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
          transition: "all 0.3s ease",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          maxWidth: "380px",
          lineHeight: "1.4"
        });
        document.body.appendChild(bannerEl);
      }

      if (type === "success") {
        bannerEl.style.background = "#059669";
        bannerEl.style.color = "#ffffff";
        bannerEl.style.border = "1px solid #10b981";
      } else if (type === "warn") {
        bannerEl.style.background = "#d97706";
        bannerEl.style.color = "#ffffff";
        bannerEl.style.border = "1px solid #f59e0b";
      } else {
        bannerEl.style.background = "#1e293b";
        bannerEl.style.color = "#38bdf8";
        bannerEl.style.border = "1px solid #38bdf8";
      }

      bannerEl.innerHTML = text;
      bannerEl.style.opacity = "1";
      bannerEl.style.transform = "translateY(0)";

      if (type === "success" || type === "warn") {
        setTimeout(() => {
          if (bannerEl) {
            bannerEl.style.opacity = "0";
            bannerEl.style.transform = "translateY(-10px)";
          }
        }, 5000);
      }
    } catch {}
  }

  // Giả lập click chuột thực tế (Next.js/React thân thiện)
  function simulateClick(el) {
    if (!el || clickedElements.has(el)) return false;
    clickedElements.add(el);
    lastClickedTime = Date.now();

    try {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch {}

    const mouseEvents = ["mouseover", "mouseenter", "mousedown", "mouseup", "click"];
    for (const evtName of mouseEvents) {
      try {
        const evt = new MouseEvent(evtName, {
          bubbles: true,
          cancelable: true,
          view: window,
          buttons: 1
        });
        el.dispatchEvent(evt);
      } catch {}
    }

    if (typeof el.click === "function") {
      try { el.click(); } catch {}
    }

    return true;
  }

  // Danh sách từ khóa ưu tiên tìm nút Trial (CHỈ bấm Start 14-day free trial, KHÔNG bấm Choose a plan)
  const TRIAL_KEYWORDS = [
    "start your 14 day free trial",
    "start 14 day free trial",
    "start 14-day free trial",
    "14 day free trial",
    "14-day free trial",
    "2 weeks free",
    "2 week free",
    "free trial",
    "start trial",
    "start free trial",
    "claim 2 weeks",
    "claim trial",
    "claim free",
    "claim",
    "dùng thử 14 ngày",
    "dùng thử miễn phí",
    "nhận ưu đãi",
    "accept invite",
    "accept referral"
  ];

  // Tìm nút Trial tốt nhất trên trang
  function findTrialButton() {
    // 1. Ưu tiên số 1: data-testid="referral-trial-sign-up" (Start your 14 day free trial)
    const exactSignUpBtn = document.querySelector('[data-testid="referral-trial-sign-up"]');
    if (exactSignUpBtn && isElementClickable(exactSignUpBtn)) {
      return { el: exactSignUpBtn, label: "Start your 14 day free trial", priority: 100 };
    }

    // 2. Tìm theo data-testid trial hợp lệ khác (BỎ QUA referral-trial-choose-plan)
    const testIdSelectors = [
      '[data-testid="referral-trial-claim"]',
      '[data-testid*="trial-button"]',
      '[data-testid*="referral-trial-sign"]'
    ];

    for (const sel of testIdSelectors) {
      const el = document.querySelector(sel);
      if (el && isElementClickable(el)) {
        return { el, label: el.textContent?.trim() || sel, priority: 90 };
      }
    }

    // 3. Tìm tất cả các button, a, role=button khớp từ khóa trial (BỎ QUA choose a plan)
    const candidates = Array.from(document.querySelectorAll('button, a, [role="button"], input[type="button"], input[type="submit"]'));
    let bestMatch = null;
    let highestScore = -1;

    for (const el of candidates) {
      if (!isElementClickable(el)) continue;

      const text = (el.textContent || el.value || "").toLowerCase().trim();
      if (!text || text.includes("choose a plan") || text.includes("choose plan")) continue;

      for (let i = 0; i < TRIAL_KEYWORDS.length; i++) {
        const kw = TRIAL_KEYWORDS[i];
        if (text.includes(kw)) {
          const score = 100 - i;
          if (score > highestScore) {
            highestScore = score;
            bestMatch = { el, label: el.textContent?.trim() || kw, priority: score };
          }
          break;
        }
      }
    }

    return bestMatch;
  }

  function isElementClickable(el) {
    if (!el || el.disabled || el.getAttribute("aria-disabled") === "true") return false;

    // Bỏ qua tuyệt đối nút "Choose a plan" theo yêu cầu người dùng
    const text = (el.textContent || el.value || "").toLowerCase().trim();
    if (text.includes("choose a plan") || text.includes("choose plan") || el.getAttribute("data-testid") === "referral-trial-choose-plan") {
      return false;
    }

    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  // Quét và tự động bấm
  async function scanAndAutoClick() {
    if (isScanning) return;
    isScanning = true;

    try {
      // Kiểm tra cài đặt người dùng
      const { settings } = await chrome.storage.local.get("settings");
      if (settings && settings.autoClickTrial === false) {
        isScanning = false;
        return;
      }

      // Chỉ thực hiện trên trang referral hoặc plans hoặc có code
      const currentUrl = window.location.href;
      const isReferPage = currentUrl.includes("/refer") || currentUrl.includes("code=") || currentUrl.includes("/plans");
      if (!isReferPage) {
        isScanning = false;
        return;
      }

      // Không bấm liên tục nếu vừa bấm cách đây < 3 giây
      if (Date.now() - lastClickedTime < 3000) {
        isScanning = false;
        return;
      }

      const match = findTrialButton();
      if (match && match.el && !clickedElements.has(match.el)) {
        showBanner(`⚡ <b>Grok Auto</b>: Đã phát hiện nút <b>${escapeHtml(match.label)}</b>. Đang tự động bấm...`);
        const clicked = simulateClick(match.el);
        if (clicked) {
          showBanner(`✅ <b>Grok Auto</b>: Đã bấm <b>${escapeHtml(match.label)}</b> thành công!`, "success");

          // Sau khi bấm nút chính, theo dõi tiếp 4 giây xem có popup/modal xác nhận "Continue" hay "Start" xuất hiện không
          checkFollowUpModal();
        }
      }
    } catch (e) {
      console.warn("[GrokAutoOpener]", e);
    } finally {
      isScanning = false;
    }
  }

  // Kiểm tra popup modal xác nhận tiếp theo (ví dụ: nút "Continue", "Confirm", "Tiếp tục")
  function checkFollowUpModal() {
    let attempts = 0;
    const modalInterval = setInterval(() => {
      attempts++;
      if (attempts > 8) {
        clearInterval(modalInterval);
        return;
      }

      const modalButtons = Array.from(document.querySelectorAll('div[role="dialog"] button, [data-testid*="modal"] button, button'));
      for (const btn of modalButtons) {
        if (!isElementClickable(btn) || clickedElements.has(btn)) continue;
        const txt = (btn.textContent || "").toLowerCase().trim();
        if (txt === "continue" || txt === "tiếp tục" || txt === "confirm" || txt === "xác nhận" || txt === "start" || txt === "claim") {
          simulateClick(btn);
          showBanner(`✅ <b>Grok Auto</b>: Đã bấm xác nhận <b>${escapeHtml(btn.textContent.trim())}</b>!`, "success");
          clearInterval(modalInterval);
          return;
        }
      }
    }, 500);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
  }

  // Khởi chạy theo dõi liên tục
  function initObserver() {
    // 1. Quét ngay khi script load
    scanAndAutoClick();

    // 2. Định kỳ quét mỗi 600ms trong 15s đầu
    let ticks = 0;
    const poller = setInterval(() => {
      ticks++;
      scanAndAutoClick();
      if (ticks > 25) clearInterval(poller);
    }, 600);

    // 3. MutationObserver theo dõi DOM thay đổi khi React/Next.js render
    const observer = new MutationObserver(() => {
      scanAndAutoClick();
    });

    if (document.body) {
      observer.observe(document.body, { childList: true, subtree: true });
    } else {
      document.addEventListener("DOMContentLoaded", () => {
        if (document.body) observer.observe(document.body, { childList: true, subtree: true });
      });
    }

    // 4. Bắt thay đổi route URL của Next.js (pushState / popstate)
    window.addEventListener("popstate", () => setTimeout(scanAndAutoClick, 400));
    const origPush = history.pushState;
    history.pushState = function (...args) {
      const res = origPush.apply(this, args);
      setTimeout(scanAndAutoClick, 400);
      return res;
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initObserver);
  } else {
    initObserver();
  }
})();

