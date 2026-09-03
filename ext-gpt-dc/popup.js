const ta       = document.getElementById('ta');
const saveBtn  = document.getElementById('saveBtn');
const clearBtn = document.getElementById('clearBtn');
const dot      = document.getElementById('dot');
const statusTx = document.getElementById('statusTxt');
const totpWrap = document.getElementById('totpWrap');
const totpCode = document.getElementById('totpCode');
const timerFill = document.getElementById('timerFill');
const toast    = document.getElementById('toast');
const copyBtn  = document.getElementById('copyBtn');

let totpInterval = null;

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
copyBtn.onclick = () => {
    const code = totpCode.textContent;
    if (code && code !== '------') {
        navigator.clipboard.writeText(code).then(() => showToast('📋 Đã copy!', 'ok'));
    }
};

// ---- Parse raw line ----
function parse(raw) {
    if (!raw) return null;
    const parts = raw.split(/\t+|\s{2,}/);
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
