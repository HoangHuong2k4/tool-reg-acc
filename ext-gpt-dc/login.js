(async function () {

    const stored  = await chrome.storage.local.get(['chatgpt_account']);
    const hostname = window.location.hostname;
    const pathname = window.location.pathname;

    // =============================================
    //  UTILS
    // =============================================
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    function waitForElement(selector, timeout = 10000) {
        return new Promise((resolve, reject) => {
            let elapsed = 0;
            const timer = setInterval(() => {
                const el = document.querySelector(selector);
                if (el) { clearInterval(timer); resolve(el); }
                elapsed += 200;
                if (elapsed >= timeout) { clearInterval(timer); reject(new Error('Timeout: ' + selector)); }
            }, 200);
        });
    }

    async function simulateTyping(element, text) {
        if (!element) return;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        element.focus();
        setter.call(element, '');
        element.dispatchEvent(new Event('input', { bubbles: true }));
        for (let i = 0; i < text.length; i++) {
            setter.call(element, text.slice(0, i + 1));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            await sleep(Math.random() * 60 + 40);
        }
        element.blur();
    }

    // Dùng cho các input đặc biệt như 2FA — set value 1 lần rồi fire đủ events
    function setInputValue(element, value) {
        if (!element) return;
        element.focus();
        // Dùng native setter để React nhận biết
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(element, value);
        // Fire các events mà React Aria cần (KHÔNG fire Enter — tránh submit sớm)
        element.dispatchEvent(new InputEvent('input',  { bubbles: true, inputType: 'insertText', data: value }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('[AutoLogin] setInputValue:', value, '→ element:', element.name || element.id);
    }

    // Gọi API với timeout 5 giây, fallback local TOTP nếu lỗi
    async function getTOTPCode(secret) {
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 5000);
            const resp = await fetch(
                'https://lay2fa.phh.info.vn/api/totp.php?secret=' + encodeURIComponent(secret),
                { method: 'GET', signal: controller.signal }
            );
            clearTimeout(timer);
            const json = await resp.json();
            let code = json.code || json.totp || json.otp || (json.data && (json.data.code || json.data.totp));
            if (code) code = String(code).replace(/\D/g, '').slice(0, 6);
            if (code && code.length === 6) {
                console.log('[AutoLogin] API TOTP:', code);
                return { code, source: 'api' };
            }
        } catch(e) {
            console.log('[AutoLogin] API lỗi/timeout:', e.message);
        }
        // Fallback local
        const code = await generateTOTP(secret);
        console.log('[AutoLogin] Local TOTP:', code);
        return { code, source: 'local' };
    }

    // =============================================
    //  LOGIN FLOW — nhận account object làm tham số
    // =============================================
    function updateMainStatus(msg) {
        const stat = document.getElementById('__alp_s__');
        if (stat) stat.innerHTML = msg;
        console.log('[AutoLogin Main]', msg.replace(/<[^>]+>/g,''));
    }

    async function startLoginFlow(account) {
        if (!account || !account.email) return;
        await sleep(1200);

        async function step1_ClickLogin() {
            try {
                updateMainStatus('<span style="color:#4a90e2">🔄 Đang tìm nút Log in...</span>');
                const btn = await waitForElement(
                    'button[data-mobile-auth-entry-action="login"], a[href*="log-in"], button.wm-app-loginButton'
                );
                await sleep(800); btn.click();
            } catch(e) { console.log('[AutoLogin] Không tìm thấy Log in btn:', e.message); }
        }

        async function step2_EnterEmail() {
            try {
                updateMainStatus('<span style="color:#4a90e2">🔄 Đang nhập email...</span>');
                const input = await waitForElement(
                    '#mobile-auth-email, input[type="email"], input[autocomplete="email"], input[name="username"], input[name="login_hint"]'
                );
                await sleep(600);
                await simulateTyping(input, account.email);
                updateMainStatus('<span style="color:#4a90e2">🔄 Đã nhập email, đang click...</span>');
                await sleep(400);
                // Ưu tiên nút submit bên trong form email, tránh click nhầm nút Dismiss của bottom sheet
                const btn = document.querySelector(
                    'form[data-auth-provider="email"] button[type="submit"],' +
                    'button._X60mza_emailButton,' +
                    'button[data-dd-action-name="Continue"]'
                );
                if (btn) btn.click();
            } catch(e) { console.log('[AutoLogin] Lỗi nhập email:', e.message); }
        }

        async function step3_EnterPassword() {
            try {
                updateMainStatus('<span style="color:#4a90e2">🔄 Đang nhập mật khẩu...</span>');
                const input = await waitForElement('input[type="password"], input[name="current-password"]');
                await sleep(600);
                await simulateTyping(input, account.password);
                updateMainStatus('<span style="color:#4a90e2">🔄 Đã nhập pass, đang click...</span>');
                await sleep(400);
                const btn = document.querySelector('button[type="submit"], button[name="intent"][value="validate"]');
                if (btn) btn.click();
            } catch(e) { console.log('[AutoLogin] Lỗi nhập password:', e.message); }
        }

        async function step4_Enter2FA() {
            try {
                updateMainStatus('<span style="color:#4a90e2">🔄 Đang lấy mã 2FA...</span>');
                if (!account.totp_secret) {
                    updateMainStatus('<span style="color:#e74c3c">✗ Không có secret 2FA!</span>');
                    console.log('[AutoLogin] Không có secret 2FA!');
                    return;
                }
                const { code, source } = await getTOTPCode(account.totp_secret);
                updateMainStatus('🔢 ' + (source === 'api' ? 'API' : 'Local') + ' TOTP: <b style="color:#4caf50;font-size:20px;letter-spacing:4px">' + code + '</b>');
                
                const input = await waitForElement(
                    '#_r_4_-code, input[name="code"], input[autocomplete="one-time-code"], input[inputmode="numeric"]',
                    8000
                );
                await sleep(600);
                setInputValue(input, code);
                updateMainStatus('<span style="color:#4a90e2">🔄 Đã nhập mã <b>' + code + '</b>, đang click...</span>');
                await sleep(600);
                const btn = document.querySelector(
                    'button[data-dd-action-name="Continue"], button[name="intent"][value="verify"], button[type="submit"]'
                );
                if (btn) { btn.click(); updateMainStatus('<span style="color:#4caf50">✓ Xong! Đang đăng nhập...</span>'); }
            } catch(e) { console.log('[AutoLogin] Lỗi nhập 2FA:', e.message); }
        }

        if (hostname === 'chatgpt.com') {
            if (document.querySelector('[data-testid="profile-button"]')) return;
            const emailInput = document.querySelector('input[type="email"], input[autocomplete="email"]');
            if (emailInput) {
                await step2_EnterEmail();
            } else {
                await step1_ClickLogin();
                await sleep(1500);
                await step2_EnterEmail();
            }
        } else if (hostname === 'auth.openai.com') {
            if (pathname.includes('/log-in/password'))              await step3_EnterPassword();
            else if (pathname.includes('/mfa-challenge'))           await step4_Enter2FA();
            else if (pathname.includes('/log-in'))                  await step2_EnterEmail();
        }
    }

    // =============================================
    //  FLOATING PANEL — Góc trên bên TRÁI
    // =============================================
    function injectFloatingPanel() {
        if (document.getElementById('__alp__')) return;

        const div = document.createElement('div');
        div.id = '__alp__';
        div.style.cssText = [
            'position:fixed',
            'top:14px',
            'left:14px',
            'z-index:2147483647',
            'background:linear-gradient(135deg,#1a1a2e,#16213e)',
            'border:1px solid #2a3a5a',
            'border-radius:14px',
            'padding:12px 14px 12px',
            'width:290px',
            'box-shadow:0 8px 32px rgba(0,0,0,0.55)',
            'font-family:-apple-system,BlinkMacSystemFont,Inter,sans-serif',
        ].join(';');

        div.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
                <div style="display:flex;align-items:center;gap:7px;">
                    <span style="font-size:15px;">🔐</span>
                    <span style="font-size:13px;font-weight:700;color:#e0e8ff;">Auto Login</span>
                </div>
                <button id="__alp_x__" style="background:none;border:none;color:#6677aa;cursor:pointer;font-size:16px;line-height:1;padding:0 4px;">−</button>
            </div>
            <div id="__alp_b__">
                <textarea id="__alp_ta__"
                    placeholder="Paste: email&#9;pass&#9;secret2fa"
                    spellcheck="false"
                    style="width:100%;height:58px;background:#0b0b18;border:1.5px solid #252540;border-radius:10px;padding:9px 11px;font-size:11.5px;color:#c8d8f0;font-family:monospace;outline:none;resize:none;line-height:1.5;box-sizing:border-box;"></textarea>
                <div id="__alp_s__" style="font-size:11px;color:#4477aa;margin:6px 2px 8px;min-height:16px;line-height:1.5;"></div>
                <button id="__alp_btn__" style="width:100%;padding:9px;background:linear-gradient(135deg,#4a90e2,#7b5ea7);color:#fff;border:none;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;letter-spacing:0.3px;">▶ Bắt đầu đăng nhập</button>
            </div>
        `;
        document.body.appendChild(div);

        const ta    = document.getElementById('__alp_ta__');
        const btn   = document.getElementById('__alp_btn__');
        const stat  = document.getElementById('__alp_s__');
        const tog   = document.getElementById('__alp_x__');
        const body  = document.getElementById('__alp_b__');
        let collapsed = false;

        tog.onclick = () => {
            collapsed = !collapsed;
            body.style.display = collapsed ? 'none' : 'block';
            tog.textContent = collapsed ? '+' : '−';
        };

        ta.onfocus = () => { ta.style.borderColor = '#4a90e2'; };
        ta.onblur  = () => { ta.style.borderColor = '#252540'; };
        btn.onmouseenter = () => { btn.style.opacity = '0.88'; };
        btn.onmouseleave = () => { btn.style.opacity = '1'; };

        // Hiển thị account đã lưu
        const acc = stored.chatgpt_account;
        if (acc && acc.email) {
            stat.innerHTML = '<span style="color:#4caf50;">✓ ' + acc.email + '</span>';
        } else {
            stat.innerHTML = '<span style="color:#f39c12;">⚠ Chưa có tài khoản</span>';
        }

        btn.onclick = async () => {
            const raw = ta.value.trim();
            let account = null;

            if (raw) {
                const parts = raw.split(/\t+|\s{2,}/);
                if (parts.length >= 2 && parts[0].includes('@')) {
                    account = {
                        email:       parts[0].trim(),
                        password:    parts[1].trim(),
                        totp_secret: (parts[2] || '').trim().toUpperCase().replace(/\s/g, '')
                    };
                    await chrome.storage.local.set({ chatgpt_account: account });
                    stat.innerHTML = '<span style="color:#4caf50;">✓ Đã lưu: ' + account.email + '</span>';
                } else {
                    stat.innerHTML = '<span style="color:#e74c3c;">✗ Sai định dạng! Cần: email  pass  secret</span>';
                    return;
                }
            } else {
                account = stored.chatgpt_account;
                if (!account || !account.email) {
                    stat.innerHTML = '<span style="color:#e74c3c;">✗ Chưa có TK. Paste vào ô trên!</span>';
                    return;
                }
            }

            btn.textContent = '⏳ Đang chạy...';
            btn.disabled = true;
            stat.innerHTML = '<span style="color:#4a90e2;">🔄 Đang đăng nhập: ' + account.email + '</span>';

            await startLoginFlow(account);

            btn.textContent = '▶ Bắt đầu đăng nhập';
            btn.disabled = false;
        };
    }


    function injectAuthPanel(statusMsg) {
        let div = document.getElementById('__alp_auth__');
        if (div) {
            document.getElementById('__alp_auth_s__').innerHTML = statusMsg;
            return;
        }
        div = document.createElement('div');
        div.id = '__alp_auth__';
        div.style.cssText = 'position:fixed;top:14px;left:14px;z-index:2147483647;background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #2a3a5a;border-radius:12px;padding:11px 14px;width:260px;box-shadow:0 6px 24px rgba(0,0,0,0.5);font-family:-apple-system,sans-serif;';
        div.innerHTML = `
            <div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;">
                <span style="font-size:14px;">🔐</span>
                <span style="font-size:12px;font-weight:700;color:#e0e8ff;">Auto Login</span>
            </div>
            <div id="__alp_auth_s__" style="font-size:11px;color:#7ab8e8;line-height:1.5;margin-bottom:8px;">${statusMsg}</div>
            <button id="__alp_auth_btn__" style="width:100%;padding:8px;background:linear-gradient(135deg,#4a90e2,#7b5ea7);color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;">▶ Chạy lại</button>
        `;
        document.body.appendChild(div);

        document.getElementById('__alp_auth_btn__').onclick = async () => {
            currentAuthStep = ''; // Reset state
            const freshStored = await chrome.storage.local.get(['chatgpt_account']);
            const acc = freshStored.chatgpt_account;
            if (!acc || !acc.email) {
                document.getElementById('__alp_auth_s__').innerHTML = '<span style="color:#e74c3c">✗ Chưa có tài khoản!</span>';
                return;
            }
            document.getElementById('__alp_auth_btn__').textContent = '⏳ Đang chạy...';
            document.getElementById('__alp_auth_btn__').disabled = true;
            await handleAuthStep(acc);
            document.getElementById('__alp_auth_btn__').textContent = '▶ Chạy lại';
            document.getElementById('__alp_auth_btn__').disabled = false;
        };
    }

    function updateAuthStatus(msg) {
        const el = document.getElementById('__alp_auth_s__');
        if (el) el.innerHTML = msg;
        console.log('[AutoLogin Auth]', msg.replace(/<[^>]+>/g,''));
    }

    // Logic SPA routing dựa vào DOM thay vì URL
    let currentAuthStep = '';
    let isProcessing = false;
    
    async function handleAuthDOM(account) {
        if (isProcessing) return;

        const mfaInput = document.querySelector('input[autocomplete="one-time-code"], input[name="code"], input[inputmode="numeric"]');
        const passInput = document.querySelector('input[type="password"], input[name="current-password"]');
        const emailInput = document.querySelector('input[type="email"], input[name="username"]');

        if (mfaInput && currentAuthStep !== 'mfa') {
            isProcessing = true;
            currentAuthStep = 'mfa';
            injectAuthPanel('<span style="color:#4a90e2">🔄 Đang lấy mã 2FA...</span>');
            try {
                if (!account.totp_secret) {
                    updateAuthStatus('<span style="color:#e74c3c">✗ Chưa có secret 2FA!</span>');
                    isProcessing = false;
                    return;
                }
                const { code, source } = await getTOTPCode(account.totp_secret);
                updateAuthStatus('🔢 ' + (source === 'api' ? 'API' : 'Local') + ' TOTP: <b style="color:#4caf50;font-size:20px;letter-spacing:4px">' + code + '</b>');

                await sleep(500);
                await simulateTyping(mfaInput, code);
                updateAuthStatus('<span style="color:#4a90e2">🔄 Đã nhập <b>' + code + '</b>, đang click...</span>');
                await sleep(600);
                const btn = document.querySelector(
                    'button[data-dd-action-name="Continue"], button[name="intent"][value="verify"], button[type="submit"]'
                );
                if (btn) { btn.click(); updateAuthStatus('<span style="color:#4caf50">✓ Đã click Continue!</span>'); }
            } catch(e) { updateAuthStatus('<span style="color:#e74c3c">✗ Lỗi 2FA: ' + e.message + '</span>'); }
            isProcessing = false;

        } else if (passInput && currentAuthStep !== 'password') {
            isProcessing = true;
            currentAuthStep = 'password';
            injectAuthPanel('<span style="color:#4a90e2">🔄 Đang nhập mật khẩu...</span>');
            try {
                await sleep(500);
                await simulateTyping(passInput, account.password);
                updateAuthStatus('<span style="color:#4a90e2">🔄 Đã nhập pass, đang click...</span>');
                await sleep(400);
                const btn = document.querySelector('button[type="submit"], button[name="intent"][value="validate"]');
                if (btn) { btn.click(); updateAuthStatus('<span style="color:#4caf50">✓ Đã click Continue!</span>'); }
            } catch(e) { updateAuthStatus('<span style="color:#e74c3c">✗ Lỗi pass: ' + e.message + '</span>'); }
            isProcessing = false;

        } else if (emailInput && currentAuthStep !== 'email' && window.location.pathname.includes('/log-in')) {
            isProcessing = true;
            currentAuthStep = 'email';
            injectAuthPanel('<span style="color:#4a90e2">🔄 Đang nhập email...</span>');
            try {
                await sleep(500);
                await simulateTyping(emailInput, account.email);
                updateAuthStatus('<span style="color:#4a90e2">🔄 Đã nhập email, đang click...</span>');
                await sleep(400);
                const btn = document.querySelector('button[type="submit"], button[data-dd-action-name="Continue"]');
                if (btn) btn.click();
            } catch(e) {}
            isProcessing = false;
        }
    }

    // Nút chạy lại trên auth panel
    document.addEventListener('click', async (e) => {
        if (e.target && e.target.id === '__alp_auth_btn__') {
            currentAuthStep = ''; // Reset state
            const freshStored = await chrome.storage.local.get(['chatgpt_account']);
            const acc = freshStored.chatgpt_account;
            if (!acc || !acc.email) {
                updateAuthStatus('<span style="color:#e74c3c">✗ Chưa có tài khoản!</span>');
                return;
            }
            e.target.textContent = '⏳ Đang chạy...';
            e.target.disabled = true;
            isProcessing = false;
            await handleAuthDOM(acc);
            e.target.textContent = '▶ Chạy lại';
            e.target.disabled = false;
        }
    });

    // =============================================
    //  BOOTSTRAP
    // =============================================
    const ACCOUNT = stored.chatgpt_account;

    if (hostname === 'chatgpt.com') {
        if (document.body) injectFloatingPanel();
        else document.addEventListener('DOMContentLoaded', injectFloatingPanel);
        
        // Tự động kiểm tra đăng nhập & click nút Upgrade Plus
        setInterval(() => {
            // Kiểm tra xem đã đăng nhập chưa (dựa vào nút profile)
            const isLoggedIn = document.querySelector('[data-testid="profile-button"]');
            
            // 1. Tự động chuyển trang Promo nếu đã đăng nhập và chưa ở trang đó
            if (isLoggedIn && window.location.pathname === '/' && !window.location.search.includes('promo_campaign')) {
                if (!window.__alp_is_redirecting) {
                    window.__alp_is_redirecting = true; // Tránh gọi setTimeout nhiều lần
                    console.log('[AutoLogin] Đã đăng nhập thành công, chờ 3s để sang trang Promo...');
                    updateMainStatus('<span style="color:#4a90e2">🔄 Đã đăng nhập, đợi 3s để sang form mua...</span>');
                    setTimeout(() => {
                        window.location.href = 'https://chatgpt.com/?promo_campaign=plus-1-month-free#pricing';
                    }, 3000);
                }
            }

            // 2. Tự động click nút Claim free offer / Upgrade Plus nếu nó xuất hiện
            const upgradeBtn = document.querySelector('[data-testid="select-plan-button-plus-upgrade"]');
            if (upgradeBtn && !upgradeBtn.hasAttribute('data-auto-clicked')) {
                upgradeBtn.setAttribute('data-auto-clicked', 'true');
                console.log('[AutoLogin] Đã tìm thấy nút Upgrade Plus, tự động click...');
                updateMainStatus('<span style="color:#4caf50">✓ Đang tự động click Upgrade...</span>');
                upgradeBtn.click();
            }
        }, 1000);

    } else if (hostname === 'auth.openai.com') {
        if (ACCOUNT && ACCOUNT.email) {
            // Quét DOM mỗi 800ms để tìm xem có ô input của bước nào xuất hiện không
            setInterval(() => handleAuthDOM(ACCOUNT), 800);
        } else {
            if (document.body) injectAuthPanel('<span style="color:#f39c12">⚠ Chưa có tài khoản. Mở Extension để nhập!</span>');
        }
    }


})();

