(function () {
    // Chỉ chạy ở trang Stripe Checkout của ChatGPT hoặc iframe Stripe
    const isStripe = window.location.hostname === 'js.stripe.com';
    const isCheckout = window.location.hostname === 'chatgpt.com';
    if (!isStripe && !isCheckout) return;

    // ─── Random data helpers ──────────────────────────────────────────────────
    function getRandomName() {
        const firstNames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Đoàn", "Lâm", "Trịnh", "Mai", "Đào"];
        const middleNames = ["Văn", "Thị", "Thanh", "Minh", "Hữu", "Đức", "Ngọc", "Gia", "Bảo", "Thu", "Hồng", "Hoàng", "Thành", "Đình", "Quang", "Trọng", "Tuấn", "Lan", "Phương", "Khánh", "Xuân"];
        const lastNames = ["Anh", "Bình", "Châu", "Dương", "Giang", "Hải", "Khang", "Linh", "Nhung", "Phương", "Quân", "Sơn", "Trang", "Vy", "Tuấn", "Long", "Cường", "Hùng", "Tùng", "Khoa", "Kiên", "Hiếu", "Nam", "Phúc", "Tâm", "Hương", "Hà", "Yến", "Thảo", "My", "Nhi", "Đạt", "Huy", "Tiến"];
        const r = a => a[Math.floor(Math.random() * a.length)];
        return r(firstNames) + ' ' + r(middleNames) + ' ' + r(lastNames);
    }

    function getRandomAddress1() {
        const streets = [
            "Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Hai Bà Trưng", "Đồng Khởi",
            "Lý Tự Trọng", "Nguyễn Đình Chiểu", "Pasteur", "Lê Duẩn", "Nguyễn Thị Minh Khai",
            "Điện Biên Phủ", "Cách Mạng Tháng Tám", "Nguyễn Trãi", "Võ Văn Tần", "Trương Định",
            "Bà Huyện Thanh Quan", "Nguyễn Bỉnh Khiêm", "Lê Thánh Tôn", "Tôn Đức Thắng", "Hàm Nghi",
            "Võ Thị Sáu", "Nam Kỳ Khởi Nghĩa", "Phan Đăng Lưu", "Bạch Đằng", "Đinh Tiên Hoàng",
            "Hoàng Hoa Thám", "Quang Trung", "Nguyễn Oanh", "Phạm Văn Đồng", "Mai Chí Thọ",
            "Trần Phú", "Kim Mã", "Cầu Giấy", "Hoàng Diệu", "Phan Đình Phùng", "Xã Đàn"
        ];
        const number = Math.floor(Math.random() * 999) + 1;
        return 'So ' + number + ' ' + streets[Math.floor(Math.random() * streets.length)];
    }

    function getRandomCity() {
        const cities = [
            "Ha Noi", "Ho Chi Minh", "Da Nang", "Hai Phong", "Can Tho",
            "Nha Trang", "Hue", "Vung Tau", "Bien Hoa", "Da Lat",
            "Buon Ma Thuot", "Vinh", "Thanh Hoa", "Ha Long", "Thai Nguyen",
            "Viet Tri", "Quy Nhon", "Phan Thiet", "Ca Mau", "Long Xuyen",
            "Rach Gia", "My Tho", "Tan An", "Pleiku", "Bac Ninh", "Hai Duong"
        ];
        return cities[Math.floor(Math.random() * cities.length)];
    }

    function getRandomZip() {
        const zips = ["100000", "700000", "550000", "180000", "900000", "650000", "530000", "790000", "810000", "670000", "260000", "430000", "400000", "200000", "250000"];
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
        // Helper nhận diện các trường input chính xác, tránh nhầm lẫn giữa Tên và Địa chỉ
        function isNameInput(el) {
            if (!el || el.tagName !== 'INPUT' || el.type === 'hidden' || el.type === 'checkbox' || el.type === 'radio') return false;
            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
            const stable = (el.getAttribute('data-elements-stable-field-name') || '').toLowerCase();

            // Nếu trường chứa các từ khóa địa chỉ/city/zip thì chắc chắn không phải Tên
            if (id.includes('line1') || id.includes('line2') || id.includes('city') || id.includes('locality') || id.includes('postal') || id.includes('zip')) return false;
            if (name.includes('line1') || name.includes('line2') || name.includes('city') || name.includes('locality') || name.includes('postal') || name.includes('zip')) return false;

            if (stable === 'billingname') return true;
            if (ac === 'name' || ac.includes('cc-name') || ac.includes('given-name')) return true;
            if (id.includes('billingname') || id.endsWith('-name') || id.endsWith('_name') || id === 'name') return true;
            if (name === 'name' || name === 'billingname') return true;
            if (ph.includes('tên trên thẻ') || ph.includes('họ và tên') || ph.includes('full name') || ph.includes('cardholder name')) return true;
            if ((ph.includes('name') || ph.includes('tên')) && !ph.includes('address') && !ph.includes('địa chỉ')) return true;
            return false;
        }

        function isAddress1Input(el, nameEl) {
            if (!el || el.tagName !== 'INPUT' || el.type === 'hidden' || el.type === 'checkbox' || el.type === 'radio') return false;
            if (nameEl && el === nameEl) return false; // Tuyệt đối không trùng ô Tên
            if (isNameInput(el)) return false; // Không lấy ô Tên làm Địa chỉ

            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
            const stable = (el.getAttribute('data-elements-stable-field-name') || '').toLowerCase();

            // Loại trừ dòng 2, city, zip, state
            if (id.includes('line2') || id.includes('address2') || name.includes('line2') || name.includes('address2')) return false;
            if (id.includes('locality') || id.includes('city') || id.includes('postal') || id.includes('zip') || id.includes('state')) return false;
            if (name.includes('locality') || name.includes('city') || name.includes('postal') || name.includes('zip')) return false;

            if (stable === 'addressline1' || stable === 'billingaddressline1') return true;
            if (ac === 'address-line1' || ac === 'street-address') return true;
            if (id.includes('addressline1') || id.includes('address-line1') || id.includes('billingaddressline1') || id.includes('billingaddress-addressline1') || id.includes('line1') || id.includes('address1')) return true;
            if (name.includes('addressline1') || name.includes('address-line1') || name.includes('address1') || name.includes('line1') || name === 'address') return true;
            if (ph.includes('address line 1') || ph.includes('địa chỉ dòng 1') || ph.includes('địa chỉ 1') || ph.includes('street address')) return true;
            // Stripe Address autocomplete / fallback
            if (id.includes('billingaddress') && !id.includes('name') && !id.includes('line2')) return true;
            if ((ph.includes('address') || ph.includes('địa chỉ')) && !ph.includes('name') && !ph.includes('tên') && !ph.includes('line 2') && !ph.includes('dòng 2')) return true;

            return false;
        }

        function isCityInput(el, excludeList) {
            if (!el || el.tagName !== 'INPUT') return false;
            if (excludeList && excludeList.includes(el)) return false;
            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
            const stable = (el.getAttribute('data-elements-stable-field-name') || '').toLowerCase();

            if (ac === 'address-level2' || stable === 'locality' || stable === 'billinglocality') return true;
            if (id.includes('locality') || id.includes('city')) return true;
            if (name.includes('locality') || name.includes('city')) return true;
            if (ph.includes('city') || ph.includes('thành phố')) return true;
            return false;
        }

        // 1. Kiểm tra xem ô địa chỉ đã có chưa, nếu chưa có và có nút "Enter address manually" thì click mở
        const inputs = Array.from(document.querySelectorAll('input'));
        let nameInput = inputs.find(isNameInput);
        let addrInput = inputs.find(el => isAddress1Input(el, nameInput));

        if (!addrInput) {
            const manualBtn = Array.from(document.querySelectorAll('button:not([type="submit"]):not([form]), a, [role="button"]:not([type="submit"])')).find(el => {
                const txt = (el.textContent || el.innerText || '').trim().toLowerCase();
                const isManual = txt.includes('address manually') || txt.includes('nhập địa chỉ thủ công') || txt.includes('manually') || txt.includes('thủ công');
                const isSubmit = el.type === 'submit' || el.hasAttribute('form') || /mua gói|subscribe|pay|thanh toán|bắt đầu|start trial|upgrade/i.test(txt);
                return isManual && !isSubmit;
            });
            if (manualBtn && manualBtn.offsetParent !== null) {
                console.log('[AutoFill] Tìm thấy nút Enter address manually, đang click mở ô nhập...');
                manualBtn.click();
                await new Promise(r => setTimeout(r, 600));
            }
        }

        // Lấy lại danh sách inputs sau khi mở thủ công (nếu có)
        const updatedInputs = Array.from(document.querySelectorAll('input'));
        nameInput = updatedInputs.find(isNameInput);
        addrInput = updatedInputs.find(el => isAddress1Input(el, nameInput));
        const cityInput = updatedInputs.find(el => isCityInput(el, [nameInput, addrInput]));

        const stateSelect = document.querySelector(
            'select[name="administrativeArea"], select[name="state"], select[autocomplete*="address-level1"], select[id*="administrativeArea" i], select[id*="state" i]'
        );

        if (!nameInput && !addrInput && !cityInput) {
            return;
        }

        isFilling = true;
        try {
            console.log('[AutoFill] Tìm thấy ô nhập liệu Stripe trên frame (' + window.location.pathname + '), bắt đầu điền...');

            // 1. Họ và tên (Chỉ nhập vào ô Tên)
            if (nameInput && (!nameInput.value || forceRefill)) {
                console.log('[AutoFill] Điền Tên vào ô:', nameInput.id || nameInput.name);
                await simulateTyping(nameInput, getRandomName());
                await new Promise(r => setTimeout(r, 250));
            }

            // 2. Địa chỉ dòng 1 (Chỉ nhập vào ô Address Line 1)
            if (addrInput && (!addrInput.value || forceRefill)) {
                console.log('[AutoFill] Điền Địa chỉ dòng 1 vào ô:', addrInput.id || addrInput.name);
                await simulateTyping(addrInput, getRandomAddress1());
                await new Promise(r => setTimeout(r, 350));
            }

            // 3. Thành phố (Chỉ nhập vào ô City)
            const cInput = cityInput || Array.from(document.querySelectorAll('input')).find(el => isCityInput(el, [nameInput, addrInput]));
            if (cInput && (!cInput.value || forceRefill)) {
                console.log('[AutoFill] Điền Thành phố vào ô:', cInput.id || cInput.name);
                await simulateTyping(cInput, getRandomCity());
                await new Promise(r => setTimeout(r, 250));
            }

            // 4. BỎ HẲN ĐIỀN Ô ZIP CODE THEO YÊU CẦU:
            // Tránh việc Stripe/ChatGPT nhận diện form hoàn tất 100% rồi tự động kích hoạt thanh toán.
            // Ô Zip code để người dùng tự gõ hoặc kiểm soát khi thanh toán.

            // 5. State dropdown (nếu có)
            const curStateSelect = stateSelect || document.querySelector(
                'select[name="administrativeArea"], select[name="state"], select[autocomplete*="address-level1"], select[id*="administrativeArea" i], select[id*="state" i]'
            );
            if (curStateSelect && (!curStateSelect.value || forceRefill)) {
                const opts = Array.from(curStateSelect.options).filter(o => o.value && !o.disabled);
                if (opts.length) {
                    const opt = opts[Math.floor(Math.random() * opts.length)];
                    curStateSelect.value = opt.value;
                    curStateSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    curStateSelect.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }

            console.log('[AutoFill] Đã điền xong thông tin (Tên, Địa chỉ 1, Thành phố). Đã bỏ qua ô Zip. Dừng lại, không bấm nút thanh toán.');
            try {
                window.top.postMessage({ type: 'CHATGPT_AUTOFILL_DONE' }, '*');
            } catch (e) { }
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
                try { f.contentWindow.postMessage({ type: 'CHATGPT_AUTOFILL_REFILL' }, '*'); } catch (e) { }
            });
        } catch (e) { }
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
            let hasInitCheckout = false;
            const checkAndInit = () => {
                if (hasInitCheckout) return true;
                const hasStripe = document.querySelector('iframe[src*="stripe.com"], .StripeElement');
                if (hasStripe) {
                    hasInitCheckout = true;
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

            setTimeout(() => { checkAndInit(); }, 1200);
            setTimeout(() => { checkAndInit(); }, 3000);
        }
    }

    startObserver();

})();
