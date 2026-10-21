(function () {
    // Chỉ chạy ở trang Stripe Checkout của ChatGPT hoặc iframe Stripe
    const isStripe = window.location.hostname === 'js.stripe.com';
    const isCheckout = window.location.hostname === 'chatgpt.com';
    if (!isStripe && !isCheckout) return;

    // ─── Danh sách địa chỉ Việt Nam chuẩn và đồng bộ ───────────────────────────
    const VN_LOCATIONS = [
        { city: "Ha Noi", state: "Ha Noi", zip: "100000" },
        { city: "Ho Chi Minh", state: "Ho Chi Minh", zip: "700000" },
        { city: "Da Nang", state: "Da Nang", zip: "550000" },
        { city: "Hai Phong", state: "Hai Phong", zip: "180000" },
        { city: "Can Tho", state: "Can Tho", zip: "900000" },
        { city: "Nha Trang", state: "Khanh Hoa", zip: "650000" },
        { city: "Hue", state: "Thua Thien Hue", zip: "530000" },
        { city: "Vung Tau", state: "Ba Ria - Vung Tau", zip: "790000" },
        { city: "Bien Hoa", state: "Dong Nai", zip: "810000" },
        { city: "Da Lat", state: "Lam Dong", zip: "670000" },
        { city: "Buon Ma Thuot", state: "Dak Lak", zip: "630000" },
        { city: "Vinh", state: "Nghe An", zip: "460000" },
        { city: "Thanh Hoa", state: "Thanh Hoa", zip: "440000" },
        { city: "Ha Long", state: "Quang Ninh", zip: "200000" },
        { city: "Thai Nguyen", state: "Thai Nguyen", zip: "250000" },
        { city: "Quy Nhon", state: "Binh Dinh", zip: "590000" },
        { city: "Phan Thiet", state: "Binh Thuan", zip: "800000" },
        { city: "Bac Ninh", state: "Bac Ninh", zip: "220000" }
    ];

    const STREETS = [
        "Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Hai Bà Trưng", "Đồng Khởi",
        "Lý Tự Trọng", "Nguyễn Đình Chiểu", "Pasteur", "Lê Duẩn", "Nguyễn Thị Minh Khai",
        "Điện Biên Phủ", "Cách Mạng Tháng Tám", "Nguyễn Trãi", "Võ Văn Tần", "Trương Định",
        "Bà Huyện Thanh Quan", "Nguyễn Bỉnh Khiêm", "Lê Thánh Tôn", "Tôn Đức Thắng", "Hàm Nghi",
        "Võ Thị Sáu", "Nam Kỳ Khởi Nghĩa", "Phan Đăng Lưu", "Bạch Đằng", "Đinh Tiên Hoàng",
        "Hoàng Hoa Thám", "Quang Trung", "Nguyễn Oanh", "Phạm Văn Đồng", "Mai Chí Thọ",
        "Trần Phú", "Kim Mã", "Cầu Giấy", "Hoàng Diệu", "Phan Đình Phùng", "Xã Đàn"
    ];

    function generateRandomAddress() {
        const firstNames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Đoàn", "Lâm", "Trịnh", "Mai", "Đào"];
        const middleNames = ["Văn", "Thị", "Thanh", "Minh", "Hữu", "Đức", "Ngọc", "Gia", "Bảo", "Thu", "Hồng", "Hoàng", "Thành", "Đình", "Quang", "Trọng", "Tuấn", "Lan", "Phương", "Khánh", "Xuân"];
        const lastNames = ["Anh", "Bình", "Châu", "Dương", "Giang", "Hải", "Khang", "Linh", "Nhung", "Phương", "Quân", "Sơn", "Trang", "Vy", "Tuấn", "Long", "Cường", "Hùng", "Tùng", "Khoa", "Kiên", "Hiếu", "Nam", "Phúc", "Tâm", "Hương", "Hà", "Yến", "Thảo", "My", "Nhi", "Đạt", "Huy", "Tiến"];
        const r = a => a[Math.floor(Math.random() * a.length)];
        const fullName = r(firstNames) + ' ' + r(middleNames) + ' ' + r(lastNames);

        const number = Math.floor(Math.random() * 888) + 12;
        const street = STREETS[Math.floor(Math.random() * STREETS.length)];
        const address1 = 'So ' + number + ' ' + street;

        const loc = VN_LOCATIONS[Math.floor(Math.random() * VN_LOCATIONS.length)];
        return {
            name: fullName,
            address1: address1,
            city: loc.city,
            state: loc.state,
            zip: loc.zip
        };
    }

    // ─── Clipboard Helper an toàn ──────────────────────────────────────────────
    async function copyToClipboard(text) {
        if (!text) return false;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (err) {
                console.warn('[AutoFill] navigator.clipboard failed, using fallback', err);
            }
        }
        return fallbackCopy(text);
    }

    function fallbackCopy(text) {
        try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.top = '0';
            ta.style.left = '0';
            ta.style.opacity = '0';
            ta.style.pointerEvents = 'none';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            ta.setSelectionRange(0, text.length);
            const ok = document.execCommand('copy');
            document.body.removeChild(ta);
            return ok;
        } catch (e) {
            console.error('[AutoFill] Fallback copy error:', e);
            return false;
        }
    }

    // ─── Simulate human typing (chỉ kích hoạt khi bấm nút "Điền vào form") ──────
    async function simulateTyping(element, text) {
        if (!element || !text) return;
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
            await new Promise(r => setTimeout(r, Math.random() * 25 + 15));
        }
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.blur();
    }

    // ─── Core fill logic (CHỈ CHẠY KHI NGƯỜI DÙNG BẤM NÚT "ĐIỀN VÀO FORM") ──────
    let isFilling = false;

    async function autoFillForm(forceRefill, targetAddr) {
        if (isFilling) return;

        // Nếu không có địa chỉ truyền vào, lấy từ storage hoặc tạo mới
        let addr = targetAddr;
        if (!addr && typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            try {
                const res = await chrome.storage.local.get(['current_checkout_address']);
                addr = res.current_checkout_address;
            } catch (e) { }
        }
        if (!addr) addr = generateRandomAddress();

        function isNameInput(el) {
            if (!el || el.tagName !== 'INPUT' || el.type === 'hidden' || el.type === 'checkbox' || el.type === 'radio') return false;
            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
            const stable = (el.getAttribute('data-elements-stable-field-name') || '').toLowerCase();

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
            if (nameEl && el === nameEl) return false;
            if (isNameInput(el)) return false;

            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
            const ph = (el.getAttribute('placeholder') || '').toLowerCase();
            const stable = (el.getAttribute('data-elements-stable-field-name') || '').toLowerCase();

            if (id.includes('line2') || id.includes('address2') || name.includes('line2') || name.includes('address2')) return false;
            if (id.includes('locality') || id.includes('city') || id.includes('postal') || id.includes('zip') || id.includes('state')) return false;
            if (name.includes('locality') || name.includes('city') || name.includes('postal') || name.includes('zip')) return false;

            if (stable === 'addressline1' || stable === 'billingaddressline1') return true;
            if (ac === 'address-line1' || ac === 'street-address') return true;
            if (id.includes('addressline1') || id.includes('address-line1') || id.includes('billingaddressline1') || id.includes('billingaddress-addressline1') || id.includes('line1') || id.includes('address1')) return true;
            if (name.includes('addressline1') || name.includes('address-line1') || name.includes('address1') || name.includes('line1') || name === 'address') return true;
            if (ph.includes('address line 1') || ph.includes('địa chỉ dòng 1') || ph.includes('địa chỉ 1') || ph.includes('street address')) return true;
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

        const updatedInputs = Array.from(document.querySelectorAll('input'));
        nameInput = updatedInputs.find(isNameInput);
        addrInput = updatedInputs.find(el => isAddress1Input(el, nameInput));
        const cityInput = updatedInputs.find(el => isCityInput(el, [nameInput, addrInput]));

        const stateSelect = document.querySelector(
            'select[name="administrativeArea"], select[name="state"], select[autocomplete*="address-level1"], select[id*="administrativeArea" i], select[id*="state" i]'
        );

        if (!nameInput && !addrInput && !cityInput) return;

        isFilling = true;
        try {
            console.log('[AutoFill] Đang điền theo lệnh thủ công với dữ liệu:', addr);

            // 1. Họ và tên
            if (nameInput && (!nameInput.value || forceRefill)) {
                await simulateTyping(nameInput, addr.name);
                await new Promise(r => setTimeout(r, 200));
            }

            // 2. Địa chỉ dòng 1
            if (addrInput && (!addrInput.value || forceRefill)) {
                await simulateTyping(addrInput, addr.address1);
                await new Promise(r => setTimeout(r, 250));
            }

            // 3. Thành phố
            const cInput = cityInput || Array.from(document.querySelectorAll('input')).find(el => isCityInput(el, [nameInput, addrInput]));
            if (cInput && (!cInput.value || forceRefill)) {
                await simulateTyping(cInput, addr.city);
                await new Promise(r => setTimeout(r, 200));
            }

            // 4. Bang / Tỉnh (nếu có dropdown)
            const curStateSelect = stateSelect || document.querySelector(
                'select[name="administrativeArea"], select[name="state"], select[autocomplete*="address-level1"], select[id*="administrativeArea" i], select[id*="state" i]'
            );
            if (curStateSelect && (!curStateSelect.value || forceRefill)) {
                const opts = Array.from(curStateSelect.options).filter(o => o.value && !o.disabled);
                const matchedOpt = opts.find(o => o.text.toLowerCase().includes(addr.state.toLowerCase()) || o.value.toLowerCase().includes(addr.state.toLowerCase()));
                const chosen = matchedOpt || opts[0];
                if (chosen) {
                    curStateSelect.value = chosen.value;
                    curStateSelect.dispatchEvent(new Event('change', { bubbles: true }));
                    curStateSelect.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }

            try {
                window.top.postMessage({ type: 'CHATGPT_AUTOFILL_DONE' }, '*');
            } catch (e) { }
        } finally {
            isFilling = false;
        }
    }

    // ─── Broadcast helper (chỉ kích hoạt khi bấm nút "Điền vào form") ──────────
    function broadcastRefill(addr) {
        console.log('[AutoFill] Gửi lệnh refill thủ công tới Stripe iframe...');
        try {
            window.postMessage({ type: 'CHATGPT_AUTOFILL_REFILL', address: addr }, '*');
            document.querySelectorAll('iframe').forEach(f => {
                try { f.contentWindow.postMessage({ type: 'CHATGPT_AUTOFILL_REFILL', address: addr }, '*'); } catch (e) { }
            });
        } catch (e) { }
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ trigger_refill: Date.now(), current_checkout_address: addr });
        }
    }

    // ─── Floating Address Card (CHỈ HIỂN THỊ ĐỂ COPY DÁN BẰNG TAY) ────────────
    let currentAddress = null;

    async function injectAddressCard() {
        if (!isCheckout || window.top !== window) return;
        if (document.getElementById('__af_address_card__')) return;

        // Lấy hoặc tạo địa chỉ hiện tại
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            try {
                const res = await chrome.storage.local.get(['current_checkout_address']);
                if (res && res.current_checkout_address && res.current_checkout_address.name) {
                    currentAddress = res.current_checkout_address;
                }
            } catch (e) { }
        }
        if (!currentAddress) {
            currentAddress = generateRandomAddress();
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.set({ current_checkout_address: currentAddress });
            }
        }

        // CSS cho Card và Mini Badge
        const style = document.createElement('style');
        style.textContent = `
            #__af_address_card__ {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 2147483647;
                width: 320px;
                background: linear-gradient(145deg, #121422, #181d33);
                border: 1.5px solid #2d3f66;
                border-radius: 14px;
                box-shadow: 0 12px 36px rgba(0,0,0,0.7), 0 0 15px rgba(58,130,246,0.18);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                color: #e2e8f0;
                user-select: none;
                overflow: hidden;
                transition: transform 0.2s, opacity 0.2s;
            }
            #__af_card_header__ {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 10px 14px 8px;
                background: rgba(15, 20, 35, 0.7);
                border-bottom: 1px solid #23304a;
                cursor: grab;
            }
            #__af_card_header__:active { cursor: grabbing; }
            .af-card-title {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 13px;
                font-weight: 700;
                color: #fff;
            }
            .af-badge-off {
                font-size: 9px;
                font-weight: 700;
                padding: 2px 6px;
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid rgba(239, 68, 68, 0.4);
                color: #fca5a5;
                border-radius: 10px;
                letter-spacing: 0.5px;
            }
            .af-header-btns {
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .af-icon-btn {
                background: none;
                border: none;
                color: #8899bb;
                cursor: pointer;
                font-size: 16px;
                line-height: 1;
                padding: 2px 6px;
                border-radius: 4px;
                transition: color 0.15s, background 0.15s;
            }
            .af-icon-btn:hover { color: #fff; background: rgba(255,255,255,0.08); }
            #__af_card_body__ {
                padding: 10px 14px 12px;
                display: flex;
                flex-direction: column;
                gap: 7px;
            }
            .af-notice {
                font-size: 10px;
                color: #94a3b8;
                background: rgba(30, 41, 65, 0.6);
                border-left: 3px solid #38bdf8;
                padding: 5px 8px;
                border-radius: 4px;
                line-height: 1.4;
            }
            .af-field-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: #0d101d;
                border: 1px solid #1e2840;
                border-radius: 8px;
                padding: 5px 8px;
                gap: 6px;
                transition: border-color 0.15s;
            }
            .af-field-row:hover {
                border-color: #3b82f6;
            }
            .af-field-meta {
                display: flex;
                flex-direction: column;
                overflow: hidden;
                flex: 1;
                cursor: pointer;
            }
            .af-field-label {
                font-size: 9.5px;
                font-weight: 600;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.4px;
            }
            .af-field-val {
                font-size: 12px;
                font-weight: 600;
                color: #38bdf8;
                font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .af-copy-btn {
                background: #1a2744;
                border: 1px solid #2b4170;
                color: #7dd3fc;
                font-size: 10.5px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 6px;
                cursor: pointer;
                white-space: nowrap;
                transition: all 0.15s;
                font-family: inherit;
            }
            .af-copy-btn:hover {
                background: #233760;
                color: #fff;
                border-color: #38bdf8;
            }
            .af-copy-btn.copied {
                background: #14532d !important;
                border-color: #22c55e !important;
                color: #86efac !important;
            }
            .af-btn-group {
                display: flex;
                gap: 6px;
                margin-top: 4px;
            }
            .af-action-btn {
                flex: 1;
                padding: 7px 10px;
                border-radius: 8px;
                font-size: 11.5px;
                font-weight: 600;
                cursor: pointer;
                font-family: inherit;
                border: none;
                transition: transform 0.12s, opacity 0.15s, background 0.15s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 4px;
            }
            .af-action-btn:hover { transform: translateY(-1px); }
            .af-action-btn:active { transform: translateY(0); }
            .af-btn-refresh {
                background: linear-gradient(135deg, #1e3a8a, #3b82f6);
                color: #fff;
            }
            .af-btn-copyall {
                background: #1e293b;
                border: 1px solid #334155;
                color: #cbd5e1;
            }
            .af-btn-copyall:hover {
                background: #273549;
                color: #fff;
            }
            .af-btn-fill {
                background: #281a1a;
                border: 1px solid #552727;
                color: #fca5a5;
                padding: 5px 8px;
                font-size: 10.5px;
                opacity: 0.8;
            }
            .af-btn-fill:hover {
                opacity: 1;
                background: #3b2020;
            }
            #__af_card_mini__ {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 2147483647;
                display: none;
                align-items: center;
                gap: 7px;
                background: linear-gradient(135deg, #111827, #1e293b);
                border: 1.5px solid #3b82f6;
                border-radius: 24px;
                padding: 7px 14px;
                cursor: pointer;
                box-shadow: 0 4px 18px rgba(0,0,0,0.6);
                font-family: inherit;
                font-size: 12px;
                font-weight: 700;
                color: #38bdf8;
                user-select: none;
                transition: transform 0.15s, box-shadow 0.15s;
            }
            #__af_card_mini__:hover {
                transform: scale(1.05);
                box-shadow: 0 6px 24px rgba(59,130,246,0.35);
            }
            #__af_toast__ {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(40px);
                background: #0f172a;
                border: 1px solid #22c55e;
                color: #86efac;
                font-size: 12px;
                font-weight: 600;
                padding: 7px 18px;
                border-radius: 20px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                pointer-events: none;
                transition: transform 0.25s, opacity 0.25s;
                opacity: 0;
                z-index: 2147483647;
            }
            #__af_toast__.show {
                transform: translateX(-50%) translateY(0);
                opacity: 1;
            }
        `;
        document.head.appendChild(style);

        // Toast element
        let toastEl = document.getElementById('__af_toast__');
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.id = '__af_toast__';
            document.body.appendChild(toastEl);
        }

        function showToast(msg) {
            toastEl.textContent = msg;
            toastEl.classList.add('show');
            setTimeout(() => { toastEl.classList.remove('show'); }, 1800);
        }

        // Mini pill
        const mini = document.createElement('div');
        mini.id = '__af_card_mini__';
        mini.innerHTML = `<span>📍</span><span>Địa chỉ (Copy tay)</span><span style="font-size:10px;color:#94a3b8;background:#1e293b;padding:2px 6px;border-radius:10px;">Mở</span>`;
        document.body.appendChild(mini);

        // Main card
        const card = document.createElement('div');
        card.id = '__af_address_card__';
        card.innerHTML = `
            <div id="__af_card_header__">
                <div class="af-card-title">
                    <span>📍</span>
                    <span>Địa chỉ thanh toán</span>
                    <span class="af-badge-off" title="Tự động fill đã được tắt theo yêu cầu. Vui lòng bấm Copy để dán tay!">TỰ ĐIỀN: TẮT</span>
                </div>
                <div class="af-header-btns">
                    <button class="af-icon-btn" id="__af_btn_minimize__" title="Thu nhỏ">−</button>
                </div>
            </div>
            <div id="__af_card_body__">
                <div class="af-notice">
                    ✍️ <b>Tự động điền đã tắt</b> để tránh Stripe phát hiện. Bấm <b>Copy</b> hoặc bấm trực tiếp vào chữ để dán vào form:
                </div>
                
                <div class="af-field-row" data-field="name">
                    <div class="af-field-meta" title="Click để copy">
                        <span class="af-field-label">Tên trên thẻ</span>
                        <span class="af-field-val" id="__af_val_name__">${currentAddress.name}</span>
                    </div>
                    <button class="af-copy-btn" id="__af_cp_name__">📋 Copy</button>
                </div>

                <div class="af-field-row" data-field="address1">
                    <div class="af-field-meta" title="Click để copy">
                        <span class="af-field-label">Địa chỉ dòng 1</span>
                        <span class="af-field-val" id="__af_val_addr__">${currentAddress.address1}</span>
                    </div>
                    <button class="af-copy-btn" id="__af_cp_addr__">📋 Copy</button>
                </div>

                <div class="af-field-row" data-field="city">
                    <div class="af-field-meta" title="Click để copy">
                        <span class="af-field-label">Thành phố</span>
                        <span class="af-field-val" id="__af_val_city__">${currentAddress.city}</span>
                    </div>
                    <button class="af-copy-btn" id="__af_cp_city__">📋 Copy</button>
                </div>

                <div class="af-field-row" data-field="zip">
                    <div class="af-field-meta" title="Click để copy">
                        <span class="af-field-label">Mã bưu điện (Zip)</span>
                        <span class="af-field-val" id="__af_val_zip__">${currentAddress.zip}</span>
                    </div>
                    <button class="af-copy-btn" id="__af_cp_zip__">📋 Copy</button>
                </div>

                <div class="af-field-row" data-field="state">
                    <div class="af-field-meta" title="Click để copy">
                        <span class="af-field-label">Tỉnh / Thành</span>
                        <span class="af-field-val" id="__af_val_state__">${currentAddress.state}</span>
                    </div>
                    <button class="af-copy-btn" id="__af_cp_state__">📋 Copy</button>
                </div>

                <div class="af-btn-group">
                    <button class="af-action-btn af-btn-refresh" id="__af_btn_refresh__" title="Tạo ngẫu nhiên một địa chỉ mới">
                        🔄 Đổi địa chỉ
                    </button>
                    <button class="af-action-btn af-btn-copyall" id="__af_btn_copyall__" title="Copy toàn bộ thông tin địa chỉ">
                        📋 Copy tất cả
                    </button>
                </div>

                <div style="margin-top:2px; display:flex; justify-content:center;">
                    <button class="af-action-btn af-btn-fill" id="__af_btn_fill__" title="Nếu bạn vẫn muốn tiện lợi tự điền tự động vào form thì bấm nút này">
                        ⚡ Điền tự động vào form (Tùy chọn)
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(card);

        // Update card contents
        function updateCardUI(addr) {
            currentAddress = addr;
            document.getElementById('__af_val_name__').textContent = addr.name;
            document.getElementById('__af_val_addr__').textContent = addr.address1;
            document.getElementById('__af_val_city__').textContent = addr.city;
            document.getElementById('__af_val_zip__').textContent = addr.zip;
            document.getElementById('__af_val_state__').textContent = addr.state;
        }

        // Copy button handler
        function attachCopyHandler(btnId, textGetter, label) {
            const btn = document.getElementById(btnId);
            if (!btn) return;
            btn.onclick = async (e) => {
                e.stopPropagation();
                let text = textGetter();
                if (!text && currentAddress) {
                    text = currentAddress.address1 || currentAddress.name || '';
                }
                if (!text) return;
                const ok = await copyToClipboard(text);
                if (ok) {
                    btn.textContent = '✓ Đã copy';
                    btn.classList.add('copied');
                    showToast(`✓ Đã copy ${label}: ${text}`);
                    setTimeout(() => {
                        btn.textContent = '📋 Copy';
                        btn.classList.remove('copied');
                    }, 1400);
                } else {
                    showToast(`⚠️ Lỗi copy ${label}`);
                }
            };
        }

        attachCopyHandler('__af_cp_name__', () => currentAddress?.name || document.getElementById('__af_val_name__')?.textContent, 'Tên');
        attachCopyHandler('__af_cp_addr__', () => currentAddress?.address1 || document.getElementById('__af_val_addr__')?.textContent, 'Địa chỉ');
        attachCopyHandler('__af_cp_city__', () => currentAddress?.city || document.getElementById('__af_val_city__')?.textContent, 'Thành phố');
        attachCopyHandler('__af_cp_zip__', () => currentAddress?.zip || document.getElementById('__af_val_zip__')?.textContent, 'Mã Zip');
        attachCopyHandler('__af_cp_state__', () => currentAddress?.state || document.getElementById('__af_val_state__')?.textContent, 'Tỉnh / Thành');

        // Click trực tiếp vào dòng chữ cũng copy
        card.querySelectorAll('.af-field-meta').forEach(meta => {
            meta.onclick = async () => {
                const valEl = meta.querySelector('.af-field-val');
                const labelEl = meta.querySelector('.af-field-label');
                if (valEl && valEl.textContent) {
                    const text = valEl.textContent.trim();
                    const ok = await copyToClipboard(text);
                    if (ok) {
                        showToast(`✓ Đã copy ${labelEl?.textContent || ''}: ${text}`);
                    }
                }
            };
        });

        // Nút Đổi địa chỉ
        const refreshBtn = document.getElementById('__af_btn_refresh__');
        refreshBtn.onclick = () => {
            const newAddr = generateRandomAddress();
            updateCardUI(newAddr);
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                chrome.storage.local.set({ current_checkout_address: newAddr });
            }
            showToast('🔄 Đã tạo địa chỉ mới!');
        };

        // Nút Copy tất cả
        const copyAllBtn = document.getElementById('__af_btn_copyall__');
        copyAllBtn.onclick = async () => {
            const cName = currentAddress?.name || document.getElementById('__af_val_name__')?.textContent || '';
            const cAddr = currentAddress?.address1 || document.getElementById('__af_val_addr__')?.textContent || '';
            const cCity = currentAddress?.city || document.getElementById('__af_val_city__')?.textContent || '';
            const cZip = currentAddress?.zip || document.getElementById('__af_val_zip__')?.textContent || '';
            const cState = currentAddress?.state || document.getElementById('__af_val_state__')?.textContent || '';
            const text = [
                `Tên: ${cName}`,
                `Địa chỉ: ${cAddr}`,
                `Thành phố: ${cCity}`,
                `Zip: ${cZip}`,
                `Bang: ${cState}`
            ].join('\n');
            const ok = await copyToClipboard(text);
            if (ok) {
                showToast('✓ Đã copy tất cả thông tin địa chỉ!');
            }
        };

        // Nút Điền tự động (Chỉ chạy khi người dùng chủ động bấm)
        const fillBtn = document.getElementById('__af_btn_fill__');
        fillBtn.onclick = () => {
            fillBtn.disabled = true;
            fillBtn.textContent = '⏳ Đang gửi lệnh điền...';
            broadcastRefill(currentAddress);
            showToast('⚡ Đang điền vào form thanh toán...');
            setTimeout(() => {
                fillBtn.disabled = false;
                fillBtn.textContent = '⚡ Điền tự động vào form (Tùy chọn)';
            }, 2000);
        };

        // Thu nhỏ / Mở rộng
        const minBtn = document.getElementById('__af_btn_minimize__');
        minBtn.onclick = () => {
            card.style.display = 'none';
            mini.style.display = 'flex';
        };
        mini.onclick = () => {
            card.style.display = '';
            mini.style.display = 'none';
        };

        // Kéo thả Draggable
        (function makeDraggable(panel, handle) {
            let isDragging = false, startX, startY, origLeft, origTop;
            handle.addEventListener('mousedown', (e) => {
                if (e.button !== 0 || e.target.tagName === 'BUTTON') return;
                isDragging = true;
                const rect = panel.getBoundingClientRect();
                panel.style.left = rect.left + 'px';
                panel.style.top = rect.top + 'px';
                panel.style.bottom = 'auto';
                panel.style.right = 'auto';
                startX = e.clientX;
                startY = e.clientY;
                origLeft = rect.left;
                origTop = rect.top;
                e.preventDefault();
            });
            document.addEventListener('mousemove', (e) => {
                if (!isDragging) return;
                panel.style.left = (origLeft + e.clientX - startX) + 'px';
                panel.style.top = (origTop + e.clientY - startY) + 'px';
            });
            document.addEventListener('mouseup', () => { isDragging = false; });
        })(card, document.getElementById('__af_card_header__'));

        console.log('[AutoFill] Đã hiển thị Card địa chỉ (chế độ copy tay, tự động điền: ĐÃ TẮT).');
    }

    // ─── Listeners cho lệnh đổi địa chỉ từ popup hoặc login.js ─────────────────
    window.addEventListener('message', async (e) => {
        if (!e.data) return;
        if (e.data.type === 'CHATGPT_AUTOFILL_REFILL') {
            if (isStripe) {
                console.log('[AutoFill] Nhận lệnh refill thủ công qua postMessage (Stripe frame)');
                let addr = e.data.address;
                if (!addr && typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                    try {
                        const res = await chrome.storage.local.get(['current_checkout_address']);
                        addr = res.current_checkout_address;
                    } catch (err) { }
                }
                autoFillForm(true, addr);
            }
        } else if (e.data.type === 'CHATGPT_UPDATE_ADDRESS_CARD') {
            if (isCheckout && e.data.address) {
                currentAddress = e.data.address;
                const nameEl = document.getElementById('__af_val_name__');
                if (nameEl) {
                    document.getElementById('__af_val_name__').textContent = currentAddress.name;
                    document.getElementById('__af_val_addr__').textContent = currentAddress.address1;
                    document.getElementById('__af_val_city__').textContent = currentAddress.city;
                    document.getElementById('__af_val_zip__').textContent = currentAddress.zip;
                    document.getElementById('__af_val_state__').textContent = currentAddress.state;
                }
            }
        }
    });

    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.onChanged) {
        chrome.storage.onChanged.addListener((changes, area) => {
            if (area === 'local' && changes.current_checkout_address && isCheckout) {
                const addr = changes.current_checkout_address.newValue;
                if (addr) {
                    currentAddress = addr;
                    const nameEl = document.getElementById('__af_val_name__');
                    if (nameEl) {
                        document.getElementById('__af_val_name__').textContent = addr.name;
                        document.getElementById('__af_val_addr__').textContent = addr.address1;
                        document.getElementById('__af_val_city__').textContent = addr.city;
                        document.getElementById('__af_val_zip__').textContent = addr.zip;
                        document.getElementById('__af_val_state__').textContent = addr.state;
                    }
                }
            }
        });
    }

    // ─── Khởi động ─────────────────────────────────────────────────────────────
    function startObserver() {
        if (isStripe) {
            // Trong iframe Stripe: TUYỆT ĐỐI KHÔNG TỰ ĐỘNG ĐIỀN!
            // Chỉ lắng nghe lệnh điền thủ công khi người dùng bấm nút "⚡ Điền tự động vào form"
            console.log('[AutoFill] Stripe iframe sẵn sàng. Tự động fill: ĐÃ TẮT (Chỉ chờ lệnh thủ công hoặc copy tay).');
        } else if (isCheckout) {
            // Trên trang chính chatgpt.com: Kiểm tra xem có đang ở trang checkout không
            const checkAndShowCard = () => {
                const isCheckoutUrl = window.location.pathname.includes('/checkout') ||
                    window.location.search.includes('promo_campaign') ||
                    document.querySelector('iframe[src*="stripe.com"], .StripeElement') !== null;

                if (isCheckoutUrl) {
                    injectAddressCard();
                }
            };

            const obs = new MutationObserver(() => {
                checkAndShowCard();
            });
            if (document.body) obs.observe(document.body, { childList: true, subtree: true });

            checkAndShowCard();
            setTimeout(checkAndShowCard, 1000);
            setTimeout(checkAndShowCard, 2500);
        }
    }

    startObserver();

})();
