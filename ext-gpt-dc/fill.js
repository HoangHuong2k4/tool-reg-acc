(function() {
    // Chỉ chạy ở trang Stripe Checkout của ChatGPT hoặc iframe Stripe
    const isStripe   = window.location.hostname === 'js.stripe.com';
    const isCheckout = window.location.hostname === 'chatgpt.com';
    if (!isStripe && !isCheckout) return;

    // ─── Random data helpers ──────────────────────────────────────────────────
    function getRandomName() {
        const firstNames = ["Nguyễn","Trần","Lê","Phạm","Hoàng","Huỳnh","Phan","Vũ","Võ","Đặng","Bùi","Đỗ","Hồ","Ngô","Dương","Lý","Đinh","Đoàn","Lâm","Trịnh","Mai","Đào"];
        const middleNames = ["Văn","Thị","Thanh","Minh","Hữu","Đức","Ngọc","Gia","Bảo","Thu","Hồng","Hoàng","Thành","Đình","Quang","Trọng","Tuấn","Lan","Phương","Khánh","Xuân"];
        const lastNames = ["Anh","Bình","Châu","Dương","Giang","Hải","Khang","Linh","Nhung","Phương","Quân","Sơn","Trang","Vy","Tuấn","Long","Cường","Hùng","Tùng","Khoa","Kiên","Hiếu","Nam","Phúc","Tâm","Hương","Hà","Yến","Thảo","My","Nhi","Đạt","Huy","Tiến"];
        const r = a => a[Math.floor(Math.random() * a.length)];
        return r(firstNames) + ' ' + r(middleNames) + ' ' + r(lastNames);
    }

    function getRandomAddress1() {
        const streets = [
            "Nguyễn Huệ","Lê Lợi","Trần Hưng Đạo","Hai Bà Trưng","Đồng Khởi",
            "Lý Tự Trọng","Nguyễn Đình Chiểu","Pasteur","Lê Duẩn","Nguyễn Thị Minh Khai",
            "Điện Biên Phủ","Cách Mạng Tháng Tám","Nguyễn Trãi","Võ Văn Tần","Trương Định",
            "Bà Huyện Thanh Quan","Nguyễn Bỉnh Khiêm","Lê Thánh Tôn","Tôn Đức Thắng","Hàm Nghi",
            "Võ Thị Sáu","Nam Kỳ Khởi Nghĩa","Phan Đăng Lưu","Bạch Đằng","Đinh Tiên Hoàng",
            "Hoàng Hoa Thám","Quang Trung","Nguyễn Oanh","Phạm Văn Đồng","Mai Chí Thọ",
            "Trần Phú","Kim Mã","Cầu Giấy","Hoàng Diệu","Phan Đình Phùng","Xã Đàn"
        ];
        const number = Math.floor(Math.random() * 999) + 1;
        return 'So ' + number + ' ' + streets[Math.floor(Math.random() * streets.length)];
    }

    function getRandomCity() {
        const cities = [
            "Ha Noi","Ho Chi Minh","Da Nang","Hai Phong","Can Tho",
            "Nha Trang","Hue","Vung Tau","Bien Hoa","Da Lat",
            "Buon Ma Thuot","Vinh","Thanh Hoa","Ha Long","Thai Nguyen",
            "Viet Tri","Quy Nhon","Phan Thiet","Ca Mau","Long Xuyen",
            "Rach Gia","My Tho","Tan An","Pleiku","Bac Ninh","Hai Duong"
        ];
        return cities[Math.floor(Math.random() * cities.length)];
    }

    function getRandomZip() {
        const zips = ["100000","700000","550000","180000","900000","650000","530000","790000","810000","670000","260000","430000","400000","200000","250000"];
        return zips[Math.floor(Math.random() * zips.length)];
    }

    // ─── Simulate human typing (triggers React/Stripe events) ─────────────────
    async function simulateTyping(element, text) {
        if (!element) return;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        element.focus();
        if (setter) setter.call(element, '');
        else element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 60));
        for (let i = 0; i < text.length; i++) {
            const val = text.slice(0, i + 1);
            if (setter) setter.call(element, val);
            else element.value = val;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            await new Promise(r => setTimeout(r, Math.random() * 30 + 15));
        }
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.blur();
    }

    // ─── CHỐNG TỰ ĐỘNG BẤM / SUBMIT NÚT THANH TOÁN (SUBSCRIBE / MUA GÓI) ───
    // Tuyệt đối không để bất kỳ script hoặc hành vi giả lập nào tự động bấm nút mua / submit
    function installSubmitProtector() {
        // Chặn submit tự động trên form
        window.addEventListener('submit', (e) => {
            if (!e.isTrusted || isFilling) {
                console.warn('[AutoFill Block] Đã chặn submit form tự động:', e.target);
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            }
        }, true);

        // Chặn click tự động vào các nút Mua gói / Subscribe / Submit
        window.addEventListener('click', (e) => {
            const target = e.target;
            const btn = (target && target.closest) ? target.closest(
                'button[type="submit"], button[form], button.button-uUalnz, button[aria-label*="Subscribe" i], button[aria-label*="Mua gói" i], button[data-testid*="submit" i]'
            ) : null;
            if (btn) {
                // Nếu click giả lập (script click / dispatchEvent, isTrusted === false) hoặc đang fill
                if (!e.isTrusted || isFilling) {
                    console.warn('[AutoFill Block] Đã chặn click tự động vào nút thanh toán:', btn);
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    return false;
                }
            }
        }, true);
    }
    installSubmitProtector();

    // ─── Core fill logic — KHONG click / KHONG submit bat ky nut nao ──────────
    let isFilling = false;
    let floatStatusEl = null;

    function updateFloatingStatus(msg) {
        if (floatStatusEl) floatStatusEl.textContent = msg;
    }

    async function autoFillForm(forceRefill) {
        if (isFilling) return;

        // Nếu đang ở frame chính chatgpt.com -> Broadcast lệnh fill xuống tất cả các iframe Stripe
        if (isCheckout && !isStripe) {
            updateFloatingStatus('Đang gửi lệnh điền...');
            broadcastRefill();
            return;
        }

        // Đang ở iframe Stripe (js.stripe.com)
        // 1. Thử click nút "Enter address manually" nếu có (TUYỆT ĐỐI không click bất kỳ nút submit, Mua gói hay Subscribe nào)
        const manualBtn = Array.from(document.querySelectorAll('button:not([type="submit"]):not([form]), a, [role="button"]:not([type="submit"])')).find(el => {
            const txt = (el.textContent || el.innerText || '').trim().toLowerCase();
            const isManual = txt.includes('manually') || txt.includes('thủ công') || txt === 'manual';
            const isSubmit = el.type === 'submit' || el.hasAttribute('form') || /mua gói|subscribe|pay|thanh toán/i.test(txt);
            return isManual && !isSubmit;
        });
        if (manualBtn && manualBtn.offsetParent !== null) {
            console.log('[AutoFill] Tìm thấy nút Enter address manually, đang click mở ô nhập...');
            manualBtn.click();
            await new Promise(r => setTimeout(r, 600));
        }

        const SEL_NAME = [
            'input[name="name"]',
            'input[autocomplete="name"]',
            'input[id*="billingName"]',
            'input[data-elements-stable-field-name="billingName"]',
            'input[placeholder*="Name" i]',
            'input[placeholder*="Tên" i]'
        ].join(',');

        const SEL_ADDR = [
            'input[name="addressLine1"]',
            'input[name="address1"]',
            'input[name="address"]',
            'input[name="line1"]',
            'input[autocomplete="address-line1"]',
            'input[autocomplete="street-address"]',
            'input[id*="addressLine1"]',
            'input[id*="billingAddressLine1"]',
            'input[id*="address1"]',
            'input[id*="address" i]',
            'input[id*="line1" i]',
            'input[data-elements-stable-field-name="addressLine1"]',
            'input[placeholder*="Address" i]',
            'input[placeholder*="Địa chỉ" i]'
        ].join(',');

        const SEL_CITY = [
            'input[name="locality"]',
            'input[name="city"]',
            'input[autocomplete="address-level2"]',
            'input[id*="billingLocality"]',
            'input[id*="locality" i]',
            'input[id*="city" i]',
            'input[placeholder*="City" i]',
            'input[placeholder*="Thành phố" i]'
        ].join(',');

        const SEL_ZIP = [
            'input[name="postalCode"]',
            'input[name="postal_code"]',
            'input[name="zip"]',
            'input[autocomplete="postal-code"]',
            'input[id*="billingPostalCode"]',
            'input[id*="postal" i]',
            'input[id*="zip" i]',
            'input[placeholder*="Postal" i]',
            'input[placeholder*="ZIP" i]',
            'input[placeholder*="bưu chính" i]'
        ].join(',');

        const SEL_STATE = [
            'select[name="administrativeArea"]',
            'select[name="state"]',
            'select[autocomplete*="address-level1"]',
            'select[id*="billingAdministrativeArea"]',
            'select[id*="state" i]'
        ].join(',');

        const nameInput = document.querySelector(SEL_NAME);
        const addrInput = document.querySelector(SEL_ADDR);
        const cityInput = document.querySelector(SEL_CITY);
        const zipInput  = document.querySelector(SEL_ZIP);

        if (!nameInput && !addrInput && !cityInput && !zipInput) {
            return;
        }

        isFilling = true;
        try {
            console.log('[AutoFill] Tìm thấy ô nhập liệu Stripe trên frame (' + window.location.pathname + '), bắt đầu điền...');

            // 1. Tên (thường ở payment frame)
            if (nameInput && (!nameInput.value || forceRefill)) {
                await simulateTyping(nameInput, getRandomName());
                await new Promise(r => setTimeout(r, 300));
            }

            // 2. Địa chỉ dòng 1 (thường ở address frame)
            if (addrInput && (!addrInput.value || forceRefill)) {
                await simulateTyping(addrInput, getRandomAddress1());
                await new Promise(r => setTimeout(r, 600));

                // 3. Thành phố
                const cInput = document.querySelector(SEL_CITY);
                if (cInput && (!cInput.value || forceRefill)) {
                    await simulateTyping(cInput, getRandomCity());
                    await new Promise(r => setTimeout(r, 300));
                }

                // 4. Zip code
                const zInput = document.querySelector(SEL_ZIP);
                if (zInput && (!zInput.value || forceRefill)) {
                    await simulateTyping(zInput, getRandomZip());
                    await new Promise(r => setTimeout(r, 300));
                }

                // 5. State dropdown (nếu có)
                const stateSelect = document.querySelector(SEL_STATE);
                if (stateSelect && (!stateSelect.value || forceRefill)) {
                    const opts = Array.from(stateSelect.options).filter(o => o.value && !o.disabled);
                    if (opts.length) {
                        const opt = opts[Math.floor(Math.random() * opts.length)];
                        stateSelect.value = opt.value;
                        stateSelect.dispatchEvent(new Event('change', { bubbles: true }));
                        stateSelect.dispatchEvent(new Event('input',  { bubbles: true }));
                    }
                }
            }

            console.log('[AutoFill] Đã điền xong địa chỉ trên frame:', window.location.pathname, '-- TUYỆT ĐỐI KHÔNG click nút Mua gói / Subscribe.');
            try {
                window.top.postMessage({ type: 'CHATGPT_AUTOFILL_DONE' }, '*');
            } catch(e) {}
        } finally {
            isFilling = false;
        }
    }

    // ─── Broadcast helper (dành cho frame chính) ──────────────────────────────
    function broadcastRefill() {
        console.log('[AutoFill] Gửi lệnh refill tới tất cả iframe Stripe...');
        try {
            window.postMessage({ type: 'CHATGPT_AUTOFILL_REFILL' }, '*');
            document.querySelectorAll('iframe').forEach(f => {
                try { f.contentWindow.postMessage({ type: 'CHATGPT_AUTOFILL_REFILL' }, '*'); } catch (e) {}
            });
        } catch (e) {}
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ trigger_refill: Date.now() });
        }
    }

    // ─── Floating button "Doi dia chi" (chi inject o chatgpt.com) ─────────────
    function injectFloatingButton() {
        if (!isCheckout || document.getElementById('__af_float__')) return;

        const style = document.createElement('style');
        style.textContent = [
            '#__af_float__{position:fixed;bottom:18px;right:18px;z-index:2147483647;display:flex;flex-direction:column;align-items:flex-end;gap:7px;font-family:-apple-system,BlinkMacSystemFont,Inter,sans-serif}',
            '#__af_status__{background:rgba(15,25,45,0.92);border:1px solid #2a4a7a;color:#7ab8e8;font-size:11px;padding:5px 12px;border-radius:20px;max-width:240px;text-align:right;line-height:1.5;backdrop-filter:blur(6px)}',
            '#__af_btn__{background:linear-gradient(135deg,#1a4a8a,#4a3a8a);border:none;color:#fff;font-size:13px;font-weight:700;padding:11px 20px;border-radius:24px;cursor:pointer;box-shadow:0 4px 18px rgba(74,58,138,0.55);transition:transform .15s,box-shadow .15s,opacity .15s;letter-spacing:.3px;font-family:inherit}',
            '#__af_btn__:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(74,58,138,0.75)}',
            '#__af_btn__:active{transform:translateY(0);opacity:.8}',
            '#__af_btn__:disabled{opacity:.5;cursor:not-allowed;transform:none}'
        ].join('');
        document.head.appendChild(style);

        const wrap = document.createElement('div');
        wrap.id = '__af_float__';

        const statusDiv = document.createElement('div');
        statusDiv.id = '__af_status__';
        statusDiv.textContent = 'Sẵn sàng điền địa chỉ';
        floatStatusEl = statusDiv;

        const btn = document.createElement('button');
        btn.id = '__af_btn__';
        btn.textContent = '\uD83D\uDD04 Đổi địa chỉ';
        btn.title = 'Điền ngẫu nhiên địa chỉ mới vào form Stripe Checkout (không tự bấm nút thanh toán)';

        btn.onclick = () => {
            btn.disabled = true;
            broadcastRefill();
            updateFloatingStatus('Đang gửi lệnh điền...');
            setTimeout(() => { btn.disabled = false; }, 1500);
        };

        wrap.appendChild(statusDiv);
        wrap.appendChild(btn);
        document.body.appendChild(wrap);
        console.log('[AutoFill] Đã inject nút "Đổi địa chỉ" vào trang checkout.');
    }

    // ─── Listeners cho lệnh đổi địa chỉ từ login.js / popup.js ──────────────────
    window.addEventListener('message', (e) => {
        if (e.data && e.data.type === 'CHATGPT_AUTOFILL_REFILL') {
            if (isStripe) {
                console.log('[AutoFill] Nhận lệnh refill qua postMessage (Stripe frame)');
                autoFillForm(true);
            }
        } else if (e.data && e.data.type === 'CHATGPT_AUTOFILL_DONE') {
            updateFloatingStatus('Đã điền xong địa chỉ!');
        }
    });

    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.onChanged) {
        chrome.storage.onChanged.addListener((changes, area) => {
            if (area === 'local' && changes.trigger_refill) {
                if (isStripe) {
                    console.log('[AutoFill] Nhận lệnh refill qua storage (Stripe frame)');
                    autoFillForm(true);
                }
            }
        });
    }

    // ─── Khởi động ─────────────────────────────────────────────────────────────
    function startObserver() {
        if (isStripe) {
            // Trong iframe Stripe: Kiểm tra và điền ngay khi form render
            const checkAndFill = () => {
                const SEL_CHECK = 'input[name="addressLine1"], input[name="address"], input[name="name"], input[id*="address"], input[id*="billing"]';
                if (document.querySelector(SEL_CHECK)) {
                    autoFillForm(false);
                    return true;
                }
                return false;
            };

            const obs = new MutationObserver(() => {
                if (checkAndFill()) obs.disconnect();
            });
            if (document.body) obs.observe(document.body, { childList: true, subtree: true });

            // Kiểm tra định kỳ 400ms trong 6 giây đầu
            let attempts = 0;
            const timer = setInterval(() => {
                attempts++;
                if (checkAndFill() || attempts >= 15) {
                    clearInterval(timer);
                    obs.disconnect();
                }
            }, 400);

        } else if (isCheckout) {
            // Trên trang chính chatgpt.com
            const checkAndInit = () => {
                const hasStripe = document.querySelector('iframe[src*="stripe.com"], .StripeElement');
                if (hasStripe) {
                    injectFloatingButton();
                    broadcastRefill();
                    return true;
                }
                return false;
            };

            const obs = new MutationObserver(() => {
                if (checkAndInit()) obs.disconnect();
            });
            if (document.body) obs.observe(document.body, { childList: true, subtree: true });

            setTimeout(() => {
                checkAndInit();
            }, 1200);
            setTimeout(() => {
                checkAndInit();
            }, 3000);
        }
    }

    startObserver();

})();
