// =========================================================================
// CapCut Auto Login Helper - Ultra-Simple In-Page Floating Controller
// =========================================================================

(() => {
  if (window.__CC_AUTO_LOGIN_INJECTED__) return;
  window.__CC_AUTO_LOGIN_INJECTED__ = true;

  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let isLoggingIn = false;

  // ── Helper: Parse input string (email|pass hoặc email \t pass) ─────────
  function parseAccountInput(raw) {
    if (!raw) return null;
    const clean = raw.trim();
    let email = "", password = "";

    // 1. Phân tách bằng phím Tab (email \t pass hoặc uid \t email \t pass)
    if (clean.includes("\t")) {
      const parts = clean.split("\t").map(p => p.trim()).filter(Boolean);
      const emailIdx = parts.findIndex(p => p.includes("@"));
      if (emailIdx !== -1) {
        email = parts[emailIdx];
        password = parts[emailIdx + 1] || "";
      }
    }
    // 2. Phân tách bằng dấu gạch đứng | (email|pass hoặc uid|email|pass)
    else if (clean.includes("|")) {
      const parts = clean.split("|").map(p => p.trim()).filter(Boolean);
      const emailIdx = parts.findIndex(p => p.includes("@"));
      if (emailIdx !== -1) {
        email = parts[emailIdx];
        password = parts[emailIdx + 1] || "";
      }
    }
    // 3. Phân tách bằng 4 dấu gạch ngang ---- (email----pass)
    else if (clean.includes("----")) {
      const parts = clean.split("----").map(p => p.trim()).filter(Boolean);
      const emailIdx = parts.findIndex(p => p.includes("@"));
      if (emailIdx !== -1) {
        email = parts[emailIdx];
        password = parts[emailIdx + 1] || "";
      }
    }
    // 4. Phân tách bằng dấu 2 chấm : (email:pass)
    else if (clean.includes(":")) {
      const parts = clean.split(":").map(p => p.trim()).filter(Boolean);
      const emailIdx = parts.findIndex(p => p.includes("@"));
      if (emailIdx !== -1) {
        email = parts[emailIdx];
        password = parts[emailIdx + 1] || "";
      }
    }
    // 5. Khoảng trắng
    else {
      const parts = clean.split(/\s+/).map(p => p.trim()).filter(Boolean);
      const emailIdx = parts.findIndex(p => p.includes("@"));
      if (emailIdx !== -1) {
        email = parts[emailIdx];
        password = parts[emailIdx + 1] || "";
      }
    }

    if (email && email.includes("@")) {
      return { email: email.trim(), password: (password || "capcut123").trim() };
    }
    return null;
  }

  // ── Helper: Safe React Input Setter ─────────────────────────────────────
  function setReactInputValue(input, val) {
    if (!input) return;
    input.focus();
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    nativeSetter.call(input, "");
    input.dispatchEvent(new Event("input", { bubbles: true }));

    nativeSetter.call(input, val);
    input.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: val }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  // ── Helper: Click Element with Coordinates ──────────────────────────────
  async function safeClick(element, label = "") {
    if (!element) return false;
    try {
      element.scrollIntoView({ behavior: "instant", block: "center" });
      await sleep(60);
      const rect = element.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const opts = {
        bubbles: true,
        cancelable: true,
        view: window,
        clientX: cx,
        clientY: cy,
        screenX: cx,
        screenY: cy
      };

      element.dispatchEvent(new PointerEvent("pointerdown", opts));
      element.dispatchEvent(new MouseEvent("mousedown", opts));
      element.dispatchEvent(new PointerEvent("pointerup", opts));
      element.dispatchEvent(new MouseEvent("mouseup", opts));
      element.dispatchEvent(new MouseEvent("click", opts));
      if (typeof element.click === "function") {
        element.click();
      }
      console.log(`[CapCut AutoLogin] Clicked: ${label}`);
      return true;
    } catch (err) {
      console.warn(`[CapCut AutoLogin] Failed to click ${label}:`, err);
      return false;
    }
  }

  // ── Click All Layers of Email Method Button ────────────────────────────
  async function clickEmailMethod(btn) {
    if (!btn) return false;
    btn.scrollIntoView({ behavior: "instant", block: "center" });
    await sleep(80);

    const label = btn.querySelector ? btn.querySelector(".lv_third_part_sign_in_expand-label") : null;
    const newBtn = btn.querySelector ? btn.querySelector(".lv_third_part_sign_in_expand_new-button") : (btn.classList?.contains("lv_third_part_sign_in_expand_new-button") ? btn : null);
    const wrapper = btn.closest ? btn.closest(".lv_third_part_sign_in_expand-wrapper") : null;
    const icon = btn.querySelector ? btn.querySelector(".lv_third_part_sign_in_expand-icon-email") : null;

    const layers = [label, newBtn, btn, wrapper, icon].filter(Boolean);

    for (const el of layers) {
      try {
        const rect = el.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const opts = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy, screenX: cx, screenY: cy };
        el.dispatchEvent(new PointerEvent("pointerdown", opts));
        el.dispatchEvent(new MouseEvent("mousedown", opts));
        el.dispatchEvent(new PointerEvent("pointerup", opts));
        el.dispatchEvent(new MouseEvent("mouseup", opts));
        el.dispatchEvent(new MouseEvent("click", opts));
        if (typeof el.click === "function") el.click();
      } catch (e) {
        console.warn("Click layer error:", e);
      }
    }
    console.log("[CapCut AutoLogin] Đã click đầy đủ các lớp của 'Tiếp tục bằng email'");
    return true;
  }

  // ── Helper: Wait for Element ───────────────────────────────────────────
  function waitFor(finderFn, timeoutMs = 12000, intervalMs = 250) {
    return new Promise(resolve => {
      const start = Date.now();
      const check = () => {
        try {
          const el = finderFn();
          if (el) return resolve(el);
        } catch {}
        if (Date.now() - start > timeoutMs) return resolve(null);
        setTimeout(check, intervalMs);
      };
      check();
    });
  }

  // ── DOM Finders for CapCut ─────────────────────────────────────────────
  function findToSButton() {
    const btns = Array.from(document.querySelectorAll("button, div, span"));
    return btns.find(b => {
      if (b.closest("#__ccl_root__")) return false;
      const txt = (b.textContent || "").trim();
      return txt === "OK" || txt === "Đồng ý" || txt === "Agree" || txt === "I agree";
    });
  }

  function findEmailLoginButton() {
    // 1. Selector chính xác 100% từ cấu trúc thật CapCut
    const labelSpan = Array.from(document.querySelectorAll(".lv_third_part_sign_in_expand-label, span, div")).find(el => {
      if (el.closest("#__ccl_root__")) return false;
      const t = (el.textContent || "").trim().toLowerCase();
      return t === "tiếp tục bằng email" || t === "continue with email" || t.includes("tiếp tục bằng email");
    });
    if (labelSpan) {
      return labelSpan.closest(".lv_third_part_sign_in_expand_new-button") || 
             labelSpan.closest(".lv_third_part_sign_in_expand-wrapper") || 
             labelSpan;
    }

    const emailIcon = document.querySelector(".lv_third_part_sign_in_expand-icon-email");
    if (emailIcon) {
      return emailIcon.closest(".lv_third_part_sign_in_expand_new-button") || 
             emailIcon.closest(".lv_third_part_sign_in_expand-wrapper") || 
             emailIcon.parentElement;
    }

    const expandBtn = document.querySelector(".lv_third_part_sign_in_expand_new-button, .lv_third_part_sign_in_expand-wrapper");
    if (expandBtn && (expandBtn.textContent || "").toLowerCase().includes("email")) {
      return expandBtn;
    }

    // 2. Selector based fallbacks
    const selectorMatch = document.querySelector(
      '.lv-login-method-item[data-type="email"], [data-testid="login-with-email"]'
    );
    if (selectorMatch) return selectorMatch;

    // 3. Text based fallback
    const candidates = Array.from(document.querySelectorAll("button, a, div[role='button'], div, span"));
    return candidates.find(el => {
      if (el.closest("#__ccl_root__")) return false;
      const txt = (el.textContent || "").trim().toLowerCase();
      const hasEmail = txt.includes("email") || txt.includes("e-mail");
      const isButton = txt.includes("tiếp tục") || txt.includes("continue") || txt.includes("đăng nhập") || txt.includes("log in") || txt === "email";
      return hasEmail && isButton && txt.length < 50;
    });
  }

  function findEmailInput() {
    const isSearchInput = (input) => {
      if (!input) return true;
      if (input.closest("#__ccl_root__")) return true;
      if (input.closest("header, nav, [class*='search'], [class*='Search']")) return true;
      const ph = (input.placeholder || "").toLowerCase();
      if (ph.includes("search") || ph.includes("tìm kiếm") || ph.includes("tìm")) return true;
      if (input.type === "search") return true;
      return false;
    };

    const specificSelectors = [
      'input[name="signUsername"]',
      'input[type="email"]',
      '.lv_sign_in_panel input',
      '.sign_in_panel input',
      '.login-panel input',
      'input[autocomplete="username"]',
      'input[autocomplete="email"]',
      'input[placeholder*="mail" i]',
      'input[placeholder*="email" i]'
    ];

    for (const s of specificSelectors) {
      const els = document.querySelectorAll(s);
      for (const el of els) {
        if (!isSearchInput(el) && el.type !== "hidden") {
          return el;
        }
      }
    }

    const modalInputs = document.querySelectorAll('.lv-modal input, .modal input, form input, [class*="login"] input');
    for (const el of modalInputs) {
      if (!isSearchInput(el) && el.type !== "hidden" && el.type !== "checkbox" && el.type !== "radio" && el.type !== "password") {
        return el;
      }
    }

    return null;
  }

  function findContinueButton() {
    const btns = Array.from(document.querySelectorAll("button, div[role='button'], div[id*='submit']"));
    return btns.find(b => {
      if (b.closest("#__ccl_root__")) return false;
      const txt = (b.textContent || "").trim().toLowerCase();
      return (
        txt === "tiếp tục" ||
        txt === "tiếp" ||
        txt === "continue" ||
        txt === "next" ||
        txt.includes("tiếp tục") ||
        txt.includes("continue") ||
        b.type === "submit"
      );
    });
  }

  function findPasswordInput() {
    const all = Array.from(document.querySelectorAll('input[type="password"]'));
    return all.find(el => !el.closest("#__ccl_root__"));
  }

  function findSubmitLoginButton() {
    const btns = Array.from(document.querySelectorAll("button, div[role='button']"));
    return btns.find(b => {
      if (b.closest("#__ccl_root__")) return false;
      const txt = (b.textContent || "").trim().toLowerCase();
      return (
        txt === "đăng nhập" ||
        txt === "log in" ||
        txt === "login" ||
        txt === "sign in" ||
        txt.includes("đăng nhập") ||
        txt.includes("log in") ||
        b.type === "submit"
      );
    });
  }

  function checkIsAlreadyLoggedIn() {
    const url = window.location.href;
    if (url.includes("/my-edit") || url.includes("/workspace") || url.includes("/tools")) {
      return true;
    }
    const avatar = document.querySelector(
      '.user-avatar, img[class*="avatar"], div[class*="avatar"], .header-user, [data-testid="header-avatar"]'
    );
    return Boolean(avatar);
  }

  // ── Auto Dismiss Popups ────────────────────────────────────────────────
  async function dismissPostLoginPopups() {
    for (let i = 0; i < 4; i++) {
      await sleep(1000);
      const skipBtns = Array.from(document.querySelectorAll("button, span, div"));
      const skip = skipBtns.find(b => {
        if (b.closest("#__ccl_root__")) return false;
        const txt = (b.textContent || "").trim().toLowerCase();
        return txt === "bỏ qua" || txt === "skip";
      });
      if (skip) safeClick(skip, "Bỏ qua khảo sát (Skip)");

      const closeBtns = document.querySelectorAll(
        '.lv-modal-close, button[aria-label="Close"], svg[class*="close"], [data-testid="modal-close"]'
      );
      closeBtns.forEach(c => {
        if (!c.closest("#__ccl_root__")) safeClick(c, "Đóng modal popup");
      });
    }
  }

  // ── Core Login Flow ────────────────────────────────────────────────────
  async function executeLogin() {
    if (isLoggingIn) return;
    const inp = document.getElementById("__ccl_inp__");
    const raw = (inp?.value || "").trim();
    const account = parseAccountInput(raw);

    if (!account || !account.email) {
      updateWidgetStatus("❌ Chưa có email|pass hợp lệ!", "error");
      inp?.focus();
      return;
    }

    isLoggingIn = true;
    updateWidgetStatus("Đang kiểm tra trang...", "working");

    try {
      // 0. Check already logged in
      if (checkIsAlreadyLoggedIn()) {
        updateWidgetStatus("✅ Đã đăng nhập sẵn rồi!", "success");
        isLoggingIn = false;
        return;
      }

      // If on homepage and not on login page, click Login header
      const pathname = window.location.pathname;
      if (!pathname.includes("/login") && !pathname.includes("/signup")) {
        const loginHeaderBtn = Array.from(document.querySelectorAll("button, a")).find(el => {
          if (el.closest("#__ccl_root__")) return false;
          const txt = (el.textContent || "").trim().toLowerCase();
          return txt === "đăng nhập" || txt === "log in" || txt === "sign in";
        });
        if (loginHeaderBtn) {
          updateWidgetStatus("Bấm nút Đăng nhập trang chủ...", "working");
          await safeClick(loginHeaderBtn, "Header Log In");
          await sleep(1200);
        } else {
          updateWidgetStatus("Đang chuyển sang trang Đăng nhập...", "working");
          window.location.href = "https://www.capcut.com/vi-vn/login";
          return;
        }
      }

      // Step 1: Dismiss ToS if any
      const tos = findToSButton();
      if (tos) {
        updateWidgetStatus("Đóng thông báo điều khoản...", "working");
        await safeClick(tos, "ToS Dialog");
        await sleep(400);
      }

      // Step 2: Bấm nút 'Tiếp tục bằng email'
      const emailMethodBtn = findEmailLoginButton();
      if (emailMethodBtn) {
        updateWidgetStatus("Đang bấm 'Tiếp tục bằng email'...", "working");
        await clickEmailMethod(emailMethodBtn);
        await sleep(1000);
      }

      // Step 3: Chờ ô nhập Email
      updateWidgetStatus("Đang tìm ô nhập Email...", "working");
      let emailInput = await waitFor(findEmailInput, 6000);

      if (!emailInput) {
        const retryBtn = findEmailLoginButton();
        if (retryBtn) {
          updateWidgetStatus("Bấm lại 'Tiếp tục bằng email'...", "working");
          await clickEmailMethod(retryBtn);
          await sleep(1200);
          emailInput = await waitFor(findEmailInput, 5000);
        }
      }

      if (!emailInput) {
        throw new Error("Không mở được form email! Hãy bấm tay nút 'Tiếp tục bằng email'");
      }

      // Điền Email
      updateWidgetStatus(`Nhập: ${account.email}`, "working");
      setReactInputValue(emailInput, account.email);
      await sleep(350);

      // Bấm Tiếp tục
      updateWidgetStatus("Bấm Tiếp tục...", "working");
      const continueBtn = await waitFor(findContinueButton, 4000);
      if (continueBtn) {
        await safeClick(continueBtn, "Tiếp tục");
        await sleep(1200);
      } else {
        emailInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, bubbles: true }));
        await sleep(1200);
      }

      // Step 4: Chờ ô nhập Password
      updateWidgetStatus("Đang chờ ô Mật khẩu...", "working");
      const pwdInput = await waitFor(findPasswordInput, 7000);
      if (!pwdInput) {
        throw new Error("Không thấy ô mật khẩu! (Có thể cần giải OTP/Captcha)");
      }

      setReactInputValue(pwdInput, account.password);
      await sleep(300);

      // Checkbox đồng ý điều khoản nếu có
      const cb = document.querySelector('input[type="checkbox"]:not(:checked)');
      if (cb && !cb.closest("#__ccl_root__")) {
        safeClick(cb, "Checkbox đồng ý");
        await sleep(200);
      }

      // Step 5: Bấm Đăng nhập
      updateWidgetStatus("Bấm Đăng nhập...", "working");
      const submitBtn = await waitFor(findSubmitLoginButton, 4000);
      if (submitBtn) {
        await safeClick(submitBtn, "Đăng nhập submit");
      } else {
        pwdInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", keyCode: 13, bubbles: true }));
      }

      // Step 6: Chờ kết quả
      updateWidgetStatus("Đang xử lý đăng nhập...", "working");
      const success = await waitFor(() => {
        if (checkIsAlreadyLoggedIn()) return true;
        const p = window.location.pathname;
        if (!p.includes("/login") && !p.includes("/signup") && p.length > 1) return true;
        return null;
      }, 15000);

      if (success) {
        updateWidgetStatus("🎉 Đăng nhập thành công!", "success");
        dismissPostLoginPopups();
      } else {
        const errEl = document.querySelector('.lv-form-item-explain, .error-message, [class*="error"]');
        if (errEl && errEl.textContent) {
          updateWidgetStatus(`❌ ${errEl.textContent.trim().slice(0, 40)}`, "error");
        } else {
          updateWidgetStatus("Đã gửi login! Đang tải...", "working");
        }
      }
    } catch (err) {
      console.error("[CapCut AutoLogin] Error:", err);
      updateWidgetStatus(`❌ Lỗi: ${err.message}`, "error");
    } finally {
      isLoggingIn = false;
    }
  }

  // ── Floating Widget UI ─────────────────────────────────────────────────
  function injectWidget() {
    if (document.getElementById("__ccl_root__")) return;

    const root = document.createElement("div");
    root.id = "__ccl_root__";
    root.innerHTML = `
      <div id="__ccl_card__">
        <div id="__ccl_header__">
          <div id="__ccl_brand__">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
              <path d="M4 4H20L15 11H9L4 4Z" fill="#FFF"/>
              <path d="M9 13H15L20 20H4L9 13Z" fill="#00F0FE"/>
            </svg>
            <span>CapCut Auto Login</span>
          </div>
          <button class="ccl-icon-btn" id="__ccl_btn_toggle__" title="Thu gọn / Mở rộng">━</button>
        </div>

        <div id="__ccl_body__">
          <div class="ccl-input-wrap">
            <div class="ccl-label">
              <span>⚡ DÁN EMAIL [TAB] PASS</span>
            </div>
            <input type="text" id="__ccl_inp__" placeholder="email	pass hoặc email|pass" spellcheck="false" autocomplete="off" />
          </div>

          <button id="__ccl_btn_login__">
            <span>🚀 ĐĂNG NHẬP NGAY</span>
          </button>

          <div id="__ccl_status__">
            <span>📌 Dán email tab pass rồi bấm Đăng nhập.</span>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(root);

    const inp = document.getElementById("__ccl_inp__");
    const btnLogin = document.getElementById("__ccl_btn_login__");
    const btnToggle = document.getElementById("__ccl_btn_toggle__");
    const card = document.getElementById("__ccl_card__");

    // Save input on change
    inp.addEventListener("input", () => {
      const raw = inp.value.trim();
      const parsed = parseAccountInput(raw);
      if (parsed) {
        updateWidgetStatus(`Nhận diện: ${parsed.email}`, "normal");
      }
      chrome.storage.local.set({ lastInput: raw }).catch(() => {});
    });

    // Enter key triggers login
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        executeLogin();
      }
    });

    btnLogin.addEventListener("click", () => {
      executeLogin();
    });

    btnToggle.addEventListener("click", () => {
      card.classList.toggle("collapsed");
      btnToggle.textContent = card.classList.contains("collapsed") ? "➕" : "━";
    });

    makeDraggable(root, document.getElementById("__ccl_header__"));
  }

  function updateWidgetStatus(msg, type = "normal") {
    const stat = document.getElementById("__ccl_status__");
    if (!stat) return;
    stat.className = "";
    if (type === "success") stat.classList.add("success");
    else if (type === "error") stat.classList.add("error");
    else if (type === "working") stat.classList.add("working");

    const spinner = type === "working" ? '<span class="ccl-spin"></span> ' : "";
    stat.innerHTML = `${spinner}<span>${msg}</span>`;
  }

  // ── Drag & Drop helper ─────────────────────────────────────────────────
  function makeDraggable(element, handle) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    handle.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
      if (e.target.tagName === "BUTTON") return;
      e.preventDefault();
      pos3 = e.clientX;
      pos4 = e.clientY;
      document.onmouseup = closeDragElement;
      document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
      e.preventDefault();
      pos1 = pos3 - e.clientX;
      pos2 = pos4 - e.clientY;
      pos3 = e.clientX;
      pos4 = e.clientY;
      element.style.top = `${element.offsetTop - pos2}px`;
      element.style.left = `${element.offsetLeft - pos1}px`;
      element.style.bottom = "auto";
      element.style.right = "auto";
    }

    function closeDragElement() {
      document.onmouseup = null;
      document.onmousemove = null;
    }
  }

  // ── Listen for messages from popup ─────────────────────────────────────
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === "TRIGGER_LOGIN") {
      executeLogin();
      sendResponse({ success: true });
    }
  });

  // ── Initialize ─────────────────────────────────────────────────────────
  async function init() {
    await sleep(300);
    injectWidget();

    // Restore last input if any
    const data = await chrome.storage.local.get(["lastInput"]);
    const inp = document.getElementById("__ccl_inp__");
    if (inp && data.lastInput) {
      inp.value = data.lastInput;
      const parsed = parseAccountInput(data.lastInput);
      if (parsed) {
        updateWidgetStatus(`Sẵn sàng: ${parsed.email}`, "normal");
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
