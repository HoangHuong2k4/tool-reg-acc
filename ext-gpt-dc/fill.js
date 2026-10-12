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
        element.focus();
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        await new Promise(r => setTimeout(r, 80));
        for (let i = 0; i < text.length; i++) {
            element.value += text[i];
            element.dispatchEvent(new Event('input',  { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            await new Promise(r => setTimeout(r, Math.random() * 50 + 30));
        }
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

        const SEL_NAME  = 'input[name="name"], input[autocomplete="name"], input[id*="billingName"], input[data-elements-stable-field-name="billingName"]';
        const SEL_ADDR  = 'input[name="addressLine1"], input[autocomplete="address-line1"], input[id*="billingAddressLine1"], input[name="address1"], input[id*="addressLine1"]';
        const SEL_CITY  = 'input[name="locality"], input[autocomplete="address-level2"], input[name="city"], input[id*="billingLocality"]';
        const SEL_ZIP   = 'input[name="postalCode"], input[autocomplete="postal-code"], input[name="zip"], input[name="postal_code"], input[id*="billingPostalCode"]';
        const SEL_STATE = 'select[name="administrativeArea"], select[autocomplete*="address-level1"], select[name="state"], select[id*="billingAdministrativeArea"]';

        const nameInput = document.querySelector(SEL_NAME);
        const addrInput = document.querySelector(SEL_ADDR);

        if (!nameInput && !addrInput) {
            console.log('[AutoFill] Khong tim thay o nhap lieu Stripe tren frame nay.');
            return;
        }

        isFilling = true;
        updateFloatingStatus('Dang dien dia chi...');
        console.log('[AutoFill] Bat dau fill form (KHONG auto click/submit)');

        // 1. Ten
        if (nameInput && (!nameInput.value || forceRefill)) {
            await simulateTyping(nameInput, getRandomName());
            await new Promise(r => setTimeout(r, 400));
        }

        // 2. Dia chi dong 1
        if (addrInput && (!addrInput.value || forceRefill)) {
            await simulateTyping(addrInput, getRandomAddress1());
            await new Promise(r => setTimeout(r, 900));

            // 3. Thanh pho
            const cityInput = document.querySelector(SEL_CITY);
            if (cityInput && (!cityInput.value || forceRefill)) {
                await simulateTyping(cityInput, getRandomCity());
                await new Promise(r => setTimeout(r, 300));
            }

            // 4. Zip
            const zipInput = document.querySelector(SEL_ZIP);
            if (zipInput && (!zipInput.value || forceRefill)) {
                await simulateTyping(zipInput, getRandomZip());
                await new Promise(r => setTimeout(r, 300));
            }

            // 5. State dropdown (neu co)
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

        console.log('[AutoFill] Hoan thanh fill -- KHONG click submit/checkout.');
        updateFloatingStatus('Da dien xong dia chi!');
        isFilling = false;
    }

    // ─── Floating button "Doi dia chi" (chi inject o chatgpt.com, khong vao iframe) ──
    function injectFloatingButton() {
        if (document.getElementById('__af_float__')) return;

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
        statusDiv.textContent = 'San sang dien dia chi';
        floatStatusEl = statusDiv;

        const btn = document.createElement('button');
        btn.id = '__af_btn__';
        btn.textContent = '\uD83D\uDD04 Doi dia chi';
        btn.title = 'Dien ngau nhien dia chi moi vao form thanh toan Stripe (khong tu bam nut thanh toan)';

        btn.onclick = async () => {
            if (isFilling) return;
            btn.disabled = true;
            await autoFillForm(true);
            setTimeout(() => { btn.disabled = false; }, 1500);
        };

        wrap.appendChild(statusDiv);
        wrap.appendChild(btn);
        document.body.appendChild(wrap);
        console.log('[AutoFill] Da inject nut "Doi dia chi" vao trang checkout.');
    }

    // ─── Khoi dong ─────────────────────────────────────────────────────────────
    const FORM_PROBE = 'input[name="name"], input[name="addressLine1"], input[autocomplete="address-line1"], input[id*="billingAddressLine1"]';

    function startObserver() {
        const obs = new MutationObserver((_m, o) => {
            if (document.querySelector(FORM_PROBE)) {
                o.disconnect();
                setTimeout(() => autoFillForm(false), 900);
            }
        });
        if (document.body) obs.observe(document.body, { childList: true, subtree: true });
    }

    if (isCheckout) {
        if (document.body) injectFloatingButton();
        else document.addEventListener('DOMContentLoaded', injectFloatingButton);
    }

    startObserver();
    setTimeout(() => {
        if (document.querySelector(FORM_PROBE)) {
            autoFillForm(false);
        } else {
            setTimeout(() => {
                if (document.querySelector(FORM_PROBE)) autoFillForm(false);
            }, 2000);
        }
    }, 1200);

})();
