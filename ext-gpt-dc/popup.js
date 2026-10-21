const ta           = document.getElementById('ta');
const saveBtn      = document.getElementById('saveBtn');
const clearBtn     = document.getElementById('clearBtn');
const refillBtn    = document.getElementById('refillBtn');
const dot          = document.getElementById('dot');
const statusTx     = document.getElementById('statusTxt');
const totpWrap     = document.getElementById('totpWrap');
const totpCode     = document.getElementById('totpCode');
const timerFill    = document.getElementById('timerFill');
const toast        = document.getElementById('toast');
const copyBtn      = document.getElementById('copyBtn');

const popCopyAllBtn = document.getElementById('popCopyAllBtn');
const popNewAddrBtn = document.getElementById('popNewAddrBtn');
const popName       = document.getElementById('popName');
const popAddr       = document.getElementById('popAddr');
const popCity       = document.getElementById('popCity');
const popZip        = document.getElementById('popZip');

const popCpName     = document.getElementById('popCpName');
const popCpAddr     = document.getElementById('popCpAddr');
const popCpCity     = document.getElementById('popCpCity');
const popCpZip      = document.getElementById('popCpZip');

const popRowName    = document.getElementById('popRowName');
const popRowAddr    = document.getElementById('popRowAddr');
const popRowCity    = document.getElementById('popRowCity');
const popRowZip     = document.getElementById('popRowZip');

let totpInterval = null;
let currentAddress = null;

// ---- Address Helper ----
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
    { city: "Vinh", state: "Nghe An", zip: "460000" }
];

const STREETS = [
    "Nguyễn Huệ", "Lê Lợi", "Trần Hưng Đạo", "Hai Bà Trưng", "Đồng Khởi",
    "Lý Tự Trọng", "Nguyễn Đình Chiểu", "Pasteur", "Lê Duẩn", "Nguyễn Thị Minh Khai",
    "Điện Biên Phủ", "Cách Mạng Tháng Tám", "Nguyễn Trãi", "Võ Văn Tần", "Trương Định"
];

function generateRandomAddress() {
    const firstNames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ"];
    const middleNames = ["Văn", "Thị", "Thanh", "Minh", "Hữu", "Đức", "Ngọc", "Gia", "Bảo", "Thu", "Hồng"];
    const lastNames = ["Anh", "Bình", "Châu", "Dương", "Giang", "Hải", "Khang", "Linh", "Quân", "Sơn", "Tuấn", "Hùng", "Huy", "Tiến"];
    const r = a => a[Math.floor(Math.random() * a.length)];
    const fullName = r(firstNames) + ' ' + r(middleNames) + ' ' + r(lastNames);

    const number = Math.floor(Math.random() * 888) + 12;
    const address1 = 'So ' + number + ' ' + r(STREETS);
    const loc = r(VN_LOCATIONS);

    return {
        name: fullName,
        address1: address1,
        city: loc.city,
        state: loc.state,
        zip: loc.zip
    };
}

function updateAddressUI(addr) {
    if (!addr) return;
    currentAddress = addr;
    if (popName) popName.textContent = addr.name || '';
    if (popAddr) popAddr.textContent = addr.address1 || '';
    if (popCity) popCity.textContent = addr.city || '';
    if (popZip)  popZip.textContent  = addr.zip || '';
}

// Load địa chỉ hiện tại
chrome.storage.local.get(['current_checkout_address'], (res) => {
    if (res && res.current_checkout_address && res.current_checkout_address.name) {
        updateAddressUI(res.current_checkout_address);
    } else {
        const addr = generateRandomAddress();
        chrome.storage.local.set({ current_checkout_address: addr });
        updateAddressUI(addr);
    }
});

function setNewAddress() {
    const addr = generateRandomAddress();
    currentAddress = addr;
    updateAddressUI(addr);
    chrome.storage.local.set({ current_checkout_address: addr }, () => {
        showToast('📍 Đã tạo địa chỉ mới!', 'ok');
    });
    return addr;
}

if (popNewAddrBtn) popNewAddrBtn.onclick = setNewAddress;
if (refillBtn) refillBtn.onclick = setNewAddress;

// ---- Safe Clipboard Helper ----
async function copyToClipboard(text) {
    if (!text) return false;
    // 1. Dùng navigator.clipboard trước
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (e) {
            console.warn('[Popup] navigator.clipboard error:', e);
        }
    }
    // 2. Fallback sang textarea + execCommand
    try {
        const taEl = document.createElement('textarea');
        taEl.value = text;
        taEl.setAttribute('readonly', '');
        taEl.style.position = 'fixed';
        taEl.style.top = '0';
        taEl.style.left = '0';
        taEl.style.opacity = '0';
        taEl.style.pointerEvents = 'none';
        document.body.appendChild(taEl);
        taEl.focus();
        taEl.select();
        taEl.setSelectionRange(0, text.length);
        const ok = document.execCommand('copy');
        document.body.removeChild(taEl);
        return ok;
    } catch (err) {
        console.error('[Popup] fallback copy error:', err);
        return false;
    }
}

// Copy handlers
async function copyField(valGetter, btnEl, label) {
    let text = valGetter();
    if (!text || text === 'Chưa tạo') {
        const newAddr = setNewAddress();
        text = valGetter() || newAddr.name || newAddr.address1;
    }
    if (!text) return;

    const ok = await copyToClipboard(text);
    if (ok) {
        showToast('📋 Đã copy ' + label + ': ' + text, 'ok');
        if (btnEl) {
            btnEl.textContent = '✓';
            btnEl.classList.add('copied');
            setTimeout(() => {
                btnEl.textContent = '📋';
                btnEl.classList.remove('copied');
            }, 1200);
        }
    } else {
        showToast('⚠️ Lỗi copy ' + label, 'err');
    }
}

const getName = () => currentAddress?.name || popName?.textContent;
const getAddr = () => currentAddress?.address1 || popAddr?.textContent;
const getCity = () => currentAddress?.city || popCity?.textContent;
const getZip  = () => currentAddress?.zip  || popZip?.textContent;

if (popCpName)  popCpName.onclick  = (e) => { e.stopPropagation(); copyField(getName, popCpName, 'Tên'); };
if (popCpAddr)  popCpAddr.onclick  = (e) => { e.stopPropagation(); copyField(getAddr, popCpAddr, 'Địa chỉ'); };
if (popCpCity)  popCpCity.onclick  = (e) => { e.stopPropagation(); copyField(getCity, popCpCity, 'Thành phố'); };
if (popCpZip)   popCpZip.onclick   = (e) => { e.stopPropagation(); copyField(getZip,  popCpZip,  'Mã Zip'); };

if (popRowName) popRowName.onclick = () => copyField(getName, popCpName, 'Tên');
if (popRowAddr) popRowAddr.onclick = () => copyField(getAddr, popCpAddr, 'Địa chỉ');
if (popRowCity) popRowCity.onclick = () => copyField(getCity, popCpCity, 'Thành phố');
if (popRowZip)  popRowZip.onclick  = () => copyField(getZip,  popCpZip,  'Mã Zip');

if (popCopyAllBtn) {
    popCopyAllBtn.onclick = async (e) => {
        e.stopPropagation();
        if (!currentAddress || !currentAddress.name) {
            setNewAddress();
        }
        const text = [
            `Tên: ${getName()}`,
            `Địa chỉ: ${getAddr()}`,
            `Thành phố: ${getCity()}`,
            `Zip: ${getZip()}`
        ].join('\n');

        const ok = await copyToClipboard(text);
        if (ok) {
            showToast('📋 Đã copy tất cả thông tin địa chỉ!', 'ok');
            popCopyAllBtn.textContent = '✓ Đã copy';
            setTimeout(() => { popCopyAllBtn.textContent = '📋 Copy hết'; }, 1200);
        } else {
            showToast('⚠️ Lỗi copy địa chỉ!', 'err');
        }
    };
}

// ---- Load tài khoản đã lưu ----
chrome.storage.local.get(['chatgpt_account'], (result) => {
    const acc = result.chatgpt_account;
    if (acc && acc.email) {
        ta.value = [acc.email, acc.password, acc.totp_secret].filter(Boolean).join('\t');
        setStatus(true, acc.email);
        if (acc.totp_secret) startTOTP(acc.totp_secret);
    }
});

// ---- Live parse khi gõ/paste ----
ta.addEventListener('input', () => {
    const acc = parse(ta.value.trim());
    if (acc && acc.totp_secret && acc.totp_secret.length >= 16) {
        startTOTP(acc.totp_secret);
    } else {
        totpWrap.style.display = 'none';
        if (totpInterval) clearInterval(totpInterval);
    }
});

// ---- Lưu ----
saveBtn.addEventListener('click', () => {
    const acc = parse(ta.value.trim());
    if (!acc) { showToast('Sai định dạng! Cần: email  pass  secret', 'err'); return; }
    chrome.storage.local.set({ chatgpt_account: acc }, () => {
        setStatus(true, acc.email);
        showToast('✅ Đã lưu!', 'ok');
        if (acc.totp_secret) startTOTP(acc.totp_secret);
    });
});

// ---- Xóa ----
clearBtn.addEventListener('click', () => {
    chrome.storage.local.remove('chatgpt_account', () => {
        ta.value = '';
        totpWrap.style.display = 'none';
        if (totpInterval) clearInterval(totpInterval);
        setStatus(false);
        showToast('🗑 Đã xóa', 'err');
    });
});

// ---- Copy TOTP ----
copyBtn.onclick = async () => {
    const code = totpCode.textContent?.trim();
    if (code && code !== '------' && code !== 'Lỗi') {
        const ok = await copyToClipboard(code);
        if (ok) {
            showToast('📋 Đã copy mã TOTP!', 'ok');
            copyBtn.textContent = '✓';
            setTimeout(() => { copyBtn.textContent = '📋 Copy'; }, 1200);
        } else {
            showToast('⚠️ Lỗi copy TOTP', 'err');
        }
    }
};

// ---- Parse raw line ----
function parse(raw) {
    if (!raw) return null;
    const parts = raw.split(/\t+|\s{2,}|\|/);
    if (parts.length < 2 || !parts[0].includes('@')) return null;
    return {
        email:       parts[0].trim(),
        password:    parts[1].trim(),
        totp_secret: (parts[2] || '').trim().toUpperCase().replace(/\s/g, '')
    };
}

// ---- TOTP display + timer ----
function startTOTP(secret) {
    if (totpInterval) clearInterval(totpInterval);
    totpWrap.style.display = 'block';

    async function refresh() {
        try { totpCode.textContent = await generateTOTP(secret); }
        catch(e) { totpCode.textContent = 'Lỗi'; }
    }

    function tick() {
        const rem = 30 - (Math.floor(Date.now() / 1000) % 30);
        timerFill.style.width = (rem / 30 * 100) + '%';
        timerFill.style.background = rem > 10
            ? 'linear-gradient(90deg, #4caf50, #8bc34a)'
            : 'linear-gradient(90deg, #f39c12, #e74c3c)';
        if (Math.floor(Date.now() / 1000) % 30 === 0) refresh();
    }

    refresh();
    tick();
    totpInterval = setInterval(tick, 1000);
}

// ---- Status ----
function setStatus(ok, email) {
    dot.className = 'dot ' + (ok ? 'ok' : 'warn');
    statusTx.textContent = ok ? ('✓ ' + email) : 'Chưa có tài khoản nào được lưu';
}

// ---- Toast ----
function showToast(msg, type) {
    toast.textContent = msg;
    toast.className = 'toast ' + (type || '') + ' show';
    setTimeout(() => { toast.className = 'toast'; }, 2200);
}
