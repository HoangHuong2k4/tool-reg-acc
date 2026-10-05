// ===================== GROK =====================
let grkIsRunning = false;
let grkEvt = null;
let grkMailType = 'hotmail';
let grkApiSource = 'mixmmo';
let grkBrowserType = 'uc';
let grkLanguage = 'ko-KR';
let grkHeadless = false;
let grkOpenPayment = true;
let grkApplePay = false;
let grkPaymentMode = 'masa'; // 'masa' = Masa168 tự động | 'manual' = quét tay qua Telegram
let grkSessionMode = 'session';
let grkFilter = 'ALL';
let grkTotal = 0, grkOk = 0, grkFail = 0;

function grkSetMailType(t) {
  grkMailType = t;
  ['grk-mailHotmail','grk-mailDomain','grk-mailBilling'].forEach(id => {
      let el = document.getElementById(id);
      if(el) el.classList.remove('active');
  });
  
  const map = {hotmail: 'grk-mailHotmail', domain: 'grk-mailDomain', billing: 'grk-mailBilling'};
  let activeEl = document.getElementById(map[t]);
  if(activeEl) activeEl.classList.add('active');

  const hGroup = document.getElementById('grk-hotmailGroup');
  const dGroup = document.getElementById('grk-domainGroup');
  const apiGroup = document.getElementById('grk-apiSourceGroup');
  const bGroup = document.getElementById('grk-billingGroup');
  const paymentGroup = document.getElementById('grk-openPaymentGroup');
  
  if (hGroup) hGroup.style.display = t === 'hotmail' ? '' : 'none';
  if (dGroup) dGroup.style.display = t === 'domain' ? '' : 'none';
  if (apiGroup) apiGroup.style.display = t === 'hotmail' ? '' : 'none';
  if (bGroup) bGroup.style.display = t === 'billing' ? '' : 'none';
  if (paymentGroup) paymentGroup.style.display = t === 'billing' ? 'none' : '';
}

function grkSetApiSource(s) {
  grkApiSource = s;
  ['grk-sourceDongvanfb','grk-sourceMixmmo'].forEach(id => document.getElementById(id).classList.remove('active'));
  document.getElementById(s === 'dongvanfb' ? 'grk-sourceDongvanfb' : 'grk-sourceMixmmo').classList.add('active');
}

function grkSetBrowser(b) {
  grkBrowserType = b;
  ['grk-browserUc','grk-browserChrome','grk-browserFirefox'].forEach(id => { const el = document.getElementById(id); if(el) el.classList.remove('active'); });
  const map = {uc: 'grk-browserUc', chrome: 'grk-browserChrome', firefox: 'grk-browserFirefox'};
  const el = document.getElementById(map[b]);
  if (el) el.classList.add('active');
}

function grkSetLanguage(lang) {
  grkLanguage = lang;
  const us = document.getElementById('grk-langUs');
  const ko = document.getElementById('grk-langKo');
  if(us) us.classList.toggle('active', lang === 'en-US');
  if(ko) ko.classList.toggle('active', lang === 'ko-KR');
}

function grkToggleHeadless() {
  grkHeadless = !grkHeadless;
  const tog = document.getElementById('grk-headlessToggle');
  if(tog) tog.classList.toggle('active', grkHeadless);
}

function grkToggleOpenPayment() {
  grkOpenPayment = !grkOpenPayment;
  if(grkOpenPayment) {
    grkApplePay = false;
    document.getElementById('grk-applePayToggle')?.classList.remove('active');
  }
  const tog = document.getElementById('grk-openPaymentToggle');
  if(tog) tog.classList.toggle('active', grkOpenPayment);
  // Hiện/ẩn panel chế độ thanh toán
  const modeGroup = document.getElementById('grk-paymentModeGroup');
  if(modeGroup) modeGroup.style.display = grkOpenPayment ? '' : 'none';
}

function grkToggleApplePay() {
  grkApplePay = !grkApplePay;
  if(grkApplePay) {
    grkOpenPayment = false;
    document.getElementById('grk-openPaymentToggle')?.classList.remove('active');
    document.getElementById('grk-paymentModeGroup').style.display = 'none';
  }
  const tog = document.getElementById('grk-applePayToggle');
  if(tog) tog.classList.toggle('active', grkApplePay);
}

function grkSetPaymentMode(mode) {
  grkPaymentMode = mode;
  document.getElementById('grk-payModeMasa')?.classList.toggle('active', mode === 'masa');
  document.getElementById('grk-payModeManual')?.classList.toggle('active', mode === 'manual');
  const hint = document.getElementById('grk-payModeHint');
  if(hint) hint.textContent = mode === 'masa'
    ? 'Link NicePay sẽ được gửi lên Masa168 để quét tự động'
    : 'Link NicePay sẽ được gửi qua Telegram — không gọi API Masa168';
}

async function grkLoadHotmailCount() {
  try {
    const r = await fetch('/api/grok/hotmail/count');
    const d = await r.json();
    const c = d.count || 0;
    const badge = document.getElementById('grk-hotmailCountBadge');
    const label = document.getElementById('grk-hotmailCountLabel');
    const stat  = document.getElementById('grk-statHotmail');
    if(badge) badge.style.display = '';
    if(label) label.textContent = c;
    if(stat)  stat.textContent = c;
  } catch(e) {}
}

async function grkLoadBillingCount() {
  try {
    const r = await fetch('/api/grok/billing/count');
    const d = await r.json();
    const c = d.count || 0;
    const badge = document.getElementById('grk-billingCountBadge');
    const label = document.getElementById('grk-billingCountLabel');
    if(badge) badge.style.display = '';
    if(label) label.textContent = c;
  } catch(e) {}
}

async function grkUploadHotmail(input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/api/grok/hotmail/upload', { method: 'POST', body: fd });
    const d = await r.json();
    showToast('✅', `Đã upload ${d.count} hotmail Grok!`);
    grkLoadHotmailCount();
    input.value = '';
  } catch(e) { showToast('❌', 'Lỗi upload!'); }
}

function grkAppendLog(entry) {
  const wrap = document.getElementById('grk-logWrap');
  if (!wrap) return;
  const icons = {OK:'✅',WARN:'⚠️',ERR:'❌',INFO:'📌'};
  const classes = {OK:'log-ok',WARN:'log-warn',ERR:'log-err',INFO:'log-info'};
  const lvl = entry.level || 'INFO';
  if (grkFilter !== 'ALL' && lvl !== grkFilter) return;
  const div = document.createElement('div');
  div.className = `log-entry ${classes[lvl]||'log-info'}`;
  div.innerHTML = `<span class="log-time">${entry.time||''}</span><span class="log-icon">${icons[lvl]||'📌'}</span><span class="log-msg">${escHtml(entry.msg||'')}</span>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function grkSetFilter(f, btn) {
  grkFilter = f;
  document.querySelectorAll('#tab-grok .log-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
}

function grkClearLog() {
  const wrap = document.getElementById('grk-logWrap');
  if (wrap) wrap.innerHTML = '';
}

function grkSetStatus(running) {
  grkIsRunning = running;
  const dot = document.getElementById('grk-statusDot');
  const txt = document.getElementById('grk-statusText');
  const startBtn = document.getElementById('grk-startBtn');
  const stopBtn = document.getElementById('grk-stopBtn');
  if(dot) dot.classList.toggle('active', running);
  if(txt) txt.textContent = running ? 'Đang chạy...' : 'Idle';
  if(startBtn) startBtn.style.display = running ? 'none' : '';
  if(stopBtn) stopBtn.style.display = running ? '' : 'none';
}

async function grkStartTask() {
  if (grkIsRunning) return;
  let count = parseInt(document.getElementById('grk-count').value) || 3;
  if (grkMailType === 'billing') {
    try {
      const r = await fetch('/api/grok/billing/count');
      const d = await r.json();
      count = d.count || count;
    } catch(e) {}
  }
  const threads = parseInt(document.getElementById('grk-threads').value) || 3;
  grkTotal = count; grkOk = 0; grkFail = 0;
  const pct = document.getElementById('grk-statPct');
  const bar = document.getElementById('grk-progressBar');
  if(pct) pct.textContent = '0%';
  if(bar) bar.style.width = '0%';
  document.getElementById('grk-statOk').textContent = '0';
  document.getElementById('grk-statOk').textContent = '0';
  document.getElementById('grk-statFail').textContent = '0';
  
  let cards = [];
  if (grkMailType === 'billing') {
    const cardsText = document.getElementById('grk-cardsInput').value || '';
    cards = cardsText.split('\n').map(c => c.trim()).filter(c => c);
  }

  try {
    const r = await fetch('/api/grok/task/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ count, threads, mail_type: grkMailType, mail_api_source: grkApiSource, browser_type: grkBrowserType, headless: grkHeadless, open_payment: grkOpenPayment, apple_pay: grkApplePay, language: grkLanguage, cards, payment_mode: grkPaymentMode })
    });
    const d = await r.json();
    if (!d.success) { showToast('❌', d.error || 'Lỗi khởi động'); return; }
    grkSetStatus(true);
    grkStartStream();
  } catch(e) { showToast('❌', 'Lỗi kết nối'); }
}

function grkStartStream() {
  if (grkEvt) { grkEvt.close(); grkEvt = null; }
  grkEvt = new EventSource('/api/grok/task/stream');
  grkEvt.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      if (d.type === 'ping') return;
      if (d.type === 'log') {
        grkAppendLog(d);
      } else if (d.type === 'result') {
        if (d.success) { grkOk++; document.getElementById('grk-statOk').textContent = grkOk; }
        else { grkFail++; document.getElementById('grk-statFail').textContent = grkFail; }
        const done = grkOk + grkFail;
        const pct = grkTotal > 0 ? Math.round(done / grkTotal * 100) : 0;
        const pctEl = document.getElementById('grk-statPct');
        const barEl = document.getElementById('grk-progressBar');
        if(pctEl) pctEl.textContent = pct + '%';
        if(barEl) barEl.style.width = pct + '%';
      } else if (d.type === 'done' || d.type === 'stopped') {
        grkSetStatus(false);
        grkLoadAccounts();
        grkLoadHotmailCount();
        grkLoadBillingCount();
        // Không close EventSource ở đây để UI vẫn nhận được log từ tiến trình chạy ngầm (ví dụ: Masa168 check thanh toán)
        showToast('✅', `Grok xong: ${grkOk} thành công / ${grkFail} thất bại`);
      } else if (d.type === 'account') {
        grkLoadAccounts();
      }
    } catch(ex) {}
  };
  grkEvt.onerror = () => { if(grkIsRunning) setTimeout(grkStartStream, 3000); };
}

async function grkStopTask() {
  await fetch('/api/grok/task/stop', { method: 'POST' });
  grkSetStatus(false);
  if (grkEvt) { grkEvt.close(); grkEvt = null; }
  showToast('⏹', 'Đã dừng Grok!');
}

async function grkCloseBrowsers() {
  await fetch('/api/grok/task/close_browsers', { method: 'POST' });
  showToast('💥', 'Đã đóng trình duyệt Grok!');
}

function grkSetAccountsTab(mode) {
  grkSessionMode = mode;
  const s = document.getElementById('grk-tabAccountsSession');
  const a = document.getElementById('grk-tabAccountsAll');
  if(s) s.classList.toggle('active', mode === 'session');
  if(a) a.classList.toggle('active', mode === 'all');
  grkLoadAccounts();
}

async function grkLoadAccounts() {
  try {
    const r = await fetch(`/api/grok/accounts?session=${grkSessionMode === 'session'}`);
    const d = await r.json();
    const tbody = document.getElementById('grk-accountsBody');
    if (!tbody) return;
    if (!d.accounts || !d.accounts.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px;">Chưa có tài khoản nào</td></tr>';
      return;
    }
    const selectAllCheck = document.getElementById('grk-selectAllAccs');
    if (selectAllCheck) selectAllCheck.checked = false;
    
    tbody.innerHTML = d.accounts.map((acc, i) => `
      <tr>
        <td style="text-align: center;"><input type="checkbox" class="grk-acc-checkbox" data-email="${escHtml(acc.email||'')}" data-password="${escHtml(acc.password||'')}"></td>
        <td><span class="mono">${escHtml(acc.email||'')}</span></td>
        <td><span class="mono">${escHtml(acc.password||'')}</span></td>
        <td><span class="badge badge-ok">✅</span></td>
        <td style="text-align: right;">
          <button class="btn-secondary btn" style="padding: 2px 8px; font-size: 10px; border-color: #10b981; color: #10b981; margin-right: 4px;" onclick="grkChangeCardActiveTab('${escHtml(acc.email||'')}')">⚡ Tab mở</button>
          <button class="btn-secondary btn" style="padding: 2px 8px; font-size: 10px; border-color: var(--accent); color: var(--accent);" onclick="grkChangeSingleCard('${escHtml(acc.email||'')}', '${escHtml(acc.password||'')}')">💳 Đổi thẻ</button>
        </td>
      </tr>`).join('');
  } catch(e) {}
}

function grkToggleSelectAll(chk) {
  const cbs = document.querySelectorAll('.grk-acc-checkbox');
  cbs.forEach(c => c.checked = chk.checked);
}

async function grkExecuteChangeCards(accs) {
  if (!accs.length) return;
  
  // Create file content
  const lines = accs.map(a => `${a.email}|${a.password}`).join('\n');
  
  // Upload to grok billing endpoint
  try {
    const formData = new FormData();
    const blob = new Blob([lines], { type: 'text/plain' });
    formData.append("file", blob, "grok_billing.txt");
    
    // For grok billing we have an upload API: /api/grok/billing/upload
    // Wait, the API uses request.json.get("data")! Let's check how it's defined.
    // In app.py: request.json.get("data", "")
    const res = await fetch('/api/grok/billing/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: lines })
    });
    
    const r = await res.json();
    if (r.success) {
      // Switch to billing mode
      grkSetMailType('billing');
      // Scroll to top
      document.querySelector('.main-content').scrollTo({top: 0, behavior: 'smooth'});
      showToast('💳', `Đã chuyển ${accs.length} tài khoản sang chế độ Lấy Link Billing!\nHãy điền thẻ và bấm BẮT ĐẦU.`);
    } else {
      showToast('❌', 'Lỗi khi lưu tài khoản Billing');
    }
  } catch (e) {
    console.error(e);
    showToast('❌', 'Có lỗi xảy ra!');
  }
}

function grkChangeSingleCard(email, password) {
  showConfirmModal(
    'Xác nhận đổi thẻ', 
    `Bạn có chắc muốn đẩy tài khoản ${email} sang chế độ đổi thẻ?`, 
    () => grkExecuteChangeCards([{email, password}]), 
    'Đổi thẻ'
  );
}

function grkChangeCardsBulk() {
  const cbs = document.querySelectorAll('.grk-acc-checkbox:checked');
  if (cbs.length === 0) {
    return showToast('⚠️', 'Vui lòng chọn ít nhất 1 tài khoản!');
  }
  
  const accs = [];
  cbs.forEach(c => {
    accs.push({
      email: c.getAttribute('data-email'),
      password: c.getAttribute('data-password')
    });
  });
  
  showConfirmModal(
    'Xác nhận đổi thẻ hàng loạt', 
    `Bạn có chắc muốn đẩy ${accs.length} tài khoản đã chọn sang chế độ đổi thẻ?`, 
    () => grkExecuteChangeCards(accs), 
    'Đổi thẻ'
  );
}

async function grkCopyAccounts() {
  try {
    const r = await fetch(`/api/grok/accounts/raw?session=${grkSessionMode === 'session'}`);
    const t = await r.text();
    await navigator.clipboard.writeText(t);
    showToast('📋', 'Đã copy tài khoản Grok!');
  } catch(e) { showToast('❌', 'Lỗi copy!'); }
}

async function grkClearAccounts() {
  showConfirmModal('Xóa tài khoản', 'Xóa tất cả tài khoản Grok?', async () => {
    await fetch('/api/grok/accounts/clear', { method: 'POST' });
    grkLoadAccounts();
    showToast('🗑️', 'Đã xóa tài khoản Grok!');
  }, 'Xóa');
}
